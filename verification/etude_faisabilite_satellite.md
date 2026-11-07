# Étude de faisabilité : les images satellite pour les prairies sorties de la déclaration

Novembre 2026. Les résultats chiffrés et leurs preuves sont dans `sentinel2/preuves.md`.

## La question

Le registre PAC dit qu'une prairie est sortie de la déclaration, pas ce qu'elle est devenue.
55 539 ha sont dans ce cas depuis 2018, dont 30 796 ha la seule année 2022→2023 (exploitants
retraités sortis de la PAC, règle « agriculteur actif »). Deux décisions en dépendent :

1. **Objectif 2030** : si l'herbe sortie en 2023 est encore là, l'écart en hectares déclarés tombe
   de −29 878 ha à environ −6 300 ha.
2. **Où aller voir** : 135 communes « prioritaires » entreraient dans la liste des communes où l'on
   retourne le plus si leurs prairies sorties étaient perdues.

## Ce qui a été repris du travail de Mouhssine

- Gardé : le calcul du NDVI, l'idée de classer une parcelle d'après son NDVI de l'année, les 30
  parcelles tirées au hasard (`docs/verification_parcelles.md`).
- Écarté : les 30 résultats écrits à la main dans le code, sans source ni date, et leur extension
  aux 55 539 ha ; la carte « Télédétection » qui renommait le registre PAC ; le diagnostic « zone
  noire » qui renvoyait le même verdict à toutes les communes.

## Les sources ouvertes possibles

| Source | Ce qu'elle donne | Accès | Verdict |
|---|---|---|---|
| Sentinel-2 L2A (Copernicus) via Microsoft Planetary Computer | Images tous les 5 jours, 10 m ; NDVI et classification des nuages calculés par le service sur le contour d'une parcelle | Ouvert, **sans compte, rien à installer** | **Retenu, testé** |
| Sentinel-2 via Copernicus Data Space | Mêmes images | Compte gratuit obligatoire | Possible, pas nécessaire |
| Sentinel-2 via Earth Search (AWS) | Mêmes images en fichiers | Ouvert, mais il faut GDAL/rasterio pour les lire | Pour passer à grande échelle |
| Carte OSO (Theia, CESBIO) | Occupation du sol annuelle à 10 m, avec une classe prairies | Ouvert | À tester : millésimes récents et justesse sur les prairies à vérifier |
| Photo aérienne IGN (BD ORTHO) | Photo précise, tous les 3 ans environ par département | Ouvert, consultable sur Géoportail | Pour trancher à l'œil (liens dans les preuves) |
| Couche prairies Copernicus (HRL Grassland) | Carte des prairies à 10 m | Ouvert | 2018 seulement : ne dit rien sur 2023 |
| OCS GE (IGN) | Occupation du sol | Ouvert | Range prairies et cultures dans la même classe : inutilisable ici |

## Ce qui a été fait et ce qu'il en ressort

- Le service répond en environ 1 seconde par image et par parcelle. Une parcelle, c'est environ
  50 images par an : **110 parcelles en 13 minutes** avec 6 requêtes en parallèle.
- **Une première règle, fixée à l'avance, a échoué** : elle voyait labourées 11 prairies sur 20
  qui étaient toujours déclarées. Cause : des images isolées que la classification de l'ESA met à
  tort en sol nu. La règle a été corrigée sur ces 40 témoins, puis **validée sur 40 autres, jamais
  regardés : 2 erreurs sur 29 parcelles tranchées** (11 indéterminées).
- **Sorties de 2023** : sur 40 parcelles tirées au hasard, 35 tranchées, **toutes restent vertes
  toute l'année 2025, sans labour** (au moins 90 %, intervalle à 95 %).
- **Les 30 parcelles** (sorties entre 2018 et 2025) : 21 sur 22 tranchées restent vertes.

## Où le faire tourner : les options

| Option | Parcelles | Durée avec le service | Ce que ça décide |
|---|---|---|---|
| A. Échantillon des sorties de 2023 (fait) | 40 | 5 min | L'écart à l'objectif 2030 : entre −12 400 et −6 300 ha au lieu de −29 878 |
| B. Les 135 communes prioritaires de « Où aller voir », toutes les parcelles sorties d'au moins 1 ha | 2 246 (10 213 ha sur 12 434) | environ 4 à 5 h, à lancer la nuit | Commune par commune : faut-il encore y aller, ou le satellite a-t-il répondu ? |
| C. Les 237 communes de « Où aller voir » | 5 567 (21 086 ha) | environ 11 h | Même chose, liste complète |
| D. Toute la Normandie | 12 161 (40 119 ha) | plus d'une journée ; mieux avec GDAL en local | Une carte régionale des sorties encore vertes |

**Recommandation** : A est fait et répond à la question la plus forte pour le jury (l'objectif
2030). B est la suite logique pour « Où aller voir » : la page pourrait alors dire, pour chaque
commune prioritaire, quelle part de ses prairies sorties reste verte, et ne garder « à aller voir »
que ce que le satellite ne tranche pas.

## Limites, à dire au jury

- **Vert n'est pas herbe** : une friche, une luzerne ou un jeune bois donnent aussi un couvert
  permanent. La photo aérienne IGN tranche à l'œil (lien pour chaque parcelle dans les preuves).
- Une année d'images (2025) : un labour d'une autre année ne se voit pas.
- Parcelles d'au moins 1 ha (pixels de 10 m) ; contours de la parcelle avant sa sortie.
- L'objectif régional officiel se mesure en part de la surface agricole toujours en herbe
  (statistique agricole), pas en hectares déclarés à la PAC : le satellite éclaire le registre, il
  ne remplace pas l'indicateur officiel.

## Refaire

```
python scripts/analyser_satellite_sentinel.py --sentinel
```

Les tirages sont reproductibles (graines fixes) ; chaque mesure est tracée dans
`sentinel2/images.csv`.
