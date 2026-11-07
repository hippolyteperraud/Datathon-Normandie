"""Technique : ce qui permet de vérifier et de refaire le travail. Les preuves de chaque recommandation
(et les tests qui les vérifient), les sources, les mots de l'outil, et le bouton qui relance les
calculs."""
import re

import altair as alt
import pandas as pd
import streamlit as st

from commun import (AXE_FR, CAT, MIN_HA, NEUTRE, OFFICIEL, aides_chiffres, bornes, comparaison,
                    evaluation, exiger_sorties, ha, lancer, manquantes, nombre, pct, table)
from prairimetre.config import RECENT
from prairimetre.donnees import FAMILLES as FAMILLES_ZONAGES
from prairimetre.sources import SOURCES
from prairimetre.telecharger import derniere_date

MOTS = {
    "Aire de captage": "zone dont l'eau rejoint un captage d'eau potable.",
    "BCAE": "règles de la PAC (la 2 : zones humides et tourbières ; la 9 : prairies sensibles).",
    "Brut, net": "net = brut moins les prairies apparues dans la même commune.",
    "Chiffre officiel": aides_chiffres()["Chiffre officiel"],
    "EPCI": "communauté de communes, d'agglomération ou urbaine.",
    "MAEC, PSE": "aides pour garder ses prairies.",
    "Natura 2000": "sites européens protégés.",
    "OCS GE": "carte de l'occupation du sol (IGN).",
    "Prairie déclarée": "en herbe depuis au moins 5 ans, déclarée à la PAC.",
    "Prairimètre": aides_chiffres()["Prairimètre"],
    "Ratio officiel": aides_chiffres()["Ratio officiel"],
    "Retournée": "labourée, puis déclarée en culture.",
    "RPG": "carte des parcelles déclarées à la PAC (IGN).",
    "Sortie de la déclaration": "plus dans le registre ; l'herbe peut être encore là.",
    "Statistique agricole annuelle": "enquête du ministère de l'Agriculture.",
    "ZNIEFF": "inventaire de milieux naturels, sans effet sur le labour.",
}

NOMS_ZONAGES = {
    "prairies_sensibles": "Prairies sensibles (BCAE 9)",
    "bcae_zones_humides_tourbieres": "Zones humides et tourbières (BCAE 2)",
    "par7_zones_humides_est": "Zones humides, programme nitrates",
    "natura2000_sic": "Natura 2000, habitats",
    "natura2000_zps": "Natura 2000, oiseaux",
    "rnn": "Réserves naturelles nationales", "rnr": "Réserves naturelles régionales",
    "apb": "Arrêtés de protection de biotope", "cen": "Sites des conservatoires",
    "zones_humides_dreal": "Zones humides (inventaire DREAL)",
    "znieff1": "ZNIEFF de type 1",
    "srce_reservoirs": "Réservoirs de biodiversité (SRCE)",
    "plu_zone_n": "Zone N des PLU",
    "aires_alimentation_captages": "Aires de captage d'eau potable",
    "pnr": "Parcs naturels régionaux",
}
FAMILLES = {"regle": "règle qui encadre le labour", "site": "site protégé",
            "inventaire": "inventaire (sans effet sur le labour)",
            "aires_alimentation_captages": "acteur (sans règle)", "pnr": "acteur (sans règle)"}
COULEURS_FAMILLES = {"règle qui encadre le labour": CAT[0], "site protégé": CAT[1],
                     "inventaire (sans effet sur le labour)": CAT[2],
                     "acteur (sans règle)": NEUTRE}

