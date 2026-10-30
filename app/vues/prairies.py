"""Où agir : quelles communes, intercommunalités ou aires de captage d'eau potable cibler.
Les aires de captage sont une échelle comme une autre : des territoires où une prairie retournée
pèse plus lourd, parce qu'elle protégeait l'eau potable."""
import pandas as pd
import streamlit as st

from commun import (CAT, DEPARTEMENTS, FOND, bornes, captages_carte, classement, communes_carte,
                    contact_captage, deck, epci_carte, exiger_sorties, ha, hex_rgb, legende,
                    nom_propre, nombre, pct, selection_carte, table)
from prairimetre.config import RECENT

exiger_sorties()
a0, an = bornes()
r0 = an - RECENT
t = table("communes")
t = t.assign(sortie_nette=t.devenues_non_declare - t.venues_non_declare)
k, cc = table("captages"), table("communes_captages")

OBJECTIFS = {
    "Où financer le maintien": {
        "couleur": CAT[0],
        "decision": "Ce sont les territoires où l'animation agricole, les mesures "
                    "agro-environnementales (MAEC) et les paiements pour services environnementaux "
                    "auront le plus d'effet."},
    "Où vérifier d'abord": {
        "col": "sortie_nette", "couleur": CAT[1],
        "mesure": f"hectares sortis de la déclaration PAC, nets des retours ({a0}–{an})",
        "decision": "Ces prairies ne sont plus déclarées, mais l'herbe est souvent encore là : "
                    "une vérification sur photo aérienne ou sur place s'impose avant d'agir."},
    "Où trouver des exemples": {
        "col": f"pp_{a0}", "couleur": CAT[2],
        "mesure": f"hectares de prairies en {a0}, dans les communes sans perte nette",
        "decision": "Ces communes gardent leurs prairies : leurs éleveurs et leurs pratiques "
                    "peuvent servir d'exemple aux territoires voisins."},
}
CRITERES = {
    "hectares": ("retourne_recent", f"hectares retournés en culture ({r0}–{an})", False),
    "taux": ("retournement_recent_taux_annuel",
             f"part des prairies retournée chaque année ({r0}–{an})", True),
    "zonages d'enjeux": ("retourne_recent_enjeux",
                         f"hectares retournés dans un zonage d'enjeux ou une aire de captage "
                         f"({r0}–{an})", False),
}
AIRES = "aires de captage"

st.title("Où agir")
objectif = st.segmented_control("Ce que vous cherchez", list(OBJECTIFS),
                                default=list(OBJECTIFS)[0], key="objectif") \
    or list(OBJECTIFS)[0]
financer = objectif == "Où financer le maintien"
echelles = ["communes", "intercommunalités"] + ([AIRES] if financer else [])
f2, f3, f4 = st.columns([3, 2, 2])
echelle = f2.segmented_control("Échelle", echelles, default="communes",
                               key=f"echelle_{objectif}") or "communes"
dep = f3.selectbox("Territoire", ["Normandie"] + list(DEPARTEMENTS),
                   format_func=lambda d: DEPARTEMENTS.get(d, d))
tailles = [20, 50, 100] if echelle == "communes" else [5, 10, 20]
n = f4.segmented_control("Combien", tailles, default=tailles[1], key=f"combien_{echelle}") \
    or tailles[1]
O = dict(OBJECTIFS[objectif])
en_pct = False
if financer:
    criteres = [c for c in CRITERES if echelle != AIRES or c != "zonages d'enjeux"]
    critere = st.segmented_control(
        "Classer par", criteres, default="hectares", key=f"critere_{echelle}",
        help="Les hectares font ressortir les grands territoires ; le taux, ceux qui perdent une "
             f"grande part de leurs prairies (au moins 100 ha en {r0}) ; les zonages d'enjeux, "
             "les retournements là où l'eau ou la nature sont en jeu.") or "hectares"
    O["col"], O["mesure"], en_pct = CRITERES[critere]
territoire = "la Normandie" if dep == "Normandie" else DEPARTEMENTS[dep]

