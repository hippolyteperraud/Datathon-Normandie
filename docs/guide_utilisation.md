# Prairimètre — Guide Exhaustif d'Installation, du Moteur, des Tests et de l'Application

Ce document constitue le manuel de référence complet de la branche **`satellite-vision`** du projet **Prairimètre** (Datathon Normandie 2026). Il couvre l'installation (Windows et WSL/Linux), l'architecture des dossiers, toutes les commandes du moteur (`prairimetre/`), le module de télédétection satellitaire Sentinel-2 (`satellite.py`), la suite de tests unitaires (`tests/`), les cinq vues de l'application (`app/`) et le guide de dépannage.

---

## 1. Philosophie et architecture du projet

**Objectif** : Piloter chaque année le « zéro perte nette » de prairies permanentes en Normandie à l'horizon 2030, en suivant les surfaces parcelle par parcelle et en distinguant les **vraies pertes agronomiques** (retournement en culture) des **pertes purement administratives** (sortie de la déclaration PAC alors que l'herbe est toujours présente au sol, vérifiée par satellite Sentinel-2, OCS GE et LUCAS).

### Structure des répertoires

| Répertoire / Fichier | Rôle | Versionné (Git) |
| :--- | :--- | :---: |
| `prairimetre/` | Moteur de calcul géospatial, indicateurs, évaluation et télédétection Sentinel-2 | Oui |
| `app/` | Application interactive Streamlit (5 vues dans `app/vues/` + `commun.py` + `humain.py`) | Oui |
| `sorties/` | **Tables de résultats CSV précalculées** lues directement par l'application | Oui |
| `tests/` | Suite de tests unitaires rapides sur géométries synthétiques et profils NDVI | Local / Livrable |
| `docs/` | Documentation technique, méthodologique, audit parcellaire et présent guide | Oui |
| `importer_donnees.py` | Script d'acquisition automatisée des 24 sources ouvertes (IGN, data.gouv.fr, Eurostat) | Local / Livrable |
| `data/` | Données géographiques brutes et recadrées sur la Normandie (`~736 Mo` à `6,7 Go`) | Non (trop volumineux) |
| `cache/` | Fichiers intermédiaires GeoParquet (`pp_*.parquet`, `devenir_*.parquet`, `zonages_*.parquet`, `~637 Mo`) | Non (régénérable) |
| `livraison/` | Archives `.zip` générées par la commande `python -m prairimetre livrer` | Non |

---

## 2. Installation (Windows 11 & Linux / WSL Ubuntu)

### Option A — Sous Windows (PowerShell / CMD, Python 3.13 recommandé)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Option B — Sous WSL 2 / Ubuntu (compatible Python 3.12, 3.13 et 3.14)

> **Astuce WSL** : Créez l'environnement virtuel dans votre dossier personnel Linux (`~/.venv-datathon`) plutôt que sur la partition montée `/mnt/c/...` pour éviter les lenteurs d'écriture NTFS et les conflits de liens symboliques.

```bash
python3 -m venv ~/.venv-datathon
source ~/.venv-datathon/bin/activate
pip install --upgrade pip
pip install geopandas pyogrio pyarrow shapely pyproj pandas numpy requests truststore py7zr streamlit pydeck altair
```

---

## 3. Démarrage immédiat vs Recalcul complet (Important)

### A. Lancer l'application immédiatement (3 secondes, 0 calcul)

**Vous n'avez PAS besoin de télécharger les 6,7 Go de l'IGN ni de lancer 3 heures de calcul pour faire tourner l'application.**
Toutes les tables de résultats (`communes.csv`, `communes_zones.csv`, `captages.csv`, `serie_region.csv`, `bilan_direct.csv`, `objectif.csv`, `evaluation_*.csv`, `audit_satellite_parcelles.csv`, `zones_noires_satellite.csv`) sont **déjà générées dans `sorties/`**.

```bash
python -m streamlit run app/accueil.py
```
Ouvrez ensuite **http://localhost:8501** dans votre navigateur.

### B. Pourquoi un calcul peut prendre 3 heures chez un coéquipier (et comment l'éviter)

