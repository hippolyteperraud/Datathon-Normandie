"""Carte des données : quelles données on a où, et où il en faudrait plus.

En haut, une petite carte par source : vert, la source dit quelque chose ; noir, elle ne dit rien ;
gris, peu ou pas de prairies. En bas, chaque donnée à collecter, ses chiffres et ses communes :
l'état réel des prairies sorties de la déclaration (la réponse décide quelles communes entrent dans
la liste où payer le maintien), puis les habitats prairiaux des départements sans cartographie.
Tout est calculé à partir des sorties du moteur et des sources en local."""
import re

import pandas as pd
import pydeck as pdk
import streamlit as st

from commun import (ACTIONS, CAT, DEPARTEMENTS, GRIS, HORS, MIN_HA, NOIR, bornes, classement,
                    communes_carte, communes_moitie, date_source, deck, evaluation, exiger_sorties,
                    ha, hex_rgb, legende, nombre, pct, selection_carte, table, variation)
from prairimetre.config import CACHE, DATA
from prairimetre.sources import SOURCES

PLEIN, PARTIEL = CAT[2], "#8fd3b8"

exiger_sorties()
a0, an = bornes()
t = table("communes")

# Dernier millésime de la carte d'occupation du sol de l'IGN (OCS GE) en local, par département
millesimes = {}
for d, m in re.findall(r"ocsge_(\d{2})_(\d{4})",
                       " ".join(f.name for f in (DATA / "ocsge").glob("*.gpkg"))):
    millesimes[d] = max(millesimes.get(d, 0), int(m))


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


# La clé de cache change dès qu'une source est réimportée : les croisements se refont seuls
lu = lucas_par_commune(date_source("lucas") + date_source("communes")) \
    .reindex(t.index, fill_value=0) if disponible("lucas", "lucas") else None
hab = habitats_par_commune(date_source("habitats_natura2000") + date_source("communes")) \
    if disponible("habitats_natura2000", "habitats_prairiaux") else None


# --- Une source par petite carte : une classe par commune, chaque classe a sa couleur et son nom ---
def src_registre():
    c = pd.Series("suivi", index=t.index).where(t.statut == "calculé", "peu")
    return c, {"suivi": (PLEIN, "prairies suivies"), "peu": (GRIS, f"moins de {MIN_HA} ha de prairies")}


def src_ign():
    editions = sorted(set(millesimes.values()), reverse=True)
    classes = {str(m): (PLEIN if k == 0 else PARTIEL, f"édition {m}") for k, m in enumerate(editions)}
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


# --- Page ------------------------------------------------------------------------------------------
st.title("Carte des données")
st.subheader("Les données qu'on a")
for colonne, (titre, source, aide) in zip(st.columns(len(SOURCES_CARTES)), SOURCES_CARTES):
    with colonne:
        petite_carte(titre, source, aide)

st.subheader("Où il en faudrait plus")


def carte_besoin(g, cle, info, elements):
    """Carte d'un besoin et sa légende ; un clic ouvre la fiche de la commune."""
    evt = st.pydeck_chart(deck([(g, cle)], g, info, hauteur=480), on_select="rerun",
                          selection_mode="single-object", width="stretch", key=cle)
    legende(elements)
    # Un clic ne compte qu'une fois (la sélection de la carte persiste d'un rechargement à l'autre)
    clic = selection_carte(evt, cle, "insee")
    if clic and clic != st.session_state.get(f"_clic_{cle}"):
        st.session_state[f"_clic_{cle}"] = clic
        st.session_state["commune"] = clic
        st.switch_page("vues/commune.py")


def chiffre(colonne, titre, valeur, note=None, aide=None):
    colonne.metric(titre, valeur, note, delta_color="off", delta_arrow="off", border=True,
                   height="stretch", help=aide)


