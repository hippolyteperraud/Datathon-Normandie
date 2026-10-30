"""Lexique : les mots de l'outil, en clair."""
import streamlit as st

from commun import LEXIQUE

st.title("Lexique")
for mot, sens in LEXIQUE.items():
    st.markdown(f"**{mot}**  \n{sens[0].upper()}{sens[1:]}")
