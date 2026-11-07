# Audit du code : 7 novembre 2026

Périmètre : le moteur (`prairimetre/`), l'application (`app/`), les scripts et les tests, soit environ
4 900 lignes. Méthode : relecture, plus un contrôle automatique des imports inutilisés et des
fonctions jamais appelées. Après corrections : 23 tests passent, les 5 pages s'ouvrent sans erreur.

## Corrigé

### Ce qui pouvait tromper

| Problème | Conséquence | Correction |
|---|---|---|
| L'objectif 2030 était mesuré sur le registre PAC, avec 2022 comme référence (« à confirmer ») | L'écart affiché (−29 878 ha) ne mesurait pas l'objectif officiel | Référence 2021 (texte de la SRB, objectif III.5) ; la mesure officielle (superficie toujours en herbe, Agreste) est calculée et affichée en premier : −7 871 ha entre 2021 et 2024 |
| Deux mesures différentes de la statistique agricole : « +4 834 ha » (prairies productives seules) et la superficie toujours en herbe | Deux chiffres pour une même notion | Une seule mesure partout : la superficie toujours en herbe (+3 903 ha en 2023) |
| L'année de référence du ratio de la PAC était prise sur la première année du registre | Faux si le registre commençait une autre année | Fixée à 2018, comme le règlement (`REFERENCE_RATIO`) |
| Le code de la région (`REGION = "R28"`) existait dans `config.py`, mais « R28 » était écrit en dur dans `sources.py` et `telecharger.py` | Changer de région demandait de modifier trois fichiers : l'argument « changement d'échelle » était faux | Un seul endroit : `config.REGION` |
| `SEUIL_ECLAT`, seuil de « bruit géométrique » documenté mais jamais appliqué | Laissait croire à un filtrage inexistant | Retiré |
| Colonne `levier` de `communes.csv` remplie avec des noms d'actions abandonnés (« payer le maintien », « s'appuyer sur les exemples ») | Une sortie publique avec des noms périmés | Retirée (elle disparaît au prochain « Relancer les calculs ») |
| Onglet Technique : les preuves renvoyaient aux « moyens d'agir » supprimés | Texte faux | Réécrit ; ajout de la preuve satellite et de la limite sur les 39 % |
| Vérification satellite : la première règle, fixée à l'avance, voyait 11 prairies sur 20 labourées | Résultat faux si on l'avait gardée | Règle corrigée sur 40 témoins, validée sur 40 autres jamais regardés (2 erreurs sur 29) ; l'échec est raconté dans les preuves |

### Code mort retiré

- Moteur : `flux_commune`, `saa` (remplacée par `sth`), `NOMS_FAMILLES`, `ANNUELLES`,
  `AUTOMATIQUES`. (`sorties/sobriete.csv` n'est pas orpheline : `__main__.py` y trace la durée de
  chaque calcul et le volume des données ; elle est gardée.)
- Application : les restes de l'ancien « Où agir » dans `commun.py` (`contact_captage`,
  `etat_sorties`, `epci_carte`, `captages_carte`, `couleurs_liste`, `DE_TERRITOIRE`, `NOIR`) ;
  dans `humain.py`, `terrains` et `fois_caen` ; `ACTIONS` réduit aux trois noms encore lus ; trois
  imports inutilisés.
- Onglet Objectif 2030 réécrit : une variable inutilisée, un même nom (`bas`) employé pour deux
  choses, un ordre de lecture peu clair. Ordre désormais : l'objectif, quatre chiffres, les deux
  courbes, pourquoi le registre perd plus que la statistique agricole, ce qui retient les
  prairies, ce qu'on ne sait pas, puis le ratio de la PAC dans un volet repliable.

Les fichiers remplacés sont gardés dans `app/sauvegardes/` (`*_avant_audit_2026-11-07.py`).

## Pas corrigé : à décider

1. **La bande du haut** affiche « −60 050 ha, Prairimètre 2018→2025 » (choix du 5 novembre).
   Avec l'objectif clarifié, la mesure officielle (−7 871 ha depuis 2021, statistique agricole)
   serait plus juste en premier chiffre.
2. **La part de 39 % ne peut pas être recalculée** : il manque la surface agricole utile de la
   statistique agricole (Agreste, SAA). Ajouter cette source rendrait l'indicateur officiel
   complet.
3. **`.gitignore` ignore `app/` et `prairimetre/`** : tout nouveau fichier doit être ajouté avec
   `git add -f`. Ça a déjà fait planter la branche publiée (`exemples.py` absent). C'est le risque
   le plus concret du dépôt.
4. **« Où aller voir » (`app/vues/donnees.py`, onglet de Mouhssine)** : sa docstring parle encore
   de « la liste où payer le maintien ». C'est un texte non affiché ; à corriger par lui.
5. **`evaluation_moteurs.csv`** (lien maïs / retournement) est calculée mais affichée nulle part :
   à montrer dans Technique comme piste « testée et écartée », ou à retirer.
6. **La documentation** (`README.md`, `TESTER_APPLICATION.md`, `docs/`) parle encore de
   « Où agir », « Carte des données », « Données et méthode » et de LUCAS : à refaire à la fin,
   comme prévu.
7. **Tests** : pas de test sur `sth()` ni sur la fusion des deux sources dans `objectif()`.

## Ce qui est sain

- Les nombres sont écrits en Python au format français, pas par Vega.
- Les chiffres de l'appli sont calculés à partir de `sorties/`, sans chiffre de résultat écrit à la
  main. Les chiffres officiels cités sont rangés à part, avec leur source (`app/references.py`).
- Les tirages au hasard sont reproductibles (graines fixes). Chaque mesure satellite est tracée
  (`verification/sentinel2/images.csv`).
- Les accès réseau (téléchargements, Sentinel-2) ne se font qu'en ligne de commande, jamais à
  l'ouverture de l'appli.
