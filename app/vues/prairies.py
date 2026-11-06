"""Objectif 2030 : où en sont les prairies permanentes déclarées, les années à part et ce qui les
explique, ce qu'on ne sait pas, pourquoi l'alerte officielle ne sonne pas, et ce qui retient les
prairies.

Les chiffres viennent des sorties du moteur (sorties/) et changent d'eux-mêmes avec chaque nouveau
registre. Une année est « à part » quand ses sorties de la déclaration dépassent le double d'une
année ordinaire, quand son retournement en dépasse 1,75 fois, ou quand la part de ses sorties
déclarées de nouveau ensuite en dépasse 1,75 fois (une année ordinaire = la médiane des autres).
Les explications officielles (app/references.py, avec leurs sources) ne s'affichent que pour une
année que les données montrent à part."""
import altair as alt
import pandas as pd
import streamlit as st

from commun import (ACTIONS, AXE_FR, DEPARTEMENTS, FLUX_COULEURS, OFFICIEL, SEUIL_RATIO_PCT,
                    bornes, classement, comparaison, evaluation, exiger_sorties, ha, nombre, table)
from humain import bandeau, pourquoi
from references import AGRICULTEUR_ACTIF, FIN_AUTORISATION_2019, RATIOS

FOIS_SORTIES = 2        # sorties de la déclaration : au-delà du double d'une année ordinaire
FOIS_RETOURNEMENT = 1.75
FOIS_RETOUR = 1.75      # part des sorties déclarées de nouveau ensuite

exiger_sorties()
a0, an = bornes()
obj, serie, bilan = table("objectif"), table("serie_region"), table("bilan_direct")
suivi = table("suivi_sorties")
saa, cl = evaluation("saa"), evaluation("classes", index_col=0)
COULEUR = ACTIONS["suivre"]["couleur"]
ROUGE, ORANGE, VERT = (FLUX_COULEURS[c] for c in ("culture", "non déclaré", "prairie permanente"))


def fois_ordinaire(v):
    """Chaque valeur divisée par la médiane des autres (valeurs manquantes ignorées)."""
    return pd.Series([x / v.drop(i).median() if pd.notna(x) else float("nan")
                      for i, x in v.items()], index=v.index)


# --- Les chiffres -------------------------------------------------------------------------------
niveau = obj.set_index("annee").prairies_ha
ref = obj.iloc[0]
a_ref, a_obj = int(ref.annee_reference), int(ref.annee_objectif)
ref_ha = ref.reference_ha if pd.notna(ref.reference_ha) else niveau.get(a_ref, niveau.iloc[0])
ecart = niveau.loc[an] - ref_ha                      # < 0 : il manque des prairies
depuis_a0 = niveau.loc[an] - niveau.loc[a0]
sorties_total = bilan.loc["région"][("disparues_devenues", "non déclaré")]

# Une période par ligne (« 2022-2023 ») : flux de l'année et devenir de ses sorties à la fin
s = serie.assign(fin=serie.periode.str[-4:].astype(int))
s["libelle"] = s.periode.str.replace("-", "→")
s = s.merge(suivi[suivi.dep == "région"].drop(columns=["dep", "fin"]), on="periode", how="left")
s["entrees"] = s.entree_culture + s.entree_non_declare + s.entree_temporaire
s["part_revenue"] = (s.redeclares_ha / s.sortis_ha).where(s.fin < an)
s["fois_sorties"] = fois_ordinaire(s.sortie_non_declare)
s["fois_retournement"] = fois_ordinaire(s.sortie_culture)
s["fois_retour"] = fois_ordinaire(s.part_revenue)
s["sorties_fortes"] = s.fois_sorties > FOIS_SORTIES
s["retournement_fort"] = s.fois_retournement > FOIS_RETOURNEMENT
s["trou"] = s.fois_retour > FOIS_RETOUR
s["a_part"] = s.sorties_fortes | s.retournement_fort | s.trou
if saa is not None:
    s = s.merge(saa[["annee", "saa_variation"]], left_on="fin", right_on="annee", how="left")
else:
    s["saa_variation"] = float("nan")
fortes = s[s.sorties_fortes]
apres = int(fortes.fin.max()) if len(fortes) else None   # fin de la dernière année de fortes sorties

# --- En-tête ------------------------------------------------------------------------------------
bandeau("Prairimètre", "Le suivi des prairies permanentes de Normandie")
st.title(f"Suivre l'objectif {a_obj}")
st.markdown(f"Objectif régional : **zéro perte nette de prairies permanentes en {a_obj}**, par "
            f"rapport à {a_ref}.")


def chiffre(colonne, titre, valeur, note, aide=None):
    colonne.metric(titre, valeur, note, delta_color="off", delta_arrow="off", border=True,
                   help=aide, height="stretch")