# --- Tableau à l'échelle choisie ------------------------------------------------------------------
perimetre = t if dep == "Normandie" else t[t.dep == dep]
perimetre = perimetre[perimetre.statut == "calculé"]
if objectif == "Où trouver des exemples":
    perimetre = perimetre[perimetre.solde >= 0]
if echelle == AIRES:
    u = k.rename(columns={"retourne_recent_ha": "retourne_recent"}).copy()
    u["nom"] = u.nom.map(nom_propre)
    if dep != "Normandie":  # aires qui ont des prairies dans le département
        u = u[u.index.isin(cc[cc.insee.str[:2] == dep].aac)]
    if en_pct:
        u = u[u[f"pp_{r0}"] >= 100]
elif echelle == "intercommunalités":
    somme = ["retourne_recent", "retourne_recent_enjeux", "sortie_nette", f"pp_{a0}", f"pp_{r0}"]
    u = perimetre.groupby("epci").agg({**{c: "sum" for c in somme}, "epci_nom": "first"})
    u = u.rename(columns={"epci_nom": "nom"})
    u["retournement_recent_taux_annuel"] = u.retourne_recent / u[f"pp_{r0}"] / RECENT
    if en_pct:
        u = u[u[f"pp_{r0}"] >= 100]
else:
    u = perimetre.rename(columns={"nom_officiel": "nom"})
    if en_pct:
        u = u[u[f"pp_{r0}"] >= 100]
liste = u[u[O["col"]] > 0].sort_values(O["col"], ascending=False).head(n)
total = u[O["col"]].clip(lower=0).sum()

if objectif == "Où trouver des exemples":
    st.markdown(f"#### {len(u)} {echelle} de {territoire} n'ont pas perdu de prairies depuis {a0}. "
                f"Les {len(liste)} qui en ont le plus en totalisent {ha(liste[O['col']].sum())}.")
elif en_pct:
    st.markdown(f"#### Les {len(liste)} {echelle} de {territoire} qui perdent la plus grande part "
                f"de leurs prairies : de {pct(liste[O['col']].min(), 1)} à "
                f"{pct(liste[O['col']].max(), 1)} par an ({r0}–{an}).")
else:
    cadre = " dans les aires de captage" if echelle == AIRES else ""
    st.markdown(f"#### Ces {len(liste)} {echelle} portent {pct(liste[O['col']].sum() / total, 0)} "
                f"des {O['mesure']}{cadre} de {territoire}.")
st.markdown(O["decision"]
            + (" Au-dessus d'un captage, une prairie retournée laisse passer davantage de nitrates "
               "et de pesticides vers l'eau potable." if echelle == AIRES else ""))

# --- Carte et liste ----------------------------------------------------------------------------------
gauche, droite = st.columns([3, 2], gap="large")
rangs = {i: r + 1 for r, i in enumerate(liste.index)}
with gauche:
    if echelle == AIRES:
        g = captages_carte()
        g = g[g.aac.isin(u.index)].copy()
        cle, couche = "aac", "captages"
    elif echelle == "intercommunalités":
        g = epci_carte()
        g = g[g.epci.isin(u.index)].copy()
        cle, couche = "epci", "epci"
    else:
        g = communes_carte()
        g = (g if dep == "Normandie" else g[g.dep == dep]).copy()
        cle, couche = "insee", "communes"
    g["nom"] = g[cle].map(u.nom)
    g["couleur"] = [hex_rgb(O["couleur"]) if i in rangs
                    else hex_rgb(FOND, 160) if i in u.index else [0, 0, 0, 0] for i in g[cle]]
    g["valeur"] = g[cle].map(u[O["col"]]).map(lambda v: pct(v, 1) if en_pct else ha(v))
    g["rang"] = g[cle].map(lambda i: f"n° {rangs[i]} de la liste" if i in rangs else "hors liste")
    g["nom"] = g.nom.fillna(g[cle])
    evt = st.pydeck_chart(
        deck([(g[[cle, "nom", "couleur", "valeur", "rang", "geometry"]], couche)], g,
             "<b>{nom}</b><br/>{valeur}<br/>{rang}"),
        on_select="rerun", selection_mode="single-object", width="stretch",
        key=f"carte_{echelle}")
    seuil = 100 if en_pct else 20
    legende([(O["couleur"], "dans la liste"), (FOND, "hors liste")]
            + ([("#ffffff", f"non classée (moins de {seuil} ha de prairies)")]
               if echelle != AIRES else []))
    clic = selection_carte(evt, couche, cle)
    if clic and echelle == "communes":
        st.session_state["commune"] = clic
        st.switch_page("vues/commune.py")
    if clic and echelle == AIRES:
        st.session_state["aac"] = clic

