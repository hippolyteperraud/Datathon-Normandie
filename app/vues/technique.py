"""Technique : ce qui permet de vérifier et de refaire le travail. Les preuves des chiffres de l'appli,
les sources, le glossaire, et les boutons qui relancent les calculs. Version précédente :
app/sauvegardes/technique_avant_2026-11-11.py."""
import html
import re

import streamlit as st

from commun import DEPARTEMENTS, GLOSSAIRE, bornes, exiger_sorties, ha, manquantes, nombre
from prairimetre.sources import SOURCES
from prairimetre.telecharger import derniere_date


NOMS_SOURCES = {
    "rpg": "Registre parcellaire graphique (registre PAC)", "pp_officiel": "Couche officielle des prairies",
    "prairies_sensibles": "Prairies sensibles (BCAE 9)", "bcae_zones_humides_tourbieres":
        "Zones humides et tourbières (BCAE 2)", "natura2000_sic": "Natura 2000, habitats",
    "par7_zones_humides_est": "Zones humides, programme nitrates",
    "srce_reservoirs": "Réservoirs de biodiversité (SRCE)",
    "natura2000_zps": "Natura 2000, oiseaux", "pnr": "Parcs naturels régionaux",
    "rnn": "Réserves naturelles nationales", "rnr": "Réserves naturelles régionales",
    "cen": "Sites des conservatoires", "apb": "Arrêtés de biotope", "plu_zonage": "Zonage des PLU",
    "aires_alimentation_captages": "Aires de captage d'eau potable",
    "epci_noms": "Noms des intercommunalités", "codes_postaux": "Codes postaux",
    "communes": "Communes", "ocsge": "Occupation du sol (OCS GE)",
    "saa_prairies": "Statistique agricole annuelle, prairies",
    "saa_series": "Statistique agricole annuelle, séries longues",
    "habitats_natura2000": "Habitats Natura 2000 (Calvados, Manche, Orne)",
    "zones_humides_dreal": "Zones humides (DREAL)", "znieff1": "ZNIEFF de type 1",
}
# Les sources lues à part du moteur : (nom, lien, producteur)
SENTINEL = ("Images Sentinel-2 (niveau 2A)", "https://planetarycomputer.microsoft.com/dataset/sentinel-2-l2a",
            "ESA / Copernicus, via Planetary Computer")
BD_ORTHO = ("Photos aériennes (BD ORTHO)", "https://cartes.gouv.fr/rechercher-une-donnee/dataset/IGNF_BD-ORTHO",
            "IGN")
HUBEAU = ("Analyses de nitrates des rivières", "https://hubeau.eaufrance.fr/page/api-qualite-cours-deau",
          "Hub'Eau (OFB, BRGM)")
# Les sources rangées selon ce à quoi elles servent dans l'appli : (titre, à quoi elles servent, sources)
GROUPES_SOURCES = [
    ("Les prairies, parcelle par parcelle", "Ma commune, Objectif 2030",
     ["rpg", "pp_officiel", SENTINEL, BD_ORTHO]),
    ("Toute l'herbe de Normandie", "le constat officiel et le recomptage",
     ["saa_series", "saa_prairies", "ocsge"]),
    ("Les règles", "Recommandations : ce que les règles retiennent",
     ["prairies_sensibles", "bcae_zones_humides_tourbieres", "natura2000_sic", "natura2000_zps",
      "par7_zones_humides_est", "aires_alimentation_captages"]),
    ("Le même terrain, pour comparer", "Recommandations : comparer à terrain égal",
     ["zones_humides_dreal", "znieff1", "srce_reservoirs", "habitats_natura2000", "pnr", "rnn", "rnr", "cen",
      "apb", "plu_zonage"]),
    ("L'eau", "Recommandations : les nitrates des rivières", [HUBEAU]),
    ("Les communes", "les noms, les contours, la recherche", ["communes", "epci_noms", "codes_postaux"]),
]

