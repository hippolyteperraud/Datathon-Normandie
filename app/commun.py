"""Fonctions partagées par les pages : lecture des sorties du moteur, formats, couleurs, cartes,
et lancement des commandes du moteur (python -m prairimetre ...).

Règle des données manquantes : on n'affiche jamais une case vide ou « None » ; chaque absence
est remplacée par sa raison (« moins de 20 ha de prairies », « non renseigné dans le Sandre »...).
"""
import re
from pathlib import Path

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


# --- Lecture des sorties du moteur ------------------------------------------------------------

def manquantes():
    return [t for t in TABLES if not (SORTIES / f"{t}.csv").exists()]


def table(nom):
    """Table du moteur ; relue dès que le moteur l'a recalculée (date du fichier)."""
    return _lire(nom, (SORTIES / f"{nom}.csv").stat().st_mtime)


@st.cache_data(show_spinner=False)
def _lire(nom, date):  # « date » sans tiret bas : Streamlit ne hache pas les arguments « _… »
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
def _evaluation(nom, date, **kw):
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


GAIN_MINIMUM_HA = 5    # en dessous, le gain pèse moins qu'une parcelle : ce n'est pas un exemple
PERTE_MAXIMUM_HA = 1   # en dessous, un écart de contour d'une année à l'autre, pas une perte


def communes_exemples(t):
    """Les communes où ça va bien : (gain, gardent). gain : hectares gagnés de façon assurée sur
    d'anciennes cultures (ni une prairie temporaire devenue permanente, ni une nouvelle déclaration),
    net de ce qui a été perdu, au moins GAIN_MINIMUM_HA ; gardent : les autres communes qui n'ont
    perdu aucune prairie de la première année."""
    calc = t[t.statut == "calculé"]
    sur_cultures = calc.venues_culture - calc.devenues_culture
    temporaires = (calc.venues_temporaire - calc.devenues_temporaire).clip(lower=0)
    declarees = calc.venues_non_declare - calc.devenues_non_declare
    assure = pd.concat([calc.solde, sur_cultures], axis=1).min(axis=1)
    gain = assure[(calc.solde > 0) & (sur_cultures >= declarees + temporaires) & (assure >= GAIN_MINIMUM_HA)]
    gardent = [i for i in calc.index[calc.disparues < PERTE_MAXIMUM_HA] if i not in set(gain.index)]
    return gain, gardent


# Chaque auteur, son école et le logo de l'école (dans app/assets), avec sa hauteur à l'écran en pixels :
# les deux logos n'ont pas la même forme, ces hauteurs leur donnent un poids voisin
EQUIPE = [("Hippolyte Perraud", "INSA Rouen Normandie", "logo_insa_rouen.png", 25),
          ("Mouhssine Bairoune", "ENSICAEN", "logo_ensicaen.png", 38)]


@st.cache_data
def _logo(fichier):
    """Le logo en data URI (le HTML de st.markdown ne lit pas les fichiers locaux) ; None s'il manque."""
    import base64
    f = Path(__file__).parent / "assets" / fichier
    return f"data:image/png;base64,{base64.b64encode(f.read_bytes()).decode()}" if f.exists() else None


def equipe():
    """Les auteurs et le logo de leur école, en haut à droite de toutes les pages, au niveau du menu.
    Sur un écran trop étroit, ils passent sous le menu. Le logo est posé sur un fond blanc, pour rester
    lisible en thème sombre ; s'il manque, le nom de l'école le remplace."""
    def case(nom, ecole, fichier, hauteur):
        src = _logo(fichier)
        marque = (f'<img src="{src}" alt="{ecole}" title="{ecole}" style="height:{hauteur}px">' if src
                  else f'<span class="ecole">{ecole}</span>')
        return f'<span class="case"><span class="nom">{nom}</span><span class="marque">{marque}</span></span>'
    st.markdown(
        "<style>"
        ".equipe {display:flex;align-items:center;gap:1.4rem;position:fixed;top:0;right:3.2rem;"
        "height:3.75rem;z-index:999999}"
        ".equipe .case {display:flex;align-items:center;gap:0.55rem}"
        ".equipe .nom {font-size:0.92rem;font-weight:700;white-space:nowrap}"
        ".equipe .marque {display:flex;align-items:center;background:#fff;border-radius:6px;"
        "padding:3px 6px}"
        ".equipe .marque img {display:block}"
        ".equipe .ecole {font-size:0.72rem;color:#1f2a24;white-space:nowrap}"
        "@media (max-width:1100px) {.equipe {position:static;height:auto;flex-wrap:wrap;"
        "margin-bottom:1rem}}"
        "</style>"
        f'<div class="equipe">{"".join(case(*e) for e in EQUIPE)}</div>', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _herbe(date_mesures):
    from prairimetre import sentinel as sen
    return sen.herbe_reelle()


def herbe_communes():
    """Ce que sont devenues, en hectares, les prairies de la première année, commune par commune (voir
    sentinel.herbe_reelle). Recalculé quand le bloc des mesures satellite change."""
    from prairimetre import sentinel as sen
    f = sen.bloc()[0]
    return _herbe(f.stat().st_mtime if f.exists() else 0)


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
def _communes_carte(date):
    def f():
        from prairimetre.donnees import communes
        g = communes()[["insee", "nom_officiel", "dep", "epci", "geometry"]].copy()
        g["geometry"] = g.geometry.simplify(80, preserve_topology=True)
        return g.to_crs(4326)
    return _sur_disque("communes", f)


def hex_rgb(h, alpha=220):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)] + [alpha]


def deck(couches, vue_sur, info, hauteur=560, zoom=None):
    """Carte pydeck. couches : liste de (GeoDataFrame WGS84 avec colonne 'couleur', id) ;
    vue_sur : GeoDataFrame sur lequel centrer ; info : HTML du survol ; zoom : imposé pour une petite
    carte (sinon tiré de l'étendue)."""
    layers = [pdk.Layer("GeoJsonLayer", data=g.__geo_interface__, id=i, pickable=True,
                        stroked=True, filled=True, get_fill_color="properties.couleur",
                        get_line_color=[255, 255, 255, 160], line_width_min_pixels=0.5,
                        auto_highlight=True) for g, i in couches]
    b = vue_sur.total_bounds
    etendue = max(b[2] - b[0], b[3] - b[1])
    zoom = zoom or (6.8 if etendue > 2 else 8.2 if etendue > 0.8 else 9.5 if etendue > 0.3 else 11)
    vue = pdk.ViewState(longitude=(b[0] + b[2]) / 2, latitude=(b[1] + b[3]) / 2, zoom=zoom)
    # Le fond de carte est toujours affiché (il demande une connexion internet)
    return pdk.Deck(layers=layers, initial_view_state=vue, map_provider="carto",
                    map_style="light", height=hauteur,
                    tooltip={"html": info, "style": {"fontSize": "12px"}})


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


# --- Appel du moteur en ligne de commande ----------------------------------------------------
