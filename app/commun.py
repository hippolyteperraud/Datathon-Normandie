"""Fonctions partagées par les pages : lecture des sorties du moteur, formats, couleurs, cartes,
et lancement des commandes du moteur (python -m prairimetre ...).

Règle des données manquantes : on n'affiche jamais une case vide ou « None » ; chaque absence
est remplacée par sa raison (« moins de 20 ha de prairies », « non renseigné dans le Sandre »...).
"""
import re
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st

from prairimetre.config import CACHE, DATA, MIN_HA, RACINE, SORTIES, annees
from prairimetre.sources import SOURCES

TABLES = ["communes", "communes_zones", "serie_region", "captages", "communes_captages",
          "bilan_direct", "cultures_destination", "objectif", "suivi_sorties"]

# Chiffre officiel (vérifié sur Légifrance le 22/10/2026)
OFFICIEL = {"perte_ha": -59703, "perte_pct": -8.9, "ratio_evol_pct": -1.97,
            "date": "septembre 2026",
            "source": "Arrêté du 11 septembre 2026, JORF n° 0218 du 18 septembre 2026"}
# Baisse du ratio de prairies permanentes au-delà de laquelle tout retournement est interdit et les
# prairies retournées doivent être réimplantées (règlement délégué (UE) 2022/126, article 48)
SEUIL_RATIO_PCT = 5

DEPARTEMENTS = {"14": "Calvados", "27": "Eure", "50": "Manche", "61": "Orne",
                "76": "Seine-Maritime"}
# « les communes du Calvados », « de l'Eure »... (filtre Territoire des pages)

# Palette catégorielle : contraste ≥ 3:1 sur les fonds clair et sombre (vert assombri pour
# l'atteindre) ; chaque couleur est toujours doublée d'un libellé.
CAT = ["#2a78d6", "#eb6834", "#169c6c"]
NEUTRE = "#c3c2b7"
# Cartes (fond de carte blanc) : les mêmes états partout
HORS = "#a9a89f"     # des données, mais hors de la liste affichée
GRIS = "#6b6a65"     # pas de diagnostic : peu ou pas de prairies (villes, zones d'activité,
                     # communes de cultures). Le registre les couvre : ce n'est pas un manque
# Parcelles de « Ma commune » : une couleur par devenir, lisible sur fond blanc
FLUX_COULEURS = {"culture": "#c2452d", "non déclaré": "#f0a202", "prairie temporaire": "#2a78d6",
                 "prairie permanente": "#2e7d4f", "autre": "#5b5a55", "ajoutée": "#8a4fc4"}

# Les noms et couleurs partagés par les pages : l'objectif 2030, la liste des communes qui portent
# la moitié du retournement récent (son nom est repris par Où aller voir), la vérification.
ACTIONS = {
    "suivre": {"titre": "Suivre l'objectif en hectares", "couleur": CAT[0]},
    "payer": {"titre": "Communes où l'on retourne le plus", "couleur": CAT[0]},
    "verifier": {"titre": "Vérifier d'abord", "couleur": CAT[1]},
}


# --- Formats ----------------------------------------------------------------------------------

def nombre(x, dec=0, signe=False):
    """12 345,6 (espace fine insécable pour les milliers, virgule décimale, vrai signe moins)."""
    if x is None or pd.isna(x):
        return "–"
    s = f"{x:{'+' if signe else ''},.{dec}f}".replace(",", " ").replace(".", ",")
    return s.replace("-", "−")


def ha(x, signe=False):
    return f"{nombre(x, 0, signe)} ha"


def pct(x, dec=1, signe=False):
    return "–" if pd.isna(x) else f"{nombre(100 * x, dec, signe)} %"


def variation(x, unite="ha", dec=0):
    """Delta de st.metric : signe ASCII en tête (Streamlit en déduit flèche et couleur)."""
    if pd.isna(x):
        return None
    return f"{'-' if x < 0 else '+'}{nombre(abs(x), dec)} {unite}".strip()


# --- Lecture des sorties du moteur ------------------------------------------------------------

def manquantes():
    return [t for t in TABLES if not (SORTIES / f"{t}.csv").exists()]


def table(nom):
    """Table du moteur ; relue dès que le moteur l'a recalculée (date du fichier)."""
    return _lire(nom, (SORTIES / f"{nom}.csv").stat().st_mtime)


