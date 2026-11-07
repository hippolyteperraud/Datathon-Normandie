"""1. L'objectif 2030 : où en est-on ? La mesure officielle (statistique agricole), le registre PAC à
côté, et pourquoi le registre dit pire. Le détail des années à part est dans Technique."""
import altair as alt
import pandas as pd
import streamlit as st

from commun import ACTIONS, AXE_FR, bornes, exiger_sorties, ha, nombre, pct, table
from humain import bandeau
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

bandeau("Prairimètre", "Le suivi des prairies permanentes de Normandie")
st.title(f"L'objectif {a_obj} : zéro perte nette de prairies permanentes")

tenu = perte_herbe >= 0
st.markdown(
    f"### {'Tenu' if tenu else 'Pas tenu'} : depuis {a_ref}, la Normandie a "
    f"{'gagné' if tenu else 'perdu'} {ha(abs(perte_herbe))} de prairies permanentes"
    + (f", et leur part dans la surface agricole passe de {pct(part.loc[a_ref], 1)} à "
       f"{pct(part.loc[fin], 1)}." if a_ref in part.index and fin in part.index else "."),
    help=f"« {o['periode']} », cible « {o['cible']} » ({o['texte']}). La dernière année de la "
         "statistique agricole est provisoire.")

c1, c2 = st.columns(2)
c1.metric(f"Mesure officielle, {a_ref}→{fin}", ha(perte_herbe, signe=True),
          "statistique agricole (Agreste) : toute l'herbe permanente", delta_color="off",
          delta_arrow="off", border=True)
c2.metric(f"Registre PAC, {a_ref}→{an}", ha(perte_registre, signe=True),
          "prairies déclarées à la PAC seulement", delta_color="off", delta_arrow="off", border=True)

# --- Les deux sources, une courbe chacune ---------------------------------------------------------
d = pd.concat([registre.rename("ha").reset_index().assign(source="registre PAC"),
               herbe.rename("ha").reset_index().assign(source="statistique agricole")])
d["valeur"] = d.ha.map(ha)
ligne = alt.Chart(d).mark_line(strokeWidth=2.5, point=alt.OverlayMarkDef(size=55)).encode(
    x=alt.X("annee:O", title=None, axis=alt.Axis(labelAngle=0)),
    y=alt.Y("ha:Q", title="hectares", axis=alt.Axis(labelExpr=AXE_FR),
            scale=alt.Scale(zero=False, domain=[d.ha.min() * 0.97, d.ha.max() * 1.01])),
    color=alt.Color("source:N", title=None, legend=alt.Legend(orient="bottom"),
                    scale=alt.Scale(domain=["statistique agricole", "registre PAC"],
                                    range=["#8a897f", ACTIONS["suivre"]["couleur"]])),
    tooltip=[alt.Tooltip("annee:O", title="année"), alt.Tooltip("source:N"),
             alt.Tooltip("valeur:N", title="prairies")])
repere = alt.Chart(pd.DataFrame({"annee": [a_ref]})).mark_rule(color="#8a897f", strokeDash=[4, 3]) \
    .encode(x="annee:O")
st.altair_chart((ligne + repere).properties(height=320), width="stretch")

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
    phrase += (f", mais pas le paysage : vu du satellite en {an}, **{nombre(100 * r['part_verte'], 0)} ha "
               f"sur 100 des prairies sorties de la déclaration sont restés verts**, sans labour "
               f"({ha(r['ha'])} mesurés sur {ha(r['cible_ha'])}).")
else:
    phrase += ", mais la statistique agricole, qui compte toute l'herbe, ne les perd pas."
st.markdown(phrase)
st.caption("Le détail (2019, 2023, ratio de la PAC, vérification par satellite) : Technique.")

# --- Ce qu'il faut faire : quatre actions, chacune tirée des résultats et prouvée dans un onglet -----
from commun import communes_moitie, comparaison, evaluation  # noqa: E402

terrain, zon = evaluation("terrain"), evaluation("zonages", index_col=0)
t = table("communes")
st.subheader("Ce qu'il faut faire")
actions = [(None,
            f"**Suivre l'objectif avec la bonne mesure** : la part de l'herbe dans la surface agricole "
            f"(statistique agricole), chaque année. Le registre PAC dit où et comment on perd, pas "
            f"combien ; le ratio de la PAC ne donne plus l'alerte.")]
if terrain is not None and zon is not None:
    r = terrain.set_index("comparaison").rapport_meme_commune
    _, aac = comparaison("aires_alimentation_captages")
    actions.append(("vues/regles.py",
                    f"**Étendre la protection contre le retournement** : à terrain égal, l'interdiction "
                    f"divise le retournement par {nombre(1 / r[r.index.str.contains('Natura')].iloc[0], 0)} à "
                    f"{nombre(1 / r[r.index.str.contains('zones humides')].iloc[0], 0)}, mais ne couvre que "
                    f"{nombre(100 * zon.loc['prairies_sensibles', 'part_des_prairies'], 0)} ha de prairies sur "
                    "100" + (" ; au-dessus des captages d'eau potable, rien ne retient l'herbe." if len(aac) and
                             0.85 < aac.mean() < 1.2 else ".")))
actions.append(("vues/agir.py",
                f"**Commencer par {nombre(len(communes_moitie(t)))} communes**, qui portent la moitié du "
                "retournement récent, et s'appuyer sur les communes exemples, qui gagnent ou gardent "
                "leurs prairies."))
actions.append(("vues/technique.py",
                "**Vérifier chaque année par satellite les prairies sorties de la PAC** avant de les compter "
                "comme perdues : la plupart restent vertes, sans labour."))
for page, texte in actions:
    g, d = st.columns([6, 1], vertical_alignment="center")
    g.markdown(texte)
    if page:
        try:  # le lien n'existe que dans l'appli lancée par accueil.py (menu)
            d.page_link(page, label="Voir", icon=":material/arrow_forward:")
        except st.errors.StreamlitAPIException:
            pass
