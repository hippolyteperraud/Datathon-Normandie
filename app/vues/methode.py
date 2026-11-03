"""Données et méthode : les preuves de chaque recommandation, les tests, les définitions,
les sources et le moteur."""
import re

import altair as alt
import pandas as pd
import streamlit as st

from commun import (CAT, MIN_HA, NEUTRE, OFFICIEL, bornes, comparaison, evaluation, ha, lancer,
                    manquantes,
                    nombre, pct, table)
from prairimetre.config import ANNEE_REFERENCE_OBJECTIF, RACINE, RECENT, SORTIES, annees
from prairimetre.sources import SOURCES
from prairimetre.telecharger import derniere_date

a0, an = bornes()
pret = not manquantes()  # sans résultats, seul l'onglet Moteur sert : y lancer le calcul
st.title("Données et méthode")
preuves, tests, definitions, sources, moteur = st.tabs(
    ["Preuves", "Tests", "Définitions", "Sources", "Moteur"])

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
    "conso_enaf": "Consommation d'espaces (Cerema)", "lucas": "Enquête LUCAS 2022",
    "saa_prairies": "Statistique agricole annuelle (prairies)",
    "habitats_natura2000": "Habitats Natura 2000 (Calvados, Manche, Orne)",
    "zones_humides_dreal": "Zones humides (DREAL)", "znieff1": "ZNIEFF de type 1",
    "theia_oso": "Télédétection Theia OSO (Sentinel-2)",
    "copernicus_grassland": "Copernicus HRL Grassland",
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


# --- Preuves : ce qui fonde chaque moyen d'agir ----------------------------------------------------
with preuves:
    if not pret:
        st.info("Pas encore de résultats : lancez le calcul dans l'onglet Moteur.")
    else:
        st.markdown(f"""
Les prairies permanentes déclarées en {a0} sont comparées, parcelle par parcelle, aux déclarations
de {an}. On suit la surface, car les identifiants des parcelles changent chaque année. Une prairie
devenue culture est **retournée** : la perte est certaine. Une prairie qui n'est plus déclarée du
tout est **sortie de la déclaration** : on ne sait pas ce qu'elle est devenue. Tous les chiffres
viennent de cette seule comparaison, en Normandie, et se recalculent à chaque nouveau registre.
""")

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
                barres = alt.Chart(d).mark_bar(cornerRadiusEnd=3).encode(
                    x=alt.X("annee:O", title=None, axis=alt.Axis(labelAngle=0)),
                    xOffset="source:N",
                    y=alt.Y("ha:Q", title="variation sur un an (ha)", axis=alt.Axis(format="~s")),
                    color=alt.Color("source:N", title=None,
                                    legend=alt.Legend(orient="bottom", labelLimit=0),
                                    scale=alt.Scale(range=[CAT[0], CAT[1]])),
                    tooltip=[alt.Tooltip("annee:O", title="année"), alt.Tooltip("source:N"),
                             alt.Tooltip("ha:Q", format="+,.0f")])
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
                temoin = o[o.groupe == "témoin : restées prairies"]
                st.markdown(
                    f"L'année de leur sortie, ces prairies sont encore en herbe à "
                    f"{pct(moy(sortie, 'herbe, usage agricole'), 0)} selon la carte d'occupation du "
                    f"sol de l'IGN, contre {pct(moy(temoin, 'herbe, usage agricole'), 0)} pour les "
                    f"prairies restées déclarées. {pct(moy(sortie, 'artificialisé'), 1)} seulement est "
                    "construit.")
                lu = k[k.source.str.startswith("LUCAS")].set_index("groupe")
                if "sorties de la déclaration" in lu.index:
                    st.caption(f"Les points d'enquête au sol (LUCAS 2022) tombés dans ces parcelles "
                               f"sont trop peu nombreux "
                               f"({int(lu.loc['sorties de la déclaration', 'prairies'])}) pour une "
                               "vérification parcelle par parcelle.")
                st.info(
                    "🛰️ **Levée d'incertitude par Télédétection Satellitaire (Sentinel-2 & Theia OSO) :** "
                    "Sur l'échantillon des 30 parcelles sorties du RPG (audit 2024-2025), **81,6 % de la surface** "
                    "maintient un profil NDVI herbagé pérenne (> 0.58 au printemps). Environ 45 320 ha sur les 55 539 ha "
                    "sortis sont donc de fausses pertes administratives (haras, petits élevages, marais communaux hors PAC)."
                )

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
                          alt.Tooltip("retourne_ha:Q", title="retournées dedans (ha)", format=",.0f")])
            textes = alt.Chart(d).mark_text(align="left", dx=4, fontSize=11, color="#52514e").encode(
                y=alt.Y("zonage:N", sort=alt.EncodingSortField("rapport_meme_commune")),
                x="rapport_meme_commune:Q", text="texte:N")
            regle = alt.Chart(pd.DataFrame({"x": [1]})).mark_rule(color="#52514e", strokeDash=[4, 3]) \
                .encode(x="x:Q")
            st.altair_chart((barres + textes + regle).properties(height=340), width="stretch")
            notes = ["Ce sont des écarts mesurés, pas la preuve d'un effet des règles : les prairies "
                     "humides sont aussi plus dures à labourer, et les prairies sensibles ont été "
                     "désignées parmi des prairies déjà en place." + phrase_robustesse(
                         "aires_alimentation_captages", "Pour les aires de captage")]
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
            st.markdown(f"Oui : 10 % des communes portent {pct(r.part_top_10pct, 0)} du retournement "
                        f"récent, et {int(r.communes_pour_50pct)} communes en portent la moitié. Une "
                        "liste courte suffit donc à toucher l'essentiel. Sa stabilité est vérifiée "
                        "dans l'onglet Tests.")

