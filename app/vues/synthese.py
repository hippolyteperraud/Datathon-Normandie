"""Synthèse : trois recommandations, chacune avec le constat qui la fonde, ce qu'il faut faire,
qui le fait, et l'indicateur qui permettra d'en vérifier l'effet l'année suivante.
Règle de la page : une donnée n'y figure que si elle fonde une recommandation."""
import altair as alt
import pandas as pd
import streamlit as st

from commun import (CAT, NEUTRE, OFFICIEL, arrondi_ha, bornes, evaluation, exiger_sorties, ha,
                    nombre, pct, table)
from humain import bandeau, fois_caen, pourquoi
from prairimetre.config import RECENT

exiger_sorties()
a0, an = bornes()
r0 = an - RECENT
bilan, t, k, obj = table("bilan_direct"), table("communes"), table("captages"), table("objectif")
cl, z, certitude = (evaluation("classes", index_col=0), evaluation("zonages", index_col=0),
                    evaluation("certitude"))

region = bilan.loc["région"]
pp0, ppn = region[("disparues_devenues", "depart")], region[("nouvelles_venant_de", "arrivee")]
solde = ppn - pp0
retournees = region[("disparues_devenues", "culture")]
sorties = region[("disparues_devenues", "non déclaré")]
ref = obj.iloc[0]
a_ref, a_obj = int(ref.annee_reference), int(ref.annee_objectif)
ecart = -obj.ecart_ha.iloc[-1]                       # hectares manquants par rapport à a_ref
rythme = ecart / (an - a_ref)                        # perte par an depuis a_ref
effort = ecart / (a_obj - an)                        # à regagner chaque année d'ici a_obj
chute = obj.set_index("annee").prairies_ha.diff()
annee_chute = int(chute.idxmin())
calc = t[t.statut == "calculé"]
retourne_an = calc.retourne_recent.sum() / RECENT    # retournement récent, par an

bandeau("Prairimètre", "Le suivi des prairies permanentes de Normandie")
st.markdown(
    f"#### Depuis {a0}, la Normandie a perdu {arrondi_ha(-solde)} ha de prairies déclarées "
    f"({pct(solde / pp0, 0, signe=True)}, {fois_caen(-solde)}). Le ratio réglementaire de la PAC "
    f"ne recule pourtant que de {nombre(-OFFICIEL['ratio_evol_pct'], 2)} % : il ne déclenche plus "
    "d'alerte. Trois recommandations en découlent.")


def bloc(numero, titre, qui):
    st.markdown(f"### {numero}. {titre}")
    st.caption(f"Pour : {qui}")


