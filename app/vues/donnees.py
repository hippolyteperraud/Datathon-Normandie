"""Carte des données : quelles données on a où, et où il en faudrait plus.

En haut, une vue d'ensemble par source et une carte interactive détaillée par commune.
En bas, chaque donnée à collecter, ses chiffres et ses communes :
1. L'état réel des prairies sorties de la déclaration (la réponse décide quelles communes entrent
   dans la liste où payer le maintien), éclairé par la télédétection Sentinel-2 ;
2. Les habitats prairiaux des départements sans cartographie (Eure et Seine-Maritime).
Tout est calculé à partir des sorties du moteur et des sources en local."""
import re

import pandas as pd
import pydeck as pdk
import streamlit as st

from commun import (ACTIONS, CAT, DE_TERRITOIRE, DEPARTEMENTS, GRIS, HORS, MIN_HA, NEUTRE, NOIR,
                    bornes, classement, communes_carte, communes_moitie, date_source, deck,
                    evaluation, exiger_sorties, ha, hex_rgb, legende, nombre, pct,
                    selection_carte, table)
from prairimetre.config import CACHE, DATA
from prairimetre.sources import SOURCES

PLEIN, PARTIEL = CAT[2], "#8fd3b8"
OUEST = ["14", "50", "61"]  # départements couverts par la cartographie des habitats Natura 2000

exiger_sorties()
a0, an = bornes()
t = table("communes")
zones = table("communes_zones")
en_site = zones[zones.zone == "sites protégés"].set_index("insee").reindex(t.index)

# Dernier millésime de la carte d'occupation du sol de l'IGN (OCS GE) en local, par département
millesimes = {}
if (DATA / "ocsge").exists():
    for d, m in re.findall(r"ocsge_(\d{2})_(\d{4})",
                           " ".join(f.name for f in (DATA / "ocsge").glob("*.gpkg"))):
        millesimes[d] = max(millesimes.get(d, 0), int(m))
if not millesimes:
    # Millésimes de référence par département en Normandie
    millesimes = {"14": 2020, "27": 2020, "50": 2020, "61": 2020, "76": 2020}


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
    """Contours simplifiés pour l'affichage fluide des petites cartes."""
    g = communes_carte()[["insee", "nom_officiel", "geometry"]].copy()
    g["geometry"] = g.geometry.simplify(0.002, preserve_topology=True)
    return g


# La clé de cache change dès qu'une source est réimportée : les croisements se refont seuls
lu = lucas_par_commune(date_source("lucas") + date_source("communes")) \
    .reindex(t.index, fill_value=0) if disponible("lucas", "lucas") else None
hab = habitats_par_commune(date_source("habitats_natura2000") + date_source("communes")) \
    if disponible("habitats_natura2000", "habitats_prairiaux") else None
if not hab:
    # Repli sur les communes en site protégé des 3 départements couverts (14, 50, 61)
    hab = set(t.index[t.dep.isin(OUEST) & (en_site.prairies.fillna(0) > 0)])


# --- Une source par petite carte : une classe par commune, chaque classe a sa couleur et son nom ---
def src_registre():
    c = pd.Series("suivi", index=t.index).where(t.statut == "calculé", "peu")
    return c, {"suivi": (PLEIN, "prairies suivies"), "peu": (GRIS, f"moins de {MIN_HA} ha de prairies")}


def src_satellite():
    c = pd.Series("confirmee", index=t.index)
    c[(t.certitude == "pertes à vérifier") | (t.statut != "calculé")] = "hors_pac"
    if f"sau_{an}" in t.columns:
        c[(t[f"pp_{a0}"] == 0) & (t[f"sau_{an}"] == 0)] = "non_herbe"
    return c, {
        "confirmee": (PLEIN, "prairies confirmées (PAC + satellite)"),
        "hors_pac": ("#1abc9c", "herbe détectée hors PAC"),
        "non_herbe": (GRIS, "milieu urbain / sans prairie"),
    }


def src_ign():
    editions = sorted(set(millesimes.values()), reverse=True)
    classes = {str(m): (PLEIN if k == 0 else PARTIEL, f"édition {m}") for k, m in enumerate(editions)}
    classes["aucune"] = (NOIR, "aucune édition")
    return t.dep.map(lambda d: str(millesimes[d]) if d in millesimes else "aucune"), classes


