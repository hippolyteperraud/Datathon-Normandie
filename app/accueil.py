"""Application Prairimètre.

    python -m streamlit run app/accueil.py      (depuis la racine du projet)

Une page par usage. Les pages lisent les tables du moteur (sorties/) ; « Ma commune » et
« Technique » appellent aussi directement le moteur Python.
"""
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
for chemin in (ICI.parent, ICI):  # le moteur (prairimetre) et les modules de l'appli
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))

import streamlit as st  # noqa: E402

from commun import equipe  # noqa: E402

st.set_page_config(page_title="Prairimètre", page_icon=":material/grass:", layout="wide")
st.logo(str(ICI / "assets" / "logo.svg"), size="large")

page = st.navigation([
    st.Page("vues/objectif.py", title="Objectif 2030", icon=":material/flag:", default=True),
    st.Page("vues/regles.py", title="Ce qui marche", icon=":material/shield:"),
    st.Page("vues/commune.py", title="Ma commune", icon=":material/location_city:"),
    st.Page("vues/technique.py", title="Technique", icon=":material/build:"),
], position="top")  # le menu est un bandeau en haut de la page, toujours visible
equipe()
# Moins de vide en haut de page : chaque onglet doit tenir sur un écran de portable
st.html("<style>[data-testid='stMainBlockContainer'] {padding-top: 4.2rem; padding-bottom: 2rem}"
        "h1 {padding-top: 0.4rem !important}</style>")
page.run()