@st.cache_data(show_spinner=False)
def _lire(nom, date):  # « date » sans tiret bas : Streamlit ne hache pas les arguments « _… »
    if nom == "bilan_direct":
        return pd.read_csv(SORTIES / "bilan_direct.csv", header=[0, 1], index_col=0)
    t = pd.read_csv(SORTIES / f"{nom}.csv", dtype={"insee": str, "epci": str, "dep": str,
                                                   "aac": str})
    cle = {"communes": "insee", "captages": "aac", "cultures_destination": "culture"}.get(nom)
    return t.set_index(cle) if cle else t


def evaluation(nom, **kw):
    """Table d'évaluation du moteur, ou None si « evaluer » n'a pas encore tourné."""
    f = SORTIES / f"evaluation_{nom}.csv"
    return _evaluation(nom, f.stat().st_mtime, **kw) if f.exists() else None


@st.cache_data(show_spinner=False)
def _evaluation(nom, date, **kw):
    return pd.read_csv(SORTIES / f"evaluation_{nom}.csv", **kw)


def bornes():
    """Première et dernière année des résultats affichés, lues dans sorties/ : les pages restent
    cohérentes même si un registre vient d'être téléchargé sans être encore calculé."""
    f = SORTIES / "communes.csv"
    if f.exists():
        A = sorted(int(c[3:]) for c in pd.read_csv(f, nrows=0).columns
                   if re.fullmatch(r"pp_\d{4}", c))
    else:
        A = annees()
    return (A[0], A[-1]) if A else (None, None)


def exiger_sorties():
    """Arrête la page avec un message si le moteur n'a pas encore produit ses tables ; prévient
    si un registre plus récent que les résultats est en local (recalcul à lancer)."""
    m = manquantes()
    if m:
        st.warning("Les résultats du moteur sont incomplets (manquent : " + ", ".join(m)
                   + "). Lancez « Relancer les calculs » dans Technique → Recalculer.")
        st.page_link("vues/technique.py", label="Technique", icon=":material/build:")
        st.stop()
    A, an = annees(), bornes()[1]
    if A and A[-1] > an:
        st.warning(f"Le registre {A[-1]} est téléchargé, mais les résultats s'arrêtent à {an}. "
                   "Lancez « Relancer les calculs » dans Technique → Recalculer.")


def aides_chiffres():
    """Ce que compte chacun des trois chiffres de la Normandie (bande du haut, page Technique)."""
    return {"Prairimètre": "prairies permanentes déclarées à la PAC (RPG, groupe 18) : les PPH et, "
                           "jusqu'en 2022, les PRL, devenues PPH à 94 % en 2023.",
            "Chiffre officiel": f"prairies permanentes au sens réglementaire de la PAC. "
                                f"{OFFICIEL['source']}.",
            "Ratio officiel": f"part des prairies dans la surface agricole déclarée à la PAC, "
                              f"comparée à 2018. Au-delà de 4 % de baisse, les exploitants doivent "
                              f"compenser ; au-delà de {SEUIL_RATIO_PCT} %, tout retournement est "
                              "interdit et les prairies retournées doivent être réimplantées "
                              "(règlement délégué (UE) 2022/126, article 48 ; arrêté du 26 décembre "
                              "2025)."}


