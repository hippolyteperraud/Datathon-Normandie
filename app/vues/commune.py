"""Ma commune : ce qu'elle a perdu, comment, que faire et avec qui, la carte de ses prairies.
Les parcelles sont extraites à la demande par le moteur."""
import pandas as pd
import streamlit as st

from commun import (ACTIONS, FLUX_COULEURS, bornes, communes_moitie, contact_captage, deck,
                    exiger_sorties, ha, hex_rgb, legende, motif_manquant, nom_propre, nombre, pct,
                    table, variation)
from humain import terrains
from prairimetre.config import RECENT
from prairimetre.indicateurs import parcelles_commune

exiger_sorties()
a0, an, r0 = bornes(avec_recent=True)
t, k, cc = table("communes"), table("captages"), table("communes_captages")


@st.cache_data(show_spinner="Le moteur extrait les parcelles de la commune…")
def parcelles(insee, annee):
    """Parcelles de la commune ; l'année des résultats fait partie de la clé du cache, pour
    qu'un nouveau registre soit pris en compte sans redémarrer l'application."""
    disparues, nouvelles = parcelles_commune(insee)
    return disparues.to_crs(4326), nouvelles.to_crs(4326)


def libelle(i):
    """« Rouen (76000, 76100) » : le code postal, pas le code INSEE."""
    cp = t.loc[i, "codes_postaux"] if "codes_postaux" in t else None
    return f"{t.loc[i, 'nom_officiel']} ({cp if isinstance(cp, str) else 'code INSEE ' + i})"


options = t.sort_values("nom_officiel").index.tolist()
if st.session_state.get("commune") not in options:  # 1re visite : la commune qui retourne le plus
    st.session_state["commune"] = t.rang_hectares.idxmin()
insee = st.selectbox("Commune (nom ou code postal)", options, key="commune", format_func=libelle)
r = t.loc[insee]
pp0, ppn = r[f"pp_{a0}"], r[f"pp_{an}"]

st.title(r.nom_officiel)
st.caption(", ".join([r.epci_nom, f"département {r.dep}"]
                     + ([f"Parc naturel régional {r.pnr}"] if isinstance(r.pnr, str) else [])))

# --- Diagnostic ----------------------------------------------------------------------------------
motif = motif_manquant(r.statut)
if motif:
    st.info(f"Pas de diagnostic pour cette commune. {motif} Prairies déclarées : {ha(pp0)} en "
            f"{a0}, {ha(ppn)} en {an}.")
    st.stop()

sens = "perdu" if r.solde < 0 else "gagné"
cause = {
    "retournement": "surtout parce que des prairies ont été retournées en culture",
    "sortie de la déclaration": "surtout parce que des prairies ne sont plus déclarées à la PAC ; "
                                "l'herbe peut y être encore présente",
    "stable ou en gain": "ses prairies se maintiennent",
}[r.mecanisme]
def rang(n):
    return "1re" if n == 1 else f"{n}e"


rangs = []
if r.rang_hectares <= 100:
    rangs.append(f"{rang(int(r.rang_hectares))} pour les hectares retournés")
if pd.notna(r.rang_taux) and r.rang_taux <= 100:
    rangs.append(f"{rang(int(r.rang_taux))} pour la part de ses prairies retournée")
st.markdown(f"#### Depuis {a0}, {r.nom_officiel} a {sens} {ha(abs(r.solde))} de prairies "
            f"déclarées ({pct(r.solde_taux, 0, signe=True)}), {cause}."
            + (f" Sur {r0}–{an}, elle se classe {' et '.join(rangs)} parmi les communes "
               "normandes." if rangs else ""))
if abs(r.solde) >= 1:
    st.caption(f"{ha(abs(r.solde))}, c'est à peu près {terrains(abs(r.solde))}.")

c1, c2, c3 = st.columns(3)
c1.metric(f"Prairies déclarées en {an}", ha(ppn), f"{variation(ppn - pp0)} depuis {a0}",
          border=True)
