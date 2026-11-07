"""Fonctions partagées par les pages : lecture des sorties du moteur, formats, couleurs, cartes,
et lancement des commandes du moteur (python -m prairimetre ...).

Règle des données manquantes : on n'affiche jamais une case vide ou « None » ; chaque absence
est remplacée par sa raison (« moins de 20 ha de prairies », « non renseigné dans le Sandre »...).
"""
import os
import re
import subprocess
import sys

import pandas as pd
import pydeck as pdk
import streamlit as st

from prairimetre.config import CACHE, DATA, MIN_HA, RACINE, SORTIES, annees
from prairimetre.sources import SOURCES

TABLES = ["communes", "communes_zones", "serie_region", "captages", "communes_captages",
          "bilan_direct", "cultures_destination", "objectif", "suivi_sorties"]

# Chiffre officiel (vérifié sur Légifrance le 22/10/2026)
OFFICIEL = {"perte_ha": -59703, "perte_pct": -8.9, "ratio_evol_pct": -1.97,
            "date": "septembre 2026",
            "source": "Arrêté du 11 septembre 2026, JORF n° 0218 du 18 septembre 2026"}
# Baisse du ratio de prairies permanentes au-delà de laquelle tout retournement est interdit et les
# prairies retournées doivent être réimplantées (règlement délégué (UE) 2022/126, article 48)
SEUIL_RATIO_PCT = 5

DEPARTEMENTS = {"14": "Calvados", "27": "Eure", "50": "Manche", "61": "Orne",
                "76": "Seine-Maritime"}
# « les communes du Calvados », « de l'Eure »... (filtre Territoire des pages)

# Palette catégorielle : contraste ≥ 3:1 sur les fonds clair et sombre (vert assombri pour
# l'atteindre) ; chaque couleur est toujours doublée d'un libellé.
CAT = ["#2a78d6", "#eb6834", "#169c6c"]
NEUTRE = "#c3c2b7"
# Cartes (fond de carte blanc) : les mêmes états partout
HORS = "#a9a89f"     # des données, mais hors de la liste affichée
GRIS = "#6b6a65"     # pas de diagnostic : peu ou pas de prairies (villes, zones d'activité,
                     # communes de cultures). Le registre les couvre : ce n'est pas un manque
# Parcelles de « Ma commune » : une couleur par devenir, lisible sur fond blanc
FLUX_COULEURS = {"culture": "#c2452d", "non déclaré": "#f0a202", "prairie temporaire": "#2a78d6",
                 "prairie permanente": "#2e7d4f", "autre": "#5b5a55", "ajoutée": "#8a4fc4"}

# Les noms et couleurs partagés par les pages : l'objectif 2030, la liste des communes qui portent
# la moitié du retournement récent (son nom est repris par Où aller voir), la vérification.
ACTIONS = {
    "suivre": {"titre": "Suivre l'objectif en hectares", "couleur": CAT[0]},
    "payer": {"titre": "Communes où l'on retourne le plus", "couleur": CAT[0]},
    "verifier": {"titre": "Vérifier d'abord", "couleur": CAT[1]},
}


# --- Formats ----------------------------------------------------------------------------------

def nombre(x, dec=0, signe=False):
    """12 345,6 (espace fine insécable pour les milliers, virgule décimale, vrai signe moins)."""
    if x is None or pd.isna(x):
        return "–"
    s = f"{x:{'+' if signe else ''},.{dec}f}".replace(",", " ").replace(".", ",")
    return s.replace("-", "−")


def ha(x, signe=False):
    return f"{nombre(x, 0, signe)} ha"


def pct(x, dec=1, signe=False):
    return "–" if pd.isna(x) else f"{nombre(100 * x, dec, signe)} %"


def variation(x, unite="ha", dec=0):
    """Delta de st.metric : signe ASCII en tête (Streamlit en déduit flèche et couleur)."""
    if pd.isna(x):
        return None
    return f"{'-' if x < 0 else '+'}{nombre(abs(x), dec)} {unite}".strip()


def nom_propre(x):
    """« SYNDICAT DES EAUX (SITE) » -> « Syndicat des Eaux (SITE) » ; les sigles entre
    parenthèses restent en majuscules, les noms déjà en casse mixte ne changent pas."""
    if not (isinstance(x, str) and x.isupper()):
        return x
    s = x.title()
    for mot in ("De", "Des", "Du", "Et", "La", "Le", "En"):
        s = s.replace(f" {mot} ", f" {mot.lower()} ")
    s = s.replace("L'", "l'").replace("D'", "d'")
    s = re.sub(r"\bAac\b", "AAC", s.replace("_", " "))
    return re.sub(r"\(([^)]*)\)", lambda m: f"({m.group(1).upper()})", s)


