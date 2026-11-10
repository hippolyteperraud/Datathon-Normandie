"""1. L'objectif 2030 : le point de situation de la dernière année, en hectares, pour chaque département
et pour la région. En tête, le verdict officiel : en hectares depuis 2021 (ce que dit l'objectif), la
part de la surface agricole à côté (l'indicateur que suit la Région). Puis toutes les cartes de Ma
commune additionnées, avec la même règle et les mêmes mots : en herbe, pas en herbe, on ne sait pas.
Que des nombres et des sommes : chaque total se refait à la main.
Les versions précédentes (graphes, pourcentages, vérification) sont dans app/sauvegardes/."""
import pandas as pd
import streamlit as st

from commun import DEPARTEMENTS, bornes, exiger_sorties, ha, nombre, table
from prairimetre import sentinel as sen
from prairimetre.donnees import DATA, SOURCES, prairies
from references import OBJECTIF_REGIONAL, SUIVI_SRB

exiger_sorties()
a0, an = bornes()
VERT, ROUGE, ORANGE = "#2e7d4f", "#c2452d", "#f0a202"

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


bloc = sen.bloc()[0]
h = _carte(bloc.stat().st_mtime if bloc.exists() else 0, an)
# Chaque case est arrondie à l'hectare, puis TOUTES les sommes sont faites sur les cases arrondies :
# les totaux du tableau se refont à la main, sans écart d'arrondi
cases = h.pivot_table(index="cle", columns="dep", values="ha", aggfunc="sum").fillna(0).round().astype(int)
deps = [d for d in DEPARTEMENTS if d in cases.columns]
cases = cases[deps].reindex([c for _, (_, l) in FAMILLES.items() for c, _ in l], fill_value=0)
cases["Normandie"] = cases.sum(axis=1)
colonnes = [DEPARTEMENTS[d] for d in deps] + ["Normandie"]
cases.columns = colonnes


# --- 1. Le verdict : en hectares depuis 2021 (ce que dit l'objectif), la part de la surface agricole à
# côté (l'indicateur que suit la Région). Mesure officielle : statistique agricole (Agreste).
obj = table("objectif").set_index("annee")
sth = obj.sth_ha.dropna()
part = obj.part_sth.dropna() if "part_sth" in obj else pd.Series(dtype=float)
a_ref, fin = int(obj.annee_reference.iloc[0]), int(sth.index.max())


def part_txt(a):
    """La part de la surface agricole : celle du bilan de la Région quand il la publie, sinon recalculée."""
    p = SUIVI_SRB["parts_pct"].get(a)
    if p is None and a in part.index:
        p = 100 * part.loc[a]
    return f"{nombre(p, 1)} %" if p is not None else None


