"""Fonctions partagées par les pages : lecture des sorties du moteur, formats, couleurs, cartes,
et lancement des commandes du moteur (python -m prairimetre ...).

Règle des données manquantes : on n'affiche jamais une case vide ou « None » ; chaque absence
est remplacée par sa raison (« moins de 20 ha de prairies », « non renseigné dans le Sandre »...).
"""
import os
import re
import subprocess
import sys

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st

from prairimetre.config import CACHE, MIN_HA, RACINE, SORTIES, annees

TABLES = ["communes", "serie_region", "captages", "communes_captages", "bilan_direct",
          "cultures_destination", "objectif"]

# Chiffre officiel (vérifié sur Légifrance le 22/10/2026)
OFFICIEL = {"perte_ha": -59703, "perte_pct": -8.9, "ratio_evol_pct": -1.97,
            "source": "Arrêté du 11 septembre 2026, JORF n° 0218 du 18 septembre 2026"}

LEXIQUE = {
    "Aire d'alimentation de captage": "surface sur laquelle l'eau de pluie s'infiltre avant de "
                                      "rejoindre un captage d'eau potable.",
    "BCAE": "les « bonnes conditions agricoles et environnementales » imposées par la PAC. La BCAE 9 "
            "interdit de retourner les prairies sensibles ; la BCAE 2 protège les zones humides "
            "et les tourbières.",
    "Intercommunalité (EPCI)": "communauté de communes, d'agglomération ou urbaine.",
    "MAEC, paiements pour services environnementaux": "aides versées à un agriculteur qui "
                                                       "s'engage à garder ses prairies.",
    "Natura 2000, ZNIEFF": "Natura 2000 désigne des sites européens protégés ; une ZNIEFF est un "
                           "inventaire des milieux naturels remarquables, sans effet juridique sur "
                           "le labour.",
    "OCS GE, LUCAS, statistique agricole annuelle": "trois sources indépendantes du registre "
                                                     "parcellaire, utilisées pour vérifier ses "
                                                     "chiffres : la carte d'occupation du sol de "
                                                     "l'IGN, l'enquête de terrain européenne et "
                                                     "l'enquête annuelle du ministère de "
                                                     "l'Agriculture.",
    "Prairie permanente déclarée": "surface en herbe depuis au moins cinq ans, déclarée par un "
                                   "agriculteur à la PAC. L'outil ne voit que les prairies "
                                   "déclarées.",
    "Ratio de prairies permanentes": "part des prairies permanentes dans la surface agricole, "
                                     "suivie par l'État pour la PAC. S'il baisse de plus de 5 %, "
                                     "les retournements sont soumis à autorisation.",
    "Registre parcellaire graphique (RPG)": "carte des parcelles déclarées à la PAC, publiée "
                                            "chaque année par l'IGN, sans nom d'exploitant.",
    "Retournement": "prairie labourée puis déclarée en culture (maïs, blé…). La perte est certaine, "
                    "puisque la culture est déclarée.",
    "Sortie de la déclaration": "prairie qui n'apparaît plus dans le registre parcellaire. L'herbe "
                                "est souvent encore là (changement d'exploitant, chevaux, terrain "
                                "sans aide PAC) : la perte n'est pas certaine.",
}

DEPARTEMENTS = {"14": "Calvados", "27": "Eure", "50": "Manche", "61": "Orne",
                "76": "Seine-Maritime"}

# Palette catégorielle : contraste ≥ 3:1 sur les fonds clair et sombre (vert assombri pour
# l'atteindre) ; chaque couleur est toujours doublée d'un libellé. Bleu séquentiel clair -> foncé.
CAT = ["#2a78d6", "#eb6834", "#169c6c"]
NEUTRE = "#c3c2b7"
FOND = "#ecebe6"  # communes hors sélection ou sans indicateur
FLUX_COULEURS = {"culture": CAT[0], "non déclaré": CAT[1], "prairie temporaire": CAT[2]}
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


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


