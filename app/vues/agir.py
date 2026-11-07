"""3. Où agir : une seule carte. En rouge, les communes qui portent la moitié du retournement récent
(là où agir) ; en vert, les communes qui gagnent des prairies sur d'anciennes cultures ou n'en perdent
pas (de qui s'inspirer). Un clic sur une commune ouvre sa fiche."""
import pandas as pd
import streamlit as st

from commun import (FLUX_COULEURS, HORS, bornes, communes_carte, communes_moitie, deck, exiger_sorties,
                    ha, hex_rgb, nombre, selection_carte, table)
from prairimetre.config import RECENT

GAIN_MINIMUM_HA = 5    # en dessous, le gain pèse moins qu'une parcelle : ce n'est pas un exemple
PERTE_MAXIMUM_HA = 1   # en dessous, un écart de contour d'une année à l'autre, pas une perte

exiger_sorties()
a0, an = bornes()
r0 = an - RECENT
t = table("communes")
calc = t[t.statut == "calculé"]

# Là où agir : les communes qui portent ensemble la moitié du retournement récent
retournent = list(communes_moitie(t))
# De qui s'inspirer : un gain assuré sur d'anciennes cultures (ni une prairie temporaire devenue
# permanente, ni une nouvelle déclaration), ou aucune prairie perdue
sur_cultures = calc.venues_culture - calc.devenues_culture
temporaires = (calc.venues_temporaire - calc.devenues_temporaire).clip(lower=0)
declarees = calc.venues_non_declare - calc.devenues_non_declare
assure = pd.concat([calc.solde, sur_cultures], axis=1).min(axis=1)
gain = assure[(calc.solde > 0) & (sur_cultures >= declarees + temporaires) & (assure >= GAIN_MINIMUM_HA)]
gardent = [i for i in calc.index[calc.disparues < PERTE_MAXIMUM_HA] if i not in set(gain.index)]

ROUGE, VERT, VERT_CLAIR = FLUX_COULEURS["culture"], FLUX_COULEURS["prairie permanente"], "#8fc93a"
GROUPES = {
    "retournent": (f"Où l'on retourne le plus : {nombre(len(retournent))} communes", ROUGE, retournent,
                   f"Ensemble, elles portent la moitié des prairies retournées en culture entre {r0} et "
                   f"{an}. Là où agir en premier."),
    "gagnent": (f"Gagnent des prairies : {nombre(len(gain))} communes", VERT, list(gain.index),
                f"Au moins {GAIN_MINIMUM_HA} ha de prairies gagnés sur d'anciennes cultures depuis {a0}, "
                "net de ce qu'elles ont retourné."),
    "gardent": (f"N'en perdent pas : {nombre(len(gardent))} communes", VERT_CLAIR, gardent,
                f"Moins de {PERTE_MAXIMUM_HA} ha de leurs prairies de {a0} perdus en {an}."),
}

st.title("Où agir")
st.markdown(f"### Agir là où l'on retourne : {nombre(len(retournent))} communes portent la moitié du "
            f"retournement récent ({ha(calc.retourne_recent[retournent].sum())} en {an - r0} ans). "
            f"S'inspirer des {nombre(len(gain) + len(gardent))} communes qui gagnent ou gardent leurs "
            "prairies.")

zone_carte = st.container()  # la carte au-dessus de sa légende, qui décide de ce qu'elle montre
st.html("<style>"
        ".st-key-legende_agir button[data-variant='pills'] {display: inline-flex; align-items: center;}"
        ".st-key-legende_agir button[data-variant='pills']::before {content: ''; width: 12px; "
        "height: 12px; border-radius: 3px; margin-right: 6px; border: 1px solid rgba(128,128,128,0.45);}"
        ".st-key-legende_agir button[aria-pressed='false'] {opacity: 0.6;}"
        + "".join(f".st-key-legende_agir button[aria-pressed='true']:nth-of-type({n})::before "
                  f"{{background: {c};}}" for n, (_, c, _, _) in enumerate(GROUPES.values(), 1))
        + "</style>")
visibles = st.pills("Communes", list(GROUPES), selection_mode="multi", default=list(GROUPES),
                    format_func=lambda k: GROUPES[k][0], key="legende_agir",
                    label_visibility="collapsed",
                    help=" ".join(f"**{nom.split(' :')[0]}** : {aide}" for nom, _, _, aide in GROUPES.values()))
couleur = {}
for k in reversed(list(GROUPES)):  # « où l'on retourne » passe devant si une commune est dans deux groupes
    if k in visibles:
        couleur.update({i: GROUPES[k][1] for i in GROUPES[k][2]})


def info(i):
    if i in set(retournent):
        return f"{ha(t.retourne_recent[i])} retournés en culture, {r0}→{an}"
    if i in gain.index:
        return f"{ha(gain[i], signe=True)} de prairies sur d'anciennes cultures depuis {a0}"
    if i in set(gardent):
        return f"aucune prairie perdue depuis {a0}"
    return ""


g = communes_carte().copy()
g["couleur"] = [hex_rgb(couleur[i]) if i in couleur else hex_rgb(HORS, 200) for i in g.insee]
g["valeur"] = g.insee.map(info)
CLE = "carte_agir"
evt = zone_carte.pydeck_chart(deck([(g[["insee", "nom_officiel", "couleur", "valeur", "geometry"]], CLE)],
                                   g, "<b>{nom_officiel}</b><br/>{valeur}"),
                              on_select="rerun", selection_mode="single-object", width="stretch", key=CLE)
st.caption("Un clic sur une commune ouvre sa fiche.")
clic = selection_carte(evt, CLE, "insee")
if clic and clic != st.session_state.get(f"_clic_{CLE}"):  # un clic ne compte qu'une fois
    st.session_state[f"_clic_{CLE}"] = clic
    st.session_state["commune"] = clic
    st.switch_page("vues/commune.py")

lignes = [{"insee": i, "commune": t.nom_officiel[i], "departement": t.dep[i], "groupe": k,
           f"retourne_{r0}_{an}_ha": round(t.retourne_recent[i]), f"prairies_{an}_ha": round(t[f"pp_{an}"][i])}
          for k, (_, _, ids, _) in GROUPES.items() for i in ids]
st.download_button(f"Télécharger les listes ({nombre(len(lignes))} communes, CSV)",
                   pd.DataFrame(lignes).to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig"),
                   "prairimetre_ou_agir.csv", "text/csv", icon=":material/download:", key="dl_agir")
