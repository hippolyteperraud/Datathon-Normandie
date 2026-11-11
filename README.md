<p align="center">
  <img src="app/assets/logo_prairimetre.png" alt="Prairimètre" width="420">
</p>

<h3 align="center">Les prairies de Normandie, suivies parcelle par parcelle</h3>

<p align="center">
  Où elles disparaissent, ce qu'elles deviennent, et ce qui marche pour les garder.
</p>

<p align="center">
  <img alt="Datathon Normandie 2026" src="https://img.shields.io/badge/Datathon-Normandie%202026-2e7d4f">
  <img alt="Données ouvertes" src="https://img.shields.io/badge/donn%C3%A9es-100%25%20ouvertes-1baf7a">
  <img alt="Python 3.13" src="https://img.shields.io/badge/Python-3.13-2a78d6">
  <img alt="Streamlit" src="https://img.shields.io/badge/Streamlit-1.66-c2452d">
  <img alt="Licence MIT" src="https://img.shields.io/badge/licence-MIT-8a8f98">
</p>

<p align="center">
  <img src="images%20readme/accueil.png" alt="L'accueil de Prairimètre" width="900">
</p>

---

## Le problème : un seul chiffre

La Région Normandie s'est fixé **zéro perte nette de prairies permanentes entre 2021 et 2030**
(Stratégie régionale pour la biodiversité, objectif III.5). La mesure officielle, la statistique
agricole, dit combien on en perd :

<h3 align="center">−12 468 ha</h3>
<p align="center">de surface toujours en herbe de 2021 à 2025</p>

Elle ne dit ni **où**, ni **pourquoi**, ni **ce qui marche** pour les garder.

## Notre réponse : chaque parcelle

Prairimètre croise **8 années du registre PAC** (2018 → 2025) et **675 images satellite Sentinel-2** de 2025,
prairie par prairie. On sait ainsi, pour chaque parcelle de Normandie, si elle est restée en herbe, si
elle a été retournée, ou si elle est sortie de la PAC tout en restant verte.

<table>
  <tr>
    <td align="center"><h3>21 636</h3>prairies sorties de la PAC,<br>vérifiées une à une au satellite</td>
    <td align="center"><h3>1,2 %</h3>d'erreur sur toute l'herbe<br>de Normandie, recomptée</td>
    <td align="center"><h3>16 102 ha</h3>de prés que la statistique<br>ne compte plus</td>
    <td align="center"><h3>7× moins</h3>de retournement là où<br>c'est interdit</td>
  </tr>
</table>