# Les cartes des onglets Preuves, Sources et Glossaire
STYLE = """<style>
.tq-grille{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:.9rem;margin:.3rem 0 .6rem}
.tq-carte{border:1px solid rgba(128,128,128,.3);border-radius:.6rem;padding:.85rem 1.05rem}
.tq-titre{font-weight:700;font-size:1.02rem}
.tq-sous{font-size:.8rem;opacity:.65;margin:.05rem 0 .45rem}
.tq-l{font-size:.88rem;line-height:1.38;margin:.45rem 0 0}
.tq-l a{color:inherit;text-decoration:underline;text-decoration-color:rgba(128,128,128,.6);text-underline-offset:2px}
.tq-meta{font-size:.78rem;opacity:.6}
.tq-chiffre{font-weight:700;white-space:nowrap}
.tq-pile{display:flex;flex-direction:column;gap:.9rem;margin:.3rem 0 .6rem}
.tq-ligne{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:.2rem 1.4rem}
.tq-ligne .tq-l{margin:.35rem 0 0}
</style>"""


def carte(titre, sous_titre, lignes):
    """Une carte : titre, sous-titre discret, lignes (HTML déjà échappé)."""
    return (f"<div class='tq-carte'><div class='tq-titre'>{titre}</div>"
            + (f"<div class='tq-sous'>{sous_titre}</div>" if sous_titre else "")
            + "".join(f"<div class='tq-l'>{texte}</div>" for texte in lignes) + "</div>")


def grille(cartes):
    st.html(STYLE + "<div class='tq-grille'>" + "".join(cartes) + "</div>")


def gras(x):
    return f"<span class='tq-chiffre'>{x}</span>"


a0, an = bornes()
pret = not manquantes()  # sans résultats, seul l'onglet Moteur sert : y lancer le calcul
st.title("Technique")
# Les questions de l'onglet Preuves sont des menus déroulants : leur titre a la taille d'un titre de
# niveau 3 (comme un st.subheader), pour se lire comme des titres et non comme du texte courant
st.html("<style>"
        "[data-testid='stExpander'] summary {padding-top: .7rem; padding-bottom: .7rem}"
        "[data-testid='stExpander'] summary p {font-size: 1.5rem; font-weight: 600; line-height: 1.3}"
        "[data-testid='stExpander'] summary svg {width: 1.6rem; height: 1.6rem}"
        "</style>")
if pret:
    exiger_sorties()  # prévient si un registre plus récent que les résultats est en local
# ?preuve=recompte : posé par le bouton « Comment on a recompté » d'Objectif 2030, ouvre Preuves, partie 2
cible = st.query_params.get("preuve")
moteur, preuves, sources, mots = st.tabs(["Moteur", "Preuves", "Sources", "Glossaire"],
                                         default="Preuves" if cible else None)
SANS_RESULTATS = "Pas encore de résultats : lancez le calcul dans l'onglet Moteur."


