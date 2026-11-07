"""Objectif 2030 : zéro perte nette de prairies permanentes (Stratégie régionale pour la biodiversité,
objectif III.5), « autant de prairies permanentes entre 2021 et 2030 ».

Dans l'ordre : trois chiffres (la mesure officielle, le registre PAC, le registre corrigé par le
satellite), les courbes, pourquoi le registre perd plus que la statistique agricole (les années à
part), ce qui retient les prairies, ce qu'on ne sait pas, et le ratio de la PAC.

Les chiffres viennent des sorties du moteur (sorties/) et de la vérification satellite
(verification/sentinel2/) ; ils changent d'eux-mêmes avec chaque nouveau registre. Une année est
« à part » quand ses sorties de la déclaration dépassent le double d'une année ordinaire, quand son
retournement en dépasse 1,75 fois, ou quand la part de ses sorties déclarées de nouveau ensuite en
dépasse 1,75 fois (année ordinaire = médiane des autres). Les explications officielles
(app/references.py, avec leurs sources) ne s'affichent que pour une année que les données montrent
à part."""
import altair as alt
import pandas as pd
import streamlit as st

from commun import (ACTIONS, AXE_FR, DEPARTEMENTS, FLUX_COULEURS, OFFICIEL, SEUIL_RATIO_PCT,
                    arrondi_ha, bornes, classement, comparaison, evaluation, exiger_sorties, ha,
                    nombre, pct, table)
from humain import bandeau, pourquoi
from references import (AGRICULTEUR_ACTIF, FIN_AUTORISATION_2019, OBJECTIF_REGIONAL, RATIOS,
                        REFERENCE_RATIO)

FOIS_SORTIES = 2         # sorties de la déclaration : au-delà du double d'une année ordinaire
FOIS_RETOURNEMENT = 1.75
FOIS_RETOUR = 1.75       # part des sorties déclarées de nouveau ensuite
PREUVES = "verification/sentinel2/preuves.md"
COULEUR = ACTIONS["suivre"]["couleur"]
GRIS_CLAIR = "#d6d5cd"
ROUGE, ORANGE, VERT = (FLUX_COULEURS[c] for c in ("culture", "non déclaré", "prairie permanente"))
MARQUE = dict(fontSize=13, fontWeight="bold", color=ORANGE)

exiger_sorties()
a0, an = bornes()
obj, serie, bilan = table("objectif"), table("serie_region"), table("bilan_direct")
suivi = table("suivi_sorties")
saa, cl = evaluation("saa"), evaluation("classes", index_col=0)
terrain, bcae2 = evaluation("terrain"), evaluation("bcae2")   # les règles à terrain égal


def fois_ordinaire(v):
    """Chaque valeur divisée par la médiane des autres (valeurs manquantes ignorées)."""
    return pd.Series([x / v.drop(i).median() if pd.notna(x) else float("nan")
                      for i, x in v.items()], index=v.index)


def pluriel(n, mot):
    return f"{nombre(n)} {mot}{'s' if n > 1 else ''}"


# --- Les chiffres -------------------------------------------------------------------------------
annuel = obj.set_index("annee")
niveau = annuel.prairies_ha.dropna()                 # registre PAC
sth = annuel.sth_ha.dropna() if "sth_ha" in annuel else pd.Series(dtype=float)  # mesure officielle
a_ref, a_obj = int(annuel.annee_reference.iloc[0]), int(annuel.annee_objectif.iloc[0])
ref_ha = niveau.get(a_ref, niveau.iloc[0])
ecart = niveau.loc[an] - ref_ha                      # registre depuis la référence (< 0 : perte)
depuis_a0 = niveau.loc[an] - niveau.loc[a0]
sth_fin = int(sth.index.max()) if len(sth) else None
sth_ecart = sth.loc[sth_fin] - sth.loc[a_ref] if sth_fin and a_ref in sth.index else None
part = annuel.part_sth.dropna() if "part_sth" in annuel else pd.Series(dtype=float)  # STH / SAU
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
s = s.merge(saa[["annee", "saa_variation"]], left_on="fin", right_on="annee", how="left") \
    if saa is not None else s.assign(saa_variation=float("nan"))
fortes = s[s.sorties_fortes]
apres = int(fortes.fin.max()) if len(fortes) else None   # fin de la dernière année de fortes sorties

