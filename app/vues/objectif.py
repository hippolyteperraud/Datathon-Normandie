"""1. L'objectif 2030, sur un seul écran (le but du projet est présenté dans l'onglet Accueil) : la statistique agricole dit combien
de prairies la Normandie perd ; Prairimètre dit où, parcelle par parcelle, et le vérifie au satellite.
- À gauche, le constat officiel (statistique agricole, en hectares depuis 2021).
- À droite, ce que Prairimètre ajoute : où (les cartes de Ma commune additionnées), fiable (notre
  recomptage satellite face à la statistique, chiffres de verification/sentinel2/<an>/herbe_hors_pac.json
  calculés par python -m prairimetre.sentinel_nuit resumer), et ce que la statistique ne voit plus.
Le détail, limites comprises, s'ouvre dans des fenêtres. Versions précédentes : app/sauvegardes/."""
import json

import pandas as pd
import streamlit as st

from commun import DEPARTEMENTS, bornes, exiger_sorties, ha, nombre, table
from prairimetre import sentinel as sen
from prairimetre.donnees import DATA, SOURCES, prairies
from references import OBJECTIF_REGIONAL, SUIVI_SRB

exiger_sorties()
a0, an = bornes()
VERT, ROUGE, ORANGE = "#2e7d4f", "#c2452d", "#f0a202"
# Les trois parts de l'herbe hors registre PAC (palette catégorielle : bleu, aqua, orange, dans cet ordre)
BLEU, AQUA, ORANGE_VIF = "#2a78d6", "#1baf7a", "#eb6834"
GRIS = "rgba(128,128,128,.45)"
GRIS_PAC = "#8a8f98"          # le registre PAC, commun aux deux côtés du bilan
DISCRET = "font-size:.78rem;opacity:.65"
PETIT_TITRE = "font-size:.78rem;opacity:.7;text-transform:uppercase;letter-spacing:.03em;margin-bottom:.25rem"
# Une seule page : moins de marge en haut, titre plus petit
st.html("<style>[data-testid='stMainBlockContainer']{padding-top:3.4rem !important;padding-bottom:.5rem}"
        "h1{font-size:1.75rem !important;padding:.2rem 0 0 !important}</style>")

# Les lignes du tableau : famille -> [(clé de la carte, mot de Ma commune)]. « sortie, bâtie » est dans
# « pas en herbe » comme sur la carte de Ma commune.
FAMILLES = {
    "En herbe": (VERT, [("toujours", "toujours en prairie"), ("verte", "sortie, restée verte"),
                        ("temporaire", "devenue prairie temporaire"), ("ajoutee", f"ajoutée depuis {a0}")]),
    "Pas en herbe": (ROUGE, [("culture", "retournée en culture"), ("autre", "bois, lande, autre"),
                             ("labouree", "sortie, labourée"), ("batie", "sortie, bâtie")]),
    "On ne sait pas": (ORANGE, [("verifier", "sortie, à vérifier sur le terrain")]),
}


@st.cache_data(show_spinner="Le moteur additionne les cartes de toutes les communes…")
def _carte(date_mesures, annee):
    return sen.herbe_carte()


@st.cache_data(show_spinner=False)
def _passage(annee):
    """Statistique agricole de l'année (herbe des exploitations, hors exploitations) et prairies
    permanentes déclarées au registre PAC."""
    t = pd.read_csv(DATA / SOURCES["saa_series"]["fichier"]).set_index("annee")
    return (int(t.loc[annee, "sth_exploitations"]), int(t.loc[annee, "sth_hors_exploitations"]),
            int(round(prairies(annee).surf_parc.sum())))


@st.cache_data(show_spinner=False)
def _hors_pac_lu(annee, date_fichier):
    f = sen.DOSSIER / str(annee) / "herbe_hors_pac.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def _hors_pac(annee):
    """Les chiffres de herbe_hors_pac.json, relus dès que le fichier change."""
    f = sen.DOSSIER / str(annee) / "herbe_hors_pac.json"
    return _hors_pac_lu(annee, f.stat().st_mtime if f.exists() else 0)


