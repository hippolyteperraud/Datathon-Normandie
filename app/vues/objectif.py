"""1. L'objectif 2030 : où en est-on ? La mesure officielle (statistique agricole), le registre PAC à
côté, et pourquoi le registre dit pire. Tout tient sur un écran ; le détail des années à part est dans
Technique, ce qu'il faut faire dans Ce qui marche."""
import altair as alt
import pandas as pd
import streamlit as st

from commun import ACTIONS, AXE_FR, bornes, exiger_sorties, ha, nombre, pct, table
from references import AGRICULTEUR_ACTIF, OBJECTIF_REGIONAL

exiger_sorties()
a0, an = bornes()
obj = table("objectif").set_index("annee")
o = OBJECTIF_REGIONAL
a_ref, a_obj = int(obj.annee_reference.iloc[0]), int(obj.annee_objectif.iloc[0])
registre = obj.prairies_ha.dropna()
herbe = obj.sth_ha.dropna()
part = obj.part_sth.dropna() if "part_sth" in obj else pd.Series(dtype=float)
fin = int(herbe.index.max())
perte_herbe = herbe.loc[fin] - herbe.loc[a_ref]
perte_registre = registre.loc[an] - registre.loc[a_ref]
GRIS, BLEU = "#6f6e66", ACTIONS["suivre"]["couleur"]

st.title(f"Objectif {a_obj} : zéro perte nette de prairies permanentes")
tenu = perte_herbe >= 0
st.markdown(
    f"### {'Tenu' if tenu else 'Pas tenu'} : depuis {a_ref}, la Normandie a "
    f"{'gagné' if tenu else 'perdu'} {ha(abs(perte_herbe))} de prairies permanentes"
    + (f", et leur part dans la surface agricole passe de {pct(part.loc[a_ref], 1)} à "
       f"{pct(part.loc[fin], 1)}." if a_ref in part.index and fin in part.index else "."),
    help=f"« {o['periode']} », cible « {o['cible']} » ({o['texte']}). La dernière année de la "
         "statistique agricole est provisoire.")

# --- Les deux chiffres à gauche, les deux courbes à droite ---------------------------------------
gauche, droite = st.columns([1, 2.2], gap="large", vertical_alignment="center")
gauche.metric(f"Mesure officielle, {a_ref}→{fin}", ha(perte_herbe, signe=True),
              "statistique agricole (Agreste) : toute l'herbe", delta_color="off", delta_arrow="off",
              border=True)
gauche.metric(f"Registre PAC, {a_ref}→{an}", ha(perte_registre, signe=True),
              "prairies déclarées à la PAC seulement", delta_color="off", delta_arrow="off", border=True)

d = pd.concat([registre.rename("ha").reset_index().assign(source="registre PAC"),
               herbe.rename("ha").reset_index().assign(source="statistique agricole")])
d["valeur"] = d.ha.map(ha)
couleurs = alt.Scale(domain=["statistique agricole", "registre PAC"], range=[GRIS, BLEU])
base = alt.Chart(d).encode(
    x=alt.X("annee:O", title=None, axis=alt.Axis(labelAngle=0, labelFontSize=12, ticks=False,
                                                  domain=False)),
    y=alt.Y("ha:Q", title=None, axis=alt.Axis(labelExpr=AXE_FR + " + ' ha'", tickCount=4, labelFontSize=11,
                                              domain=False, ticks=False, gridOpacity=0.35),
            scale=alt.Scale(zero=False, domain=[d.ha.min() * 0.96, d.ha.max() * 1.02])),
    color=alt.Color("source:N", scale=couleurs, legend=None))
lignes = base.mark_line(strokeWidth=3, point=alt.OverlayMarkDef(size=50)).encode(
    tooltip=[alt.Tooltip("annee:O", title="année"), alt.Tooltip("source:N"),
             alt.Tooltip("valeur:N", title="prairies")])
# Le nom de chaque courbe écrit au-dessus de son premier point : pas de légende à chercher
noms = base.transform_filter(alt.datum.annee == int(d.annee.min())).mark_text(
    align="left", dx=-4, dy=-14, fontSize=13, fontWeight="bold").encode(text="source:N")
repere = alt.Chart(pd.DataFrame({"annee": [a_ref], "texte": [f"référence {a_ref}"]}))
regle = repere.mark_rule(color="#a9a89f", strokeDash=[4, 3]).encode(x="annee:O")
texte_repere = repere.mark_text(align="left", dx=5, baseline="top", fontSize=11, color="#8a897f").encode(
    x="annee:O", y=alt.value(2), text="texte:N")
droite.altair_chart((regle + texte_repere + lignes + noms).properties(height=240), width="stretch")

# --- Pourquoi le registre dit pire : une phrase -----------------------------------------------------
aa = AGRICULTEUR_ACTIF
phrase = (f"**Pourquoi le registre dit pire.** En 2023, la PAC réserve ses aides aux « agriculteurs "
          f"actifs » : {nombre(aa['sortants'])} exploitations sortent, dont près de "
          f"{aa['part_67_ans_pct']} sur 100 ont un chef de 67 ans ou plus. Leurs prairies quittent le "
          "registre")
try:
    from prairimetre.sentinel import resume_mesures
    r = resume_mesures()
except FileNotFoundError:
    r = None
if r and r["part_verte"] is not None:
    phrase += (f", mais pas le paysage : vu du satellite en {an}, **{round(100 * r['ha_verts'] / r['ha'])} ha "
               f"sur 100 des prairies sorties sont restés verts**, sans labour.")