# --- Glossaire --------------------------------------------------------------------------------
# Les mots de l'appli, rangés par thème : (mot affiché, définition, formes reconnues dans le texte).
# Les formes sont des expressions régulières JavaScript, sans tenir compte des majuscules ; elles
# posent une bulle sur le mot dans toutes les pages. Une liste vide : le mot est dans l'onglet
# Glossaire mais n'a pas de bulle (trop courant ou ambigu pour être repéré seul).
GLOSSAIRE = {
    "Les chiffres officiels": [
        ("Statistique agricole", "les chiffres annuels du ministère de l'Agriculture (Agreste). C'est elle qui "
                                 "mesure l'objectif 2030.", [r"statistique agricole(?: annuelle)?"]),
        ("Agreste", "le service de la statistique du ministère de l'Agriculture.", [r"Agreste"]),
        ("Surface toujours en herbe", "dans la statistique agricole, l'herbe qui reste en place d'une année sur "
                                      "l'autre : prairies permanentes, landes, parcours. La mesure de l'objectif "
                                      "2030.", [r"surfaces? toujours en herbe", r"STH"]),
        ("SAU", "surface agricole utilisée : terres cultivées, prairies et cultures permanentes.", [r"SAU"]),
        ("Stratégie régionale pour la biodiversité", "le plan de la Région Normandie pour 2030 ; son objectif "
                                                     "III.5 : zéro perte nette de prairies permanentes.",
         [r"stratégie régionale pour la biodiversité"]),
    ],
    "Les prairies": [
        ("Prairie permanente", "de l'herbe ni labourée ni remise en culture depuis au moins 5 ans.",
         [r"prairies? permanentes?"]),
        ("Prairie temporaire", "de l'herbe semée depuis moins de 5 ans ; à la 6e année, elle devient permanente.",
         [r"prairies? temporaires?"]),
        ("Jeune prairie permanente", "devenue permanente depuis peu : quelques années avant, c'était une prairie "
                                     "temporaire ou une culture.", [r"jeunes? prairies?(?: permanentes?)?"]),
        ("Retournée", "labourée, puis remise en culture.", [r"retourn(?:ée|ées|és|é)", r"retournements?"]),
    ],
    "Le registre PAC": [
        ("PAC", "politique agricole commune : pour toucher ses aides, les agriculteurs déclarent chaque année "
                "leurs parcelles.", [r"PAC"]),
        ("Registre PAC", "la carte des parcelles déclarées à la PAC, publiée chaque année par l'IGN (RPG).",
         [r"registres? PAC", r"RPG"]),
        ("Sortie de la PAC", "une parcelle qui n'est plus déclarée. L'herbe peut être encore là.",
         [r"sorties? de la PAC", r"sorties? de la déclaration"]),
        ("Ajoutée depuis 2018", "déclarée prairie permanente pour la première fois après 2018.",
         [r"ajoutées? depuis \d{4}"]),
    ],
    "Le satellite": [
        ("Sentinel-2", "satellites européens (Copernicus) qui photographient la Normandie tous les 5 jours, en "
                       "pixels de 10 m.", [r"Sentinel-2"]),
        ("NDVI", "indice de verdure tiré des images satellite : haut pour de l'herbe qui pousse, bas pour de la "
                 "terre nue.", [r"NDVI"]),
        ("Restée verte", "sortie de la PAC, mais verte toute l'année sur les images, sans trace de labour.",
         [r"restées? vertes?"]),
        ("À vérifier sur le terrain", "sortie de la PAC : les images ne tranchent pas, ou la parcelle est trop "
                                      "petite pour être mesurée.", [r"à vérifier sur (?:le terrain|place)"]),
        ("Angle mort de la statistique", "des prés sortis de la PAC avant 2023, toujours fauchés ou pâturés, "
                                         "que la statistique agricole ne compte plus.", [r"angle mort"]),
        ("OCS GE", "la carte de l'occupation du sol de l'IGN (2022 ou 2023 selon le département).", [r"OCS GE"]),
        ("Photos aériennes", "les photos de l'IGN (BD ORTHO), regardées à l'œil pour contrôler le satellite.",
         [r"photos aériennes"]),
        ("Intervalle de confiance à 95 %", "la fourchette où se trouve la vraie valeur, avec 95 chances sur "
                                           "100.", [r"intervalles? de confiance"]),
    ],
    "Les règles et les zones": [
        ("BCAE", "règles environnementales à respecter pour toucher les aides de la PAC. BCAE 1 : garder assez de "
                 "prairies dans la région ; BCAE 2 : protéger zones humides et tourbières (depuis 2025) ; BCAE 9 : "
                 "ne pas retourner les prairies sensibles.", [r"BCAE(?: \d)?"]),
        ("Prairie sensible", "prairie permanente d'un site Natura 2000 où le labour est interdit (BCAE 9).",
         [r"prairies? sensibles?"]),
        ("Autorisation régionale", "quand la part de prairies de la région baisse trop, retourner une prairie "
                                   "demande une autorisation (en Normandie, en 2023-2024).",
         [r"autorisations? régionales?"]),
        ("Natura 2000", "réseau européen de sites naturels protégés.", [r"Natura 2000"]),
        ("ZNIEFF", "inventaire de milieux naturels remarquables, sans effet sur le labour.", [r"ZNIEFF"]),
        ("Zone de captage", "zone où la pluie rejoint un captage d'eau potable (aire d'alimentation de captage).",
         [r"zones? de captages?(?: d['’]eau)?", r"aires? d['’]alimentation (?:de|des) captages?",
          r"aires? de captages?"]),
        ("Nitrates", "forme de l'azote qui vient surtout des engrais et des effluents d'élevage ; au-delà de "
                     "50 mg/L, l'eau n'est plus potable.", [r"nitrates?"]),
        ("Hub'Eau", "portail public des données sur l'eau ; il diffuse les analyses de nitrates des rivières.",
         [r"Hub['’]?eau"]),
    ],
}


