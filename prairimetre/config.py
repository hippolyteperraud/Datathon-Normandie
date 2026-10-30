"""Réglages du moteur : chemins, territoire, seuils."""
import os
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
# Dossiers réglables (ex. tester un import complet sans toucher aux données en place)
DATA = Path(os.environ.get("PRAIRIMETRE_DATA", RACINE / "data"))
CACHE = Path(os.environ.get("PRAIRIMETRE_CACHE", RACINE / "cache"))
SORTIES = Path(os.environ.get("PRAIRIMETRE_SORTIES", RACINE / "sorties"))
MANIFEST = DATA / "manifest.json"

REGION = "R28"                       # code de la Normandie dans les archives IGN
DEPARTEMENTS = ["14", "27", "50", "61", "76"]
BBOX = (330000, 6740000, 620000, 7000000)  # emprise Lambert-93 de la Normandie, avec marge
ANNEE_DEBUT = 2018                   # premier millésime suivi

MIN_HA = 20        # en dessous, un taux communal n'a pas de sens (sensibilité testée : 10, 20, 50)
SEUIL_ECLAT = 0.1  # part de parcelle en dessous de laquelle un changement est du bruit géométrique
RECENT = 3         # « récent » = les 3 derniers millésimes (sensibilité testée : 2, 3, 4)

# Objectif régional : zéro perte nette de prairies permanentes en 2030 (stratégie régionale
# biodiversité, objectif III.5). Année de référence retenue : 2022, année d'adoption de la
# stratégie. À CONFIRMER avec la Région ; changer ici suffit.
ANNEE_REFERENCE_OBJECTIF = 2022
ANNEE_OBJECTIF = 2030


def annees():
    """Millésimes RPG présents en local, du plus ancien au plus récent."""
    trouve = (re.fullmatch(r"rpg_(\d{4})\.gpkg", f.name) for f in (DATA / "rpg").glob("rpg_*.gpkg"))
    return sorted(int(m.group(1)) for m in trouve if m and int(m.group(1)) >= ANNEE_DEBUT)


for _d in (CACHE, SORTIES):
    _d.mkdir(parents=True, exist_ok=True)