c2.metric(f"Retournées en culture, {r0}–{an}", ha(r.retourne_recent),
          f"{pct(r.retournement_recent_taux_annuel, 1)} des prairies par an"
          if pd.notna(r.retournement_recent_taux_annuel) else f"moins de 20 ha de prairies en {r0}",
          delta_color="off", delta_arrow="off", border=True)
c3.metric("Prairies où une règle encadre le labour",
          pct(r.part_regle, 0) if pd.notna(r.part_regle) else f"aucune prairie en {an}",
          f"site protégé {pct(r.part_site, 0)}, inventaire {pct(r.part_inventaire, 0)}"
          if pd.notna(r.part_regle) else None,
          delta_color="off", delta_arrow="off", border=True,
          help="Règle : prairies sensibles (BCAE 9), zones humides et tourbières (BCAE 2), "
               "zones humides du programme nitrates. Sites protégés : Natura 2000, réserves, "
               "arrêtés de biotope, conservatoires. Inventaires (ZNIEFF, zones humides DREAL, "
               "zone N des PLU) : sans effet juridique sur le labour.")
st.caption(f"Depuis {a0}, {ha(r.devenues_culture)} ont été retournés en culture et "
           f"{ha(r.devenues_non_declare)} sont sortis de la déclaration PAC. Un retournement est "
           "certain (une culture est déclarée à la place) ; une sortie de la déclaration ne dit "
           "pas ce qu'est devenue la parcelle.")

# --- Que faire, avec qui ---------------------------------------------------------------------------
with st.container(border=True):
    st.markdown("**Que faire, avec qui**")
    # L'action découle du mécanisme dominant de ses pertes (calculé par le moteur) : les mêmes
    # noms que les moyens d'agir de la page Où agir et la vérification de la Carte des données
    action = next(a for a in ACTIONS.values() if a.get("mecanisme") == r.mecanisme)
    net_culture = r.devenues_culture - r.venues_culture
    net_sortie = r.devenues_non_declare - r.venues_non_declare
    if r.mecanisme == "retournement":
        pourquoi_ = (f"en solde depuis {a0} (retours déduits), la commune a perdu "
                     f"{ha(net_culture)} de prairies au profit des cultures, plus que par les "
                     f"sorties de la déclaration ({ha(max(net_sortie, 0))}) : la perte est "
                     "certaine.")
        if insee in communes_moitie(t):
            pourquoi_ += (f" Elle fait partie des {len(communes_moitie(t))} communes qui portent la "
                          f"moitié du retournement de {r0}–{an}.")
        if pd.notna(r.part_regle) and r.part_regle < 0.005:
            pourquoi_ += " Aucune de ses prairies n'est couverte par une règle qui encadre le labour."
        elif pd.notna(r.part_regle) and r.part_regle < 0.5:
            pourquoi_ += (f" Seulement {pct(r.part_regle, 0)} de ses prairies sont couvertes par "
                          "une règle qui encadre le labour.")
        quoi = ("avec la chambre d'agriculture : mesures agro-environnementales, paiements pour "
                "services environnementaux.")
    elif r.mecanisme == "sortie de la déclaration":
        pourquoi_ = (f"en solde depuis {a0} (retours déduits), {ha(net_sortie)} de prairies sont "
                     f"sorties de la déclaration, "
                     f"{'autant' if round(net_sortie) == round(net_culture) else 'plus'} que les "
                     f"{ha(max(net_culture, 0))} perdues au "
                     "profit des cultures : on ne sait pas si l'herbe est encore là.")
        quoi = "sur photo aérienne ou sur place, avant d'agir."
    else:
        voisines = t[(t.epci == r.epci) & (t.statut == "calculé") & (t.retourne_recent > 0)] \
            .sort_values("retourne_recent", ascending=False).nom_officiel.head(3)
        pourquoi_ = (f"la commune a {'gagné des' if r.solde > 0 else 'gardé ses'} prairies "
                     f"depuis {a0} ({ha(r.solde, signe=True)}).")
        quoi = (": faire témoigner ses éleveurs dans les communes voisines qui retournent"
                + (f", par exemple {', '.join(voisines)}." if len(voisines) else "."))
    st.markdown(f"**{action['titre']}** {quoi}  \nPourquoi : {pourquoi_}")
    lignes = [f"Intercommunalité : {r.epci_nom}."]
    if isinstance(r.pnr, str):
        lignes.append(f"Parc naturel régional {r.pnr} : animation et charte du parc.")
    aires = cc[(cc.insee == insee) & (cc.prairies_ha >= 10)] \
        .sort_values("prairies_ha", ascending=False).head(3)
    for aac, h in zip(aires.aac, aires.prairies_ha):
        if aac in k.index:
            lignes.append(f"{ha(h)} de prairies au-dessus du captage « {nom_propre(k.loc[aac, 'nom'])} »"
                          f" : contact {contact_captage(k.loc[aac])}.")
    if r.part_inventaire >= 0.2 and r.part_regle < 0.2:
        lignes.append(f"{pct(r.part_inventaire, 0)} des prairies sont dans un inventaire "
                      "(ZNIEFF, zone humide) : un argument pour l'animation et les MAEC, mais pas "
                      "une interdiction de labour.")
    st.markdown("\n".join(f"- {l}" for l in lignes))

