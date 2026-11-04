# Prairimètre — plan de refonte de l'app et intégration du détecteur satellite

Établi le 4 novembre 2026, à partir du code de la branche `test-app-v1` (app Streamlit, moteur, `sorties/`).
Mis à jour le 5 novembre : la page « Ma commune » est terminée et **n'est plus modifiée** ; le menu est déjà un
bandeau en haut ; le fond de carte est toujours affiché (l'interrupteur est supprimé).
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

**Une page « La carte », une seule carte.** Les boutons changent ce que la carte colore ; ils ne changent pas
de page. Un clic sur une commune affiche à côté de la carte une mini-fiche (nom, 3 chiffres) avec un lien vers
la page « Ma commune », qui reste la fiche complète et n'est pas modifiée.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ 🌿 Prairimètre            Depuis 2018 : 55 000 ha retournés · 55 000 ha à vérifier  │
├──────────────────────────────────────────────────────────────────────────┤
│  [ Ce qu'on a perdu ] [ Ce qu'on ne sait pas ] [ Où chercher ] [ Les bons exemples ] │
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
        Menu en haut : La carte · Ma commune (inchangée) · Comprendre (fiabilité du détecteur, méthode, sources, lexique)
```

### 3.2 Les quatre boutons

| Bouton | Ce que la carte colore | Remplace dans l'app actuelle |
|---|---|---|
| **Ce qu'on a perdu** | Hectares retournés en culture par commune (du jaune pâle au rouge). Un bouton « en hectares / en % » | Où agir, moyen 2 « Payer le maintien » (listes, 3 critères, 3 échelles) |
| **Ce qu'on ne sait pas** | Pour chaque commune, l'état du sort des prairies sorties : vert « encore de l'herbe », rouge « perdue », orange « on ne sait toujours pas » (avec le détecteur) | Où agir, moyen 1 (partie « sorties ») + Carte des données, besoin 1 |
| **Où chercher** | Priorité de collecte : les communes où des hectares incertains pèsent le plus. Liste exportable des parcelles à vérifier | Carte des données, besoins 1 et 2 + les 4 petites cartes de sources |
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
   « brut/net » : sortis de la page principale, définis dans « Comprendre ».
5. **Jamais de case vide** : règle déjà en place dans `commun.py`, à conserver.
6. **Les options dans un seul endroit** (panneau de droite ou `st.popover`), quatre au maximum : territoire,
   niveau, fond de carte, nombre de communes dans la liste.

### 3.4 Fond « photo aérienne »

Un bouton Plan / Photo sur la carte. La photo aérienne de l'IGN (licence ouverte) permet de voir pourquoi une
parcelle est « incertaine » et rend la fiche commune bien plus parlante. À tester d'abord : dépend de l'accès réseau
et du service de tuiles de l'IGN. L'ancien interrupteur « Fond de carte » est supprimé : le fond « plan » est
toujours affiché (sans internet, les cartes restent vides) ; le bouton Plan / Photo ne concerne que la nouvelle carte.

### 3.5 Trois pages au lieu de cinq, dans le bandeau du haut

| Page | Contenu |
|---|---|
| **La carte** (accueil) | les quatre boutons, la mini-fiche, l'export |
| **Ma commune** | **Inchangée** (décision du 5 novembre) |
| **Comprendre** | Fiabilité du détecteur (benchmark, courbe précision/couverture) · les preuves actuelles · sources · lexique · moteur (nouveau registre). En sections repliables, pas en 3 onglets |

---

## 4. Ce qui est refait, gardé, supprimé

| Élément actuel | Décision |
|---|---|
| `prairimetre/` (moteur), `sorties/`, tests | **Gardés tels quels.** On ajoute `detecteur.py` + 1 table |
| `commun.py` : `deck`, `communes_carte`, `epci_carte`, formats, `nombre/ha/pct` | **Gardés.** On y ajoute une fonction `carte_data(mode, niveau, dep)` qui renvoie la table à colorer |
| `vues/prairies.py` (Où agir) | **Refait** : devient la page « La carte ». Les 3 fonctions `suivre/payer/exemple` deviennent 3 des 4 modes |
| `vues/donnees.py` (Carte des données) | **Refait** : les 4 petites cartes disparaissent ; les 2 grandes cartes deviennent le mode « Où chercher ». Les 8 compteurs deviennent 3 |
| `vues/commune.py` (Ma commune) | **Gardée telle quelle.** Aucune modification, y compris quand le détecteur arrivera (toute évolution se décide à part) |
| `vues/methode.py` + `lexique.py` | **Fusionnés** en page « Comprendre » |
| Fiche captage (`fiche_captage`) | **Option** « Eau potable » du mode « Ce qu'on a perdu » (filtre), plus une échelle à part |
| Habitats prairiaux (besoin 2) | **Déplacé** dans « Comprendre » (limites). Ne répond pas à la question centrale |
| Bandeau SVG, `signature()` | Bandeau **réduit** à une ligne de titre ; signature gardée |
| Menu latéral, interrupteur « Fond de carte » | **Déjà fait** : menu en bandeau en haut, fond toujours affiché |

---

## 5. Ordre de travail

Tailles : S < ½ jour, M ≈ 1 jour, L ≈ 2 jours. Date limite de remise non connue : l'ordre suit la valeur.

| # | Tâche | Taille | Dépend de |
|---|---|---|---|
| 1 | Valider le contrat d'interface du détecteur avec Mouhssine (format, date d'image, précision actuelle) | S | — |
| 2 | Nouvelle page « La carte » avec modes 1, 2 (sans détecteur : « on ne sait pas » en orange) et 4 | M–L | — |
| 3 | Mini-fiche au clic sur la carte + lien vers Ma commune | S | 2 |
| 4 | Page « Comprendre » (fusion méthode + lexique + sources + moteur) | S | — |
| 5 | Benchmark niveaux A et B + courbe précision/couverture | M | 1 |
| 6 | Intégration du détecteur dans le mode 2 (3 états) et dans le compteur d'en-tête | M | 1, 2 |
| 7 | Mode « Où chercher » + export des parcelles à vérifier | M | 6 |
| 8 | Annotation manuelle des 30 parcelles, puis ≈ 70 de plus (benchmark niveau C) | L | — (à faire en parallèle) |
| 9 | Bouton fond « photo aérienne » | S | 2 |
| 10 | Vérification : parcourir l'app avec quelqu'un qui ne connaît pas le projet, noter où il hésite | S | 2–7 |

Les tâches 2, 4 et 8 peuvent démarrer tout de suite, sans attendre le détecteur.

---

## 6. À décider ou à vérifier

1. **Format de sortie du détecteur** : `p_herbe` par parcelle RPG 2018 est supposé. À confirmer.
2. **Quelles images, quelle date** : une image d'été 2025 par parcelle suffit-elle, ou une série sur plusieurs années ?
3. **Précision actuelle du modèle** et sur quel jeu elle a été mesurée (déclaré, LUCAS, manuel ?).
4. **Taille de l'annotation manuelle** : 30 parcelles seulement, ou ≈ 100 ? Moins de 50 rend le niveau C peu concluant.
5. **Parcelles de moins de 1 ha** : écartées du détecteur (recommandé) ou comptées « incertaines » ?
6. **Présélection de la commune** : le lien « Voir Ma commune » ouvre la page sans la commune cliquée, sauf à ajouter
   une ligne dans `vues/commune.py`. Par défaut la page n'est pas touchée.