def glossaire():
    """Tous les mots, sans les thèmes : (mot, définition, formes)."""
    return [m for mots in GLOSSAIRE.values() for m in mots]


def bulles_glossaire():
    """Une bulle sur chaque mot du glossaire, dans toutes les pages : le mot est souligné en
    pointillé et sa définition s'affiche au survol.

    Le texte des pages n'est pas modifié (Streamlit le redessine à chaque interaction) : les mots
    sont repérés par le navigateur et soulignés avec l'API CSS Custom Highlight, et la bulle est un
    élément à part, posé au-dessus de la page. Sans cette API (vieux navigateur), la page reste
    lisible, sans les bulles."""
    import json
    termes = [{"mot": m, "def": d, "formes": f} for m, d, f in glossaire() if f]
    # Le script ne doit prendre aucune place dans la page : son conteneur est masqué
    st.html("<style>.st-key-glossaire_js {display:none}</style>")
    with st.container(key="glossaire_js"):
        _script_glossaire(termes)


def _script_glossaire(termes):
    # Streamlit écarte un script qui contient « < » (pris pour une balise) : le script est donc
    # passé en base64, décodé en UTF-8 puis exécuté par le navigateur
    import base64
    import json
    js = """
(() => {
  const TERMES = %s;
  const w = window, doc = document;
  if (!w.CSS || !CSS.highlights || !w.Highlight) return;
  const motif = new RegExp("(?<![\\\\p{L}\\\\p{N}-])(?:" + TERMES.map((t, i) =>
      "(" + t.formes.join("|") + ")").join("|") + ")(?![\\\\p{L}\\\\p{N}-])", "giu");
  const IGNORER = "code, pre, a, button, input, textarea, svg, script, style, [data-testid='stHeader'],"
      + " [data-testid='stSidebar'], [class*='st-key-glossaire_liste'], .gl-bulle, [role='tooltip'],"
      + " [data-testid='stTooltipContent'], .equipe, [data-testid='stTabs'] [role='tab']";
  let zones = [];  // {range, terme}
  const souligne = new Highlight();
  CSS.highlights.set("glossaire", souligne);
  if (!doc.getElementById("gl-style")) {
    const s = doc.createElement("style"); s.id = "gl-style";
    // Aucun soulignement : le mot reste tel quel, la bulle s'ouvre au survol
    s.textContent = ".gl-bulle{position:fixed;z-index:1000000;max-width:320px;padding:.5rem .7rem;border-radius:8px;"
      + "background:#262730;color:#fafafa;font:400 .82rem/1.35 'Source Sans Pro',sans-serif;"
      + "box-shadow:0 4px 14px rgba(0,0,0,.25);pointer-events:none;display:none}"
      + ".gl-bulle b{display:block;margin-bottom:.1rem}";
    doc.head.appendChild(s);
  }
  let bulle = doc.querySelector(".gl-bulle");
  if (!bulle) { bulle = doc.createElement("div"); bulle.className = "gl-bulle"; doc.body.appendChild(bulle); }

  function scanner() {
    zones = []; souligne.clear();
    const racines = doc.querySelectorAll("[data-testid='stMain'], [role='dialog']");
    racines.forEach(racine => {
      const marche = doc.createTreeWalker(racine, NodeFilter.SHOW_TEXT, {acceptNode: n =>
        !n.nodeValue.trim() || !n.parentElement || n.parentElement.closest(IGNORER)
          ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT});
      const vus = new Map();  // un seul soulignement par mot et par bloc de texte
      for (let n = marche.nextNode(); n; n = marche.nextNode()) {
        const bloc = n.parentElement.closest("[data-testid='stElementContainer'], [data-testid='stExpander'] summary") || racine;
        if (!vus.has(bloc)) vus.set(bloc, new Set());
        motif.lastIndex = 0;
        for (let m; (m = motif.exec(n.nodeValue));) {
          const i = m.slice(1).findIndex(x => x !== undefined);
          if (i < 0) continue;
          const r = doc.createRange();
          r.setStart(n, m.index); r.setEnd(n, m.index + m[0].length);
          zones.push({range: r, terme: TERMES[i]});
          if (!vus.get(bloc).has(i)) { vus.get(bloc).add(i); souligne.add(r); }
        }
      }
    });
  }
  let attente = null;
  const plusTard = () => { clearTimeout(attente); attente = setTimeout(scanner, 250); };
  if (w.__glObs) w.__glObs.disconnect();
  // la bulle elle-même change à chaque survol : ce n'est pas une raison de relire la page
  w.__glObs = new MutationObserver(l => { if (l.some(m => !bulle.contains(m.target))) plusTard(); });
  w.__glObs.observe(doc.body, {childList: true, subtree: true, characterData: true});
  scanner();

  function cacher() { bulle.style.display = "none"; }
  function survol(e) {
    const x = e.clientX, y = e.clientY;
    for (const z of zones) {
      if (!z.range.startContainer.isConnected) continue;
      for (const b of z.range.getClientRects()) {
        if (x >= b.left && x <= b.right && y >= b.top - 2 && y <= b.bottom + 2) {
          bulle.innerHTML = "<b></b><span></span>";
          bulle.firstChild.textContent = z.terme.mot;
          bulle.lastChild.textContent = z.terme.def;
          bulle.style.display = "block";
          const l = Math.min(b.left, w.innerWidth - bulle.offsetWidth - 8);
          const haut = b.top - bulle.offsetHeight - 6;
          bulle.style.left = Math.max(8, l) + "px";
          bulle.style.top = (haut > 4 ? haut : b.bottom + 6) + "px";
          return;
        }
      }
    }
    cacher();
  }
  let image = 0;
  if (w.__glSurvol) doc.removeEventListener("mousemove", w.__glSurvol);
  w.__glSurvol = e => { cancelAnimationFrame(image); image = requestAnimationFrame(() => survol(e)); };
  doc.addEventListener("mousemove", w.__glSurvol, {passive: true});
  if (!w.__glDefile) { w.__glDefile = true;
    doc.addEventListener("scroll", () => { const b = doc.querySelector(".gl-bulle"); if (b) b.style.display = "none"; },
                         {passive: true, capture: true}); }
})();
""" % json.dumps(termes, ensure_ascii=False)
    code = base64.b64encode(js.encode("utf-8")).decode()
    st.html(f'<script>(0, eval)(new TextDecoder().decode(Uint8Array.from(atob("{code}"), c => c.charCodeAt(0))));'
            '</script>', unsafe_allow_javascript=True)


