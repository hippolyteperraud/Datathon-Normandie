"""1. L'objectif 2030, sur un seul écran (le but du projet est présenté dans l'onglet Accueil).
Deux cases côte à côte, de même taille :
- le constat officiel (statistique agricole, surface toujours en herbe depuis 2021) ;
- la fiabilité de Prairimètre : toute l'herbe de Normandie recomptée au satellite, face à la statistique.
  L'écart se partage entre les prés sortis de la PAC avant 2023 que la statistique ne compte plus et
  notre erreur, qui dépend surtout de la taille des prés (chiffres de
  verification/sentinel2/<an>/herbe_hors_pac.json, clé precision_taille : scripts/precision_par_taille.py).
Le détail du recomptage est dans Technique → Preuves, partie 4 (app/herbe_hors_pac.py) : le bouton y
mène. Versions précédentes : app/sauvegardes/."""
import streamlit as st

from commun import bornes, exiger_sorties, ha, nombre, table
from herbe_hors_pac import BLEU, ORANGE_VIF, chiffres
from references import OBJECTIF_REGIONAL, SUIVI_SRB

exiger_sorties()
_, an = bornes()
VERT, ROUGE, GRIS = "#2e7d4f", "#c2452d", "#8a8f98"
DISCRET = "font-size:.78rem;opacity:.65"
PETIT_TITRE = "font-size:.78rem;opacity:.7;text-transform:uppercase;letter-spacing:.03em;margin-bottom:.25rem"
# Une seule page : moins de marge en haut, titre plus petit
st.html("<style>[data-testid='stMainBlockContainer']{padding-top:3.4rem !important;padding-bottom:0}"
        "h1{font-size:1.75rem !important;padding:.2rem 0 0 !important}</style>")

# --- Les chiffres ----------------------------------------------------------------------------------
obj = table("objectif").set_index("annee")
sth = obj.sth_ha.dropna().astype(int)
a_ref, fin = int(obj.annee_reference.iloc[0]), int(sth.index.max())
ecart = int(sth.loc[fin] - sth.loc[a_ref])

rec = chiffres(an) if fin == an and an in sth.index else None
if rec:
    assert rec.expl + rec.hors == int(sth.loc[an])
    # Notre herbe et celle de la statistique ; l'écart = les prés sortis avant 2023 + le reste, non expliqué
    eux_total, nous_total = rec.expl + rec.hors, rec.pac + rec.vu
    ecart_herbe = nous_total - eux_total
    assert ecart_herbe == rec.ecart_total
    ancien = rec.ancien
    reste = ecart_herbe - ancien
    part_reste = 100 * reste / eux_total
    taille = rec.hp.get("precision_taille")


# --- Petits éléments en HTML -----------------------------------------------------------------------
def etiquette(texte):
    return f"<div style='{PETIT_TITRE}'>{texte}</div>"


def grand(texte, couleur):
    return f"<div style='font-size:1.6rem;font-weight:700;color:{couleur};line-height:1.15'>{texte}</div>"


def legende(texte):
    return f"<div style='font-size:.86rem;line-height:1.35;margin:.25rem 0 .45rem'>{texte}</div>"


def courbe_sth():
    """La surface toujours en herbe chaque année depuis la référence, sous la ligne du niveau à tenir."""
    ref = int(sth.loc[a_ref])
    pts = [(a, int(v)) for a, v in sth.items() if a >= a_ref]
    haut, bas = max(ref, *(v for _, v in pts)), min(ref, *(v for _, v in pts))
    W, G, Y0, HY = 560, 50, 40, 165            # largeur, marge gauche et droite, haut et hauteur de la courbe
    X = lambda i: G + i * (W - 2 * G) / max(len(pts) - 1, 1)  # noqa: E731
    Y = lambda v: Y0 + (haut - v) / max(haut - bas, 1) * HY  # noqa: E731
    ligne = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, (_, v) in enumerate(pts))
    txt = "fill='currentColor' text-anchor='middle' font-size='13'"
    elems = [f"<line x1='8' x2='{W - 8}' y1='{Y(ref):.1f}' y2='{Y(ref):.1f}' stroke='{VERT}' stroke-width='1.5' "
             "stroke-dasharray='5 4'/>",
             f"<text x='{W - 8}' y='{Y(ref) - 7:.1f}' fill='{VERT}' font-size='13' text-anchor='end'>"
             f"niveau de {a_ref} à tenir</text>",
             f"<polyline points='{ligne}' fill='none' stroke='{ROUGE}' stroke-width='2.5' stroke-linejoin='round'/>"]
    for i, (a, v) in enumerate(pts):
        elems.append(f"<circle cx='{X(i):.1f}' cy='{Y(v):.1f}' r='4.5' fill='{VERT if v >= ref else ROUGE}'>"
                     f"<title>{a} : {ha(v)}</title></circle>"
                     f"<text x='{X(i):.1f}' y='{Y0 + HY + 42}' {txt} opacity='.65'>{a}</text>")
    # Le chiffre du début au-dessus, celui de la fin en dessous : rien ne chevauche la courbe
    elems.append(f"<text x='{X(0):.1f}' y='{Y(pts[0][1]) - 9:.1f}' {txt} font-weight='700'>{ha(pts[0][1])}</text>")
    elems.append(f"<text x='{X(len(pts) - 1):.1f}' y='{Y(pts[-1][1]) + 19:.1f}' {txt} font-weight='700'>"
                 f"{ha(pts[-1][1])}</text>")
    return (f"<svg viewBox='0 0 {W} {Y0 + HY + 47}' width='100%' role='img' aria-label='Surface toujours en "
            f"herbe de {pts[0][0]} à {pts[-1][0]}' style='display:block;margin:.2rem 0'>{''.join(elems)}</svg>")