else:
    phrase += ", mais la statistique agricole, qui compte toute l'herbe, ne les perd pas."
st.markdown(phrase)

# --- Les prairies de la première année, aujourd'hui : en herbe, plus en herbe, à vérifier -----------
from commun import DEPARTEMENTS, herbe_communes  # noqa: E402
from prairimetre import sentinel as sen  # noqa: E402


h = herbe_communes()
FAMILLES_HERBE = {"en herbe": (sen.HERBE, "#2e7d4f"),
                  "plus en herbe": (sen.PAS_HERBE, "#c2452d"),
                  "à vérifier sur le terrain": (["verifier"], "#f0a202")}
par_dep = h.groupby("dep")[sen.CLASSES].sum()
par_dep.index = par_dep.index.map(lambda k: DEPARTEMENTS.get(k, k))
par_dep.loc["Normandie"] = par_dep.sum()
lignes = []
for lieu, x in par_dep.iterrows():
    total = x.sum()
    for fam, (cles, _) in FAMILLES_HERBE.items():
        v = x[cles].sum()
        lignes.append({"lieu": lieu, "famille": fam, "sur100": 100 * v / total, "t_ha": ha(v),
                       "texte": f"{round(100 * v / total)}" if 100 * v / total >= 4 else ""})
dh = pd.DataFrame(lignes)
ordre_lieux = ["Normandie"] + sorted(l for l in par_dep.index if l != "Normandie")
herbe_region = 100 * par_dep.loc["Normandie", sen.HERBE].sum() / par_dep.loc["Normandie"].sum()
st.markdown(f"**Les prairies de {a0}, en {an} : {round(herbe_region)} ha sur 100 sont encore en herbe.** "
            "Ce qui ne l'est plus, et ce qu'il faut aller voir :",
            help="En herbe : toujours déclarées en prairie, devenues prairies temporaires, ou sorties de la PAC "
                 "mais vertes toute l'année sur les images Sentinel-2. Plus en herbe : retournées en culture, "
                 "sorties puis labourées ou bâties, devenues bois ou landes. À vérifier : sorties que le "
                 "satellite ne tranche pas, ou trop petites pour être mesurées. Les bordures (écarts de "
                 "contour d'une année à l'autre) suivent leur parcelle, comme sur la carte de Ma commune. "
                 + ("" if r is None or r["parcelles"] >= r["cible_parcelles"] else
                    f"Mesure satellite en cours : {nombre(r['cible_parcelles'] - r['parcelles'])} parcelles "
                    "restent à mesurer, la part « à vérifier » va baisser."))
pertes = dh[dh.famille != "en herbe"].copy()
pertes["rang"] = pertes.famille.map({"plus en herbe": 0, "à vérifier sur le terrain": 1})
pertes["texte"] = pertes.sur100.map(lambda v: nombre(v, 0) if v >= 1.5 else "")
herbe = dh[dh.famille == "en herbe"].assign(
    etiquette=lambda x: x.sur100.map(lambda v: f"{round(v)} ha sur 100 encore en herbe"))
fin = pertes.groupby("lieu").sur100.sum()
herbe["x"] = herbe.lieu.map(fin)
y = alt.Y("lieu:N", sort=ordre_lieux, title=None,
          axis=alt.Axis(ticks=False, domain=False, labelFontSize=12, labelOverlap=False, labelPadding=8,
                        labelFontWeight=alt.expr("datum.value == 'Normandie' ? 700 : 400")))
x_max = fin.max() * 2.1
barres = alt.Chart(pertes).mark_bar(cornerRadiusEnd=3).encode(
    y=y, x=alt.X("sur100:Q", stack="zero", title=None, axis=None, scale=alt.Scale(domain=[0, x_max])),
    order=alt.Order("rang:Q"),
    color=alt.Color("famille:N", title=None, legend=alt.Legend(orient="top", labelFontSize=12),
                    scale=alt.Scale(domain=["plus en herbe", "à vérifier sur le terrain"],
                                    range=["#c2452d", "#f0a202"])),
    tooltip=[alt.Tooltip("lieu:N", title=" "), alt.Tooltip("famille:N", title=" "),
             alt.Tooltip("t_ha:N", title="surface")])
chiffres = alt.Chart(pertes).mark_text(color="white", fontSize=11, fontWeight="bold").encode(
    y=y, x=alt.X("milieu:Q", scale=alt.Scale(domain=[0, x_max])), text="texte:N").transform_window(
    cumul="sum(sur100)", sort=[alt.SortField("rang")], groupby=["lieu"]).transform_calculate(
    milieu="datum.cumul - datum.sur100 / 2")
sombre = st.context.theme.type == "dark"
reste = alt.Chart(herbe).mark_text(align="left", dx=8, fontSize=12,
                                   color="#d6d5cd" if sombre else "#2e7d4f").encode(
    y=y, x=alt.X("x:Q", scale=alt.Scale(domain=[0, x_max])), text="etiquette:N")
st.altair_chart((barres + chiffres + reste).properties(height=30 * len(ordre_lieux)), width="stretch")
st.caption("Ha sur 100 des prairies déclarées en " + str(a0) + ", par département. Le détail (2019, 2023, ratio de la PAC, "
           "satellite) : Technique. Ce qu'il faut faire : Ce qui marche.")
