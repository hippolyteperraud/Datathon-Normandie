# Importer les données (prairies)
python importer_donnees.py --liste            # les 24 sources : quoi, qui, vers où
python importer_donnees.py --puis-calculer    # tout récupérer (≈ 6,7 Go), puis recalculer
python importer_donnees.py --seulement lucas  # une seule source

********************************************

# Prairimètre — Datathon Normandie 2026

Documents : problématique et réponses [docs/03_problematique_et_reponses.pdf](docs/03_problematique_et_reponses.pdf),
données [docs/donnees_projet.pdf](docs/donnees_projet.pdf), état de l'art [docs/etat_de_l_art.md](docs/etat_de_l_art.md),
guide [docs/guide_utilisation.md](docs/guide_utilisation.md), descriptif
[docs/Descriptif_projet_Prairimetre.docx](docs/Descriptif_projet_Prairimetre.docx), questions aux
experts [docs/questions_experts.md](docs/questions_experts.md), avancement
[docs/compte_rendu_avancement.md](docs/compte_rendu_avancement.md) et suivi des corrections
[docs/suivi_corrections.md](docs/suivi_corrections.md).

Outil de pilotage annuel du « zéro perte nette » de prairies permanentes en Normandie.
Règle de l'application : une donnée n'est affichée que si elle change une décision.

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

## Récupérer toutes les données (un seul fichier)

```
python importer_donnees.py --liste            # les 24 sources utilisées : quoi, qui, vers où
python importer_donnees.py --puis-calculer    # tout télécharger (≈ 6,7 Go), puis recalculer
```

Chaque source est cherchée à sa source officielle (service de téléchargement de l'IGN, API de
data.gouv.fr, Eurostat), recadrée sur la Normandie, vérifiée et tracée dans `data/manifest.json`.

## Ajouter des données (depuis la racine du projet)

Trois cas, trois commandes. Tout est aussi faisable sans terminal, dans l'appli :
« Données et méthode » → onglet « Moteur ».

| Cas | Commande |
|---|---|
| Savoir où on en est | `python -m prairimetre etat` |
| Un nouveau RPG est sorti | `python -m prairimetre mettre-a-jour` (trouve seul la dernière année, télécharge, contrôle, recalcule ; environ 1 h). `--avec-officielle` ajoute la couche officielle des prairies (contrôle seulement, service très lent : ~6 h) |
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
| Synthèse | Trois décisions, chacune avec le chiffre qui la fonde et qui la prend : piloter 2030 en hectares, financer la prairie ordinaire, concentrer l'effort | Région, jury |
| Prairies : où agir | Où financer le maintien (critère : hectares, taux, zonages d'enjeux), où vérifier d'abord, où trouver des exemples ; communes ou intercommunalités | Région, chambre d'agriculture, DDT(M), PNR |
| Eau potable | Quelles aires de captage perdent leurs prairies, et qui alerter ? | Agence de l'eau, syndicats d'eau, DDT(M) |
| Ma commune | Qu'a perdu la commune, comment, que faire et avec qui ? | Élus, EPCI, habitants |
| Données et méthode | Preuves, définitions, sources et données manquantes, lexique, moteur | Jury, experts, équipe |

Barre latérale : lexique, et interrupteur du fond de
carte (à couper sans internet : les cartes restent lisibles).

L'appli lit les tables de `sorties/` (relues dès que le moteur les recalcule) et appelle le
moteur de deux façons : en l'important (`parcelles_commune`) et en lançant ses commandes
(`python -m prairimetre ...`).
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
| `indicateurs.py` | Compteur et boussole : comparaison directe début → fin, en Normandie seulement ; tables par commune et par aire de captage, objectif 2030, cultures de remplacement |
| `evaluation.py` | Zonages par famille (règle, site, inventaire), concentration, prédiction, sensibilité aux seuils, certitude (OCS GE, LUCAS), statistique agricole annuelle, habitats prairiaux, maïs |

Tests : `python -m unittest discover tests` (petites données inventées, moins d'une seconde).

Paquet de remise, en local (rien n'est envoyé) : `python -m prairimetre livrer` écrit
`livraison/prairimetre_<date>.zip` (code, résultats, manifest, documents ; `--avec-donnees`
pour joindre `data/`). La durée de chaque calcul et le volume des données sont tracés dans
`sorties/sobriete.csv`.

Réglages (`prairimetre/config.py`) : seuil de 20 ha par commune, période récente de 3 ans,
année de référence de l'objectif 2030 (2022, à confirmer avec la Région).

## Dossiers

| Dossier | Contenu | Suivi par git |
|---|---|---|
| `importer_donnees.py` | Récupère toutes les données utilisées, en une commande | non commité |
| `prairimetre/` | Moteur de calcul (Python) | non (exclu dans `.gitignore`) |
| `app/` | Application Streamlit | non (exclu dans `.gitignore`) |
| `tests/` | Tests automatisés du moteur | non commité |
| `livraison/` | Paquet de remise (zip), créé à la demande par `livrer` | non commité |
| `docs/` | Problématique et réponses, données, guide, état de l'art, descriptif, suivi | en partie |
| `consignes/` | Documents des organisateurs | oui |
| `data/` | Données lues par le moteur (environ 6 Go, voir `data/manifest.json`) | non |
| `data/_hors_perimetre/` | Données écartées, gardées au cas où (3,8 Go) | non |
| `cache/` | Fichiers intermédiaires, régénérables | non |
| `sorties/` | Tables de résultats (CSV) | non |
