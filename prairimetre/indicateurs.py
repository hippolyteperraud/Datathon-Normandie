"""Indicateurs : compteur (combien, où, comment) et boussole (où agir, avec quel levier).

Une seule façon de compter : on compare les prairies du début et de la fin d'une période
(croisement direct des géométries). Les sommes année par année, qui comptent plusieurs fois une
parcelle qui alterne, ne servent qu'au graphique annuel. Seul le territoire normand est compté
(le RPG régional contient aussi des parcelles situées dans les régions voisines).

Sorties (dossier sorties/), chacune lue par l'application :
- serie_region.csv : entrées, sorties et solde, année par année (graphique) ;
- bilan_direct.csv : prairies disparues et apparues entre le début et la fin ;
- cultures_destination.csv : ce que sont devenues les prairies retournées ;
- communes.csv : une ligne par commune (pertes, mécanisme, certitude, zonages, contexte agricole) ;
- captages.csv, communes_captages.csv : les aires d'alimentation de captage d'eau potable.
"""
import ast

import numpy as np
import pandas as pd

from .config import ANNEE_OBJECTIF, ANNEE_REFERENCE_OBJECTIF, CACHE, MIN_HA, RECENT, SORTIES, annees
from .donnees import FAMILLES, ZONAGES, communes, prairies, rpg, zonage
from .suivi import CATEGORIES, avec_commune, categorie, croiser, devenir, origine

FLUX = {"culture": "culture", "non déclaré": "non_declare", "prairie temporaire": "temporaire"}
GROUPES_CULTURES = {
    1: "blé tendre", 2: "maïs (grain et ensilage)", 3: "orge", 4: "autres céréales", 5: "colza",
    6: "tournesol", 7: "autres oléagineux", 8: "protéagineux", 9: "lin, chanvre (fibres)",
    11: "gel", 14: "riz", 15: "légumineuses à grains", 16: "fourrages annuels (trèfle, luzerne…)",
    24: "autres cultures industrielles", 25: "légumes ou fleurs"}
LEVIERS = {
    "retournement": "animation agricole, MAEC et paiements pour services environnementaux ; "
                    "contrôle là où une règle interdit le retournement",
    "sortie de la déclaration": "vérifier sur le terrain avant d'agir : l'herbe est souvent encore "
                                "là, et la statistique agricole ne confirme pas toutes ces pertes",
    "stable ou en gain": "valoriser les pratiques et les éleveurs (exemple à diffuser)",
    "trop peu de prairies": "aucun",
}


def periodes():
    """Début, fin et début de la période récente."""
    A = annees()
    return A[0], A[-1], A[-1] - RECENT


# --- Zonages des prairies d'une année ----------------------------------------------------------

def _zonages_a_jour(t):
    attendues = {f"z_{n}" for n in ZONAGES} | {f"z_{f}" for f in FAMILLES} | {"z_enjeu"}
    return attendues == {c for c in t.columns if c.startswith("z_")}


def appartenance(x, y):
    """Colonnes z_<zonage> et z_<famille> (booléens), nom du PNR, code de l'aire de captage."""
    import geopandas as gpd
    pts = gpd.GeoSeries(gpd.points_from_xy(x, y), crs=2154)
    out = {}
    for nom in ZONAGES:
        z = zonage(nom)
        iz, ip = pts.sindex.query(z.geometry, predicate="contains")
        dedans = np.zeros(len(pts), bool)
        dedans[ip] = True
        out[f"z_{nom}"] = dedans
        if nom == "pnr":
            out["pnr"] = pd.Series(z.nom_site.values[iz], index=ip).groupby(level=0).first() \
                .reindex(range(len(pts))).values
        if nom == "aires_alimentation_captages":
            out["aac"] = pd.Series(z.cdaac.astype(str).values[iz], index=ip).groupby(level=0) \
                .first().reindex(range(len(pts))).values
    out = pd.DataFrame(out)
    for famille, noms in FAMILLES.items():
        out[f"z_{famille}"] = out[[f"z_{n}" for n in noms]].any(axis=1)
    out["z_enjeu"] = out[[f"z_{f}" for f in FAMILLES]].any(axis=1)
    return out


