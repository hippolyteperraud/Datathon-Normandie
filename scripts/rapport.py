"""Rapport du Prairimètre : un document HTML et PDF, avec ses cartes et ses graphiques, tous calculés à
partir des sorties du moteur (sorties/) et de la vérification satellite (verification/sentinel2/).
Aucun chiffre de résultat n'est écrit à la main ; les chiffres officiels cités viennent de
app/references.py, avec leur source.

Depuis la racine du projet :
    python scripts/rapport.py            # écrit docs/rapport/rapport_prairimetre.html et .pdf
"""
import json
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(RACINE), str(RACINE / "app")]

import geopandas as gpd  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

from prairimetre.config import CACHE, SORTIES  # noqa: E402
from prairimetre.sentinel import DOSSIER as SAT, bilan as bilan_sat, mesures, resume_mesures  # noqa: E402
from references import (AGRICULTEUR_ACTIF, FIN_AUTORISATION_2019, OBJECTIF_REGIONAL,  # noqa: E402
                        RATIOS, REFERENCE_RATIO)

SORTIE = RACINE / "docs" / "rapport"
FIG = SORTIE / "figures"
BLEU, GRIS, ROUGE, ORANGE, VERT = "#2a78d6", "#8a897f", "#c2452d", "#f0a202", "#2e7d4f"
FOND, TRAIT = "#ecebe6", "#ffffff"
DEPS = {"14": "Calvados", "27": "Eure", "50": "Manche", "61": "Orne", "76": "Seine-Maritime"}
OFFICIEL = {"perte_ha": -59703, "ratio_evol_pct": -1.97, "date": "septembre 2026",
            "source": "arrêté du 11 septembre 2026, JORF n° 0218 du 18 septembre 2026"}

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": "#888", "axes.labelcolor": "#333",
                     "xtick.color": "#444", "ytick.color": "#444", "figure.dpi": 100})


# --- Formats français --------------------------------------------------------------------------
def nb(x, dec=0, signe=False):
    s = f"{x:{'+' if signe else ''},.{dec}f}".replace(",", "\u202f").replace(".", ",")
    return s.replace("-", "−")


def ha(x, signe=False):
    return f"{nb(x, 0, signe)}\u00a0ha"


def axe_fr(ax, axe="y"):
    f = matplotlib.ticker.FuncFormatter(lambda v, _: nb(v))
    (ax.yaxis if axe == "y" else ax.xaxis).set_major_formatter(f)


def sauver(fig, nom):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / nom, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return f"figures/{nom}"


# --- Les données -------------------------------------------------------------------------------
def lire(nom, **kw):
    return pd.read_csv(SORTIES / f"{nom}.csv", **kw)


t = lire("communes", dtype={"insee": str, "epci": str, "dep": str}).set_index("insee")
obj = lire("objectif").set_index("annee")
serie = lire("serie_region")
suivi = lire("suivi_sorties", dtype={"dep": str})
bil = pd.read_csv(SORTIES / "bilan_direct.csv", header=[0, 1], index_col=0).loc["région"]
cl = pd.read_csv(SORTIES / "evaluation_classes.csv", index_col=0)
rob = pd.read_csv(SORTIES / "evaluation_robustesse.csv")
terrain = pd.read_csv(SORTIES / "evaluation_terrain.csv")
bcae2 = pd.read_csv(SORTIES / "evaluation_bcae2.csv")
photos = pd.read_csv(SAT / "photo_interpretation.csv", dtype={"id_rpg": str}) \
    if (SAT / "photo_interpretation.csv").exists() else pd.DataFrame()
saa_2023 = pd.read_csv(SORTIES / "evaluation_saa.csv").set_index("annee").saa_variation.loc[2023]
sobriete = pd.read_csv(SORTIES / "sobriete.csv") if (SORTIES / "sobriete.csv").exists() else None
images_ko = (SAT / "images.csv").stat().st_size / 1024
calc = t[t.statut == "calculé"]
A = sorted(int(c[3:]) for c in t.columns if c.startswith("pp_") and c[3:].isdigit())
a0, an = A[0], A[-1]
a_ref, a_obj = int(obj.annee_reference.iloc[0]), int(obj.annee_objectif.iloc[0])
niveau, sth = obj.prairies_ha.dropna(), obj.sth_ha.dropna()
sth_fin = int(sth.index.max())
ecart = niveau.loc[an] - niveau.loc[a_ref]
sth_ecart = sth.loc[sth_fin] - sth.loc[a_ref]
part = obj.part_sth.dropna() if "part_sth" in obj else pd.Series(dtype=float)
saa_2019 = pd.read_csv(SORTIES / "evaluation_saa.csv").set_index("annee").saa_variation.get(2019)
solde = bil[("nouvelles_venant_de", "arrivee")] - bil[("disparues_devenues", "depart")]
retournees = bil[("disparues_devenues", "culture")]
sorties = bil[("disparues_devenues", "non déclaré")]

s = serie.assign(fin=serie.periode.str[-4:].astype(int))
s = s.merge(suivi[suivi.dep == "région"].drop(columns=["dep", "fin"]), on="periode")
s["libelle"] = s.periode.str.replace("-", "→")
s["entrees"] = s.entree_culture + s.entree_non_declare + s.entree_temporaire
r23 = s[s.fin == 2023].iloc[0]
r19 = s[s.fin == 2019].iloc[0]
autres = s[~s.fin.isin([2019, 2023])]
ordinaire_sorties, ordinaire_ret = autres.sortie_non_declare.median(), autres.sortie_culture.median()
part_revenue = (s.redeclares_ha / s.sortis_ha).where(s.fin < an)
ordinaire_retour = part_revenue[~s.fin.isin([2019]) & part_revenue.notna()].median()