# --- Carte des prairies ----------------------------------------------------------------------------
st.subheader("Carte des prairies")
VUES = {f"Les prairies de {a0}, aujourd'hui":
        f"Chaque prairie déclarée en {a0}, colorée selon ce qu'elle est devenue en {an}.",
        f"Les nouvelles prairies de {an}":
        f"Chaque prairie déclarée en {an} qui ne l'était pas en {a0}, colorée selon ce qu'elle "
        f"était avant."}
voir = st.toggle("Afficher les parcelles", value=True,
                 help="Parcelles du registre parcellaire graphique : donnée publique et anonyme "
                      "(aucun nom d'exploitant), publiée par l'IGN.")
if voir:
    vue = st.segmented_control("Afficher", list(VUES), default=list(VUES)[0],
                               label_visibility="collapsed") or list(VUES)[0]
    st.caption(VUES[vue])
    disparues, nouvelles = parcelles(insee, an)
    nouvelle = vue == list(VUES)[1]
    if nouvelle:
        noms = {"culture": "était une culture", "non déclaré": "n'était pas déclarée",
                "prairie temporaire": "était une prairie temporaire"}
    else:
        noms = {"culture": "retournée en culture", "non déclaré": "sortie de la déclaration",
                "prairie temporaire": "devenue prairie temporaire",
                "prairie permanente": "toujours en prairie"}
    autre = "autre (bois, lande…)"
    couleurs = {noms[c]: FLUX_COULEURS[c] for c in noms} | {autre: FLUX_COULEURS["autre"]}
    g, col = (nouvelles.copy(), "origine") if nouvelle else (disparues.copy(), "devenir")
    if g.empty:
        st.info("Aucune parcelle à afficher.")
    else:
        g["libelle"] = g[col].map(lambda x: noms.get(x, autre))
        g["couleur"] = [hex_rgb(couleurs[x]) for x in g.libelle]
        g["t_ha"] = g.ha.map(lambda x: ha(x) if x >= 1 else f"{x:.2f} ha".replace(".", ","))
        st.pydeck_chart(deck([(g[["libelle", "t_ha", "couleur", "geometry"]], "parcelles")], g,
                             "<b>{libelle}</b><br/>{t_ha}", hauteur=480), width="stretch")
        nombres = g.libelle.value_counts()
        legende([(couleurs[c], f"{c} ({nombre(n)} parcelle{'s' if n > 1 else ''})")
                 for c, n in nombres.items()])
        st.caption("La couleur d'une parcelle est celle de la plus grande part de sa surface. "
                   "Données publiques et anonymes (RPG, IGN) : aucun exploitant n'est désigné.")