GAIN_MINIMUM_HA = 5   # en dessous, le gain pèse moins qu'une parcelle : ce n'est pas un exemple
PERTE_MAXIMUM_HA = 1   # en dessous, un écart de contour d'une année à l'autre, pas une perte


def communes_exemples(t):
    """Les communes où ça va bien : (gain, gardent). gain : hectares gagnés de façon assurée sur
    d'anciennes cultures (ni une prairie temporaire devenue permanente, ni une nouvelle déclaration),
    net de ce qui a été perdu, au moins GAIN_MINIMUM_HA ; gardent : les autres communes qui n'ont
    perdu aucune prairie de la première année."""
    calc = t[t.statut == "calculé"]
    sur_cultures = calc.venues_culture - calc.devenues_culture
    temporaires = (calc.venues_temporaire - calc.devenues_temporaire).clip(lower=0)
    declarees = calc.venues_non_declare - calc.devenues_non_declare
    assure = pd.concat([calc.solde, sur_cultures], axis=1).min(axis=1)
    gain = assure[(calc.solde > 0) & (sur_cultures >= declarees + temporaires) & (assure >= GAIN_MINIMUM_HA)]
    gardent = [i for i in calc.index[calc.disparues < PERTE_MAXIMUM_HA] if i not in set(gain.index)]
    return gain, gardent


