"""L'herbe hors registre PAC recomptée au satellite : les chiffres de la case « La fiabilité de
Prairimètre » (page Objectif 2030), et comment on les a calculés (onglet Technique → Preuves, partie 4,
où mène le bouton « Comment on a recompté »). D'où vient l'erreur est dit sur la page Objectif 2030.

Chiffres de verification/sentinel2/<an>/herbe_hors_pac.json (python -m prairimetre.sentinel_nuit resumer)
et des séries longues d'Agreste : aucun chiffre n'est écrit à la main. Version précédente, avec l'écart
détaillé : app/sauvegardes/herbe_hors_pac_avec_ecart_2026-11-11.py."""
import json
from types import SimpleNamespace

import pandas as pd
import streamlit as st

from commun import ha, nombre
from prairimetre import sentinel as sen
from prairimetre.donnees import DATA, SOURCES, prairies

BLEU, ORANGE_VIF = "#2a78d6", "#eb6834"


@st.cache_data(show_spinner=False)
def _passage(annee):
    """Statistique agricole de l'année (herbe des exploitations, hors exploitations) et prairies
    permanentes déclarées au registre PAC."""
    t = pd.read_csv(DATA / SOURCES["saa_series"]["fichier"]).set_index("annee")
    return (int(t.loc[annee, "sth_exploitations"]), int(t.loc[annee, "sth_hors_exploitations"]),
            int(round(prairies(annee).surf_parc.sum())))


@st.cache_data(show_spinner=False)
def _lu(annee, date_fichier):
    f = sen.DOSSIER / str(annee) / "herbe_hors_pac.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def chiffres(an):
    """Les chiffres du recomptage pour l'année an (relus dès que le fichier change), ou None."""
    f = sen.DOSSIER / str(an) / "herbe_hors_pac.json"
    hp = _lu(an, f.stat().st_mtime if f.exists() else 0)
    cb = hp.get("courbe") if hp else None
    if not cb:
        return None
    expl, hors, pac = _passage(an)
    X = hp["origines"]["total"]                          # origine exacte, géométrie entière
    vu = X["depuis_2023"] + X["jamais"] + X["avant_2023"]
    assert abs(vu - cb["ha_nature"]["herbe"]) <= 3      # arrondis : le total affiché est la somme des parts
    expl_hors = expl - pac                               # herbe des exploitations non déclarée en prairie permanente
    return SimpleNamespace(
        an=an, hp=hp, cb=cb, expl=expl, hors=hors, pac=pac, vu=vu, ancien=X["avant_2023"],
        n_photos=sum(hp["photos"]["sortie avant 2023"].values()) + sum(hp["photos"]["sortie depuis 2023"].values()),
        ecart_total=vu - (expl_hors + hors))


def afficher(an):
    """La partie 4 de l'onglet Preuves : comment on a recompté toute l'herbe de Normandie."""
    c = chiffres(an)
    if c is None:
        st.info(f"Le recomptage de l'herbe de {an} au satellite n'est pas encore fait "
                f"(verification/sentinel2/{an}/herbe_hors_pac.json).")
        return
    hp, cb = c.hp, c.cb
    st.markdown(
        f"Toute l'herbe de Normandie en {an} = les prairies permanentes déclarées à la PAC "
        f"(**{ha(c.pac)}**, registre PAC) + l'herbe hors PAC, recomptée ainsi :\n\n"
        f"1. **L'herbe hors registre, sur la carte IGN** (OCS GE, couvert herbacé d'usage agricole ou sans "
        f"usage ; 2022 dans l'Eure, la Manche et la Seine-Maritime, 2023 dans le Calvados et l'Orne), moins tout "
        f"ce qui est déclaré à la PAC en {an} : {nombre(hp['morceaux'])} morceaux, "
        f"{ha(sum(cb['ha_nature'].values()))}.\n"
        f"2. **Chaque morceau vu au satellite** : sa courbe de verdure (NDVI) sur {hp['images']} images "
        f"Sentinel-2 de {an}, classée herbe, culture ou bois par un modèle appris sur "
        f"{nombre(cb['etalons']['herbe'])} prairies, {nombre(cb['etalons']['culture'])} cultures et "
        f"{nombre(cb['etalons']['bois'])} bois connus : {ha(cb['ha_nature']['herbe'])} d'herbe, "
        f"{ha(cb['ha_nature']['bois'])} de bois, landes et roseaux, {ha(cb['ha_nature']['culture'])} de cultures.\n"
        f"3. **L'origine de chaque hectare** : le morceau entier comparé au registre PAC de chaque année de "
        f"2018 à {an - 1} ; on garde la dernière année où il y était. C'est ce qui isole les "
        f"{ha(c.ancien)} de prés sortis de la PAC avant 2023.\n"
        f"4. **Contrôle sur photos aériennes**, à l'aveugle : {c.n_photos} morceaux d'au moins 1 ha.\n\n"
        f"Total : {ha(c.pac)} + {ha(c.vu)} = **{ha(c.pac + c.vu)}**.")
    st.caption(f"Détail : verification/sentinel2/compte_rendu_{an}.md ; précision selon la taille des prés : "
               "scripts/precision_par_taille.py.")
