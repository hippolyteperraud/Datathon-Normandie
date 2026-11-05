"""Lexique et définitions : les mots de l'outil, en clair, et les chiffres qui circulent sur les
prairies normandes."""
import importlib
import streamlit as st

import commun
importlib.reload(commun)
from commun import LEXIQUE, OFFICIEL, SEUIL_RATIO_PCT, bornes, ha, manquantes, nombre, table
from prairimetre.config import ANNEE_REFERENCE_OBJECTIF

st.title("Lexique et définitions")

recherche = st.text_input(
    "Filtrer les termes du lexique",
    placeholder="Ex. : NDVI, BCAE, RPG, retournement, captage, Sentinel-2…",
    label_visibility="collapsed",
)

termes_filtres = {
    mot: sens
    for mot, sens in LEXIQUE.items()
    if not recherche.strip()
    or recherche.lower() in mot.lower()
    or recherche.lower() in sens.lower()
}

if not termes_filtres:
    st.info(f"Aucun terme ne correspond à « {recherche} ».")
else:
    for mot, sens in termes_filtres.items():
        st.markdown(f"**{mot}**  \n{sens[0].upper()}{sens[1:]}")

st.divider()
st.subheader("Barème biophysique du score NDVI (Sentinel-2)")
st.markdown("""
Formule : $\\text{NDVI} = \\frac{\\text{NIR (B08)} - \\text{Red (B04)}}{\\text{NIR (B08)} + \\text{Red (B04)}}$ (résolution spatiale : **10 m**, revisite : **5 jours**).

| Couvert observé | NDVI minimal (hiver / labour) | NDVI maximal (printemps) | Amplitude annuelle ($\\max - \\min$) | Diagnostic Prairimètre |
|---|---|---|---|---|
| **Prairie permanente maintenue** | $\\ge 0,40$ | $\\ge 0,58$ | $\\le 0,28$ | **Maintien en herbe** (fausse perte administrative si sortie PAC) |
| **Friche ou pâture extensive** | $\\ge 0,32$ | Moyenne $\\ge 0,48$ | Modérée | **Maintien en herbe** (extensif / chevaux / délaissé) |
| **Culture annuelle (blé, maïs…)** | $< 0,25$ (sol nu / labour) | $> 0,65$ | $> 0,35$ | **Retournement réel** (perte de prairie) |
| **Boisement / forêt dense** | $> 0,65$ | Moyenne $> 0,72$ | Faible | **Boisement / ligneux** |
| **Surface bâtie ou minérale** | $< 0,25$ | $< 0,28$ | Très faible | **Artificialisation** (bâti, voirie, carrière) |
""")

st.divider()
st.subheader("Quatre chiffres, quatre définitions")
if manquantes():
    st.info("Pas encore de résultats : lancez le calcul dans Données et méthode → Moteur.")
    st.stop()
a0, an = bornes()
bil = table("bilan_direct").loc["région"]
solde = bil[("nouvelles_venant_de", "arrivee")] - bil[("disparues_devenues", "depart")]
st.markdown(f"""
Quatre chiffres circulent sur les prairies normandes. Ils ne comptent pas la même chose.

| Chiffre | Ce qu'il compte | Évolution |
|---|---|---|
| Prairimètre | prairies permanentes déclarées à la PAC (RPG, groupe de cultures 18), en Normandie | {ha(solde, signe=True)} ({a0}→{an}) |
| Chiffre officiel | prairies permanentes au sens réglementaire de la PAC, région Normandie | {ha(OFFICIEL['perte_ha'], signe=True)} ({nombre(OFFICIEL['perte_pct'], 1)} %) |
| Ratio officiel | part des prairies permanentes dans la surface agricole | {nombre(OFFICIEL['ratio_evol_pct'], 2)} % |
| Statistique agricole annuelle | prairies permanentes productives (enquête, toutes exploitations) | voir Données et méthode → Preuves |

- Le groupe 18 du RPG réunit les prairies permanentes (PPH) et, jusqu'en 2022, les prairies de
  plus de cinq ans (PRL). En 2023, les PRL disparaissent : 94 % d'entre elles deviennent PPH, et la
  série reste continue.
- Le ratio est comparé à un ratio de référence, recalculé en 2024 (règlement UE 2024/1235) après le
  passage de la Normandie au régime d'interdiction en 2023. Il ne recule que de
  {nombre(-OFFICIEL['ratio_evol_pct'], 2)} %, loin du seuil d'alerte de {SEUIL_RATIO_PCT} %, alors
  que les hectares diminuent nettement. C'est pourquoi l'outil suit les hectares plutôt que le ratio.
- L'objectif de zéro perte nette en 2030 est mesuré par rapport au niveau de
  {ANNEE_REFERENCE_OBJECTIF}.
- Source du chiffre officiel : {OFFICIEL['source']}.
""")