# --- Les chiffres ----------------------------------------------------------------------------------
obj = table("objectif").set_index("annee")
sth = obj.sth_ha.dropna().astype(int)
a_ref, fin = int(obj.annee_reference.iloc[0]), int(sth.index.max())
ecart = int(sth.loc[fin] - sth.loc[a_ref])

bloc = sen.bloc()[0]
h = _carte(bloc.stat().st_mtime if bloc.exists() else 0, an)
# Chaque case est arrondie à l'hectare, puis TOUTES les sommes sont faites sur les cases arrondies
cases = h.pivot_table(index="cle", columns="dep", values="ha", aggfunc="sum").fillna(0).round().astype(int)
deps = [d for d in DEPARTEMENTS if d in cases.columns]
cases = cases[deps].reindex([c for _, (_, l) in FAMILLES.items() for c, _ in l], fill_value=0)
cases["Normandie"] = cases.sum(axis=1)
colonnes = [DEPARTEMENTS[d] for d in deps] + ["Normandie"]
cases.columns = colonnes

hp = _hors_pac(an) if fin == an and an in sth.index else None
cb = hp.get("courbe") if hp else None
if cb:
    expl, hors, pac = _passage(an)
    assert expl + hors == int(sth.loc[an])
    X = hp["origines"]["total"]                          # origine exacte, géométrie entière
    recent, jamais, ancien = X["depuis_2023"], X["jamais"], X["avant_2023"]
    vu = recent + jamais + ancien
    assert abs(vu - cb["ha_nature"]["herbe"]) <= 3      # arrondis : le total affiché est la somme des parts
    expl_hors = expl - pac                               # herbe des exploitations non déclarée en prairie permanente
    autre_reg = sum(hp["registre_autre_herbe"].values())  # vergers et surfaces pastorales du registre
    pr_anc, pr_rec = hp["photos"]["sortie avant 2023"], hp["photos"]["sortie depuis 2023"]
    n_anc, n_rec = sum(pr_anc.values()), sum(pr_rec.values())
    conf = cb["confusion_pct"]
    ag = {int(a): x for a, x in hp["agreste"]["annees"].items()}
    PD = hp["origines"]["par_dep"]
    HD = {d: x[str(an)] for d, x in hp["agreste"]["hors_par_dep"].items()}
    ecart_dep = {d: PD[d]["jamais"] + PD[d]["avant_2023"] - HD[d] for d in DEPARTEMENTS if d in PD and d in HD}
    ecart_total = vu - (expl_hors + hors)


# --- Petits graphiques en HTML ---------------------------------------------------------------------
def barres_annees(valeurs, couleurs, titre_g, note, H=70, signe=False):
    """Barres verticales par année, depuis le zéro (vers le haut ou vers le bas)."""
    m = max(abs(x) for x in valeurs.values()) or 1
    haut = max([0] + [x for x in valeurs.values() if x > 0]) / m * H
    bas = max([0] + [-x for x in valeurs.values() if x < 0]) / m * H
    cols = []
    for a, x in valeurs.items():
        hb = abs(x) / m * H
        b = (f"<div title='{a} : {ha(x, signe=signe)}' style='height:{hb:.0f}px;background:{couleurs[a]};"
             f"border-radius:{'4px 4px 0 0' if x > 0 else '0 0 4px 4px'};margin:0 14%'></div>")
        cols.append(f"<div style='flex:1;text-align:center'>"
                    f"<div style='height:{haut:.0f}px;display:flex;flex-direction:column;justify-content:flex-end'>"
                    f"{b if x > 0 else ''}</div><div style='border-top:2px solid {GRIS}'></div>"
                    f"<div style='height:{bas:.0f}px'>{b if x < 0 else ''}</div>"
                    f"<div style='font-size:.74rem;font-weight:600;font-variant-numeric:tabular-nums;white-space:nowrap'>"
                    f"{nombre(x, signe=signe)}</div><div style='{DISCRET}'>{a}</div></div>")
    return (f"<div style='font-weight:600;font-size:.88rem;margin-bottom:.25rem'>{titre_g}</div>"
            f"<div style='display:flex;gap:3px;align-items:flex-start'>{''.join(cols)}</div>"
            f"<div style='{DISCRET};margin-top:.2rem'>{note}</div>")