NOMS_SOURCES = {
    "rpg": "Registre parcellaire graphique", "pp_officiel": "Couche officielle des prairies",
    "prairies_sensibles": "Prairies sensibles", "bcae_zones_humides_tourbieres":
        "Zones humides et tourbières BCAE", "natura2000_sic": "Natura 2000, habitats",
    "par7_zones_humides_est": "Zones humides, programme nitrates",
    "srce_reservoirs": "Réservoirs de biodiversité (SRCE)",
    "natura2000_zps": "Natura 2000, oiseaux", "pnr": "Parcs naturels régionaux",
    "rnn": "Réserves naturelles nationales", "rnr": "Réserves naturelles régionales",
    "cen": "Sites des conservatoires", "apb": "Arrêtés de biotope", "plu_zonage": "Zonage des PLU",
    "aires_alimentation_captages": "Aires de captage d'eau potable",
    "epci_noms": "Noms des intercommunalités", "codes_postaux": "Codes postaux",
    "communes": "Communes", "ocsge": "OCS GE",
    "saa_prairies": "Statistique agricole annuelle (prairies)",
    "saa_series": "Statistique agricole annuelle (séries longues : herbe et SAU)",
    "habitats_natura2000": "Habitats Natura 2000 (Calvados, Manche, Orne)",
    "zones_humides_dreal": "Zones humides (DREAL)", "znieff1": "ZNIEFF de type 1",
}
# Les sources rangées selon ce à quoi elles servent
GROUPES_SOURCES = {
    "Le compteur": ["rpg", "pp_officiel", "saa_series", "saa_prairies", "ocsge"],
    "Les règles": FAMILLES_ZONAGES["regle"],
    "Les sites protégés": FAMILLES_ZONAGES["site"],
    "Les inventaires": ["zones_humides_dreal", "znieff1", "srce_reservoirs", "plu_zonage"],
    "Les acteurs": ["aires_alimentation_captages", "pnr"],
    "Les habitats": ["habitats_natura2000"],
    "Les communes": ["communes", "epci_noms", "codes_postaux"],
}


def phrase_robustesse(zonage, sujet):
    """« Pour les règles, le rapport va de 0,18 à 0,24 selon la période : on y retourne moins
    qu'ailleurs (environ 5 fois moins). » — tiré des tests de robustesse du moteur."""
    sens, v = comparaison(zonage)
    if sens is None:
        return ""
    return (f" {sujet}, le rapport va de {nombre(v.min(), 2)} à {nombre(v.max(), 2)} selon la "
            f"période : on y retourne {sens} qu'ailleurs"
            + (f" (environ {nombre(1 / v.mean(), 0)} fois moins)." if sens == "moins" else "."))


def moy(d, c):
    """Moyenne pondérée par la surface."""
    return (d[c] * d.ha).sum() / d.ha.sum()


def executer(*etapes):
    """Lance une ou plusieurs commandes du moteur à la suite, journal en direct ; s'arrête à la
    première qui échoue. Renvoie True si tout s'est bien passé."""
    st.session_state["en_cours"] = True
    zone, journal = st.empty(), []
    progression = re.compile(r"\d+ / [\d,]+ (Mo|objets)$")
    try:
        with st.spinner("Le moteur travaille…"):
            for args in etapes:
                journal.append("$ python -m prairimetre " + " ".join(map(str, args)))
                for ligne in lancer(*args):
                    if ligne.startswith("__code__"):
                        code = int(ligne[8:])
                        break
                    # une barre de progression remplace la ligne précédente
                    if progression.search(ligne) and progression.search(journal[-1]):
                        journal[-1] = ligne
                    else:
                        journal.append(ligne)
                    zone.code("\n".join(journal[-40:]), language=None)
                if code != 0:
                    st.error("Le moteur s'est arrêté : voir le journal ci-dessus. Rien n'a été "
                             "remplacé si la vérification a échoué.")
                    return False
    finally:
        st.session_state["en_cours"] = False
        st.cache_data.clear()  # les pages relisent les nouvelles sorties
    st.success("Terminé : toutes les pages affichent maintenant les nouvelles données.")
    return True


a0, an = bornes()
pret = not manquantes()  # sans résultats, seul l'onglet Recalculer sert : y lancer le calcul
st.title("Technique")
if pret:
    exiger_sorties()  # prévient si un registre plus récent que les résultats est en local
preuves, sources, mots, moteur = st.tabs(["Preuves", "Sources", "Les mots", "Recalculer"])
SANS_RESULTATS = "Pas encore de résultats : lancez le calcul dans l'onglet Recalculer."

