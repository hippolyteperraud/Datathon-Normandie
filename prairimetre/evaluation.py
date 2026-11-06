"""Évaluation : ce que l'outil sait, mesuré, et ce qu'il ne sait pas.

Toutes les mesures comparent le début et la fin d'une période (croisement direct), en Normandie.

Sorties (dossier sorties/) :
- evaluation_zonages.csv : retournement dans chaque zonage et chaque famille, comparé au reste de
  la même commune ;
- evaluation_classes.csv : répartition des prairies et du retournement entre règles, sites
  protégés, inventaires et « rien » (classes exclusives) ;
- evaluation_concentration.csv, evaluation_prediction.csv, evaluation_sensibilite.csv ;
- evaluation_certitude.csv : état du sol (OCS GE) des prairies sorties de la déclaration ;
- evaluation_saa.csv : RPG comparé à la statistique agricole annuelle (source indépendante) ;
- evaluation_habitats.csv : habitats prairiaux d'intérêt européen (biodiversité) ;
- evaluation_moteurs.csv : retournement selon la progression du maïs dans la commune.
"""
import json

import numpy as np
import pandas as pd

from .config import DATA, MIN_HA, RECENT, SORTIES, annees
from .donnees import FAMILLES, HABITATS_PRAIRIAUX, ZONAGES, habitats_prairiaux, ocsge, prairies, saa
from .indicateurs import normandie, periodes, serie, zonages_annee
from .suivi import croiser, devenir


def _debut():
    """Prairies du début : zonages + retournement direct jusqu'à la fin, en Normandie."""
    a0, an, _ = periodes()
    z, d = zonages_annee(a0), devenir(a0, an)
    z = z.assign(retourne=d.culture.values, sortie=d["non déclaré"].values)
    return normandie(z), an - a0


def _rapport_meme_commune(e, dedans):
    """Retournement observé dans le zonage / attendu au taux du reste de la même commune."""
    t = e.assign(d=dedans).groupby(["insee", "d"])[["ha", "retourne"]].sum().unstack("d").dropna()
    if not len(t):
        return np.nan, 0
    attendu = (t[("retourne", False)] / t[("ha", False)] * t[("ha", True)]).sum()
    return t[("retourne", True)].sum() / attendu, len(t)


def zonages():
    e, n = _debut()
    lignes = []
    for nom in ZONAGES + [f for f in FAMILLES] + ["enjeu"]:
        z = e[f"z_{nom}"]
        rapport, mixtes = _rapport_meme_commune(e, z)
        lignes.append({
            "zonage": nom, "famille": next((f for f, ns in FAMILLES.items() if nom in ns), nom),
            "part_des_prairies": e.ha[z].sum() / e.ha.sum(),
            "retourne_ha": e.retourne[z].sum(),
            "part_du_retournement": e.retourne[z].sum() / e.retourne.sum(),
            "taux_annuel_dedans": e.retourne[z].sum() / e.ha[z].sum() / n,
            "taux_annuel_dehors": e.retourne[~z].sum() / e.ha[~z].sum() / n,
            "communes_mixtes": mixtes, "rapport_meme_commune": rapport})
    return pd.DataFrame(lignes).set_index("zonage")


def robustesse():
    """Les rapports « dans le zonage / reste de la même commune » tiennent-ils d'une période à
    l'autre ? Règles et aires de captage (le 25/10/2026 : règles 0,18 à 0,24, robustes ; captages
    0,91 à 1,13, qu'on ne peut résumer que par « autant qu'à côté »)."""
    A = annees()
    a0, an, r0 = periodes()
    coupure = A[0] + (len(A) - 1) // 2 + 1
    zonages_testes = {"regle": "z_regle", "aires_alimentation_captages":
                      "z_aires_alimentation_captages"}
    lignes = []
    for a, b in [(a0, an), (a0, coupure), (r0, an)]:
        z, d = zonages_annee(a), devenir(a, b)
        e = normandie(z.assign(retourne=d.culture.values))
        for nom, col in zonages_testes.items():
            r, n = _rapport_meme_commune(e, e[col])
            lignes.append({"zonage": nom, "periode": f"{a}-{b}", "methode": "comparaison directe",
                           "rapport_meme_commune": r, "communes_mixtes": n})
    for nom, col in zonages_testes.items():  # année par année, cumulé
        num = att = 0
        for a in A[:-1]:
            z, d = zonages_annee(a), devenir(a, a + 1)
            e = normandie(z.assign(retourne=d.culture.values, d=z[col].values))
            t = e.groupby(["insee", "d"])[["ha", "retourne"]].sum().unstack("d").dropna()
            num += t[("retourne", True)].sum()
            att += (t[("retourne", False)] / t[("ha", False)] * t[("ha", True)]).sum()
        lignes.append({"zonage": nom, "periode": f"{A[0]}-{A[-1]}",
                       "methode": "année par année, cumulé", "rapport_meme_commune": num / att})
    return pd.DataFrame(lignes)