def zonages_annee(a):
    """Pour chaque prairie de l'année a (même ordre que prairies(a)) : commune, surface, zonages."""
    f = CACHE / f"zonages_{a}.parquet"
    if f.exists():
        z = pd.read_parquet(f)
        if _zonages_a_jour(z):
            return z
    p = prairies(a)
    pt = p.geometry.representative_point()
    z = appartenance(pt.x.values, pt.y.values)
    z = pd.concat([avec_commune(p).reset_index(drop=True), z], axis=1)
    z["ha"] = p.geometry.area.values / 1e4
    z.to_parquet(f)
    return z


def normandie(t):
    """Garde les objets situés en Normandie (commune connue)."""
    return t[t.insee.notna()]


# --- Compteur -----------------------------------------------------------------------------------

def _flux(a, b, par=None):
    """Sorties (devenir) et entrées (origine) entre a et b, en Normandie, éventuellement par clé."""
    s, e = normandie(devenir(a, b)), normandie(origine(a, b))
    if par is None:
        s, e = s.assign(k=0), e.assign(k=0)
        par = "k"
    cols = list(FLUX)
    t = pd.concat([
        s.groupby(par).ha.sum().rename("depart"),
        e.groupby(par).ha.sum().rename("arrivee"),
        s.groupby(par)[cols].sum().rename(columns=lambda c: f"sortie_{FLUX[c]}"),
        e.groupby(par)[cols].sum().rename(columns=lambda c: f"entree_{FLUX[c]}"),
    ], axis=1).fillna(0)
    t["solde"] = t.arrivee - t.depart
    return t


def serie():
    """Année par année, en Normandie : surface de départ et d'arrivée, flux (graphique annuel)."""
    A = annees()
    t = pd.concat({f"{a}-{a + 1}": _flux(a, a + 1) for a in A[:-1]}, names=["periode"])
    return t.droplevel(-1)


def bilan_direct():
    """Début -> fin : prairies disparues (et ce qu'elles sont devenues), prairies apparues
    (et d'où elles viennent), par département et pour la Normandie."""
    a0, an, _ = periodes()
    lignes = {}
    for sens, t in [("disparues_devenues", normandie(devenir(a0, an))),
                    ("nouvelles_venant_de", normandie(origine(a0, an)))]:
        cols = [c for c in CATEGORIES if c != "prairie permanente"]
        par_dep = t.groupby("dep")[cols].sum()
        par_dep.loc["région"] = t[cols].sum()
        par_dep["total"] = par_dep.sum(axis=1)
        par_dep[("depart" if sens.startswith("disp") else "arrivee")] = \
            pd.concat([t.groupby("dep").ha.sum(), pd.Series({"région": t.ha.sum()})])
        lignes[sens] = par_dep
    return pd.concat(lignes, axis=1)


def cultures_destination():
    """Ce que sont devenues les prairies du début retournées en culture à la fin (par culture)."""
    a0, an, _ = periodes()
    f = CACHE / f"cultures_{a0}_{an}.parquet"
    if f.exists():
        return pd.read_parquet(f)
    d = devenir(a0, an)
    p = prairies(a0)[d.insee.notna().values].reset_index(drop=True)
    r = rpg(an)
    r = r[r.code_group.isin(list(GROUPES_CULTURES))].copy()
    r["categorie"] = r.code_group.map(GROUPES_CULTURES)
    m = croiser(p, r).drop(columns=["ha", "non déclaré"]).sum().sort_values(ascending=False)
    t = pd.DataFrame({"ha": m, "part": m / m.sum()}).rename_axis("culture")
    t.to_parquet(f)
    return t


def objectif():
    """Trajectoire vers l'objectif 2030 : surface de référence et écart."""
    s = serie()
    niveaux = pd.Series(list(s.depart) + [s.arrivee.iloc[-1]],
                        index=[int(p[:4]) for p in s.index] + [annees()[-1]])
    ref = niveaux.get(ANNEE_REFERENCE_OBJECTIF)
    return pd.DataFrame({"annee": niveaux.index, "prairies_ha": niveaux.values,
                         "reference_ha": ref, "annee_reference": ANNEE_REFERENCE_OBJECTIF,
                         "annee_objectif": ANNEE_OBJECTIF,
                         "ecart_ha": niveaux.values - ref if ref is not None else np.nan})


