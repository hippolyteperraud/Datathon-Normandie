# Compte rendu : l'herbe hors PAC vue par le satellite (2025)

Calculs du 10/11/2026, sans réseau, sur 675 images Sentinel-2 de 2025.

Fichiers dans `data/sentinel2/2025/` :
- `bilan.txt` ;
- `etats_cibles.parquet` ;
- `etats_etalons.parquet` ;
- `etalonnage_tirages.csv`.

## La question

Pour 2025, la statistique agricole (Agreste) compte **766 157 ha** toujours en herbe en Normandie. Le registre PAC ne compte que **621 621 ha** de prairies permanentes déclarées. Il reste **144 536 ha** d'herbe en dehors du registre.

Agreste découpe ces 144 536 ha en deux parts :
- **106 477 ha** hors exploitations agricoles ;
- **38 059 ha** d'herbe d'exploitations non déclarée en prairie permanente.

Peut-on retrouver ce chiffre nous-mêmes, avec la carte IGN et le satellite ?

## Ce qu'on a fait

1. **L'herbe de la carte IGN hors registre.** On a pris le couvert herbacé de la carte OCS GE, à usage agricole ou sans usage. On en a retiré tout ce qui est déclaré à la PAC en 2025. Il reste **160 672 morceaux, soit 220 931 ha**.
2. **Chaque morceau vu au satellite**, avec la même règle que pour les prairies de la page Objectif 2030. Chaque morceau reçoit un état : couvert permanent, labouré, bâti, ou indéterminé.
3. **Contrôle du calcul.** Sur les 21 636 prairies déjà mesurées avant, le calcul hors ligne donne **le même état dans 99,7 % des cas** quand les deux calculs tranchent. Les autres sont des prairies juste au bord d'un seuil de la règle.
4. **Étalonnage de la règle sur des parcelles dont on connaît la réponse.** On a mesuré, avec la même règle :
   - **15 000 parcelles d'herbe sûre**, déclarées prairie permanente en 2024 et en 2025 ;
   - **13 418 parcelles de cultures sûres** en 2025 (céréales, maïs, colza, etc.).

   Elles sont dans les mêmes classes de taille que les morceaux hors PAC, de 0,1 ha à plus de 5 ha.

## Ce que dit l'étalonnage : la règle voit 3 prairies sur 4

| Parcelles connues | couvert permanent | indéterminé | labourée |
|---|---:|---:|---:|
| Herbe sûre | **75 %** | 22 % | 2,5 % |
| Cultures sûres (parcelles de 1 à 5 ha) | 0,2 % | 1,7 % | 97,9 % |

- **Une culture n'est presque jamais classée « couvert permanent »** : 0,1 à 0,4 % au-delà de 0,5 ha, 5 % pour les plus petites. Quand la règle dit « couvert permanent », c'est donc bien de l'herbe, ou au moins une végétation verte toute l'année.
- **Mais la règle ne classe en « couvert permanent » que 75 % de l'herbe sûre.** Les 22 % restants tombent en zone grise. Leur NDVI le plus bas tombe surtout en janvier, ou en juillet-août (été sec). C'est voulu : la règle préfère ne pas trancher plutôt que se tromper.
- Pour les petites parcelles, la règle voit moins bien : 65 % de l'herbe sûre de 0,1 à 0,25 ha, 76 % de 1 à 5 ha.

**Conséquence : compter seulement le « couvert permanent » sous-estime l'herbe d'environ un quart.**

## Le résultat

| Herbe hors registre PAC 2025 | Hectares |
|---|---:|
| Classée « couvert permanent » (minimum sûr) | **138 469** |
| **Herbe estimée, après étalonnage** | **184 384** (intervalle à 95 % : 180 271 à 189 462) |
| Agreste | **144 536** |

L'estimation après étalonnage se fait classe de taille par classe de taille :
- herbe = (couvert permanent observé − part due aux cultures) ÷ part de l'herbe sûre classée couvert permanent ;
- l'intervalle vient de 300 tirages au hasard des parcelles.

Une autre méthode (le mélange herbe/cultures sur les quatre états) donne 199 344 ha. Elle colle moins bien aux observations : les morceaux hors PAC ont plus de zone grise que l'herbe sûre elle-même. On retient donc 184 384 ha.

**Par origine** (même calcul) :

| | Satellite après étalonnage | Agreste |
|---|---:|---:|
| Jamais déclarée à la PAC 2018-2024 | 125 997 (123 424 à 129 239) | 106 477 (hors exploitations) |
| Déjà déclarée à la PAC 2018-2024 | 58 387 (56 347 à 61 307) | 38 059 (exploitations, non PP) |

Rapprocher « jamais déclarée » de « hors exploitations » est une approximation de notre part : Agreste ne les définit pas ainsi.

## Ce que ça veut dire

- **On ne retrouve pas exactement Agreste.** Après correction, la carte IGN et le satellite voient environ **40 000 ha d'herbe de plus** qu'Agreste hors registre PAC (184 384 contre 144 536).
- Le « 96 % » annoncé avant l'étalonnage était une coïncidence. Il comparait le seul « couvert permanent » au chiffre d'Agreste, alors que la règle ne voit que 75 % de l'herbe.
- **Le minimum de 138 469 ha est sûr.** L'herbe hors registre est donc bien réelle et du même ordre que le chiffre d'Agreste.
- **D'où peuvent venir les 40 000 ha de plus ?** Ce sont des pistes, aucune n'est vérifiée :
  - la carte IGN date de 2022 (Eure, Manche, Seine-Maritime) ou de 2023 (Calvados, Orne), pas de 2025 ;
  - l'usage « sans usage » de l'IGN peut contenir de l'herbe qu'Agreste ne compte pas comme superficie toujours en herbe : friches, délaissés, bords de route larges, jardins ;
  - une végétation verte toute l'année qui n'est pas de l'herbe (broussailles) peut être classée « couvert permanent » ;
  - le chiffre « hors exploitations » d'Agreste est lui-même une estimation régionale : il varie de 106 000 à 117 000 ha selon les années récentes.

**La mesure officielle de l'objectif 2030 reste Agreste.** Le satellite confirme que l'herbe hors registre existe, au moins 138 469 ha, et dit où elle est. Il ne donne pas le chiffre d'Agreste à l'hectare près.

## Conséquence pour la page Objectif 2030 (à valider, rien n'est changé)

La ligne « sortie, restée verte » (37 993 ha) utilise la même règle. D'après l'étalonnage, elle compte environ 3 prairies sur 4 parmi celles qui sont vraiment restées en herbe : **c'est un minimum**. Il faudra le dire sur la page, ou corriger ce chiffre de la même façon. À décider.

## Ce qu'on ne sait pas

- Si l'herbe hors registre **diminue** depuis 2021 : on n'a mesuré que 2025.
- La part exacte d'herbe dans la zone grise des morceaux hors PAC : ils ont plus de zone grise que l'herbe sûre, donc ce ne sont pas tous des prés comme ceux des exploitations.
