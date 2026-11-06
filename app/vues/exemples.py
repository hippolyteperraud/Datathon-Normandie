"""Prendre exemple : les communes qui déclarent plus de prairies permanentes, là où on peut assurer que
ce sont des prairies gagnées : une culture déclarée au début, une prairie permanente déclarée à la fin ;
et celles qui n'ont perdu aucune de leurs prairies. Tout est calculé à partir des sorties du moteur."""

import pandas as pd
import streamlit as st

from commun import (DEPARTEMENTS, FLUX_COULEURS, HORS, bornes, communes_carte, deck, exiger_sorties, ha,
                    hex_rgb, nombre, selection_carte, table)

GAIN_MINIMUM_HA = 5  # en dessous, le gain pèse moins qu'une parcelle : ce n'est pas un exemple

exiger_sorties()
a0, an = bornes()
t = table("communes")
calc = t[t.statut == "calculé"]
VERT = FLUX_COULEURS["prairie permanente"]

# Le gain qu'on peut assurer : pris sur des cultures, net de ce que la commune a retourné, et sans
# dépasser ce que la commune a réellement gagné. Il doit être la principale origine du gain : ni une
# prairie temporaire devenue permanente (l'herbe était déjà là), ni une nouvelle déclaration (peut-être
# aussi).
sur_cultures = calc.venues_culture - calc.devenues_culture
temporaires = (calc.venues_temporaire - calc.devenues_temporaire).clip(lower=0)
declarees = calc.venues_non_declare - calc.devenues_non_declare
assure = pd.concat([calc.solde, sur_cultures], axis=1).min(axis=1)
garde = (calc.solde > 0) & (sur_cultures >= declarees + temporaires) & (assure >= GAIN_MINIMUM_HA)
gain = assure[garde].sort_values(ascending=False)

# Les communes qui n'ont rien perdu : de leurs prairies de a0, moins d'un hectare n'est plus une
# prairie permanente en an (ni retourné, ni sorti de la déclaration, ni passé en prairie temporaire).
# Le seuil d'un hectare absorbe les petits écarts de contour d'une année à l'autre. Un solde nul ne
# suffit pas : la plupart des communes à solde nul ou positif perdent des prairies et en déclarent
# d'autres ailleurs.
PERTE_MAXIMUM_HA = 1
sans_perte = calc.index[calc.disparues < PERTE_MAXIMUM_HA]
gardees = [i for i in sans_perte if i not in set(gain.index)]  # celles qui gagnent restent vertes
VERT_CLAIR = "#8fc93a"

st.title("Prendre exemple")
st.subheader("Les communes qui gagnent des prairies, et celles qui n'en perdent pas")
st.markdown(f"**{nombre(len(gain))} communes** ont gagné **{ha(gain.sum())}** de prairies sur "
            f"d'anciennes cultures depuis {a0}. **{nombre(len(sans_perte))} communes** n'ont perdu "
            f"aucune de leurs prairies de {a0} ({ha(calc[f'pp_{an}'][sans_perte].sum())} en {an})"
            + (f", dont {nombre(len(sans_perte) - len(gardees))} parmi celles qui gagnent."
               if len(gardees) < len(sans_perte) else "."))

# Le compte suit ce que la carte montre : « gagnent » éteint, les communes qui gagnent sans rien
# perdre passent en vert clair (valeur de la légende au rechargement qui suit le clic)
gagnent_allume = "gagnent" in st.session_state.get("legende_exemples", ["gagnent"])
GROUPES = {
    "gagnent": ("Gagnent des prairies sur d'anciennes cultures", VERT, len(gain),
                f"Une culture déclarée en {a0}, une prairie permanente déclarée en {an} : au moins "
                f"{GAIN_MINIMUM_HA} ha de gain, net de ce que la commune a retourné."),
    "gardent": ("Ne perdent pas de prairies", VERT_CLAIR,
                len(gardees) if gagnent_allume else len(sans_perte),
                f"Moins de {PERTE_MAXIMUM_HA} ha de leurs prairies de {a0} ne sont plus des prairies "
                f"permanentes en {an} : ni retournées, ni sorties de la déclaration, ni passées en "
                "prairie temporaire. Celles qui gagnent aussi restent en vert foncé tant que "
                "« Gagnent » est allumé."),
}