# --- Contexte agricole -------------------------------------------------------------------------

def rpg_communes(a):
    """Commune de chaque parcelle RPG de l'année a (même ordre que rpg(a))."""
    f = CACHE / f"rpg_insee_{a}.parquet"
    if f.exists():
        return pd.read_parquet(f).insee
    t = avec_commune(rpg(a)).reset_index(drop=True)
    t.to_parquet(f)
    return t.insee


def contexte_agricole():
    """Par commune : surface agricole déclarée et maïs, début et fin (RPG)."""
    a0, an, _ = periodes()
    lignes = {}
    for a in (a0, an):
        r = rpg(a)
        r = r.assign(insee=rpg_communes(a).values, mais=r.surf_parc.where(r.code_group == 2, 0))
        g = r.groupby("insee")[["surf_parc", "mais"]].sum()
        lignes[f"sau_{a}"], lignes[f"mais_{a}"] = g.surf_parc, g.mais
    t = pd.DataFrame(lignes).fillna(0)
    t[f"part_mais_{an}"] = (t[f"mais_{an}"] / t[f"sau_{an}"]).where(t[f"sau_{an}"] > 0)
    t["evolution_mais_ha"] = t[f"mais_{an}"] - t[f"mais_{a0}"]
    return t


# --- Communes ----------------------------------------------------------------------------------

def _par_commune(t, prefixe):
    cols = {"ha": f"{prefixe}ha"} | {c: f"{prefixe}{FLUX.get(c, c)}" for c in FLUX}
    g = t.groupby("insee")[["ha", *FLUX, "prairie permanente"]].sum()
    g = g.rename(columns=cols | {"prairie permanente": f"{prefixe}reste"})
    return g


def table_communes():
    a0, an, r0 = periodes()
    D, O = normandie(devenir(a0, an)), normandie(origine(a0, an))
    Dr = devenir(r0, an)
    c = communes().drop(columns="geometry").set_index("insee")
    s, e = _par_commune(D, "devenues_"), _par_commune(O, "venues_")
    t = c.join(pd.DataFrame({f"pp_{a0}": s["devenues_ha"], f"pp_{an}": e["venues_ha"]}))
    t = t.join(s.drop(columns="devenues_ha")).join(e.drop(columns="venues_ha"))
    t["disparues"] = t[f"pp_{a0}"] - t["devenues_reste"]
    t["apparues"] = t[f"pp_{an}"] - t["venues_reste"]
    t["retourne"] = t["devenues_culture"]

    # Période récente (r0 -> an) : retournement, et retournement dans un zonage d'enjeux
    Zr = zonages_annee(r0)
    rec = pd.DataFrame({"insee": Zr.insee, "ha": Dr.ha.values, "retourne": Dr.culture.values,
                        "enjeu": Dr.culture.values * (Zr.z_enjeu | Zr.aac.notna()).values})
    rec = rec.dropna(subset=["insee"]).groupby("insee").sum()
    t[f"pp_{r0}"] = rec.ha
    t["retourne_recent"] = rec.retourne
    t["retourne_recent_enjeux"] = rec.enjeu
    num = [x for x in t.columns if x.startswith(("pp_", "devenues_", "venues_", "retourne"))] \
        + ["disparues", "apparues"]
    t[num] = t[num].fillna(0)  # commune sans prairie : 0 ha (les textes restent intacts)
    t["solde"] = t[f"pp_{an}"] - t[f"pp_{a0}"]
    t["part_anciennes"] = (t["venues_reste"] / t[f"pp_{an}"]).where(t[f"pp_{an}"] > 0)

    base = t[f"pp_{a0}"]
    valide = base >= MIN_HA
    t["solde_taux"] = (t.solde / base).where(valide)
    t["retournement_taux_annuel"] = (t.retourne / base / (an - a0)).where(valide)
    t["retournement_recent_taux_annuel"] = (t.retourne_recent / t[f"pp_{r0}"] / RECENT) \
        .where(t[f"pp_{r0}"] >= MIN_HA)

    # Mécanisme dominant : le solde le plus négatif entre culture et non-déclaration
    s_cult = t.venues_culture - t.devenues_culture
    s_nd = t.venues_non_declare - t.devenues_non_declare
    t["mecanisme"] = np.where(s_cult <= s_nd, "retournement", "sortie de la déclaration")
    t.loc[t.solde >= 0, "mecanisme"] = "stable ou en gain"
    t.loc[~valide, "mecanisme"] = "trop peu de prairies"
    t["levier"] = t.mecanisme.map(LEVIERS)

    # Certitude : un retournement est déclaré en culture ; une sortie de la déclaration ne dit
    # pas ce qu'est devenue la parcelle (et la statistique agricole ne la voit pas toujours)
    pertes = (t.devenues_culture + t.devenues_non_declare).replace(0, np.nan)
    part_declaree = t.devenues_culture / pertes
    t["certitude"] = np.select([~valide, part_declaree >= 0.5],
                               ["non calculée", "pertes déclarées"], "pertes à vérifier")

    # Zonages des prairies actuelles de la commune
    z = normandie(zonages_annee(an))
    tot = z.groupby("insee").ha.sum()
    for famille in FAMILLES:
        t[f"part_{famille}"] = (z.ha.where(z[f"z_{famille}"], 0).groupby(z.insee).sum() / tot) \
            .reindex(t.index)
    t["pnr"] = z.dropna(subset=["pnr"]).groupby("insee").pnr.first().reindex(t.index)
    t["prairies_en_captage_ha"] = z.ha.where(z.aac.notna(), 0).groupby(z.insee).sum() \
        .reindex(t.index).fillna(0)

    t = t.join(contexte_agricole())

    # Pourquoi un indicateur peut manquer : à afficher tel quel, jamais un « NaN »
    t["statut"] = np.select([(base == 0) & (t[f"pp_{an}"] == 0), ~valide],
                            ["aucune prairie", f"moins de {MIN_HA} ha de prairies en {a0}"],
                            "calculé")

    # Trois classements, à présenter ensemble : ils ne désignent pas les mêmes communes
    t["rang_hectares"] = t.retourne_recent.rank(ascending=False, method="min")
    t["rang_taux"] = t.retournement_recent_taux_annuel.where(t[f"pp_{r0}"] >= 100) \
        .rank(ascending=False, method="min")
    t["rang_enjeux"] = t.retourne_recent_enjeux.rank(ascending=False, method="min")
    return t