1. **`python importer_donnees.py` complet** télécharge ~6,7 Go sur les serveurs WFS/Atom de l'IGN (8 millésimes RPG + 5 départements OCS GE + zonages). La bande passante WFS de l'IGN impose plusieurs heures de téléchargement (et ~6 h supplémentaires avec `--avec-officielle`).
2. **Double cache du moteur (`cache/` + mémoire vive `_MEMOIRE`)** :
   - Sur la branche `satellite-vision`, `prairimetre/donnees.py` et `prairimetre/suivi.py` intègrent un **cache en mémoire RAM** (`_MEMOIRE` et `_MEMOIRE_SUIVI`) en complément du cache disque GeoParquet (`cache/`).
   - Avec `cache/` présent, **`python -m prairimetre calculer` s'exécute en 88 secondes** (trace dans `sorties/sobriete.csv`).
   - Pour partager l'environnement de calcul avec un binôme sans attendre, partagez simplement le dossier `cache/` (~637 Mo).

---

## 4. Le Moteur (`prairimetre/`) — Modules et Commandes CLI

### 4.1 Architecture des 9 modules du paquet `prairimetre`

| Module | Rôle et responsabilités techniques |
| :--- | :--- |
| `config.py` | Chemins (`DATA`, `CACHE`, `SORTIES`, `MANIFEST`), constantes (`ANNEE_DEBUT = 2018`, `RECENT = 3`, `MIN_HA = 20`, `ANNEE_REFERENCE_OBJECTIF = 2022`, `ANNEE_OBJECTIF = 2030`) et détection dynamique des millésimes RPG présents dans `data/rpg/`. |
| `sources.py` | Catalogue déclaratif des **24 sources de données** : URL/flux WFS, producteur, licence, chemin cible dans `data/`, colonnes obligatoires et mode d'acquisition (`auto`, `wfs`, `manuel`). |
| `telecharger.py` | Téléchargement résilient (avec certificats système via `truststore`), extraction d'archives `.7z`/`.zip`, pagination WFS, calcul d'empreinte `SHA-256` dans `data/manifest.json` et invalidation ciblée du cache. |
| `importer.py` | Import normalisé de fichiers locaux (`.gpkg`, `.shp`, `.geojson`, `.csv`, `.zip`, `.7z`), reprojection automatique en **Lambert-93 (EPSG:2154)**, découpage sur le contour normand et validation du schéma. |
| `controles.py` | Contrôles d'intégrité automatiques (`OK` / `ECART`) : validité géométrique, CRS 2154, bornes de surfaces, cohérence avec les valeurs de référence officielles. |
| `donnees.py` | Lecture optimisée via `pyogrio`, réparation géométrique (`make_valid()`), standardisation des codes INSEE sur 5 caractères (`code5`), classification des 3 familles de zonages (`regle`, `site`, `inventaire`) et double cache (GeoParquet `cache/` + dictionnaire RAM `_MEMOIRE`). |
| `suivi.py` | Suivi spatial parcelle par parcelle via index R-tree (`shapely.STRtree`) par lots de 20 000 géométries : calcul matriciel de `devenir(a0, a1)` et `origine(a0, a1)`, plafonnement des superpositions topologiques et déduction de la part « non déclarée ». |
| `indicateurs.py` | Génération de toutes les tables décisionnelles de `sorties/` : `serie_region.csv`, `bilan_direct.csv`, `cultures_destination.csv`, `objectif.csv`, `communes.csv` (avec mécanisme dominant, certitude, levier d'action et triple classement), `communes_zones.csv`, `captages.csv` et `communes_captages.csv`. |
| `evaluation.py` | Évaluation scientifique et statistique : efficacité des protections à commune constante (`zonages`), robustesse multi-périodes (`robustesse`), concentration de Pareto (`concentration`), pouvoir prédictif (`prediction`), sensibilité aux seuils (`sensibilite`), croisement OCS GE & LUCAS (`certitude`), comparaison SAA (`comparaison_saa`), habitats Natura 2000 (`habitats`) et corrélation avec l'expansion du maïs (`moteurs`). |
| `satellite.py` | Module de télédétection multi-temporelle **Sentinel-2 (NDVI)** et **Theia OSO (CESBIO)** : classification phénologique des parcelles sorties de la PAC, audit des 30 parcelles de contrôle et résolution des 23 « zones noires » communales. |

### 4.2 Toutes les commandes en ligne de commande (CLI)

Toutes les commandes se lancent depuis la racine du dépôt :

```bash
# 1. État du système : millésimes RPG locaux, dernier RPG publié par l'IGN, fraîcheur des 24 sources
python -m prairimetre etat

# 2. Contrôler l'intégrité des données (toutes les années ou une année précise)
python -m prairimetre controler
python -m prairimetre controler --annee 2025

# 3. Calculer tous les indicateurs (génère les tables dans sorties/ ; ~88 s avec cache)
python -m prairimetre calculer

# 4. Évaluer les preuves scientifiques (génère evaluation_*.csv dans sorties/)
python -m prairimetre evaluer --rapide   # Sans recalculer le croisement lourd OCS GE (~30 s)
python -m prairimetre evaluer            # Complet avec croisement OCS GE & LUCAS

# 5. Générer les tables de télédétection satellitaire Sentinel-2 dans sorties/
python -m prairimetre.satellite

# 6. Télécharger une source spécifique ou tous les zonages WFS
python -m prairimetre telecharger rpg --annee 2018 2025
python -m prairimetre telecharger zonages
python -m prairimetre telecharger lucas

# 7. Importer un fichier téléchargé manuellement (.7z, .zip, .gpkg, .csv)
python -m prairimetre importer communes ADMIN-EXPRESS-COG.7z
python -m prairimetre importer ocsge OCS-GE_14_2023.7z --dep 14 --millesime 2023
python -m prairimetre importer rpg RPG_R28_2025.7z --annee 2025

# 8. Mise à jour annuelle tout-en-un (détecte le nouveau RPG, télécharge, contrôle, calcule, évalue)
python -m prairimetre mettre-a-jour

# 9. Créer le paquet de livraison zip dans livraison/
python -m prairimetre livrer                  # Code + sorties/ + docs/ + manifest (~1,5 Mo)
python -m prairimetre livrer --avec-donnees   # Archive complète incluant data/ (~6,7 Go)
```

---

## 5. Module de Télédétection Satellitaire (`prairimetre/satellite.py`)

Le RPG ne couvre que les terres déclarées aux aides PAC, créant deux angles morts majeurs :
1. **55 539 ha** de prairies sorties de la déclaration PAC entre 2018 et 2025 (labour réel ou simple arrêt de déclaration ?).
2. **23 communes normandes (« zones noires »)** ayant $0\text{ ha}$ de prairie déclarée à la PAC.

### Principe biophysique Sentinel-2 (indice NDVI)

Le module exploite la réflectance dans le Proche Infrarouge ($\text{NIR}$, bande B08 à 10 m) et le Rouge ($\text{Red}$, bande B04 à 10 m) :

$$\text{NDVI} = \frac{\text{NIR} - \text{Red}}{\text{NIR} + \text{Red}} \in [-1\,;\,+1]$$

### Grille des seuils décisionnels (`classifier_profil_ndvi`)

| Signature / Classe | $\text{NDVI}_{\min}$ (hiver) | $\text{NDVI}_{\max}$ (printemps) | Amplitude ($\Delta\text{NDVI}$) | Diagnostic retenu |
| :--- | :---: | :---: | :---: | :--- |
| **Prairie permanente** | $\ge 0,40$ | $\ge 0,58$ | $\le 0,28$ | **Maintien physique en herbe** (confiance $85\text{–}95\,\%$) |
| **Friche / pâture extensive** | $\ge 0,32$ | $\ge 0,48$ | $\le 0,35$ | **Maintien en herbe extensif** (confiance $80\,\%$) |
| **Culture annuelle (labour)** | $< 0,25$ (sol nu) | $> 0,60$ | $> 0,35$ | **Retournement réel en culture** (confiance $92\,\%$) |
| **Boisement / ligneux** | $> 0,65$ | $> 0,72$ | Faible | **Fermeture du milieu / forêt** (confiance $90\,\%$) |
| **Surface artificialisée** | $< 0,28$ | $< 0,28$ | Très faible | **Imperméabilisation / bâti** (confiance $95\,\%$) |

**Résultats clés produits dans `sorties/`** :
- `sorties/verification_satellite_30_parcelles.csv` : sur les 30 parcelles normandes sorties de la déclaration auditées ($124,1\text{ ha}$), **81,6 % de la surface (101,3 ha, soit 24 parcelles sur 30)** sont toujours en herbe physique (haras, prés équins, pâtures non déclarées), **3 parcelles (16,8 ha)** sont retournées en culture, **2 parcelles (3,5 ha)** boisées et **1 parcelle (2,5 ha)** artificialisée.
- Diagnostic des **23 communes sans déclaration PAC** (`diagnostic_zone_noire`) : requalifie les « zones noires » du RPG grâce au satellite Sentinel-2 et à Theia OSO (classe 221).

---

## 6. Suite de Tests Automatisés (`tests/test_moteur.py`)

Les tests s'exécutent en **moins d'une seconde** sur des géométries synthétiques en mémoire (aucun besoin du dossier `data/`).

### Lancer tous les tests

```bash
python -m unittest discover tests -v
```

### Détail des 10 tests unitaires vérifiés

| Classe de test | Méthode de test | Ce qui est vérifié |
| :--- | :--- | :--- |
| **`Codes`** | `test_code_insee_sur_cinq_caracteres` | Normalisation stricte des codes INSEE (`1001` $\rightarrow$ `"01001"`, `"14118.0"` $\rightarrow$ `"14118"`, suppression des espaces). |
| **`Codes`** | `test_categories_rpg` | Affectation exacte des groupes et codes cultures RPG (`18` $\rightarrow$ prairie permanente, `19` $\rightarrow$ temporaire, `2` $\rightarrow$ culture, `BOR` $\rightarrow$ boisement). |
| **`Croisement`** | `test_moitie_retournee_moitie_non_declaree` | Intersection géométrique d'un carré de 1 ha ($100\text{ m} \times 100\text{ m}$) à moitié labouré : $0,5\text{ ha}$ culture + $0,5\text{ ha}$ non déclaré. |
| **`Croisement`** | `test_recouvrement_borne_a_la_surface` | Deux parcelles superposées ne dépassent jamais $100\,\%$ de la surface initiale de la prairie ($1,0\text{ ha}$ max). |
| **`Croisement`** | `test_prairie_sans_voisin` | Une prairie sans parcelle RPG l'année finale est intégralement classée en « non déclaré » ($1,0\text{ ha}$). |
| **`Croisement`** | `test_bilan_conserve_la_surface` | Conservation stricte des surfaces ($\sum \text{destinations} = \text{surface de départ}$). |
| **`Ocsge`** | `test_herbe_agricole_ou_non` | Décodage de la matrice Couverture $\times$ Usage de l'OCS GE (`CS2.2.1` + `US1.1` vs autres usages, bâti `CS1.1`, ligneux `CS2.1`). |
| **`Satellite`** | `test_calcul_ndvi` | Exactitude de la formule $\text{NDVI} = (\text{NIR} - \text{Red}) / (\text{NIR} + \text{Red})$ et gestion de la division par zéro. |
| **`Satellite`** | `test_classification_profils_phenologiques` | Discrimination automatique d'un profil annuel de prairie permanente, d'une culture labourée et d'une surface bâtie. |
| **`Satellite`** | `test_audit_et_diagnostic_zone_noire` | Synthèse statistique des 30 parcelles auditées ($81,6\,\%$ de maintien en herbe) et requalification des zones noires hors PAC. |

---

## 7. Guide des 5 Pages de l'Application (`app/`)

L'application est structurée autour de `app/accueil.py`, `app/commun.py` (chargements mis en cache `@st.cache_data`, palettes, lexique) et `app/humain.py` (illustrations SVG et ordres de grandeur).

| Page | Fichier source | Fonctionnalités principales |
| :--- | :--- | :--- |
| **1. Où agir** | `app/vues/prairies.py` | • Bandeau d'état par rapport à l'objectif 2030.<br>• **Moyen 1** : Suivre le compteur en hectares (et non en ratio PAC) avec trajectoire 2018–2025.<br>• **Moyen 2** : Cibler les paiements de maintien (MAEC/PSE) par commune, EPCI ou aire de captage d'eau potable (carte interactive + export CSV).<br>• **Moyen 3** : S'appuyer sur les communes exemplaires qui gagnent des prairies. |
| **2. Ma commune** | `app/vues/commune.py` | • Recherche par nom ou code postal.<br>• Bilan complet 2018 $\rightarrow$ 2025 (maintenues, retournées en culture, sorties de la déclaration, nouvelles).<br>• Décomposition **zone par zone** (`zones humides`, `sites protégés`, `prairies sensibles`, `ZNIEFF`, `captages`, `habitats Natura 2000`).<br>• Carte interactive des parcelles de la commune (en Lambert-93 reprojecté WGS84). |
| **3. Cartes et données** | `app/vues/donnees.py` | • **4 mini-cartes synchronisées** comparant la couverture de chaque source : Registre PAC, Télédétection Sentinel-2 (0 zone noire), OCS GE et Habitats Natura 2000.<br>• **Explorateur cartographique grand format** (Sélecteur 4 couches + zoom + infobulles détaillées).<br>• Section dédiée à l'audit Sentinel-2 / Theia OSO des 30 parcelles et des 23 communes hors PAC.<br>• Ciblage des **195 communes** où vérifier le terrain avant de financer, et des départements 27/76 sans cartographie Natura 2000. |
| **4. Données et méthode** | `app/vues/methode.py` | • **Onglet Preuves** : démonstration statistique de chaque levier (protection BCAE 9 vs sites/inventaires, concentration de Pareto, lien avec l'ensilage de maïs, télédétection Sentinel-2).<br>• **Onglet Sources** : catalogue interactif des 24 jeux de données et références.<br>• **Onglet Moteur** : interface sans terminal pour contrôler l'état, importer un fichier ou lancer une mise à jour. |
| **5. Lexique** | `app/vues/lexique.py` | • Barre de recherche instantanée parmi **22 définitions techniques et réglementaires** (dont le Score NDVI, Sentinel-2, Theia OSO, BCAE 1/2/9, MAEC, PSE, AAC, OCS GE, LUCAS, SAA).<br>• Tableau de référence des seuils biophysiques NDVI.<br>• Comparatif des « 4 chiffres qui circulent sur les prairies » (ratio PAC, RPG brut, SAA, Prairimètre). |

---

## 8. Dépannage (FAQ Technique)

| Problème rencontré | Cause technique | Solution |
| :--- | :--- | :--- |
| **Le calcul tourne depuis plusieurs heures chez un coéquipier** | Il a lancé `importer_donnees.py` (6,7 Go sur serveurs lents IGN) ou `calculer`/`evaluer` sur une ancienne branche sans le cache RAM `_MEMOIRE`. | Arrêter avec `Ctrl + C`. Récupérer la branche `satellite-vision` où `sorties/*.csv` est déjà prêt, puis lancer directement `streamlit run app/accueil.py`. |
| **Les polygones des cartes apparaissent gris/transparents sans couleurs** | Sous `pandas >= 3.0`, appliquer `.map()` sur une colonne `StringDtype` (`g.insee`) convertit les listes `[R, G, B, A]` en chaînes de caractères `"[R, G, B, A]"`. | Corrigé dans `app/vues/donnees.py` par l'utilisation de listes en compréhension `[hex_rgb(...) for i in g.insee]`. |
| **Une des mini-cartes ne s'affiche pas dans le navigateur** | Les navigateurs limitent le nombre de contextes WebGL simultanés (souvent 8 à 16 par onglet). | Corrigé dans `app/vues/donnees.py` en désactivant la couche WebGL de tuiles (`map_provider=None`) sur les 4 mini-cartes de comparaison. |
| **Modification de `LEXIQUE` ou d'une constante dans `commun.py` non visible** | Streamlit garde en mémoire les modules importés tant que le processus Python tourne. | `app/vues/lexique.py` recharge dynamiquement `commun` via `importlib.reload(commun)` ; pour les autres vues, relancer `streamlit run app/accueil.py`. |
| **Erreur `.venv-linux` sous WSL (`python3.12: not found`)** | L'ancien dossier `.venv-linux` pointait vers Python 3.12 alors qu'Ubuntu 26.04 utilise Python 3.14. | Activer `~/.venv-datathon` (`source ~/.venv-datathon/bin/activate`) créé avec le Python natif de la distribution WSL. |
