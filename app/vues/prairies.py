"""Où agir : les trois moyens d'agir pour les prairies permanentes. Pour chacun : le conseil, ce
qui le fonde, pour qui, où, et l'indicateur qui en suivra l'effet.

Aucun conseil n'est écrit à la main : chaque phrase est tirée des sorties du moteur (sorties/),
et change d'elle-même avec chaque nouveau registre parcellaire. Les comparaisons (« moins »,
« autant », « plus » qu'ailleurs) sont tranchées par les tests de robustesse du moteur."""
import altair as alt
import pandas as pd
import streamlit as st

from commun import (ACTIONS, DE_TERRITOIRE, DEPARTEMENTS, HORS, NOIR, OFFICIEL, SEUIL_RATIO_PCT,
                    arrondi_ha, bornes, captages_carte, classement, communes_carte, communes_moitie,
                    comparaison,
                    contact_captage, couleurs_liste, deck, epci_carte, evaluation, exiger_sorties,
                    ha, legende, nom_propre, nombre, pct, selection_carte, table)
from humain import bandeau, fois_caen, pourquoi
from prairimetre.config import MIN_HA, RECENT

exiger_sorties()
a0, an, r0 = bornes(avec_recent=True)
t, k, cc = table("communes"), table("captages"), table("communes_captages")
bilan, obj = table("bilan_direct"), table("objectif")
cl, certitude = evaluation("classes", index_col=0), evaluation("certitude")
calc = t[t.statut == "calculé"]

# --- Les chiffres qui fondent les conseils ---------------------------------------------------------
region = bilan.loc["région"]
pp0, ppn = region[("disparues_devenues", "depart")], region[("nouvelles_venant_de", "arrivee")]
solde = ppn - pp0
retournees = region[("disparues_devenues", "culture")]
sorties = region[("disparues_devenues", "non déclaré")]
ref = obj.iloc[0]
a_ref, a_obj = int(ref.annee_reference), int(ref.annee_objectif)
niveau = obj.set_index("annee").prairies_ha
ref_ha = ref.reference_ha if pd.notna(ref.reference_ha) else (niveau.loc[a_ref] if a_ref in niveau.index else niveau.iloc[0])
manque = ref_ha - (niveau.loc[an] if an in niveau.index else niveau.iloc[-1])
effort = manque / max(a_obj - an, 1)                # à regagner chaque année d'ici a_obj
n_moitie = len(communes_moitie(t))
exemples = calc[calc.mecanisme == ACTIONS["exemple"]["mecanisme"]]


def part_herbe():
    """Part des prairies sorties de la déclaration encore en herbe (OCS GE), si évaluée."""
    if certitude is None:
        return None
    o = certitude[certitude.source.str.startswith("OCS")
                  & (certitude.groupe == "sorties de la déclaration")]
    return (o["herbe, usage agricole"] * o.ha).sum() / o.ha.sum() if len(o) else None


# --- En-tête ----------------------------------------------------------------------------------------
bandeau("Prairimètre", "Le suivi des prairies permanentes de Normandie")
st.markdown(
    f"#### Depuis {a0}, la Normandie a {'perdu' if solde < 0 else 'gagné'} "
    f"{arrondi_ha(abs(solde))} ha de prairies déclarées ({pct(solde / pp0, 0, signe=True)}, "
    f"{fois_caen(abs(solde))}). "
    + (f"Il en manque {arrondi_ha(manque)} ha pour retrouver le niveau de {a_ref}, objectif de "
       f"{a_obj}." if manque > 0 else
       f"Le niveau de {a_ref}, objectif de {a_obj}, est tenu ({ha(-manque, signe=True)}).")
    + " Trois moyens d'agir :")

# --- Les trois moyens : un conseil court chacun, un clic pour le détail ------------------------------
COURTS = {
    "suivre": (f"Regagner {arrondi_ha(effort)} ha par an d'ici {a_obj}, compté en hectares à "
               "chaque registre." if manque > 0 else
               f"Garder le niveau de {a_ref}, mesuré en hectares à chaque registre."),
    "payer": (f"Financer le maintien de l'herbe là où l'on retourne : la moitié du retournement "
              f"récent se fait dans {n_moitie} communes."),
    "exemple": (f"{nombre(len(exemples))} communes gardent leurs prairies depuis {a0} : faire "
                "connaître leurs éleveurs là où l'on retourne."),
}
MOYENS = list(COURTS)
if st.session_state.get("moyen") not in MOYENS:
    st.session_state["moyen"] = MOYENS[0]