# La vérification par images Sentinel-2, si elle a tourné
try:
    from prairimetre.sentinel import DOSSIER as DOSSIER_SAT, bilan as bilan_sat
    sat = bilan_sat(pd.read_csv(DOSSIER_SAT / "parcelles.csv", dtype={"id_rpg": str, "insee": str}))
except FileNotFoundError:
    sat = None
s23 = sat["sortie 2023"] if sat and apres == 2023 and sat["sortie 2023"]["tranchees"] else None
t30 = sat["30 parcelles"] if sat and sat["30 parcelles"]["tranchees"] else None


def cause_courte(r):
    """Ce qui explique une année à part, en quelques mots, pour les graphiques."""
    morceaux = []
    if r.sorties_fortes:
        morceaux.append("retraités sortis de la PAC" if r.fin == 2023 else "sorties de la déclaration")
    if r.retournement_fort:
        morceaux.append("fin de l'autorisation" if r.fin == 2019 else "retournement fort")
    if r.trou:
        morceaux.append("registre troué")
    return " + ".join(morceaux)


causes = s[s.a_part].copy()
causes["cause"] = [cause_courte(r) for _, r in causes.iterrows()]
causes["numero"] = [str(i) for i in range(1, len(causes) + 1)]

# --- En-tête ------------------------------------------------------------------------------------
bandeau("Prairimètre", "Le suivi des prairies permanentes de Normandie")
st.title(f"Objectif {a_obj} : zéro perte nette de prairies permanentes")
o = OBJECTIF_REGIONAL
st.markdown(f"« {o['periode']} », avec pour cible « {o['cible']} ».",
            help=f"« {o['objectif']} ». {o['texte']} : {o['lien']}")


def chiffre(colonne, titre, valeur, note, aide=None):
    colonne.metric(titre, valeur, note, delta_color="off", delta_arrow="off", border=True,
                   help=aide, height="stretch")


cases = st.columns(4 if apres else 2)
if sth_ecart is not None:
    note = (f"{pct(part.loc[sth_fin], 1)} de la SAU (cible {OBJECTIF_REGIONAL['part_sau_pct']} %)"
            if sth_fin in part.index else f"depuis {a_ref} ({ha(sth.loc[sth_fin])})")
    chiffre(cases[0], f"Mesure officielle, {a_ref}→{sth_fin}", ha(sth_ecart, signe=True), note,
            aide="Superficie toujours en herbe de la statistique agricole annuelle (Agreste, séries "
                 "longues), la source de l'objectif régional. Elle compte toute l'herbe permanente, y "
                 "compris celle des exploitants qui ne déclarent pas à la PAC. La dernière année est "
                 "provisoire.")
else:
    chiffre(cases[0], f"Prairies déclarées en {an}", ha(niveau.loc[an]),
            f"{ha(depuis_a0, signe=True)} depuis {a0}")
chiffre(cases[1], f"Registre PAC, {an}", ha(ecart, signe=True),
        f"depuis {a_ref} ({ha(niveau.loc[an])} déclarés)",
        aide="Prairies permanentes déclarées à la PAC (registre parcellaire graphique). Le registre dit "
             "où et comment on perd, mais ne voit plus l'herbe des exploitants sortis de la PAC.")
if apres:
    r = fortes.iloc[-1]
    if s23:
        pire = ecart + s23["bas"] * s23["population_ha"]
        mieux = ecart + r.toujours_hors_ha
        chiffre(cases[2], "Registre corrigé par le satellite", f"{arrondi_ha(pire)} ha",
                f"au pire ; {arrondi_ha(mieux)} ha au mieux",
                aide=f"Sur {s23['parcelles']} parcelles tirées au hasard parmi les prairies sorties en "
                     f"{r.libelle} et toujours hors déclaration en {an}, {s23['couvert']} des "
                     f"{s23['tranchees']} tranchées restent vertes toute l'année {an}, sans labour "
                     f"(images Sentinel-2). Au pire : seulement la part sûre à 95 % "
                     f"({nombre(100 * s23['bas'], 0)} sur 100) des parcelles d'au moins 1 ha. Au mieux : "
                     f"toutes les {ha(r.toujours_hors_ha)} encore hors déclaration. Preuves : {PREUVES}.")
    else:
        chiffre(cases[2], f"Si l'herbe sortie en {apres} est restée",
                ha(ecart + r.toujours_hors_ha, signe=True), f"{ha(r.toujours_hors_ha)} encore hors PAC",
                aide=f"Le registre si les prairies sorties de la déclaration en {r.libelle}, et pas "
                     "déclarées de nouveau depuis, sont encore en herbe : une borne, pas une estimation.")
    chiffre(cases[3], f"Registre depuis {apres}", ha(niveau.loc[an] - niveau.loc[apres], signe=True),
            f"en {an - apres} ans")