st.title("Objectif 2030 : zéro perte nette de prairies permanentes")
if a_ref in sth.index:
    ecart = sth.loc[fin] - sth.loc[a_ref]
    tenu = ecart >= 0
    couleur = VERT if tenu else ROUGE
    st.html(f"<div style='font-size:1.9rem;font-weight:700;color:{couleur};margin:-.4rem 0 .6rem'>"
            f"{'Tenu' if tenu else 'Pas tenu'} : {ha(ecart, signe=True)} depuis {a_ref}"
            f"<span style='font-size:.95rem;font-weight:400;opacity:.75'>&nbsp;&nbsp;mesure officielle : statistique agricole, "
            f"{fin} provisoire</span></div>")

    # À gauche, ce que disent les textes, mot pour mot ; à droite, les chiffres de la statistique agricole
    textes, chiffres = st.columns([1.35, 1], gap="large")
    o = OBJECTIF_REGIONAL
    CITE = "margin:.15rem 0 .5rem;padding-left:.8rem;border-left:3px solid rgba(128,128,128,.45)"
    SOURCE = "font-size:.8rem;opacity:.65;text-transform:uppercase;letter-spacing:.03em"
    textes.html(
        f"<div style='{SOURCE}'>{o['texte']}</div>"
        f"<div style='{CITE}'>« {o['objectif']} »<br>« {o['periode']} »<br>"
        f"Indicateur : « {o['indicateur']} »</div>"
        f"<div style='{SOURCE}'>Suivi de la Région (premier bilan 2022-2024)</div>"
        f"<div style='{CITE}'>" + "<br>".join(f"« {c} »" for c in SUIVI_SRB["citations"]) + "</div>")

    def ligne_chiffres(nom, surface, part_a, gras=False):
        g = "font-weight:700;" if gras else ""
        return (f"<tr><td style='padding:.3rem .6rem;{g}'>{nom}</td>"
                f"<td style='padding:.3rem .6rem;text-align:right;white-space:nowrap;{g}'>{surface}</td>"
                f"<td style='padding:.3rem .6rem;text-align:right;white-space:nowrap'>{part_a}</td></tr>")

    lignes = [ligne_chiffres(f"{a_ref} (référence)", ha(sth.loc[a_ref]), part_txt(a_ref) or "–")]
    for a in sorted({fin - 1, fin}):
        if a in sth.index and a > a_ref:
            lignes.append(ligne_chiffres(f"{a}{' (provisoire)' if a == fin else ''}", ha(sth.loc[a]),
                                         (part_txt(a) or "–") + ("" if a in SUIVI_SRB["parts_pct"] else " *")))
    lignes.append(ligne_chiffres("2030 (objectif)", f"au moins {ha(sth.loc[a_ref])}", "", gras=True))
    chiffres.html(
        "<table style='width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums'>"
        "<tr style='border-bottom:1px solid rgba(128,128,128,.4)'><th style='text-align:left;padding:.3rem .6rem;"
        "font-weight:400;opacity:.7'>année</th><th style='text-align:right;padding:.3rem .6rem;font-weight:400;"
        "opacity:.7'>surface toujours en herbe</th><th style='text-align:right;padding:.3rem .6rem;"
        "font-weight:400;opacity:.7'>part de la SAU</th></tr>" + "".join(lignes) + "</table>"
        "<div style='font-size:.8rem;opacity:.65;margin-top:.3rem'>Statistique agricole (Agreste, séries "
        "longues 2010-2025). * part calculée par nous ; les autres sont celles du bilan de la Région.</div>")

# --- 2. Ce que montrent les parcelles en {an} : toutes les cartes de Ma commune additionnées ----------
titre, bouton = st.columns([4, 1], vertical_alignment="bottom")
titre.subheader(f"Ce que nous faisons : regarder chaque prairie en {an}")
with bouton.popover("Comment on fait", icon=":material/help:", width="stretch"):
    st.markdown(
        f"**1. On part des prairies.** Toutes les prairies permanentes déclarées à la PAC en {a0}, et "
        f"celles déclarées pour la première fois depuis.\n\n"
        f"**2. On regarde ce qu'elles sont en {an} dans le registre PAC** (ce que l'agriculteur déclare) : "
        "toujours prairie permanente, prairie temporaire, culture, bois ou lande…\n\n"
        f"**3. Si une prairie n'est plus déclarée, on regarde le satellite** (images Sentinel-2 de {an}) : "
        "restée verte toute l'année, passée par le sol nu (labourée), sans végétation (bâtie), ou on ne "
        "sait pas (le satellite ne tranche pas, ou la parcelle est trop petite).\n\n"
        "**4. On additionne les hectares**, commune par commune : c'est la somme des cartes de Ma commune. "
        "Une parcelle compte en entier dans la couleur de sa plus grande part, comme sur la carte. Chaque "
        "case est arrondie à l'hectare et les totaux sont faits sur les cases arrondies.\n\n"
        f"**Ce n'est pas la mesure officielle.** Celle d'en haut vient de la statistique agricole "
        f"(Agreste) et se compare à {a_ref}. Ce tableau suit les parcelles du registre PAC depuis {a0} : "
        "il dit où sont les prairies et ce qu'elles sont devenues.")
st.html(f"<div style='margin:-.5rem 0 .4rem;opacity:.8'>Chaque prairie permanente de {a0}, et chaque "
        f"prairie ajoutée depuis, vue dans le registre PAC de {an} ou, si elle n'y est plus, par le "
        "satellite. En hectares.</div>")

