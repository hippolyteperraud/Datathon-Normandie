"""Où aller voir : une seule carte, où aller voir les prairies sorties de la déclaration, pour savoir
si l'herbe est encore là. Visées : les communes qui portent la moitié des sorties ; prioritaires
celles où la réponse peut changer la liste où payer le maintien."""
import pandas as pd
import streamlit as st

from commun import (ACTIONS, HORS, bornes, communes_carte, communes_moitie, deck, exiger_sorties, ha,
                    hex_rgb, nombre, pct, selection_carte, table)

exiger_sorties()
a0, an = bornes()
t = table("communes")

sorties = t.devenues_non_declare
part_sortie = sorties / t[f"pp_{a0}"]
# Les communes, de la plus touchée à la moins touchée, qui portent ensemble la moitié des sorties
rang = sorties[t.statut == "calculé"].sort_values(ascending=False)
moitie = rang.index[:int((rang.cumsum() / rang.sum() < 0.5).sum() + 1)]
liste_payer = set(communes_moitie(t))
# Hors de la liste, la réponse décide si la commune y entre ; dans la liste, elle n'y change rien
prioritaires = [i for i in moitie if i not in liste_payer]
secondaires = [i for i in moitie if i in liste_payer]
payer = ACTIONS["payer"]["titre"]

st.title("Où aller voir nos prairies")
st.subheader("Celles sorties de la déclaration : l'herbe est-elle encore là ?")


def chiffre(colonne, titre, valeur, note):
    colonne.metric(titre, valeur, note, delta_color="off", delta_arrow="off", border=True,
                   height="stretch")


c1, c2 = st.columns(2)
chiffre(c1, f"Sorties de la déclaration depuis {a0}", ha(sorties.sum()),
        "encore en herbe : ne sait pas")
chiffre(c2, "Communes à aller voir", nombre(len(moitie)),
        f"{ha(sorties[moitie].sum())}, la moitié des sorties")

FORT, CLAIR = ACTIONS["verifier"]["couleur"], "#f6b89c"
fort, clair = set(prioritaires), set(secondaires)
PRIORITES = {"prioritaire": ("Prioritaire", FORT, sorties[prioritaires].sum(), len(prioritaires)),
             "secondaire": ("Secondaire", CLAIR, sorties[secondaires].sum(), len(secondaires))}

zone_carte = st.container()  # la carte au-dessus de sa légende, qui décide de ce qu'elle montre
# La légende se clique : chaque bouton garde son carré de couleur, vide quand il est éteint
st.html("<style>"
        ".st-key-legende_priorite button[data-variant='pills'] {display: inline-flex; "
        "align-items: center;}"
        ".st-key-legende_priorite button[data-variant='pills']::before {content: ''; width: 12px; "
        "height: 12px; border-radius: 3px; margin-right: 6px; "
        "border: 1px solid rgba(128,128,128,0.45);}"
        ".st-key-legende_priorite button[aria-pressed='false'] {opacity: 0.6;}"
        + "".join(f".st-key-legende_priorite button[aria-pressed='true']"
                  f":nth-of-type({n})::before {{background: {c};}}"
                  for n, (_, c, _, _) in enumerate(PRIORITES.values(), 1))
        + "</style>")
visibles = st.pills(
    "Priorité", list(PRIORITES), selection_mode="multi", default=list(PRIORITES),
    format_func=lambda p: f"{PRIORITES[p][0]} : {ha(PRIORITES[p][2])}, "
                          f"{nombre(PRIORITES[p][3])} communes",
    key="legende_priorite",
    help=f"Ces communes portent la moitié des sorties. **Prioritaire** : la commune n'est pas "
         f"dans « {payer} » ; si ces prairies sont perdues, elle peut y entrer : aller voir "
         f"peut changer la décision. **Secondaire** : la commune est déjà dans « {payer} » : "
         "aller voir ne change pas la décision.")
fort_vu = fort if "prioritaire" in visibles else set()
clair_vu = clair if "secondaire" in visibles else set()

g = communes_carte().copy()
g["couleur"] = [hex_rgb(FORT) if i in fort_vu else hex_rgb(CLAIR) if i in clair_vu
                else hex_rgb(HORS, 200) for i in g.insee]
g["valeur"] = g.insee.map(lambda i: f"{ha(sorties[i])} sortis, {pct(part_sortie[i], 0)} de ses prairies")
CLE = "carte_sorties"
evt = zone_carte.pydeck_chart(deck([(g[["insee", "nom_officiel", "couleur", "valeur", "geometry"]], CLE)],
                                   g, "<b>{nom_officiel}</b><br/>{valeur}"),
                              on_select="rerun", selection_mode="single-object", width="stretch",
                              key=CLE)
# Un clic ne compte qu'une fois (la sélection de la carte persiste d'un rechargement à l'autre)
clic = selection_carte(evt, CLE, "insee")
if clic and clic != st.session_state.get(f"_clic_{CLE}"):
    st.session_state[f"_clic_{CLE}"] = clic
    st.session_state["commune"] = clic
    st.switch_page("vues/commune.py")

# La liste des communes à aller voir, téléchargeable
export = pd.DataFrame({
    "insee": moitie, "commune": t.nom_officiel[moitie].values, "departement": t.dep[moitie].values,
    "sorties_declaration_ha": sorties[moitie].round(0).values,
    f"part_des_prairies_{a0}_pct": (100 * part_sortie[moitie]).round(0).values,
    "priorite": ["prioritaire" if i in fort else "secondaire" for i in moitie]})
st.download_button(f"Télécharger la liste ({nombre(len(export))} communes, CSV)",
                   export.to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig"),
                   "prairimetre_communes_a_aller_voir.csv", "text/csv", icon=":material/download:",
                   key="dl_communes_a_aller_voir")
