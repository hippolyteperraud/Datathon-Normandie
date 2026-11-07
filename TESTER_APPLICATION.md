# Tester l'application Prairimètre

Le dépôt contient le code, pas les données (environ 6,5 Go, trop lourdes pour GitHub). Un script les
télécharge depuis leurs sources officielles (IGN, data.gouv.fr, Sandre), puis calcule les
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
| Objectif 2030 (accueil) | L'objectif régional selon la statistique agricole et selon le registre PAC, pourquoi ils diffèrent (2019, 2023), ce qui retient les prairies, ce qu'on ne sait pas |
| Ma commune | Ce que sont devenues les prairies d'une commune, la carte de ses parcelles |
| Où aller voir | Les communes qui portent la moitié des sorties de la déclaration, et ce que le satellite y voit |
| Prendre exemple | Les communes qui gagnent des prairies, et celles qui n'en perdent pas |
| Technique | Les preuves, les sources et les textes officiels, les mots de l'outil, le recalcul |

La vision satellite (`verification/sentinel2/`) est fournie dans le dépôt ; pour la refaire :
`python scripts/analyser_satellite_sentinel.py --sentinel`.

Le fond de carte demande une connexion internet.

## En cas de problème

- `ModuleNotFoundError: prairimetre` : la commande n'a pas été lancée depuis la racine du projet.
- « Les résultats du moteur sont incomplets » dans l'application : le calcul n'a pas tourné.
  Lancer `python -m prairimetre calculer` puis `python -m prairimetre evaluer`.
- Vérifier le moteur : `python -m unittest discover tests` (moins d'une seconde).