# --- Besoin 1 : que sont devenues les prairies sorties de la déclaration ? -------------------------
st.markdown("##### 1. L'état réel des prairies sorties de la déclaration")
st.caption("À collecter : relevés de terrain ou images satellite. Question : encore en herbe ?")
sorties = t.devenues_non_declare
part_sortie = sorties / t[f"pp_{a0}"]
# Les communes, de la plus touchée à la moins touchée, qui portent ensemble la moitié des sorties
rang = sorties[t.statut == "calculé"].sort_values(ascending=False)
moitie = rang.index[:int((rang.cumsum() / rang.sum() < 0.5).sum() + 1)]
liste_payer = set(communes_moitie(t))
# Hors de la liste, la réponse décide si la commune y entre ; dans la liste, elle n'y change rien
decisives = [i for i in moitie if i not in liste_payer]
deja = [i for i in moitie if i in liste_payer]
payer = ACTIONS["payer"]["titre"]

certitude, saa = evaluation("certitude"), evaluation("saa")
c1, c2, c3, c4 = st.columns(4)
chiffre(c1, f"Sorties de la déclaration depuis {a0}", ha(sorties.sum()),
        "encore en herbe : ne sait pas")
if certitude is not None:
    p = certitude[certitude.source.str.startswith("LUCAS")
                  & (certitude.groupe == "sorties de la déclaration")].iloc[0]
    chiffre(c2, "Points d'enquête au sol sur ces prairies", nombre(p.prairies),
            f"{nombre(p.prairies * p.herbe)} en herbe en {p.source.split()[-1]}",
            "L'occupation du sol de l'IGN range prairies et cultures dans la même classe : elle "
            "ne peut pas répondre.")
if saa is not None:
    s = saa.loc[(saa.saa_variation - saa.rpg_variation).abs().idxmax()]
    chiffre(c3, f"Variation {int(s.annee)} selon le registre", ha(s.rpg_variation, signe=True),
            f"statistique agricole : {ha(s.saa_variation, signe=True)}",
            "Les deux sources officielles se contredisent : cela pèse sur le suivi de l'objectif "
            "2030 en hectares.")
chiffre(c4, "Communes où la décision en dépend", nombre(len(decisives)),
        f"{ha(sorties[decisives].sum())} sortis",
        f"{nombre(len(moitie))} communes portent la moitié des sorties. {nombre(len(decisives))} "
        f"ne sont pas dans les {nombre(len(liste_payer))} communes de « {payer} » : si ces "
        "hectares sont perdus, elles devraient y être.")

FORT, CLAIR = ACTIONS["verifier"]["couleur"], "#f6b89c"
gauche, droite = st.columns([3, 2], gap="large")
with gauche:
    g = communes_carte().copy()
    calculees = set(t.index[t.statut == "calculé"])
    fort, clair = set(decisives), set(deja)
    g["couleur"] = [hex_rgb(FORT) if i in fort else hex_rgb(CLAIR) if i in clair
                    else hex_rgb(HORS, 200) if i in calculees else hex_rgb(GRIS, 230) for i in g.insee]
    g["valeur"] = g.insee.map(lambda i: f"{ha(sorties[i])} sortis, {pct(part_sortie[i], 0)} de ses prairies")
    g["liste"] = g.insee.map(lambda i: f"dans « {payer} »" if i in liste_payer else f"hors de « {payer} »")
    carte_besoin(g[["insee", "nom_officiel", "couleur", "valeur", "liste", "geometry"]],
                 "besoin_sorties", "<b>{nom_officiel}</b><br/>{valeur}<br/>{liste}",
                 [(FORT, f"hors de « {payer} », la réponse décide : {nombre(len(decisives))} "
                         f"communes, {ha(sorties[decisives].sum())}"),
                  (CLAIR, f"déjà dedans : {nombre(len(deja))} communes, {ha(sorties[deja].sum())}"),
                  (HORS, f"autres : {nombre(len(calculees) - len(moitie))}"),
                  (GRIS, f"moins de {MIN_HA} ha de prairies : {nombre(len(t) - len(calculees))}")])
with droite:
    tete = decisives[:15]
    st.altair_chart(classement([f"{t.nom_officiel[i]} ({pct(part_sortie[i], 0)})" for i in tete],
                               sorties[tete], FORT,
                               f"hectares sortis (part de ses prairies de {a0})"), width="stretch")