def limites():
    """Ce que l'outil ne sait pas, rangé par source ; les chiffres sont lus dans les résultats."""
    from herbe_hors_pac import chiffres
    from prairimetre.sentinel import SURFACE_MIN_HA
    c = chiffres(an)
    cartes = []
    if c:
        hp = c.hp
        photos = hp["photos"]["sortie avant 2023"]
        pres, vus = photos.get("prairie", 0), sum(photos.values())
        taille = hp.get("precision_taille")
        sat = [f"Vert toute l'année ne veut pas dire pré : une friche reste verte aussi. Sur photos aériennes, "
               f"{gras(f'{pres} prés sur {vus}')} morceaux contrôlés.",
               f"« Restée verte » est un minimum : la règle ne reconnaît que "
               f"{gras(nombre(hp['etalons_pct']['herbe']['couvert permanent'], 0) + ' %')} de l'herbe sûre."]
        if taille:
            sat.append(f"Les petits prés sont moins bien reconnus : {gras(nombre(taille['petits']['pct'], 1) + ' %')} "
                       f"sous 5 ha, contre {gras(nombre(taille['grands']['pct'], 1) + ' %')} au-dessus.")
        sat.append(f"Une part sortie de moins de {nombre(SURFACE_MIN_HA, 2)} ha n'est pas mesurée : elle reste "
                   "« à vérifier sur le terrain », comme celles où les images ne tranchent pas.")
        cartes.append(carte("Le satellite", "ce que deviennent les prairies sorties de la PAC", sat))
        PD, U = hp["origines"]["par_dep"], hp["herbe_ign_usages"]
        HD = {d: x[str(an)] for d, x in hp["agreste"]["hors_par_dep"].items()}
        ecart_dep = {d: PD[d]["jamais"] + PD[d]["avant_2023"] - HD[d] for d in DEPARTEMENTS if d in PD and d in HD}
        bas, haut = min(ecart_dep, key=ecart_dep.get), max(ecart_dep, key=ecart_dep.get)
        cartes.append(carte("Le recomptage de l'herbe", "toute l'herbe de Normandie, face à la statistique", [
            f"{gras(ha(c.ecart_total - c.ancien))} d'écart restent non expliqués.",
            f"Juste pour toute la Normandie : par département, l'écart va de "
            f"{gras(ha(ecart_dep[bas], signe=True))} ({DEPARTEMENTS[bas]}) à "
            f"{gras(ha(ecart_dep[haut], signe=True))} ({DEPARTEMENTS[haut]}).",
            f"L'herbe des jardins et des zones d'activité n'est pas cherchée : {gras(ha(U.get('US5', 0)))} en "
            f"usage résidentiel, {gras(ha(U.get('US3', 0)))} en usage tertiaire.",
            "La carte IGN date de 2022 ou 2023 : l'herbe apparue depuis n'est pas cherchée ; les morceaux de moins "
            "de 0,1 ha et les bandes de moins de 20 m sont écartés."]))
    cartes.append(carte("La statistique agricole", "la mesure officielle de l'objectif", [
        f"{an} est provisoire : le chiffre devient définitif l'année suivante.",
        "Son herbe « hors exploitations » est une estimation, dont la méthode n'est pas publiée."]))
    cartes.append(carte("Le registre PAC", "les prairies déclarées", [
        f"Une prairie ajoutée au registre depuis {a0} n'est pas forcément nouvelle : on ne sait pas si elle était "
        "déjà en herbe avant d'être déclarée.",
        "Il ne dit pas ce que devient une prairie sortie : c'est le satellite qui le regarde."]))
    cartes.append(carte("Les recommandations", "ce qui marche pour garder l'herbe", [
        "Ce sont des comparaisons (à terrain égal, avant et après une règle), pas des preuves de cause.",
        "« Environ 20 000 ha gardés » est une projection, pas une mesure.",
        "Nitrates et prairies évoluent ensemble ; le lien entre les deux n'est pas prouvé."]))
    grille(cartes)


# --- Preuves : ce qui fonde les chiffres de l'appli -------------------------------------------------
with preuves:
    if not pret:
        st.info(SANS_RESULTATS)
    else:
        # 1. La vérification par satellite : principe, exemples, contrôles ----------------------------
        with st.expander("1. Comment le satellite vérifie-t-il ce que deviennent les prairies ?"):
            from preuves_satellite import afficher as afficher_satellite
            afficher_satellite(an)

        # 2. Toute l'herbe de Normandie recomptée au satellite : comment -------------------------------
        with st.expander("2. Comment a-t-on recompté toute l'herbe de Normandie ?", expanded=bool(cible)):
            from herbe_hors_pac import afficher as afficher_herbe
            afficher_herbe(an)

        # 3. Les limites ----------------------------------------------------------------------------------
        with st.expander("3. Que ne sait pas l'outil ?"):
            limites()

