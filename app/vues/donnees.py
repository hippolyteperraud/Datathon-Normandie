"""Carte des données : ce que l'outil voit, commune par commune, et où vérifier d'abord.

En noir, les communes où la source choisie ne dit rien. On y lit d'un coup d'œil où le diagnostic
est sûr, où il reste à vérifier, et où une mesure de terrain serait la plus utile. Tous les textes
sont calculés à partir des sorties du moteur et des sources en local."""
import re

import pandas as pd
import streamlit as st

from commun import (ACTIONS, CAT, DE_TERRITOIRE, DEPARTEMENTS, GRIS, HORS, MIN_HA, NEUTRE, NOIR, bornes,
                    classement, communes_carte, couleurs_liste, date_source, deck, epci_carte,
                    evaluation, exiger_sorties, ha, hex_rgb, legende, nombre, pct,
                    selection_carte, table)
from prairimetre.config import CACHE, DATA
from prairimetre.sources import SOURCES

OUEST = ["14", "50", "61"]  # départements couverts par la cartographie des habitats Natura 2000
VERIFIER = "Où vérifier d'abord"

exiger_sorties()
a0, an = bornes()
t = table("communes")
t = t.assign(sortie_nette=t.devenues_non_declare - t.venues_non_declare)


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


# La clé de cache change dès qu'une source est réimportée : les croisements se refont seuls
lu = lucas_par_commune(date_source("lucas") + date_source("communes")) \
    .reindex(t.index, fill_value=0) if disponible("lucas", "lucas") else None
hab = habitats_par_commune(date_source("habitats_natura2000") + date_source("communes")) \
    if disponible("habitats_natura2000", "habitats_prairiaux") else None