regle, hors = cl.loc["règle"], cl.loc["aucun zonage"]
rapports = rob[rob.zonage == "regle"].rapport_meme_commune
aac = rob[rob.zonage == "aires_alimentation_captages"].rapport_meme_commune

ret = calc.retourne_recent.sort_values(ascending=False)
liste211 = list(ret.index[:int((ret.cumsum() / ret.sum() < 0.5).sum() + 1)])
rang = calc.devenues_non_declare.sort_values(ascending=False)
moitie = list(rang.index[:int((rang.cumsum() / rang.sum() < 0.5).sum() + 1)])
prio = [i for i in moitie if i not in set(liste211)]
second = [i for i in moitie if i in set(liste211)]

# Prendre exemple : même calcul que la page
sur_cultures = calc.venues_culture - calc.devenues_culture
temporaires = (calc.venues_temporaire - calc.devenues_temporaire).clip(lower=0)
declarees = calc.venues_non_declare - calc.devenues_non_declare
assure = pd.concat([calc.solde, sur_cultures], axis=1).min(axis=1)
gain = assure[(calc.solde > 0) & (sur_cultures >= declarees + temporaires) & (assure >= 5)]
sans_perte = calc.index[calc.disparues < 1]

# Satellite
sat_t = pd.read_csv(SAT / "parcelles.csv", dtype={"id_rpg": str, "insee": str})
sat = bilan_sat(sat_t)
s23, val = sat["sortie 2023"], sat["validation"]
images = pd.read_csv(SAT / "images.csv", dtype={"id_rpg": str})
com_sat = mesures()           # le bloc des mesures de la dernière année : toutes les communes
res_sat = resume_mesures()

# Fond de carte : communes en Lambert-93, contours des départements
g = gpd.read_parquet(CACHE / "carte_communes.parquet").to_crs(2154)
deps = g.assign(geometry=g.buffer(60)).dissolve("dep").buffer(-60).boundary


def fond(ax):
    g.plot(ax=ax, color=FOND, edgecolor=TRAIT, linewidth=0.15)
    deps.plot(ax=ax, color="#555", linewidth=0.6)
    ax.set_axis_off()
    ax.set_aspect("equal")


# --- Figures -------------------------------------------------------------------------------------
def fig_sources():
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    ax.plot(niveau.index, niveau.values, "-o", color=BLEU, ms=4, lw=2, label="registre PAC (déclarées)")
    ax.plot(sth.index, sth.values, "-o", color=GRIS, ms=4, lw=2,
            label="statistique agricole (toujours en herbe)")
    ax.axvline(a_ref, color="#bbb", lw=0.8, ls=":")
    ax.text(a_ref + 0.05, ax.get_ylim()[1], f" {a_ref}, référence\n de l'objectif", va="top", fontsize=7.5,
            color="#666")
    for k, (fin, txt) in enumerate([(2019, "fin de l'autorisation\n+ registre troué"),
                                    (2023, "retraités sortis\nde la PAC")], 1):
        y = niveau.loc[fin]
        ax.annotate(f"{k}", (fin, y), xytext=(9, -11), textcoords="offset points", ha="center",
                    color=ORANGE, fontweight="bold", fontsize=11)
    axe_fr(ax)
    ax.set_ylabel("hectares")
    ax.legend(frameon=False, loc="center right", fontsize=8)
    ax.set_xticks(range(a0, an + 1))
    return sauver(fig, "deux_sources.png")


def fig_flux():
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    x = np.arange(len(s))
    ax.bar(x, s.entrees, color=VERT, label="entrées")
    ax.bar(x, -s.sortie_culture, color=ROUGE, label="retournées en culture")
    ax.bar(x, -s.sortie_non_declare, bottom=-s.sortie_culture, color=ORANGE,
           label="sorties de la déclaration")
    ax.scatter(x, s.solde, marker="_", s=260, color="black", lw=2.5, label="solde de l'année", zorder=3)
    ax.axhline(0, color="#999", lw=0.6)
    for k, fin in enumerate([2019, 2023], 1):
        i = int(np.where(s.fin == fin)[0][0])
        ax.text(i, -(s.sortie_culture.iloc[i] + s.sortie_non_declare.iloc[i]) - 2500, str(k),
                ha="center", va="top", color=ORANGE, fontweight="bold", fontsize=11)
    ax.set_xticks(x, s.libelle, rotation=30, fontsize=8)
    axe_fr(ax)
    ax.set_ylabel("hectares")
    ax.legend(frameon=False, fontsize=7.5, ncol=2, loc="upper right")
    ax.set_ylim(top=s.entrees.max() * 1.9)
    return sauver(fig, "flux_annuels.png")


def fig_draaf():
    p = suivi[(suivi.periode == "2022-2023") & (suivi.dep != "région")].set_index("dep").sortis_ha
    k = list(AGRICULTEUR_ACTIF["prairies_par_dep_ha"])
    fig, ax = plt.subplots(figsize=(4.6, 2.6))
    y = np.arange(len(k))
    ax.barh(y + 0.2, [AGRICULTEUR_ACTIF["prairies_par_dep_ha"][d] for d in k], 0.38, color=GRIS,
            label="DRAAF Normandie")
    ax.barh(y - 0.2, [p.get(d, 0) for d in k], 0.38, color=ORANGE, label="Prairimètre")
    ax.set_yticks(y, [DEPS[d] for d in k])
    ax.invert_yaxis()
    axe_fr(ax, "x")
    ax.set_xlabel("hectares de prairies sortis de la déclaration en 2023")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    return sauver(fig, "draaf_prairimetre.png")


