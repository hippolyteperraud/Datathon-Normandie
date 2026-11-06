"""Carte des données : quelles données on a où, et où il en faudrait plus.

En haut, une vue d'ensemble par source (Registre PAC et Télédétection Sentinel-2) et une carte
interactive détaillée par commune.
En bas, l'état réel des prairies sorties de la déclaration (la réponse décide quelles communes
entrent dans la liste où payer le maintien), éclairé par la télédétection Sentinel-2.
Tout est calculé à partir des sorties du moteur et des sources en local."""
import pandas as pd
import pydeck as pdk
import streamlit as st

from commun import (ACTIONS, CAT, DEPARTEMENTS, GRIS, HORS, MIN_HA, NEUTRE, NOIR,
                    bornes, classement, communes_carte, communes_moitie, date_source, deck,
                    evaluation, exiger_sorties, ha, hex_rgb, legende, nombre, pct,
                    selection_carte, table)

PLEIN = CAT[2]

exiger_sorties()
a0, an = bornes()
t = table("communes")


@st.cache_data(show_spinner=False)
def contours_legers(_date):
    """Contours simplifiés pour l'affichage fluide des petites cartes."""
    g = communes_carte()[["insee", "nom_officiel", "geometry"]].copy()
    g["geometry"] = g.geometry.simplify(0.002, preserve_topology=True)
    return g


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


SOURCES_CARTES = [
    (f"Registre PAC {a0}–{an}", src_registre,
     "Parcelles déclarées à la PAC, chaque année (IGN)."),
    ("Télédétection (Sentinel-2)", src_satellite,
     "Observation satellitaire multi-temporelle (10 m) : détecte l'herbe physique hors aides PAC."),
]


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


VUES_GRANDES = {
    f"Registre PAC ({a0}–{an})": detail_registre,
    "Télédétection satellitaire (Sentinel-2 / Theia OSO)": detail_satellite,
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


# --- Besoin : que sont devenues les prairies sorties de la déclaration ? ----------------------------
st.markdown("##### L'état réel des prairies sorties de la déclaration")
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

# --- Le tableau complet, téléchargeable --------------------------------------------------------------
_sat_c, _sat_cls = src_satellite()
export = pd.DataFrame({
    "insee": t.index, "commune": t.nom_officiel.values, "departement": t.dep.values,
    "satellite_sentinel2": _sat_c.map(lambda x: _sat_cls[x][1]).values,
    f"prairies_{a0}_ha": t[f"pp_{a0}"].round(0).values,
    "retournees_ha": t.devenues_culture.round(0).values,
    "sorties_declaration_ha": sorties.round(0).values,
    "moitie_des_sorties": t.index.isin(moitie),
    "liste_payer_le_maintien": t.index.isin(liste_payer)})
st.download_button(f"Télécharger le tableau ({nombre(len(export))} communes, CSV)",
                   export.to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig"),
                   "prairimetre_couverture_donnees.csv", "text/csv", icon=":material/download:",
                   key="dl_couverture")