# --- Preuves : ce qui fonde chaque chiffre de l'appli -----------------------------------------------
with preuves:
    if not pret:
        st.info(SANS_RESULTATS)
    else:
        st.markdown(f"Les prairies permanentes déclarées en {a0} sont comparées, parcelle par "
                    f"parcelle, aux déclarations de {an}, en Normandie. Tous les chiffres viennent "
                    "de cette seule comparaison et se recalculent à chaque nouveau registre. Chaque "
                    "question ci-dessous fonde un chiffre de l'appli ; chaque réponse a été "
                    "recalculée autrement pour vérifier qu'elle ne dépend pas d'un choix de méthode.")

        # 1. Le compteur en hectares -------------------------------------------------------------------
        st.subheader("1. Le compteur en hectares est-il fiable ?")
        bil = table("bilan_direct").loc["région"]
        solde = bil[("nouvelles_venant_de", "arrivee")] - bil[("disparues_devenues", "depart")]
        st.markdown(f"Pour les retournements, oui. Le solde {a0}→{an} ({ha(solde, signe=True)}) est à "
                    f"{ha(abs(solde - OFFICIEL['perte_ha']))} du chiffre officiel "
                    f"({ha(OFFICIEL['perte_ha'], signe=True)}). Les sorties de la déclaration, elles, "
                    "demandent une vérification.")
        s = evaluation("saa", index_col=0)
        k = evaluation("certitude")
        g1, g2 = st.columns([3, 2], gap="large")
        if s is not None:
            with g1:
                d = s[["rpg_variation", "saa_variation"]].dropna().reset_index().melt(
                    "annee", var_name="source", value_name="ha")
                d["source"] = d.source.map({"rpg_variation": "prairies déclarées (RPG)",
                                            "saa_variation": "statistique agricole annuelle"})
                d["variation"] = d.ha.map(lambda x: ha(x, signe=True))
                barres = alt.Chart(d).mark_bar(cornerRadiusEnd=3).encode(
                    x=alt.X("annee:O", title=None, axis=alt.Axis(labelAngle=0)),
                    xOffset="source:N",
                    y=alt.Y("ha:Q", title="variation (ha/an)",
                            axis=alt.Axis(labelExpr=AXE_FR)),
                    color=alt.Color("source:N", title=None,
                                    legend=alt.Legend(orient="bottom", labelLimit=0),
                                    scale=alt.Scale(range=[CAT[0], CAT[1]])),
                    tooltip=[alt.Tooltip("annee:O", title="année"), alt.Tooltip("source:N"),
                             alt.Tooltip("variation:N")])
                st.altair_chart(barres.properties(height=220), width="stretch")
                v = s[["rpg_variation", "saa_variation"]].dropna()
                if len(v):
                    y = v.rpg_variation.idxmin()
                    rpg, saa = v.loc[y, "rpg_variation"], v.loc[y, "saa_variation"]
                    st.caption(f"En {y}, les prairies déclarées varient de {ha(rpg, signe=True)}, la "
                               f"statistique agricole annuelle, indépendante de la PAC, de "
                               f"{ha(saa, signe=True)}"
                               + (" : une partie de la perte du registre tient aux déclarations."
                                  if rpg < 0 and saa > rpg / 2 else "."))
        if k is not None:
            with g2:
                o = k[k.source.str.startswith("OCS")]
                sortie = o[o.groupe == "sorties de la déclaration"]
                st.markdown(
                    f"L'année de leur sortie, {pct(moy(sortie, 'herbe, usage agricole'), 0)} de "
                    "ces prairies restent des terres agricoles selon la carte d'occupation du sol "
                    f"de l'IGN, et {pct(moy(sortie, 'artificialisé'), 1)} seulement est construit. "
                    "Mais cette carte range prairies et cultures dans la même classe : elle ne dit "
                    "pas si l'herbe est encore là.")
        sat = None
        try:
            from prairimetre.sentinel import DOSSIER as DOSSIER_SAT, bilan as bilan_sat
            sat = bilan_sat(pd.read_csv(DOSSIER_SAT / "parcelles.csv", dtype={"id_rpg": str}))
        except FileNotFoundError:
            pass
        if sat:
            s23 = sat["sortie 2023"]
            st.markdown(
                f"**Les images Sentinel-2 le disent en partie.** Une règle tirée du NDVI de toute "
                f"l'année sépare une prairie d'une parcelle labourée : validée sur 40 parcelles dont le "
                f"registre donne la réponse, elle se trompe {sat['erreurs_validation']} fois sur "
                f"{sat['tranchees_validation']} (une première règle, fixée à l'avance, avait échoué et "
                f"a été abandonnée). Sur {s23['parcelles']} prairies sorties de la PAC en 2023, tirées au "
                f"hasard, {s23['couvert']} des {s23['tranchees']} tranchées restent vertes toute l'année, "
                "sans labour. Preuves, parcelle par parcelle, avec un lien vers la photo aérienne : "
                "`verification/sentinel2/preuves.md`.")

        # 2. Les règles et les zonages -----------------------------------------------------------------
        z = evaluation("zonages", index_col=0)
        cl = evaluation("classes", index_col=0)
        h = evaluation("habitats", index_col=0)
        if z is not None and cl is not None:
            st.subheader("2. Les règles retiennent-elles les prairies ?")
            st.markdown(
                f"Là où elles s'appliquent, oui, mais elles couvrent peu. Dans une même commune, on "
                f"retourne environ {nombre(1 / z.loc['regle', 'rapport_meme_commune'], 0)} fois moins "
                f"là où une règle encadre le labour. Ces règles couvrent "
                f"{pct(cl.loc['règle', 'part_des_prairies'], 0)} des prairies, et "
                f"{pct(cl.loc['aucun zonage', 'part_du_retournement'], 0)} du retournement a lieu hors "
                "de tout zonage. Le graphique compare chaque zonage au reste de la même commune : "
                "sous 1, on y retourne moins ; autour de 1, autant.")
            d = z.loc[[n for n in NOMS_ZONAGES if n in z.index]].reset_index()
            petits = d[d.part_des_prairies < 0.01]  # trop peu de prairies pour un rapport fiable
            d = d[d.part_des_prairies >= 0.01].copy()
            d["famille"] = d.famille.map(FAMILLES)
            d["texte"] = d.rapport_meme_commune.map(lambda v: nombre(v, 2))
            d["retournees"] = d.retourne_ha.map(ha)
            d["zonage"] = d.zonage.map(NOMS_ZONAGES)
            barres = alt.Chart(d).mark_bar(cornerRadiusEnd=4, height=14).encode(
                y=alt.Y("zonage:N", sort=alt.EncodingSortField("rapport_meme_commune"), title=None,
                        axis=alt.Axis(labelLimit=260, ticks=False)),
                x=alt.X("rapport_meme_commune:Q",
                        title="retournement dans le zonage / reste de la même commune",
                        axis=alt.Axis(labels=False, ticks=False)),
                color=alt.Color("famille:N", title=None,
                                legend=alt.Legend(orient="bottom", labelLimit=0),
                                scale=alt.Scale(domain=list(COULEURS_FAMILLES),
                                                range=list(COULEURS_FAMILLES.values()))),
                tooltip=[alt.Tooltip("zonage:N"), alt.Tooltip("famille:N"),
                         alt.Tooltip("texte:N", title="rapport"),
                         alt.Tooltip("retournees:N", title="retournées dedans")])
            textes = alt.Chart(d).mark_text(align="left", dx=4, fontSize=11, color="#52514e").encode(
                y=alt.Y("zonage:N", sort=alt.EncodingSortField("rapport_meme_commune")),
                x="rapport_meme_commune:Q", text="texte:N")
            regle = alt.Chart(pd.DataFrame({"x": [1]})).mark_rule(color="#52514e", strokeDash=[4, 3]) \
                .encode(x="x:Q")
            st.altair_chart((barres + textes + regle).properties(height=340), width="stretch")
            terrain = evaluation("terrain")
            a_terrain_egal = ""
            if terrain is not None and len(terrain) == 3:
                r = terrain.set_index("comparaison").rapport_meme_commune
                a_terrain_egal = (
                    f" Pour séparer les deux, on compare à terrain égal : les prairies d'inventaire, "
                    f"sans aucune règle, sont déjà {nombre(1 / r.iloc[0], 1)} fois moins retournées ; "
                    f"mais dans les sites Natura 2000, les prairies sensibles (interdiction) le sont "
                    f"{nombre(1 / r.iloc[1], 0)} fois moins que les autres prairies du site, et dans les "
                    f"zones humides {nombre(1 / r.iloc[2], 0)} fois moins. Le terrain compte, et "
                    "l'interdiction agit en plus.")
            notes = ["Les prairies humides sont aussi plus dures à labourer, et les prairies sensibles "
                     "ont été désignées parmi des prairies déjà en place." + a_terrain_egal
                     + phrase_robustesse("regle", "Pour les règles")
                     + phrase_robustesse("aires_alimentation_captages",
                                         "Pour les aires de captage")]
            if len(petits):
                notes.append("Non représentés, faute de prairies : "
                             + ", ".join(petits.zonage.map(NOMS_ZONAGES).str.lower()) + ".")
            st.caption(" ".join(notes))
            if h is not None:
                tot = h.loc["total"]
                st.markdown(
                    f"Les prairies remarquables connues tiennent : sur {ha(tot.en_prairie_declaree_ha)} "
                    f"d'habitats prairiaux d'intérêt européen déclarés en {a0} dans les sites Natura "
                    f"2000 du Calvados, de la Manche et de l'Orne, {ha(tot.retourne_ha)} ont été "
                    "retournés. Les pertes touchent la prairie ordinaire.")

        # 3. La concentration ----------------------------------------------------------------------------
        c = evaluation("concentration", index_col=0)
        if c is not None:
            st.subheader("3. Les retournements sont-ils concentrés ?")
            r = c.loc["retourne_recent"]
            texte = (f"Oui : 10 % des communes portent {pct(r.part_top_10pct, 0)} du retournement "
                     f"récent, et {int(r.communes_pour_50pct)} communes en portent la moitié. Une "
                     "liste courte suffit donc à toucher l'essentiel.")
            sens = evaluation("sensibilite")
            if sens is not None:
                rec = sens[sens.parametre.str.startswith("période")]
                texte += (f" Elle est stable : parmi les 50 communes qui retournent le plus en "
                          f"{RECENT} ans, "
                          + " et ".join(f"{int(n)} y restent avec {int(v)} ans"
                                        for v, n in zip(rec.valeur,
                                                        rec.communes_communes_avec_reference)
                                        if int(v) != RECENT) + ".")
            st.markdown(texte)
            p = evaluation("prediction", index_col=0)
            if p is not None:
                st.caption(f"On ne peut pas prévoir les retournements : classer les communes sur la "
                           f"première moitié de la période retrouve "
                           f"{pct(p.capture_top_10pct.iloc[0], 0)} des retournements de "
                           f"{p.periode_testee.iloc[0].replace('-', '–')} dans le premier dixième, "
                           f"autant que la simple surface en prairie "
                           f"({pct(p.capture_top_10pct.iloc[1], 0)}). La liste repose donc sur ce "
                           "qui est observé, et se refait à chaque registre.")

        st.subheader("4. Le calcul est-il reproductible ?")
        st.markdown(
            "Oui. À chaque nouvelle année, le moteur contrôle le registre téléchargé (projection, "
            "colonnes, surfaces, cohérence avec l'année précédente) avant tout calcul. Le 25 "
            "octobre 2026, le registre 2025 retéléchargé et recalculé de bout en bout a redonné "
            "exactement les mêmes résultats ; le 27 octobre, toutes les données retéléchargées "
            "avec `importer_donnees.py` étaient identiques, à une aire de captage près, publiée "
            "entre-temps par le Sandre. Des tests automatisés vérifient le calcul des surfaces et "
            "des catégories (`python -m unittest discover tests`).")

        st.subheader("5. Que ne sait pas l'outil ?")
        t, cap = table("communes"), table("captages")
        n_peu = int((t.statut != "calculé").sum())
        st.markdown(
            f"- {n_peu} communes ont moins de {MIN_HA} ha de prairies en {a0}, ou aucune : elles "
            "ne sont pas classées, et leur fiche en donne la raison.\n"
            f"- Le maître d'ouvrage n'est pas renseigné par le Sandre pour "
            f"{int(cap.maitre_ouvrage.isna().sum())} aires de captage sur {len(cap)}, et le service "
            f"de l'État pour {int(cap.service_etat.isna().sum())} : l'outil propose alors "
            "l'interlocuteur suivant, jusqu'à l'Agence de l'eau du bassin, toujours connue.\n"
            "- Le registre ne dit pas ce que devient une prairie sortie de la déclaration ; les "
            "images satellite montrent si elle reste verte, pas si c'est de l'herbe ou une friche.\n"
            "- La cible de l'objectif (39 % de la surface agricole) a été fixée sur une ancienne "
            "version des chiffres ; Agreste a depuis révisé ses séries : l'outil mesure la part dans "
            "les séries révisées.\n"
            "- Les parcelles hors Normandie déclarées dans le registre normand sont exclues de tous "
            "les chiffres.\n"
            "- La richesse écologique des prairies n'est cartographiée que dans les sites Natura "
            "2000 de l'ouest de la région.")

