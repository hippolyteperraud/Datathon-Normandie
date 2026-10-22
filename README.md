# Datathon Normandie 2026 — Prairies permanentes

Outil de pilotage annuel du « zéro perte nette » de prairies permanentes en Normandie.
Problématique : [docs/02_problématique.pdf](docs/02_problématique.pdf).

## Dossiers

| Dossier | Contenu | Suivi par git |
|---|---|---|
| `src/` | Code Python | oui |
| `docs/` | Problématique, documentation des données | oui |
| `consignes/` | Documents des organisateurs | oui |
| `data/` | Données brutes (10,7 Go, voir `data/manifest.json`) | non |
| `cache/` | Fichiers intermédiaires, régénérables | non |
| `sorties/` | Tables de résultats (CSV) | non |

## Lancer (depuis la racine du projet)

```
python src/charger.py      # contrôles des données (OK / ECART), crée le cache
python src/devenir.py      # devenir des prairies d'une année à l'autre
python src/indicateur.py   # indicateur communal et test de prédiction
python src/diagnostic.py   # zonages, concentration, typologie, certitude
```

Prérequis : Python 3.11+, geopandas >= 1.0, pyogrio, pyarrow, shapely 2.
