"""2. Ce qui retient les prairies : l'interaction entre les règles et le retournement, mesurée à
terrain égal (sorties/evaluation_terrain.csv, evaluation_zonages.csv, evaluation_classes.csv)."""
import altair as alt
import pandas as pd
import streamlit as st

from commun import comparaison, evaluation, exiger_sorties, nombre

exiger_sorties()
st.title("Ce qui retient les prairies")

terrain = evaluation("terrain")
zon = evaluation("zonages", index_col=0)
cl = evaluation("classes", index_col=0)
_, captages = comparaison("aires_alimentation_captages")
if terrain is None or zon is None or cl is None:
    st.info("Résultats manquants : lancez « Relancer les calculs » dans Technique.")
    st.stop()

r = terrain.set_index("comparaison").rapport_meme_commune
seul = r[r.index.str.startswith("inventaires")].iloc[0]
n2000 = r[r.index.str.contains("Natura")].iloc[0]
humides = r[r.index.str.contains("zones humides")].iloc[0]
sensibles = zon.loc["prairies_sensibles", "part_des_prairies"]
hors = cl.loc["aucun zonage", "part_du_retournement"]

st.markdown(f"### L'interdiction de retourner retient l'herbe : à terrain égal, on retourne "
            f"{nombre(1 / n2000, 0)} à {nombre(1 / humides, 0)} fois moins. Mais elle ne protège que "
            f"{nombre(100 * sensibles, 0)} ha de prairies sur 100.")

# Combien de fois moins de retournement, dans la même commune
lignes = [("terrain seul : prairies d'inventaire, sans règle", seul, "#8a897f"),
          ("interdiction, à terrain égal : sites Natura 2000", n2000, "#2e7d4f"),
          ("interdiction, à terrain égal : zones humides", humides, "#2e7d4f")]
if len(captages):
    lignes.append(("aires de captage d'eau potable, sans règle", captages.mean(), "#c2452d"))
d = pd.DataFrame([{"comparaison": n, "fois": 1 / v, "couleur": c,
                   "texte": "autant qu'à côté" if 0.85 < v < 1.2 else f"{nombre(1 / v, 1)} fois moins"}
                  for n, v, c in lignes])
base = alt.Chart(d).encode(
    y=alt.Y("comparaison:N", sort=None, title=None,
            axis=alt.Axis(labelLimit=360, labelFontSize=13, ticks=False, domain=False)),
    x=alt.X("fois:Q", title="combien de fois moins de retournement qu'à côté, dans la même commune",
            axis=alt.Axis(labels=False, ticks=False, gridOpacity=0.2),
            scale=alt.Scale(domain=[0, d.fois.max() * 1.25])))
barres = base.mark_bar(height=22, cornerRadiusEnd=4).encode(
    color=alt.Color("couleur:N", scale=None), tooltip=[alt.Tooltip("texte:N", title=" ")])
clair = st.context.theme.type == "dark"
textes = base.mark_text(align="left", dx=6, fontSize=13, fontWeight="bold",
                        color="#e8e7e0" if clair else "#33332f").encode(text="texte:N")
st.altair_chart((barres + textes).properties(height=70 * len(d)), width="stretch")

st.markdown(f"**Pour décider.** Le terrain compte (les prairies humides ou remarquables sont moins "
            f"labourées), mais l'interdiction agit en plus. Or {nombre(100 * hors, 0)} ha sur 100 du "
            "retournement se font hors de tout zonage, et au-dessus des captages d'eau potable rien ne "
            "retient l'herbe : c'est là qu'une protection manque.")
st.caption("Comparaisons dans la même commune, entre prairies de même nature. La règle sur les zones "
           "humides (BCAE 2) ne s'applique que depuis 2025 : trop tôt pour la juger. Le projet n'a pas de "
           "données sur les paiements (mesures agro-environnementales). Détail : Technique → Preuves.")