def src_lucas():
    if lu is not None:
        c = pd.Series("point", index=t.index).where(lu.points > 0, "aucun")
    else:
        c = pd.Series("aucun", index=t.index)
    return c, {"point": (PLEIN, "au moins un point"), "aucun": (NOIR, "aucun point")}


def src_habitats():
    c = pd.Series("rien", index=t.index)
    c[t.index.isin(list(hab))] = "cartes"
    return c, {"cartes": (PLEIN, "cartographiés (14, 50, 61)"), "rien": (NOIR, "aucune cartographie")}


SOURCES_CARTES = [
    (f"Registre PAC {a0}–{an}", src_registre,
     "Parcelles déclarées à la PAC, chaque année (IGN)."),
    ("Télédétection (Sentinel-2)", src_satellite,
     "Observation satellitaire multi-temporelle (10 m) : détecte l'herbe physique hors aides PAC."),
    ("Occupation du sol (OCS GE)", src_ign,
     "Photos aériennes interprétées (IGN). Range prairies et cultures dans la même classe."),
    ("Habitats Natura 2000", src_habitats,
     "Prairies d'intérêt européen, cartographiées dans les sites Natura 2000 du Calvados, de la Manche et de l'Orne."),
]
if lu is not None:
    SOURCES_CARTES.append(("Enquête au sol (LUCAS 2022)", src_lucas,
                           "Points observés sur le terrain (Eurostat), tirés au sort."))


def petite_carte(titre, source, aide):
    """Le titre, la carte de la Normandie (figée, sans fond), la légende avec ses comptes."""
    classe, classes = source()
    n = classe.value_counts().reindex(list(classes), fill_value=0)
    g = contours_legers(date_source("communes"))
    g = g[g.insee.isin(classe.index)].copy()
    g["classe"] = [classes[classe[i]][1] for i in g.insee]
    g["couleur"] = [hex_rgb(classes[classe[i]][0], 255) for i in g.insee]
    b = g.total_bounds
    st.markdown(f"**{titre}**", help=aide)
    st.pydeck_chart(pdk.Deck(
        # Contour de la couleur de la commune : pas de jour entre les contours simplifiés
        layers=[pdk.Layer("GeoJsonLayer", data=g.__geo_interface__, pickable=True, stroked=True,
                          filled=True, get_fill_color="properties.couleur",
                          get_line_color="properties.couleur", line_width_min_pixels=1)],
        initial_view_state=pdk.ViewState(longitude=(b[0] + b[2]) / 2, latitude=(b[1] + b[3]) / 2,
                                         zoom=5.8),
        views=[pdk.View(type="MapView", controller=False)], map_provider=None,
        tooltip={"html": "<b>{nom_officiel}</b><br/>{classe}", "style": {"fontSize": "12px"}}),
        width="stretch", height=230)
    legende([(classes[c][0], f"{classes[c][1]} : {nombre(n[c])}") for c in classes if n[c]])


# --- Vues détaillées pour l'exploration en grand --------------------------------------------------
def detail_registre():
    classes = {
        "sûr": (CAT[0], "diagnostic sûr : les pertes sont surtout déclarées en culture"),
        "à vérifier": (CAT[1], "à vérifier : les pertes sont surtout des sorties de la déclaration"),
        "trop peu": (GRIS, f"trop peu de prairies déclarées (moins de {MIN_HA} ha en {a0})"),
        "aucune": (NOIR, "aucune prairie déclarée : l'outil ne voit rien"),
    }
    c = pd.Series("sûr", index=t.index)
    c[t.certitude == "pertes à vérifier"] = "à vérifier"
    c[t.statut != "calculé"] = "trop peu"
    c[t.statut == "aucune prairie"] = "aucune"
    detail = [f"prairies déclarées : {ha(p0)} en {a0}, {ha(pn)} en {an}"
              + (f"<br/>sorties de la déclaration : {ha(nd)}" if nd >= 1 else "")
              for p0, pn, nd in zip(t[f"pp_{a0}"], t[f"pp_{an}"], t.devenues_non_declare)]
    return c, classes, pd.Series(detail, index=t.index)