# Chaque auteur, son école et le logo de l'école (dans app/assets), avec sa hauteur à l'écran en pixels :
# les deux logos n'ont pas la même forme, ces hauteurs leur donnent un poids voisin
EQUIPE = [("Hippolyte Perraud", "INSA Rouen Normandie", "logo_insa_rouen.png", 25),
          ("Mouhssine Bairoune", "ENSICAEN", "logo_ensicaen.png", 38)]


@st.cache_data
def _logo(fichier):
    """Le logo en data URI (le HTML de st.markdown ne lit pas les fichiers locaux) ; None s'il manque."""
    import base64
    f = Path(__file__).parent / "assets" / fichier
    return f"data:image/png;base64,{base64.b64encode(f.read_bytes()).decode()}" if f.exists() else None


def equipe():
    """Les auteurs et le logo de leur école, en haut à droite de toutes les pages, au niveau du menu.
    Sur un écran trop étroit, ils passent sous le menu. Le logo est posé sur un fond blanc, pour rester
    lisible en thème sombre ; s'il manque, le nom de l'école le remplace."""
    def case(nom, ecole, fichier, hauteur):
        src = _logo(fichier)
        marque = (f'<img src="{src}" alt="{ecole}" title="{ecole}" style="height:{hauteur}px">' if src
                  else f'<span class="ecole">{ecole}</span>')
        return f'<span class="case"><span class="nom">{nom}</span><span class="marque">{marque}</span></span>'
    st.markdown(
        "<style>"
        ".equipe {display:flex;align-items:center;gap:1.4rem;position:fixed;top:0;right:3.2rem;"
        "height:3.75rem;z-index:999999}"
        ".equipe .case {display:flex;align-items:center;gap:0.55rem}"
        ".equipe .nom {font-size:0.92rem;font-weight:700;white-space:nowrap}"
        ".equipe .marque {display:flex;align-items:center;background:#fff;border-radius:6px;"
        "padding:3px 6px}"
        ".equipe .marque img {display:block}"
        ".equipe .ecole {font-size:0.72rem;color:#1f2a24;white-space:nowrap}"
        "@media (max-width:1100px) {.equipe {position:static;height:auto;flex-wrap:wrap;"
        "margin-bottom:1rem}}"
        "</style>"
        f'<div class="equipe">{"".join(case(*e) for e in EQUIPE)}</div>', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _herbe(date_mesures):
    from prairimetre import sentinel as sen
    return sen.herbe_reelle()


def herbe_communes():
    """Ce que sont devenues, en hectares, les prairies de la première année, commune par commune (voir
    sentinel.herbe_reelle). Recalculé quand le bloc des mesures satellite change."""
    from prairimetre import sentinel as sen
    f = sen.bloc()[0]
    return _herbe(f.stat().st_mtime if f.exists() else 0)


def comparaison(zonage):
    """Retourne-t-on « moins », « autant » ou « plus » dans ce zonage qu'à côté, dans la même
    commune ? Tranché sur toutes les périodes testées par le moteur : « autant » si les rapports
    encadrent 1. Renvoie (sens, rapports), ou (None, série vide) si l'évaluation manque."""
    rob, z = evaluation("robustesse"), evaluation("zonages", index_col=0)
    v = rob[rob.zonage == zonage].rapport_meme_commune if rob is not None else pd.Series()
    if v.empty and z is not None and zonage in z.index:
        v = pd.Series([z.loc[zonage, "rapport_meme_commune"]])
    if v.empty:
        return None, v
    return ("moins" if v.max() < 1 else "plus" if v.min() > 1 else "autant"), v


def motif_manquant(statut):
    """Pourquoi une commune n'a pas de diagnostic, en clair ; None si elle en a un."""
    if statut == "aucune prairie":
        return "Aucune prairie permanente déclarée dans la commune."
    if statut.startswith("moins de"):
        return f"Trop peu de prairies ({statut}) pour qu'un taux ait un sens."
    return None


def date_source(nom):
    """Date du fichier d'une source dans data/ (0 s'il n'y est pas) : sert de clé aux caches de
    l'appli, qui se refont dès que la source est réimportée."""
    f = DATA / SOURCES[nom]["fichier"]
    return f.stat().st_mtime if f.exists() else 0


# --- Cartes ------------------------------------------------------------------------------------

def _sur_disque(nom, fabrique):
    """Géométries de carte gardées dans cache/ : calculées une seule fois, même après un
    redémarrage (premier affichage rapide)."""
    import geopandas as gpd
    f = CACHE / f"carte_{nom}.parquet"
    if f.exists():
        return gpd.read_parquet(f)
    g = fabrique()
    g.to_parquet(f)
    return g


def communes_carte():
    """Contours des communes simplifiés (≈ 80 m) en WGS84, légers pour le navigateur."""
    return _communes_carte(date_source("communes"))


@st.cache_data(show_spinner="Préparation de la carte…")
def _communes_carte(date):
    def f():
        from prairimetre.donnees import communes
        g = communes()[["insee", "nom_officiel", "dep", "epci", "geometry"]].copy()
        g["geometry"] = g.geometry.simplify(80, preserve_topology=True)
        return g.to_crs(4326)
    return _sur_disque("communes", f)


def hex_rgb(h, alpha=220):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)] + [alpha]


