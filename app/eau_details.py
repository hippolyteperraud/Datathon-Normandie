"""Les nitrates des rivières, pour l'encadré bleu de la page Recommandations.

Les calculs sont dans prairimetre/eau.py (mesures Hubeau) ; aucun chiffre n'est écrit à la main."""
import streamlit as st

from prairimetre import eau


@st.cache_data(show_spinner="Lecture des analyses d'eau…")
def _nitrates(date):
    t, debut, fin = eau.tendance()
    return t, debut, fin, eau.robustesse(), eau.depassements()


def nitrates():
    """(tendance par station, période d'avant, période d'après, robustesse, dépassements), ou None si
    les mesures ne sont pas installées."""
    f = eau.fichier_mesures()
    if f is None or not eau.STATIONS.exists():
        return None
    return _nitrates(f.stat().st_mtime)