def barre(nom, sous_titre, segments, echelle):
    """Une ligne du bilan : nom, barre à l'échelle (segments de couleur séparés de 2 px), total."""
    total = sum(s[0] for s in segments)
    cases_b, etiquettes = [], []
    for i, (val, couleur, info) in enumerate(segments):
        w = 100 * val / echelle
        rayon = "0 4px 4px 0" if i == len(segments) - 1 else "0"
        cases_b.append(f"<div title='{info} : {ha(val)}' style='width:calc({w:.3f}% - 2px);background:{couleur};"
                       f"border-radius:{rayon};flex:none'></div>")
        # Étiquette sous le segment s'il est assez large ; sinon le chiffre est dans l'infobulle et en dessous
        etiquettes.append(f"<div style='width:calc({w:.3f}% - 2px);flex:none;text-align:center;overflow:visible;"
                          f"font-variant-numeric:tabular-nums;white-space:nowrap;font-size:.78rem'>"
                          f"{nombre(val) if w >= 9 else ''}</div>")
    return (f"<div style='line-height:1.15'><b>{nom}</b><div style='{DISCRET}'>{sous_titre}</div></div>"
            f"<div><div style='display:flex;gap:2px;height:24px'>{''.join(cases_b)}</div>"
            f"<div style='display:flex;gap:2px;margin-top:.1rem'>{''.join(etiquettes)}</div></div>"
            f"<div style='font-weight:700;white-space:nowrap;font-variant-numeric:tabular-nums'>{ha(total)}</div>")


def barres_dep(valeurs, titre_g, note):
    """Barres horizontales de part et d'autre du zéro, une par département."""
    m = max(abs(x) for x in valeurs.values()) or 1
    lig = []
    for d, x in valeurs.items():
        w = 50 * abs(x) / m
        cote = (f"left:50%;width:{w:.1f}%;background:{ORANGE_VIF};border-radius:0 4px 4px 0" if x > 0 else
                f"right:50%;width:{w:.1f}%;background:{AQUA};border-radius:4px 0 0 4px")
        lig.append(f"<div style='display:grid;grid-template-columns:7.5rem 1fr 6.5rem;align-items:center;gap:.4rem'>"
                   f"<div style='font-size:.88rem'>{DEPARTEMENTS[d]}</div>"
                   f"<div title='{DEPARTEMENTS[d]} : {ha(x, signe=True)}' style='position:relative;height:22px'>"
                   f"<div style='position:absolute;left:50%;top:0;bottom:0;border-left:2px solid {GRIS}'></div>"
                   f"<div style='position:absolute;top:3px;bottom:3px;{cote}'></div></div>"
                   f"<div style='font-size:.85rem;text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap'>"
                   f"{ha(x, signe=True)}</div></div>")
    return (f"<div style='font-weight:600;font-size:.88rem;margin-bottom:.3rem'>{titre_g}</div>"
            + "".join(lig) + f"<div style='{DISCRET};margin-top:.3rem'>{note}</div>")


CELLULE = "padding:.18rem .55rem;text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap"
TRAIT = "border-top:1px solid rgba(128,128,128,.35)"


