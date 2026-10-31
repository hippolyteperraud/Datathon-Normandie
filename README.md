# Données sur l'eau en Normandie

Scripts autonomes pour explorer les données des stations de mesure Hubeau, analyser les
nitrates dans les cours d'eau et examiner des couches géographiques liées à l'eau potable.

## Préparer l'environnement

Avec Python 3.13 sous Windows :

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Les scripts `parcourir_bases.py`, `verifier_tailles.py`, `test_aac.py` et
`test_zones_vulnerables.py` explorent ou téléchargent des couches avec pandas et GeoPandas.
L'analyse des nitrates utilise la bibliothèque standard de Python.

## Stations de mesure Hubeau

Récupérer l'inventaire des stations de qualité des rivières des cinq départements :

```powershell
python scripts\recuperer_hubeau.py
```

Le fichier `data/raw/qualite_eau_hubeau/stations_normandie.csv` décrit les stations et
leurs coordonnées ; ce n'est pas le fichier des analyses d'eau.

Pour compter les stations et consulter les champs :

```powershell
python scripts\parcourir_bases.py
python scripts\verifier_tailles.py
```

## Mesures de nitrates

Avec une connexion internet et le fichier de stations précédent :

```powershell
python scripts\analyser_nitrates.py
```

Le script récupère les analyses Hubeau qualifiées pour les nitrates (2015–2025), puis écrit
les mesures filtrées et les résumés par année, département et station sous `data/`.
La méthode, les résultats obtenus et les limites sont décrits dans
[`docs/suivi_qualite_eau.md`](docs/suivi_qualite_eau.md).

## Aires d'alimentation de captage et zones vulnérables

`scripts/test_aac.py` examine le GeoPackage des aires d'alimentation de captage attendu dans
`data/raw/aac_normandie/AAC.gpkg`. `scripts/test_zones_vulnerables.py` interroge le service
WFS du Sandre et écrit la couche téléchargée dans `data/raw/zones_vulnerables/`.

Le fichier [`glossaire_eau.md`](glossaire_eau.md) explique la différence entre les aires
d'alimentation de captage et les stations de mesure. Le GeoPackage AAC local peut contenir
des aires hors de Normandie : le bassin administratif Seine-Normandie ne se confond pas avec
les limites régionales.

## Tests

Depuis la racine du dépôt :

```powershell
python -m unittest discover -s tests -v
```

Ces tests utilisent de petites données construites en mémoire ; ils n'appellent pas l'API
Hubeau.

## Interprétation

Une évolution des nitrates mesurés dans les rivières ne prouve pas que les prairies en sont
la cause. Les résultats constituent un état descriptif ; ils ne sont pas un seuil
réglementaire et ne décrivent pas directement l'eau potable au robinet. Pour étudier le lien
avec l'occupation des sols, il faudrait notamment rattacher les stations à leurs bassins
versants amont et prendre en compte d'autres facteurs possibles.