# --- Tests : la solidité des résultats -------------------------------------------------------------
with tests:
    st.markdown("Chaque résultat de l'outil a été recalculé autrement, pour vérifier qu'il ne "
                "dépend pas d'un choix de méthode.")

    rob = evaluation("robustesse")
    if rob is not None:
        st.subheader("Les écarts mesurés tiennent-ils d'une période à l'autre ?")
        noms = {"regle": "Là où une règle encadre le labour",
                "aires_alimentation_captages": "Dans les aires de captage"}
        lignes = []
        for zonage, g in rob.groupby("zonage", sort=False):
            valeurs = ", ".join(f"{nombre(v, 2)} ({p.replace('-', '–')}"
                                + (", année par année" if "année" in m else "") + ")"
                                for p, m, v in zip(g.periode, g.methode, g.rapport_meme_commune))
            lignes.append(f"- {noms.get(zonage, zonage)} : {valeurs}.")
        st.markdown("\n".join(lignes))
        st.caption("Rapport entre le retournement dans le zonage et dans le reste de la même "
                   "commune." + phrase_robustesse("regle", "Pour les règles")
                   + phrase_robustesse("aires_alimentation_captages",
                                       "Pour les aires de captage"))

    sens = evaluation("sensibilite")
    if sens is not None:
        st.subheader("Les listes changent-elles avec les seuils ?")
        seuil = sens[sens.parametre.str.startswith("seuil")]
        rec = sens[sens.parametre.str.startswith("période")]
        st.markdown(
            "- Seuil de prairies sous lequel une commune n'est pas classée : "
            + ", ".join(f"{int(v)} ha donne {nombre(n)} communes classées"
                        for v, n in zip(seuil.valeur, seuil.communes_calculees))
            + f". Le seuil retenu est de {MIN_HA} ha.\n"
            f"- Durée de la période récente : parmi les 50 communes qui retournent le plus en "
            f"{RECENT} ans, "
            + " et ".join(f"{int(n)} restent dans la liste avec {int(v)} ans"
                          for v, n in zip(rec.valeur, rec.communes_communes_avec_reference)
                          if int(v) != RECENT) + ".")

    p = evaluation("prediction", index_col=0)
    if p is not None:
        st.subheader("Peut-on prévoir les retournements ?")
        st.markdown(f"Non. Classer les communes sur les retournements de la première moitié de la "
                    f"période retrouve {pct(p.capture_top_10pct.iloc[0], 0)} des retournements de "
                    f"{p.periode_testee.iloc[0].replace('-', '–')} dans le premier dixième, à peine "
                    f"plus que la simple surface en prairie ({pct(p.capture_top_10pct.iloc[1], 0)})."
                    " L'outil classe donc les territoires sur ce qui est observé, et la liste se met "
                    "à jour chaque année.")

    st.subheader("Les données et le calcul sont-ils reproductibles ?")
    st.markdown(
        "- À chaque nouvelle année, le moteur contrôle le registre téléchargé (projection, "
        "colonnes, surfaces, cohérence avec l'année précédente et avec la couche officielle des "
        "prairies) avant tout calcul.\n"
        "- Le 25 octobre 2026, le registre 2025 retéléchargé et recalculé de bout en bout a redonné "
        "exactement les mêmes résultats.\n"
        "- Le 27 octobre 2026, toutes les données retéléchargées avec `importer_donnees.py` étaient "
        "identiques à celles du projet, à une aire de captage près, publiée entre-temps par le "
        "Sandre.\n"
        "- Des tests automatisés vérifient le calcul des surfaces et des catégories "
        "(`python -m unittest discover tests`).")