def classes():
    """Chaque prairie dans une seule classe : la plus forte qui la couvre."""
    e, n = _debut()
    classe = np.select([e.z_regle, e.z_site, e.z_inventaire],
                       ["règle", "site protégé", "inventaire seul"], "aucun zonage")
    g = e.assign(classe=classe).groupby("classe")[["ha", "retourne", "sortie"]].sum()
    g["part_des_prairies"] = g.ha / g.ha.sum()
    g["part_du_retournement"] = g.retourne / g.retourne.sum()
    g["taux_annuel"] = g.retourne / g.ha / n
    return g.reindex(["règle", "site protégé", "inventaire seul", "aucun zonage"])


def concentration():
    c = pd.read_csv(SORTIES / "communes.csv", dtype={"insee": str})
    c = c[c.statut == "calculé"]
    lignes = []
    for col in ["retourne", "retourne_recent", "devenues_non_declare"]:
        s = c[col].sort_values(ascending=False)
        cum = s.cumsum() / s.sum()
        lignes.append({"mesure": col, "communes": len(s),
                       "part_top_10pct": cum.iloc[len(s) // 10 - 1],
                       "communes_pour_50pct": int((cum < .5).sum() + 1)})
    return pd.DataFrame(lignes).set_index("mesure")


def _capture(score, cible, part):
    haut = score.sort_values(ascending=False).index[:int(len(score) * part)]
    return cible.loc[haut].sum() / cible.sum()


def prediction():
    """Score calculé sur la première moitié de la période, testé sur la seconde."""
    A = annees()
    coupure = A[0] + (len(A) - 1) // 2 + 1
    avant = normandie(devenir(A[0], coupure)).groupby("insee")
    apres = normandie(devenir(coupure, A[-1])).groupby("insee").culture.sum()
    pp0 = avant.ha.sum()
    idx = pp0[pp0 >= MIN_HA].index
    cible = apres.reindex(idx).fillna(0)
    scores = {
        f"ha retournés {A[0]}-{coupure}": avant.culture.sum().reindex(idx).fillna(0),
        f"témoin : surface en prairie {A[0]}": pp0.reindex(idx),
        "témoin : hasard": pd.Series(np.random.default_rng(0).random(len(idx)), idx),
    }
    return pd.DataFrame({nom: {
        "periode_testee": f"{coupure}-{A[-1]}",
        "spearman": s.rank().corr(cible.rank()),
        "capture_top_10pct": _capture(s, cible, .1),
        "capture_top_20pct": _capture(s, cible, .2)} for nom, s in scores.items()}).T


def sensibilite():
    """Les résultats changent-ils avec les seuils ? (communes calculées, liste des 50 premières)"""
    a0, an, _ = periodes()
    d0 = normandie(devenir(a0, an)).groupby("insee").ha.sum()
    lignes = [{"parametre": "seuil de prairies (ha)", "valeur": s,
               "communes_calculees": int((d0 >= s).sum())} for s in (10, 20, 50)]

    def top50(k):
        d = normandie(devenir(an - k, an)).groupby("insee")
        r = d.culture.sum()[d.ha.sum() >= MIN_HA]
        return set(r.nlargest(50).index)

    ref = top50(RECENT)
    for k in (2, 3, 4):
        lignes.append({"parametre": "période récente (années)", "valeur": k,
                       "communes_communes_avec_reference": len(top50(k) & ref)})
    return pd.DataFrame(lignes)


def etat_ocsge(cs, us):
    """État du sol OCS GE. « herbe, usage agricole » = prairie OU culture (CS2.2.1)."""
    etat = pd.Series("autre", index=cs.index, dtype="object")
    etat[cs.str.startswith("CS1.1")] = "artificialisé"
    etat[cs.str.startswith("CS2.1")] = "ligneux"
    herbe = cs == "CS2.2.1"
    etat[herbe & (us == "US1.1")] = "herbe, usage agricole"
    etat[herbe & (us != "US1.1")] = "herbe, autre usage"
    return etat


def certitude(seuil=0.5):
    """Prairies sorties de la déclaration (et témoin : restées prairies) vues par l'OCS GE
    l'année même."""
    A = annees()
    millesimes = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))["ocsge"]["millesimes"]
    lignes = []
    for dep, ms in millesimes.items():
        m = max(int(x) for x in ms)
        if m - 1 not in A or m not in A:
            continue
        d = devenir(m - 1, m)
        p = prairies(m - 1)
        o = ocsge(dep, m)
        o["categorie"] = etat_ocsge(o.code_cs, o.code_us)
        for groupe, col in [("sorties de la déclaration", "non déclaré"),
                            ("témoin : restées prairies", "prairie permanente")]:
            sel = (d.dep == dep) & (d[col] > seuil * d.ha)
            r = croiser(p[sel.values].reset_index(drop=True), o).drop(columns="non déclaré")
            parts = r.drop(columns="ha").sum() / r.ha.sum()
            lignes.append({"source": f"OCS GE {m}", "dep": dep, "groupe": groupe,
                           "prairies": int(sel.sum()), "ha": r.ha.sum(), **parts.to_dict()})
    return pd.DataFrame(lignes)