def deck(couches, vue_sur, info, hauteur=560, zoom=None):
    """Carte pydeck. couches : liste de (GeoDataFrame WGS84 avec colonne 'couleur', id) ;
    vue_sur : GeoDataFrame sur lequel centrer ; info : HTML du survol ; zoom : imposé pour une petite
    carte (sinon tiré de l'étendue)."""
    layers = [pdk.Layer("GeoJsonLayer", data=g.__geo_interface__, id=i, pickable=True,
                        stroked=True, filled=True, get_fill_color="properties.couleur",
                        get_line_color=[255, 255, 255, 160], line_width_min_pixels=0.5,
                        auto_highlight=True) for g, i in couches]
    b = vue_sur.total_bounds
    etendue = max(b[2] - b[0], b[3] - b[1])
    zoom = zoom or (6.8 if etendue > 2 else 8.2 if etendue > 0.8 else 9.5 if etendue > 0.3 else 11)
    vue = pdk.ViewState(longitude=(b[0] + b[2]) / 2, latitude=(b[1] + b[3]) / 2, zoom=zoom)
    # Le fond de carte est toujours affiché (il demande une connexion internet)
    return pdk.Deck(layers=layers, initial_view_state=vue, map_provider="carto",
                    map_style="light", height=hauteur,
                    tooltip={"html": info, "style": {"fontSize": "12px"}})


def selection_carte(evenement, couche, champ):
    """Valeur du champ de l'objet cliqué sur la carte, ou None."""
    if evenement and evenement.selection:
        objets = evenement.selection.objects.get(couche, [])
        if objets:
            return objets[0]["properties"].get(champ)
    return None


# --- Titres et légendes des figures ----------------------------------------------------------
# Toutes les cartes et tous les graphiques de l'appli ont un titre au-dessus ; les légendes des cartes
# sont placées en dessous.

def titre_figure(texte, cible=None, aide=None):
    """Le titre d'une carte ou d'un graphique, au-dessus de la figure (même style partout)."""
    (cible or st).markdown(f"<div style='font-weight:700;font-size:1.02rem;margin:0 0 .15rem'>{texte}</div>",
                           unsafe_allow_html=True, help=aide)


def legende(elements, note="", cible=None):
    """La légende d'une carte, sous la carte : elements = [(couleur, libellé, forme ● ou ■)]."""
    morceaux = [f"<span style='white-space:nowrap'><span style='color:{c};font-size:1.1em'>{forme}</span> {lib}</span>"
                for c, lib, forme in elements]
    (cible or st).markdown(
        "<div style='font-size:.88rem;margin-top:-.4rem;display:flex;flex-wrap:wrap;gap:.3rem 1.1rem'>"
        + "".join(morceaux) + (f"<span style='opacity:.7'>{note}</span>" if note else "") + "</div>",
        unsafe_allow_html=True)


def espace(rem):
    """Un espace vertical, pour aérer une page ou aligner deux colonnes."""
    st.html(f"<div style='height:{rem}rem'></div>")


# --- Graphiques ------------------------------------------------------------------------------

# Graduations d'axe à la française (« 620 000 », « −20 000 ») : Vega écrirait « 620k »
AXE_FR = "replace(format(datum.value, ',.0f'), regexp(',', 'g'), ' ')"


# --- Appel du moteur en ligne de commande ----------------------------------------------------
