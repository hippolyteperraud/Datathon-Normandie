"""Suivre l'objectif 2030 : où en sont les prairies permanentes déclarées, ce qu'on ne sait pas
(chiffres non confirmés ou bizarres, dits explicitement), et ce qui les retient.

Rien n'est écrit à la main : chaque chiffre est tiré des sorties du moteur (sorties/) et change de
lui-même avec chaque nouveau registre parcellaire. Une année est dite « bizarre » quand ses sorties
de la déclaration dépassent le double d'une année ordinaire (médiane des autres années)."""
import altair as alt
import pandas as pd
import streamlit as st

from commun import (ACTIONS, AXE_FR, FLUX_COULEURS, OFFICIEL, SEUIL_RATIO_PCT, bornes,
                    classement, comparaison, evaluation, exiger_sorties, ha, nombre, table)
from humain import bandeau, pourquoi

FOIS_ORDINAIRE = 2  # au-delà du double d'une année ordinaire, une année est à expliquer

exiger_sorties()
a0, an = bornes()
obj, serie, bilan = table("objectif"), table("serie_region"), table("bilan_direct")
saa, cl = evaluation("saa"), evaluation("classes", index_col=0)
COULEUR, BIZARRE = ACTIONS["suivre"]["couleur"], FLUX_COULEURS["non déclaré"]

# --- Les chiffres -------------------------------------------------------------------------------
niveau = obj.set_index("annee").prairies_ha
ref = obj.iloc[0]
a_ref, a_obj = int(ref.annee_reference), int(ref.annee_objectif)
ref_ha = ref.reference_ha if pd.notna(ref.reference_ha) else niveau.get(a_ref, niveau.iloc[0])
ecart = niveau.loc[an] - ref_ha                      # < 0 : il manque des prairies
depuis_a0 = niveau.loc[an] - niveau.loc[a0]
sorties = bilan.loc["région"][("disparues_devenues", "non déclaré")]

# Une période par ligne (« 2022-2023 ») : l'année d'arrivée, le solde, les sorties de la déclaration
s = serie.assign(fin=serie.periode.str[-4:].astype(int))
s["libelle"] = s.periode.str.replace("-", "→")
s["fois"] = [v / s.sortie_non_declare.drop(i).median() for i, v in s.sortie_non_declare.items()]
s["bizarre"] = s.fois > FOIS_ORDINAIRE
if saa is not None:
    s = s.merge(saa[["annee", "saa_variation"]], left_on="fin", right_on="annee", how="left")
else:
    s["saa_variation"] = float("nan")
bizarres = s[s.bizarre]
apres = int(bizarres.fin.max()) if len(bizarres) else None   # fin de la dernière année bizarre

# --- En-tête ------------------------------------------------------------------------------------
bandeau("Prairimètre", "Le suivi des prairies permanentes de Normandie")
st.title(f"Suivre l'objectif {a_obj}")
st.markdown(f"Objectif régional : **zéro perte nette de prairies permanentes en {a_obj}**, par "
            f"rapport à {a_ref}.")


def chiffre(colonne, titre, valeur, note):
    colonne.metric(titre, valeur, note, delta_color="off", delta_arrow="off", border=True)


c1, c2, c3 = st.columns(3)
chiffre(c1, f"Prairies déclarées en {an}", ha(niveau.loc[an]),
        f"{ha(depuis_a0, signe=True)} depuis {a0}")
chiffre(c2, f"Écart au niveau de {a_ref}", ha(ecart, signe=True), f"référence {a_ref} non confirmée")
if apres is not None and apres < an:
    chiffre(c3, f"Depuis {apres}", ha(niveau.loc[an] - niveau.loc[apres], signe=True),
            f"après l'année bizarre {apres - 1}→{apres}")
elif an - 1 in niveau.index:
    chiffre(c3, f"Entre {an - 1} et {an}", ha(niveau.loc[an] - niveau.loc[an - 1], signe=True),
            "dernière année")