def arrondi_ha(x):
    """Ordre de grandeur pour les phrases : 60 050 -> « 60 000 »."""
    if abs(x) >= 10000:
        return nombre(round(x, -3))
    if abs(x) >= 1000:
        return nombre(round(x, -2))
    return nombre(round(x))


# --- Lecture des sorties du moteur ------------------------------------------------------------

def manquantes():
    return [t for t in TABLES if not (SORTIES / f"{t}.csv").exists()]


def table(nom):
    """Table du moteur ; relue dès que le moteur l'a recalculée (date du fichier)."""
    return _lire(nom, (SORTIES / f"{nom}.csv").stat().st_mtime)


@st.cache_data(show_spinner=False)
def _lire(nom, _date):
    if nom == "bilan_direct":
        return pd.read_csv(SORTIES / "bilan_direct.csv", header=[0, 1], index_col=0)
    t = pd.read_csv(SORTIES / f"{nom}.csv", dtype={"insee": str, "epci": str, "dep": str,
                                                   "aac": str})
    cle = {"communes": "insee", "captages": "aac", "cultures_destination": "culture"}.get(nom)
    return t.set_index(cle) if cle else t


def evaluation(nom, **kw):
    """Table d'évaluation du moteur, ou None si « evaluer » n'a pas encore tourné."""
    f = SORTIES / f"evaluation_{nom}.csv"
    return _evaluation(nom, f.stat().st_mtime, **kw) if f.exists() else None


@st.cache_data(show_spinner=False)
def _evaluation(nom, _date, **kw):
    return pd.read_csv(SORTIES / f"evaluation_{nom}.csv", **kw)


def bornes():
    """Première et dernière année des résultats affichés, lues dans sorties/ : les pages restent
    cohérentes même si un registre vient d'être téléchargé sans être encore calculé."""
    f = SORTIES / "communes.csv"
    if f.exists():
        A = sorted(int(c[3:]) for c in pd.read_csv(f, nrows=0).columns
                   if re.fullmatch(r"pp_\d{4}", c))
    else:
        A = annees()
    return (A[0], A[-1]) if A else (None, None)


def exiger_sorties():
    """Arrête la page avec un message si le moteur n'a pas encore produit ses tables ; prévient
    si un registre plus récent que les résultats est en local (recalcul à lancer)."""
    m = manquantes()
    if m:
        st.warning("Les résultats du moteur sont incomplets (manquent : " + ", ".join(m)
                   + "). Lancez « Relancer les calculs » dans Technique → Recalculer.")
        st.page_link("vues/technique.py", label="Technique", icon=":material/build:")
        st.stop()
    A, an = annees(), bornes()[1]
    if A and A[-1] > an:
        st.warning(f"Le registre {A[-1]} est téléchargé, mais les résultats s'arrêtent à {an}. "
                   "Lancez « Relancer les calculs » dans Technique → Recalculer.")


def aides_chiffres():
    """Ce que compte chacun des trois chiffres de la Normandie (bande du haut, page Technique)."""
    return {"Prairimètre": "prairies permanentes déclarées à la PAC (RPG, groupe 18) : les PPH et, "
                           "jusqu'en 2022, les PRL, devenues PPH à 94 % en 2023.",
            "Chiffre officiel": f"prairies permanentes au sens réglementaire de la PAC. "
                                f"{OFFICIEL['source']}.",
            "Ratio officiel": f"part des prairies dans la surface agricole déclarée à la PAC, "
                              f"comparée à 2018. Au-delà de 4 % de baisse, les exploitants doivent "
                              f"compenser ; au-delà de {SEUIL_RATIO_PCT} %, tout retournement est "
                              "interdit et les prairies retournées doivent être réimplantées "
                              "(règlement délégué (UE) 2022/126, article 48 ; arrêté du 26 décembre "
                              "2025)."}