# --- Sources : rangées par usage, en cartes -----------------------------------------------------------
with sources:
    def ligne_source(s):
        """Une source : nom en lien, producteur et date de la donnée installée."""
        if isinstance(s, tuple):
            nom, lien, qui = s
            return (f"<a href='{lien}' target='_blank'>{html.escape(nom)}</a><br>"
                    f"<span class='tq-meta'>{html.escape(qui)}</span>")
        d = SOURCES[s]
        lien = d.get("lien") or re.match(r"https?://\S+", d["page"]).group(0)
        date = derniere_date(s)
        date = "/".join(reversed(date[:10].split("-"))) if date else "date inconnue"
        return (f"<a href='{lien}' target='_blank'>{html.escape(NOMS_SOURCES.get(s, s.replace('_', ' ')))}</a>"
                f"<br><span class='tq-meta'>{html.escape(d['producteur'])} · téléchargée le {date}</span>")

    rangees = {s for _, _, liste in GROUPES_SOURCES for s in liste if isinstance(s, str)}
    # une source nouvelle reste visible tant qu'elle n'est pas rangée
    autres = [s for s in SOURCES if s not in rangees]
    groupes = GROUPES_SOURCES + ([("Autres", "pas encore rangées", autres)] if autres else [])
    from references import AGRICULTEUR_ACTIF, FIN_AUTORISATION_2019, OBJECTIF_REGIONAL, RATIOS
    textes = [(OBJECTIF_REGIONAL["texte"], OBJECTIF_REGIONAL["lien"], "l'objectif 2030")] + [
        (r["texte"], r["lien"], f"le ratio de prairies {r['annee']}") for r in RATIOS] + [
        ("Règlement délégué (UE) 2022/126, article 48", "https://eur-lex.europa.eu/eli/reg_del/2022/126/oj",
         "les seuils du ratio"),
        (AGRICULTEUR_ACTIF["texte"], AGRICULTEUR_ACTIF["lien"], "les sorties de 2023, agriculteur actif"),
        (FIN_AUTORISATION_2019["texte"], FIN_AUTORISATION_2019["lien"], "la fin de l'autorisation en 2019"),
        ("Directive (UE) 2020/2184", "https://eur-lex.europa.eu/eli/dir/2020/2184/oj",
         "la limite de 50 mg/L de nitrates")]
    def boite(titre, sous_titre, lignes):
        """Une grande boîte sur toute la largeur ; ses sources côte à côte, en colonnes."""
        return (f"<div class='tq-carte'><div class='tq-titre'>{titre}</div><div class='tq-sous'>{sous_titre}</div>"
                "<div class='tq-ligne'>" + "".join(f"<div class='tq-l'>{x}</div>" for x in lignes) + "</div></div>")

    st.html(STYLE + "<div class='tq-pile'>"
            + "".join(boite(t, f"Sert à : {u}", [ligne_source(s) for s in liste]) for t, u, liste in groupes)
            + boite("Les textes officiels", "Ce que disent les textes",
                    [f"<a href='{lien}' target='_blank'>{html.escape(t)}</a><br><span class='tq-meta'>"
                     f"{html.escape(objet)}</span>" for t, lien, objet in textes])
            + "</div>")
    st.caption("Toutes les données sont ouvertes (Licence Ouverte 2.0).")

# --- Glossaire : les mots de l'outil, par thème (aussi en bulle, au survol, dans toutes les pages) ------
with mots:
    st.caption("Ces mots ont aussi une bulle au survol, dans toutes les pages.")
    # le conteneur « glossaire_liste » : pas de bulle sur les mots de la liste elle-même
    with st.container(key="glossaire_liste"):
        # Un tableau : le mot à gauche, sa définition à droite, une ligne de titre par thème
        cel = "padding:.45rem .8rem;vertical-align:top;border-bottom:1px solid rgba(128,128,128,.18)"
        lignes = []
        for theme, liste in GLOSSAIRE.items():
            lignes.append(f"<tr><td colspan='2' style='padding:1.1rem .8rem .35rem;font-size:.78rem;opacity:.7;"
                          f"text-transform:uppercase;letter-spacing:.04em;font-weight:600;"
                          f"border-bottom:1px solid rgba(128,128,128,.45)'>{html.escape(theme)}</td></tr>")
            lignes += [f"<tr><td style='{cel};font-weight:700;white-space:nowrap;width:1%'>{html.escape(m)}</td>"
                       f"<td style='{cel}'>{html.escape(d[0].upper() + d[1:])}</td></tr>" for m, d, _ in liste]
        st.html("<table style='width:100%;max-width:980px;border-collapse:collapse;font-size:.95rem;"
                f"line-height:1.45'>{''.join(lignes)}</table>")