def choisir(m):
    st.session_state["moyen"] = m


for i, (col, m) in enumerate(zip(st.columns(3), MOYENS), start=1):
    with col.container(border=True, height="stretch"):
        st.markdown(f"**{i}. {ACTIONS[m]['titre']}**")
        st.markdown(COURTS[m])
        st.caption(f"Pour : {ACTIONS[m]['pour']}")
        st.button("Voir le détail" if st.session_state["moyen"] != m else "Affiché ci-dessous",
                  key=f"btn_{m}", on_click=choisir, args=(m,), width="stretch",
                  type="primary" if st.session_state["moyen"] == m else "secondary")

moyen = st.session_state["moyen"]
numero = MOYENS.index(moyen) + 1
st.divider()
st.markdown(f"### {numero}. {ACTIONS[moyen]['titre']}")


def rubrique(titre, texte):
    st.markdown(f"**{titre}.** {texte}")


# --- 1. Suivre l'objectif en hectares ------------------------------------------------------------------
def suivre():
    herbe = part_herbe()
    ratio = -OFFICIEL["ratio_evol_pct"]
    conseil = (f"Mesurer l'objectif {a_obj} avec ce compteur en hectares, recalculé à chaque "
               "registre parcellaire, " + (f"et viser un gain de {arrondi_ha(effort)} ha par an "
                                           f"pour retrouver le niveau de {a_ref}."
                                           if manque > 0 else "pour garder le niveau atteint."))
    if 0 <= ratio < SEUIL_RATIO_PCT:
        conseil += (f" Ne pas s'en remettre au ratio de la PAC : il ne recule que de "
                    f"{nombre(ratio, 2)} % (chiffre officiel de {OFFICIEL['date']}), sous son "
                    f"seuil d'alerte de {SEUIL_RATIO_PCT} %, alors que les hectares baissent de "
                    f"{pct(-solde / pp0, 1)}.")
    conseil += (f" Compter les {arrondi_ha(retournees)} ha retournés en culture comme des pertes "
                f"certaines ; vérifier les {arrondi_ha(sorties)} ha sortis de la déclaration avant "
                "de les compter (page Carte des données).")
    rubrique("Le conseil", conseil)
    chute = niveau.diff().dropna()
    pire = int(chute.idxmin()) if len(chute) else an
    pire_chute = chute.min() if len(chute) else 0
    rubrique("Pourquoi", f"Les pertes se partagent entre {arrondi_ha(retournees)} ha retournés en "
             f"culture, une perte certaine, et {arrondi_ha(sorties)} ha sortis de la déclaration"
             + (f", dont {pct(herbe, 0)} encore en herbe selon la carte d'occupation du sol de "
                "l'IGN" if herbe is not None else "")
             + f". La plus forte baisse annuelle date de {pire} ({ha(pire_chute, signe=True)}).")
    st.caption(f"Pour : {ACTIONS['suivre']['pour']}")

    gauche, droite = st.columns([3, 2], gap="large")
    with gauche:
        d = obj.rename(columns={"annee": "année", "prairies_ha": "ha"})
        ligne = alt.Chart(d).mark_line(strokeWidth=2, color=ACTIONS["suivre"]["couleur"],
                                       point=alt.OverlayMarkDef(size=60)).encode(
            x=alt.X("année:O", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("ha:Q", title="hectares de prairies déclarées", scale=alt.Scale(zero=False),
                    axis=alt.Axis(format="~s")),
            tooltip=[alt.Tooltip("année:O"), alt.Tooltip("ha:Q", format=",.0f")])
        cible = alt.Chart(pd.DataFrame({"y": [ref_ha]})).mark_rule(
            color="#52514e", strokeDash=[4, 3]).encode(y="y:Q")
        texte = alt.Chart(pd.DataFrame({"y": [ref_ha], "x": [str(a0)]})).mark_text(
            align="left", dy=-7, fontSize=11, color="#52514e").encode(
            y="y:Q", x="x:O", text=alt.value(f"niveau de {a_ref}, à retrouver en {a_obj}"))
        st.altair_chart((ligne + cible + texte).properties(height=260), width="stretch")
    with droite:
        deps = bilan.drop(index="région")
        dep_solde = (deps[("nouvelles_venant_de", "arrivee")]
                     - deps[("disparues_devenues", "depart")]).sort_values()
        dep_taux = dep_solde / deps[("disparues_devenues", "depart")]
        pertes = dep_solde.clip(upper=0)
        tete = pertes[pertes < 0].index[:2]
        st.markdown(f"**Où.** Par département, de {a0} à {an}"
                    + (f" : {' et '.join(DEPARTEMENTS.get(d, d) for d in tete)} portent "
                       f"{pct(pertes[tete].sum() / pertes.sum(), 0)} de la perte."
                       if len(tete) and pertes.sum() < 0 else "."))
        st.altair_chart(classement([f"{DEPARTEMENTS.get(d, d)} ({pct(dep_taux[d], 0, signe=True)})"
                                    for d in dep_solde.index], -dep_solde.values,
                                   ACTIONS["suivre"]["couleur"], "hectares perdus"),
                        width="stretch")
    an_prec = int(niveau.index[niveau.index < an].max()) if (niveau.index < an).any() else a0
    rubrique("Indicateur de suivi",
             f"Le solde annuel des prairies déclarées, en hectares : "
             f"{ha(niveau.loc[an] - niveau.loc[an_prec], signe=True)} entre {an_prec} et {an}.")
    st.caption(f"Ratio officiel : {OFFICIEL['source']}. Année de référence de l'objectif : {a_ref} "
               "(réglage du moteur, prairimetre/config.py).")


# --- 2. Payer le maintien --------------------------------------------------------------------------
CRITERES = {
    "hectares": ("retourne_recent", f"hectares retournés en culture ({r0}–{an})", False),
    "taux": ("retournement_recent_taux_annuel",
             f"part des prairies retournée chaque année ({r0}–{an})", True),
    "zonages d'enjeux": ("retourne_recent_enjeux",
                         f"hectares retournés dans un zonage d'enjeux ou une aire de captage "
                         f"({r0}–{an})", False),
}
AIRES = "aires de captage"


def payer():
    sens_regle, v_regle = comparaison("regle")
    sens_aac, v_aac = comparaison("aires_alimentation_captages")
    conseil = ("Payer le maintien de l'herbe (mesures agro-environnementales, paiements pour "
               "services environnementaux) dans les territoires de la liste ci-dessous, qui "
               f"portent l'essentiel du retournement : la moitié se fait dans {n_moitie} communes "
               f"sur {nombre(len(calc))}.")
    if sens_aac in ("autant", "plus"):
        conseil += (f" Au-dessus des captages d'eau potable, on retourne {sens_aac} qu'ailleurs : "
                    "les Agences de l'eau ont intérêt à y financer ce maintien (échelle « aires "
                    "de captage »).")
    rubrique("Le conseil", conseil)
    if cl is not None:
        hors, regle = cl.loc["aucun zonage"], cl.loc["règle"]
        pourquoi_ = (f"{pct(hors.part_du_retournement, 0)} des retournements ont lieu hors de "
                     "tout zonage, là où rien n'encadre le labour.")
        if sens_regle == "moins":
            pourquoi_ += (f" Là où une règle l'encadre, on retourne environ "
                          f"{nombre(1 / v_regle.mean(), 0)} fois moins qu'à côté, dans la même "
                          f"commune ; mais ces règles ne couvrent que "
                          f"{pct(regle.part_des_prairies, 0)} des prairies.")
        rubrique("Pourquoi", pourquoi_)
    st.caption(f"Pour : {ACTIONS['payer']['pour']}")

    f1, f3 = st.columns([3, 2])
    f2, f4 = st.columns([3, 2])
    echelle = f1.segmented_control("Échelle", ["communes", "intercommunalités", AIRES],
                                   default="communes", key="echelle_payer") or "communes"
    criteres = [c for c in CRITERES if echelle != AIRES or c != "zonages d'enjeux"]
    critere = f2.segmented_control(
        "Classer par", criteres, default="hectares", key=f"critere_{echelle}",
        help="Les hectares font ressortir les grands territoires ; le taux, ceux qui perdent une "
             f"grande part de leurs prairies (au moins 100 ha en {r0}) ; les zonages d'enjeux, "
             "les retournements là où l'eau ou la nature sont en jeu.") or "hectares"
    col, mesure, en_pct = CRITERES[critere]
    dep = f3.selectbox("Territoire", ["Normandie"] + list(DEPARTEMENTS), key="dep_payer",
                       format_func=lambda d: DEPARTEMENTS.get(d, d))
    tailles = [20, 50, 100] if echelle == "communes" else [5, 10, 20]
    n = f4.segmented_control("Combien", tailles, default=tailles[1], key=f"combien_{echelle}") \
        or tailles[1]
    seuil = 100 if en_pct else MIN_HA

    perimetre = calc if dep == "Normandie" else calc[calc.dep == dep]
    if echelle == AIRES:
        u = k.rename(columns={"retourne_recent_ha": "retourne_recent"}).copy()
        u["nom"] = u.nom.map(nom_propre)
        if dep != "Normandie":  # aires qui ont des prairies dans le département
            u = u[u.index.isin(cc[cc.insee.str[:2] == dep].aac)]
    elif echelle == "intercommunalités":
        somme = ["retourne_recent", "retourne_recent_enjeux", f"pp_{r0}"]
        u = perimetre.groupby("epci").agg({**{c: "sum" for c in somme}, "epci_nom": "first"})
        u = u.rename(columns={"epci_nom": "nom"})
        delta_r = max(an - r0, 1)
        u["retournement_recent_taux_annuel"] = u.retourne_recent / u[f"pp_{r0}"] / delta_r
    else:
        u = perimetre.rename(columns={"nom_officiel": "nom"})
    if en_pct:
        u = u[u[f"pp_{r0}"] >= 100]
    liste = u[u[col] > 0].sort_values(col, ascending=False).head(n)
    total = u[col].clip(lower=0).sum()
    de = DE_TERRITOIRE[dep]
    if en_pct:
        st.markdown(f"**Où.** Les {len(liste)} {echelle} {de} qui perdent la plus "
                    f"grande part de leurs prairies : de {pct(liste[col].min(), 1)} à "
                    f"{pct(liste[col].max(), 1)} par an.")
    else:
        st.markdown(f"**Où.** Ces {len(liste)} {echelle} portent "
                    f"{pct(liste[col].sum() / total, 0)} des {mesure} {de}.")
    carte_et_liste(echelle, dep, u, liste, col, en_pct, ACTIONS["payer"]["couleur"],
                   f"non classée : moins de {seuil} ha de prairies, ou aucune", "payer")
    if echelle == AIRES and len(liste):
        fiche_captage(liste, u)
    if cl is not None:
        rubrique("Indicateur de suivi",
                 f"La part des prairies hors zonage retournée chaque année : "
                 f"{pct(cl.loc['aucun zonage', 'taux_annuel'], 1)} sur {a0}–{an}. À comparer, "
                 "l'an prochain, dans les territoires de la liste et ailleurs.")


def fiche_captage(liste, u):
    """Interlocuteurs de l'aire de captage choisie (liste, ou clic sur la carte)."""
    options = list(liste.index) + [a for a in u.index if a not in liste.index]
    if st.session_state.get("aac") not in options:
        st.session_state["aac"] = options[0]
    choix = st.selectbox("Aire de captage", options, key="aac",
                         format_func=lambda a: nom_propre(k.loc[a, "nom"]))
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
    contacts = [f"{nom_propre(r[c])} ({role})" for c, role in roles.items()
                if isinstance(r[c], str)]
    contacts.append(f"{r.agence_eau}, qui finance les paiements pour services environnementaux")
    st.markdown("Interlocuteurs : " + " ; ".join(contacts) + ".")
    absents = [role for c, role in roles.items() if not isinstance(r[c], str)]
    if absents:
        texte = " et ".join(absents)
        st.caption(f"{texte[0].upper()}{texte[1:]} : non renseigné par le Sandre.")


# --- 3. S'appuyer sur les exemples ------------------------------------------------------------------
def exemple():
    epci = calc.groupby("epci").agg(nom=("epci_nom", "first"), perte=("retourne_recent", "sum"))
    epci = epci.sort_values("perte", ascending=False)
    paires = []
    for e, row in epci.head(5).iterrows():
        ici = exemples[exemples.epci == e].sort_values(f"pp_{an}", ascending=False)
        paires.append(f"- **{row.nom}** ({ha(row.perte)} retournés sur {r0}–{an}) : "
                      + (f"{len(ici)} commune{'s' if len(ici) > 1 else ''} sans perte nette, "
                         f"dont {', '.join(ici.nom_officiel.head(3))}." if len(ici) else
                         "aucune commune sans perte nette ; chercher dans les intercommunalités "
                         "voisines."))
    rubrique("Le conseil", "Faire témoigner les éleveurs des communes qui gardent leurs prairies "
             "dans les intercommunalités qui en retournent le plus. Pour les cinq premières :")
    st.markdown("\n".join(paires))
    rubrique("Pourquoi", f"{nombre(len(exemples))} communes sur {nombre(len(calc))} n'ont pas "
             f"perdu de prairies depuis {a0}. Leurs éleveurs montrent, au plus près, qu'on peut "
             "garder l'herbe dans les mêmes conditions de sol et de marché.")
    st.caption(f"Pour : {ACTIONS['exemple']['pour']}")

    f1, f2, f3 = st.columns([3, 2, 2])
    echelle = f1.segmented_control("Échelle", ["communes", "intercommunalités"],
                                   default="communes", key="echelle_exemple") or "communes"
    dep = f2.selectbox("Territoire", ["Normandie"] + list(DEPARTEMENTS), key="dep_exemple",
                       format_func=lambda d: DEPARTEMENTS.get(d, d))
    tailles = [20, 50, 100] if echelle == "communes" else [5, 10, 20]
    n = f3.segmented_control("Combien", tailles, default=tailles[1],
                             key=f"combien_ex_{echelle}") or tailles[1]
    perimetre = calc if dep == "Normandie" else calc[calc.dep == dep]
    col = f"pp_{an}"
    if echelle == "intercommunalités":
        u = perimetre.groupby("epci").agg(nom=("epci_nom", "first"), solde=("solde", "sum"),
                                          **{col: (col, "sum")})
    else:
        u = perimetre.rename(columns={"nom_officiel": "nom"})
    exemplaires = u[u.solde >= 0]
    liste = exemplaires.sort_values(col, ascending=False).head(n)
    de = DE_TERRITOIRE[dep]
    if exemplaires.empty:
        st.markdown(f"**Où.** Aucune des {nombre(len(u))} {echelle} {de} n'a gardé toutes ses "
                    f"prairies depuis {a0} : les exemples sont à chercher à l'échelle des "
                    "communes.")
    else:
        st.markdown(f"**Où.** {nombre(len(exemplaires))} {echelle} {de} sur {nombre(len(u))} "
                    f"n'ont pas perdu de prairies depuis {a0}. Les {len(liste)} qui en gardent "
                    f"le plus en totalisent {ha(liste[col].sum())}.")
    carte_et_liste(echelle, dep, u, liste, col, False, ACTIONS["exemple"]["couleur"],
                   f"non classée : moins de {MIN_HA} ha de prairies, ou aucune", "exemple",
                   hors=f"perd des prairies depuis {a0}")
    rubrique("Indicateur de suivi", f"Le nombre de communes sans perte nette : "
             f"{nombre(len(exemples))} sur {nombre(len(calc))} entre {a0} et {an}.")


# --- Carte et liste, communes aux deux derniers moyens ----------------------------------------------
def carte_et_liste(echelle, dep, u, liste, col, en_pct, couleur, sans_donnee, cle_vue,
                   hors="hors de la liste"):
    gauche, droite = st.columns([3, 2], gap="large")
    rangs = {i: r + 1 for r, i in enumerate(liste.index)}
    with gauche:
        if echelle == AIRES:
            g, cle, couche = captages_carte(), "aac", "captages"
            g = g[g.aac.isin(u.index)].copy()
        elif echelle == "intercommunalités":
            g, cle, couche = epci_carte(), "epci", "epci"
            g = g[g.epci.isin(u.index)].copy()
        else:
            g, cle, couche = communes_carte(), "insee", "communes"
            g = (g if dep == "Normandie" else g[g.dep == dep]).copy()
        noms = u.nom if "nom" in u else pd.Series(dtype=str)
        g["nom"] = g[cle].map(noms).fillna(g[cle].map(t.nom_officiel) if cle == "insee"
                                           else g[cle])
        g["couleur"] = couleurs_liste(g[cle], rangs, set(u.index), couleur)
        g["valeur"] = g[cle].map(u[col]).map(
            lambda v: "sans donnée" if pd.isna(v) else pct(v, 1) if en_pct else ha(v))
        g["rang"] = g[cle].map(lambda i: f"n° {rangs[i]} de la liste" if i in rangs
                               else hors if i in u.index else sans_donnee)
        evt = st.pydeck_chart(
            deck([(g[[cle, "nom", "couleur", "valeur", "rang", "geometry"]], couche)], g,
                 "<b>{nom}</b><br/>{valeur}<br/>{rang}"),
            on_select="rerun", selection_mode="single-object", width="stretch",
            key=f"carte_{cle_vue}_{echelle}")
        elements = [(couleur, "dans la liste"), (HORS, hors)]
        if (~g[cle].isin(u.index)).any():
            elements.append((NOIR, sans_donnee))
        legende(elements)
        clic = selection_carte(evt, couche, cle)
        # Un clic ne compte qu'une fois : la sélection de la carte persiste d'un rechargement à
        # l'autre, et ne doit pas écraser un choix fait ensuite dans la liste déroulante.
        if clic and clic != st.session_state.get(f"_clic_{cle_vue}_{echelle}"):
            st.session_state[f"_clic_{cle_vue}_{echelle}"] = clic
            if echelle == "communes":
                st.session_state["commune"] = clic
                st.switch_page("vues/commune.py")
            elif echelle == AIRES:
                st.session_state["aac"] = clic
    with droite:
        tete = liste.head(15)
        st.markdown(f"Les {len(tete)} premières")
        st.altair_chart(classement(tete.nom, tete[col], couleur,
                                   "part par an" if en_pct else "hectares", en_pct=en_pct),
                        width="stretch")
        st.caption({"communes": "Un clic sur une commune de la carte ouvre sa fiche.",
                    AIRES: "Un clic sur une aire de la carte affiche ses interlocuteurs "
                           "ci-dessous."}.get(echelle, ""))
        export = pd.DataFrame({"rang": range(1, len(liste) + 1), "nom": liste.nom.values,
                               col: liste[col].round(4 if en_pct else 0).values})
        if echelle == "communes":
            export.insert(2, "intercommunalite", liste.epci_nom.values)
        if echelle == AIRES:
            export.insert(2, "premier_contact", [contact_captage(k.loc[a]) for a in liste.index])
        st.download_button(f"Télécharger la liste ({len(liste)} {echelle}, CSV)",
                           export.to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig"),
                           f"prairimetre_{cle_vue}_{col}_{echelle.replace(' ', '_')}.csv",
                           "text/csv", icon=":material/download:", key=f"dl_{cle_vue}")


AFFICHER = {"suivre": suivre, "payer": payer, "exemple": exemple}
AFFICHER[moyen]()

st.caption(f"Comparaison des prairies déclarées de {a0}, {r0} et {an}, parcelle par parcelle. "
           f"{nombre(len(t) - len(calc))} communes ont trop peu de prairies pour être classées "
           f"(moins de {MIN_HA} ha en {a0}) : elles sont en noir sur les cartes. Pour les aires "
           "de captage, seule la partie normande est comptée.")
with st.expander("Pourquoi les prairies comptent"):
    pourquoi()