def contact_captage(r):
    """Premier interlocuteur connu d'une aire de captage : maître d'ouvrage, sinon service de
    l'État, sinon Agence de l'eau du bassin (toujours connue)."""
    for c in ("maitre_ouvrage", "service_etat", "agence_eau"):
        if isinstance(r[c], str) and r[c]:
            return nom_propre(r[c])
    return "à identifier"


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
    A = annees()
    return A[0], A[-1]


def exiger_sorties():
    """Arrête la page avec un message si le moteur n'a pas encore produit ses tables."""
    m = manquantes()
    if m:
        st.warning("Les résultats du moteur sont incomplets (manquent : " + ", ".join(m)
                   + "). Lancez « Recalculer » dans Données et méthode → Moteur.")
        st.page_link("vues/methode.py", label="Données et méthode", icon=":material/settings:")
        st.stop()


MOTIF_MANQUANT = {"calculé": None,
                  f"moins de {MIN_HA} ha de prairies en {annees()[0]}":
                      f"Trop peu de prairies en {annees()[0]} (moins de {MIN_HA} ha) pour qu'un "
                      "taux ait un sens.",
                  "aucune prairie": "Aucune prairie permanente déclarée dans la commune."}


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


@st.cache_data(show_spinner="Préparation de la carte…")
def communes_carte():
    """Contours des communes simplifiés (≈ 80 m) en WGS84, légers pour le navigateur."""
    def f():
        from prairimetre.donnees import communes
        g = communes()[["insee", "nom_officiel", "dep", "epci", "geometry"]].copy()
        g["geometry"] = g.geometry.simplify(80, preserve_topology=True)
        return g.to_crs(4326)
    return _sur_disque("communes", f)


@st.cache_data(show_spinner="Préparation de la carte…")
def epci_carte():
    """Contours des intercommunalités (union de leurs communes), simplifiés, en WGS84."""
    def f():
        from prairimetre.donnees import communes
        g = communes()[["epci", "geometry"]].dissolve("epci").reset_index()
        g["geometry"] = g.geometry.simplify(150, preserve_topology=True)
        return g.to_crs(4326)
    return _sur_disque("epci", f)


@st.cache_data(show_spinner="Préparation de la carte des captages…")
def captages_carte():
    """Partie normande de chaque aire de captage, simplifiée, en WGS84."""
    def f():
        from prairimetre.donnees import region, zonage
        a = zonage("aires_alimentation_captages")[["cdaac", "geometry"]].copy()
        a["aac"] = a.cdaac.astype(str)
        a = a.drop_duplicates("aac")
        a["geometry"] = a.geometry.intersection(region().geometry.iloc[0]) \
            .simplify(100, preserve_topology=True)
        a = a[~a.geometry.is_empty]
        return a[["aac", "geometry"]].to_crs(4326)
    return _sur_disque("captages", f)


def hex_rgb(h, alpha=220):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)] + [alpha]


def couleur_sequentielle(v, vmax, alpha=220):
    if pd.isna(v) or vmax <= 0:
        return hex_rgb(FOND, alpha)
    i = min(int(v / vmax * (len(SEQ) - 1) + 0.5), len(SEQ) - 1)
    return hex_rgb(SEQ[max(i, 0)], alpha)


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
    # Sans internet : pas de fond de carte (interrupteur dans la barre latérale), le reste marche
    fond = st.session_state.get("fond_carte", True)
    return pdk.Deck(layers=layers, initial_view_state=vue, map_provider="carto" if fond else None,
                    map_style="light" if fond else None, height=hauteur,
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
        tooltip=[alt.Tooltip("nom:N", title=" "), alt.Tooltip(
            "ha:Q", title="valeur", format=".2%" if en_pct else ",.0f")])
    textes = base.mark_text(align="left", dx=4, fontSize=11, color="#52514e").encode(text="texte:N")
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