# --- Deux graphiques : le niveau, et le solde de chaque année face à la statistique agricole ------
gauche, droite = st.columns(2, gap="large")
with gauche:
    d = obj.rename(columns={"annee": "année", "prairies_ha": "ha"})
    d["prairies"] = d.ha.map(ha)
    ligne = alt.Chart(d).mark_line(strokeWidth=2, color=COULEUR,
                                   point=alt.OverlayMarkDef(size=60)).encode(
        x=alt.X("année:O", title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("ha:Q", title="hectares de prairies déclarées", scale=alt.Scale(zero=False),
                axis=alt.Axis(labelExpr=AXE_FR)),
        tooltip=[alt.Tooltip("année:O"), alt.Tooltip("prairies:N")])
    cible = alt.Chart(pd.DataFrame({"y": [ref_ha]})).mark_rule(
        color="#8a897f", strokeDash=[4, 3]).encode(y="y:Q")
    texte = alt.Chart(pd.DataFrame({"y": [ref_ha], "x": [str(a0)]})).mark_text(
        align="left", dy=-7, fontSize=11, color="#8a897f").encode(
        y="y:Q", x="x:O", text=alt.value(f"niveau de {a_ref}, à retrouver en {a_obj}"))
    st.markdown("**Les prairies déclarées, chaque année**")
    st.altair_chart((ligne + cible + texte).properties(height=280), width="stretch")
with droite:
    b = s[["libelle", "solde", "bizarre", "saa_variation"]].copy()
    b["registre"] = b.solde.map(lambda v: ha(v, signe=True))
    b["statistique"] = b.saa_variation.map(lambda v: "pas de donnée" if pd.isna(v)
                                           else ha(v, signe=True))
    b["etat"] = b.bizarre.map({True: "année bizarre", False: "année ordinaire"})
    x = alt.X("libelle:N", sort=None, title=None, axis=alt.Axis(labelAngle=-30))
    barres = alt.Chart(b).mark_bar(cornerRadius=3).encode(
        x=x, y=alt.Y("solde:Q", title="hectares",
                     axis=alt.Axis(labelExpr=AXE_FR)),
        color=alt.Color("etat:N", title=None, legend=alt.Legend(orient="bottom"),
                        scale=alt.Scale(domain=["année ordinaire", "année bizarre"],
                                        range=[COULEUR, BIZARRE])),
        tooltip=[alt.Tooltip("libelle:N", title="année"),
                 alt.Tooltip("registre:N", title="registre PAC"),
                 alt.Tooltip("statistique:N", title="statistique agricole")])
    points = alt.Chart(b.dropna(subset=["saa_variation"])).mark_point(
        shape="diamond", size=110, filled=True, color="#d6d5cd", stroke="#3a3a36").encode(
        x=x, y="saa_variation:Q",
        tooltip=[alt.Tooltip("libelle:N", title="année"),
                 alt.Tooltip("statistique:N", title="statistique agricole")])
    st.markdown("**Le solde de chaque année**",
                help="Barres : le registre PAC. Losanges : la statistique agricole annuelle "
                     "(Agreste), pour les années où le projet l'a.")
    st.altair_chart((barres + points).properties(height=280), width="stretch")

# --- Ce qu'on ne sait pas : chaque chiffre non confirmé ou bizarre, dit explicitement ------------
st.subheader("Ce qu'on ne sait pas")
doutes = [f"**La référence {a_ref} n'est pas confirmée** par la Région. L'écart de "
          f"{ha(ecart, signe=True)} en dépend : par rapport à {a0}, il serait de "
          f"{ha(depuis_a0, signe=True)}."]
for _, r in bizarres.iterrows():
    phrase = (f"**{r.libelle} est une année bizarre** : {ha(r.solde, signe=True)} en un an, dont "
              f"{ha(r.sortie_non_declare)} sortis de la déclaration, "
              f"{nombre(r.fois, 1)} fois une année ordinaire.")
    if pd.notna(r.saa_variation) and (r.saa_variation > 0) != (r.solde > 0):
        phrase += f" La statistique agricole dit l'inverse : {ha(r.saa_variation, signe=True)}."
    if r.fin == 2023:
        phrase += (" C'est l'année de la nouvelle PAC (les prairies de longue durée deviennent "
                   "des prairies permanentes) : explication probable, **non vérifiée**.")
    if a_ref < r.fin <= an and ecart < 0 and r.solde < 0:
        phrase += f" Elle pèse {ha(-r.solde)} des {ha(-ecart)} d'écart à l'objectif."
    doutes.append(phrase)
doutes.append(f"**{ha(sorties)} sont sortis de la déclaration** depuis {a0} : aucune source du "
              "projet ne dit si l'herbe est encore là.")
try:
    from prairimetre.satellite import PARCELLES_30, lire_observations
    n_vues = len(lire_observations())
    doutes[-1] += (f" Vérification par images satellite en cours : {n_vues} "
                   f"parcelle{'s' if n_vues > 1 else ''} vérifiée{'s' if n_vues > 1 else ''} sur "
                   f"{len(PARCELLES_30)} (page Où aller voir).")
except ValueError as erreur:
    doutes[-1] += f" Le fichier de vérification par images satellite est à corriger : {erreur}."
ratio = -OFFICIEL["ratio_evol_pct"]
if 0 <= ratio < SEUIL_RATIO_PCT:
    doutes.append(f"**Le ratio officiel ne sonne pas** : il ne recule que de {nombre(ratio, 2)} % "
                  f"({OFFICIEL['date']}), sous son seuil d'alerte de {SEUIL_RATIO_PCT} %, alors que "
                  f"les prairies déclarées ont perdu {ha(-depuis_a0)} depuis {a0}.")
debut_saa = int(saa.annee.min()) if saa is not None and len(saa) else None
ordinaires = s[~s.bizarre].sort_values("solde")
if debut_saa and len(ordinaires) and ordinaires.iloc[0].fin < debut_saa:
    r = ordinaires.iloc[0]
    doutes.append(f"**{r.libelle} est la plus forte baisse ordinaire** ({ha(r.solde, signe=True)})"
                  f" : la statistique agricole du projet commence en {debut_saa}, on ne peut pas "
                  "la comparer.")
with st.container(border=True):
    st.markdown("\n".join(f"- {d}" for d in doutes))

# --- Ce qui retient les prairies : la règle, mesurée ---------------------------------------------
if cl is not None:
    st.subheader("Ce qui retient les prairies")
    sens, rapports = comparaison("regle")
    sens_aac, _ = comparaison("aires_alimentation_captages")
    regle, hors = cl.loc["règle"], cl.loc["aucun zonage"]
    if sens == "moins":
        st.markdown(f"#### Là où une règle encadre le labour, on retourne environ "
                    f"{nombre(1 / rapports.mean(), 0)} fois moins qu'à côté, dans la même commune.")
    gauche, droite = st.columns([3, 2], gap="large")
    with gauche:
        noms = {"règle": "sous une règle qui encadre le labour", "site protégé": "site protégé",
                "inventaire seul": "inventaire seul (sans effet sur le labour)",
                "aucun zonage": "aucun zonage"}
        # Sur 1 000 ha plutôt que 100 : des nombres entiers lisibles (15, 107), sans pourcentage
        st.altair_chart(classement([noms.get(i, i) for i in cl.index], 1000 * cl.retourne / cl.ha,
                                   COULEUR, f"hectares retournés en culture depuis {a0}, sur "
                                            f"1 000 ha de prairies de {a0}"), width="stretch")
    with droite:
        chiffre(st, "Prairies sous une règle", f"{nombre(100 * regle.part_des_prairies, 0)} ha sur 100",
                "BCAE 9, BCAE 2, programme nitrates")
        chiffre(st, "Retournement hors de tout zonage",
                f"{nombre(100 * hors.part_du_retournement, 0)} ha sur 100", f"depuis {a0}")
    limites = ["**C'est une comparaison, pas une preuve de cause** : les règles portent sur des "
               "terrains humides ou fragiles, moins faciles à labourer de toute façon. Comparer dans "
               "la même commune enlève l'effet de la commune, pas celui du sol.",
               "Le projet n'a **aucune donnée sur les paiements** (mesures agro-environnementales) : "
               "il ne dit pas si payer retient l'herbe."]
    if len(rapports) > 1:
        limites.insert(0, f"Selon la période, on retourne de {nombre(1 / rapports.max(), 1)} à "
                          f"{nombre(1 / rapports.min(), 1)} fois moins sous une règle : le résultat "
                          "est solide.")
    if sens_aac == "autant":
        limites.append("Au-dessus des captages d'eau potable, on retourne autant qu'à côté.")
    st.markdown("\n".join(f"- {x}" for x in limites))

st.markdown("**À suivre à chaque nouveau registre** : le solde de l'année en hectares, et la part "
            "retournée sous une règle et hors de tout zonage.")

with st.expander("Pourquoi les prairies comptent"):
    pourquoi()