# --- Sources : rangées par usage, une ligne chacune -------------------------------------------------
with sources:
    def ligne_source(nom):
        s = SOURCES[nom]
        lien = s.get("lien") or re.match(r"https?://\S+", s["page"]).group(0)
        date = derniere_date(nom)
        date = "-".join(reversed(date[:10].split("-"))).replace("-", "/") if date else "date inconnue"
        return f"- [{NOMS_SOURCES.get(nom, nom.replace('_', ' '))}]({lien}), {s['producteur']}, {date}"

    rangees = {n for noms in GROUPES_SOURCES.values() for n in noms}
    # Une source nouvelle reste visible tant qu'elle n'est pas rangée
    autres = [n for n in SOURCES if n not in rangees]
    groupes = list(GROUPES_SOURCES.items()) + ([("Autres", autres)] if autres else [])
    moitie = (len(groupes) + 1) // 2
    for colonne, partie in zip(st.columns(2, gap="large"), (groupes[:moitie], groupes[moitie:])):
        for titre, noms in partie:
            colonne.markdown(f"**{titre}**\n" + "\n".join(ligne_source(n) for n in noms))
    st.caption("Toutes ouvertes (Licence Ouverte 2.0). `python importer_donnees.py` les retélécharge "
               "et les trace dans data/manifest.json.")
    from references import AGRICULTEUR_ACTIF, FIN_AUTORISATION_2019, OBJECTIF_REGIONAL, RATIOS
    textes = [(OBJECTIF_REGIONAL["texte"], OBJECTIF_REGIONAL["lien"], "l'objectif 2030")] + [
        (r["texte"], r["lien"], f"ratio de prairies {r['annee']}") for r in RATIOS] + [
        (AGRICULTEUR_ACTIF["texte"], AGRICULTEUR_ACTIF["lien"], "sorties de 2023, agriculteur actif"),
        (FIN_AUTORISATION_2019["texte"], FIN_AUTORISATION_2019["lien"],
         "fin du régime d'autorisation en 2019")]
    st.markdown("**Textes officiels : l'objectif et les années à part**\n"
                + "\n".join(f"- [{t}]({lien}) : {objet}" for t, lien, objet in textes))

# --- Les mots ---------------------------------------------------------------------------------------
with mots:
    lignes = [f"**{mot}** : {sens}" for mot, sens in MOTS.items()]
    milieu = (len(lignes) + 1) // 2
    for colonne, partie in zip(st.columns(2), (lignes[:milieu], lignes[milieu:])):
        colonne.markdown("  \n".join(partie))

# --- Recalculer : un seul bouton --------------------------------------------------------------------
with moteur:
    if st.button("Relancer les calculs", type="primary", icon=":material/play_arrow:",
                 disabled=st.session_state.get("en_cours", False)):
        executer(["calculer"], ["evaluer"])