st.session_state.setdefault("objectif_details", False)
details = st.session_state["objectif_details"]
PAD = ".2rem" if details else ".32rem"      # le détail ouvert tient aussi sur un écran
CELLULE = f"padding:{PAD} .8rem;text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap"
TRAIT = "border-top:1px solid rgba(128,128,128,.35)"


def ligne(nom, valeurs, style_nom="", style="", pastille=None):
    p = (f"<span style='display:inline-block;width:.75rem;height:.75rem;border-radius:3px;background:{pastille};"
         "margin-right:.5rem;vertical-align:-1px'></span>") if pastille else ""
    tds = "".join(f"<td style='{CELLULE};{style}"
                  f"{';font-weight:700' if c == 'Normandie' else ''}'>{nombre(v)}</td>"
                  for c, v in valeurs.items())
    return f"<tr><td style='padding:{PAD} .8rem;{style_nom};{style}'>{p}{nom}</td>{tds}</tr>"


html = ["<table style='width:100%;border-collapse:collapse;font-size:1rem'>",
        f"<tr><th style='text-align:left;padding:{PAD} .8rem;font-weight:400;opacity:.7'>en hectares</th>"
        + "".join(f"<th style='{CELLULE};{'font-weight:700' if c == 'Normandie' else 'font-weight:600'}'>{c}</th>"
                  for c in colonnes) + "</tr>"]
# Toujours visibles : les trois familles et le total. Le détail de chaque famille n'apparaît qu'avec le
# bouton « Détails du tableau »
for famille, (couleur, sous) in FAMILLES.items():
    total = cases.loc[[c for c, _ in sous]].sum()
    html.append(ligne(famille, total, f"font-weight:700;color:{couleur}", f"{TRAIT};font-weight:700",
                      pastille=couleur))
    if details and len(sous) > 1:
        for cle, mot in sous:
            html.append(ligne(mot, cases.loc[cle], "padding-left:2.1rem;opacity:.85", "opacity:.85"))
html.append(ligne("Total", cases.sum(), "font-weight:700", "border-top:2px solid rgba(128,128,128,.6);"
                  "font-weight:700"))
html.append("</table>")
st.html("".join(html))


def basculer():
    st.session_state["objectif_details"] = not st.session_state["objectif_details"]


st.button("Masquer les détails" if details else "Détails du tableau", on_click=basculer,
          icon=":material/expand_less:" if details else ":material/expand_more:")


# --- 3. Pourquoi « en herbe » n'est pas le nombre d'en haut : on passe de l'un à l'autre au chiffre près.
# Haut : statistique agricole = herbe des exploitations + herbe hors exploitations. Bas : registre PAC.
@st.cache_data(show_spinner=False)
def _passage(annee):
    t = pd.read_csv(DATA / SOURCES["saa_series"]["fichier"]).set_index("annee")
    return (int(t.loc[annee, "sth_exploitations"]), int(t.loc[annee, "sth_hors_exploitations"]),
            int(round(prairies(annee).surf_parc.sum())))