# --- 1. Suivre l'objectif en hectares --------------------------------------------------------------
with st.container(border=True):
    bloc(1, f"Suivre l'objectif {a_obj} en hectares, chaque année", "la Région")
    gauche, droite = st.columns([2, 3], gap="large")
    with gauche:
        herbe = None
        if certitude is not None:
            o = certitude[certitude.source.str.startswith("OCS")
                          & (certitude.groupe == "sorties de la déclaration")]
            herbe = (o["herbe, usage agricole"] * o.ha).sum() / o.ha.sum()
        st.markdown(
            f"**Constat.** Par rapport à {a_ref}, il manque {ha(ecart)} de prairies déclarées, "
            f"soit une perte de {arrondi_ha(rythme)} ha par an, dont l'essentiel en {annee_chute} "
            f"({ha(chute.min())}). Les pertes se partagent entre {arrondi_ha(retournees)} ha "
            f"retournés en culture depuis {a0} et {arrondi_ha(sorties)} ha sortis de la "
            "déclaration"
            + (f", encore en herbe à {pct(herbe, 0)} selon la carte d'occupation du sol de l'IGN."
               if herbe is not None else "."))
        st.markdown(
            f"**Recommandation.** Mesurer l'objectif avec ce compteur plutôt qu'avec le ratio : "
            f"pour revenir au niveau de {a_ref} en {a_obj}, il faudrait regagner environ "
            f"{arrondi_ha(effort)} ha par an. Compter les retournements comme des pertes, et faire "
            f"contrôler un échantillon des sorties de la déclaration avant de les compter : si "
            "l'herbe est restée, l'écart réel est plus faible.")
        st.markdown(f"**Indicateur de suivi.** Le solde annuel en hectares, par département, "
                    f"publié à chaque nouveau registre parcellaire.")
    with droite:
        d = obj.rename(columns={"annee": "année", "prairies_ha": "ha"})
        ligne = alt.Chart(d).mark_line(strokeWidth=2, color=CAT[0],
                                       point=alt.OverlayMarkDef(size=60, color=CAT[0])).encode(
            x=alt.X("année:O", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("ha:Q", title="hectares de prairies déclarées", scale=alt.Scale(zero=False),
                    axis=alt.Axis(format="~s")),
            tooltip=[alt.Tooltip("année:O"), alt.Tooltip("ha:Q", format=",.0f")])
        cible = alt.Chart(pd.DataFrame({"y": [ref.reference_ha]})).mark_rule(
            color="#52514e", strokeDash=[4, 3]).encode(y="y:Q")
        texte = alt.Chart(pd.DataFrame({"y": [ref.reference_ha], "x": [str(a0)]})).mark_text(
            align="left", dy=-7, fontSize=11, color="#52514e").encode(
            y="y:Q", x="x:O", text=alt.value(f"niveau de {a_ref}, à retrouver en {a_obj}"))
        st.altair_chart((ligne + cible + texte).properties(height=260), width="stretch")
        st.caption(f"Chiffre officiel {a0}→2026 : {ha(OFFICIEL['perte_ha'], signe=True)} "
                   f"({OFFICIEL['source']}).")

# --- 2. Financer la prairie ordinaire --------------------------------------------------------------
with st.container(border=True):
    bloc(2, "Payer le maintien des prairies que rien ne protège",
         "la Région, la chambre d'agriculture, les Agences de l'eau")
    if cl is not None and z is not None:
        hors = cl.loc["aucun zonage"]
        gauche, droite = st.columns([2, 3], gap="large")
        with gauche:
            st.markdown(
                f"**Constat.** Là où une règle encadre le labour (prairies sensibles, zones "
                f"humides de la PAC), on retourne environ "
                f"{nombre(1 / z.loc['regle', 'rapport_meme_commune'], 0)} fois moins qu'à côté, "
                f"dans la même commune. Mais ces règles ne couvrent que "
                f"{pct(cl.loc['règle', 'part_des_prairies'], 0)} des prairies, et "
                f"{pct(hors.part_du_retournement, 0)} des retournements ont lieu hors de tout "
                f"zonage. Au-dessus des captages d'eau potable, on retourne autant qu'ailleurs.")
            st.markdown(
                f"**Recommandation.** Étendre les inventaires ne suffira pas : ils n'interdisent "
                f"pas le labour. Il faut payer le maintien de l'herbe (MAEC, paiements pour "
                f"services environnementaux) là où rien ne la protège, en commençant par les "
                f"aires de captage, où {arrondi_ha(k.retourne_recent_ha.sum() / RECENT)} ha sont "
                f"retournés chaque année sur {r0}–{an}.")
            st.markdown(f"**Indicateur de suivi.** La part des prairies hors zonage retournée "
                        f"chaque année : {pct(hors.taux_annuel, 1)} aujourd'hui.")
        with droite:
            d = cl.reset_index()[["classe", "taux_annuel"]]
            d["texte"] = d.taux_annuel.map(lambda v: pct(v, 2))
            d["classe"] = d.classe.map({"règle": "une règle encadre le labour",
                                        "site protégé": "site protégé, sans règle",
                                        "inventaire seul": "inventaire seulement",
                                        "aucun zonage": "aucun zonage"})
            base = alt.Chart(d).encode(
                y=alt.Y("classe:N", sort=None, title=None,
                        axis=alt.Axis(labelLimit=220, ticks=False, labelOverlap=False)),
                x=alt.X("taux_annuel:Q", title="part des prairies retournée chaque année",
                        axis=alt.Axis(labels=False, gridOpacity=0.3)))
            barres = base.mark_bar(cornerRadiusEnd=4, height=16).encode(
                color=alt.condition(alt.datum.classe == "aucun zonage", alt.value(CAT[0]),
                                    alt.value(NEUTRE)),
                tooltip=[alt.Tooltip("classe:N", title=" "), alt.Tooltip("texte:N", title="par an")])
            textes = base.mark_text(align="left", dx=4, fontSize=12, color="#52514e").encode(
                text="texte:N")
            st.altair_chart((barres + textes).properties(height=190), width="stretch")
            st.caption("Comparaison à commune égale : les prairies humides sont aussi plus dures "
                       "à labourer, ce qui explique une partie de l'écart.")
    else:
        st.info("Les résultats de l'évaluation manquent : lancer « evaluer » (Données et "
                "méthode, onglet Moteur).")

# --- 3. Concentrer l'effort -----------------------------------------------------------------------
ret = calc.retourne_recent.sort_values(ascending=False)
n_moitie = int((ret.cumsum() / ret.sum() < 0.5).sum() + 1)
epci = calc.groupby("epci_nom").retourne_recent.sum().sort_values(ascending=False)
kr = k.retourne_recent_ha.sort_values(ascending=False)
top10 = kr.head(10).sum() / kr.sum()
with st.container(border=True):
    bloc(3, "Concentrer l'effort sur une liste courte",
         "la chambre d'agriculture, les DDT(M), les intercommunalités, les syndicats d'eau")
    tete = ", ".join(f"{nom} ({ha(v)})" for nom, v in epci.head(3).items())
    st.markdown(
        f"**Constat.** Sur {r0}–{an}, environ {arrondi_ha(retourne_an)} ha de prairies sont "
        f"retournés chaque année. La moitié l'est dans {n_moitie} communes seulement. Trois "
        f"intercommunalités en portent {pct(epci.head(3).sum() / epci.sum(), 0)} : {tete}. "
        f"Côté eau potable, 10 aires de captage portent {pct(top10, 0)} des retournements "
        "au-dessus des captages.")
    st.markdown(
        "**Recommandation.** Bâtir un programme d'animation par intercommunalité de tête, avec la "
        "liste des communes concernées, et prévenir le gestionnaire de chacune des 10 aires de "
        "captage.")
    st.markdown("**Indicateur de suivi.** Le retournement dans les communes de la liste, comparé "
                "au reste de la région.")
    c1, c2, c3 = st.columns(3)
    aller = None
    if c1.button("Voir la liste des communes", icon=":material/arrow_forward:"):
        aller = ("vues/prairies.py", "communes")
    if c2.button("Voir les aires de captage", icon=":material/arrow_forward:"):
        aller = ("vues/prairies.py", "aires de captage")
    if c3.button("Ouvrir le diagnostic d'une commune", icon=":material/arrow_forward:"):
        aller = ("vues/commune.py", None)
    if aller:
        page, echelle = aller
        if echelle:  # ouvre « Où agir » directement sur la bonne vue
            st.session_state["objectif"] = "Où financer le maintien"
            st.session_state["echelle_Où financer le maintien"] = echelle
        st.switch_page(page)

with st.expander("Pourquoi les prairies comptent"):
    pourquoi()