def fig_regles():
    noms = {"règle": "sous une règle qui\nencadre le labour", "site protégé": "site protégé",
            "inventaire seul": "inventaire seul", "aucun zonage": "aucun zonage"}
    v = 1000 * cl.retourne / cl.ha
    fig, ax = plt.subplots(figsize=(4.8, 2.4))
    couleurs = [VERT if i == "règle" else ROUGE if i == "aucun zonage" else GRIS for i in cl.index]
    ax.barh(range(len(v)), v.values, color=couleurs)
    for i, x in enumerate(v.values):
        ax.text(x + 1.5, i, nb(x), va="center", fontsize=8)
    ax.set_yticks(range(len(v)), [noms.get(i, i) for i in cl.index], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel(f"ha retournés en culture {a0}→{an}, sur 1 000 ha de prairies de {a0}")
    ax.set_xlim(0, v.max() * 1.18)
    return sauver(fig, "regles.png")


def fig_carte_retournement():
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    fond(ax)
    v = calc.retourne_recent.reindex(g.insee)
    gg = g.assign(v=v.values)
    bornes = [0, 5, 15, 30, 60, np.inf]
    teintes = ["#f7e6d4", "#f1c08c", "#e48a52", "#c9512f", "#8a2318"]
    gg["classe"] = pd.cut(gg.v, bornes, labels=False, include_lowest=True)
    gg[gg.v.notna()].plot(ax=ax, column="classe", cmap=ListedColormap(teintes), vmin=0, vmax=len(teintes) - 1, edgecolor=TRAIT,
                          linewidth=0.1)
    gg[gg.insee.isin(liste211)].boundary.plot(ax=ax, color="black", linewidth=0.45)
    deps.plot(ax=ax, color="#555", linewidth=0.6)
    etiquettes = ["moins de 5 ha", "5 à 15 ha", "15 à 30 ha", "30 à 60 ha", "plus de 60 ha"]
    poignees = [Patch(color=c, label=e) for c, e in zip(teintes, etiquettes)] + [
        Patch(facecolor="none", edgecolor="black", label=f"les {len(liste211)} communes qui portent\n"
                                                          "la moitié du retournement"),
        Patch(color=FOND, label="peu ou pas de prairies")]
    ax.legend(handles=poignees, loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False, fontsize=7.5,
              title=f"Retournées en culture, {an - 3}→{an}", title_fontsize=8)
    return sauver(fig, "carte_retournement.png")


def fig_carte_aller_voir():
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    fond(ax)
    if len(com_sat):
        c = com_sat[com_sat.etat != "indéterminé"].groupby("insee").apply(
            lambda x: x.loc[x.etat == "couvert permanent", "ha"].sum() / x.ha.sum(), include_groups=False)
        gg = g.assign(v=g.insee.map(c))
        bornes, teintes = [0, 0.5, 0.8, 0.95, 1.01], ["#c9512f", "#f1c08c", "#a8d5a2", "#2e7d4f"]
        gg["classe"] = pd.cut(gg.v, bornes, labels=False, include_lowest=True, right=False)
        gg[gg.v.notna()].plot(ax=ax, column="classe", cmap=ListedColormap(teintes), vmin=0, vmax=len(teintes) - 1, edgecolor=TRAIT,
                              linewidth=0.1)
        gris = gg[gg.insee.isin(set(com_sat.insee)) & gg.v.isna()]  # mesurées, rien de tranché
        if len(gris):
            gris.plot(ax=ax, color="#d8d6cc", hatch="////", edgecolor="#999", linewidth=0.1)
        etiquettes = ["moins de la moitié", "50 à 80 sur 100", "80 à 95 sur 100", "95 sur 100 et plus"]
        poignees = [Patch(color=c, label=e) for c, e in zip(teintes, etiquettes)] + (
            [Patch(facecolor="#d8d6cc", hatch="////", edgecolor="#999",
                   label=f"rien de tranché ({len(gris)})")] if len(gris) else []) + [
            Patch(color=FOND, label="aucune prairie sortie\nd'au moins 1 ha")]
        titre = (f"Prairies sorties encore vertes en {an}\n(ha sur 100 tranchés par le satellite,\n"
                 "images Sentinel-2)")
    else:
        gg = g.assign(p=g.insee.isin(prio), s=g.insee.isin(second))
        gg[gg.p].plot(ax=ax, color=ORANGE, edgecolor=TRAIT, linewidth=0.1)
        gg[gg.s].plot(ax=ax, color="#f6c99c", edgecolor=TRAIT, linewidth=0.1)
        poignees = [Patch(color=ORANGE, label=f"prioritaires ({len(prio)})"),
                    Patch(color="#f6c99c", label=f"secondaires ({len(second)})")]
        titre = "Communes à aller voir"
    deps.plot(ax=ax, color="#555", linewidth=0.6)
    ax.legend(handles=poignees, loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False, fontsize=7.5,
              title=titre, title_fontsize=8)
    return sauver(fig, "carte_aller_voir.png")


def fig_carte_echantillon():
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    fond(ax)
    e = sat_t[sat_t.groupe.isin(["sortie 2023", "30 parcelles"])]
    pts = gpd.GeoDataFrame(e, geometry=gpd.points_from_xy(e.longitude, e.latitude), crs=4326).to_crs(2154)
    styles = {"couvert permanent": (VERT, "o", "verte toute l'année"), "labourée": (ROUGE, "X", "labourée"),
              "indéterminé": ("#999", "o", "ne se tranche pas")}
    for etat, (c, mk, lab) in styles.items():
        x = pts[pts.etat == etat]
        if len(x):
            x.plot(ax=ax, color=c, marker=mk, markersize=26, edgecolor="white", linewidth=0.5,
                   label=f"{lab} ({len(x)})")
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False, fontsize=7.5,
              title="Prairies sorties vérifiées par satellite", title_fontsize=8)
    return sauver(fig, "carte_echantillon.png")


