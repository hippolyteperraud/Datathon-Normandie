"""Explore les mesures de nitrates des cours d'eau normands via l'API Hubeau.

Depuis la racine du dépôt :
    python scripts/analyser_nitrates.py

Les données téléchargées et les tableaux produits restent dans data/ (ignoré par Git).
"""
import argparse
import csv
import json
import statistics
import time
from collections import defaultdict
from datetime import date
from http.client import HTTPException
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

RACINE = Path(__file__).resolve().parents[1]
STATIONS = RACINE / "data/raw/qualite_eau_hubeau/stations_normandie.csv"
SORTIES = RACINE / "data/processed/qualite_eau"
API = "https://hubeau.eaufrance.fr/api/v2/qualite_rivieres/analyse_pc"
DEPARTEMENTS = {"14", "27", "50", "61", "76"}
TAILLE_PAGE = 5_000
UNITE_NITRATES = "173"

CHAMPS_MESURE = [
    "code_station", "libelle_station", "code_departement", "libelle_departement",
    "date_prelevement", "resultat", "symbole_unite", "code_fraction",
    "libelle_fraction", "code_qualification", "libelle_qualification",
    "code_statut", "mnemo_statut",
]


def charger_stations(chemin=STATIONS):
    """Indexe les stations de la région à partir du CSV local Hubeau."""
    if not chemin.exists():
        raise FileNotFoundError(
            f"Fichier absent : {chemin}. Lancez d'abord scripts/recuperer_hubeau.py."
        )
    with chemin.open(encoding="utf-8-sig", newline="") as fichier:
        lecteur = csv.DictReader(fichier)
        requis = {"code_station", "code_departement", "libelle_departement"}
        if not lecteur.fieldnames or not requis.issubset(lecteur.fieldnames):
            raise ValueError(
                f"Colonnes manquantes dans {chemin.name} : {sorted(requis)}"
            )
        return {
            ligne["code_station"]: ligne
            for ligne in lecteur
            if ligne["code_departement"] in DEPARTEMENTS
        }


def telecharger_mesures(debut, fin):
    """Récupère les résultats année par année pour respecter la limite Hubeau."""
    mesures = []
    total_attendu = 0

    for annee in range(debut, fin + 1):
        params = {
            "code_region": "28",
            "code_parametre": "1340",
            "code_support": "3",
            "code_fraction": "3",
            "code_qualification": "1",
            "code_statut": "3",
            "date_debut_prelevement": f"{annee}-01-01",
            "date_fin_prelevement": f"{annee}-12-31",
            "size": str(TAILLE_PAGE),
            "format": "json",
        }
        url = f"{API}?{urlencode(params)}"
        total_annee = None
        recues_annee = 0

        while url:
            if urlparse(url).netloc != urlparse(API).netloc:
                raise ValueError(f"Adresse de pagination Hubeau inattendue : {url}")
            requete = Request(url, headers={"User-Agent": "Normandie-eau/1.0"})
            for essai in range(3):
                try:
                    with urlopen(requete, timeout=90) as reponse:
                        page = json.load(reponse)
                    break
                except (HTTPException, OSError, URLError) as erreur:
                    if essai == 2:
                        raise RuntimeError(f"Échec de la requête Hubeau : {erreur}") from erreur
                    time.sleep(2 ** essai)

            if total_annee is None:
                total_annee = int(page["count"])
            mesures.extend(page["data"])
            recues_annee += len(page["data"])
            print(f"\r{annee} : {recues_annee:,} / {total_annee:,}", end="", flush=True)
            url = page.get("next")

        print()
        if recues_annee != total_annee:
            raise RuntimeError(
                f"Téléchargement incomplet pour {annee} : "
                f"{recues_annee} mesures reçues sur {total_annee}."
            )
        total_attendu += total_annee

    if len(mesures) != total_attendu:
        raise RuntimeError(
            f"Téléchargement incomplet : {len(mesures)} mesures reçues sur {total_attendu}."
        )
    return mesures


