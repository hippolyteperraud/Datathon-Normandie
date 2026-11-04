# État de l'art : qui suit déjà les prairies permanentes, et ce que Prairimètre ajoute

Recherche du 25 octobre 2026. Les liens sont en bas de page.

## Ce qui existe

| Qui | Quoi | Limite pour la Normandie |
|---|---|---|
| **État, PAC** (arrêté annuel des ratios) | Ratio régional de prairies permanentes, comparé à une référence ; régime d'autorisation ou d'interdiction si la baisse dépasse un seuil. La Normandie a été placée en régime d'interdiction fin 2023 (baisse de 6,45 %), puis en est sortie après le recalcul des références permis par l'Union européenne en 2024 (déprise de l'élevage). | Un ratio régional, sans localisation. Après le recalcul, il ne recule que de 1,97 % alors que la région a perdu 60 000 ha de prairies déclarées depuis 2018. |
| **DRAAF Normandie** (Agreste Études n° 6, septembre 2021) | Les prairies normandes de 2008 à 2019 : −103 000 ha (−11 %), surtout retournées en terres arables ; le retournement se concentre dans les élevages laitiers de l'ouest, qui évoluent vers la polyculture-élevage, et profite aux grandes cultures à l'est. | Étude ponctuelle, arrêtée en 2019, fondée sur des données non ouvertes (OSCOM, BDNI) ; ne suit ni les règles ni l'eau potable. Elle explique le « pourquoi » (systèmes d'exploitation) que les données ouvertes ne permettent pas de refaire. |
| **DRAAF Grand Est** (Agreste, 2022) | Analyse des RPG 2015-2019 superposés deux à deux : environ 1 % des prairies remises en culture chaque année, y compris dans les aires de captage et Natura 2000. | Étude ponctuelle, non mise à jour, autre région, non reproductible par un tiers. |
| **Data Grand Est** (groupe de travail prairies, 2023-2024) | Les services jugent « utile » un indicateur récurrent des retournements ; pistes : NDVI (DREAL Nouvelle-Aquitaine), apprentissage sur images Sentinel-2. | Besoin exprimé, pas d'outil livré. |
| **DREAL Hauts-de-France** (2026) | Carte en ligne des zonages où le retournement est encadré (programme nitrates, zones humides, captages, pentes). | Dit où une règle s'applique, pas où les prairies disparaissent. |
| **Statistique agricole annuelle** (Agreste) | Surfaces en prairies par département et par an. | Pas de localisation fine ; ne distingue pas retournement et changement de déclaration. |

Nous n'avons trouvé **aucun observatoire régional** qui suive chaque année, parcelle par parcelle, le
devenir des prairies à partir du RPG, en Normandie ou ailleurs.

## Ce que Prairimètre ajoute

1. **Annuel et reproductible** : une commande télécharge le nouveau RPG et recalcule tout ; le code
   et la méthode sont ouverts.
2. **Le devenir de chaque prairie**, pas un solde : retournée en culture (perte déclarée) ou sortie
   de la déclaration (perte à vérifier), et ce qui pousse à la place.
3. **Le contrôle par des sources indépendantes** : statistique agricole annuelle, OCS GE de l'IGN,
   points d'enquête LUCAS. Il montre qu'une partie de la chute de 2023 est administrative.
4. **L'effet associé des règles**, à commune égale, séparé de celui des simples inventaires.
5. **Une réponse par acteur** : communes et intercommunalités à cibler, aires de captage avec leur
   contact, fiche par commune pour les élus et les habitants.

## Ce que Prairimètre ne fait pas (et que d'autres font mieux)

- La télédétection (NDVI, Sentinel-2) verrait l'herbe hors déclaration PAC : c'est la suite logique,
  hors de portée d'un datathon de quatre semaines et coûteuse en calcul.
- La décision de l'exploitant (transmission, agrandissement) : données non ouvertes.

## Sources

- Arrêté du 11 septembre 2026, JORF n° 0218 (ratios 2026) ; presse agricole sur le régime 2023 et le recalcul 2024 : [Réussir Lait](https://www.reussir.fr/lait/prairies-permanentes-4-regions-en-regime-dautorisation-ou-dinterdiction)
- DRAAF Normandie, Agreste Études n° 6, « Les prairies en Normandie entre 2008 et 2019 », septembre 2021 (copie locale : `data/references/agreste_etudes_6_prairies_normandie_2008_2019.pdf`)
- [DRAAF Grand Est, Agreste, prairies permanentes (2022)](https://draaf.grand-est.agriculture.gouv.fr/IMG/pdf/2022-03-prairies_permanentes.pdf)
- [Data Grand Est, compte rendu du GT prairies, 3 mars 2023](https://www.datagrandest.fr/portail/sites/default/files/rge_animationdge_20230303_cr_gt_prairies_vf.pdf) ; [GT prairie, 23 mai 2024](https://datagrandest.fr/portail/sites/default/files/rge_animationdge_20240523_a2s_gt_prairie.pdf)
- [DREAL Hauts-de-France, carte des zonages prairies (2026)](https://www.hauts-de-france.developpement-durable.gouv.fr/IMG/pdf/2026-tuto_explication_carto_zonages_prairie.pdf)