def fig_ndvi():
    """Trois profils de NDVI de l'année : une prairie déclarée, une culture, une prairie sortie."""
    p = images[(images.part_sale < 0.05) & images.ndvi.notna()].copy()
    p["date"] = pd.to_datetime(p.date)

    def un(groupe, etat):
        """La parcelle du groupe la plus parlante : la plus d'images, et pour une culture, le plus
        d'images en sol nu."""
        ids = sat_t[(sat_t.groupe == groupe) & (sat_t.etat == etat)].id_rpg
        x = p[p.id_rpg.isin(ids)].groupby("id_rpg").ndvi
        score = x.apply(lambda v: (v < 0.25).sum()) * 100 + x.size() if etat == "labourée" else x.size()
        return p[p.id_rpg == score.idxmax()] if len(score) else None
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    for (groupe, etat, c, lab) in [("validation prairie", "couvert permanent", VERT,
                                    "prairie encore déclarée (témoin)"),
                                   ("validation culture", "labourée", ROUGE, "parcelle mise en culture (témoin)"),
                                   ("sortie 2023", "couvert permanent", ORANGE,
                                    "prairie sortie de la PAC en 2023")]:
        x = un(groupe, etat)
        if x is not None:
            ax.plot(x.date, x.ndvi, "-o", color=c, ms=3, lw=1.6, label=lab)
    ax.axhline(0.25, color="#999", lw=0.7, ls="--")
    ax.text(p.date.min(), 0.26, "sol nu sous 0,25", fontsize=7, color="#666")
    ax.set_ylabel("NDVI (images sans nuage)")
    ax.set_ylim(0, 0.95)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: nb(v, 1)))
    ax.legend(frameon=False, fontsize=7.5, loc="lower right")
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%m/%y"))
    return sauver(fig, "profils_ndvi.png")


def fig_photos():
    """Quatre des cas douteux, sur la photo aérienne de l'IGN, avec leur lecture."""
    from PIL import Image
    if photos.empty:
        return None
    choix = photos.head(4)
    import textwrap
    fig, axes = plt.subplots(1, len(choix), figsize=(7.4, 2.6))
    for ax, (_, r) in zip(np.atleast_1d(axes), choix.iterrows()):
        ax.imshow(Image.open(SAT / r.photo))
        ax.set_axis_off()
        legende_photo = r.ce_qu_on_voit.split(" ;")[0].split(",")[0]
        ax.set_title("\n".join(textwrap.wrap(legende_photo, 26)), fontsize=7)
    return sauver(fig, "photos_aeriennes.png")


def fig_carte_exemples():
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    fond(ax)
    g[g.insee.isin(sans_perte) & ~g.insee.isin(gain.index)].plot(ax=ax, color="#8fc93a", edgecolor=TRAIT,
                                                                 linewidth=0.1)
    g[g.insee.isin(gain.index)].plot(ax=ax, color=VERT, edgecolor=TRAIT, linewidth=0.1)
    deps.plot(ax=ax, color="#555", linewidth=0.6)
    ax.legend(handles=[Patch(color=VERT, label=f"gagnent sur d'anciennes cultures ({len(gain)})"),
                       Patch(color="#8fc93a", label=f"ne perdent rien ({len(set(sans_perte) - set(gain.index))} "
                                                    "autres)")],
              loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False, fontsize=7.5,
              title="Communes exemples depuis 2018",
              title_fontsize=8)
    return sauver(fig, "carte_exemples.png")