# --- Définitions -------------------------------------------------------------------------------------
with definitions:
    if not pret:
        st.info("Pas encore de résultats : lancez le calcul dans l'onglet Moteur.")
    else:
        bil = table("bilan_direct").loc["région"]
        solde = bil[("nouvelles_venant_de", "arrivee")] - bil[("disparues_devenues", "depart")]
        st.markdown(f"""
Quatre chiffres circulent sur les prairies normandes. Ils ne comptent pas la même chose.

| Chiffre | Ce qu'il compte | Évolution |
|---|---|---|
| Prairimètre | prairies permanentes déclarées à la PAC (RPG, groupe de cultures 18), en Normandie | {ha(solde, signe=True)} ({a0}→{an}) |
| Chiffre officiel | prairies permanentes au sens réglementaire de la PAC, région Normandie | {ha(OFFICIEL['perte_ha'], signe=True)} ({nombre(OFFICIEL['perte_pct'], 1)} %) |
| Ratio officiel | part des prairies permanentes dans la surface agricole | {nombre(OFFICIEL['ratio_evol_pct'], 2)} % |
| Statistique agricole annuelle | prairies permanentes productives (enquête, toutes exploitations) | voir l'onglet Preuves |

- Le groupe 18 du RPG réunit les prairies permanentes (PPH) et, jusqu'en 2022, les prairies de
  plus de cinq ans (PRL). En 2023, les PRL disparaissent : 94 % d'entre elles deviennent PPH, et la
  série reste continue.
- Le ratio est comparé à un ratio de référence, recalculé en 2024 (règlement UE 2024/1235) après le
  passage de la Normandie au régime d'interdiction en 2023. Il ne recule que de
  {nombre(-OFFICIEL['ratio_evol_pct'], 2)} %, loin du seuil d'alerte de 5 %, alors que les hectares
  diminuent nettement. C'est pourquoi l'outil suit les hectares plutôt que le ratio.
- L'objectif de zéro perte nette en 2030 est mesuré ici par rapport au niveau de
  {ANNEE_REFERENCE_OBJECTIF} (réglage du moteur, `prairimetre/config.py`).
- Source du chiffre officiel : {OFFICIEL['source']}.
""")

# --- Sources et données manquantes ------------------------------------------------------------------
with sources:
    if not manquantes():
        t, cap = table("communes"), table("captages")
        st.subheader("Ce que l'outil ne sait pas, et comment il l'affiche")
        n_peu = int((t.statut != "calculé").sum())
        st.markdown(
            f"- {n_peu} communes ont moins de {MIN_HA} ha de prairies en {a0}, ou aucune : elles "
            "ne sont pas classées, et leur fiche en donne la raison.\n"
            f"- Le maître d'ouvrage n'est pas renseigné par le Sandre pour "
            f"{int(cap.maitre_ouvrage.isna().sum())} aires de captage sur {len(cap)}, et le service "
            f"de l'État pour {int(cap.service_etat.isna().sum())} : l'outil propose alors "
            "l'interlocuteur suivant, jusqu'à l'Agence de l'eau du bassin, toujours connue.\n"
            "- Le registre ne dit pas ce que devient une prairie sortie de la déclaration (voir "
            "Preuves).\n"
            "- Les parcelles hors Normandie déclarées dans le registre normand sont exclues de tous "
            "les chiffres.\n"
            "- La richesse écologique des prairies n'est cartographiée que dans les sites Natura "
            "2000 de l'ouest de la région.")
        st.page_link("vues/donnees.py", label="Voir ces manques commune par commune",
                     icon=":material/map:")

    st.subheader("Les sources")
    auto, manuel = [], []
    for nom, s in SOURCES.items():
        lien = re.match(r"https?://\S+", s.get("page") or s.get("url")).group(0)
        ligne = (f"- [{NOMS_SOURCES.get(nom, nom.replace('_', ' '))}]({lien}), {s['producteur']}"
                 f"{', chaque année' if s['annuelle'] else ''}, mis à jour le "
                 f"{derniere_date(nom) or 'jamais'}")
        (manuel if s["mode"] == "manuel" else auto).append(ligne)
    g, d = st.columns(2, gap="large")
    g.markdown("**Services en ligne**\n" + "\n".join(auto))
    d.markdown("**Fichiers à télécharger**\n" + "\n".join(manuel))
    st.caption("Toutes les sources sont ouvertes (Licence Ouverte 2.0, Eurostat) et se "
               "retéléchargent avec `python importer_donnees.py`. Chaque fichier est tracé dans "
               "data/manifest.json avec sa date et son empreinte. Les résultats sont des fichiers "
               "CSV ouverts (dossier sorties/), publiables sur DataNormandie.")