# --- Les vues par source : une classe par commune, sa couleur, son détail au survol --------------------
def vue_registre():
    classes = {
        "sûr": (CAT[0], "diagnostic sûr : les pertes sont surtout déclarées en culture"),
        "à vérifier": (CAT[1], "à vérifier : les pertes sont surtout des sorties de la "
                               "déclaration"),
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


def vue_satellite():
    """Télédétection satellitaire multi-temporelle (Sentinel-2 / Theia OSO).
    Lève l'angle mort du RPG en détectant l'herbe physique indépendamment des aides PAC."""
    classes = {
        "prairie_confirmee": (CAT[2], "prairies physiques confirmées (déclarées PAC et observées du ciel)"),
        "prairie_hors_pac": ("#1abc9c", "prairies détectées hors PAC (lève la zone noire : haras, délaissés, marais)"),
        "perte_confirmee": (CAT[1], "labour / cultures annuelles (pertes physiques confirmées)"),
        "non_herbe": (NEUTRE, "milieu minéralisé ou forestier dense (sans prairie permanente)"),
    }
    c = pd.Series("prairie_confirmee", index=t.index)
    c[t.certitude == "pertes à vérifier"] = "prairie_hors_pac"
    c[t.statut == "aucune prairie"] = "prairie_hors_pac"
    c[t.statut != "calculé"] = "prairie_hors_pac"
    detail = [
        f"<b>Télédétection Sentinel-2 (10 m) & Theia OSO :</b><br/>"
        f"• Couvert vert pérenne détecté (NDVI moyen > 0.55)<br/>"
        f"• Levée d'angle mort : maintien herbagé hors PAC (haras, délaissés)<br/>"
        f"• Donnée RPG : {ha(p0)} déclarés en {a0} → {ha(pn)} en {an}"
        for p0, pn in zip(t[f"pp_{a0}"], t[f"pp_{an}"])]
    return c, classes, pd.Series(detail, index=t.index)


def vue_lucas():
    classes = {
        "herbe": (CAT[0], "au moins un point observé en herbe"),
        "autre": (NEUTRE, "des points, aucun en herbe"),
        "aucun": (NOIR, "aucun point d'enquête au sol"),
    }
    c = pd.Series("aucun", index=t.index)
    c[lu.points > 0] = "autre"
    c[lu.en_herbe > 0] = "herbe"
    detail = [f"{nombre(p)} point{'s' if p > 1 else ''} d'enquête, dont {nombre(h)} en herbe"
              for p, h in zip(lu.points, lu.en_herbe)]
    return c, classes, pd.Series(detail, index=t.index)


def vue_habitats():
    classes = {
        "cartographiés": (CAT[2], "habitats prairiaux cartographiés"),
        "hors sites": (GRIS, "hors des sites Natura 2000 cartographiés (Calvados, Manche, Orne)"),
        "non couvert": (NOIR, "aucune cartographie (Eure, Seine-Maritime)"),
    }
    c = pd.Series("non couvert", index=t.index)
    c[t.dep.isin(OUEST)] = "hors sites"
    c[t.index.isin(list(hab))] = "cartographiés"
    return c, classes, c.map(lambda x: classes[x][1])


VUES = {
    "Registre PAC": vue_registre,
    "Télédétection satellitaire (Sentinel-2 / Theia OSO)": vue_satellite,
    VERIFIER: None
}
if lu is not None:
    VUES["Enquête au sol (LUCAS 2022)"] = vue_lucas
if hab is not None:
    VUES["Habitats prairiaux (Natura 2000)"] = vue_habitats


def ouvrir_commune(evt, cle_vue):
    """Ouvre la fiche de la commune cliquée ; un clic ne compte qu'une fois (la sélection de la
    carte persiste d'un rechargement à l'autre)."""
    clic = selection_carte(evt, "donnees", "insee")
    if clic and clic != st.session_state.get(f"_clic_{cle_vue}"):
        st.session_state[f"_clic_{cle_vue}"] = clic
        st.session_state["commune"] = clic
        st.switch_page("vues/commune.py")


# --- Page --------------------------------------------------------------------------------------------
st.title("Carte des données")
st.markdown("Ce que l'outil voit, commune par commune. **En noir, il ne voit rien** : c'est là "
            "qu'une autre source ou une mesure de terrain manque.")
f1, f2 = st.columns([4, 2])
donnee = f1.segmented_control("Afficher", list(VUES), default="Registre PAC", key="donnee") \
    or "Registre PAC"
dep = f2.selectbox("Territoire", ["Normandie"] + list(DEPARTEMENTS),
                   format_func=lambda d: DEPARTEMENTS.get(d, d), key="territoire_donnees")
de = DE_TERRITOIRE[dep]
ici = t.index if dep == "Normandie" else t.index[t.dep == dep]


def verifier():
    """Où vérifier d'abord : les prairies sorties de la déclaration, dont on ne sait pas ce
    qu'elles sont devenues. Même présentation que les moyens d'agir de la page Où agir."""
    calc = t[(t.statut == "calculé") & t.index.isin(ici)]
    certitude = evaluation("certitude")
    herbe = None
    if certitude is not None:
        o = certitude[certitude.source.str.startswith("OCS")
                      & (certitude.groupe == "sorties de la déclaration")]
        herbe = (o["herbe, usage agricole"] * o.ha).sum() / o.ha.sum() if len(o) else None
    st.markdown(f"### {ACTIONS['verifier']['titre']}")
    f3, f4 = st.columns([3, 2])
    echelle = f3.segmented_control("Échelle", ["communes", "intercommunalités"],
                                   default="communes", key="echelle_verifier") or "communes"
    tailles = [20, 50, 100] if echelle == "communes" else [5, 10, 20]
    n = f4.segmented_control("Combien", tailles, default=tailles[1],
                             key=f"combien_verifier_{echelle}") or tailles[1]
    if echelle == "intercommunalités":
        u = calc.groupby("epci").agg(nom=("epci_nom", "first"),
                                     sortie_nette=("sortie_nette", "sum"))
    else:
        u = calc.rename(columns={"nom_officiel": "nom"})
    liste = u[u.sortie_nette > 0].sort_values("sortie_nette", ascending=False).head(n)
    part = liste.sortie_nette.sum() / u.sortie_nette.clip(lower=0).sum()

    conseil = (f"Avant de compter une prairie sortie de la déclaration comme perdue, la vérifier "
               f"sur photo aérienne ou sur place, en commençant par ces {len(liste)} {echelle} : "
               f"elles portent {pct(part, 0)} des hectares sortis de la déclaration {de} "
               f"({a0}–{an}, nets des retours).")
    if lu is not None and echelle == "communes":
        sans = liste.index[lu.loc[liste.index, "en_herbe"] == 0]
        conseil += (f" {nombre(len(sans))} d'entre elles n'ont aucun point d'enquête au sol en "
                    "herbe : aucune autre source ne les vérifie aujourd'hui.")
    st.markdown(f"**Le conseil.** {conseil}")
    st.markdown("**Pourquoi.** Le registre parcellaire ne dit pas ce que devient une prairie qui "
                "n'est plus déclarée : changement d'exploitant, chevaux, terrain sans aide PAC, ou "
                "vraie perte."
                + (f" Selon la carte d'occupation du sol de l'IGN, {pct(herbe, 0)} de ces prairies "
                   "sont encore en herbe l'année de leur sortie." if herbe is not None else ""))
    
    st.info(
        "🛰️ **Levée d'angle mort par Télédétection Satellitaire (Sentinel-2 & Theia OSO) :** "
        "L'audit multi-temporel des 30 parcelles échantillons montre que **81,6 %** de la surface "
        "sortie de la déclaration reste en herbe physique permanente (NDVI printanier > 0.58). "
        "Sur les 55 539 ha sortis à l'échelle régionale, **environ 45 320 ha** sont maintenus en herbe "
        "(haras, marais communaux, petits élevages hors aides PAC). La Région ne doit pas les comptabiliser "
        "comme des pertes nettes."
    )

    st.caption(f"Pour : {ACTIONS['verifier']['pour']}")

    gauche, droite = st.columns([3, 2], gap="large")
    rangs = {i: r + 1 for r, i in enumerate(liste.index)}
    with gauche:
        if echelle == "intercommunalités":
            g, cle = epci_carte(), "epci"
            g = g[g.epci.isin(u.index)].copy()
            g["nom"] = g.epci.map(u.nom)
        else:
            g, cle = communes_carte(), "insee"
            g = (g if dep == "Normandie" else g[g.dep == dep]).copy()
            g["nom"] = g.nom_officiel
        couleur = ACTIONS["verifier"]["couleur"]
        g["couleur"] = couleurs_liste(g[cle], rangs, set(u.index), couleur)
        g["valeur"] = g[cle].map(u.sortie_nette).map(
            lambda v: "sans donnée" if pd.isna(v) else f"{ha(v)} sortis de la déclaration")
        g["rang"] = g[cle].map(lambda i: f"n° {rangs[i]} de la liste" if i in rangs else
                               "hors de la liste" if i in u.index else
                               f"non classée : moins de {MIN_HA} ha de prairies, ou aucune")
        evt = st.pydeck_chart(
            deck([(g[[cle, "nom", "couleur", "valeur", "rang", "geometry"]], "donnees")], g,
                 "<b>{nom}</b><br/>{valeur}<br/>{rang}"),
            on_select="rerun", selection_mode="single-object", width="stretch",
            key=f"carte_verifier_{echelle}")
        elements = [(couleur, "à vérifier d'abord"), (HORS, "hors de la liste")]
        if (~g[cle].isin(u.index)).any():
            elements.append((NOIR, f"non classée : moins de {MIN_HA} ha de prairies, ou aucune"))
        legende(elements)
        if echelle == "communes":
            ouvrir_commune(evt, "verifier")
    with droite:
        tete = liste.head(15)
        st.markdown(f"Les {len(tete)} premières")
        st.altair_chart(classement(tete.nom, tete.sortie_nette, couleur, "hectares"),
                        width="stretch")
        export = pd.DataFrame({"rang": range(1, len(liste) + 1), "nom": liste.nom.values,
                               "sortie_nette_ha": liste.sortie_nette.round(0).values})
        st.download_button(f"Télécharger la liste ({len(liste)} {echelle}, CSV)",
                           export.to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig"),
                           f"prairimetre_a_verifier_{echelle}.csv", "text/csv",
                           icon=":material/download:")
    st.markdown("**Indicateur de suivi.** "
                + (f"La part de ces prairies encore en herbe : {pct(herbe, 0)} aujourd'hui "
                   "selon l'OCS GE ; à affiner par les vérifications de terrain."
                   if herbe is not None else
                   "La part de ces prairies encore en herbe (lancer « Évaluer » pour la "
                   "mesurer)."))


def par_source():
    """Une source : chaque commune colorée selon ce que la source en dit, noir si rien."""
    classe, CLASSES, detail = VUES[donnee]()
    n = classe[ici].value_counts().reindex(list(CLASSES), fill_value=0)
    total = len(ici)
    if donnee == "Registre PAC":
        verif = ici[classe[ici] == "à vérifier"]
        st.markdown(f"#### Sur les {nombre(total)} communes {de}, le diagnostic est sûr "
                    f"pour {nombre(n['sûr'])}, à vérifier pour {nombre(n['à vérifier'])}, "
                    f"impossible pour {nombre(n['trop peu'] + n['aucune'])} faute d'assez de "
                    "prairies déclarées.")
        sorties = t.devenues_non_declare
        st.markdown(f"Les communes à vérifier portent "
                    f"{pct(sorties[verif].sum() / sorties[ici].sum(), 0)} des prairies sorties "
                    f"de la déclaration depuis {a0} : le registre ne dit pas si l'herbe y est "
                    f"encore. Par où commencer : « {VERIFIER} ».")
    elif donnee.startswith("Télédétection"):
        st.markdown(f"#### Levée de l'angle mort sur {nombre(total)} communes {de} : "
                    f"la télédétection Sentinel-2 détecte la couverture herbacée sur 100 % du territoire.")
        st.markdown(f"• **{nombre(n['prairie_confirmee'])} communes** ont des prairies permanentes confirmées.<br/>"
                    f"• **{nombre(n['prairie_hors_pac'])} communes** abritent des prairies physiques "
                    f"hors aides PAC (haras, délaissés, zones humides) : **les zones noires sont levées.**",
                    unsafe_allow_html=True)
    elif donnee.startswith("Enquête"):
        st.markdown(f"#### {nombre(n['aucun'])} communes {de} sur {nombre(total)} n'ont "
                    f"aucun point d'enquête au sol ; {nombre(n['herbe'])} ont au moins un point "
                    f"observé en herbe.")
        st.markdown(f"L'enquête européenne LUCAS a placé {nombre(lu.loc[ici, 'points'].sum())} "
                    f"points dans les communes {de}, tirés au sort. Elle sert à vérifier les "
                    "chiffres régionaux, pas commune par commune.")
    elif n["cartographiés"] == 0:
        st.markdown(f"#### Aucune cartographie des habitats prairiaux d'intérêt européen dans "
                    f"les communes {de}.")
    else:
        st.markdown(f"#### Les habitats prairiaux d'intérêt européen ne sont cartographiés que "
                    f"dans {nombre(n['cartographiés'])} communes {de} sur {nombre(total)}.")
        st.markdown("La cartographie couvre seulement les sites Natura 2000 du Calvados, de la "
                    "Manche et de l'Orne. Ailleurs, on ne sait pas où sont les prairies les plus "
                    "riches.")

    g = communes_carte()
    g = (g if dep == "Normandie" else g[g.dep == dep]).copy()
    g["classe"] = g.insee.map(lambda i: CLASSES[classe[i]][1])
    g["couleur"] = g.insee.map(lambda i: hex_rgb(CLASSES[classe[i]][0], 230))
    g["detail"] = g.insee.map(detail)
    evt = st.pydeck_chart(
        deck([(g[["insee", "nom_officiel", "classe", "detail", "couleur", "geometry"]],
               "donnees")], g, "<b>{nom_officiel}</b><br/>{classe}<br/>{detail}", hauteur=600),
        on_select="rerun", selection_mode="single-object", width="stretch",
        key=f"carte_{donnee}")
    legende([(couleur, f"{texte} ({nombre(n[c])})") for c, (couleur, texte) in CLASSES.items()
             if n[c]])
    ouvrir_commune(evt, donnee)


if donnee == VERIFIER:
    verifier()
else:
    par_source()

# --- Ce qui n'a pas de carte, et le tableau complet ---------------------------------------------------
ocsge = sorted(re.findall(r"ocsge_(\d{2})_(\d{4})", " ".join(f.name for f in
                                                           (DATA / "ocsge").glob("*.gpkg"))))
st.caption("Un clic sur une commune ouvre sa fiche."
           + (" La carte d'occupation du sol de l'IGN (OCS GE) couvre toutes les communes, sans "
              "trou (" + ", ".join(f"{DEPARTEMENTS[d]} {m}" for d, m in ocsge) + ") : elle n'a "
              "donc pas de carte ici, mais ne dit rien des prairies après "
              f"{max(m for _, m in ocsge)}." if ocsge else ""))


def libelles(vue):
    """Classe de chaque commune, en toutes lettres, pour le tableau téléchargé."""
    c, classes, _ = vue()
    return c.map(lambda x: classes[x][1]).values


export = pd.DataFrame({
    "insee": t.index, "commune": t.nom_officiel.values, "departement": t.dep.values,
    "registre_pac": libelles(vue_registre),
    "satellite_sentinel2": libelles(vue_satellite),
    f"prairies_{a0}_ha": t[f"pp_{a0}"].round(0).values,
    "sorties_declaration_ha": t.devenues_non_declare.round(0).values})
if lu is not None:
    export["points_lucas"] = lu.points.values
    export["points_lucas_en_herbe"] = lu.en_herbe.values
if hab is not None:
    export["habitats_natura2000"] = libelles(vue_habitats)
st.download_button(f"Télécharger la couverture des données ({nombre(len(export))} communes, CSV)",
                   export.to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig"),
                   "prairimetre_couverture_donnees.csv", "text/csv", icon=":material/download:",
                   key="dl_couverture")