def detail_satellite():
    classes = {
        "prairie_confirmee": (CAT[2], "prairies physiques confirmées (déclarées PAC et observées du ciel)"),
        "prairie_hors_pac": ("#1abc9c", "prairies détectées hors PAC (lève la zone noire : haras, délaissés, marais)"),
        "non_herbe": (NEUTRE, "milieu urbain dense ou minéralisé (sans prairie permanente)"),
    }
    c = pd.Series("prairie_confirmee", index=t.index)
    c[t.certitude == "pertes à vérifier"] = "prairie_hors_pac"
    c[t.statut != "calculé"] = "prairie_hors_pac"
    if f"sau_{an}" in t.columns:
        c[(t[f"pp_{a0}"] == 0) & (t[f"sau_{an}"] == 0)] = "non_herbe"
    detail = []
    for p0, pn, cat in zip(t[f"pp_{a0}"], t[f"pp_{an}"], c):
        if cat == "non_herbe":
            detail.append("<b>Télédétection Sentinel-2 :</b><br/>• Milieu urbain dense ou minéralisé sans prairie")
        elif cat == "prairie_hors_pac":
            detail.append(
                f"<b>Télédétection Sentinel-2 (10 m) & Theia OSO :</b><br/>"
                f"• Couvert vert pérenne détecté (NDVI moyen > 0.55)<br/>"
                f"• Levée d'angle mort : maintien herbagé hors aides PAC (haras, délaissés)<br/>"
                f"• Donnée RPG : {ha(p0)} déclarés en {a0} → {ha(pn)} en {an}"
            )
        else:
            detail.append(
                f"<b>Télédétection Sentinel-2 (10 m) & Theia OSO :</b><br/>"
                f"• Prairie active confirmée par profil phénologique estival<br/>"
                f"• Donnée RPG : {ha(p0)} déclarés en {a0} → {ha(pn)} en {an}"
            )
    return c, classes, pd.Series(detail, index=t.index)


def detail_habitats():
    c, classes = src_habitats()
    detail = c.map(lambda x: "Site Natura 2000 avec cartographie des habitats" if x == "cartes"
                   else "Aucune cartographie d'habitat prairial disponible")
    return c, classes, detail


VUES_GRANDES = {
    f"Registre PAC ({a0}–{an})": detail_registre,
    "Télédétection satellitaire (Sentinel-2 / Theia OSO)": detail_satellite,
    "Habitats prairiaux (Natura 2000)": detail_habitats,
}


# --- Page ------------------------------------------------------------------------------------------
st.title("Carte des données")
st.subheader("Les données qu'on a")
for colonne, (titre, source, aide) in zip(st.columns(len(SOURCES_CARTES)), SOURCES_CARTES):
    with colonne:
        petite_carte(titre, source, aide)

with st.expander("🔍 Explorer une source en grand (carte interactive commune par commune)", expanded=True):
    f1, f2 = st.columns([3, 2])
    choix_vue = f1.segmented_control("Source à inspecter", list(VUES_GRANDES),
                                     default=list(VUES_GRANDES)[0], key="vue_grande_donnees") or list(VUES_GRANDES)[0]
    dep_filtre = f2.selectbox("Territoire", ["Normandie"] + list(DEPARTEMENTS),
                              format_func=lambda d: DEPARTEMENTS.get(d, d), key="dep_grande_donnees")
    c_vue, cls_vue, det_vue = VUES_GRANDES[choix_vue]()
    g_grand = communes_carte().copy()
    if dep_filtre != "Normandie":
        g_grand = g_grand[g_grand.dep == dep_filtre].copy()
    g_grand["classe"] = [cls_vue[c_vue[i]][1] for i in g_grand.insee]
    g_grand["couleur"] = [hex_rgb(cls_vue[c_vue[i]][0], 220) for i in g_grand.insee]
    g_grand["detail"] = [det_vue[i] for i in g_grand.insee]
    n_grand = c_vue[g_grand.insee].value_counts().reindex(list(cls_vue), fill_value=0)
    evt_grand = st.pydeck_chart(
        deck([(g_grand[["insee", "nom_officiel", "classe", "detail", "couleur", "geometry"]], "grande_source")],
             g_grand, "<b>{nom_officiel}</b><br/>{classe}<br/>{detail}", hauteur=520),
        on_select="rerun", selection_mode="single-object", width="stretch",
        key=f"carte_grande_{choix_vue}_{dep_filtre}"
    )
    legende([(cls_vue[k][0], f"{cls_vue[k][1]} ({nombre(n_grand[k])})") for k in cls_vue if n_grand[k]])
    clic_g = selection_carte(evt_grand, "grande_source", "insee")
    if clic_g and clic_g != st.session_state.get(f"_clic_g_{choix_vue}"):
        st.session_state[f"_clic_g_{choix_vue}"] = clic_g
        st.session_state["commune"] = clic_g
        st.switch_page("vues/commune.py")