def tableau(details):
    """Le tableau des parcelles : les trois familles et le total ; avec le détail de chaque famille."""
    def ligne(nom, valeurs, style_nom="", style="", pastille=None):
        p = (f"<span style='display:inline-block;width:.7rem;height:.7rem;border-radius:3px;background:{pastille};"
             "margin-right:.45rem;vertical-align:-1px'></span>") if pastille else ""
        tds = "".join(f"<td style='{CELLULE};{style}{';font-weight:700' if c == 'Normandie' else ''}'>{nombre(v)}</td>"
                      for c, v in valeurs.items())
        return f"<tr><td style='padding:.18rem .55rem;{style_nom};{style}'>{p}{nom}</td>{tds}</tr>"

    html = ["<table style='width:100%;border-collapse:collapse;font-size:.9rem'>",
            "<tr><th style='text-align:left;padding:.18rem .55rem;font-weight:400;opacity:.7'>en hectares</th>"
            + "".join(f"<th style='{CELLULE};font-weight:{700 if c == 'Normandie' else 600}'>{c}</th>" for c in colonnes)
            + "</tr>"]
    for famille, (couleur, sous) in FAMILLES.items():
        html.append(ligne(famille, cases.loc[[c for c, _ in sous]].sum(), f"font-weight:700;color:{couleur}",
                          f"{TRAIT};font-weight:700", pastille=couleur))
        if details and len(sous) > 1:
            for cle, mot in sous:
                html.append(ligne(mot, cases.loc[cle], "padding-left:1.8rem;opacity:.85", "opacity:.85"))
    html.append(ligne("Total", cases.sum(), "font-weight:700", "border-top:2px solid rgba(128,128,128,.6);font-weight:700"))
    return "".join(html) + "</table>"


# --- Les fenêtres de détail (s'ouvrent par-dessus la page, sans l'allonger) --------------------------
@st.dialog("Ce que disent les textes", width="large")
def fenetre_textes():
    o = OBJECTIF_REGIONAL
    CITE = "margin:.15rem 0 .7rem;padding-left:.8rem;border-left:3px solid rgba(128,128,128,.45)"
    st.html(f"<div style='{PETIT_TITRE}'>{o['texte']}</div>"
            f"<div style='{CITE}'>« {o['objectif']} »<br>« {o['periode']} »<br>Indicateur : « {o['indicateur']} »</div>"
            f"<div style='{PETIT_TITRE}'>{SUIVI_SRB['texte']}</div>"
            f"<div style='{CITE}'>" + "<br>".join(f"« {c} »" for c in SUIVI_SRB["citations"]) + "</div>"
            f"<div style='{DISCRET}'>La mesure officielle est la surface toujours en herbe de la statistique "
            "agricole (Agreste, séries longues).</div>")


@st.dialog("Les prairies du registre PAC : le tableau détaillé", width="large")
def fenetre_tableau():
    st.html(tableau(True))
    st.markdown(
        f"**Comment on fait.** On part de toutes les prairies permanentes déclarées à la PAC en {a0}, et de "
        f"celles déclarées pour la première fois depuis. On regarde ce qu'elles sont dans le registre PAC de "
        f"{an} ; si elles n'y sont plus, on regarde le satellite (images Sentinel-2 de {an}) : restée verte "
        "toute l'année, labourée, bâtie, ou on ne sait pas. On additionne les cartes de Ma commune ; chaque "
        "case est arrondie à l'hectare.\n\n"
        "**« Sortie, restée verte » est un minimum** : sur des prairies connues, la règle satellite n'en "
        "reconnaît qu'environ 3 sur 4 comme vertes toute l'année.")
    if cb:
        N = cases["Normandie"]
        suivies = int(N["toujours"] + N["ajoutee"])
        en_herbe = suivies + int(N["verte"] + N["temporaire"])
        assert en_herbe == int(cases.loc[[c for c, _ in FAMILLES["En herbe"][1]], "Normandie"].sum())
        S, NB = "padding:.2rem .6rem", "padding:.2rem .6rem;text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums"

        def etape(nom, v, total=False, signe=False):
            g = "font-weight:700;border-top:1px solid rgba(128,128,128,.4);" if total else "opacity:.85;"
            return f"<tr><td style='{S};{g}'>{nom}</td><td style='{NB};{g}'>{ha(v, signe=signe)}</td></tr>"

        st.markdown(f"**Pourquoi « En herbe » fait {ha(en_herbe)} et pas {ha(expl + hors)}.** Le tableau ne "
                    "suit que le registre PAC ; la statistique agricole compte aussi l'herbe hors exploitations.")
        st.html("<table style='width:100%;border-collapse:collapse'>"
                + etape(f"Statistique agricole {an}", expl + hors, total=True)
                + etape("herbe hors exploitations agricoles", -hors, signe=True)
                + etape("herbe des exploitations non déclarée en prairie permanente à la PAC", pac - expl, signe=True)
                + etape(f"Prairies permanentes déclarées à la PAC en {an}", pac, total=True)
                + etape(f"écart de méthode : parcelles sans commune, parcelles redessinées depuis {a0}",
                        suivies - pac, signe=True)
                + etape(f"Toujours en prairie + ajoutée depuis {a0}", suivies, total=True)
                + etape("sortie, restée verte (au moins)", int(N["verte"]), signe=True)
                + etape("devenue prairie temporaire", int(N["temporaire"]), signe=True)
                + etape("En herbe (tableau)", en_herbe, total=True) + "</table>")