zone_carte = st.container()  # la carte au-dessus de sa légende, qui décide de ce qu'elle montre
# La légende se clique : chaque bouton garde son carré de couleur, vide quand il est éteint
st.html("<style>"
        ".st-key-legende_exemples button[data-variant='pills'] {display: inline-flex; "
        "align-items: center;}"
        ".st-key-legende_exemples button[data-variant='pills']::before {content: ''; width: 12px; "
        "height: 12px; border-radius: 3px; margin-right: 6px; "
        "border: 1px solid rgba(128,128,128,0.45);}"
        ".st-key-legende_exemples button[aria-pressed='false'] {opacity: 0.6;}"
        + "".join(f".st-key-legende_exemples button[aria-pressed='true']"
                  f":nth-of-type({n})::before {{background: {c};}}"
                  for n, (_, c, _, _) in enumerate(GROUPES.values(), 1))
        + "</style>")
visibles = st.pills(
    "Communes", list(GROUPES), selection_mode="multi", default=list(GROUPES),
    format_func=lambda k: f"{GROUPES[k][0]} : {nombre(GROUPES[k][2])} communes",
    key="legende_exemples", label_visibility="collapsed",
    help=" ".join(f"**{nom}** : {aide}" for nom, _, _, aide in GROUPES.values()))
vertes = set(gain.index) if "gagnent" in visibles else set()
# Éteindre « gagnent » laisse voir en vert clair celles qui gagnent sans rien perdre
claires = set(sans_perte) - vertes if "gardent" in visibles else set()

g = communes_carte().copy()
g["couleur"] = [hex_rgb(VERT) if i in vertes else hex_rgb(VERT_CLAIR) if i in claires
                else hex_rgb(HORS, 200) for i in g.insee]
g["valeur"] = [f"{ha(gain[i], signe=True)} sur d'anciennes cultures" if i in vertes else
               f"aucune prairie perdue depuis {a0} ({ha(t[f'pp_{an}'][i])} en {an})"
               if i in claires else "" for i in g.insee]
CLE = "carte_exemples"
evt = zone_carte.pydeck_chart(deck([(g[["insee", "nom_officiel", "couleur", "valeur", "geometry"]], CLE)],
                                   g, "<b>{nom_officiel}</b><br/>{valeur}", hauteur=560),
                              on_select="rerun", selection_mode="single-object", width="stretch",
                              key=CLE)

# Un clic ne compte qu'une fois (la sélection de la carte persiste d'un rechargement à l'autre)
clic = selection_carte(evt, CLE, "insee")
if clic and clic != st.session_state.get(f"_clic_{CLE}"):
    st.session_state[f"_clic_{CLE}"] = clic
    st.session_state["commune"] = clic
    st.switch_page("vues/commune.py")


# --- La liste des communes qui gagnent, en détail, sur demande ------------------------------------
def basculer_liste():
    st.session_state["liste_exemples"] = not st.session_state.get("liste_exemples", False)


ouverte = st.session_state.get("liste_exemples", False)
st.button(f"{'Masquer' if ouverte else 'Voir'} la liste des {nombre(len(gain))} communes qui "
          "gagnent des prairies", on_click=basculer_liste, type="primary", width="stretch",
          icon=":material/expand_less:" if ouverte else ":material/list:", key="btn_liste_exemples")
if ouverte:
    # Valeurs écrites en Python : le tableau garde le format français (espaces, virgules)
    st.dataframe(pd.DataFrame({
        "Commune": t.nom_officiel[gain.index].values,
        "Département": t.dep[gain.index].map(DEPARTEMENTS).values,
        f"Gagné sur d'anciennes cultures depuis {a0}": [ha(v, signe=True) for v in gain.values],
        f"Prairies en {a0}": [ha(v) for v in t[f"pp_{a0}"][gain.index]],
        f"Prairies en {an}": [ha(v) for v in t[f"pp_{an}"][gain.index]]}),
        hide_index=True, width="stretch")

    liste = list(gain.index) + gardees
    export = pd.DataFrame({
        "insee": liste, "commune": t.nom_officiel[liste].values,
        "departement": t.dep[liste].values,
        "groupe": ["gagne sur d'anciennes cultures"] * len(gain) + ["ne perd pas"] * len(gardees),
        f"prairies_{a0}_ha": t[f"pp_{a0}"][liste].round(0).values,
        f"prairies_{an}_ha": t[f"pp_{an}"][liste].round(0).values,
        "gain_sur_cultures_ha": list(gain.round(0).values) + [None] * len(gardees),
        "prairies_perdues_ha": t.disparues[liste].round(1).values})
    st.download_button(f"Télécharger les deux groupes ({nombre(len(export))} communes, CSV)",
                       export.to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig"),
                       "prairimetre_communes_exemples.csv", "text/csv",
                       icon=":material/download:", key="dl_communes_exemples")