def analyser(mesures, stations, debut, fin, duree_fenetre=3):
    """Construit des résumés annuels et compare les mêmes stations entre deux périodes."""
    if duree_fenetre < 1 or fin - debut + 1 < 2 * duree_fenetre:
        raise ValueError("Il faut deux fenêtres temporelles distinctes et complètes.")
    par_station_annee = defaultdict(list)
    mesures_retenues = []

    for mesure in mesures:
        if (
            str(mesure.get("code_support")) != "3"
            or str(mesure.get("code_fraction")) != "3"
            or str(mesure.get("code_qualification")) != "1"
            or str(mesure.get("code_statut")) != "3"
            or str(mesure.get("code_unite")) != UNITE_NITRATES
        ):
            continue

        code = str(mesure.get("code_station", ""))
        station = stations.get(code)
        if station is None:
            continue
        try:
            valeur = float(mesure["resultat"])
            annee = int(str(mesure["date_prelevement"])[:4])
        except (KeyError, TypeError, ValueError):
            continue
        if not debut <= annee <= fin:
            continue

        mesures_retenues.append({
            "code_station": code,
            "libelle_station": mesure.get("libelle_station", ""),
            "code_departement": station["code_departement"],
            "libelle_departement": station["libelle_departement"],
            "date_prelevement": mesure["date_prelevement"],
            "resultat": valeur,
            "symbole_unite": mesure.get("symbole_unite", ""),
            "code_fraction": mesure["code_fraction"],
            "libelle_fraction": mesure.get("libelle_fraction", ""),
            "code_qualification": mesure["code_qualification"],
            "libelle_qualification": mesure.get("libelle_qualification", ""),
            "code_statut": mesure["code_statut"],
            "mnemo_statut": mesure.get("mnemo_statut", ""),
        })
        par_station_annee[(code, annee)].append(valeur)

    valeurs_annuelles = {
        cle: statistics.median(valeurs)
        for cle, valeurs in par_station_annee.items()
    }
    par_annee = defaultdict(list)
    par_departement_annee = defaultdict(list)
    analyses_par_annee = defaultdict(int)
    analyses_par_departement_annee = defaultdict(int)
    noms_departements = {}
    for (code, annee), mediane in valeurs_annuelles.items():
        station = stations[code]
        departement = station["code_departement"]
        par_annee[annee].append(mediane)
        par_departement_annee[(departement, annee)].append(mediane)
        analyses_par_annee[annee] += len(par_station_annee[(code, annee)])
        analyses_par_departement_annee[(departement, annee)] += len(
            par_station_annee[(code, annee)]
        )
        noms_departements[departement] = station["libelle_departement"]

    resume_annuel = [
        {
            "annee": annee,
            "stations": len(valeurs),
            "analyses": analyses_par_annee[annee],
            "mediane_des_medianes_station_mg_l": statistics.median(valeurs),
        }
        for annee, valeurs in sorted(par_annee.items())
    ]

    resume_departement = []
    for (departement, annee), valeurs in sorted(par_departement_annee.items()):
        resume_departement.append({
            "code_departement": departement,
            "departement": noms_departements[departement],
            "annee": annee,
            "stations": len(valeurs),
            "analyses": analyses_par_departement_annee[(departement, annee)],
            "mediane_des_medianes_station_mg_l": statistics.median(valeurs),
        })

    fenetre_debut = range(debut, min(debut + duree_fenetre, fin + 1))
    fenetre_fin = range(max(fin - duree_fenetre + 1, debut), fin + 1)
    tendances = []
    for code, station in stations.items():
        premiere = [
            valeurs_annuelles[(code, annee)]
            for annee in fenetre_debut
            if (code, annee) in valeurs_annuelles
        ]
        derniere = [
            valeurs_annuelles[(code, annee)]
            for annee in fenetre_fin
            if (code, annee) in valeurs_annuelles
        ]
        if len(premiere) < 2 or len(derniere) < 2:
            continue
        mediane_debut = statistics.median(premiere)
        mediane_fin = statistics.median(derniere)
        tendances.append({
            "code_station": code,
            "station": station.get("libelle_station", ""),
            "code_departement": station["code_departement"],
            "departement": station["libelle_departement"],
            "annees_observees_debut": len(premiere),
            "annees_observees_fin": len(derniere),
            "mediane_debut_mg_l": mediane_debut,
            "mediane_fin_mg_l": mediane_fin,
            "variation_mg_l": mediane_fin - mediane_debut,
        })

    variations = [ligne["variation_mg_l"] for ligne in tendances]
    resume_tendance = [{
        "periode_debut": f"{min(fenetre_debut)}-{max(fenetre_debut)}",
        "periode_fin": f"{min(fenetre_fin)}-{max(fenetre_fin)}",
        "stations_comparables": len(tendances),
        "variation_mediane_mg_l": statistics.median(variations) if variations else None,
        "stations_en_hausse": sum(v > 0 for v in variations),
        "stations_en_baisse": sum(v < 0 for v in variations),
        "stations_stables": sum(v == 0 for v in variations),
    }]
    return mesures_retenues, resume_annuel, resume_departement, tendances, resume_tendance