def morceau(v, couleur, mot):
    """Une part de la barre de l'écart, son chiffre et son mot écrits dedans."""
    return (f"<div title='{ha(v)} : {mot}' style='width:calc({100 * v / ecart_herbe:.1f}% - 2px);flex:none;"
            f"background:{couleur};color:#fff;display:flex;align-items:center;justify-content:center;gap:.35rem;"
            f"font-size:.82rem;white-space:nowrap;overflow:hidden'><b>{ha(v)}</b>{mot}</div>")


def reconnu(t, couleur):
    """Une ligne : classe de taille, part de l'herbe connue reconnue (barre), intervalle à 95 %."""
    bas, haut = t["ic95"]
    return (f"<div style='display:flex;justify-content:space-between;font-size:.88rem;margin-top:.85rem'>"
            f"<span>{t['classe'][0].upper() + t['classe'][1:]}</span><span><b style='font-size:1rem'>{nombre(t['pct'], 1)} %</b> "
            f"<span style='opacity:.7'>(entre {nombre(bas, 1)} et {nombre(haut, 1)} %)</span></span></div>"
            "<div style='position:relative;height:14px;margin-top:.25rem;background:rgba(128,128,128,.18);"
            "border-radius:3px'>"
            f"<div style='height:100%;width:{t['pct']:.1f}%;background:{couleur};border-radius:3px'></div>"
            f"<div title='intervalle à 95 %' style='position:absolute;top:-3px;bottom:-3px;left:{bas:.1f}%;"
            f"width:{max(haut - bas, .5):.1f}%;border:1.5px solid currentColor;border-radius:2px;opacity:.6'>"
            "</div></div>")


# --- Les fenêtres ------------------------------------------------------------------------------------
@st.dialog("Ce que disent les textes")
def fenetre_textes():
    o, r = OBJECTIF_REGIONAL, SUIVI_SRB["annee_reference"]
    st.html(f"<div style='font-size:1.05rem;padding-left:.8rem;border-left:3px solid {VERT}'>"
            f"« {o['objectif']} »</div>"
            f"<div style='{DISCRET};margin:.3rem 0 .9rem .8rem'><a href='{o['lien']}' target='_blank' "
            "style='color:inherit'>Stratégie régionale pour la biodiversité Normandie 2030</a>, objectif III.5</div>"
            f"<div>La Région le mesure par la surface toujours en herbe de la statistique agricole, référence "
            f"{r} : {ha(SUIVI_SRB['sth_ha'][r])}.</div>")


def vers_preuves():
    """Ouvre Technique → Preuves, partie 4 : comment on a recompté l'herbe."""
    st.switch_page("vues/technique.py", query_params={"preuve": "recompte"})


# --- La page : le constat officiel et la fiabilité de Prairimètre, côte à côte et de même taille ------
st.title("Objectif 2030 : zéro perte nette de prairies permanentes")
# Les deux cases ont la même hauteur ; leur bouton est calé en bas
st.html("<style>[class*='st-key-bloc_'] > div:last-child{margin-top:auto}"
        "[class*='st-key-bloc_'] [data-testid='stVerticalBlock']{gap:.35rem}</style>"
        "<div style='height:.8rem'></div>")  # un petit espace entre le titre et les deux cases
gauche, droite = st.columns(2, gap="medium")

with gauche, st.container(border=True, key="bloc_constat", height="stretch"):
    st.html(etiquette("Le constat officiel")
            + grand(ha(ecart, signe=True), VERT if ecart >= 0 else ROUGE)
            + legende(f"de surface toujours en herbe depuis {a_ref}"))
    st.markdown(courbe_sth(), unsafe_allow_html=True)  # st.html retire le SVG
    st.html(f"<div style='{DISCRET}'>Statistique agricole (Agreste) ; {fin} provisoire.</div>")
    if st.button("Ce que disent les textes", icon=":material/format_quote:", width="stretch"):
        fenetre_textes()

if rec:
    with droite, st.container(border=True, key="bloc_fiabilite", height="stretch"):
        st.html(etiquette("La fiabilité de Prairimètre")
                + grand(f"{nombre(part_reste, 1)} %", BLEU)
                + legende(f"d'erreur sur l'herbe de Normandie recomptée au satellite ({an})")
                + "<div style='height:1rem'></div>"
                + legende(f"<b>{ha(nous_total)}</b> pour nous, <b>{ha(eux_total)}</b> pour la statistique. "
                          "L'écart :")
                + "<div style='display:flex;gap:2px;height:32px;border-radius:4px;overflow:hidden;margin:.3rem 0 .5rem'>"
                + morceau(ancien, ORANGE_VIF, "angle mort de la statistique") + morceau(reste, GRIS, "notre erreur")
                + "</div>"
                + f"<div style='{DISCRET}'>Angle mort : prés sortis de la PAC avant 2023, toujours fauchés ou "
                  "pâturés, qu'elle ne compte plus.</div>"
                + ("<div style='font-weight:700;font-size:.95rem;margin-top:1.7rem'>Notre erreur selon la taille "
                   "des prés</div>"
                   + reconnu(taille["grands"], BLEU) + reconnu(taille["petits"], GRIS)
                   + f"<div style='{DISCRET};margin-top:.6rem'>Entre parenthèses : intervalle de confiance à "
                     "95 %.</div>" if taille else ""))
        if st.button("Comment on a recompté", icon=":material/satellite_alt:", width="stretch"):
            vers_preuves()
