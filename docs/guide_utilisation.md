# Prairimètre — guide d'installation et d'utilisation

Pour : une personne qui reçoit le paquet de remise et veut faire tourner l'outil sur son ordinateur.
Tout se passe en local : rien n'est mis en ligne.

## 1. Installer (une fois, environ 10 minutes)

1. Installer **Python 3.13** (testé avec 3.13.7, Windows 11) : https://www.python.org/downloads/
   (cocher « Add python.exe to PATH »).
2. Décompresser le paquet `prairimetre_<date>.zip`, puis ouvrir un terminal dans le dossier obtenu.
3. Installer les bibliothèques, aux versions testées :

   ```
   pip install -r requirements.txt
   ```

4. Vérifier : `python -m unittest discover tests` doit afficher `OK` (8 tests).

## 2. Les données

- **Paquet avec données** (`livrer --avec-donnees`) : rien à faire, `data/` est fourni.
- **Paquet sans données** : les résultats (`sorties/`) suffisent pour ouvrir l'application. Pour
  recalculer, retélécharger toutes les données avec **un seul fichier** :

  ```
  python importer_donnees.py --liste           # les 24 sources : quoi, qui, vers où
  python importer_donnees.py --puis-calculer   # tout récupérer, puis recalculer (plusieurs heures)
  python importer_donnees.py --seulement lucas # une seule source
  ```

  Chaque source est cherchée à sa source officielle (IGN, data.gouv.fr, Eurostat), recadrée sur
  la Normandie, vérifiée, puis tracée dans `data/manifest.json`. Une source en panne n'arrête pas
  les autres ; le bilan final dit lesquelles relancer. Le détail des sources est dans
  `docs/donnees_projet.pdf`.

## 3. Lancer l'application

```
python -m streamlit run app/accueil.py
```

Puis ouvrir http://localhost:8501 dans le navigateur. Le serveur n'écoute que sur cet ordinateur.
Le fond de carte demande une connexion internet.

## 4. Utiliser l'application

Le menu, en bandeau en haut de la page, donne accès aux cinq pages, dont le **Lexique et définitions**.

| Page | À quoi elle sert |
|---|---|
| Où agir (accueil) | Les trois moyens d'agir : suivre l'objectif 2030 en hectares, payer le maintien des prairies là où l'on retourne, s'appuyer sur les communes qui gardent leurs prairies. Pour chacun : le conseil, pourquoi, pour qui, où (carte et liste à télécharger), l'indicateur de suivi |
| Ma commune | Les hectares d'une commune : prairies de 2025, retournées, sorties de la déclaration, ajoutées ; ce que sont devenues les prairies de 2018, en tout et zone par zone (zones humides, sites protégés, prairies sensibles, ZNIEFF, captages, habitats ; « ne sait pas » si la source ne dit rien) ; une seule carte de ses prairies |
| Carte des données | Les données qu'on a : une petite carte par source (registre PAC, occupation du sol, enquête au sol, habitats), en noir là où elle ne dit rien. Où il en faudrait plus : chaque donnée à collecter, ses chiffres et ses communes (l'état réel des prairies sorties de la déclaration ; les habitats prairiaux des départements sans cartographie). Télécharger le tableau |
| Données et méthode | La preuve de chaque moyen d'agir (avec les tests qui la vérifient), les sources, le moteur (nouveau registre ; recalcul proposé seulement si les résultats ne sont pas à jour) |
| Lexique et définitions | Les mots de l'outil, et les quatre chiffres qui circulent sur les prairies |

Lire les chiffres :

- **Retournée en culture** = perte déclarée : une culture est déclarée à la place de la prairie.
- **Sortie de la déclaration** = perte à vérifier : la parcelle n'est plus déclarée à la PAC, l'herbe
  est souvent encore là.
- Une case sans chiffre affiche toujours sa raison (par exemple « moins de 20 ha de prairies »).

## 5. Chaque année, quand un nouveau RPG paraît

Dans l'application : **Données et méthode → Moteur → « Chercher et installer le dernier
millésime »**. Ou dans le terminal :

```
python -m prairimetre mettre-a-jour
```

Le moteur trouve le dernier millésime publié par l'IGN, le télécharge, le contrôle, recalcule les
indicateurs et l'évaluation. Rien n'est remplacé si un contrôle échoue. Durée mesurée le
25/10/2026 : environ une heure. Option `--avec-officielle` : télécharge aussi la couche officielle
des prairies, qui ne sert qu'à un contrôle de plus, mais dont le service est très lent (près de
6 h supplémentaires). Toutes les durées sont dans `sorties/sobriete.csv`.

## 6. Préparer une remise

```
python -m prairimetre livrer                  # code, résultats, manifest, documents (≈ 1 Mo)
python -m prairimetre livrer --avec-donnees   # + data/ (≈ 6,7 Go)
```

Le paquet est écrit dans `livraison/`. Il n'est envoyé nulle part.

## 7. En cas de problème

| Symptôme | Solution |
|---|---|
| « Les résultats du moteur sont incomplets » | `python -m prairimetre calculer` puis `evaluer` |
| Une carte reste vide | vérifier la connexion internet (le fond de carte en a besoin) |
| Le service de l'IGN ou du Sandre ne répond pas | réessayer plus tard, ou télécharger le fichier à la main et utiliser `importer` |
| Erreur de certificat au téléchargement | `pip install truststore` (déjà dans requirements.txt) |