def chiffres_normandie():
    """Les trois chiffres de la région, sur toutes les pages, au même niveau que le menu. Sur un écran
    trop étroit pour les deux, ils passent sous le menu. Rien tant que le moteur n'a pas produit ses
    résultats."""
    if manquantes():
        return
    a0, an = bornes()
    bil = table("bilan_direct").loc["région"]
    solde = bil[("nouvelles_venant_de", "arrivee")] - bil[("disparues_devenues", "depart")]
    aides = aides_chiffres()
    cases = [(ha(solde, signe=True), f"Prairimètre, {a0}→{an}", aides["Prairimètre"]),
             (ha(OFFICIEL["perte_ha"], signe=True), "Chiffre officiel", aides["Chiffre officiel"]),
             (f"{nombre(OFFICIEL['ratio_evol_pct'], 2)} %", "Ratio officiel", aides["Ratio officiel"])]
    st.markdown(
        "<style>"
        ".chiffres-normandie {display:flex;align-items:center;gap:1.4rem;position:fixed;top:0;"
        "right:3.2rem;height:3.75rem;z-index:999999}"
        ".chiffres-normandie .case {display:flex;flex-direction:column;line-height:1.15}"
        ".chiffres-normandie .valeur {font-size:1.15rem;font-weight:700;white-space:nowrap}"
        ".chiffres-normandie .nom {font-size:0.7rem;opacity:0.75;white-space:nowrap}"
        ".chiffres-normandie .region {font-size:0.68rem;font-weight:600;letter-spacing:0.04em;"
        "opacity:0.7}"
        "@media (max-width:1240px) {.chiffres-normandie {position:static;height:auto;flex-wrap:wrap;"
        "margin-bottom:1rem}}"
        "</style>"
        '<div class="chiffres-normandie"><span class="region">NORMANDIE</span>'
        + "".join(f'<span class="case" title="{aide}"><span class="valeur">{valeur}</span>'
                  f'<span class="nom">{nom}</span></span>' for valeur, nom, aide in cases)
        + "</div>", unsafe_allow_html=True)


def communes_moitie(t):
    """Les communes, de la plus touchée à la moins touchée, qui portent ensemble la moitié du
    retournement récent (index de la table communes)."""
    ret = t[t.statut == "calculé"].retourne_recent.sort_values(ascending=False)
    return ret.index[:int((ret.cumsum() / ret.sum() < 0.5).sum() + 1)]


def comparaison(zonage):
    """Retourne-t-on « moins », « autant » ou « plus » dans ce zonage qu'à côté, dans la même
    commune ? Tranché sur toutes les périodes testées par le moteur : « autant » si les rapports
    encadrent 1. Renvoie (sens, rapports), ou (None, série vide) si l'évaluation manque."""
    rob, z = evaluation("robustesse"), evaluation("zonages", index_col=0)
    v = rob[rob.zonage == zonage].rapport_meme_commune if rob is not None else pd.Series()
    if v.empty and z is not None and zonage in z.index:
        v = pd.Series([z.loc[zonage, "rapport_meme_commune"]])
    if v.empty:
        return None, v
    return ("moins" if v.max() < 1 else "plus" if v.min() > 1 else "autant"), v


def motif_manquant(statut):
    """Pourquoi une commune n'a pas de diagnostic, en clair ; None si elle en a un."""
    if statut == "aucune prairie":
        return "Aucune prairie permanente déclarée dans la commune."
    if statut.startswith("moins de"):
        return f"Trop peu de prairies ({statut}) pour qu'un taux ait un sens."
    return None


def date_source(nom):
    """Date du fichier d'une source dans data/ (0 s'il n'y est pas) : sert de clé aux caches de
    l'appli, qui se refont dès que la source est réimportée."""
    f = DATA / SOURCES[nom]["fichier"]
    return f.stat().st_mtime if f.exists() else 0


# --- Cartes ------------------------------------------------------------------------------------

def _sur_disque(nom, fabrique):
    """Géométries de carte gardées dans cache/ : calculées une seule fois, même après un
    redémarrage (premier affichage rapide)."""
    import geopandas as gpd
    f = CACHE / f"carte_{nom}.parquet"
    if f.exists():
        return gpd.read_parquet(f)
    g = fabrique()
    g.to_parquet(f)
    return g


def communes_carte():
    """Contours des communes simplifiés (≈ 80 m) en WGS84, légers pour le navigateur."""
    return _communes_carte(date_source("communes"))


@st.cache_data(show_spinner="Préparation de la carte…")
def _communes_carte(_date):
    def f():
        from prairimetre.donnees import communes
        g = communes()[["insee", "nom_officiel", "dep", "epci", "geometry"]].copy()
        g["geometry"] = g.geometry.simplify(80, preserve_topology=True)
        return g.to_crs(4326)
    return _sur_disque("communes", f)


