"""Carte des données : ce que l'outil voit, commune par commune. En noir, les communes où la
source choisie ne dit rien. On y lit d'un coup d'œil où le diagnostic est sûr, où il reste à
vérifier, et où une mesure de terrain serait la plus utile."""
import re

import pandas as pd
import streamlit as st

from commun import (CAT, DEPARTEMENTS, MIN_HA, NEUTRE, bornes, communes_carte, deck,
                    exiger_sorties, ha, hex_rgb, legende, nombre, pct, selection_carte, table)
from prairimetre.config import CACHE, DATA
from prairimetre.sources import SOURCES

NOIR, GRIS = "#000000", "#6b6a65"
OUEST = ["14", "50", "61"]  # départements couverts par la cartographie des habitats Natura 2000

exiger_sorties()
a0, an = bornes()
t = table("communes")


def disponible(source, cache):
    """Une source est utilisable si son fichier est dans data/ ou déjà mis en cache."""
    return (DATA / SOURCES[source]["fichier"]).exists() or (CACHE / f"{cache}.parquet").exists()


@st.cache_data(show_spinner="Croisement des points d'enquête avec les communes…")
def lucas_par_commune():
    """Points d'enquête LUCAS 2022 par commune : nombre total, nombre observés en herbe."""
    import geopandas as gpd
    from prairimetre.donnees import communes, lucas
    j = gpd.sjoin(lucas(), communes()[["insee", "geometry"]], predicate="within")
    return j.groupby("insee").agg(points=("point_id", "size"),
                                  en_herbe=("prairie_terrain", "sum"))


@st.cache_data(show_spinner="Croisement des habitats avec les communes…")
def habitats_par_commune():
    """Communes touchées par la cartographie des habitats prairiaux Natura 2000."""
    import geopandas as gpd
    from prairimetre.donnees import communes, habitats_prairiaux
    j = gpd.sjoin(habitats_prairiaux()[["geometry"]], communes()[["insee", "geometry"]],
                  predicate="intersects")
    return set(j.insee)


lu = lucas_par_commune().reindex(t.index, fill_value=0) if disponible("lucas", "lucas") \
    else None
hab = habitats_par_commune() if disponible("habitats_natura2000", "habitats_prairiaux") \
    else None


# --- Les trois vues : une classe par commune, sa couleur, son détail au survol ----------------------
def vue_registre():
    classes = {
        "sûr": (CAT[0], "diagnostic sûr : les pertes sont surtout déclarées en culture"),
        "à vérifier": (CAT[1], "à vérifier : les pertes sont surtout des sorties de la "
                               "déclaration, une mesure serait utile"),
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


VUES = {"Registre PAC": vue_registre}
if lu is not None:
    VUES["Enquête au sol (LUCAS 2022)"] = vue_lucas
if hab is not None:
    VUES["Habitats prairiaux (Natura 2000)"] = vue_habitats

# --- Page --------------------------------------------------------------------------------------------
st.title("Carte des données")
st.markdown("Ce que l'outil voit, commune par commune. **En noir, il ne voit rien** : c'est là "
            "qu'une autre source ou une mesure de terrain manque.")
f1, f2 = st.columns([3, 2])
donnee = f1.segmented_control("Donnée", list(VUES), default="Registre PAC", key="donnee") \
    or "Registre PAC"
dep = f2.selectbox("Territoire", ["Normandie"] + list(DEPARTEMENTS),
                   format_func=lambda d: DEPARTEMENTS.get(d, d), key="territoire_donnees")
de = {"Normandie": "de Normandie", "14": "du Calvados", "27": "de l'Eure", "50": "de la Manche",
      "61": "de l'Orne", "76": "de la Seine-Maritime"}[dep]

classe, CLASSES, detail = VUES[donnee]()
ici = t.index if dep == "Normandie" else t.index[t.dep == dep]
n = classe[ici].value_counts().reindex(list(CLASSES), fill_value=0)
total = len(ici)

if donnee == "Registre PAC":
    verif = ici[classe[ici] == "à vérifier"]
    st.markdown(f"#### Sur les {nombre(total)} communes {de}, le diagnostic est sûr "
                f"pour {nombre(n['sûr'])}, à vérifier pour {nombre(n['à vérifier'])}, impossible "
                f"pour {nombre(n['trop peu'] + n['aucune'])} faute d'assez de prairies déclarées.")
    sorties = t.devenues_non_declare
    phrase = (f"Les communes à vérifier portent {pct(sorties[verif].sum() / sorties[ici].sum(), 0)} "
              f"des prairies sorties de la déclaration depuis {a0} : le registre ne dit pas si "
              "l'herbe y est encore.")
    if lu is not None:
        sans = verif[lu.loc[verif, "en_herbe"] == 0]
        phrase += (f" {nombre(len(sans))} d'entre elles n'ont aucun point d'enquête au sol en "
                   "herbe : c'est là qu'une photo aérienne ou un relevé de terrain apporterait le "
                   "plus.")
    st.markdown(phrase)
elif donnee.startswith("Enquête"):
    st.markdown(f"#### {nombre(n['aucun'])} communes {de} sur {nombre(total)} n'ont "
                f"aucun point d'enquête au sol ; {nombre(n['herbe'])} ont au moins un point "
                f"observé en herbe.")
    st.markdown(f"L'enquête européenne LUCAS a placé {nombre(lu.loc[ici, 'points'].sum())} points "
                f"dans les communes {de}, tirés au sort. Elle sert à vérifier les chiffres "
                "régionaux, pas commune par commune.")
elif n["cartographiés"] == 0:
    st.markdown(f"#### Aucune cartographie des habitats prairiaux d'intérêt européen dans les "
                f"communes {de}.")
else:
    st.markdown(f"#### Les habitats prairiaux d'intérêt européen ne sont cartographiés que dans "
                f"{nombre(n['cartographiés'])} communes {de} sur {nombre(total)}.")
    st.markdown("La cartographie couvre seulement les sites Natura 2000 du Calvados, de la Manche "
                "et de l'Orne. Ailleurs, on ne sait pas où sont les prairies les plus riches.")

g = communes_carte()
g = (g if dep == "Normandie" else g[g.dep == dep]).copy()
g["classe"] = g.insee.map(lambda i: CLASSES[classe[i]][1])
g["couleur"] = g.insee.map(lambda i: hex_rgb(CLASSES[classe[i]][0], 230))
g["detail"] = g.insee.map(detail)
evt = st.pydeck_chart(
    deck([(g[["insee", "nom_officiel", "classe", "detail", "couleur", "geometry"]], "donnees")],
         g, "<b>{nom_officiel}</b><br/>{classe}<br/>{detail}", hauteur=600),
    on_select="rerun", selection_mode="single-object", width="stretch", key=f"carte_{donnee}")
legende([(couleur, f"{texte} ({nombre(n[c])})") for c, (couleur, texte) in CLASSES.items()
         if n[c]])
clic = selection_carte(evt, "donnees", "insee")
if clic:
    st.session_state["commune"] = clic
    st.switch_page("vues/commune.py")

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
    f"prairies_{a0}_ha": t[f"pp_{a0}"].round(0).values,
    "sorties_declaration_ha": t.devenues_non_declare.round(0).values})
if lu is not None:
    export["points_lucas"] = lu.points.values
    export["points_lucas_en_herbe"] = lu.en_herbe.values
if hab is not None:
    export["habitats_natura2000"] = libelles(vue_habitats)
st.download_button(f"Télécharger la couverture des données ({nombre(len(export))} communes, CSV)",
                   export.to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig"),
                   "prairimetre_couverture_donnees.csv", "text/csv", icon=":material/download:")
