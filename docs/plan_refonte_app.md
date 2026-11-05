# Prairimètre — plan de refonte de l'app et intégration du détecteur satellite

Établi le 4 novembre 2026, à partir du code de la branche `test-app-v1` (app Streamlit, moteur, `sorties/`).
Mis à jour le 5 novembre (3 fois) : la page « Ma commune » est terminée et **n'est plus modifiée** ; le menu est déjà un
bandeau en haut ; le fond de carte est toujours affiché (l'interrupteur est supprimé). Menu cible : **Normandie ·
Ma commune · Technique** ; le Lexique est supprimé, et la vérification des parcelles vit dans le mode
« Où mesurer » de la page Normandie (sections 3.5 et 3.6).
Le code du détecteur satellite n'est pas dans le dépôt : tout ce qui le concerne ci-dessous repose sur un
contrat d'interface à valider avec Mouhssine (section 2).

---

## 1. Pourquoi l'app actuelle se lit mal

Chiffres relevés dans le code :

| Constat | Détail |
|---|---|
| 5 pages + 3 sous-onglets | Où agir, Ma commune, Carte des données, Données et méthode (Preuves / Sources / Moteur), Lexique |
| Jusqu'à 8 cartes | 1 dans Où agir, 4 petites + 2 grandes dans Carte des données, 1 dans Ma commune |
| Des dizaines de combinaisons de filtres | Où agir : 3 moyens × 3 échelles × 3 critères × 6 territoires × 3 tailles de liste |
| Un même code couleur pour des choses différentes | Bleu = « payer », vert = « exemples », orange = « vérifier » ; noir = pas de donnée, gris = peu de prairies, gris clair = hors liste |
| Du vocabulaire d'expert | mécanisme, moyen d'agir, zonage d'enjeux, brut/net, BCAE, ratio, sortie de la déclaration |
| Chaque « moyen » = 5 rubriques de texte | Le conseil, Pourquoi, Pour qui, Où, Indicateur de suivi |

Le fond est bon (moteur, chiffres vérifiés, tests). Le problème est la présentation : l'information est
**découpée** (une page, une carte, un filtre par sous-question) alors qu'elle devrait être **concentrée**
(une carte, un bouton par sous-question).

Le message qui devrait sauter aux yeux, et qui est aujourd'hui noyé :

> Depuis 2018, environ 55 000 ha de prairies ont été **retournés en culture** (perte certaine) et environ
> 55 000 ha **ne sont plus déclarés** (on ne sait pas si l'herbe est encore là).
> 237 communes sur 2 377 portent à elles seules la moitié de ces « on ne sait pas ».

C'est exactement le trou que le détecteur satellite peut combler.

---

## 2. Le détecteur satellite : ce qui est faisable

### 2.1 Ce qu'il doit répondre

Une seule question, parcelle par parcelle : **« est-ce encore de l'herbe ? »**, avec un niveau de confiance.
Cible principale : les ≈ 12 000 prairies de 2018 d'au moins 1 ha dont 90 % ont quitté la déclaration
(55 539 ha au total en « sortie de la déclaration »).

Il ne dit pas « permanente » ou « temporaire » (une image seule ne le permet pas) : il dit « herbe » ou
« pas herbe ». Il faut l'écrire ainsi dans l'app.

### 2.2 Contrat d'interface (à valider)

Pour que l'app reste indépendante du modèle, un seul fichier d'échange, par parcelle :

| Colonne | Contenu |
|---|---|
| `id_rpg_2018` | identifiant de la parcelle (celui du RPG 2018, comme dans `docs/verification_parcelles.md`) |
| `insee` | commune |
| `ha` | surface |
| `p_herbe` | probabilité entre 0 et 1 que la parcelle soit encore en herbe |
| `date_image`, `version_modele` | pour la traçabilité (« comment quelqu'un d'autre refait la vérification ») |

Fichier : `sorties/detecteur_parcelles.parquet`. Le moteur en tire une table par commune
(`sorties/detecteur_communes.csv`) ; l'app ne lit que celle-là, comme pour les autres tables.

Trois états, seuils réglables dans `config.py` (point de départ : 0,8 et 0,2) :
**encore de l'herbe** (p ≥ 0,8), **perdue** (p ≤ 0,2), **on ne sait toujours pas** (entre les deux).

### 2.3 Le benchmark : trois niveaux de vérité

| Niveau | Jeu de vérification | Ce qu'il prouve | Limite |
|---|---|---|---|
| A. Déclaré | Parcelles RPG 2025 « prairie permanente » contre « culture », toute la Normandie | Le modèle sait distinguer herbe et culture en général | Étiquette déclarée, donc bruitée ; ne ressemble pas aux parcelles « sorties » |
| B. Terrain | Points LUCAS 2022 (911 points restés en prairie, 9 retournés, 11 sortis) | Vérité indépendante du registre | Seulement 11 points sur les sorties : trop peu pour conclure seul |
| C. À la main | Les 30 parcelles de `docs/verification_parcelles.md`, à compléter jusqu'à ≈ 100 | Le seul test sur le cas qui nous intéresse | Annotation manuelle, donc petit effectif |

Règles pour que le benchmark soit honnête :

1. **Piège du « tout est herbe ».** Sur les 11 points LUCAS de sorties, 9 sont en herbe (≈ 82 %). Un modèle
   qui répond toujours « herbe » aurait donc 82 % de bonnes réponses. Il faut rapporter le **rappel de la
   classe « pas herbe »**, pas seulement la précision globale.
2. **Trois points de comparaison simples** que le modèle doit battre : « tout est herbe » ; l'OCS GE de l'IGN
   (89 % des sorties restent « terres agricoles », sans distinguer herbe et culture) ; un seuil de
   végétation (NDVI) saisonnier basique. Si le modèle ne bat pas le troisième, il faut le savoir.
3. **Validation par blocs géographiques** (entraîner sur trois départements, tester sur les deux autres), sinon
   le modèle « reconnaît » des voisins de parcelle et le score est gonflé.
4. **Calibration** : quand le modèle dit 80 %, il doit avoir raison 80 % du temps. C'est cela, « un niveau de
   confiance correct ».
5. **Un graphique central** : courbe *précision en fonction de la part des hectares tranchés* (en relevant le
   seuil de confiance, on tranche moins d'hectares mais on se trompe moins). C'est la figure qui répond au jury.

### 2.4 Faire monter le pourcentage : où regarder

Indicateur unique à afficher : **la part des hectares sortis dont on connaît le sort avec confiance**
(« taux de connaissance »). Aujourd'hui il est quasi nul. Le détecteur le fait monter ; l'app doit surtout dire
**où l'améliorer le plus vite** :

| Où chercher | Pourquoi | Comment le calculer |
|---|---|---|
| Communes qui portent le plus d'hectares incertains | Chaque parcelle tranchée y rapporte le plus | Tri de `ha × (état = incertain)` par commune ; 237 communes = 50 % des sorties, 100 communes = 32 % |
| Parcelles juste au milieu (p ≈ 0,5) et grandes | Une annotation manuelle y change le plus le résultat | Tri par incertitude × surface ; export CSV de la liste des parcelles à vérifier (id RPG + coordonnée, même format que le document de vérification) |
| Territoires où le modèle est moins bon | Petites parcelles, bocage dense, nuages | Score du benchmark par département puis par taille de parcelle |
| Communes sans aucune donnée de terrain | Aucun point LUCAS, aucune parcelle annotée | Croisement LUCAS × communes (déjà codé dans `vues/donnees.py`) |

Ce sont des **tris simples**, pas de l'optimisation : cela reste dans le périmètre « travail de data » décidé.

### 2.5 Ce qui n'est pas faisable (ou à éviter)

- Faire tourner le modèle en direct dans l'app : trop lent. Précalculer et lire un fichier.
- Distinguer prairie permanente et temporaire avec une seule image.
- Parcelles de moins de ≈ 0,5 ha : un pixel Sentinel-2 fait 10 m (0,01 ha), le signal est trop pauvre. Les écarter
  et le dire (le tirage des 30 parcelles est déjà à ≥ 1 ha).
- Afficher les images satellite brutes de toutes les parcelles : choisir quelques parcelles d'exemple.

---

## 3. La nouvelle app : une carte, quatre boutons

### 3.1 Principe

**Une page « Normandie », une seule carte.** Les boutons changent ce que la carte colore ; ils ne changent pas
de page. Un clic sur une commune affiche à côté de la carte une mini-fiche (nom, 3 chiffres) avec un lien vers
la page « Ma commune », qui reste la fiche complète et n'est pas modifiée.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ 🌿 Prairimètre            Depuis 2018 : 55 000 ha retournés · 55 000 ha à vérifier  │
├──────────────────────────────────────────────────────────────────────────┤
│  [ Ce qu'on a perdu ] [ Ce qu'on ne sait pas ] [ Où mesurer ] [ Les bons exemples ] │
├──────────────────────────────────────────────┬───────────────────────────┤
│                                              │  Phrase du mode, 1 ligne  │
│                                              │  « Quoi faire »           │
│              LA CARTE                        │  ───────────────────────  │
│     (communes ou intercommunalités)          │  Options                  │
│                                              │  ▸ Territoire  [Normandie]│
│   légende : 3 couleurs maximum               │  ▸ Niveau  (communes|EPCI)│
│                                              │  ▸ Fond  (plan | photo)   │
│                                              │  ▸ Top N  ──●──           │
│                                              │  ───────────────────────  │
│                                              │  Mini-fiche (3 chiffres)  │
│                                              │  [ Voir Ma commune → ]    │
│                                              │  [⬇ Télécharger la liste] │
└──────────────────────────────────────────────┴───────────────────────────┘
        Menu en haut : Normandie · Ma commune (inchangée) · Technique
```

### 3.2 Les quatre boutons

| Bouton | Ce que la carte colore | Remplace dans l'app actuelle |
|---|---|---|
| **Ce qu'on a perdu** | Hectares retournés en culture par commune (du jaune pâle au rouge). Un bouton « en hectares / en % » | Où agir, moyen 2 « Payer le maintien » (listes, 3 critères, 3 échelles) |
| **Ce qu'on ne sait pas** | Pour chaque commune, l'état du sort des prairies sorties : vert « encore de l'herbe », rouge « perdue », orange « on ne sait toujours pas » (avec le détecteur) | Où agir, moyen 1 (partie « sorties ») + Carte des données, besoin 1 |
| **Où mesurer** | Priorité de mesure : les communes où le plus d'hectares sont sortis de la déclaration (puis, avec le détecteur, où le plus d'hectares restent incertains). C'est ici que sert l'outil par images satellite (3.6) | Carte des données, besoins 1 et 2 + les 4 petites cartes de sources |
| **Les bons exemples** | Communes qui n'ont pas perdu de prairies depuis 2018 (vert) | Où agir, moyen 3 |

Le graphique de l'objectif 2030 (courbe d'hectares, niveau à retrouver) passe dans l'en-tête, en petit : c'est
le moyen 1 « Suivre l'objectif », qui n'est pas une carte mais un compteur.

### 3.3 Règles pour qu'un enfant de 10 ans comprenne

1. **Un code couleur, partout, celui de « Ma commune »** (`FLUX_COULEURS`) : rouge = retournée en culture,
   orange = sortie de la déclaration (on ne sait pas), vert = toujours en prairie, noir = pas de donnée.
   Plus de bleu/vert/orange réutilisés pour des sens différents, plus de trois gris.
2. **Un chiffre géant par écran**, écrit en phrase : « 55 000 ha, c'est environ 20 fois la ville de Caen ». L'app a
   déjà `fois_caen()` : le garder.
3. **Une phrase d'action** par bouton, avec le mot « quoi » : « Là, on peut payer les éleveurs pour garder
   l'herbe. » Remplace les 5 rubriques (Conseil / Pourquoi / Pour qui / Où / Indicateur).
4. **Vocabulaire identique à « Ma commune »** : « retournée en culture », « sortie de la déclaration »,
   « toujours en prairie ». Ne pas inventer d'autres mots d'une page à l'autre. « mécanisme », « zonage d'enjeux »,
   « brut/net » : sortis de la page principale, les mots difficiles restent en info-bulle là où ils apparaissent (pas de page Lexique).
5. **Jamais de case vide** : règle déjà en place dans `commun.py`, à conserver.
6. **Les options dans un seul endroit** (panneau de droite ou `st.popover`), quatre au maximum : territoire,
   niveau, fond de carte, nombre de communes dans la liste.

### 3.4 Fond « photo aérienne »

Un bouton Plan / Photo sur la carte. La photo aérienne de l'IGN (licence ouverte) permet de voir pourquoi une
parcelle est « incertaine » et rend la fiche commune bien plus parlante. À tester d'abord : dépend de l'accès réseau
et du service de tuiles de l'IGN. Elle sert dans le mode « Où mesurer » pour regarder les parcelles d'une commune. L'ancien interrupteur « Fond de carte » est supprimé : le fond « plan » est
toujours affiché (sans internet, les cartes restent vides) ; le bouton Plan / Photo ne concerne que la nouvelle carte.

### 3.5 Trois pages au lieu de cinq, dans le bandeau du haut

| Page | Rôle en une phrase | Contenu |
|---|---|---|
| **Normandie** (accueil) | « Où est-ce que ça disparaît, et où faut-il mesurer ? » | les quatre boutons (perdu / on ne sait pas / où mesurer / bons exemples), la mini-fiche, l'export |
| **Ma commune** | « Et chez moi ? » | **Inchangée** (décision du 5 novembre) |
| **Technique** | « Peut-on se fier à ces chiffres ? » | 4 mini-onglets : **Les preuves**, **D'où viennent les données**, **Les chiffres officiels**, **Recalculer** (voir 3.7) |

Noms choisis pour se lire sans explication : un lieu (Normandie, Ma commune), puis un mot d'ingénieur isolé dans
un seul bouton (Technique). « Où agir », « Carte des données », « Données et méthode » et « Lexique et
définitions » disparaissent. Il n'y a pas de page dédiée à la vérification d'une parcelle isolée : la cible, ce
sont les lieux où il y a eu le plus de sorties de la déclaration (décision du 5 novembre).

### 3.6 Le mode « Où mesurer » (là où sert le détecteur satellite)

Question posée à l'écran : **« Où faut-il aller mesurer pour savoir ce que sont devenues les prairies sorties de
la déclaration ? »**

1. **La carte** colore les communes selon les hectares sortis de la déclaration depuis 2018 (du jaune pâle au
   orange foncé). Un curseur « Top N » (10, 50, 100 communes) met en avant les plus touchées : 237 communes
   sur 2 377 portent la moitié des sorties.
2. **Au clic sur une commune** : le nombre d'hectares et de parcelles sortis, et ce que dit le détecteur
   (barre à trois états : encore de l'herbe / perdue / on ne sait toujours pas, quand il sera branché).
3. **Les parcelles à mesurer** : la liste des plus grandes parcelles sorties de la commune, vues sur photo
   aérienne, avec un export CSV (id RPG 2018 + coordonnées, même format que `docs/verification_parcelles.md`).
4. **Le chiffre qui suit le progrès** : « part des hectares sortis dont on connaît le sort avec confiance »
   (le taux de connaissance de 2.4), en haut de la page.
5. **Avant le détecteur** : le mode fonctionne déjà avec le seul classement par hectares sortis ; le détecteur
   ajoute la barre à trois états et remplace le tri par « hectares incertains ».

Le contrôle à la main (30 parcelles, puis environ 100) se fait **hors de l'app**, dans un fichier par personne
(`verifications/hippolyte.csv`, `verifications/mouhssine.csv`), à partir du document de vérification. Son résultat
et celui du benchmark s'affichent dans Technique → Les preuves.

Limite à écrire sur la page : une photo aérienne n'a pas toujours été prise en 2025 ; une image trop ancienne ne
permet pas de conclure.

### 3.7 La page « Technique »

Un seul bouton dans le menu, quatre mini-onglets, rien d'autre :

| Mini-onglet | Reprend |
|---|---|
| **Les preuves** | les 4 questions de l'onglet Preuves actuel (le compteur est-il fiable, les règles, la concentration, la reproductibilité) + « ce que l'outil ne sait pas » ; plus tard, la fiabilité du détecteur (benchmark, courbe précision/couverture) et le résultat du contrôle à la main |
| **D'où viennent les données** | l'onglet Sources actuel (liste, producteur, date de mise à jour) |
| **Les chiffres officiels** | le tableau « quatre chiffres, quatre définitions » du Lexique actuel (Prairimètre, chiffre officiel, ratio, statistique agricole) et sa note sur PPH et PRL. C'est la seule partie du Lexique qui répond à une vraie question (« pourquoi vos chiffres diffèrent des officiels ? ») |
| **Recalculer** | l'onglet Moteur actuel (nouveau registre, recalcul d'une année), inchangé |

---

## 4. Ce qui est refait, gardé, supprimé

| Élément actuel | Décision |
|---|---|
| `prairimetre/` (moteur), `sorties/`, tests | **Gardés tels quels.** On ajoute `detecteur.py` + 1 table |
| `commun.py` : `deck`, `communes_carte`, `epci_carte`, formats, `nombre/ha/pct` | **Gardés.** On y ajoute une fonction `carte_data(mode, niveau, dep)` qui renvoie la table à colorer |
| `vues/prairies.py` (Où agir) | **Refait** : devient la page « Normandie ». Les 3 fonctions `suivre/payer/exemple` deviennent 3 des 4 modes |
| `vues/donnees.py` (Carte des données) | **Refait** : les 4 petites cartes disparaissent ; les 2 grandes cartes deviennent le mode « Où mesurer » (3.6). Les 8 compteurs deviennent 3 |
| `vues/commune.py` (Ma commune) | **Gardée telle quelle.** Aucune modification, y compris quand le détecteur arrivera (toute évolution se décide à part) |
| `vues/methode.py` | **Devient la page « Technique »** (4 mini-onglets, contenu repris tel quel) |
| `vues/lexique.py` | **Supprimée (fait le 5 novembre).** Dans Technique : trois chiffres et les mots, une ligne par mot |
| Fiche captage (`fiche_captage`) | **Option** « Eau potable » du mode « Ce qu'on a perdu » (filtre), plus une échelle à part |
| Habitats prairiaux (besoin 2) | **Déplacé** dans « Technique » → Les preuves (limites). Ne répond pas à la question centrale |
| Bandeau SVG, `signature()` | Bandeau **réduit** à une ligne de titre ; signature gardée |
| Menu latéral, interrupteur « Fond de carte » | **Déjà fait** : menu en bandeau en haut, fond toujours affiché |

---

## 5. Ordre de travail

Tailles : S < ½ jour, M ≈ 1 jour, L ≈ 2 jours. Date limite de remise non connue : l'ordre suit la valeur.

| # | Tâche | Taille | Dépend de |
|---|---|---|---|
| 1 | Valider le contrat d'interface du détecteur avec Mouhssine (format, date d'image, précision actuelle) | S | — |
| 2 | Nouvelle page « Normandie » avec modes 1, 2 (sans détecteur : « on ne sait pas » en orange) et 4 | M–L | — |
| 3 | Mini-fiche au clic sur la carte + lien vers Ma commune | S | 2 |
| 4 | Menu renommé (Normandie · Ma commune · Technique), Lexique supprimé, page « Technique » à 4 mini-onglets | S | — |
| 5 | Benchmark niveaux A et B + courbe précision/couverture | M | 1 |
| 6 | Intégration du détecteur dans les modes « Ce qu'on ne sait pas » et « Où mesurer » (3 états) et dans le compteur d'en-tête | M | 1, 2, 7 |
| 7 | Mode « Où mesurer » : classement des communes par hectares sortis, liste des parcelles à mesurer sur photo aérienne, export CSV (version sans détecteur) | M | 2, 9 |
| 8 | Contrôle à la main hors de l'app : les 30 parcelles puis ≈ 70 de plus, un fichier par personne (benchmark niveau C) | L | — (à faire en parallèle) |
| 9 | Fond « photo aérienne » dans `deck()` (sert au mode « Où mesurer ») | S | — |
| 10 | Vérification : parcourir l'app avec quelqu'un qui ne connaît pas le projet, noter où il hésite | S | 2–7 |

Les tâches 2, 4, 7, 8 et 9 peuvent démarrer tout de suite, sans attendre le détecteur. Ordre conseillé : 4 (rapide),
puis 9, 2 et 7 (la page Normandie avec le mode « Où mesurer »), pendant que 8 avance en parallèle.

---

## 6. À décider ou à vérifier

1. **Format de sortie du détecteur** : `p_herbe` par parcelle RPG 2018 est supposé. À confirmer.
2. **Quelles images, quelle date** : une image d'été 2025 par parcelle suffit-elle, ou une série sur plusieurs années ?
3. **Précision actuelle du modèle** et sur quel jeu elle a été mesurée (déclaré, LUCAS, manuel ?).
4. **Taille de l'annotation manuelle** : 30 parcelles seulement, ou ≈ 100 ? Moins de 50 rend le niveau C peu concluant.
5. **Parcelles de moins de 1 ha** : écartées du détecteur (recommandé) ou comptées « incertaines » ?
6. **Présélection de la commune** : le lien « Voir Ma commune » ouvre la page sans la commune cliquée, sauf à ajouter
   une ligne dans `vues/commune.py`. Par défaut la page n'est pas touchée.