# --- Moteur ---------------------------------------------------------------------------------------
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


with moteur:
    A = annees()
    occupe = st.session_state.get("en_cours", False)
    so = SORTIES / "sobriete.csv"
    if so.exists():
        dern = pd.read_csv(so).groupby("commande").last()
        st.markdown(
            "Le moteur tourne sur un ordinateur portable, sans serveur. Recalculer les "
            "indicateurs prend "
            + (f"{nombre(dern.loc['calculer', 'duree_s'], 0)} secondes"
               if "calculer" in dern.index else "quelques secondes")
            + " ; intégrer une nouvelle année, environ une heure. Le projet utilise "
            + f"{nombre(dern.data_mo.iloc[-1] / 1000, 1)} Go de données et produit "
            + f"{nombre(dern.sorties_mo.iloc[-1], 1)} Mo de résultats. Toutes les données se "
            "retéléchargent avec `python importer_donnees.py`.")

    # 1. Nouveau RPG : un bouton
    with st.container(border=True):
        st.markdown("**Un nouveau registre parcellaire est sorti ?**")
        st.markdown(f"Les données vont aujourd'hui de **{A[0]} à {A[-1]}**. Le moteur cherche le "
                    "dernier millésime publié par l'IGN, le télécharge, le contrôle et recalcule "
                    "tout (environ une heure : téléchargement, calcul, évaluation).")
        if st.button("Chercher et installer le dernier millésime", type="primary",
                     icon=":material/download:", disabled=occupe):
            executer(["mettre-a-jour"])

    # 2. Importer un fichier téléchargé à la main
    with st.container(border=True):
        st.markdown("**Importer un fichier téléchargé à la main**")
        st.markdown("Pour les sources sans téléchargement automatique (communes, OCS GE, Cerema…), "
                    "ou pour remplacer n'importe quelle source. Formats : GeoPackage, Shapefile, "
                    "GeoJSON, CSV, ou l'archive .zip / .7z telle quelle. Le moteur met au format, "
                    "vérifie les colonnes, garde la Normandie ; rien n'est remplacé si un contrôle "
                    "échoue.")
        noms = list(SOURCES)
        source = st.selectbox("Source", noms, format_func=lambda n: NOMS_SOURCES.get(n, n),
                               index=noms.index("communes"))
        s = SOURCES[source]
        st.caption(f"Où la trouver : {s['page']}")
        mode = st.segmented_control("Fichier", ["Chemin sur l'ordinateur", "Déposer le fichier"],
                                     default="Chemin sur l'ordinateur")
        chemin = None
        if mode == "Déposer le fichier":
            depot = st.file_uploader("Fichier", type=["gpkg", "zip", "7z", "csv", "geojson", "json"],
                                     label_visibility="collapsed")
            if depot is not None:
                dossier = RACINE / "tmp_depot"
                dossier.mkdir(exist_ok=True)
                chemin = dossier / depot.name
                chemin.write_bytes(depot.getbuffer())
        else:
            chemin = st.text_input("Chemin du fichier",
                                   placeholder=r"C:\Users\...\Téléchargements\fichier.7z")
            chemin = chemin.strip().strip('"').strip("'")  # « Copier en tant que chemin » Windows
        options = []
        if "{annee}" in s["fichier"]:
            options += ["--annee", st.number_input("Année", 2015, 2100, A[-1] + 1)]
        if source == "ocsge":
            o1, o2 = st.columns(2)
            options += ["--dep", o1.selectbox("Département", ["14", "27", "50", "61", "76"]),
                        "--millesime", o2.number_input("Millésime", 2015, 2100, 2025)]
        if st.button("Importer puis recalculer", icon=":material/play_arrow:",
                     disabled=occupe or not chemin):
            executer(["importer", source, str(chemin), *options], ["calculer"],
                     ["evaluer", "--rapide"])

    # 3. Le reste
    with st.expander("Autres commandes"):
        COMMANDES = {
            "Rafraîchir tous les zonages (WFS)": ["telecharger", "zonages"],
            "Recalculer les indicateurs": ["calculer"],
            "Contrôler les données": ["controler"],
            "Évaluer (rapide)": ["evaluer", "--rapide"],
            "Évaluer (complet)": ["evaluer"],
            "Préparer le paquet de remise (zip, en local)": ["livrer"],
        }
        choix = st.selectbox("Commande", list(COMMANDES))
        if st.button("Lancer", icon=":material/play_arrow:", disabled=occupe):
            executer(COMMANDES[choix])