# --- Besoin 2 : les départements où aucun habitat prairial n'est cartographié ----------------------
zones = table("communes_zones")
en_site = zones[zones.zone == "sites protégés"].set_index("insee").reindex(t.index)
connus = zones[(zones.zone == "habitats") & zones.prairies.notna()].insee
sans_carte = sorted(set(t.dep) - set(t.dep[connus]))
if hab is not None and sans_carte:
    noms_dep = " et ".join(DEPARTEMENTS[d] for d in sans_carte)
    ici = en_site[t.dep.isin(sans_carte) & (en_site.prairies >= 1)].sort_values("prairies", ascending=False)
    st.markdown(f"##### 2. Les habitats prairiaux des sites protégés : {noms_dep}")
    st.caption("À collecter : cartographie des habitats. Question : quels habitats sont touchés ?")
    c1, c2, c3, c4 = st.columns(4)
    chiffre(c1, "Prairies en site protégé, sans carte des habitats", ha(ici.prairies.sum()),
            f"{nombre(len(ici))} communes")
    chiffre(c2, f"Retournées dessus depuis {a0}", ha(ici.culture.sum()), "habitat touché : ne sait pas")
    chiffre(c3, f"Sorties de la déclaration dessus depuis {a0}", ha(ici.non_declare.sum()),
            "habitat touché : ne sait pas")
    h = evaluation("habitats")
    if h is not None:
        h = h[h.code == "total"].iloc[0]
        chiffre(c4, "Habitats retournés, là où ils sont cartographiés", ha(h.retourne_ha),
                f"sur {ha(h.surface_cartographiee_ha)} cartographiés",
                "Ce résultat ne vaut que pour les départements cartographiés : ailleurs, on ne "
                "sait pas si les habitats tiennent aussi bien.")
    gauche, droite = st.columns([3, 2], gap="large")
    with gauche:
        g = communes_carte().copy()
        cibles = set(ici.index)
        g["couleur"] = [hex_rgb(FORT) if i in cibles else hex_rgb(HORS, 200) for i in g.insee]
        g["valeur"] = g.insee.map(lambda i: f"{ha(en_site.prairies[i])} de prairies en site protégé")
        g["perte"] = g.insee.map(lambda i: f"{ha(en_site.culture[i])} retournés")
        carte_besoin(g[["insee", "nom_officiel", "couleur", "valeur", "perte", "geometry"]],
                     "besoin_habitats", "<b>{nom_officiel}</b><br/>{valeur}<br/>{perte}",
                     [(FORT, f"prairies en site protégé, sans carte : {nombre(len(ici))} communes"),
                      (HORS, f"autres : {nombre(len(g) - len(ici))}")])
    with droite:
        tete = ici.index[:15]
        st.altair_chart(classement(t.nom_officiel[tete], ici.prairies[tete], FORT,
                                   "hectares de prairies en site protégé"), width="stretch")

# --- Le tableau complet, téléchargeable --------------------------------------------------------------
export = pd.DataFrame({
    "insee": t.index, "commune": t.nom_officiel.values, "departement": t.dep.values,
    f"prairies_{a0}_ha": t[f"pp_{a0}"].round(0).values,
    "retournees_ha": t.devenues_culture.round(0).values,
    "sorties_declaration_ha": sorties.round(0).values,
    "moitie_des_sorties": t.index.isin(moitie),
    "liste_payer_le_maintien": t.index.isin(liste_payer),
    "prairies_en_site_protege_ha": en_site.prairies.round(0).values,
    "site_protege_sans_carte_habitats": t.dep.isin(sans_carte).values & (en_site.prairies >= 1).values})
if lu is not None:
    export["points_lucas"] = lu.points.values
    export["points_lucas_en_herbe"] = lu.en_herbe.values
if hab is not None:
    export["habitats_natura2000"] = t.index.isin(list(hab))
if millesimes:
    export["carte_ign_millesime"] = t.dep.map(millesimes).values
st.download_button(f"Télécharger le tableau ({nombre(len(export))} communes, CSV)",
                   export.to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig"),
                   "prairimetre_couverture_donnees.csv", "text/csv", icon=":material/download:",
                   key="dl_couverture")