# --- Le document -------------------------------------------------------------------------------
def rapport():
    figs = {f.__name__: f() for f in (fig_sources, fig_flux, fig_draaf, fig_regles, fig_carte_retournement,
                                      fig_carte_aller_voir, fig_carte_echantillon, fig_ndvi,
                                      fig_carte_exemples, fig_photos)}
    aa, o = AGRICULTEUR_ACTIF, OBJECTIF_REGIONAL
    pire = ecart + s23["bas"] * s23["population_ha"]
    mieux = ecart + r23.toujours_hors_ha
    if res_sat:
        r = res_sat
        v_100, l_100 = (round(100 * r[k] / r["ha"]) for k in ("ha_verts", "ha_laboures"))
        complet = r["parcelles"] >= r["cible_parcelles"]
        avancement = (f"{nb(r['parcelles'])} parcelles, {ha(r['ha'])}"
                      + ("" if complet else f", sur {nb(r['cible_parcelles'])} à mesurer ({ha(r['cible_ha'])})"))
        com_txt = (f"<p>Dans toute la Normandie, chaque prairie de {a0} d'au moins 1&nbsp;ha sortie de la "
                   f"déclaration en {an} est mesurée une à une sur les images {an} : {avancement}"
                   f"{' (toutes)' if complet else ''}. <b>{v_100} ha sur 100 restent verts toute "
                   f"l'année</b> ({ha(r['ha_verts'])}), {l_100} ont été labourés ({ha(r['ha_laboures'])}) ; "
                   f"les {100 - v_100 - l_100} autres ne se tranchent pas ({r['pourquoi_indetermines']})"
                   + (f" ou sont bâtis ({ha(r['ha_batis'])})" if r["ha_batis"] >= 0.5 else "")
                   + ". La carte le dit commune par commune.</p>")
        inconnu_sat = (f"le satellite a mesuré {ha(r['ha'])} sur les {ha(sorties)} de prairies sorties depuis {a0} "
                       "(les parcelles de moins de 1&nbsp;ha et celles sorties en partie ne le sont pas), et "
                       f"{ha(r['ha_indetermines'])} ne se tranchent pas ; il dit si la parcelle reste verte, "
                       "pas si c'est de l'herbe ou une friche.")
    else:
        com_txt = "<p>La mesure commune par commune est en cours.</p>"
        inconnu_sat = "le satellite n'en a mesuré qu'un échantillon."
    v = val
    t_seul = terrain[terrain.test == "terrain seul"].rapport_meme_commune.iloc[0]
    t_n2000 = terrain[terrain.comparaison.str.contains("Natura")].rapport_meme_commune.iloc[0]
    t_zh = terrain[terrain.comparaison.str.contains("zones humides")].rapport_meme_commune.iloc[0]
    b_avant = bcae2[~bcae2.regle_en_vigueur].taux_dedans.mean()
    b_dehors = bcae2[~bcae2.regle_en_vigueur].taux_dehors.mean()
    occ = sat.get("occupation_vertes_2023", {})
    ph = sat.get("photos", {})
    herbe = ""
    if occ:
        herbe = (f"<p><b>Herbe ou friche ?</b> Selon la carte d'occupation du sol 2023 d'Impact Observatory, "
                 f"les {s23['couvert']} prairies sorties restées vertes sont : "
                 + ", ".join(f"{nb(n)} {k}" for k, n in occ.items())
                 + (" ; aucune n'est boisée." if "arbres" not in occ else "."))
        if ph:
            herbe += (f" Les {nb(sum(ph.values()))} cas douteux, regardés sur la photo aérienne de l'IGN, sont "
                      "des prés (pâtures, prés-vergers, prés à chevaux), dont un en partie corps de ferme "
                      "(lecture faite par l'assistant IA, à confirmer par l'équipe).")
        herbe += "</p>"
    planche = ""
    if figs.get("fig_photos"):
        planche = (f'<figure><img src="{figs["fig_photos"]}" style="width:96%"><figcaption>Cas douteux '
                   "regardés sur la photo aérienne de l'IGN (contour de la parcelle en rouge).</figcaption>"
                   "</figure>")
    cout = ""
    if sobriete is not None and len(sobriete):
        der = sobriete.groupby("commande").last()
        duree = lambda x: f"{nb(x)} s" if x < 120 else f"{nb(x / 60)} min"
        morceaux = [f"« {c} » {duree(der.loc[c, 'duree_s'])}" for c in ("calculer", "evaluer")
                    if c in der.index]
        cout = (f"Le moteur trace son propre coût (<code>sorties/sobriete.csv</code>) : "
                f"{', '.join(morceaux)}, pour {nb(der.data_mo.iloc[-1] / 1024, 1)} Go de données.")
    html = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<title>Prairimètre : les prairies permanentes de Normandie</title>
