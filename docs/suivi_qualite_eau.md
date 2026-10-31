# Suivi de la qualité de l'eau et des prairies

## Objectif

Les prairies permanentes peuvent ralentir le ruissellement et retenir une partie des
nitrates avant leur arrivée dans les cours d'eau. Ce suivi décrit l'évolution des mesures
de nitrates dans les cours d'eau normands en comparant les mêmes stations entre deux
périodes, sans confondre corrélation et causalité. L'analyse ne croise pas encore ces mesures
avec les données d'occupation des sols.

L'indicateur décrit les tendances mesurées aux stations de rivière. Il ne mesure pas
encore l'effet des prairies. Une analyse ultérieure pourra relier les stations à leurs
bassins versants amont et calculer la part de prairies dans chaque bassin.

## Ce qui existe déjà dans le dépôt

- `data/raw/qualite_eau_hubeau/stations_normandie.csv` contient 1 467 stations de mesure
  des cours d'eau, réparties dans les cinq départements.
- Le fichier décrit les stations et leurs coordonnées ; il ne contient pas les résultats
  des analyses d'eau. Le script d'analyse récupère les résultats séparément depuis
  l'API Hubeau.
- `data/raw/aac_normandie/AAC.gpkg` contient 1 659 aires d'alimentation de captage au
  niveau national, dont 638 associées au bassin administratif Seine-Normandie. Le bassin
  ne correspond pas aux limites de la Normandie : filtrer seulement sur son nom ne permet
  pas d'identifier les aires situées dans la région.
- Une station de qualité des rivières et une aire d'alimentation de captage ne sont pas
  deux objets que l'on peut relier simplement par proximité : la première mesure l'eau de
  surface, la seconde concerne l'alimentation d'un captage, souvent souterrain.

## Méthode

Le script `scripts/analyser_nitrates.py` interroge Hubeau pour le paramètre **nitrates**
(code 1340), dans les cours d'eau de Normandie, sur les années complètes 2015 à 2025.
Il retient l'eau (support 3), la phase aqueuse filtrée (fraction 3), les résultats qualifiés
corrects (qualification 1), les données validées de niveau 2 (statut 3) et l'unité
mg(NO3)/L (code 173).

Pour éviter qu'une station très souvent échantillonnée pèse davantage dans le bilan
régional, le script calcule d'abord une médiane par station et par année, puis la médiane
de ces stations. Il compare ensuite, station par station, les médianes de 2015–2017 et
2023–2025. Seules les stations ayant au moins deux années d'observation dans chacune des
deux fenêtres sont incluses dans cette comparaison.

## Exécution et résultats

Depuis la racine du dépôt, après récupération du fichier des stations :

```text
python scripts/analyser_nitrates.py
```

Le script utilise uniquement la bibliothèque standard de Python pour analyser les données.
Les mesures et tableaux restent dans `data/`, qui est ignoré par Git :

- `data/raw/qualite_eau_hubeau/nitrates_2015_2025.csv` : mesures retenues ;
- `data/processed/qualite_eau/nitrates_par_annee.csv` : médiane des stations par année ;
- `data/processed/qualite_eau/nitrates_par_departement.csv` : même indicateur par département ;
- `data/processed/qualite_eau/tendance_stations_nitrates.csv` : comparaison des stations
  présentes dans les deux fenêtres ;
- `data/processed/qualite_eau/synthese_tendance_nitrates.csv` : résumé des stations comparables.

L'API est interrogée à chaque exécution ; les résultats reflètent donc l'état de Hubeau au
moment du téléchargement. Les tableaux peuvent être ouverts dans un tableur et servir de
support à une première discussion.

### Premier résultat (exécution du 31 octobre 2026)

Le téléchargement a retenu **32 669 analyses**, correspondant à **709 stations**. La médiane
des médianes de station est passée de **20,1 mg(NO3)/L en 2015** (406 stations) à
**22,0 mg(NO3)/L en 2025** (395 stations). Parmi les **279 stations** ayant au moins deux
années observées dans chacune des fenêtres 2015–2017 et 2023–2025, la variation médiane
entre les deux fenêtres est de **+1,65 mg(NO3)/L** ; elle est positive pour 192 stations et
négative pour 87.

Ce résultat est un signal descriptif à vérifier, pas une conclusion sur l'effet des
prairies. La couverture et la fréquence des mesures varient d'une année et d'une station
à l'autre ; aucune correction des facteurs météo, géologiques, agricoles ou
d'assainissement n'est appliquée.

## Limites d'interprétation

- Une évolution régionale des nitrates ne permet pas, à elle seule, d'attribuer cette
  évolution aux prairies. Les pluies, les sols, la géologie, les cultures, l'assainissement,
  les prélèvements et les changements de stations peuvent aussi compter.
- Les données portent sur les rivières, pas directement sur l'eau distribuée au robinet
  ni sur la qualité de l'eau brute de chaque captage.
- Les médianes par station réduisent le poids des stations très échantillonnées, mais les
  stations retenues et la fréquence de mesure varient encore selon les années.
- La comparaison temporelle des stations est un indicateur exploratoire, pas un seuil
  réglementaire ni une preuve d'effet.

## Étape suivante

Choisir quelques bassins versants amont bien suivis, récupérer leurs limites
hydrographiques, puis calculer la part de prairies permanentes dans chaque bassin aux mêmes
périodes que les mesures. On pourra alors comparer les tendances de nitrates entre bassins
où les prairies se maintiennent et bassins où elles reculent, en explicitant les limites et
les autres facteurs possibles.

Sources : [API Hubeau - qualité des cours d'eau](https://hubeau.eaufrance.fr/page/api-qualite-cours-deau)
et [données Hubeau des aires d'alimentation de captage](https://hubeau.eaufrance.fr/).
