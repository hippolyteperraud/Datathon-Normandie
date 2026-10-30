# Tester l'application Prairimètre

Le dépôt contient le code, pas les données (6,7 Go, trop lourdes pour GitHub). Un script les
télécharge depuis leurs sources officielles (IGN, data.gouv.fr, Eurostat), puis calcule les
résultats. Compter **environ 11 Go d'espace disque** (données + fichiers intermédiaires) et
**plusieurs heures** la première fois. Testé avec Python 3.13 sous Windows 11.

## 1. Récupérer le code

```
git clone https://github.com/hippolyteperraud/Datathon-Normandie.git
cd Datathon-Normandie
git checkout test-app-v1
```

## 2. Installer les dépendances

```
pip install -r requirements.txt
```

## 3. Télécharger les données et calculer les résultats

Toujours depuis la racine du projet (le script utilise le code du dossier `prairimetre/`) :

```
python importer_donnees.py --puis-calculer
```

Le script télécharge les 24 sources dans `data/`, puis calcule les résultats dans `sorties/`.
À la fin, il affiche un bilan : chaque source doit être marquée `OK`.

**Si une source est en `ÉCHEC`** (un service en ligne en panne, par exemple), le calcul n'est
pas lancé. Relancer seulement les sources en échec, puis le calcul :

```
python importer_donnees.py --seulement <source1> <source2>
python -m prairimetre calculer
python -m prairimetre evaluer
```

## 4. Lancer l'application

```
python -m streamlit run app/accueil.py
```

Puis ouvrir http://localhost:8501 dans le navigateur. L'application ne tourne que sur votre
machine : elle n'est pas accessible depuis le réseau.

## Ce qu'il faut regarder

| Page | Ce qu'elle montre |
|---|---|
| Synthèse | Les trois recommandations et leurs chiffres |
| Où agir | Les communes, intercommunalités ou aires de captage à cibler |
| Ma commune | Le diagnostic d'une commune et la carte de ses parcelles |
| Carte des données | Ce que l'outil voit dans chaque commune ; en noir, là où il ne voit rien |
| Données et méthode | Les preuves, les tests, les sources, et la mise à jour des données |

Sans connexion internet, désactiver « Fond de carte » dans la barre latérale : les cartes
restent lisibles.

## En cas de problème

- `ModuleNotFoundError: prairimetre` : la commande n'a pas été lancée depuis la racine du projet.
- « Les résultats du moteur sont incomplets » dans l'application : le calcul n'a pas tourné.
  Lancer `python -m prairimetre calculer` puis `python -m prairimetre evaluer`.
- Vérifier le moteur : `python -m unittest discover tests` (moins d'une seconde).