# --- Moteur : trois mises à jour, un bouton chacune ------------------------------------------------------
with moteur:
    import json
    import subprocess
    import sys
    import time

    import psutil

    from prairimetre import sentinel as sen
    from prairimetre.config import RACINE, SORTIES, annees

    DETACHE = ({"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
               if sys.platform == "win32" else {"start_new_session": True})
    F_MAJ, JOURNAL_MAJ = SORTIES / "mise_a_jour.json", SORTIES / "mise_a_jour.txt"

    def lancer_detache(args, journal):
        """Lance une commande du moteur qui continue même si on ferme l'appli ; renvoie son numéro."""
        proc = subprocess.Popen([sys.executable, "-X", "utf8", "-m", "prairimetre", *args], cwd=RACINE,
                                stdout=open(journal, "w", encoding="utf-8"), stderr=subprocess.STDOUT,
                                env={**__import__("os").environ, "PYTHONUNBUFFERED": "1"}, **DETACHE)
        return proc.pid

    def mise_a_jour_en_cours():
        if not F_MAJ.exists():
            return None
        a = json.loads(F_MAJ.read_text(encoding="utf-8"))
        return a if psutil.pid_exists(a["pid"]) else None

    def lancer_mise_a_jour(args, quoi):
        pid = lancer_detache(args, JOURNAL_MAJ)
        F_MAJ.write_text(json.dumps({"pid": pid, "debut": time.time(), "quoi": quoi}), encoding="utf-8")
        st.toast("Mise à jour lancée.")
        st.rerun()

    @st.cache_data(ttl=6 * 3600, show_spinner=False)
    def publies():
        """Millésimes du registre publiés par l'IGN (vérifié au plus toutes les 6 heures)."""
        from prairimetre.telecharger import annees_publiees
        try:
            return annees_publiees()
        except Exception:
            return None

    @st.cache_data(ttl=6 * 3600, show_spinner=False)
    def agreste_publie():
        """Dernières séries longues publiées par Agreste : (dernière année, provisoire ?), ou None."""
        if str(RACINE) not in sys.path:
            sys.path.insert(0, str(RACINE))
        try:
            import importer_donnees
            m = re.search(r"(\d{4})-(\d{4})_Donnees(\w+?)-", importer_donnees.archive_agreste())
            return (int(m.group(2)), m.group(3).lower().startswith("provisoire")) if m else None
        except Exception:
            return None

    st.markdown("Le moteur refait tous les chiffres de l'appli à partir de trois sources ouvertes, chacune "
                "mise à jour d'un bouton. Un calcul continue même si l'on ferme l'appli ; un seul à la fois.")

    @st.fragment(run_every="20s")
    def suivi():
        """Le calcul en cours, s'il y en a un : son avancement, sur toute la largeur."""
        a, s = mise_a_jour_en_cours(), sen.avancement()
        if a:
            lignes = JOURNAL_MAJ.read_text(encoding="utf-8", errors="replace").strip().splitlines()
            st.info(f"{a.get('quoi', 'Mise à jour')} en cours depuis "
                    f"{nombre((time.time() - a['debut']) / 60)} min. Dernière étape :")
            st.code("\n".join(lignes[-6:]) or "démarrage…", language=None)
        if s:
            reste = max(s["total"] - s["faits"], 0)
            st.progress(min(s["faits"] / max(s["total"], 1), 1.0),
                        text=f"Images satellite : {nombre(s['faits'])} parcelles sur {nombre(s['total'])}, "
                             f"fin dans environ {nombre(reste * sen.SECONDES_PAR_PARCELLE / 3600, 1)} h.")
        return bool(a or s)

    occupe = suivi()
    c1, c2, c3 = st.columns(3)

    # 1. Le registre PAC : chaque année, un nouveau millésime (IGN) ----------------------------------
    with c1.container(border=True, height="stretch"):
        st.markdown("##### :material/agriculture: Registre PAC",
                    help="Les parcelles déclarées à la PAC (IGN), une carte par année : le compteur des "
                         "prairies, commune par commune.")
        A, pub = annees(), publies()
        nouveau = max(pub) if pub and A and max(pub) > A[-1] else None
        st.markdown(f"Installé : **{A[0]}→{A[-1]}**  \n"
                    + (f"**Le registre {nouveau} est publié.**" if nouveau else
                       "À jour." if pub else "Publications de l'IGN injoignables."))
        if st.button(f"Installer {nouveau} et recalculer" if nouveau else "Recalculer",
                     type="primary" if nouveau else "secondary", key="registre", disabled=occupe, width="stretch",
                     help="Télécharge le nouveau registre, le contrôle, recalcule toutes les tables et les "
                          "preuves (environ 1 h). Ensuite, lancer les images satellite de la nouvelle année."):
            lancer_mise_a_jour(["mettre-a-jour"] if nouveau else ["recalculer"],
                               f"Registre {nouveau}" if nouveau else "Recalcul")

    # 2. La statistique agricole (Agreste) : la mesure officielle de l'objectif ----------------------
    with c2.container(border=True, height="stretch"):
        st.markdown("##### :material/query_stats: Statistique agricole",
                    help="Les séries longues de la statistique agricole annuelle (Agreste) : l'herbe et la "
                         "surface agricole de la région, la mesure officielle de l'objectif 2030.")
        from prairimetre.donnees import saa_region
        serie = saa_region()
        installe = int(serie.index.max()) if len(serie) else None
        p = agreste_publie()
        nouvelle = p is not None and installe is not None and p[0] > installe
        st.markdown((f"Installée : **jusqu'à {installe}**" if installe else "Pas encore installée.") + "  \n"
                    + (f"**Les séries {p[0]} sont publiées.**" if nouvelle else
                       f"À jour (dernière année {'provisoire' if p[1] else 'définitive'})." if p else
                       "Site d'Agreste injoignable."))
        if st.button(f"Installer {p[0]} et recalculer" if nouvelle else "Retélécharger et recalculer",
                     type="primary" if nouvelle else "secondary", key="agreste", disabled=occupe,
                     width="stretch",
                     help="Télécharge les dernières séries d'Agreste (les chiffres provisoires deviennent "
                          "définitifs l'année suivante), puis recalcule tout (environ 1 h)."):
            lancer_mise_a_jour(["agreste"], "Statistique agricole")

    # 3. Les images satellite : les prairies sorties de la déclaration, une fois pour toutes ----------
    with c3.container(border=True, height="stretch"):
        st.markdown("##### :material/satellite_alt: Images satellite",
                    help="Chaque prairie sortie de la déclaration (sa part sortie, dès 0,25 ha) est regardée sur toutes les "
                         "images Sentinel-2 sans nuage de la dernière année du registre : restée verte, ou "
                         "labourée. Les résultats sont rangés dans verification/sentinel2/<année>/ et l'appli "
                         "ne fait que les lire : une parcelle déjà mesurée n'est jamais redemandée.")
        r = sen.resume_mesures()
        complet = r is not None and r["parcelles"] >= r["cible_parcelles"]
        st.markdown(f"Images **{sen.periode()[1]}** : "
                    + (f"{nombre(r['parcelles'])} prairies sorties mesurées sur {nombre(r['cible_parcelles'])}."
                       if r else "aucune prairie sortie mesurée.") + "  \n"
                    + ("Toutes sont mesurées." if complet else "Des prairies restent à mesurer."))
        if st.button("Mesurer les prairies restantes", key="sat_lancer", disabled=occupe or complet,
                     width="stretch",
                     help="Mesure les prairies sorties pas encore mesurées pour la dernière année du registre "
                          "(environ 15 h la première fois, puis seulement les nouvelles)."):
            lancer_detache(["satellite"], sen.DOSSIER / "journal.txt")
            st.toast("Mesure lancée.")
            st.rerun()