def comparaison_saa():
    """Prairies permanentes : RPG (Normandie) et statistique agricole annuelle, année par année."""
    s = serie()
    rpg_niveau = pd.Series(list(s.depart) + [s.arrivee.iloc[-1]],
                           index=[int(p[:4]) for p in s.index] + [annees()[-1]])
    a = saa().groupby("annee").niveau.sum()
    t = pd.DataFrame({"rpg_ha": rpg_niveau, "saa_ha": a}).dropna()
    t["rpg_variation"] = t.rpg_ha.diff()
    t["saa_variation"] = t.saa_ha.diff()
    return t.rename_axis("annee")


def habitats():
    """Habitats prairiaux d'intérêt européen (Natura 2000, 14-50-61) : surface cartographiée,
    part déclarée en prairie permanente au début, part retournée à la fin."""
    a0, an, _ = periodes()
    h = habitats_prairiaux()
    p, d = prairies(a0), devenir(a0, an)
    h = h.assign(categorie="habitat")
    m = croiser(p, h)  # surface de chaque prairie couverte par un habitat prairial
    dans = m.get("habitat", pd.Series(0, index=m.index))
    retourne = dans * (d.culture / d.ha).fillna(0).values
    lignes = [{"code": c, "habitat": HABITATS_PRAIRIAUX[c],
               "surface_cartographiee_ha": h.geometry[h.code == c].area.sum() / 1e4}
              for c in HABITATS_PRAIRIAUX]
    t = pd.DataFrame(lignes).set_index("code")
    t.loc["total", "surface_cartographiee_ha"] = t.surface_cartographiee_ha.sum()
    t.loc["total", "habitat"] = "habitats prairiaux d'intérêt européen"
    t.loc["total", "en_prairie_declaree_ha"] = dans.sum()
    t.loc["total", "retourne_ha"] = retourne.sum()
    # état de conservation (1, 2, 3 : du meilleur au plus dégradé), parmi les polygones renseignés
    for e in (1, 2, 3):
        t.loc["total", f"etat_{e}_part"] = (h.etatcons == e).sum() / h.etatcons.notna().sum()
    return t


def moteurs():
    """Le retournement suit-il la progression du maïs ? (communes calculées, quintiles)"""
    c = pd.read_csv(SORTIES / "communes.csv", dtype={"insee": str})
    a0, an, _ = periodes()
    c = c[(c.statut == "calculé") & (c[f"sau_{an}"] > 0)].copy()
    c["evol_mais_part"] = c.evolution_mais_ha / c[f"sau_{an}"]
    c["quintile"] = pd.qcut(c.evol_mais_part.rank(method="first"), 5,
                            labels=["1 (le maïs recule le plus)", "2", "3", "4",
                                    "5 (le maïs progresse le plus)"])
    g = c.groupby("quintile", observed=True).agg(
        communes=("insee", "size"), retourne=("retourne", "sum"), prairies=(f"pp_{a0}", "sum"))
    g["taux_retournement"] = g.retourne / g.prairies / (an - a0)
    g.loc["corrélation de rang", "taux_retournement"] = \
        c.evol_mais_part.rank().corr(c.retournement_taux_annuel.rank())
    return g


def evaluer(avec_certitude=True):
    zonages().to_csv(SORTIES / "evaluation_zonages.csv")
    classes().to_csv(SORTIES / "evaluation_classes.csv")
    robustesse().to_csv(SORTIES / "evaluation_robustesse.csv", index=False)
    concentration().to_csv(SORTIES / "evaluation_concentration.csv")
    prediction().to_csv(SORTIES / "evaluation_prediction.csv")
    sensibilite().to_csv(SORTIES / "evaluation_sensibilite.csv", index=False)
    comparaison_saa().to_csv(SORTIES / "evaluation_saa.csv")
    habitats().to_csv(SORTIES / "evaluation_habitats.csv")
    moteurs().to_csv(SORTIES / "evaluation_moteurs.csv")
    if avec_certitude:
        certitude().to_csv(SORTIES / "evaluation_certitude.csv", index=False)