# --- Deux graphiques : les deux sources, et ce qui entre et sort chaque année ---------------------
gauche, droite = st.columns(2, gap="large")
with gauche:
    lignes = {"prairies_ha": ("registre PAC", COULEUR), "sth_ha": ("statistique agricole", GRIS_CLAIR)}
    d = pd.concat([obj[["annee", c]].dropna().rename(columns={"annee": "année", c: "ha"})
                   .assign(source=nom) for c, (nom, _) in lignes.items() if c in obj])
    d["prairies"] = d.ha.map(ha)
    ligne = alt.Chart(d).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=50)).encode(
        x=alt.X("année:O", title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("ha:Q", title="hectares", axis=alt.Axis(labelExpr=AXE_FR), scale=alt.Scale(
            zero=False, domain=[d.ha.min() - 0.03 * d.ha.max(), d.ha.max() * 1.01])),
        color=alt.Color("source:N", title=None, legend=alt.Legend(orient="bottom", direction="vertical"),
                        scale=alt.Scale(domain=[n for n, _ in lignes.values()],
                                        range=[c for _, c in lignes.values()])),
        tooltip=[alt.Tooltip("année:O"), alt.Tooltip("source:N"), alt.Tooltip("prairies:N")])
    pics = alt.Chart(pd.DataFrame({"année": causes.fin.values, "ha": niveau.loc[causes.fin].values,
                                   "numero": causes.numero.values, "cause": causes.cause.values})) \
        .mark_text(dy=17, **MARQUE).encode(x="année:O", y="ha:Q", text="numero:N",
                                           tooltip=[alt.Tooltip("cause:N", title="d'où vient la chute")])
    cible = alt.Chart(pd.DataFrame({"y": [ref_ha]})).mark_rule(
        color="#8a897f", strokeDash=[4, 3]).encode(y="y:Q")
    texte = alt.Chart(pd.DataFrame({"y": [ref_ha], "x": [a0]})).mark_text(
        align="left", dy=-7, fontSize=11, color="#8a897f").encode(
        y="y:Q", x="x:O", text=alt.value(f"registre {a_ref}, à retrouver en {a_obj}"))
    st.markdown("**Les prairies permanentes, chaque année**",
                help="Les deux sources ne comptent pas la même chose : la statistique agricole compte "
                     "toute l'herbe permanente, le registre seulement ce qui est déclaré à la PAC.")
    st.altair_chart((ligne + cible + texte + pics).properties(height=300), width="stretch")
with droite:
    flux = [("entrées", "entrees", 1, VERT), ("retournées en culture", "sortie_culture", -1, ROUGE),
            ("sorties de la déclaration", "sortie_non_declare", -1, ORANGE)]
    f = pd.concat([pd.DataFrame({"année": s.libelle, "flux": nom, "ordre": i, "ha": signe * s[col],
                                 "valeur": s[col].map(ha)})
                   for i, (nom, col, signe, _) in enumerate(flux)])
    x = alt.X("année:N", sort=None, title=None, axis=alt.Axis(labelAngle=-40, labelOverlap=False))
    barres = alt.Chart(f).mark_bar().encode(
        x=x, y=alt.Y("ha:Q", title="hectares", stack="zero", axis=alt.Axis(labelExpr=AXE_FR)),
        color=alt.Color("flux:N", title=None,
                        legend=alt.Legend(orient="bottom", direction="vertical", labelLimit=260),
                        scale=alt.Scale(domain=[n for n, *_ in flux], range=[c for *_, c in flux])),
        order="ordre:Q",
        tooltip=[alt.Tooltip("année:N"), alt.Tooltip("flux:N"), alt.Tooltip("valeur:N", title="ha")])
    n = s[["libelle", "solde", "saa_variation"]].rename(columns={"libelle": "année"})
    n["registre"] = n.solde.map(lambda v: ha(v, signe=True))
    n["statistique"] = n.saa_variation.map(lambda v: "pas de donnée" if pd.isna(v) else ha(v, signe=True))
    solde = alt.Chart(n).mark_tick(color="#f4f3ee", thickness=3, size=22).encode(
        x=x, y="solde:Q", tooltip=[alt.Tooltip("année:N"), alt.Tooltip("registre:N", title="solde")])
    stat = alt.Chart(n.dropna(subset=["saa_variation"])).mark_point(
        shape="diamond", size=90, filled=True, color="#f4f3ee", stroke="#3a3a36").encode(
        x=x, y="saa_variation:Q",
        tooltip=[alt.Tooltip("année:N"), alt.Tooltip("statistique:N", title="statistique agricole")])
    numeros = alt.Chart(pd.DataFrame({"année": causes.libelle, "numero": causes.numero,
                                      "cause": causes.cause,
                                      "y": -(causes.sortie_culture + causes.sortie_non_declare)})) \
        .mark_text(dy=12, **MARQUE).encode(x=x, y="y:Q", text="numero:N",
                                           tooltip=[alt.Tooltip("cause:N", title="d'où vient le pic")])
    st.markdown("**Ce qui entre et sort chaque année**",
                help="Barres : ce que le registre PAC voit entrer et sortir. Trait blanc : le solde de "
                     "l'année. Losange : le solde selon la statistique agricole annuelle (Agreste), pour "
                     "les années où le projet l'a.")
    st.altair_chart((barres + solde + stat + numeros).properties(height=300), width="stretch")
if len(causes):
    st.markdown(" · ".join(f"<span style='color:{ORANGE};font-weight:700'>{r.numero}</span> "
                           f"**{r.libelle}** : {r.cause}" for _, r in causes.iterrows())
                + " (détail ci-dessous)", unsafe_allow_html=True)


# --- Pourquoi le registre perd plus que la statistique agricole : les années à part ---------------
def comparaison_draaf(r):
    """Prairies sorties en 2023 par département : la DRAAF et le Prairimètre."""
    p = suivi[(suivi.periode == r.periode) & (suivi.dep != "région")].set_index("dep").sortis_ha
    d = pd.DataFrame([{"département": DEPARTEMENTS.get(k, k), "source": src, "ha": v, "valeur": ha(v)}
                      for k, draaf in AGRICULTEUR_ACTIF["prairies_par_dep_ha"].items()
                      for src, v in (("DRAAF Normandie", draaf), ("Prairimètre", p.get(k, 0)))])
    return alt.Chart(d).mark_bar(cornerRadiusEnd=3, height=10).encode(
        y=alt.Y("département:N", title=None, sort=None, axis=alt.Axis(labelOverlap=False)),
        yOffset="source:N",
        x=alt.X("ha:Q", title="hectares", axis=alt.Axis(labelExpr=AXE_FR)),
        color=alt.Color("source:N", title=None, legend=alt.Legend(orient="bottom", direction="vertical"),
                        scale=alt.Scale(range=["#8a897f", ORANGE])),
        tooltip=[alt.Tooltip("département:N"), alt.Tooltip("source:N"),
                 alt.Tooltip("valeur:N", title="ha")]).properties(height=280)


def faits(r, ordinaire_retour):
    """Ce que les données montrent d'une année à part, une phrase par fait."""
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
        dep = suivi[(suivi.periode == r.periode) & (suivi.dep != "région")].set_index("dep")
        part = (dep.redeclares_ha / dep.sortis_ha).sort_values(ascending=False)
        forts = part[part > 2 * ordinaire_retour]
        ou = ", ".join(DEPARTEMENTS.get(d, d) for d in forts.index)
        poids = dep.redeclares_ha[forts.index].sum() / dep.redeclares_ha.sum()
        points.append(f"**{nombre(100 * r.part_revenue, 0)} ha sur 100 des surfaces sorties sont "
                      f"déclarés de nouveau ensuite**, contre {nombre(100 * ordinaire_retour, 0)} "
                      "d'habitude : elles manquaient au registre publié cette année-là, puis sont "
                      "revenues intactes."
                      + (f" Le trou se concentre sur : {ou} ({nombre(100 * poids, 0)} ha sur 100 des "
                         "surfaces revenues). " if len(forts) else " ")
                      + "C'est un manque du fichier publié, pas un changement dans les champs. "
                      "Explication probable, non confirmée par un document : le registre publié est "
                      "l'état connu au 1er janvier suivant (IGN), sans les dossiers pas encore "
                      f"instruits. La comparaison directe {a0}→{an} n'en dépend pas.")
    if pd.notna(r.saa_variation) and (r.saa_variation > 0) != (r.solde > 0):
        points.append(f"La statistique agricole dit l'inverse du registre : "
                      f"{ha(r.saa_variation, signe=True)} (registre : {ha(r.solde, signe=True)}).")
    elif pd.notna(r.saa_variation) and r.saa_variation < 0 and r.solde < 0:
        points.append(f"La statistique agricole voit aussi une baisse : {ha(r.saa_variation, signe=True)} "
                      f"(registre : {ha(r.solde, signe=True)}) : la perte est réelle.")
    if a_ref < r.fin <= an and ecart < 0 and r.solde < 0 and -r.solde > -ecart / 2:
        points.append(f"Cette année pèse {ha(-r.solde)} des {ha(-ecart)} perdus par le registre "
                      f"depuis {a_ref}.")
    return points


def explication(r):
    """L'explication officielle d'une année à part, avec sa source ; None si aucune n'est connue."""
    if r.fin == 2023 and r.sorties_fortes:
        aa = AGRICULTEUR_ACTIF
        return (f"**Expliqué : la nouvelle PAC réserve les aides aux « agriculteurs actifs »**. Après "
                f"67 ans, un exploitant qui touche sa retraite n'y a plus droit. La DRAAF compte "
                f"{nombre(aa['sortants'])} exploitations sorties (−{aa['baisse_declarants_pct']} % de "
                f"déclarants), dont près de {aa['part_67_ans_pct']} sur 100 ont un chef de 67 ans ou "
                f"plus ; plus de {nombre(aa['prairies_sorties_ha'])} ha de prairies permanentes sortent "
                f"du champ de la PAC, {aa['part_prairies_pct']} ha sur 100 des surfaces sorties. "
                f"Source : [{aa['texte']}]({aa['lien']}).")
    if r.fin == 2019 and r.retournement_fort:
        return ("**Coïncide avec la fin du régime d'autorisation** : jusqu'en 2018, retourner une "
                "prairie en Normandie demandait une autorisation ; elle n'est plus exigée en 2019. Lien "
                f"très probable, pas démontré. Source : [{FIN_AUTORISATION_2019['texte']}]"
                f"({FIN_AUTORISATION_2019['lien']}).")
    return None


def herbe_ou_friche():
    """Ce que sont les prairies sorties restées vertes : carte d'occupation du sol, photo aérienne."""
    occ, ph = sat.get("occupation_vertes_2023"), sat.get("photos")
    if not occ:
        return "Vert ne veut pas forcément dire herbe : une friche donne le même signal."
    texte = ("**Herbe ou friche ?** Selon la carte d'occupation du sol 2023 (Impact Observatory) : "
             + ", ".join(f"{nombre(n)} {k}" for k, n in occ.items())
             + (" ; aucune boisée." if "arbres" not in occ else "."))
    if ph:
        texte += (f" Sur la photo aérienne de l'IGN, les {nombre(sum(ph.values()))} cas douteux sont "
                  + ", ".join(f"{nombre(n)} {k}" for k, n in ph.items())
                  + " : des pâtures, des prés-vergers, des prés à chevaux (lecture à confirmer).")
    return texte


def vu_du_satellite():
    return (f"**Vu du satellite (Sentinel-2, {an})** : sur {s23['parcelles']} de ces parcelles tirées au "
            f"hasard, **{s23['couvert']} des {s23['tranchees']} tranchées restent vertes toute l'année, "
            f"sans labour**, {pluriel(s23['labourees'], 'labourée')} (au moins "
            f"{nombre(100 * s23['bas'], 0)} sur 100, intervalle à 95 %). La règle a été testée sur 40 "
            f"parcelles dont le registre donne la réponse : {sat['erreurs_validation']} erreurs sur "
            f"{sat['tranchees_validation']}. " + herbe_ou_friche() + f" Preuves : `{PREUVES}`.")


if len(causes):
    st.subheader("Pourquoi le registre perd plus que la statistique agricole")
    ordinaire_retour = s.part_revenue[~s.trou].median()
    for _, r in causes.iterrows():
        titres = (["des prairies entières sortent de la déclaration"] if r.sorties_fortes else []) \
            + ([f"{nombre(r.fois_retournement, 1)} fois plus de retournement en culture"]
               if r.retournement_fort else []) \
            + (["des parcelles manquent au registre publié"] if r.trou else [])
        texte_officiel, points = explication(r), faits(r, ordinaire_retour)
        with st.container(border=True):
            st.markdown(f"#### {r.libelle} : {', '.join(titres)}")
            if r.fin == 2023 and texte_officiel:
                g, dr = st.columns([3, 2], gap="large")
                with g:
                    st.markdown(texte_officiel)
                    st.markdown("\n".join(f"- {p}" for p in points))
                    st.markdown(vu_du_satellite() if s23 else
                                "**Ce qu'on ne sait pas** : si l'herbe est encore là. Ce sont surtout "
                                "des retraités, et la statistique agricole, qui compte l'herbe même hors "
                                "PAC, ne voit pas de baisse : c'est probable, pas prouvé.")
                with dr:
                    st.markdown("**Prairies sorties, par département**",
                                help="Les deux comptes viennent du même registre de l'ASP, mais la DRAAF "
                                     "compte les surfaces des exploitations sorties, le Prairimètre les "
                                     "parcelles qui ne sont plus couvertes.")
                    st.altair_chart(comparaison_draaf(r), width="stretch")
            else:
                if texte_officiel:
                    st.markdown(texte_officiel)
                st.markdown("\n".join(f"- {p}" for p in points))

# --- Ce qui retient les prairies : la règle, mesurée ---------------------------------------------
if cl is not None:
    st.subheader("Ce qui retient les prairies")
    sens, rapports = comparaison("regle")
    sens_aac, _ = comparaison("aires_alimentation_captages")
    regle, hors = cl.loc["règle"], cl.loc["aucun zonage"]
    egal = terrain[terrain.test == "règle à terrain égal"] if terrain is not None else None
    if egal is not None and len(egal) and (egal.rapport_meme_commune < 1).all():
        st.markdown(f"#### L'interdiction de retourner retient l'herbe : à terrain égal, on retourne "
                    f"{nombre(1 / egal.rapport_meme_commune.max(), 0)} à "
                    f"{nombre(1 / egal.rapport_meme_commune.min(), 0)} fois moins.")
    elif sens == "moins":
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
    limites = []
    if len(rapports) > 1:
        limites.append(f"Toutes règles confondues, on retourne {nombre(1 / rapports.max(), 1)} à "
                       f"{nombre(1 / rapports.min(), 1)} fois moins qu'à côté, dans la même commune, "
                       "selon la période.")
    if terrain is not None and len(terrain):
        t_seul = terrain[terrain.test == "terrain seul"].rapport_meme_commune
        n2000 = terrain[terrain.comparaison.str.contains("Natura")].rapport_meme_commune
        zh = terrain[terrain.comparaison.str.contains("zones humides")].rapport_meme_commune
        if len(t_seul):
            limites.append(f"**Le terrain compte** : sans aucune règle, les prairies d'inventaire (ZNIEFF, "
                           f"zones humides) sont déjà {nombre(1 / t_seul.iloc[0], 1)} fois moins "
                           "retournées que les autres de la même commune.")
        if len(n2000) and len(zh):
            limites.append(f"**Mais la règle agit en plus** : dans les sites Natura 2000, les prairies "
                           f"sensibles (interdiction de retourner, BCAE 9) sont {nombre(1 / n2000.iloc[0], 0)} "
                           f"fois moins retournées que les autres prairies du site ; dans les zones "
                           f"humides, {nombre(1 / zh.iloc[0], 0)} fois moins.")
    if bcae2 is not None and len(bcae2):
        avant, apres = bcae2[~bcae2.regle_en_vigueur], bcae2[bcae2.regle_en_vigueur]
        if len(avant) and len(apres):
            limites.append(f"**La BCAE 2** (zones humides, depuis 2025 : un labour au plus en 4 ans) : ses "
                           f"prairies étaient déjà très peu retournées avant ({nombre(1000 * avant.taux_dedans.mean(), 1)} "
                           f"pour mille par an, contre {nombre(1000 * avant.taux_dehors.mean(), 0)} ailleurs) ; "
                           f"la première année, {nombre(1000 * apres.taux_dedans.iloc[-1], 1)} pour mille : "
                           "pas d'effet visible encore.")
    limites.append("Le projet n'a **aucune donnée sur les paiements** (mesures agro-environnementales) : "
                   "il ne dit pas si payer retient l'herbe.")
    if sens_aac == "autant":
        limites.append("Au-dessus des captages d'eau potable, on retourne autant qu'à côté.")
    st.markdown("\n".join(f"- {x}" for x in limites))

# --- Ce qu'on ne sait pas -------------------------------------------------------------------------
st.subheader("Ce qu'on ne sait pas")
if len(part) and o.get("annee_cible") in part.index and a_ref in part.index:
    doutes = [f"**La cible de {o['part_sau_pct']} % a été fixée sur une ancienne version des chiffres** "
              f"({o['annee_cible']}, publiée en 2020). Agreste a depuis révisé ses séries pour les "
              f"mettre en cohérence avec le recensement agricole 2020 : {o['annee_cible']} y vaut "
              f"{pct(part.loc[o['annee_cible']], 1)}. Mesurée dans la même série, la part de l'herbe "
              f"recule de {pct(part.loc[a_ref], 1)} ({a_ref}) à {pct(part.loc[sth_fin], 1)} ({sth_fin}, "
              "provisoire) : l'objectif n'est pas tenu."]
else:
    doutes = [f"**La part officielle ({o['part_sau_pct']} % de la surface agricole) ne peut pas être "
              "recalculée ici** : les séries longues de la statistique agricole manquent "
              "(`python importer_donnees.py --seulement saa_series`)."]
if sth_ecart is not None:
    doutes.append(f"**Les deux sources ne disent pas la même chose** : depuis {a_ref}, le registre PAC "
                  f"perd {ha(-ecart)}, la statistique agricole {ha(-sth_ecart)} (jusqu'en {sth_fin}). "
                  "L'écart vient surtout des exploitants sortis de la PAC en 2023, que la statistique "
                  "agricole compte encore.")
doutes.append(f"**Si les {ha(sorties_total)} sortis de la déclaration depuis {a0} sont encore de "
              "l'herbe, partout.**"
              + (f" Vu du satellite, {t30['couvert']} parcelles sur {t30['tranchees']} tranchées (sur "
                 f"{t30['parcelles']} tirées au hasard) restent vertes toute l'année {an}, et les cas "
                 "douteux regardés sur photo aérienne sont des prés ; mais ce n'est qu'un échantillon, "
                 "et la mesure de toutes les parcelles des communes à aller voir est en cours (page Où "
                 "aller voir)." if t30 else " Aucune source du projet ne le dit encore."))
debut_saa = int(saa.annee.min()) if saa is not None and len(saa) else None
for _, r in causes[causes.fin < (debut_saa or 0)].iterrows():
    doutes.append(f"**{r.libelle} ne peut pas être comparée à la statistique agricole** : le projet "
                  f"ne l'a qu'à partir de {debut_saa}.")
with st.container(border=True):
    st.markdown("\n".join(f"- {d}" for d in doutes))

# --- Le ratio de la PAC : pourquoi l'alerte officielle ne sonne pas --------------------------------
ratio = -OFFICIEL["ratio_evol_pct"]
if 0 <= ratio < SEUIL_RATIO_PCT:
    with st.expander("Le ratio de la PAC : pourquoi l'alerte officielle ne sonne pas"):
        etapes = [f"**{r['annee']}** : recul de {nombre(-r['evolution_pct'], 2)} % par rapport à "
                  f"{REFERENCE_RATIO} (référence {nombre(r['reference_pct'], 2)} %), donc "
                  f"{r['consequence']} ([{r['texte']}]({r['lien']}))." for r in RATIOS]
        st.markdown(
            "Le ratio de la PAC compare la part des prairies dans la surface agricole à celle de "
            f"{REFERENCE_RATIO}. **En 2024, sa référence {REFERENCE_RATIO} a été recalculée** à la baisse : "
            "le recul de 2023 s'efface.\n" + "\n".join(f"- {e}" for e in etapes)
            + f"\n- **{OFFICIEL['date']}** : recul de {nombre(ratio, 2)} %, sous le seuil de "
              f"{SEUIL_RATIO_PCT} % ({OFFICIEL['source']}).\n\n"
              "L'objectif régional se suit avec la statistique agricole et en hectares, pas avec le "
              "ratio de la PAC.")

st.markdown("**À suivre à chaque nouveau registre** : la mesure officielle (statistique agricole), le "
            "solde du registre, les sorties de la déclaration et leur retour, et la part retournée sous "
            "une règle et hors de tout zonage.")

with st.expander("Pourquoi les prairies comptent"):
    pourquoi()