@st.dialog("D'où vient l'écart avec la statistique agricole", width="large")
def fenetre_ecart():
    ans_ag = sorted(ag)
    surplus = {a: ag[a]["expl"] - ag[a]["registre_pp"] for a in ans_ag}
    hors_s = {a: ag[a]["hors"] for a in ans_ag}
    avant23 = [a for a in ans_ag if a < 2023]
    hausse_dep = {d: x["2022"] - x["2018"] for d, x in hp["agreste"]["hors_par_dep"].items()}
    U = hp["herbe_ign_usages"]
    st.markdown(
        f"{ha(vu)} d'herbe hors du registre PAC pour nous, {ha(expl_hors + hors)} pour la statistique "
        f"agricole : **{ha(ecart_total, signe=True)}**. L'herbe sortie de la PAC depuis 2023 tombe juste "
        f"({nombre(recent)} contre {nombre(expl_hors)} ha) ; tout l'écart est dans le reste.")
    st.markdown(f"**1. Vérifié : {ha(ancien)} de prés sortis de la PAC avant 2023 n'apparaissent pas dans les "
                "séries de la statistique.**")
    g1, g2 = st.columns(2, gap="large")
    g1.html(barres_annees(surplus, {a: ("#8a8f98" if a < 2023 else BLEU) for a in ans_ag},
                          "Herbe des exploitations en plus du registre PAC",
                          "Statistique agricole moins prairies permanentes du registre, en hectares."))
    g2.html(barres_annees(hors_s, {a: AQUA for a in ans_ag}, "Herbe hors exploitations",
                          "Statistique agricole, « collectifs et hors champ », en hectares."))
    st.markdown(
        f"- Jusqu'en 2022, l'herbe des exploitations suit le registre PAC, à "
        f"{nombre(min(surplus[a] for a in avant23))} - {nombre(max(surplus[a] for a in avant23))} ha près : ce "
        "qui sort du registre sort aussi de l'herbe des exploitations.\n"
        f"- L'herbe hors exploitations ne la reprend pas : {nombre(hors_s[avant23[0]])} ha en {avant23[0]}, "
        f"{nombre(hors_s[avant23[-1]])} ha en {avant23[-1]} ; aucun département ne monte d'autant que ses "
        f"prairies sorties (au plus {ha(max(hausse_dep.values()), signe=True)}).\n"
        f"- Ce sont pourtant, en grande majorité, des prés utilisés : sur photos aériennes, à l'aveugle, "
        f"{pr_anc.get('prairie', 0)} sur {n_anc}, comme ceux sortis depuis 2023 ({pr_rec.get('prairie', 0)} sur "
        f"{n_rec}).\n"
        f"- En 2023 au contraire, la statistique n'a pas suivi le registre ("
        f"−{nombre(ag[2022]['registre_pp'] - ag[2023]['registre_pp'])} ha au registre, "
        f"−{nombre(ag[2022]['expl'] - ag[2023]['expl'])} ha pour elle). La Région : « {SUIVI_SRB['lecture_2023']} »")
    st.markdown(f"**2. Non expliqué : {ha(ecart_total - ancien)}.** Par département, notre mesure et la "
                "statistique s'écartent beaucoup plus que cela, dans les deux sens.")
    g3, t3 = st.columns([1, 1], gap="large")
    g3.html(barres_dep(ecart_dep, f"Notre herbe hors PAC (sauf sortie depuis 2023) moins l'herbe hors "
                       f"exploitations de la statistique, {an}",
                       "Orange : nous trouvons plus d'herbe. Vert : la statistique en compte plus."))
    t3.markdown(
        "Deux raisons possibles, que nos données ne départagent pas :\n"
        f"- le chiffre départemental de la statistique est une estimation (Manche : "
        f"{nombre(hp['agreste']['hors_par_dep']['50'][str(an - 1)])} ha en {an - 1}, "
        f"{nombre(hp['agreste']['hors_par_dep']['50'][str(an)])} ha en {an}) ;\n"
        "- nous ne cherchons que l'herbe d'usage agricole ou sans usage de la carte IGN ; elle classe aussi "
        f"{ha(U.get('US5', 0))} d'herbe en usage résidentiel et {ha(U.get('US3', 0))} en usage tertiaire, où "
        "peuvent se trouver des pâtures que la statistique compte.")