def hex_rgb(h, alpha=220):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)] + [alpha]


def deck(couches, vue_sur, info, hauteur=560):
    """Carte pydeck. couches : liste de (GeoDataFrame WGS84 avec colonne 'couleur', id) ;
    vue_sur : GeoDataFrame sur lequel centrer ; info : HTML du survol."""
    layers = [pdk.Layer("GeoJsonLayer", data=g.__geo_interface__, id=i, pickable=True,
                        stroked=True, filled=True, get_fill_color="properties.couleur",
                        get_line_color=[255, 255, 255, 160], line_width_min_pixels=0.5,
                        auto_highlight=True) for g, i in couches]
    b = vue_sur.total_bounds
    etendue = max(b[2] - b[0], b[3] - b[1])
    zoom = 6.8 if etendue > 2 else 8.2 if etendue > 0.8 else 9.5 if etendue > 0.3 else 11
    vue = pdk.ViewState(longitude=(b[0] + b[2]) / 2, latitude=(b[1] + b[3]) / 2, zoom=zoom)
    # Le fond de carte est toujours affiché (il demande une connexion internet)
    return pdk.Deck(layers=layers, initial_view_state=vue, map_provider="carto",
                    map_style="light", height=hauteur,
                    tooltip={"html": info, "style": {"fontSize": "12px"}})


def legende(elements):
    """Légende en HTML : liste de (couleur hex, libellé)."""
    st.markdown(" ".join(
        f'<span style="display:inline-flex;align-items:center;margin-right:14px;font-size:0.85rem">'
        f'<span style="width:12px;height:12px;border-radius:3px;background:{c};'
        f'border:1px solid rgba(128,128,128,0.45);display:inline-block;margin-right:6px"></span>'
        f'{l}</span>' for c, l in elements), unsafe_allow_html=True)


def selection_carte(evenement, couche, champ):
    """Valeur du champ de l'objet cliqué sur la carte, ou None."""
    if evenement and evenement.selection:
        objets = evenement.selection.objects.get(couche, [])
        if objets:
            return objets[0]["properties"].get(champ)
    return None


# --- Graphiques ------------------------------------------------------------------------------

# Graduations d'axe à la française (« 620 000 », « −20 000 ») : Vega écrirait « 620k »
AXE_FR = "replace(format(datum.value, ',.0f'), regexp(',', 'g'), ' ')"


def classement(noms, valeurs, couleur, titre_x, en_pct=False):
    """Barres horizontales triées, une par ligne, valeur écrite au bout de la barre
    (hectares, ou pourcentage si en_pct)."""
    import altair as alt
    d = pd.DataFrame({"nom": list(noms), "ha": list(valeurs)})
    d["texte"] = d.ha.map(lambda x: pct(x, 1) if en_pct else nombre(x))
    base = alt.Chart(d).encode(
        y=alt.Y("nom:N", sort=None, title=None, axis=alt.Axis(
            labelLimit=260, labelOverlap=False, labelFontSize=12, ticks=False, domain=False)),
        x=alt.X("ha:Q", title=titre_x,  # la valeur est écrite au bout de chaque barre
                axis=alt.Axis(labels=False, ticks=False, gridOpacity=0.3)))
    barres = base.mark_bar(color=couleur, cornerRadiusEnd=4, height=14).encode(
        tooltip=[alt.Tooltip("nom:N", title=" "), alt.Tooltip("texte:N", title="valeur")])
    textes = base.mark_text(align="left", dx=4, fontSize=11,
                            color="#d6d5cd" if st.context.theme.type == "dark" else "#52514e") \
        .encode(text="texte:N")
    return (barres + textes).properties(height=24 * len(d) + 30)


# --- Appel du moteur en ligne de commande ----------------------------------------------------

def lancer(*args):
    """Lance « python -m prairimetre <args> » et renvoie ses lignes au fil de l'eau."""
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
    p = subprocess.Popen([sys.executable, "-X", "utf8", "-m", "prairimetre", *map(str, args)],
                         cwd=RACINE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace", env=env, bufsize=1)
    for ligne in p.stdout:
        for morceau in ligne.rstrip("\n").split("\r"):  # barres de progression
            if morceau.strip() and "Warning" not in morceau:
                yield morceau
    p.wait()
    yield f"__code__{p.returncode}"
