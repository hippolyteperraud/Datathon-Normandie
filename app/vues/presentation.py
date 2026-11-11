"""0. Accueil : le problème, notre réponse, et une carte par onglet (mesurer, localiser, agir, vérifier)
avec son lien. Aucun résultat ici : ils sont dans les onglets. Tient sur un écran sans dérouler."""
import streamlit as st

from commun import EQUIPE, bornes, exiger_sorties

exiger_sorties()
a0, an = bornes()
VERT, BLEU, ORANGE, GRIS = "#2e7d4f", "#2a78d6", "#eb6834", "#8a8f98"

st.html("<style>[data-testid='stMainBlockContainer']{padding-top:6.3rem !important}"
        ".acc-fait{font-size:1.9rem;font-weight:800;line-height:1.1}"
        ".acc-fait-t{font-size:.95rem;line-height:1.4;margin-top:.25rem}"
        ".acc-n{display:inline-block;width:1.7rem;height:1.7rem;line-height:1.7rem;border-radius:50%;"
        "text-align:center;font-weight:700;color:#fff;margin-right:.5rem}"
        ".acc-c{font-weight:700;font-size:1.1rem}.acc-q{font-size:.92rem;line-height:1.4;margin:.4rem 0 .2rem;"
        "min-height:2.8em}.acc-o{font-size:.8rem;opacity:.65;text-transform:uppercase;letter-spacing:.03em}"
        ".st-key-acc_pb{background:rgba(128,128,128,.07)}"
        "[class*='st-key-carte_'] [data-testid='stPageLink'] a{padding-left:0 !important}</style>")

with st.container(border=True, key="acc_pb"):
    p1, p2 = st.columns(2, gap="large")
    p1.html(f"<div class='acc-o'>Le problème</div><div class='acc-fait' style='color:{GRIS}'>Un seul chiffre"
            "</div><div class='acc-fait-t'>La statistique agricole, qui fait foi, dit <b>combien</b> d'herbe "
            "la Normandie perd. Elle ne dit pas <b>où</b>, ni <b>pourquoi</b>.</div>")
    p2.html(f"<div class='acc-o'>Notre réponse</div><div class='acc-fait' style='color:{VERT}'>Chaque "
            "parcelle</div><div class='acc-fait-t'>Nous croisons le registre PAC et les <b>images "
            "satellite</b>, prairie par prairie : <b>où</b> sont les prairies, ce qu'elles deviennent, et ce qui "
            "marche pour les garder.</div>")

st.html("<div style='height:.9rem'></div>")
CARTES = [
    (VERT, "1", "Mesurer", "vues/objectif.py", "Objectif 2030", ":material/flag:",
     "L'objectif est-il tenu ? Chiffre officiel et recomptage satellite."),
    (BLEU, "2", "Localiser", "vues/commune.py", "Ma commune", ":material/location_city:",
     f"La carte des communes et l'évolution de leurs prairies depuis {a0}."),
    (ORANGE, "3", "Agir", "vues/regles.py", "Recommandations", ":material/lightbulb:",
     "Ce qui marche ou pas : règles testées et idées nouvelles."),
    (GRIS, "4", "Vérifier", "vues/technique.py", "Technique", ":material/build:",
     "Les preuves, les sources, et la relance des calculs."),
]
for col, (couleur, n, verbe, page, onglet, icone, texte) in zip(st.columns(4, gap="medium"), CARTES):
    with col, st.container(border=True, key=f"carte_{n}"):
        st.html(f"<div><span class='acc-n' style='background:{couleur}'>{n}</span><span class='acc-c'>"
                f"{verbe}</span></div><div class='acc-q'>{texte}</div>")
        st.page_link(page, label=onglet, icon=icone)

# Le pied de page, collé en bas de l'écran
st.html("<div style='position:fixed;left:0;right:0;bottom:.7rem;text-align:center;font-size:.85rem;opacity:.7;"
        "pointer-events:none'>Datathon 2026 de la Région Normandie · "
        + " et ".join(nom for nom, *_ in EQUIPE) + " · données ouvertes (open data)</div>")
