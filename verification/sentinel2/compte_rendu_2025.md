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

## D'où vient l'écart (cherché le 10/11, en fin de journée)

### 1. Des bois et des broussailles pris pour de l'herbe : environ 10 000 ha

On a mesuré avec la même règle 12 818 morceaux de forêt et 4 064 morceaux de broussailles de la carte IGN, hors registre PAC.

| Parcelles connues | couvert permanent | indéterminé | labourée |
|---|---:|---:|---:|
| Bois | 13,4 % | 82,1 % | 4,5 % |
| Broussailles | 28,0 % | 53,8 % | 17,8 % |

La règle à seuils prend donc une partie des bois et broussailles pour de l'herbe.

On a alors classé chaque morceau d'après **toute sa courbe NDVI de l'année** : NDVI de chaque mois, creux d'été, niveau d'hiver. Le classement a été appris sur l'herbe sûre, les cultures sûres et les bois. En validation, il reconnaît :
- 97,0 % de l'herbe sûre ;
- 99,3 % des cultures ;
- 96,7 % des bois.

Résultat sur les morceaux hors PAC :

| | courbe d'herbe | courbe de bois | courbe de culture |
|---|---:|---:|---:|
| « couvert permanent » de la règle | 122 606 | 15 810 | 53 |
| zone grise de la règle | 43 427 | 14 866 | 2 189 |
| « labourée » de la règle | 3 969 | 4 466 | 11 902 |
| **Total** | **170 002** | 35 142 | 14 144 |

À ces lignes s'ajoutent 1 043 ha « bâti ou minéral » et 602 ha sans assez d'images.

Les « bois » sont des landes (La Hague), des marais à roseaux (Marais-Vernier, estuaire de la Seine) et des broussailles, répartis dans les cinq départements.

