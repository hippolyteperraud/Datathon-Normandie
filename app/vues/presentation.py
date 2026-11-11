"""0. Accueil : ce qu'est Prairimètre, le problème qu'il traite, et une carte par onglet (mesurer,
localiser, agir, vérifier) avec son lien. Tient sur un écran sans dérouler. Les deux chiffres affichés
sont lus aux mêmes sources que l'onglet Objectif 2030 (table « objectif » et
verification/sentinel2/<an>/herbe_hors_pac.json)."""
import json

import streamlit as st

from commun import bornes, exiger_sorties, ha, nombre, table
from prairimetre import sentinel as sen

exiger_sorties()
a0, an = bornes()
VERT, ROUGE, BLEU, ORANGE, GRIS = "#2e7d4f", "#c2452d", "#2a78d6", "#eb6834", "#8a8f98"

obj = table("objectif").set_index("annee")
sth = obj.sth_ha.dropna().astype(int)
a_ref, fin = int(obj.annee_reference.iloc[0]), int(sth.index.max())
ecart = int(sth.loc[fin] - sth.loc[a_ref])
f = sen.DOSSIER / str(an) / "herbe_hors_pac.json"
hp = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
precision = None
if hp and "origines" in hp and str(an) in hp.get("agreste", {}).get("annees", {}):
    A = hp["agreste"]["annees"][str(an)]
    nous = A["registre_pp"] + sum(hp["origines"]["total"][k] for k in ("jamais", "avant_2023", "depuis_2023"))
    precision = 100 * abs(nous / (A["expl"] + A["hors"]) - 1)

st.html("<style>[data-testid='stMainBlockContainer']{padding-top:3.4rem !important}"
        ".acc-titre{font-size:2.3rem;font-weight:800;line-height:1.1}"
        ".acc-sous{font-size:1.08rem;opacity:.85;margin:.35rem 0 1rem;max-width:62rem}"
        ".acc-fait{font-size:1.9rem;font-weight:800;line-height:1.1}"
        ".acc-fait-t{font-size:.92rem;line-height:1.4;margin-top:.2rem}"
        ".acc-n{display:inline-block;width:1.7rem;height:1.7rem;line-height:1.7rem;border-radius:50%;"
        "text-align:center;font-weight:700;color:#fff;margin-right:.5rem}"
        ".acc-c{font-weight:700;font-size:1.1rem}.acc-q{font-size:.92rem;line-height:1.4;margin:.4rem 0 .3rem;"
        "min-height:4.2em}.acc-o{font-size:.8rem;opacity:.65;text-transform:uppercase;letter-spacing:.03em}"
        ".st-key-acc_pb{background:rgba(128,128,128,.07)}"
        "[class*='st-key-carte_'] [data-testid='stPageLink'] a{padding-left:0 !important}</style>")

st.html("<div class='acc-titre'>Prairimètre</div>"
        "<div class='acc-sous'>Suivre, parcelle par parcelle, l'objectif normand de <b>zéro perte nette de "
        "prairies permanentes d'ici 2030</b>, et trouver où agir.</div>")

with st.container(border=True, key="acc_pb"):
    p1, p2, p3 = st.columns([1, 1, 1.15], gap="large")
    p1.html(f"<div class='acc-o'>Le constat</div><div class='acc-fait' style='color:{ROUGE}'>"
            f"{ha(ecart, signe=True)}</div><div class='acc-fait-t'>de surface toujours en herbe en Normandie "
            f"depuis {a_ref} ({fin} provisoire). L'objectif n'est pas tenu.</div>")
    p2.html(f"<div class='acc-o'>Le problème</div><div class='acc-fait' style='color:{GRIS}'>Un seul chiffre"
            "</div><div class='acc-fait-t'>La statistique agricole, qui fait foi, dit <b>combien</b> d'herbe "
            "la région perd. Elle ne dit pas <b>où</b>, ni <b>pourquoi</b>.</div>")
    p3.html(f"<div class='acc-o'>Notre réponse</div><div class='acc-fait' style='color:{VERT}'>Chaque "
            "parcelle</div><div class='acc-fait-t'>Le registre PAC et le satellite, prairie par prairie, "
            "commune par commune"
            + (f" ; recompté ainsi, le total d'herbe retombe sur la statistique à {nombre(precision, 0)} % près"
               if precision is not None else "") + ".</div>")

st.html("<div class='acc-o' style='margin:.6rem 0 .3rem'>Ce que vous pouvez faire</div>")
CARTES = [
    (VERT, "1", "Mesurer", "vues/objectif.py", "Objectif 2030", ":material/flag:",
     "L'objectif est-il tenu ? Le chiffre officiel, année par année, et notre recomptage au satellite."),
    (BLEU, "2", "Localiser", "vues/commune.py", "Ma commune", ":material/location_city:",
     f"La carte de chaque prairie de la commune : toujours en herbe, retournée, à vérifier, depuis {a0}."),
    (ORANGE, "3", "Agir", "vues/regles.py", "Recommandations", ":material/lightbulb:",
     "Les règles qui freinent vraiment le retournement, testées sur nos données, et où les appliquer."),
    (GRIS, "4", "Vérifier", "vues/technique.py", "Technique", ":material/build:",
     "Les preuves de chaque résultat, les sources, et le bouton qui relance tous les calculs."),
]
for col, (couleur, n, verbe, page, onglet, icone, texte) in zip(st.columns(4, gap="medium"), CARTES):
    with col, st.container(border=True, key=f"carte_{n}"):
        st.html(f"<div><span class='acc-n' style='background:{couleur}'>{n}</span><span class='acc-c'>"
                f"{verbe}</span></div><div class='acc-q'>{texte}</div>")
        st.page_link(page, label=f"Ouvrir {onglet}", icon=icone)

st.html("<div style='font-size:.82rem;opacity:.7;margin-top:.3rem'><b>Données publiques</b> : registre "
        f"parcellaire graphique PAC {a0}-{an} (IGN / ASP), images satellite Sentinel-2 (Copernicus), "
        "occupation du sol OCS GE (IGN), statistique agricole annuelle (Agreste). Datathon Normandie 2026.</div>")