if fin == an and an in sth.index:
    expl, hors, pac = _passage(an)
    N = cases["Normandie"]
    suivies = int(N["toujours"] + N["ajoutee"])
    en_herbe = suivies + int(N["verte"] + N["temporaire"])
    # Chaque étape se refait à la main ; la dernière ligne doit retomber sur « En herbe » du tableau
    assert expl + hors == int(sth.loc[an]) and en_herbe == int(cases.loc[[c for c, _ in FAMILLES["En herbe"][1]],
                                                                         "Normandie"].sum())
    st.subheader(f"Pourquoi {nombre(en_herbe)} ha et pas {nombre(expl + hors)} ha ?")
    gauche, droite = st.columns([1, 1.15], gap="large")
    gauche.markdown(
        "**Les deux tableaux ne comptent pas la même chose.**\n\n"
        "- **En haut, la statistique agricole** compte toute la surface toujours en herbe de Normandie, "
        "même celle qui n'appartient pas à une exploitation agricole. C'est elle qui mesure l'objectif.\n"
        "- **En bas, nous partons du registre PAC** : seulement les parcelles déclarées par les "
        "agriculteurs. En échange, on sait où est chaque prairie et ce qu'elle est devenue, et le "
        "satellite suit celles qui sortent du registre.\n\n"
        f"Dans le tableau du bas, ce qui se compare à l'objectif, ce sont les prairies permanentes du "
        f"registre : **{nombre(suivies)} ha** (toujours en prairie + ajoutée depuis {a0}). Les prairies "
        "sorties restées vertes et les prairies temporaires disent où il y a encore de l'herbe, pas si "
        "l'objectif est tenu.")
    S = "padding:.22rem .6rem"
    NB = f"{S};text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums"

    def etape(nom, v, total=False, signe=False):
        g = "font-weight:700;border-top:1px solid rgba(128,128,128,.4);" if total else "opacity:.85;"
        return (f"<tr><td style='{S};{g}'>{nom}</td>"
                f"<td style='{NB};{g}'>{ha(v, signe=True) if signe else ha(v)}</td></tr>")

    droite.html(
        "<table style='width:100%;border-collapse:collapse'>"
        + etape(f"Statistique agricole {an} (en haut)", expl + hors, total=True)
        + etape("herbe hors exploitations agricoles", -hors, signe=True)
        + etape("herbe des exploitations non déclarée en prairie permanente à la PAC", pac - expl, signe=True)
        + etape(f"Prairies permanentes déclarées à la PAC en {an}", pac, total=True)
        + etape("écart de méthode : parcelles sans commune, parcelles redessinées depuis "
                f"{a0}", suivies - pac, signe=True)
        + etape(f"Toujours en prairie + ajoutée depuis {a0}", suivies, total=True)
        + etape("sortie, restée verte (au moins, voir plus bas)", int(N["verte"]), signe=True)
        + etape("devenue prairie temporaire", int(N["temporaire"]), signe=True)
        + etape("En herbe (tableau ci-dessus)", en_herbe, total=True)
        + "</table><div style='font-size:.8rem;opacity:.65;margin-top:.3rem'>Statistique agricole (Agreste, "
          f"séries longues) et registre PAC {an}, en hectares. Chaque ligne se refait à la main.</div>")


# --- 4. L'herbe hors du registre PAC : l'avons-nous retrouvée ? Toute l'herbe de la carte IGN non déclarée
# à la PAC, vue au satellite (prairimetre/sentinel_nuit.py). Chiffres lus dans herbe_hors_pac.json.
@st.cache_data(show_spinner=False)
def _hors_pac(annee):
    import json
    f = sen.DOSSIER / str(annee) / "herbe_hors_pac.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