<style>
@page {{ size: A4; margin: 16mm 15mm 16mm 15mm; }}
body {{ font-family: "Segoe UI", system-ui, sans-serif; color: #222; font-size: 10.2pt; line-height: 1.45; }}
h1 {{ font-size: 23pt; margin: 0 0 4px; color: #1f4d2e; }}
h2 {{ font-size: 14pt; color: #1f4d2e; border-bottom: 2px solid #cfe3cf; padding-bottom: 3px; margin-top: 22px;
      page-break-after: avoid; }}
h3 {{ font-size: 11pt; margin: 14px 0 4px; page-break-after: avoid; }}
.sous {{ color: #555; font-size: 11pt; margin-bottom: 14px; }}
.cases {{ display: flex; gap: 8px; margin: 12px 0; }}
.case {{ flex: 1; border: 1px solid #d8d6cc; border-radius: 8px; padding: 8px 10px; background: #fafaf7; }}
.case .v {{ font-size: 16pt; font-weight: 700; }}
.case .l {{ font-size: 8.5pt; color: #555; }}
.objectif {{ background: #eef5ee; border-left: 4px solid #2e7d4f; padding: 8px 12px; margin: 10px 0; }}
.limite {{ background: #fbf3e6; border-left: 4px solid #f0a202; padding: 8px 12px; margin: 10px 0; }}
figure {{ margin: 8px 0 12px; text-align: center; page-break-inside: avoid; }}
figure img {{ max-width: 100%; }}
figcaption {{ font-size: 8.5pt; color: #555; margin-top: 2px; }}
.deux {{ display: flex; gap: 12px; align-items: flex-start; }} .deux > * {{ flex: 1; }}
table {{ border-collapse: collapse; width: 100%; font-size: 9pt; margin: 6px 0; }}
td, th {{ border-bottom: 1px solid #e3e1d8; padding: 3px 6px; text-align: left; }}
th {{ background: #f3f2ec; }} td.n {{ text-align: right; white-space: nowrap; }}
.saut {{ page-break-before: always; }}
.src {{ font-size: 8.5pt; }} a {{ color: #2a5d9f; text-decoration: none; }}
</style></head><body>

<h1>Prairimètre</h1>
<div class="sous">Les prairies permanentes de Normandie : combien on en perd vraiment, pourquoi, ce qui les
retient et où agir. Datathon Normandie 2026, Hippolyte Perraud (INSA Rouen) et Mouhssine Bairoune
(ENSI Caen).</div>

<div class="objectif"><b>L'objectif régional</b> ({o['texte']}) : « {o['objectif']} ». « {o['periode']} »,
avec pour cible « {o['cible']} ».</div>

<div class="cases">
<div class="case"><div class="v">{ha(sth_ecart, True)}</div><div class="l">mesure officielle (statistique
agricole), {a_ref}→{sth_fin} : {nb(100 * part.loc[sth_fin], 1)} % de la SAU</div></div>
<div class="case"><div class="v">{ha(ecart, True)}</div><div class="l">registre PAC, {a_ref}→{an}</div></div>
<div class="case"><div class="v">{s23['couvert']} sur {s23['tranchees']}</div><div class="l">prairies sorties de la
PAC en 2023 encore vertes en {an} (satellite)</div></div>
<div class="case"><div class="v">≈ {nb(1 / rapports.mean(), 0)} fois moins</div><div class="l">de retournement
là où une règle encadre le labour</div></div>
</div>

<h2>1. La problématique normande</h2>
<p>La Normandie est une terre d'herbe : ses prairies permanentes nourrissent l'élevage, retiennent l'eau et le
carbone, abritent la biodiversité du bocage. La Région s'est fixé <b>zéro perte nette de prairies permanentes
en {a_obj}</b>. Trois questions se posent : <b>combien perd-on vraiment</b>, <b>les règles retiennent-elles
les prairies</b> (l'interaction entre l'homme et la nature, sujet 2 du datathon), et <b>où agir</b> ?</p>
<p>Deux sources comptent les prairies, et elles ne disent pas la même chose. Le registre parcellaire de la PAC
(RPG, publié chaque année, parcelle par parcelle) perd {ha(-ecart)} depuis {a_ref}. La statistique agricole
(Agreste), qui mesure l'objectif officiel, n'en perd que {ha(-sth_ecart)} jusqu'en {sth_fin} (chiffre
provisoire). Comprendre cet écart est la première clé ; le Prairimètre l'explique et le vérifie par satellite.</p>
<p><b>L'objectif n'est pas tenu.</b> Mesurée dans les séries d'Agreste, la part de l'herbe dans la surface
agricole recule de {nb(100 * part.loc[a_ref], 1)} % en {a_ref} à {nb(100 * part.loc[sth_fin], 1)} % en {sth_fin}.
La cible de {o['part_sau_pct']} % avait été fixée sur les chiffres {o.get('annee_cible', 2019)} publiés en 2020 ;
Agreste a depuis révisé ses séries pour les mettre en cohérence avec le recensement agricole 2020, et
{o.get('annee_cible', 2019)} y vaut {nb(100 * part.loc[o.get('annee_cible', 2019)], 1)} %. Il faut donc comparer
les années dans la même série, ce que fait le Prairimètre.</p>
<figure><img src="{figs['fig_sources']}" style="width:78%"><figcaption>Les prairies permanentes selon les deux
sources. 1 et 2 : les deux années à part, expliquées ci-dessous.</figcaption></figure>

<h2>2. Combien perd-on vraiment ?</h2>
<p>Le registre est comparé à lui-même, parcelle par parcelle, d'une année sur l'autre. Entre {a0} et {an}, le
solde est de <b>{ha(solde, True)}</b>, à {ha(abs(solde - OFFICIEL['perte_ha']))} du chiffre officiel de la
PAC ({ha(OFFICIEL['perte_ha'], True)}, {OFFICIEL['source']}). Les prairies disparaissent de deux façons :
<b>{ha(retournees)} retournées en culture</b>, une perte certaine, et <b>{ha(sorties)} sorties de la
déclaration</b>, dont le registre ne dit rien.</p>
<figure><img src="{figs['fig_flux']}" style="width:78%"><figcaption>Ce qui entre et sort du registre chaque année.
Trait noir : le solde.</figcaption></figure>

<h3>2022→2023 : des exploitants âgés sortent de la PAC</h3>
<p>{ha(r23.sortie_non_declare)} de prairies sortent de la déclaration en un an, {nb(r23.sortie_non_declare / ordinaire_sorties, 1)}
fois une année ordinaire, à {nb(100 * r23.entieres_ha / r23.sortis_ha, 0)} ha sur 100 en parcelles entières.
C'est l'effet de la nouvelle PAC, qui réserve les aides aux « agriculteurs actifs » : après 67 ans, un
exploitant qui touche sa retraite n'y a plus droit. La DRAAF compte {nb(aa['sortants'])} exploitations sorties
(−{aa['baisse_declarants_pct']} % de déclarants), dont près de {aa['part_67_ans_pct']} sur 100 ont un chef de
67 ans ou plus, et plus de {nb(aa['prairies_sorties_ha'])} ha de prairies permanentes sorties
(<a href="{aa['lien']}">{aa['texte']}</a>). Le Prairimètre retrouve ces chiffres département par département.
La même année, la statistique agricole voit les prairies augmenter ({ha(saa_2023, True)}).</p>
<div class="deux"><figure><img src="{figs['fig_draaf']}"><figcaption>Prairies sorties en 2023 par département :
la DRAAF et le Prairimètre.</figcaption></figure>
<div><p><b>Vu du satellite.</b> Sur {s23['parcelles']} de ces prairies tirées au hasard, {s23['tranchees']} ont
pu être tranchées : <b>les {s23['couvert']} restent vertes toute l'année {an}, sans labour</b> (au moins
{nb(100 * s23['bas'], 0)} sur 100 avec une confiance de 95 %). Ces sorties sont surtout administratives.</p>
<p>Corrigé par le satellite, le registre ne perd plus {ha(-ecart)} mais <b>entre {ha(-mieux)} et {ha(-pire)}</b>
depuis {a_ref}, plus proche de la statistique agricole.</p></div></div>

<h3>2018→2019 : la fin du régime d'autorisation</h3>
<p>{ha(r19.sortie_culture)} retournés en culture, {nb(r19.sortie_culture / ordinaire_ret, 1)} fois une année
ordinaire, l'année où retourner une prairie ne demande plus d'autorisation en Normandie
(<a href="{FIN_AUTORISATION_2019['lien']}">{FIN_AUTORISATION_2019['texte']}</a>) : un lien très probable, pas
démontré. La statistique agricole voit elle aussi une baisse cette année-là ({ha(saa_2019, True)}) : la perte
est réelle. La même année, {nb(100 * r19.redeclares_ha / r19.sortis_ha, 0)} ha sur 100 des surfaces sorties de la
déclaration y reviennent ensuite, contre {nb(100 * ordinaire_retour, 0)} d'habitude : le registre publié en 2019
était incomplet, surtout dans l'Orne et la Seine-Maritime, et les prairies reviennent intactes en 2020. C'est
un manque du fichier publié, pas un changement dans les champs. Explication probable, non confirmée par un
document : le registre publié est l'état connu au 1er janvier suivant (IGN), sans les dossiers pas encore
instruits. La comparaison directe {a0}→{an} n'en dépend pas.</p>

<h3>L'alerte officielle ne sonne pas</h3>
<p>Le ratio de la PAC compare la part des prairies dans la surface agricole à {REFERENCE_RATIO}.
{' '.join(f"En {r['annee']}, il recule de {nb(-r['evolution_pct'], 2)} % (référence {nb(r['reference_pct'], 2)} %) : {r['consequence']} (<a href='{r['lien']}'>{r['texte']}</a>)." for r in RATIOS)}
En {OFFICIEL['date']}, le recul n'est plus que de {nb(-OFFICIEL['ratio_evol_pct'], 2)} %. La référence a été
recalculée : l'alarme s'est tue alors que les prairies continuent de reculer. L'objectif se suit donc en
hectares, avec la statistique agricole, et le Prairimètre dit où.</p>

<h2 class="saut">3. Les règles retiennent-elles les prairies ?</h2>
<p>On compare, dans une même commune, les prairies couvertes par une règle qui encadre le labour (prairies
sensibles BCAE 9, zones humides BCAE 2, programme nitrates) et les autres. <b>Là où une règle s'applique, on
retourne environ {nb(1 / rapports.mean(), 0)} fois moins</b> (de {nb(1 / rapports.max(), 1)} à
{nb(1 / rapports.min(), 1)} fois selon la période). Mais ces règles ne couvrent que
<b>{nb(100 * regle.part_des_prairies, 0)} ha de prairies sur 100</b>, et <b>{nb(100 * hors.part_du_retournement, 0)}
ha de retournement sur 100</b> se font hors de tout zonage. Au-dessus des captages d'eau potable, où aucune
règle nationale ne s'applique, on retourne autant qu'à côté (rapport de {nb(aac.min(), 2)} à {nb(aac.max(), 2)}).</p>
<div class="deux"><figure><img src="{figs['fig_regles']}"><figcaption>Retournement selon le zonage.</figcaption></figure>
<div><p><b>La règle agit-elle par elle-même, ou parce qu'elle porte sur des terrains peu labourés ?</b>
Les deux. Sans aucune règle, les prairies d'inventaire (ZNIEFF, zones humides) sont déjà
{nb(1 / t_seul, 1)} fois moins retournées : le terrain compte. Mais <b>à terrain égal, l'interdiction de
retourner agit en plus</b> : dans les sites Natura 2000, les prairies sensibles (BCAE 9) sont
{nb(1 / t_n2000, 0)} fois moins retournées que les autres prairies du site ; dans les zones humides,
{nb(1 / t_zh, 0)} fois moins.</p>
<p>La BCAE 2 (zones humides, depuis 2025, un labour au plus en 4 ans) porte sur des prairies déjà très peu
retournées avant ({nb(1000 * b_avant, 1)} pour mille par an, contre {nb(1000 * b_dehors, 0)} ailleurs) : pas
d'effet visible la première année. Le projet n'a aucune donnée sur les paiements.</p></div></div>

<h2>4. Où agir ?</h2>
<p>Le retournement est concentré : <b>{len(liste211)} communes portent la moitié du retournement récent</b>
({an - 3}→{an}). C'est la liste courte où étendre ce qui marche.</p>
<figure><img src="{figs['fig_carte_retournement']}" style="width:86%"><figcaption>Prairies retournées en culture par
commune, {an - 3}→{an}. Contour noir : les {len(liste211)} communes qui portent la moitié du retournement.</figcaption></figure>
<p>Les sorties de la déclaration se concentrent aussi : {len(moitie)} communes en portent la moitié. La question
pour elles : l'herbe est-elle encore là ? Le satellite y répond.</p>
{com_txt}
<figure><img src="{figs['fig_carte_aller_voir']}" style="width:86%"><figcaption>Ce que le satellite voit des
prairies sorties de la déclaration, commune par commune.</figcaption></figure>
<p>Enfin, {len(gain)} communes gagnent des prairies sur d'anciennes cultures ({ha(gain.sum())}) et {len(sans_perte)}
n'en ont perdu aucune : des exemples à faire connaître.</p>
<figure><img src="{figs['fig_carte_exemples']}" style="width:70%"><figcaption>Les communes exemples.</figcaption></figure>

<h2 class="saut">5. La vision satellite</h2>
<p><b>Données ouvertes, sans compte.</b> Les images Sentinel-2 (programme Copernicus de l'Union européenne, 10 m,
une image tous les 5 jours) sont lues sur le contour de chaque parcelle grâce au catalogue public de Microsoft
Planetary Computer. Pour chaque image sans nuage de {an}, on mesure le NDVI, un indice de végétation : une
prairie reste verte toute l'année, une parcelle labourée passe par le sol nu.</p>
<figure><img src="{figs['fig_ndvi']}" style="width:78%"><figcaption>NDVI au fil de l'année {an} : une prairie
déclarée, une parcelle mise en culture, une prairie sortie de la PAC en 2023.</figcaption></figure>
<p><b>Une règle testée honnêtement.</b> Une première règle, fixée à l'avance, a échoué : elle voyait labourées
11 prairies sur 20 encore déclarées, piégée par des images isolées. Corrigée sur 40 parcelles dont le registre
donne la réponse, la règle a été <b>validée sur 40 autres, jamais regardées : {sat['erreurs_validation']} erreurs
sur {sat['tranchees_validation']}</b> parcelles tranchées ({v['prairie_indet'] + v['culture_indet']} indéterminées).</p>
<figure><img src="{figs['fig_carte_echantillon']}" style="width:80%"><figcaption>Les prairies sorties tirées au
hasard et vérifiées par satellite.</figcaption></figure>
{herbe}
{planche}
<div class="limite"><b>Limites.</b> Une seule année d'images ; parcelles d'au moins 1 ha ; la carte
d'occupation du sol range les prairies entretenues avec les cultures (testé sur les témoins), d'où le recours
au satellite et à la photo aérienne. Preuves complètes : <code>verification/sentinel2/preuves.md</code>.</div>

<h2>6. Impacts, numérique responsable, changement d'échelle</h2>
<p><b>Pour qui.</b> La Région suit son objectif avec la bonne mesure et sait pourquoi le registre PAC
exagère la perte. La chambre d'agriculture, les DDT(M) et les intercommunalités disposent d'une liste
courte de {len(liste211)} communes où le retournement se concentre, et de {len(gain)} communes exemples à faire
connaître. Les agents qui allaient vérifier sur le terrain savent où le satellite a déjà répondu.</p>
<p><b>Numérique responsable.</b> Uniquement des données ouvertes, sans compte. L'application tourne en local,
sans serveur. Les calculs lourds se font une fois par an, au nouveau registre, puis sont mis en cache. Pour le
satellite, seules les statistiques de chaque parcelle transitent, pas les images elles-mêmes (des
gigaoctets) : c'est le service public de catalogue qui calcule ; toutes les mesures des
{nb(len(sat_t))} parcelles de l'échantillon tiennent dans {nb(images_ko)} ko. {cout}</p>
<p><b>Changement d'échelle.</b> Le moteur ne dépend de la Normandie que par trois réglages (code de la région
dans les archives IGN, départements, emprise) et par les textes officiels cités. Le même code peut suivre
n'importe quelle région française, chaque année, dès la publication du registre.</p>

<h2>7. Ce qu'on ne sait pas</h2>
<ul>
<li>Ce que donneraient les chiffres de 2019 dans l'ancienne version des séries d'Agreste, sur laquelle la
cible de {o['part_sau_pct']} % a été fixée : seules les séries révisées sont publiées.</li>
<li>L'état de toutes les prairies sorties : {inconnu_sat}</li>
<li>La cause écrite du trou du registre 2019 (l'explication par l'état au 1er janvier reste à confirmer).</li>
<li>L'effet des paiements (mesures agro-environnementales) : aucune donnée dans le projet.</li>
</ul>

<h2>8. Données et méthode</h2>
<p>Toutes les données sont ouvertes : registre parcellaire graphique 2018-{an} (IGN / ASP), statistique agricole
annuelle (Agreste), zonages (DREAL Normandie, MNHN / PatriNat, MASA, Géoportail de l'urbanisme, Sandre),
OCS GE (IGN), images Sentinel-2 (Copernicus). Une seule méthode : les prairies déclarées une année sont
croisées, parcelle par parcelle, avec les déclarations suivantes. Le moteur se recalcule seul à chaque nouveau
registre (<code>python -m prairimetre mettre-a-jour</code>) ; les tirages au hasard sont reproductibles et
chaque mesure satellite est tracée. Code et application : branche <code>test-app-v1</code>.</p>
<p class="src">Textes officiels : <a href="{o['lien']}">{o['texte']}</a> ;
{' ; '.join(f"<a href='{r['lien']}'>{r['texte']}</a>" for r in RATIOS)} ;
<a href="{aa['lien']}">{aa['texte']}</a> ; <a href="{FIN_AUTORISATION_2019['lien']}">{FIN_AUTORISATION_2019['texte']}</a> ;
chiffre officiel : {OFFICIEL['source']}.</p>
</body></html>"""
    SORTIE.mkdir(parents=True, exist_ok=True)
    f = SORTIE / "rapport_prairimetre.html"
    f.write_text(html, encoding="utf-8")
    return f


def pdf(html):
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    sortie = html.with_suffix(".pdf")
    subprocess.run([str(edge), "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={sortie}", html.as_uri()], check=True, timeout=180)
    return sortie


if __name__ == "__main__":
    h = rapport()
    print(h)
    print(pdf(h))
