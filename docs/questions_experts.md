# Questions à poser aux experts

Point d'étape avec les experts, semaine du 2 novembre 2026. Contacts côté Région :
`Consignes/notes_réunion.txt`.

Chaque question ci-dessous change un chiffre, une liste ou un conseil affiché par l'application.
Pour chacune : ce qui en dépend, à qui la poser, et où modifier l'outil selon la réponse. Le reste
se recalcule seul (`python -m prairimetre calculer` puis `evaluer`).

Chiffres cités : registre parcellaire 2018 → 2025, résultats du 30 octobre 2026.

## A. Obligatoires : un chiffre affiché en dépend

### 1. Quelle est l'année de référence de l'objectif « zéro perte nette » en 2030 ?

- **À qui** : Région.
- **Ce qui en dépend** : l'outil a pris 2022, l'année d'adoption de la stratégie régionale
  biodiversité, sans confirmation. Avec 2022, il manque 29 878 ha. Il faudrait donc regagner
  environ 6 000 ha par an d'ici 2030 : c'est le premier chiffre de la page « Où agir ».
- **Où modifier** : `ANNEE_REFERENCE_OBJECTIF` dans `prairimetre/config.py`.
- **Réponse** :

### 2. L'objectif se mesure-t-il sur les prairies déclarées à la PAC ?

- **À qui** : Région, DRAAF.
- **Ce qui en dépend** : l'outil compte les prairies permanentes déclarées à la PAC (registre
  parcellaire, groupe de cultures 18). Il trouve −60 050 ha entre 2018 et 2025, contre −59 703 ha
  pour le chiffre officiel. Si l'objectif vise toutes les prairies, déclarées ou non, le compteur
  en sous-estime le niveau. Il faudra alors le dire sur chaque page.
- **Où modifier** : texte de l'en-tête de « Où agir » et page Lexique et définitions (`app/vues/`).
- **Réponse** :

### 3. Les zones humides du programme d'actions nitrates interdisent-elles le retournement ?

- **À qui** : DREAL, DDT(M), chambre d'agriculture.
- **Ce qui en dépend** : l'outil range ces zones (couche « zones humides, petites régions
  agricoles de l'est ») parmi les **règles** qui encadrent le labour. Elles couvrent 9,5 % des
  prairies. Si ce n'est qu'un inventaire, deux affirmations sont à recalculer : « les règles
  couvrent 14 % des prairies » et « on y retourne environ 5 fois moins ».
- **Où modifier** : `FAMILLES` dans `prairimetre/donnees.py` (passer la couche de `regle` à
  `inventaire`).
- **Réponse** :

### 4. Comment compter les prairies sorties de la déclaration dans l'objectif ?

- **À qui** : Région, DDT(M), DRAAF.
- **Ce qui en dépend** : 55 539 ha de prairies de 2018 ne sont plus déclarées en 2025, sans être
  devenues des cultures déclarées. Selon l'OCS GE de l'IGN, 89 % restent des terres agricoles
  l'année de leur sortie et moins de 1 % sont construites ; mais l'OCS GE range prairies et
  cultures dans la même classe, donc on ne sait pas si l'herbe est encore là. L'outil conseille de
  les vérifier avant de les compter comme perdues (Carte des données, « Où il faut des données »).