hp = _hors_pac(an) if fin == an and an in sth.index else None
if hp:
    cherche = expl + hors - pac                     # l'herbe de la statistique agricole hors registre PAC
    E, pct_h, pct_c = hp["ha_etat"], hp["etalons_pct"]["herbe"], hp["etalons_pct"]["culture"]
    vu = sum(E.values())
    est, (bas, haut) = hp["estimation"]["total"], hp["intervalle"]["total"]
    sur = E["couvert permanent"]
    pc = lambda v: nombre(v, 1).replace(",0", "") + " %"
    titre4, bouton4 = st.columns([4, 1], vertical_alignment="bottom")
    titre4.subheader(f"Les {nombre(cherche)} ha d'herbe hors registre PAC : les avons-nous retrouvés ?")
    with bouton4.popover("Comment on fait", icon=":material/help:", width="stretch"):
        st.markdown(
            f"**1. Toute l'herbe de la carte IGN** (OCS GE : couvert herbacé, usage agricole ou sans usage), "
            f"moins tout ce qui est déclaré à la PAC en {an} : {nombre(hp['morceaux'])} morceaux d'au moins "
            "0,1 ha, sans les bandes de moins de 20 m.\n\n"
            f"**2. Chaque morceau vu au satellite** sur {hp['images']} images Sentinel-2 de {an}, avec la "
            "même règle que pour les prairies sorties du registre.\n\n"
            f"**3. La règle contrôlée.** Refaite sur les {nombre(hp['temoins'])} prairies déjà mesurées : "
            f"même état pour {nombre(hp['temoins_tranchent_accord'])} sur {nombre(hp['temoins_tranchent'])} "
            "quand elle tranche.\n\n"
            f"**4. La règle étalonnée** sur des parcelles dont on connaît la réponse : "
            f"{nombre(hp['etalons']['herbe'])} parcelles d'herbe sûre (prairie permanente en {an - 1} et "
            f"{an}) et {nombre(hp['etalons']['culture'])} cultures sûres de {an}, de la même taille que les "
            "morceaux.\n\n"
            "**5. L'estimation**, classe de taille par classe de taille : le couvert permanent vu, moins ce "
            "qu'y mettent les cultures, divisé par la part de l'herbe sûre que la règle reconnaît. "
            f"Intervalle à 95 % : {hp['tirages']} tirages au hasard des parcelles.\n\n"
            f"Jamais déclarée à la PAC de 2018 à {an - 1} : {ha(hp['estimation']['jamais'])} "
            f"(statistique agricole hors exploitations : {ha(hors)}). Déjà déclarée : "
            f"{ha(hp['estimation']['deja'])} (herbe des exploitations non déclarée en prairie permanente : "
            f"{ha(expl - pac)}). Ce rapprochement est le nôtre : la statistique "
            "agricole ne les définit pas ainsi.")
    st.html(f"<div style='margin:-.5rem 0 .4rem;opacity:.8'>La statistique agricole compte "
            f"{nombre(cherche)} ha d'herbe en dehors des prairies permanentes déclarées à la PAC. Nous avons "
            "cherché cette herbe nous-mêmes, sur la carte IGN et au satellite.</div>")
    g4, d4 = st.columns([1, 1.15], gap="large")
    g4.markdown(
        f"**La règle satellite est fiable, mais prudente.** Sur des parcelles connues, elle classe en "
        f"couvert permanent **{pc(pct_h['couvert permanent'])} de l'herbe sûre** et "
        f"{pc(pct_c['couvert permanent'])} des cultures. Elle ne prend donc presque jamais une culture pour "
        "de l'herbe ; mais elle ne reconnaît qu'environ **3 prairies sur 4**, les autres restent « on ne sait "
        "pas ».\n\n"
        f"**L'herbe hors registre existe bien** : au moins **{nombre(sur)} ha**. En corrigeant ce que la "
        f"règle ne reconnaît pas, environ **{nombre(est)} ha**, soit {nombre(est - cherche)} ha de plus "
        "que la statistique agricole. Nous ne savons pas d'où vient cet écart : carte IGN de 2022-2023, "
        "friches ou broussailles vertes toute l'année, estimation de la statistique agricole.\n\n"
        "**La mesure de l'objectif reste la statistique agricole.** Le satellite confirme que cette herbe "
        "existe et dit où elle est ; il ne donne pas son chiffre à l'hectare près.\n\n"
        f"**Même prudence au-dessus** : « sortie, restée verte » ({nombre(int(N['verte']))} ha) compte "
        "environ 3 des 4 prairies vraiment restées en herbe. C'est un minimum.")
    d4.html(
        "<table style='width:100%;border-collapse:collapse'>"
        + etape(f"Herbe de la carte IGN non déclarée à la PAC en {an}", vu, total=True)
        + etape("verte toute l'année (couvert permanent)", sur)
        + etape("on ne sait pas", E["indéterminé"])
        + etape(f"labourée en {an}", E["labourée"])
        + etape("bâtie ou minérale", E["bâti ou minéral"])
        + "<tr><td colspan='2' style='height:.6rem'></td></tr>"
        + etape("Statistique agricole : herbe hors prairies permanentes PAC", cherche, total=True)
        + etape("Satellite : au moins (vert toute l'année)", sur)
        + etape("Satellite : estimation corrigée", est)
        + f"<tr><td style='{S};opacity:.65;font-size:.85rem'>intervalle à 95 %</td><td style='{NB};opacity:.65;"
          f"font-size:.85rem'>{nombre(bas)} à {nombre(haut)} ha</td></tr>"
        + "</table><div style='font-size:.8rem;opacity:.65;margin-top:.3rem'>Carte OCS GE (IGN), images "
          f"Sentinel-2 {an} (Copernicus), registre PAC {an}, statistique agricole (Agreste), en hectares.</div>")