@st.dialog("Comment on mesure, et les sources d'erreur", width="large")
def fenetre_methode():
    st.markdown(
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
        f"2018 à {an - 1} ; on garde la dernière année où il y était.\n"
        f"4. **Contrôle sur photos aériennes**, à l'aveugle : {n_anc + n_rec} morceaux d'au moins 1 ha.")
    pho = hp["photos_intervalle"]
    lignes_err = [
        ("Classement herbe / culture / bois",
         f"herbe reconnue {nombre(conf['herbe']['herbe'], 1)} % ; bois pris pour de l'herbe "
         f"{nombre(conf['bois']['herbe'], 1)} % ; cultures {nombre(conf['culture']['herbe'], 1)} %",
         f"corrigé : {ha(cb['corrige']['herbe'])} au lieu de {ha(cb['ha_nature']['herbe'])} ; le classement ne "
         "gonfle pas notre mesure"),
        ("Origine de chaque hectare", "refaite par 30 000 points tirés au hasard (scripts/verifier_origines.py)",
         "mêmes chiffres, à l'erreur de tirage près"),
        ("Contrôle photo", f"{pr_anc.get('prairie', 0)} prés sur {n_anc} sortis avant 2023",
         f"entre {pho[0]} et {pho[1]} % (intervalle à 95 %) ; morceaux de 1 ha et plus, "
         f"{nombre(100 - hp['origines']['part_moins_1ha_avant_2023'], 0)} % de leur surface"),
        ("Périmètre de la carte IGN", "herbe d'usage agricole ou sans usage seulement",
         "l'herbe résidentielle ou tertiaire n'est pas cherchée"),
        ("Date de la carte IGN (2022-2023)", "herbe apparue depuis non cherchée ; chantier récent vu en herbe",
         "dans les deux sens, non chiffré"),
        ("Morceaux de moins de 0,1 ha, bandes de moins de 20 m", "écartés", "sous-estime, non chiffré"),
        ("Herbe hors exploitations (statistique)", "estimation, méthode non publiée",
         "répartition par département différente du terrain"),
    ]
    th = "text-align:left;padding:.25rem .5rem;font-weight:600;border-bottom:1px solid rgba(128,128,128,.4)"
    td = "padding:.25rem .5rem;vertical-align:top;border-bottom:1px solid rgba(128,128,128,.15)"
    st.html("<table style='width:100%;border-collapse:collapse;font-size:.88rem'>"
            f"<tr><th style='{th}'>Source d'erreur</th><th style='{th}'>Ce qu'on a mesuré</th><th style='{th}'>Effet</th></tr>"
            + "".join(f"<tr><td style='{td};font-weight:600'>{a}</td><td style='{td}'>{b}</td><td style='{td}'>{c}</td></tr>"
                      for a, b, c in lignes_err) + "</table>"
            f"<div style='{DISCRET};margin-top:.4rem'>Détail : verification/sentinel2/compte_rendu_2025.md.</div>")