**Herbe reconnue à sa courbe : 170 002 ha** (174 289 ha en corrigeant les 3 % d'erreurs du classement). L'écart avec Agreste passe de 40 000 à environ **25 000 ha**.

### 2. Ce qui reste, comparé à Agreste partie par partie

Pour l'herbe déjà déclarée, on regarde la dernière année où le morceau était au registre PAC (point au centre du morceau).

| Herbe hors registre PAC 2025 (courbe d'herbe) | Satellite | Agreste |
|---|---:|---:|
| Jamais déclarée à la PAC (2018-2024) | 113 033 | 106 477 (hors exploitations) |
| Sortie du registre en 2023 ou après (dernière déclaration 2022, 2023 ou 2024) | **38 270** | **38 059** (exploitations, non déclarée en PP) |
| Sortie du registre avant 2023 (dernière déclaration 2018 à 2021) | 15 318 | rien |
| Déjà déclarée, année de sortie inconnue | 3 381 | rien |
| **Total** | **170 002** | **144 536** |

- **L'herbe sortie du registre depuis la PAC 2023 tombe pile sur Agreste** : 38 270 ha contre 38 059 ha. Le registre a perdu d'un coup 28 687 ha de prairies permanentes en 2023 (651 554 → 622 867 ha), alors qu'Agreste n'a baissé que de 3 669 ha. **Agreste continue de compter cette herbe comme herbe des exploitations.** Le satellite confirme qu'elle est toujours en herbe.
- **L'herbe jamais déclarée est proche d'Agreste** : 113 033 contre 106 477, soit 6 % de plus.
- **L'écart restant vient surtout de l'herbe sortie du registre avant 2023** : 15 318 ha, plus 3 381 ha d'année inconnue. De 2018 à 2022, l'écart entre Agreste et le registre est resté entre 3 928 et 7 585 ha par an. **Agreste n'a donc pas gardé ces sorties dans l'herbe des exploitations**, alors que le satellite les voit toujours en herbe en 2025.

**Ces prairies sont-elles abandonnées ? Non : contrôle sur photos aériennes (11/11).**

On a tiré au hasard 48 morceaux d'au moins 1 ha reconnus comme herbe par leur courbe :
- 24 sortis du registre avant 2023 (non comptés par Agreste) ;
- 24 sortis depuis 2023 (comptés par Agreste).

On les a regardés sur la photo aérienne de l'IGN **sans savoir à quel groupe chacun appartenait**, puis on a comparé.

| | prairie fauchée ou pâturée | friche | mélange (jardins, parc) | douteux |
|---|---:|---:|---:|---:|
| Sortis avant 2023 | 21 | 1 | 1 | 1 |
| Sortis depuis 2023 | 21 | 1 | 1 | 1 |

**Les deux groupes sont identiques.** Les prairies sorties avant 2023 sont des prés comme les autres :
- bocage, fauche, prés-vergers ;
- plusieurs paddocks et installations pour chevaux.

L'hypothèse « herbe abandonnée » est donc **rejetée**. Agreste a cessé de compter ces prairies quand elles sont sorties du registre PAC. Son chiffre « hors exploitations » est resté stable, entre 108 981 et 111 685 ha de 2018 à 2022 : il ne les a pas reprises. Nos mesures indiquent donc qu'**Agreste sous-compte environ 15 000 à 19 000 ha de prairies utilisées hors PAC**.

C'est un échantillon de 24 par groupe : la conclusion porte sur la nature de ces prairies, pas sur un pourcentage précis.

Clé et avis versionnés dans `verification/sentinel2/2025/controle_photos/` ; les planches se refont avec `python scripts/photos_herbe_hors_pac.py verification/sentinel2/2025/controle_photos`.

**Limite sur la ligne « sortie depuis 2023 ».** Le registre 2025 contient aussi de l'herbe hors prairies permanentes qu'Agreste compte peut-être dans l'herbe des exploitations :
- surfaces pastorales SPH et SPL : 614 ha ;
- vergers VRG : 7 917 ha, dont des prés-vergers à haute tige, que la statistique classe en « arbres isolés » et compte donc probablement en herbe.

L'herbe des exploitations hors registre selon Agreste est donc comprise entre 29 528 et 38 059 ha, et non exactement 38 059. L'accord « à 211 ha près » n'est pas démontré : l'écart sur cette ligne est compris entre +211 et +8 742 ha.

Source de la définition : Agreste, Statistique agricole annuelle 2025 provisoire, Chiffres et données n° 5, mai 2026, « Champ de la SAA » et « Surfaces toujours en herbe ».

### Bilan de l'écart

| | Hectares |
|---|---:|
| Estimation avec la règle à seuils | 184 384 |
| − bois, landes, roseaux, broussailles reconnus à leur courbe | ≈ −14 400 |
| = herbe reconnue à sa courbe | 170 002 |
| − herbe sortie du registre avant 2023, non comptée par Agreste | −15 318 |
| − déjà déclarée, année de sortie inconnue | −3 381 |
| − jamais déclarée, en plus d'Agreste (6 %) | −6 556 |
| − sortie depuis 2023, en plus d'Agreste | −211 |
| = Agreste | 144 536 |

Le « ≈ −14 400 » est la différence entre deux méthodes : la règle corrigée et le classement par la courbe. Ce n'est pas une somme de morceaux.

## Conséquence pour la page Objectif 2030

Le bilan par origine est sur la page depuis le 11/11. Tous ses chiffres se recalculent avec `python -m prairimetre.sentinel_nuit resumer 2025` (classement par la courbe, origines, contrôle photos), écrits dans `verification/sentinel2/2025/herbe_hors_pac.json`. La somme 113 033 + 38 270 + 15 318 + 3 381 = 170 002 ha.

La ligne « sortie, restée verte » (37 993 ha) utilise la même règle. D'après l'étalonnage, elle compte environ 3 prairies sur 4 parmi celles qui sont vraiment restées en herbe : **c'est un minimum**. Il faudra le dire sur la page, ou corriger ce chiffre de la même façon. À décider.

## Ce qu'on ne sait pas

- Si l'herbe hors registre **diminue** depuis 2021 : on n'a mesuré que 2025.
- La part exacte d'herbe dans la zone grise des morceaux hors PAC : ils ont plus de zone grise que l'herbe sûre, donc ce ne sont pas tous des prés comme ceux des exploitations.

## Vérification : les prairies sorties de la PAC en 2022 (11/11)

**La question.** Des prairies déclarées à la PAC en 2021, l'année de référence de l'objectif, puis plus jamais déclarées, sont-elles toujours en herbe ? Si oui, elles comptent dans la perte officielle alors que la prairie existe encore.

**1. Le chiffre de 4 870 ha était trop haut.** Il venait du point au centre de chaque morceau. Avec la géométrie entière (`scripts/verifier_sortie_2022.py`), sur ces 4 870 ha :

| Part des morceaux au registre PAC | toutes cultures | prairie permanente |
|---|---:|---:|
| 2021 | 4 095 ha | 3 383 ha |
| 2022 | 286 ha | 235 ha |
| 2023 | 71 ha | 56 ha |
| 2024 | 48 ha | 35 ha |

Si l'on ne garde que les morceaux couverts à au moins 50 % par une prairie permanente en 2021 et à moins de 10 % par le registre de 2022 à 2024, il reste **2 831 ha de prairie permanente de 2021**. Le satellite leur trouve une courbe d'herbe en 2025. Dans ces 2 831 ha, 2 050 ha sont aussi « couvert permanent » pour la règle à seuils.

**2. Contrôle sur photos aériennes, à l'aveugle.** On a tiré 24 morceaux de ce groupe (au moins 1 ha) et 24 prairies permanentes déclarées en 2024 et 2025 comme témoins. On les a mélangés, puis jugés sans la clé. Les photos ont été prises entre 2023 et 2026, donc toutes après la sortie de la PAC.

| | prairie fauchée ou pâturée | mélange | douteux | friche | culture | chantier, bâti |
|---|---:|---:|---:|---:|---:|---:|
| Sorties de la PAC en 2022 | 17 | 2 | 2 | 1 | 0 | 2 |
| Témoins, déclarées en 2025 | 18 | 1 | 3 | 0 | 2 | 0 |

En surface, les prairies représentent 83 % de l'échantillon pour les sorties de 2022, contre 77 % pour les témoins. Les sorties de 2022 sont donc des prés utilisés, comme ceux du registre. Deux morceaux sont des chantiers de lotissement, photographiés en juillet et août 2025 : ce sont de vraies pertes, et le satellite les a pris pour de l'herbe.

**3. La statistique agricole.** En 2022, l'herbe des exploitations a baissé de 7 801 ha et le registre de 8 726 ha. L'écart entre les deux est resté stable (6 660 puis 7 585 ha) : la statistique a suivi le registre. L'herbe hors exploitations n'a pas augmenté (−2 370 ha). Ces prairies ont donc très probablement quitté la statistique. On ne peut pas le prouver parcelle par parcelle : le chiffre « hors exploitations » est une estimation.

**Conclusion.** Environ **2 000 à 2 700 ha** de prairies comptées en 2021 sont sorties de la PAC en 2022 et sont toujours des prés utilisés. La fourchette vient de 2 831 ha × la part de prés vue sur photos (71 % en nombre, 83 % en surface), qui provient d'un échantillon de 24. Elles comptent probablement dans les −12 468 ha de la perte officielle. Même sans elles, l'objectif n'est pas tenu (environ −10 000 ha).

Fichiers : `verification/sentinel2/2025/controle_photos_sortie_2022/` (clé, avis) ; planches refaites par `scripts/photos_sortie_2022.py`.

## Bilan final de l'écart, vérifié (11/11, après-midi)

Tout est recalculé par `python -m prairimetre.sentinel_nuit resumer 2025` dans `herbe_hors_pac.json` (clés `origines`, `agreste`, `herbe_ign_usages`, `photos`, `photos_intervalle`, `courbe.confusion_pct`, `courbe.corrige`).

**1. Origine exacte de chaque hectare.** On ne prend plus le point au centre (`origines`) : chaque morceau entier est comparé au registre de chaque année de 2018 à 2024, et on garde la dernière année où la surface y était.

| Herbe hors PAC 2025 (courbe d'herbe) | Point au centre (ancien) | Surface exacte |
|---|---:|---:|
| Jamais déclarée 2018-2024 | 113 033 | **116 048** |
| Sortie avant 2023 (dernière déclaration 2018 à 2021) | 15 318 + 3 381 inconnue | **16 102** (dont 13 212 en prairie permanente) |
| Sortie depuis 2023 (dernière déclaration 2022 à 2024) | 38 270 | **37 852** |
| Total | 170 002 | 170 002 |

**2. Contrôle photo, regroupé par origine exacte.** 2 des 24 morceaux « sortis avant 2023 » étaient en majorité sortis depuis 2023. Une fois regroupés :
- sortis avant 2023 : 19 prés sur 22, soit entre 67 et 95 % (Wilson, 95 %) ;
- sortis depuis 2023 : 23 prés sur 26.

**3. Le classement par la courbe** (validation croisée, en surface) :
- il prend pour de l'herbe 3,0 % des bois et 0,6 % des cultures ;
- il rate 3,0 % de l'herbe.

Corrigée de ces erreurs, l'herbe hors PAC fait 174 292 ha. Le classement ne gonfle donc pas l'écart.

**4. Comparaison avec la statistique agricole.**
- Sortie depuis 2023 : 37 852 contre 38 059 (exploitations moins registre), soit −207 ha. L'écart monte à +8 324 ha si la statistique compte en herbe les 8 531 ha de vergers et surfaces pastorales du registre.
- Le reste : 132 150 (jamais déclarée + sortie avant 2023) contre 106 477 (herbe hors exploitations), soit **+25 673 ha**.

**5. Cause vérifiée : les prés sortis de la PAC avant 2023 (16 102 ha) n'apparaissent pas dans les séries.**
- De 2018 à 2022, l'herbe des exploitations ne dépasse le registre que de 3 928 à 7 585 ha.
- L'herbe hors exploitations passe de 111 590 à 109 315 ha.
- Par département, de 2018 à 2022, elle varie de +993 ha (Calvados, pour 3 943 ha sortis), −171 (Eure), −1 493 (Manche), −724 (Orne) et −880 (Seine-Maritime). Aucun département ne reprend ses sorties.

**6. Non tranché : par département, l'herbe hors exploitations ne suit pas le terrain.** On compare notre « jamais + sortie avant 2023 » à l'herbe hors exploitations d'Agreste 2025 (fichier départemental des séries longues, feuille TER, poste 30) :

| Département | écart |
|---|---:|
| Calvados | +5 384 |
| Eure | −10 486 |
| Manche | +23 530 |
| Orne | +10 547 |
| Seine-Maritime | −3 305 |

Dans l'Eure, toute la végétation hors PAC qu'on a mesurée (herbe 18 013 + bois 6 647 + cultures 3 210 + sans image 128 = 27 998 ha) reste sous l'herbe hors PAC d'Agreste (environ 30 000 ha). Deux raisons possibles, que nos données ne départagent pas :
- **Une estimation départementale.** Par exemple, la Manche passe de 20 409 à 15 585 ha entre 2024 et 2025.
- **Un périmètre différent.** Nous ne cherchons que l'herbe d'usage agricole (US1.1) ou sans usage (US6.3). La carte IGN classe aussi 118 367 ha de couvert herbacé en usage résidentiel (US5) et 23 986 ha en usage tertiaire (US3), registre compris. Des pâtures de particuliers ou de centres équestres peuvent s'y trouver.

**Conclusion.** Sur les 25 466 ha d'écart régional :
- 16 102 ha ont une cause vérifiée ;
- les 9 364 ha restants sont plus petits que les écarts par département, qui vont dans les deux sens. On ne peut pas les expliquer avec nos données.

**Correction de ce qui précède.** « Jamais déclarée ≈ hors exploitations (+6 %) » était un accord régional qui cache des écarts départementaux de −10 486 à +23 530 ha. Il ne faut plus le présenter comme une confirmation.

## Contrôles finaux (11/11, soir)

- **Origine exacte refaite par une autre méthode** (`scripts/verifier_origines.py`). On tire 30 000 points au hasard sur l'herbe hors PAC, puis on cherche la dernière année où chaque point est au registre.

  | | Points tirés au hasard | `origines()` |
  |---|---:|---:|
  | Jamais déclarée | 116 043 ± 895 | 116 048 |
  | Sortie avant 2023 | 16 031 ± 562 | 16 102 |
  | Sortie depuis 2023 | 37 927 ± 801 | 37 852 |
  | dont prairie permanente la dernière année (sortie avant 2023) | 13 306 | 13 212 |

  Les deux méthodes concordent à l'erreur de tirage près.
- **Statistique agricole.** Les séries régionales 2018-2025 (exploitations et hors exploitations) sont égales, au hectare près, à la somme des cinq départements du fichier départemental officiel d'Agreste.
- **Registre PAC.** Les prairies permanentes 2018-2025 sont recalculées depuis les fichiers du registre : mêmes valeurs.
- **Autres chiffres affichés** : SPH + SPL (614 ha) et VRG (7 917 ha) sont recalculés ; les 48 avis photo sont présents ; l'intervalle de Wilson pour 19 sur 22 va de 66,7 à 95,3 %.
- **Sommes.** Les sommes par département et par année retombent sur les totaux, à 3 ha près (arrondis).

La page Objectif 2030 tient maintenant sur un seul écran. Le détail (textes, tableau détaillé, causes de l'écart, méthode et sources d'erreur) s'ouvre dans des fenêtres. Ancienne version : `app/sauvegardes/objectif_avant_une_page_2026-11-11.py`.