Toutes les données sont **ouvertes** (IGN, Agreste, Copernicus, data.gouv.fr, Sandre, Hub'Eau), et
aucun chiffre de l'application n'est écrit à la main : tout est recalculé à partir des sources.

---

## Visite de l'application

### 1 · Mesurer : l'objectif 2030 est-il tenu ?

À gauche, le constat officiel. À droite, notre propre recomptage de **toute** l'herbe de Normandie au
satellite, sans partir de la statistique : **791 623 ha** pour nous, **766 157 ha** pour elle.
L'écart s'explique : **16 102 ha** sont des prés sortis de la PAC avant 2023, toujours fauchés ou
pâturés, que la statistique ne compte plus (un angle mort, pas une erreur) ; il reste **9 364 ha**,
soit **1,2 %** d'erreur. Le satellite reconnaît **98,9 %** de l'herbe des prés de 5 ha et plus,
**85,7 %** en dessous.

<p align="center">
  <img src="images%20readme/objectif%202030.png" alt="Page Objectif 2030" width="900">
</p>

### 2 · Localiser : que sont devenues les prairies de ma commune ?

Pour chaque commune qui a des prairies, la carte de toutes ses prairies depuis 2018, en trois
familles : **en herbe**, **pas en herbe**, **à vérifier sur le terrain**. Un clic sur une catégorie
de la légende la masque ou l'affiche.

<table>
  <tr>
    <td><img src="images%20readme/ma%20commune.png" alt="Ma commune : toutes les prairies"></td>
    <td><img src="images%20readme/ma%20commune%20prairie%20en%20herbe.png" alt="Ma commune : les prairies encore en herbe"></td>
  </tr>
  <tr>
    <td align="center"><sub>Toutes les prairies de 2018 et ce qu'elles sont devenues</sub></td>
    <td align="center"><sub>Seulement celles qui sont encore en herbe</sub></td>
  </tr>
</table>

### 3 · Agir : qu'est-ce qui marche vraiment ?

Chaque levier testé sur nos données, avec son verdict, son chiffre, et ce qu'on en recommande.

| Ce qu'on a testé | Ce qu'on a trouvé | Donc, on recommande |
|---|---|---|
| Interdire de retourner | **7× moins** de retournement qu'à côté, sur le même terrain | L'étendre aux 211 communes qui retournent le plus : environ 20 000 ha gardés |
| Autorisation régionale | **2× moins** l'année où elle s'appliquait | Ne pas la lever trop vite |
| Zone de captage d'eau, sans règle | **Autant** de retournement qu'à côté | Y mettre une condition d'herbe |
| Zones humides (règle de 2025) | **Trop tôt** : 17× moins de retournement, mais déjà avant la règle | Ne pas compter dessus pour 2030 |
| Recréer de l'herbe | **1 ha** recréé pour **4 ha** retournés | En recréer 4 fois plus |

**Une idée nouvelle, testée sur nos données : protéger les jeunes prairies.** Une prairie qui vient
de devenir permanente est retournée **4× plus** souvent : elles font 3 % des prairies, mais 12 % du
retournement. D'où notre recommandation : un contrat dès qu'une prairie devient permanente
(20 048 ha à suivre, repérables chaque année dans le registre PAC).

<p align="center">
  <img src="images%20readme/recommandations.png" alt="Page Recommandations" width="900">
</p>

<table>
  <tr>
    <td><img src="images%20readme/211%20communes%20ou%20on%20retourne%20le%20plus.png" alt="Les 211 communes où l'on retourne le plus"></td>
    <td><img src="images%20readme/les%20communes%20qui%20recr%C3%A9ent%20de%20l'herbe.png" alt="Les communes qui recréent de l'herbe"></td>
  </tr>
  <tr>
    <td align="center"><sub>Les 211 communes où l'on retourne le plus</sub></td>
    <td align="center"><sub>Les communes qui recréent de l'herbe sur d'anciennes cultures</sub></td>
  </tr>
</table>

### 4 · Vérifier : les preuves, les limites, les sources

Tout ce qui fonde les chiffres est dans l'onglet **Technique** : comment le satellite vérifie les
prairies, comment l'herbe a été recomptée, ce que l'outil ne sait pas, les sources avec leurs liens,
un glossaire. Le moteur se met à jour d'un bouton : nouveau registre PAC, nouvelles séries de la
statistique agricole, images satellite.

<table>
  <tr>
    <td><img src="images%20readme/technique%20moteur.png" alt="Technique : le moteur"></td>
    <td><img src="images%20readme/technique%20preuves.png" alt="Technique : les preuves"></td>
  </tr>
  <tr>
    <td><img src="images%20readme/technique%20sources.png" alt="Technique : les sources"></td>
    <td><img src="images%20readme/technique%20glossaire.png" alt="Technique : le glossaire"></td>
  </tr>
</table>

---

## Lancer l'application

Il faut **Python 3.13** (testé sous Windows 11). L'application tourne sur votre machine
(http://localhost:8501) ; le fond de carte demande une connexion internet.

<details open>
<summary><b>Depuis le zip du rendu</b> (données incluses, le plus simple)</summary>

<br>

1. Dézipper, puis ouvrir un terminal dans le dossier dézippé.
2. Installer les dépendances :
   ```
   pip install -r requirements.txt
   ```
3. Lancer l'application, puis ouvrir http://localhost:8501 :
   ```
   python -m streamlit run app/accueil.py
   ```

Le cache du moteur n'est pas dans le zip : il se recrée tout seul. La première ouverture de
**Ma commune** prend donc **3 à 4 minutes**, puis c'est instantané.

</details>

<details>
<summary><b>Depuis GitHub</b> (les données se téléchargent depuis leurs sources)</summary>

<br>

Le dépôt contient le code et les résultats satellite, pas les données (trop lourdes). Compter
**environ 11 Go** d'espace disque et **plusieurs heures** la première fois.

1. Récupérer le code :
   ```
   git clone https://github.com/hippolyteperraud/Datathon-Normandie.git
   cd Datathon-Normandie
   ```
2. Installer les dépendances :
   ```
   pip install -r requirements.txt
   ```
3. Télécharger les données et calculer les résultats (depuis la racine du projet) :
   ```
   python importer_donnees.py --puis-calculer
   ```
   Chaque source doit finir marquée `OK`. Si une source est en `ÉCHEC` (service en panne) :
   ```
   python importer_donnees.py --seulement <source>
   python -m prairimetre recalculer
   ```
4. Récupérer les mesures de nitrates (Hub'Eau) :
   ```
   python scripts/recuperer_hubeau.py
   python scripts/analyser_nitrates.py
   ```
5. Lancer l'application :
   ```
   python -m streamlit run app/accueil.py
   ```

</details>

<details>
<summary><b>Refaire les calculs</b></summary>

<br>

```
python -m prairimetre etat              # ce qui est installé, ce qui est publié
python -m prairimetre mettre-a-jour     # un nouveau registre PAC : télécharger, contrôler, recalculer
python -m prairimetre agreste           # nouvelles séries de la statistique agricole, puis recalcul
python -m prairimetre recalculer        # tables de résultats et preuves -> sorties/
python -m prairimetre satellite         # vérifier au satellite les prairies sorties de la PAC
```

Le recomptage de toute l'herbe au satellite part des images brutes Sentinel-2 (environ 13 Go, ni
dans le zip ni sur GitHub) :

```
python -m prairimetre.sentinel_hors_ligne tout 2025     # télécharger les images, puis tout mesurer
python -m prairimetre.sentinel_nuit resumer 2025        # -> verification/sentinel2/2025/herbe_hors_pac.json
python scripts/precision_par_taille.py 2025             # réussite selon la taille des prés
```

Tests du moteur : `python -m unittest discover tests`.

</details>

<details>
<summary><b>En cas de problème</b></summary>

<br>

- `ModuleNotFoundError: prairimetre` : la commande n'a pas été lancée depuis la racine du projet.
- « Les résultats du moteur sont incomplets » : lancer `python -m prairimetre recalculer`.
- « Mesures de nitrates absentes » : lancer les deux scripts Hub'Eau ci-dessus.

</details>

---

## Sous le capot

| | |
|---|---|
| **Données** | Registre parcellaire graphique 2018-2025 (IGN), statistique agricole annuelle (Agreste), occupation du sol OCS GE (IGN), images Sentinel-2 (Copernicus), photos aériennes BD ORTHO (IGN), zonages (BCAE, Natura 2000, captages, zones humides…), nitrates des rivières (Hub'Eau) |
| **Méthode** | Les prairies de chaque année croisées, parcelle par parcelle, avec les déclarations suivantes ; les prairies sorties de la PAC vérifiées au satellite (courbe de verdure NDVI sur toute l'année) ; contrôles à l'aveugle sur photos aériennes |
| **Sobriété** | Application locale ; le satellite est mesuré une fois, puis seulement relu ; une parcelle déjà mesurée n'est jamais redemandée |
| **Pile** | Python, pandas, GeoPandas, scikit-learn, Streamlit, pydeck |

| Dossier | Contenu |
|---|---|
| `app/` | L'application Streamlit (pages dans `app/vues/`) |
| `prairimetre/` | Le moteur : téléchargement, contrôles, calculs, satellite |
| `scripts/` | Nitrates, vérifications, précision du satellite |
| `verification/` | Résultats et preuves de la vérification satellite |
| `sorties/` | Tables de résultats lues par l'application |
| `data/` | Les données (dans le zip ; pas sur GitHub) |
| `docs/` | Documents du projet |
| `tests/` | Tests du moteur |

---

## L'équipe

<table>
  <tr>
    <td align="center" width="50%">
      <img src="app/assets/logo_insa_rouen.png" alt="INSA Rouen Normandie" height="48"><br>
      <b>Hippolyte Perraud</b><br><sub>INSA Rouen Normandie</sub>
    </td>
    <td align="center" width="50%">
      <img src="app/assets/logo_ensicaen.png" alt="ENSICAEN" height="48"><br>
      <b>Mouhssine Bairoune</b><br><sub>ENSICAEN</sub>
    </td>
  </tr>
</table>

<p align="center"><sub>Datathon 2026 de la Région Normandie · données ouvertes · licence <a href="LICENSE">MIT</a></sub></p>
