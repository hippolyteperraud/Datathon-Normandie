# Prairimètre — Datathon Normandie 2026

Le suivi des prairies permanentes de Normandie : combien on en perd vraiment, pourquoi, ce qui les
retient et où agir. Hippolyte Perraud (INSA Rouen) et Mouhssine Bairoune (ENSI Caen).

**Le rapport** : [docs/rapport/rapport_prairimetre.pdf](docs/rapport/rapport_prairimetre.pdf)
(cartes, chiffres, méthode, limites). Il se régénère à partir des résultats :
`python scripts/rapport.py`.

## La problématique

La Région s'est fixé **zéro perte nette de prairies permanentes en 2030** (Stratégie régionale pour
la biodiversité, objectif III.5 : « maintenir autant de prairies permanentes entre 2021 et 2030 »,
cible « 39 % de la Surface Agricole Utile, Agreste »). Sujet 2 du datathon : comprendre les
interactions humain-nature pour mieux décider. Trois questions :

1. **Combien perd-on vraiment ?** La statistique agricole (la mesure officielle) et le registre PAC
   ne disent pas la même chose ; l'écart vient surtout des exploitants âgés sortis de la PAC en 2023,
   dont les prairies restent vertes, vu du satellite.
2. **Les règles retiennent-elles les prairies ?** Là où une règle encadre le labour, on retourne
   environ 5 fois moins, mais ces règles ne couvrent que 14 % des prairies.
3. **Où agir ?** Une liste courte de communes où le retournement se concentre, les communes où aller
   vérifier les prairies sorties de la déclaration (et ce que le satellite y voit déjà), les
   communes exemples.

Une seule méthode : les prairies déclarées une année sont croisées, parcelle par parcelle, avec les
déclarations suivantes, en Normandie seulement. Toutes les données sont ouvertes.

## L'application

```
pip install -r requirements.txt
python -m streamlit run app/accueil.py      # puis http://localhost:8501 (local uniquement)
```

| Onglet | Question |
|---|---|
| Objectif 2030 | Où en est l'objectif, selon la statistique agricole et selon le registre ? Pourquoi le registre perd plus (2019, 2023, sources officielles) ? Ce qui retient les prairies, ce qu'on ne sait pas |
| Ma commune | Ce que sont devenues les prairies d'une commune, parcelle par parcelle |
| Où aller voir | Les communes qui portent la moitié des sorties de la déclaration, et ce que le satellite y voit |
| Prendre exemple | Les communes qui gagnent des prairies sur d'anciennes cultures, et celles qui n'en perdent pas |
| Technique | Preuves, sources, mots, recalcul |

L'appli lit les tables de `sorties/` et de `verification/sentinel2/` ; aucun chiffre de résultat
n'est écrit à la main. Les chiffres officiels cités sont dans `app/references.py`, avec leur source.
Après une modification de `app/commun.py`, `app/humain.py` ou `app/references.py`, relancer le
serveur.

## Les données et le moteur

```
python importer_donnees.py --liste           # les sources : quoi, qui, vers où
python importer_donnees.py --puis-calculer   # tout récupérer (environ 6,5 Go), puis calculer
python -m prairimetre etat                   # ce qui est en local, ce qui est publié
python -m prairimetre mettre-a-jour          # nouveau registre : télécharger, contrôler, recalculer
python -m prairimetre calculer               # tables de résultats -> sorties/
python -m prairimetre evaluer                # preuves : zonages, robustesse, statistique agricole…
```

Le guide pas à pas pour tout installer : [TESTER_APPLICATION.md](TESTER_APPLICATION.md).

| Module | Rôle |
|---|---|
| `prairimetre/config.py` | Réglages : région (`REGION`), départements, emprise, objectif 2030 (référence 2021) |
| `prairimetre/sources.py`, `telecharger.py`, `importer.py`, `controles.py` | Catalogue des sources, téléchargement, import manuel, contrôles |
| `prairimetre/donnees.py`, `suivi.py` | Lecture des données ; croisement des parcelles d'une année à l'autre |
| `prairimetre/indicateurs.py` | Tables de résultats : communes, objectif 2030, suivi des sorties de la déclaration |
| `prairimetre/evaluation.py` | Preuves : effet des zonages, robustesse, concentration, statistique agricole |
| `prairimetre/sentinel.py` | Vérification par images Sentinel-2 |

Changer de région : les réglages de `config.py` (code de la région, départements, emprise).

## La vision satellite

```
python scripts/analyser_satellite_sentinel.py --sentinel   # échantillons et témoins (environ 15 min)
```

Images Sentinel-2 (Copernicus), lues sans compte via le catalogue public de Microsoft Planetary
Computer : pour chaque parcelle, le NDVI de chaque image sans nuage de l'année. La règle (prairie
restée verte ou parcelle labourée) est validée sur des parcelles dont le registre donne la réponse.
Preuves parcelle par parcelle, avec un lien vers la photo aérienne IGN :
[verification/sentinel2/preuves.md](verification/sentinel2/preuves.md). Étude de faisabilité :
[verification/etude_faisabilite_satellite.md](verification/etude_faisabilite_satellite.md).

## Tests

```
python -m unittest discover tests
```

## Dossiers

| Dossier | Contenu |
|---|---|
| `app/`, `prairimetre/` | Application et moteur (exclus par `.gitignore` : ajouter un nouveau fichier avec `git add -f`) |
| `scripts/` | Rapport, vérification satellite |
| `tests/` | Tests automatisés |
| `verification/` | Résultats et preuves de la vérification satellite |
| `docs/` | Rapport, audit du code, documents de travail |
| `Consignes/` | Documents des organisateurs |
| `data/`, `cache/`, `sorties/` | Données (environ 6,5 Go), fichiers intermédiaires, résultats : non suivis par git |

Licence : voir [LICENSE](LICENSE).