def ecrire_csv(chemin, lignes, champs):
    """Écrit un CSV lisible dans un tableur, avec remplacement atomique."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_suffix(chemin.suffix + ".tmp")
    with temporaire.open("w", encoding="utf-8-sig", newline="") as fichier:
        redacteur = csv.DictWriter(fichier, fieldnames=champs, delimiter=";")
        redacteur.writeheader()
        redacteur.writerows(lignes)
    temporaire.replace(chemin)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depuis", type=int, default=2015, help="première année complète")
    parser.add_argument("--jusqua", type=int, default=date.today().year - 1,
                        help="dernière année complète (par défaut : année précédente)")
    args = parser.parse_args()
    if args.jusqua - args.depuis + 1 < 6 or args.depuis < 1900:
        parser.error("Il faut au moins six années, deux fenêtres distinctes de trois ans.")

    stations = charger_stations()
    mesures = telecharger_mesures(args.depuis, args.jusqua)
    resultats = analyser(mesures, stations, args.depuis, args.jusqua)
    mesures, annuel, departement, tendances, resume = resultats
    if not mesures:
        raise RuntimeError("Aucune mesure exploitable après les filtres de qualité et de périmètre.")

    brutes = RACINE / "data/raw/qualite_eau_hubeau"
    ecrire_csv(brutes / f"nitrates_{args.depuis}_{args.jusqua}.csv", mesures, CHAMPS_MESURE)
    ecrire_csv(SORTIES / "nitrates_par_annee.csv", annuel, list(annuel[0]))
    ecrire_csv(SORTIES / "nitrates_par_departement.csv", departement,
               list(departement[0]) if departement else [])
    ecrire_csv(SORTIES / "tendance_stations_nitrates.csv", tendances,
               list(tendances[0]) if tendances else [
                   "code_station", "station", "code_departement", "departement",
                   "annees_observees_debut", "annees_observees_fin",
                   "mediane_debut_mg_l", "mediane_fin_mg_l", "variation_mg_l",
               ])
    ecrire_csv(SORTIES / "synthese_tendance_nitrates.csv", resume, list(resume[0]))

    print(f"\n{len(mesures):,} mesures de nitrates retenues.")
    print(f"{len({ligne['code_station'] for ligne in mesures}):,} stations avec mesure.")
    print(f"Résultats : {SORTIES.relative_to(RACINE)}")
    print(f"Fichier de mesures : {brutes.relative_to(RACINE)}")


if __name__ == "__main__":
    main()