cases = st.columns(4 if apres else 2)
chiffre(cases[0], f"Prairies déclarées en {an}", ha(niveau.loc[an]),
        f"{ha(depuis_a0, signe=True)} depuis {a0}")
chiffre(cases[1], f"Écart au niveau de {a_ref}", ha(ecart, signe=True),
        "référence non confirmée")
if apres:
    r = fortes.iloc[-1]
    chiffre(cases[2], f"Si l'herbe sortie en {apres} est restée", ha(ecart + r.toujours_hors_ha,
                                                                    signe=True),
            f"{ha(r.toujours_hors_ha)} encore hors PAC",
            aide=f"L'écart à l'objectif si les prairies sorties de la déclaration en {r.libelle}, "
                 f"et pas déclarées de nouveau depuis, sont encore en herbe. Aucune source ne le dit "
                 "aujourd'hui : c'est une borne, pas une estimation.")
    chiffre(cases[3], f"Depuis {apres}", ha(niveau.loc[an] - niveau.loc[apres], signe=True),
            f"en {an - apres} ans")

# --- Deux graphiques : le niveau, et ce qui entre et sort chaque année ---------------------------
gauche, droite = st.columns(2, gap="large")
with gauche:
    d = obj.rename(columns={"annee": "année", "prairies_ha": "ha"})
    d["prairies"] = d.ha.map(ha)
    ligne = alt.Chart(d).mark_line(strokeWidth=2, color=COULEUR,
                                   point=alt.OverlayMarkDef(size=60)).encode(
        x=alt.X("année:O", title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("ha:Q", title="hectares", scale=alt.Scale(zero=False),
                axis=alt.Axis(labelExpr=AXE_FR)),
        tooltip=[alt.Tooltip("année:O"), alt.Tooltip("prairies:N")])
    cible = alt.Chart(pd.DataFrame({"y": [ref_ha]})).mark_rule(
        color="#8a897f", strokeDash=[4, 3]).encode(y="y:Q")
    texte = alt.Chart(pd.DataFrame({"y": [ref_ha], "x": [str(a0)]})).mark_text(
        align="left", dy=-7, fontSize=11, color="#8a897f").encode(
        y="y:Q", x="x:O", text=alt.value(f"niveau de {a_ref}, à retrouver en {a_obj}"))
    st.markdown("**Les prairies déclarées, chaque année**")
    st.altair_chart((ligne + cible + texte).properties(height=300), width="stretch")
with droite:
    FLUX_ANNEE = [("entrées", "entrees", 1, VERT), ("retournées en culture", "sortie_culture", -1, ROUGE),
                  ("sorties de la déclaration", "sortie_non_declare", -1, ORANGE)]
    f = pd.concat([pd.DataFrame({"année": s.libelle, "flux": nom, "ordre": i, "ha": signe * s[col],
                                 "valeur": s[col].map(ha)})
                   for i, (nom, col, signe, _) in enumerate(FLUX_ANNEE)])
    x = alt.X("année:N", sort=None, title=None, axis=alt.Axis(labelAngle=-40, labelOverlap=False))
    barres = alt.Chart(f).mark_bar().encode(
        x=x, y=alt.Y("ha:Q", title="hectares", stack="zero", axis=alt.Axis(labelExpr=AXE_FR)),
        color=alt.Color("flux:N", title=None, legend=alt.Legend(orient="bottom", direction="vertical", labelLimit=260),
                        scale=alt.Scale(domain=[n for n, *_ in FLUX_ANNEE],
                                        range=[c for *_, c in FLUX_ANNEE])),
        order="ordre:Q",
        tooltip=[alt.Tooltip("année:N"), alt.Tooltip("flux:N"), alt.Tooltip("valeur:N", title="ha")])
    n = s[["libelle", "solde", "saa_variation"]].rename(columns={"libelle": "année"})
    n["registre"] = n.solde.map(lambda v: ha(v, signe=True))
    n["statistique"] = n.saa_variation.map(lambda v: "pas de donnée" if pd.isna(v)
                                           else ha(v, signe=True))
    solde = alt.Chart(n).mark_tick(color="#f4f3ee", thickness=3, size=22).encode(
        x=x, y="solde:Q", tooltip=[alt.Tooltip("année:N"), alt.Tooltip("registre:N", title="solde")])
    stat = alt.Chart(n.dropna(subset=["saa_variation"])).mark_point(
        shape="diamond", size=90, filled=True, color="#f4f3ee", stroke="#3a3a36").encode(
        x=x, y="saa_variation:Q",
        tooltip=[alt.Tooltip("année:N"), alt.Tooltip("statistique:N", title="statistique agricole")])
    st.markdown("**Ce qui entre et sort chaque année**",
                help="Barres : ce que le registre PAC voit entrer et sortir. Trait blanc : le solde "
                     "de l'année. Losange : le solde selon la statistique agricole annuelle "
                     "(Agreste), pour les années où le projet l'a.")
    st.altair_chart((barres + solde + stat).properties(height=300), width="stretch")


# --- Les années à part, et ce qui les explique -----------------------------------------------------
def comparaison_draaf(r):
    """Prairies sorties en 2023 par département : la DRAAF et le Prairimètre."""
    p = suivi[(suivi.periode == r.periode) & (suivi.dep != "région")].set_index("dep").sortis_ha
    d = pd.DataFrame([{"département": DEPARTEMENTS.get(k, k), "source": src, "ha": v, "valeur": ha(v)}
                      for k, ref_ha_dep in AGRICULTEUR_ACTIF["prairies_par_dep_ha"].items()
                      for src, v in (("DRAAF Normandie", ref_ha_dep),
                                     ("Prairimètre", p.get(k, 0)))])
    return alt.Chart(d).mark_bar(cornerRadiusEnd=3, height=10).encode(
        y=alt.Y("département:N", title=None, sort=None, axis=alt.Axis(labelOverlap=False)),
        yOffset="source:N",
        x=alt.X("ha:Q", title="hectares",
                axis=alt.Axis(labelExpr=AXE_FR)),
        color=alt.Color("source:N", title=None,
                        legend=alt.Legend(orient="bottom", direction="vertical"),
                        scale=alt.Scale(range=["#8a897f", ORANGE])),
        tooltip=[alt.Tooltip("département:N"), alt.Tooltip("source:N"),
                 alt.Tooltip("valeur:N", title="ha")]).properties(height=280)


a_part = s[s.a_part]
if len(a_part):
    st.subheader("Les années à part")
ordinaire_retour = s.part_revenue[~s.trou].median()
for _, r in a_part.iterrows():
    titres = (["des prairies entières sortent de la déclaration"] if r.sorties_fortes else []) \
        + ([f"{nombre(r.fois_retournement, 1)} fois plus de retournement en culture"]
           if r.retournement_fort else []) \
        + (["des parcelles manquent au registre publié"] if r.trou else [])
    points = []
    if r.sorties_fortes:
        points.append(f"**{ha(r.sortie_non_declare)} sortis de la déclaration**, "
                      f"{nombre(r.fois_sorties, 1)} fois une année ordinaire ; "
                      f"{nombre(100 * r.entieres_ha / r.sortis_ha, 0)} ha sur 100 en parcelles entières.")
        if pd.notna(r.part_revenue):
            points.append(f"Seuls {nombre(100 * r.part_revenue, 0)} ha sur 100 sont déclarés de nouveau "
                          f"en {an} : ces sorties durent.")
    if r.retournement_fort:
        points.append(f"**{ha(r.sortie_culture)} retournés en culture**, "
                      f"{nombre(r.fois_retournement, 1)} fois une année ordinaire.")
    if r.trou:
        points.append(f"**{nombre(100 * r.part_revenue, 0)} ha sur 100 des surfaces sorties sont "
                      f"déclarés de nouveau ensuite**, contre {nombre(100 * ordinaire_retour, 0)} "
                      "d'habitude : elles manquaient au registre publié cette année-là, puis sont "
                      "revenues. **Cause inconnue** : aucun document trouvé ne l'explique.")
    if pd.notna(r.saa_variation) and (r.saa_variation > 0) != (r.solde > 0):
        points.append(f"La statistique agricole dit l'inverse du registre : "
                      f"{ha(r.saa_variation, signe=True)} (registre : {ha(r.solde, signe=True)}).")
    if a_ref < r.fin <= an and ecart < 0 and r.solde < 0 and -r.solde > -ecart / 2:
        points.append(f"Cette année pèse {ha(-r.solde)} des {ha(-ecart)} d'écart à l'objectif.")

    explication = None
    if r.fin == 2023 and r.sorties_fortes:
        aa = AGRICULTEUR_ACTIF
        explication = (
            f"**Expliqué : la nouvelle PAC réserve les aides aux « agriculteurs actifs »**. Après "
            f"67 ans, un exploitant qui touche sa retraite n'y a plus droit. La DRAAF compte "
            f"{nombre(aa['sortants'])} exploitations sorties (−{aa['baisse_declarants_pct']} % de "
            f"déclarants), dont près de {aa['part_67_ans_pct']} sur 100 ont un chef de 67 ans ou "
            f"plus ; plus de {nombre(aa['prairies_sorties_ha'])} ha de prairies permanentes sortent "
            f"du champ de la PAC, {aa['part_prairies_pct']} ha sur 100 des surfaces sorties. "
            f"Source : [{aa['texte']}]({aa['lien']}).")
    elif r.fin == 2019 and r.retournement_fort:
        explication = (
            "**Coïncide avec la fin du régime d'autorisation** : jusqu'en 2018, retourner une prairie "
            "en Normandie demandait une autorisation ; elle n'est plus exigée en 2019. Lien très "
            f"probable, pas démontré. Source : [{FIN_AUTORISATION_2019['texte']}]"
            f"({FIN_AUTORISATION_2019['lien']}).")

    with st.container(border=True):
        st.markdown(f"#### {r.libelle} : {', '.join(titres)}")
        if explication and r.fin == 2023:
            g, dr = st.columns([3, 2], gap="large")
            with g:
                st.markdown(explication)
                st.markdown("\n".join(f"- {p}" for p in points))
                st.markdown("**Ce qu'on ne sait pas** : si l'herbe est encore là. Ce sont surtout des "
                            "retraités, et la statistique agricole, qui compte l'herbe même hors PAC, "
                            "ne voit pas de baisse : c'est probable, pas prouvé.")
            with dr:
                st.markdown("**Prairies sorties, par département**",
                            help="Les deux comptes viennent du même registre de l'ASP, mais la DRAAF "
                                 "compte les surfaces des exploitations sorties, le Prairimètre les "
                                 "parcelles qui ne sont plus couvertes.")
                st.altair_chart(comparaison_draaf(r), width="stretch")
        else:
            if explication:
                st.markdown(explication)
            st.markdown("\n".join(f"- {p}" for p in points))

# --- Ce qu'on ne sait pas -------------------------------------------------------------------------
st.subheader("Ce qu'on ne sait pas")
doutes = [f"**La référence {a_ref} n'est pas confirmée** par la Région. L'écart de "
          f"{ha(ecart, signe=True)} en dépend : par rapport à {a0}, il serait de "
          f"{ha(depuis_a0, signe=True)}.",
          f"**Si l'herbe des {ha(sorties_total)} sortis de la déclaration depuis {a0} est encore là.** "
          "Aucune source du projet ne le dit."]
try:
    from prairimetre.satellite import PARCELLES_30, lire_observations
    n_vues = len(lire_observations())
    pl = "s" if n_vues > 1 else ""
    doutes[-1] += (f" Vérification par images satellite en cours : {n_vues} parcelle{pl} "
                   f"vérifiée{pl} sur {len(PARCELLES_30)} (page Où aller voir).")
except ValueError as erreur:
    doutes[-1] += f" Le fichier de vérification par images satellite est à corriger : {erreur}."
debut_saa = int(saa.annee.min()) if saa is not None and len(saa) else None
for _, r in a_part[a_part.fin < (debut_saa or 0)].iterrows():
    doutes.append(f"**{r.libelle} ne peut pas être comparée à la statistique agricole** : le projet "
                  f"ne l'a qu'à partir de {debut_saa}.")
with st.container(border=True):
    st.markdown("\n".join(f"- {d}" for d in doutes))

# --- Pourquoi l'alerte officielle ne sonne pas -----------------------------------------------------
ratio = -OFFICIEL["ratio_evol_pct"]
if 0 <= ratio < SEUIL_RATIO_PCT:
    st.subheader("Pourquoi l'alerte officielle ne sonne pas")
    etapes = [f"**{r['annee']}** : recul de {nombre(-r['evolution_pct'], 2)} % par rapport à "
              f"{a0} (référence {nombre(r['reference_pct'], 2)} %), donc {r['consequence']} "
              f"([{r['texte']}]({r['lien']}))." for r in RATIOS]
    st.markdown(
        "Le ratio de la PAC compare la part des prairies dans la surface agricole à celle de "
        f"{a0}. **En 2024, sa référence {a0} a été recalculée** à la baisse : le recul de 2023 "
        "s'efface.\n" + "\n".join(f"- {e}" for e in etapes)
        + f"\n- **{OFFICIEL['date']}** : recul de {nombre(ratio, 2)} %, sous le seuil de "
          f"{SEUIL_RATIO_PCT} % ({OFFICIEL['source']}).\n\n"
          f"Pendant ce temps, les prairies déclarées ont perdu **{ha(-depuis_a0)}** depuis {a0} : "
          "l'objectif se suit en hectares, pas au ratio.")

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

st.markdown("**À suivre à chaque nouveau registre** : le solde de l'année en hectares, les sorties "
            "de la déclaration et leur retour, et la part retournée sous une règle et hors de tout "
            "zonage.")

with st.expander("Pourquoi les prairies comptent"):
    pourquoi()