# --- La page : le constat officiel à gauche, ce que Prairimètre ajoute à droite ---------------------
def etiquette(texte):
    return f"<div style='{PETIT_TITRE}'>{texte}</div>"


def grand(texte, couleur):
    return f"<div style='font-size:1.6rem;font-weight:700;color:{couleur};line-height:1.15'>{texte}</div>"


def legende(texte):
    return f"<div style='font-size:.86rem;line-height:1.35;margin:.25rem 0 .45rem'>{texte}</div>"


def pile(segments, etiquettes=True):
    """Une barre empilée simple, un chiffre sous chaque part assez large."""
    total = sum(v for v, _, _ in segments)
    cases_p = "".join(f"<div title='{nom} : {ha(v)}' style='width:calc({100 * v / total:.2f}% - 2px);background:{c};"
                      "flex:none'></div>" for v, c, nom in segments)
    noms = "".join(f"<div style='width:calc({100 * v / total:.2f}% - 2px);flex:none;font-size:.74rem;line-height:1.2;"
                   f"overflow:hidden;white-space:nowrap'>{nombre(v) if etiquettes and v / total > .12 else ''}</div>"
                   for v, c, nom in segments)
    return (f"<div style='display:flex;gap:2px;height:20px;border-radius:4px;overflow:hidden'>{cases_p}</div>"
            f"<div style='display:flex;gap:2px;margin-top:.1rem'>{noms}</div>")


def carres(avis):
    """Le contrôle photo, un carré par morceau regardé : vert = pré fauché ou pâturé, gris = autre."""
    ordre = sorted(avis.items(), key=lambda x: x[0] != "prairie")
    c = "".join(f"<span title='{a}' style='display:inline-block;width:13px;height:13px;margin:0 3px 3px 0;"
                f"border-radius:3px;background:{VERT if a == 'prairie' else GRIS_PAC}'></span>"
                for a, n in ordre for _ in range(n))
    return f"<div style='line-height:0;margin:.35rem 0 .1rem'>{c}</div>"


st.title("Objectif 2030 : zéro perte nette de prairies permanentes")
st.html("<style>[class*='st-key-bloc_']{height:100%}"
        "[class*='st-key-bloc_'] [data-testid='stVerticalBlock']{gap:.35rem}</style>"
        "<div style='font-size:1rem;opacity:.8;margin:.1rem 0 .7rem'>Le chiffre officiel, et ce que "
        "Prairimètre y ajoute : savoir <b>où</b>, le vérifier, et voir ce que la statistique ne voit plus.</div>")
gauche, droite = st.columns([1.15, 2], gap="medium")

with gauche, st.container(border=True, key="bloc_constat"):
    tenu = ecart >= 0
    ans = [a for a in sth.index if a > a_ref]
    st.html(etiquette("Le constat officiel")
            + grand(f"{'Tenu' if tenu else 'Pas tenu'} : {ha(ecart, signe=True)}", VERT if tenu else ROUGE)
            + legende(f"de surface toujours en herbe depuis {a_ref}")
            + barres_annees({a: int(sth.loc[a] - sth.loc[a_ref]) for a in ans},
                            {a: (VERT if sth.loc[a] >= sth.loc[a_ref] else ROUGE) for a in ans},
                            f"Surface toujours en herbe, écart à {a_ref} (en hectares)", "", H=105, signe=True)
            + legende(f"Statistique agricole (Agreste), la mesure qui fait foi : {ha(sth.loc[a_ref])} en "
                      f"{a_ref}, {ha(sth.loc[fin])} en {fin} (provisoire). L'objectif : ne pas descendre sous "
                      f"le niveau de {a_ref}."))
    if st.button("Ce que disent les textes", icon=":material/format_quote:", width="stretch"):
        fenetre_textes()

