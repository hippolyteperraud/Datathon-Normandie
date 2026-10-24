# Prairimètre — Datathon Normandie 2026

Outil de pilotage annuel du « zéro perte nette » de prairies permanentes en Normandie.
Problématique : [docs/02_problématique.pdf](docs/02_problématique.pdf).

## Fil rouge et périmètre

> Mesurer chaque année, parcelle par parcelle, où les prairies disparaissent et si les
> protections les retiennent, pour dire à chaque acteur où agir.

Trois questions, pas une de plus :

1. **Combien perd-on, et pourquoi l'alerte ne sonne plus ?** → page Synthèse
2. **Les protections retiennent-elles les prairies ?** (interaction humain-nature, sujet 2) → Synthèse, preuves dans Données et méthode
3. **Où agir, et avec qui ?** → Prairies : où agir, Eau potable, Ma commune

**Règle** : une donnée, un calcul ou un écran qui ne répond à aucune des trois questions sort
du projet. Les données écartées sont rangées dans `data/_hors_perimetre/` (déplacées, pas
supprimées). Hors périmètre volontaire : la prédiction, l'échelle de l'exploitation, les haies,
le détail de l'artificialisation.

L'application tourne **uniquement en local** : le serveur n'écoute que sur cette machine
(`localhost`, voir `.streamlit/config.toml`). Internet ne sert qu'au fond de carte et au
téléchargement des nouvelles données.

## Installation

```
pip install -r requirements.txt
```

## Ajouter des données (depuis la racine du projet)

Trois cas, trois commandes. Tout est aussi faisable sans terminal, dans l'appli :
« Données et méthode » → onglet « Moteur ».

| Cas | Commande |
|---|---|
| Savoir où on en est | `python -m prairimetre etat` |
| Un nouveau RPG est sorti | `python -m prairimetre mettre-a-jour` (trouve seul la dernière année, télécharge, contrôle, recalcule) |
| Une source à télécharger à la main (communes, OCS GE, Cerema, LUCAS, zones humides, ZNIEFF 1) | `python -m prairimetre importer <source> <fichier>` puis `python -m prairimetre calculer` |

`importer` accepte le fichier tel que téléchargé : GeoPackage, Shapefile, GeoJSON, CSV, ou
l'archive .zip / .7z (le bon fichier y est cherché). Il met au format (colonnes, Lambert-93),
garde la Normandie, vérifie les colonnes attendues, trace l'import dans `data/manifest.json` et
vide le cache concerné. **Rien n'est remplacé si une vérification échoue.** Exemples :

```
python -m prairimetre importer communes ADMIN-EXPRESS-COG_2027.7z
python -m prairimetre importer ocsge OCS-GE_14_2026.gpkg --dep 14 --millesime 2026
python -m prairimetre importer conso_enaf conso_espaces_2011_2026.csv
python -m prairimetre importer rpg RPG_R28_2026.7z --annee 2026   # si le service IGN est en panne
```

Autres commandes : `telecharger zonages` (rafraîchir tous les zonages WFS), `controler`,
`calculer`, `evaluer [--rapide]`. Une nouvelle année ne recalcule que ce qui la concerne.

## L'application (`app/`)

```
python -m streamlit run app/accueil.py   # puis ouvrir http://localhost:8501
```

| Page | Question | Pour qui |
|---|---|---|
| Synthèse | Où en est-on ? Quelles décisions ? | Région, jury |
| Prairies : où agir | Quelles communes cibler, pour quel levier (retournement ou sortie de la PAC) ? | Région, chambre d'agriculture, DDT(M), SAFER |
| Eau potable | Quelles aires de captage perdent leurs prairies, et qui alerter ? | Agence de l'eau, syndicats d'eau, DDT(M) |
| Ma commune | Qu'a perdu la commune, comment, que faire et avec qui ? | Élus, EPCI |
| Données et méthode | Preuves, sources et données manquantes, lancement du moteur | Jury, experts, équipe |

L'appli lit les tables de `sorties/` et appelle le moteur de deux façons : en l'important
(`flux_commune`, `parcelles_commune`) et en lançant ses commandes (`python -m prairimetre ...`).
Pour ajouter une page : un fichier dans `app/vues/`, une ligne dans `app/accueil.py`.
Données manquantes : jamais de case vide, toujours la raison (voir `app/commun.py`).
Illustration, chiffres à taille humaine et signature : `app/humain.py`. Thème : `.streamlit/config.toml`.
Après une modification de `app/commun.py` ou `app/humain.py`, relancer le serveur.

## Le moteur (`prairimetre/`)

| Module | Rôle |
|---|---|
| `sources.py` | Catalogue : où se trouve chaque source, où elle va dans `data/`, colonnes attendues |
| `telecharger.py` | Téléchargement, extraction, manifest (empreinte SHA-256), invalidation du cache |
| `importer.py` | Import d'un fichier téléchargé à la main, pour n'importe quelle source |
| `controles.py` | Contrôles de cohérence (valables pour une nouvelle année) et valeurs de référence |
| `donnees.py` | Lecture des données avec cache GeoParquet |
| `suivi.py` | Croisement des géométries d'une année à l'autre : devenir et origine de chaque prairie |
| `indicateurs.py` | Compteur et boussole : tables par commune, EPCI, département, PNR, aire de captage |
| `evaluation.py` | Efficacité associée des zonages, concentration, test de prédiction, certitude |

## Dossiers

| Dossier | Contenu | Suivi par git |
|---|---|---|
| `prairimetre/` | Moteur de calcul (Python) | oui |
| `app/` | Application Streamlit | oui |
| `docs/` | Problématique, documentation des données | oui |
| `consignes/` | Documents des organisateurs | oui |
| `data/` | Données lues par le moteur (environ 6 Go, voir `data/manifest.json`) | non |
| `data/_hors_perimetre/` | Données écartées, gardées au cas où (4,2 Go) | non |
| `cache/` | Fichiers intermédiaires, régénérables | non |
| `sorties/` | Tables de résultats (CSV) | non |