- **À demander aussi** : les DDT(M) ou l'ASP savent-elles ce que deviennent ces parcelles
  (changement d'exploitant, chevaux, fin de déclaration) ? Peuvent-elles partager l'information ?
- **Où modifier** : selon la réponse, le conseil du moyen 1 et la vue « Où il faut des données ».
- **Réponse** :

### 5. Qui publie le ratio de prairies permanentes, et quand ?

- **À qui** : DRAAF.
- **Ce qui en dépend** : le ratio officiel (−1,97 %, arrêté de septembre 2026) est le seul chiffre
  que l'outil ne recalcule pas : il est saisi à la main. Il fonde la phrase « le ratio ne
  déclenche pas d'alerte ». Il faut savoir quand le mettre à jour, et si une série par
  département existe.
- **Où modifier** : `OFFICIEL` dans `app/commun.py`.
- **Réponse** :

### 6. Faut-il joindre les données à la remise ?

- **À qui** : organisateurs du datathon.
- **Ce qui en dépend** : le règlement (§ 4) demande le code **et** les données utilisées. Les
  données pèsent environ 6,7 Go, et un seul registre annuel dépasse 300 Mo. Le script
  `importer_donnees.py` les retélécharge toutes depuis leurs sources officielles, et
  `data/manifest.json` trace chaque fichier. Ce script et ce manifeste suffisent-ils, ou faut-il
  livrer les fichiers ? Si oui, sous quel format et quelle taille maximale ?
- **Où modifier** : `python -m prairimetre livrer` (ajouter `--avec-donnees` si besoin).
- **Réponse** :

## B. Utiles : elles affinent un réglage

### 7. Le seuil de 20 ha pour classer une commune est-il le bon ?

- **À qui** : Région, chambre d'agriculture.
- **Ce qui en dépend** : 267 communes ont moins de 20 ha de prairies, ou aucune. Elles ne sont
  pas classées, et apparaissent en noir sur les cartes. Avec un seuil de 10 ha, 2 484 communes
  seraient classées ; avec 50 ha, 2 068 (contre 2 377 aujourd'hui).
- **Où modifier** : `MIN_HA` dans `prairimetre/config.py`.
- **Réponse** :

### 8. Trois ans, est-ce la bonne durée pour la période « récente » ?

- **À qui** : Région, chambre d'agriculture.
- **Ce qui en dépend** : les listes de « Payer le maintien » se fondent sur les trois dernières
  années. Sur les 50 communes qui retournent le plus, 38 restent dans la liste avec deux ans,
  44 avec quatre ans.
- **Où modifier** : `RECENT` dans `prairimetre/config.py`.
- **Réponse** :

### 9. Qui contacter pour chaque aire de captage ?

- **À qui** : Agences de l'eau, ARS.
- **Ce qui en dépend** : le maître d'ouvrage manque dans le Sandre pour 129 aires sur 165, et le
  service de l'État pour 58. L'outil renvoie alors vers l'Agence de l'eau du bassin. Existe-t-il
  une liste plus complète des animateurs de captage ?
- **Où modifier** : source `aires_alimentation_captages`, ou une table de contacts à ajouter.
- **Réponse** :

### 10. Quels dispositifs financent réellement le maintien des prairies, et qui les porte ?

- **À qui** : Région, Agences de l'eau, chambre d'agriculture.
- **Ce qui en dépend** : le moyen 2 conseille de « payer le maintien de l'herbe » (mesures
  agro-environnementales, paiements pour services environnementaux). Il faut nommer les bons
  dispositifs et les bons financeurs, avec leurs conditions (zones éligibles, montants).
- **Où modifier** : `ACTIONS` dans `app/commun.py` et le texte du moyen 2.
- **Réponse** :

### 11. Une commune sans perte nette est-elle un bon exemple ?

- **À qui** : chambre d'agriculture, parcs naturels régionaux.
- **Ce qui en dépend** : le moyen 3 désigne comme exemples les 541 communes qui n'ont pas perdu de
  prairies depuis 2018. Un solde positif peut tenir à des échanges de terres plutôt qu'à des
  pratiques. Connaissez-vous des groupes d'éleveurs ou des communes reconnus, à croiser avec
  cette liste ?
- **Où modifier** : critère `mecanisme` (`prairimetre/indicateurs.py`), ou une liste à ajouter.
- **Réponse** :

### 12. Les habitats prairiaux sont-ils cartographiés dans l'Eure et en Seine-Maritime ?

- **À qui** : DREAL, conservatoire botanique compétent.
- **Ce qui en dépend** : la cartographie des habitats d'intérêt européen n'existe, dans nos
  données, que pour les sites Natura 2000 du Calvados, de la Manche et de l'Orne (251 communes).
  Les deux autres départements sont en noir sur la Carte des données.
- **Où modifier** : `python -m prairimetre importer habitats_natura2000 <fichier>`.
- **Réponse** :

### 13. Peut-on montrer la carte des parcelles sur la fiche d'une commune ?

- **À qui** : chambre d'agriculture, Région.
- **Ce qui en dépend** : la fiche « Ma commune » montre chaque parcelle (registre public et
  anonyme de l'IGN, sans nom d'exploitant). Dans une petite commune, une parcelle reste
  reconnaissable. La diffusion pose-t-elle problème aux acteurs agricoles ?
- **Où modifier** : la carte des parcelles de `app/vues/commune.py`.
- **Réponse** :

## C. À trancher dans le binôme (pas aux experts)

- Licence du code : MIT proposée (fichier `LICENSE` prêt, pas encore commité).
- Garder ou non `data/_hors_perimetre/` (3,8 Go de données écartées).