# --- Captages -----------------------------------------------------------------------------------

def _intervenant(texte):
    """Nom d'un intervenant Sandre (texte du type "{'CdIntervenant': ..., 'NomIntervenant': ...}")."""
    try:
        v = ast.literal_eval(texte) if isinstance(texte, str) else None
    except (ValueError, SyntaxError):
        return None
    v = v[0] if isinstance(v, list) and v else v
    if not isinstance(v, dict):
        return None
    return v.get("NomIntervenant") or v.get("NomPointPrelevement")


def table_captages(t):
    """Une ligne par aire d'alimentation de captage : qui la gère, ses prairies, ce qu'elle perd.
    Seule la partie normande de chaque aire est comptée."""
    from .donnees import region
    a0, an, r0 = periodes()
    D, Dr = devenir(a0, an), devenir(r0, an)
    Z0, Zr, Zn = zonages_annee(a0), zonages_annee(r0), normandie(zonages_annee(an))
    debut = pd.DataFrame({"aac": Z0.aac, "insee": Z0.insee, "ha": Z0.ha, "retourne": D.culture.values,
                          "sortie": D["non déclaré"].values}).dropna(subset=["aac", "insee"])
    recent = pd.DataFrame({"aac": Zr.aac, "insee": Zr.insee, "ha": Zr.ha,
                           "retourne": Dr.culture.values}).dropna(subset=["aac", "insee"])
    a = zonage("aires_alimentation_captages")
    a = a.assign(cdaac=a.cdaac.astype(str)).drop_duplicates("cdaac").set_index("cdaac")
    surface = a.geometry.intersection(region().geometry.iloc[0]).area / 1e4

    g = pd.DataFrame({
        "nom": a.nomdeaacadministratif,
        "maitre_ouvrage": a.commandaac.map(_intervenant),
        "service_etat": a.adminaac.map(_intervenant),
        "point_prelevement": a.ptp.map(_intervenant),
        # toujours connue (le Sandre ne renseigne pas toujours le maître d'ouvrage)
        "agence_eau": "Agence de l'eau " + a.nomcircadminbassin.str.title(),
        "surface_normandie_ha": surface,
        f"pp_{a0}": debut.groupby("aac").ha.sum(),
        f"pp_{r0}": recent.groupby("aac").ha.sum(),
        f"pp_{an}": Zn.dropna(subset=["aac"]).groupby("aac").ha.sum(),
        "retourne_ha": debut.groupby("aac").retourne.sum(),
        "retourne_recent_ha": recent.groupby("aac").retourne.sum(),
        "sortie_declaration_ha": debut.groupby("aac").sortie.sum(),
    })
    g = g[g[f"pp_{a0}"].fillna(0) > 0]
    g = g.fillna({c: 0 for c in g.columns if c.startswith(("pp_", "retourne", "sortie"))})
    g["solde"] = g[f"pp_{an}"] - g[f"pp_{a0}"]
    g["solde_taux"] = g.solde / g[f"pp_{a0}"]
    g["part_en_prairie"] = g[f"pp_{an}"] / g.surface_normandie_ha
    g["retournement_recent_taux_annuel"] = (g.retourne_recent_ha / g[f"pp_{r0}"] / RECENT) \
        .where(g[f"pp_{r0}"] >= MIN_HA)
    noms = t.nom_officiel
    par_commune = Zn.dropna(subset=["aac"]).groupby(["aac", "insee"]).ha.sum().reset_index()
    g["communes"] = par_commune.groupby("aac").insee.nunique()
    g["communes_principales"] = par_commune.sort_values("ha", ascending=False).groupby("aac") \
        .insee.apply(lambda s: ", ".join(noms.reindex(s.head(3)).fillna(s.head(3)).tolist()))
    g["rang_hectares"] = g.retourne_recent_ha.rank(ascending=False, method="min")
    g["rang_taux"] = g.retournement_recent_taux_annuel.where(g[f"pp_{r0}"] >= 100) \
        .rank(ascending=False, method="min")
    return g.sort_values("retourne_recent_ha", ascending=False).rename_axis("aac"), par_commune