with droite:
    tete = liste.head(15)
    st.markdown(f"Les {len(tete)} premières")
    st.altair_chart(classement(tete.nom, tete[O["col"]], O["couleur"],
                               "part par an" if en_pct else "hectares", en_pct=en_pct),
                    width="stretch")
    if echelle == "communes":
        st.caption("Un clic sur une commune de la carte ouvre sa fiche.")
    elif echelle == AIRES:
        st.caption("Un clic sur une aire de la carte affiche ses interlocuteurs ci-dessous.")
    export = pd.DataFrame({"rang": range(1, len(liste) + 1), "nom": liste.nom.values,
                           O["col"]: liste[O["col"]].round(4 if en_pct else 0).values})
    if echelle == "communes":
        export.insert(2, "intercommunalite", liste.epci_nom.values)
    if echelle == AIRES:
        export.insert(2, "premier_contact", [contact_captage(k.loc[a]) for a in liste.index])
    st.download_button(f"Télécharger la liste ({len(liste)} {echelle}, CSV)",
                       export.to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig"),
                       f"prairimetre_{O['col']}_{echelle.replace(' ', '_')}.csv", "text/csv",
                       icon=":material/download:")

# --- Fiche de l'aire de captage choisie ----------------------------------------------------------------
if echelle == AIRES and len(liste):
    st.divider()
    options = list(liste.index) + [a for a in u.index if a not in rangs]
    choix = st.session_state.get("aac", options[0])
    choix = st.selectbox("Aire de captage", options,
                         index=options.index(choix) if choix in options else 0,
                         format_func=lambda a: nom_propre(k.loc[a, "nom"]))
    st.session_state["aac"] = choix
    r = k.loc[choix]
    c1, c2, c3 = st.columns(3)
    c1.metric(f"Prairies dans l'aire en {an}", ha(r[f"pp_{an}"]),
              f"{pct(r.part_en_prairie, 0)} de sa surface en Normandie",
              delta_color="off", delta_arrow="off", border=True)
    c2.metric(f"Retournées en culture, {r0}–{an}", ha(r.retourne_recent_ha),
              f"{pct(r.retournement_recent_taux_annuel, 1)} des prairies par an"
              if pd.notna(r.retournement_recent_taux_annuel)
              else f"moins de 100 ha de prairies en {r0}",
              delta_color="off", delta_arrow="off", border=True)
    principales = r.communes_principales if isinstance(r.communes_principales, str) else ""
    c3.metric("Communes dont les prairies sont dans l'aire",
              nombre(r.communes) if pd.notna(r.communes) else "aucune en Normandie",
              principales[:60] or None, delta_color="off", delta_arrow="off", border=True)
    roles = {"maitre_ouvrage": "maître d'ouvrage du captage", "service_etat": "service de l'État"}
    contacts = [f"{nom_propre(r[c])} ({role})" for c, role in roles.items() if isinstance(r[c], str)]
    contacts.append(f"{r.agence_eau}, qui finance les paiements pour services environnementaux")
    st.markdown("Interlocuteurs : " + " ; ".join(contacts) + ".")
    absents = [role for c, role in roles.items() if not isinstance(r[c], str)]
    if absents:
        texte = " et ".join(absents)
        st.caption(f"{texte[0].upper()}{texte[1:]} : non renseigné par le Sandre.")

st.caption(f"Comparaison des prairies déclarées de {r0} et de {an} (de {a0} et de {an} pour les "
           f"sorties de la déclaration et les exemples), parcelle par parcelle. "
           f"{nombre((t.statut != 'calculé').sum())} communes ont trop peu de prairies pour être "
           f"classées (moins de 20 ha en {a0}). Pour les aires de captage, seule la partie "
           "normande est comptée.")
