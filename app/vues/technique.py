"""Technique : ce qui permet de vérifier et de refaire le travail : les données dont on dispose, source
par source, les chiffres qui circulent sur les prairies normandes, et les mots de l'outil."""
import streamlit as st

from cartes_sources import afficher
from commun import OFFICIEL, SEUIL_RATIO_PCT, bornes, exiger_sorties, ha, nombre, table

MOTS = {
    "Aire de captage": "zone dont l'eau rejoint un captage d'eau potable.",
    "BCAE": "règles de la PAC (la 2 : zones humides et tourbières ; la 9 : prairies sensibles).",
    "Brut, net": "net = brut moins les prairies apparues dans la même commune.",
    "EPCI": "communauté de communes, d'agglomération ou urbaine.",
    "LUCAS": "enquête de terrain européenne.",
    "MAEC, PSE": "aides pour garder ses prairies.",
    "Natura 2000": "sites européens protégés.",
    "OCS GE": "carte de l'occupation du sol (IGN).",
    "Prairie déclarée": "en herbe depuis au moins 5 ans, déclarée à la PAC.",
    "Retournée": "labourée, puis déclarée en culture.",
    "RPG": "carte des parcelles déclarées à la PAC (IGN).",
    "Sortie de la déclaration": "plus dans le registre ; l'herbe peut être encore là.",
    "Statistique agricole annuelle": "enquête du ministère de l'Agriculture.",
    "ZNIEFF": "inventaire de milieux naturels, sans effet sur le labour.",
}

exiger_sorties()
a0, an = bornes()

st.title("Technique")
st.subheader("Les données qu'on a")
afficher(table("communes"), a0, an)

st.subheader("Trois chiffres")
bil = table("bilan_direct").loc["région"]
solde = bil[("nouvelles_venant_de", "arrivee")] - bil[("disparues_devenues", "depart")]
c1, c2, c3 = st.columns(3)
c1.metric(f"Prairimètre, {a0}→{an}", ha(solde, signe=True),
          help="Prairies permanentes déclarées à la PAC (RPG, groupe 18) : les PPH et, jusqu'en "
               "2022, les PRL, devenues PPH à 94 % en 2023.")
c2.metric("Chiffre officiel", ha(OFFICIEL["perte_ha"], signe=True),
          help=f"Au sens réglementaire de la PAC. {OFFICIEL['source']}.")
c3.metric("Ratio officiel", f"{nombre(OFFICIEL['ratio_evol_pct'], 2)} %",
          help=f"Part des prairies dans la surface agricole. Au-delà de {SEUIL_RATIO_PCT} % de "
               "baisse, les retournements sont soumis à autorisation.")

st.subheader("Les mots")
lignes = [f"**{mot}** : {sens}" for mot, sens in MOTS.items()]
milieu = (len(lignes) + 1) // 2
for colonne, partie in zip(st.columns(2), (lignes[:milieu], lignes[milieu:])):
    colonne.markdown("  \n".join(partie))