# --- Consultation à la demande (application) ---------------------------------------------------

def flux_commune(insee):
    """Entrées, sorties et solde d'une commune, année par année."""
    A = annees()
    lignes = {}
    for a in A[:-1]:
        t = _flux(a, a + 1, "insee")
        if insee in t.index:
            lignes[f"{a}-{a + 1}"] = t.loc[insee]
    return pd.DataFrame(lignes).T.rename_axis("periode")


def parcelles_commune(insee):
    """Prairies du début avec leur devenir dominant à la fin, et prairies apparues depuis avec
    leur origine dominante (GeoDataFrames, Lambert-93)."""
    a0, an, _ = periodes()
    sorties = []
    for t, p, col in [(devenir(a0, an), prairies(a0), "devenir"),
                      (origine(a0, an), prairies(an), "origine")]:
        sel = (t.insee == insee).values
        g = p.loc[sel, ["geometry"]].copy()
        g[col] = t.loc[sel, CATEGORIES].idxmax(axis=1).values
        g["ha"] = t.loc[sel, "ha"].values
        sorties.append(g.reset_index(drop=True))
    disparues, nouvelles = sorties
    return disparues, nouvelles[nouvelles.origine != "prairie permanente"]


def calculer():
    """Écrit toutes les tables du compteur et de la boussole dans sorties/."""
    serie().to_csv(SORTIES / "serie_region.csv")
    bilan_direct().to_csv(SORTIES / "bilan_direct.csv")
    cultures_destination().to_csv(SORTIES / "cultures_destination.csv")
    objectif().to_csv(SORTIES / "objectif.csv", index=False)
    t = table_communes()
    t.to_csv(SORTIES / "communes.csv")
    aac, par_commune = table_captages(t)
    aac.to_csv(SORTIES / "captages.csv")
    par_commune.rename(columns={"ha": "prairies_ha"}).to_csv(SORTIES / "communes_captages.csv",
                                                             index=False)
    for ancien in ("captages_annees.csv",):  # tables d'une version précédente
        (SORTIES / ancien).unlink(missing_ok=True)
    return t