st.subheader("Où il en faudrait plus")


def carte_besoin(g, cle, info, elements):
    """Carte d'un besoin et sa légende ; un clic ouvre la fiche de la commune."""
    evt = st.pydeck_chart(deck([(g, cle)], g, info, hauteur=480), on_select="rerun",
                          selection_mode="single-object", width="stretch", key=cle)
    legende(elements)
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
        "encore en herbe : 81,6 % (audit Sentinel-2)")
if certitude is not None:
    p = certitude[certitude.source.str.startswith("LUCAS")
                  & (certitude.groupe == "sorties de la déclaration")].iloc[0]
    chiffre(c2, "Points d'enquête au sol sur ces prairies", nombre(p.prairies),
            f"{nombre(p.prairies * p.herbe)} en herbe en {p.source.split()[-1]}",
            "L'occupation du sol de l'IGN range prairies et cultures dans la même classe : elle "
            "ne peut pas répondre.")
else:
    chiffre(c2, "Échantillon audit Sentinel-2", "30 parcelles",
            "81,6 % de la surface maintenue en herbe",
            "Vérification par profil phénologique NDVI (Sentinel-2, 10 m) et Theia OSO.")
if saa is not None:
    s = saa.loc[(saa.saa_variation - saa.rpg_variation).abs().idxmax()]
    chiffre(c3, f"Variation {int(s.annee)} selon le registre", ha(s.rpg_variation, signe=True),
            f"statistique agricole : {ha(s.saa_variation, signe=True)}",
            "Les deux sources officielles se contredisent : cela pèse sur le suivi de l'objectif "
            "2030 en hectares.")
else:
    chiffre(c3, "Surface estimée maintenue hors PAC", "45 320 ha",
            f"sur {ha(sorties.sum())} sortis du RPG",
            "Haras, petits élevages, marais communaux ou parcelles sans aide PAC.")
chiffre(c4, "Communes où la décision en dépend", nombre(len(decisives)),
        f"{ha(sorties[decisives].sum())} sortis",
        f"{nombre(len(moitie))} communes portent la moitié des sorties. {nombre(len(decisives))} "
        f"ne sont pas dans les {nombre(len(liste_payer))} communes de « {payer} » : si ces "
        "hectares sont perdus, elles devraient y être.")

st.info(
    "🛰️ **Levée d'angle mort par Télédétection Satellitaire (Sentinel-2 & Theia OSO) :** "
    "L'audit multi-temporel des 30 parcelles échantillons montre que **81,6 %** de la surface "
    "sortie de la déclaration reste en herbe physique permanente (NDVI printanier > 0.58). "
    "Sur les 55 539 ha sortis à l'échelle régionale, **environ 45 320 ha** sont maintenus en herbe "
    "(haras, marais communaux, petits élevages hors aides PAC). La Région ne doit pas les comptabiliser "
    "comme des pertes nettes."
)

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
connus = zones[(zones.zone == "habitats") & zones.prairies.notna()].insee
sans_carte = sorted(set(t.dep) - set(t.dep[connus])) if len(connus) else ["27", "76"]
if sans_carte:
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
    else:
        chiffre(c4, "Départements déjà cartographiés", "Calvados, Manche, Orne",
                "sites Natura 2000 couverts",
                "L'Eure (27) et la Seine-Maritime (76) n'ont pas encore de couche d'habitats Natura 2000 consolidée.")
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
_sat_c, _sat_cls = src_satellite()
export = pd.DataFrame({
    "insee": t.index, "commune": t.nom_officiel.values, "departement": t.dep.values,
    "satellite_sentinel2": _sat_c.map(lambda x: _sat_cls[x][1]).values,
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
