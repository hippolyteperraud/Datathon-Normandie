"""Les petites cartes « Les données qu'on a » : une carte par source, vert si la source dit quelque
chose, noir si elle ne dit rien, gris s'il y a peu ou pas de prairies.

Affichées par la page Technique."""
import re

import pandas as pd
import pydeck as pdk
import streamlit as st

from commun import (CAT, GRIS, MIN_HA, NOIR, communes_carte, date_source, hex_rgb, legende,
                    nombre)
from prairimetre.config import CACHE, DATA
from prairimetre.sources import SOURCES

PLEIN, PARTIEL = CAT[2], "#8fd3b8"


def millesimes_ocsge():
    """Dernier millésime de l'occupation du sol de l'IGN (OCS GE) en local, par département."""
    millesimes = {}
    for d, m in re.findall(r"ocsge_(\d{2})_(\d{4})",
                           " ".join(f.name for f in (DATA / "ocsge").glob("*.gpkg"))):
        millesimes[d] = max(millesimes.get(d, 0), int(m))
    return millesimes


def disponible(source, cache):
    """Une source est utilisable si son fichier est dans data/ ou déjà mis en cache."""
    return (DATA / SOURCES[source]["fichier"]).exists() or (CACHE / f"{cache}.parquet").exists()


@st.cache_data(show_spinner="Croisement des points d'enquête avec les communes…")
def lucas_par_commune(_date):
    """Points d'enquête LUCAS 2022 par commune : nombre total, nombre observés en herbe."""
    import geopandas as gpd
    from prairimetre.donnees import communes, lucas
    j = gpd.sjoin(lucas(), communes()[["insee", "geometry"]], predicate="within")
    return j.groupby("insee").agg(points=("point_id", "size"),
                                  en_herbe=("prairie_terrain", "sum"))


@st.cache_data(show_spinner="Croisement des habitats avec les communes…")
def habitats_par_commune(_date):
    """Communes touchées par la cartographie des habitats prairiaux Natura 2000."""
    import geopandas as gpd
    from prairimetre.donnees import communes, habitats_prairiaux
    j = gpd.sjoin(habitats_prairiaux()[["geometry"]], communes()[["insee", "geometry"]],
                  predicate="intersects")
    return set(j.insee)


@st.cache_data(show_spinner=False)
def contours_legers(_date):
    """Contours très simplifiés (≈ 300 m) : assez pour les petites cartes, et bien plus légers."""
    g = communes_carte()[["insee", "nom_officiel", "geometry"]].copy()
    g["geometry"] = g.geometry.simplify(0.003, preserve_topology=True)
    return g


def croisements(t):
    """Points d'enquête LUCAS par commune (ou None) et communes aux habitats cartographiés (ou None).
    La clé de cache change dès qu'une source est réimportée : les croisements se refont seuls."""
    lu = lucas_par_commune(date_source("lucas") + date_source("communes")) \
        .reindex(t.index, fill_value=0) if disponible("lucas", "lucas") else None
    hab = habitats_par_commune(date_source("habitats_natura2000") + date_source("communes")) \
        if disponible("habitats_natura2000", "habitats_prairiaux") else None
    return lu, hab


def petite_carte(titre, source, aide):
    """Le titre, la carte de la Normandie (figée, sans fond), la légende avec ses comptes."""
    classe, classes = source()
    n = classe.value_counts().reindex(list(classes), fill_value=0)
    g = contours_legers(date_source("communes"))
    g = g[g.insee.isin(classe.index)].copy()
    g["classe"] = g.insee.map(lambda i: classes[classe[i]][1])
    g["couleur"] = g.insee.map(lambda i: hex_rgb(classes[classe[i]][0], 255))
    b = g.total_bounds
    st.markdown(f"**{titre}**", help=aide)
    st.pydeck_chart(pdk.Deck(
        # Contour de la couleur de la commune : pas de jour entre les contours simplifiés
        layers=[pdk.Layer("GeoJsonLayer", data=g.__geo_interface__, pickable=True, stroked=True,
                          filled=True, get_fill_color="properties.couleur",
                          get_line_color="properties.couleur", line_width_min_pixels=1)],
        initial_view_state=pdk.ViewState(longitude=(b[0] + b[2]) / 2, latitude=(b[1] + b[3]) / 2,
                                         zoom=5.6),
        views=[pdk.View(type="MapView", controller=False)], map_provider=None,
        tooltip={"html": "<b>{nom_officiel}</b><br/>{classe}", "style": {"fontSize": "12px"}}),
        width="stretch", height=230)
    legende([(classes[c][0], f"{classes[c][1]} : {nombre(n[c])}") for c in classes if n[c]])


def afficher(t, a0, an):
    """Une petite carte par source disponible, côte à côte."""
    millesimes = millesimes_ocsge()
    lu, hab = croisements(t)

    def src_registre():
        c = pd.Series("suivi", index=t.index).where(t.statut == "calculé", "peu")
        return c, {"suivi": (PLEIN, "prairies suivies"),
                   "peu": (GRIS, f"moins de {MIN_HA} ha de prairies")}

    def src_ign():
        editions = sorted(set(millesimes.values()), reverse=True)
        classes = {str(m): (PLEIN if k == 0 else PARTIEL, f"édition {m}")
                   for k, m in enumerate(editions)}
        classes["aucune"] = (NOIR, "aucune édition")
        return t.dep.map(lambda d: str(millesimes[d]) if d in millesimes else "aucune"), classes

    def src_lucas():
        c = pd.Series("point", index=t.index).where(lu.points > 0, "aucun")
        return c, {"point": (PLEIN, "au moins un point"), "aucun": (NOIR, "aucun point")}

    def src_habitats():
        c = pd.Series("rien", index=t.index)
        c[t.index.isin(list(hab))] = "cartes"
        return c, {"cartes": (PLEIN, "cartographiés"), "rien": (NOIR, "aucune cartographie")}


    SOURCES_CARTES = [(f"Registre PAC {a0}–{an}", src_registre,
                       "Parcelles déclarées à la PAC, chaque année (IGN).")]
    if millesimes:
        SOURCES_CARTES.append(("Occupation du sol (OCS GE)", src_ign,
                               "Photos aériennes interprétées (IGN). Range prairies et cultures dans "
                               "la même classe."))
    if lu is not None:
        SOURCES_CARTES.append(("Enquête au sol (LUCAS 2022)", src_lucas,
                               "Points observés sur le terrain (Eurostat), tirés au sort."))
    if hab is not None:
        SOURCES_CARTES.append(("Habitats prairiaux (Natura 2000)", src_habitats,
                               "Prairies d'intérêt européen, cartographiées dans les sites Natura "
                               "2000 du Calvados, de la Manche et de l'Orne."))

    for colonne, (titre, source, aide) in zip(st.columns(len(SOURCES_CARTES)), SOURCES_CARTES):
        with colonne:
            petite_carte(titre, source, aide)