with droite:
    st.html(etiquette("Ce que Prairimètre ajoute"))
    t1, t2, t3 = st.columns(3, gap="small")
    N = cases["Normandie"]
    en_herbe_n = int(N[[c for c, _ in FAMILLES["En herbe"][1]]].sum())
    pas_herbe_n = int(N[[c for c, _ in FAMILLES["Pas en herbe"][1]]].sum())
    ne_sait_n = int(N[[c for c, _ in FAMILLES["On ne sait pas"][1]]].sum())
    with t1, st.container(border=True, key="bloc_ou"):
        st.html(grand("Où ?", VERT)
                + legende(f"<b>{ha(int(N.sum()))}</b> de prairies suivies une par une depuis {a0}, dans chaque "
                          f"commune. Ce qu'elles sont en {an} :")
                + pile([(en_herbe_n, VERT, "en herbe"), (pas_herbe_n, ROUGE, "plus en herbe"),
                        (ne_sait_n, ORANGE, "à vérifier")])
                + legende(f"<span style='color:{VERT}'>■</span> en herbe <b>{nombre(en_herbe_n)}</b><br>"
                          f"<span style='color:{ROUGE}'>■</span> plus en herbe <b>{nombre(pas_herbe_n)}</b><br>"
                          f"<span style='color:{ORANGE}'>■</span> à vérifier sur le terrain <b>{nombre(ne_sait_n)}</b>"))
        if st.button("Le tableau", icon=":material/table:", width="stretch"):
            fenetre_tableau()
    if cb:
        eux_total, nous_total = expl + hors, pac + vu
        with t2, st.container(border=True, key="bloc_fiable"):
            st.html(grand(f"Fiable à {nombre(100 * (nous_total / eux_total - 1), 0)} % près", BLEU)
                    + legende(f"Toute l'herbe de {an}, recomptée nous-mêmes au satellite :")
                    + "<div style='display:grid;grid-template-columns:5.6rem 1fr;gap:.35rem .5rem;align-items:center;"
                      "font-size:.82rem'>"
                    + f"<div>Statistique</div><div>{pile([(pac, GRIS_PAC, 'déclarée à la PAC'), (eux_total - pac, AQUA, 'hors PAC')], False)}</div>"
                    + f"<div><b>Prairimètre</b></div><div>{pile([(pac, GRIS_PAC, 'déclarée à la PAC'), (vu, AQUA, 'hors PAC, vue au satellite')], False)}</div>"
                    + "</div>"
                    + legende(f"<b>{ha(nous_total)}</b> pour nous, <b>{ha(eux_total)}</b> pour la statistique, dont "
                              f"{ha(pac)} déclarés à la PAC des deux côtés.<br>"
                              f"<span style='color:{GRIS_PAC}'>■</span> déclarée à la PAC · "
                              f"<span style='color:{AQUA}'>■</span> hors PAC"))
            if st.button("Comment on a recompté", icon=":material/satellite_alt:", width="stretch"):
                fenetre_methode()
        with t3, st.container(border=True, key="bloc_plus"):
            st.html(grand(f"+{ha(ancien)}", ORANGE_VIF)
                    + legende("de prés <b>que la statistique ne voit plus</b> : sortis de la PAC avant 2023, "
                              "toujours fauchés ou pâturés.")
                    + carres(pr_anc)
                    + legende(f"Photos aériennes, à l'aveugle : <b>{pr_anc.get('prairie', 0)} prés sur "
                              f"{n_anc}</b> morceaux tirés au hasard."))
            if st.button("D'où vient l'écart", icon=":material/insights:", width="stretch"):
                fenetre_ecart()
