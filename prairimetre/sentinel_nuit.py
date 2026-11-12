"""Le calcul satellite SANS réseau, sur les images rapatriées par sentinel_hors_ligne.telecharger.

Deux groupes de géométries, mesurés image par image avec la même règle que sentinel.py (classer) :
- les témoins : les prairies déjà mesurées par le service en ligne (bloc de sentinel.py). La mesure
  hors ligne doit redonner leurs états : c'est la preuve que les deux calculs sont les mêmes ;
- les cibles : l'herbe de la carte IGN (OCS GE : couvert herbacé, usage agricole ou sans usage) qui
  n'est pas déclarée à la PAC l'année des images.

    python -m prairimetre.sentinel_nuit 2025
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import geopandas as gpd
import shapely
import numpy as np
import pandas as pd
from shapely.geometry import shape

from .donnees import DATA
from .sentinel_hors_ligne import DOSSIER, TUILES, catalogue, fichiers


def cibles(annee=2025):
    """L'herbe de la carte IGN qui n'est PAS déclarée à la PAC l'année donnée : chaque polygone d'herbe
    (CS2.2.1, usage US1.1 agricole ou US6.3 sans usage) moins les parcelles du registre de l'année,
    sans les bandes de moins de 20 m (bords de parcelles) ni les morceaux de moins de 0,1 ha.
    Colonnes : dep, usage, ha, part_deja_declaree (part du morceau déclarée au moins une fois de 2018 à
    l'année d'avant : 0 = jamais vue à la PAC)."""
    import shapely
    from .donnees import ocsge, rpg
    f = DOSSIER / f"cibles_{annee}.parquet"
    if f.exists():
        return gpd.read_parquet(f)
    millesimes = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))["ocsge"]["millesimes"]
    r = rpg(annee).geometry.values
    arbre = shapely.STRtree(r)
    avant = np.concatenate([rpg(a).geometry.values for a in range(2018, annee)])
    arbre_avant = shapely.STRtree(avant)

    def moins(geo, autres, a):
        ih, ir = a.query(geo, predicate="intersects")
        reste = np.array(geo, dtype=object)
        for i, g in pd.DataFrame({"ih": ih, "ir": ir}).groupby("ih"):
            try:
                reste[i] = shapely.difference(geo[i], shapely.union_all(autres[g.ir.values]))
            except shapely.errors.GEOSException:
                reste[i] = shapely.difference(shapely.make_valid(geo[i]), shapely.union_all(
                    shapely.make_valid(autres[g.ir.values]), grid_size=0.01), grid_size=0.01)
        return shapely.make_valid(reste)

    morceaux = []
    for dep, ms in sorted(millesimes.items()):
        o = ocsge(dep, max(int(x) for x in ms))
        for us in ("US1.1", "US6.3"):
            h = o[(o.code_cs == "CS2.2.1") & (o.code_us == us)].geometry.values
            ouv = shapely.buffer(shapely.buffer(moins(h, r, arbre), -10), 10)
            parts = shapely.get_parts(ouv)
            parts = parts[shapely.area(parts) / 1e4 >= 0.1]
            ha = shapely.area(parts) / 1e4
            jamais = shapely.area(moins(parts, avant, arbre_avant)) / 1e4
            morceaux.append(gpd.GeoDataFrame({"dep": dep, "usage": us, "ha": ha,
                                              "part_deja_declaree": np.clip(1 - jamais / ha, 0, 1)},
                                             geometry=parts, crs=o.crs))
            print(dep, us, len(parts), "morceaux", round(ha.sum()), "ha", flush=True)
    out = gpd.GeoDataFrame(pd.concat(morceaux, ignore_index=True), crs=morceaux[0].crs)
    f.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(f)
    return out


def temoins(annee=2025):
    """Les prairies déjà mesurées par le service en ligne, avec la même géométrie (parcelle entière,
    ou seulement la part sortie)."""
    from .donnees import prairies
    from .sentinel import _part_sortie, mesures, parcelles_cibles, periode
    a0, _ = periode()
    m = mesures(annee)
    c = parcelles_cibles()
    p = prairies(a0).loc[c.index].assign(entiere=c.entiere.values)
    p = p[p.id_parcel.astype(str).isin(set(m.id_rpg.astype(str)))]
    geo = np.array(p.geometry.values, dtype=object)
    partiel = ~p.entiere.values
    if partiel.any():
        geo[partiel] = _part_sortie(p[partiel], annee)
    return gpd.GeoDataFrame({"id_rpg": p.id_parcel.astype(str).values}, geometry=list(geo), crs=p.crs)


def _grille(chemins, pas):
    """Grille commune (transformation, largeur, hauteur) des fichiers d'une tuile."""
    import rasterio
    tr = []
    for f in chemins:
        with rasterio.open(f) as s:
            if s.crs is not None:
                tr.append((s.transform, s.width, s.height))
    x0, y0 = min(t.c for t, _, _ in tr), max(t.f for t, _, _ in tr)
    larg = max(round((t.c - x0) / pas) + w for t, w, _ in tr)
    haut = max(round((y0 - t.f) / pas) + h for t, _, h in tr)
    return rasterio.Affine(pas, 0, x0, 0, -pas, y0), larg, haut


def mesurer(groupes, annee=2025):
    """groupes : {nom: GeoDataFrame}. Pour chaque géométrie et chaque image : part de nuages (SCL,
    20 m) et NDVI moyen (10 m), comme sentinel.mesurer. Chaque image n'est lue qu'une fois pour tous
    les groupes. Une ligne par (géométrie, date) où l'image est sans nuage sur la géométrie ; si deux
    tuiles voient la même date, on garde la première de TUILES. Pixels comptés par leur centre."""
    import rasterio
    from rasterio.features import rasterize
    from .sentinel import PROPRE_MAX, SCL_SALE
    items = [i for i in catalogue(annee)
             if i["tuile"] in TUILES and all(f.exists() for f in fichiers(i, annee))]
    lut = np.zeros(256, np.float64)
    lut[list(SCL_SALE)] = 1
    lignes = {nom: [] for nom in groupes}
    for rang, tuile in enumerate(TUILES):
        its = [i for i in items if i["tuile"] == tuile and _a_donnees(fichiers(i, annee)[0])]
        if not its:
            continue
        t0 = time.time()
        epsg = its[0]["epsg"]
        emprise = gpd.GeoSeries([shape(i["geometrie"]) for i in its], crs=4326).to_crs(epsg).union_all()
        tr10, w10, h10 = _grille([fichiers(i, annee)[0] for i in its], 10)
        tr20, w20, h20 = _grille([fichiers(i, annee)[1] for i in its], 20)
        labs = {}
        for nom, geos in groupes.items():
            g = geos.to_crs(epsg)
            dedans = g.intersects(emprise).values
            formes = list(zip(g.geometry.values[dedans], (np.flatnonzero(dedans) + 1).tolist()))
            if formes:
                labs[nom] = (rasterize(formes, out_shape=(h10, w10), transform=tr10, dtype="int32"),
                             rasterize(formes, out_shape=(h20, w20), transform=tr20, dtype="int32"),
                             len(geos) + 1, len(formes))
        for i in its:
            f_ndvi, f_scl = fichiers(i, annee)
            with rasterio.open(f_scl) as s:
                scl, t20 = s.read(1).ravel(), s.transform
                f20 = (s.height, s.width)
            with rasterio.open(f_ndvi) as s:
                q, t10 = s.read(1).ravel(), s.transform
                f10 = (s.height, s.width)
            c20, l20 = round((t20.c - tr20.c) / 20), round((tr20.f - t20.f) / 20)
            c10, l10 = round((t10.c - tr10.c) / 10), round((tr10.f - t10.f) / 10)
            for nom, (lab10, lab20, n, _) in labs.items():
                lab = lab20[l20:l20 + f20[0], c20:c20 + f20[1]].ravel()
                u = np.flatnonzero(lab)               # seulement les pixels d'une géométrie (mémoire)
                total = np.bincount(lab[u], minlength=n)
                sale = np.bincount(lab[u], weights=lut[scl[u]], minlength=n)
                part_sale = np.where(total > 0, sale / np.maximum(total, 1), 1.0)
                lab = lab10[l10:l10 + f10[0], c10:c10 + f10[1]].ravel()
                u = np.flatnonzero(lab)
                u = u[q[u] != 255]
                somme = np.bincount(lab[u], weights=q[u] / 100.0 - 1, minlength=n)
                nb = np.bincount(lab[u], minlength=n)
                garde = np.flatnonzero((part_sale < PROPRE_MAX) & (nb > 0))
                garde = garde[garde > 0]
                lignes[nom].append(pd.DataFrame({"k": garde - 1, "date": i["date"], "rang": rang,
                                                 "ndvi": somme[garde] / nb[garde],
                                                 "part_sale": part_sale[garde]}))
        print(f"tuile {tuile} : {len(its)} images, " + ", ".join(f"{nom} {v[3]}" for nom, v in labs.items())
              + f", {time.time() - t0:.0f} s", flush=True)
        del labs
    out = {}
    for nom, l in lignes.items():
        if not l:
            l = [pd.DataFrame(columns=["k", "date", "rang", "ndvi", "part_sale"])]
        m = pd.concat(l, ignore_index=True).sort_values(["k", "date", "rang"]).drop_duplicates(["k", "date"])
        m.to_parquet(DOSSIER / str(annee) / f"mesures_{nom}.parquet")
        out[nom] = m
    return out


def _a_donnees(f):
    import rasterio
    with rasterio.open(f) as s:
        return s.crs is not None


def etats(geos, m):
    """État de chaque géométrie d'après ses images sans nuage (sentinel.classer)."""
    from .sentinel import classer
    e, r = {}, {}
    for k, p in m.groupby("k"):
        e[k], r[k] = classer(p.reset_index(drop=True))
    idx = range(len(geos))
    return pd.DataFrame({"etat": pd.Series(e).reindex(idx).fillna("indéterminé").values,
                         "raison": pd.Series(r).reindex(idx).fillna("0 image sans nuage").values},
                        index=geos.index)


def nuit(annee=2025):
    """Tout le calcul sans réseau ; résultats et bilan dans DOSSIER/annee/."""
    from .sentinel import mesures as en_ligne
    journal = DOSSIER / str(annee) / "bilan.txt"

    def note(t):
        print(t, flush=True)
        with open(journal, "a", encoding="utf-8") as j:
            j.write(time.strftime("%H:%M:%S ") + t + "\n")

    tm, c = temoins(annee), cibles(annee)
    note(f"Calcul : {len(tm)} témoins et {len(c)} morceaux d'herbe hors PAC")
    m = mesurer({"temoins": tm, "cibles": c}, annee)
    e_t = etats(tm, m["temoins"])
    ref = en_ligne(annee)
    ref = ref.assign(id_rpg=ref.id_rpg.astype(str)).set_index("id_rpg").etat
    comp = pd.DataFrame({"id_rpg": tm.id_rpg.values, "hors_ligne": e_t.etat.values,
                         "en_ligne": ref.reindex(tm.id_rpg.values).values})
    comp.to_csv(DOSSIER / str(annee) / "etats_temoins.csv", index=False)
    note(f"Témoins : {len(comp)} prairies mesurées en ligne ; même état hors ligne pour "
         f"{100 * (comp.hors_ligne == comp.en_ligne).mean():.1f} %")
    note(pd.crosstab(comp.en_ligne, comp.hors_ligne).to_string())
    e = etats(c, m["cibles"])
    out = pd.DataFrame(c.drop(columns="geometry")).join(e)
    out.to_parquet(DOSSIER / str(annee) / "etats_cibles.parquet")
    note(f"Herbe IGN hors registre PAC {annee}, par état (ha) :")
    note(out.pivot_table(index="etat", columns="dep", values="ha", aggfunc="sum").round().to_string())
    out["jamais_pac"] = out.part_deja_declaree < 0.5
    note(out.pivot_table(index=["jamais_pac", "etat"], columns="usage", values="ha",
                         aggfunc="sum").round().to_string())
    note("FINI")


# --- Étalonnage de la zone grise ------------------------------------------------------------------
# La règle laisse « indéterminé » un morceau dont le signal est entre l'herbe et le labour. Pour savoir
# quelle part de ces hectares est de l'herbe, on mesure avec la même règle des parcelles dont on connaît
# la réponse : de l'herbe sûre (déclarée prairie permanente l'année et l'année d'avant) et des cultures
# sûres (céréales, maïs, oléagineux, protéagineux, plantes à fibres, légumineuses à grains, cultures
# industrielles, légumes). Mêmes tailles que les morceaux d'herbe hors PAC, même ouverture de 10 m.
CULTURES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 15, 24, 25]   # code_group du registre
CLASSES_HA = [0.1, 0.25, 0.5, 1, 5, np.inf]
PAR_CLASSE = 3000
GRAINE_ETALONS = 2029


def etalons(annee=2025):
    """PAR_CLASSE parcelles d'herbe sûre et autant de cultures sûres par classe de taille (CLASSES_HA,
    surface après ouverture de 10 m). Colonnes : nature (herbe / culture), classe, ha."""
    import shapely
    from .donnees import rpg
    f = DOSSIER / f"etalons_{annee}.parquet"
    if f.exists():
        return gpd.read_parquet(f)
    r, r1 = rpg(annee), rpg(annee - 1)
    hasard = np.random.default_rng(GRAINE_ETALONS)
    out = []
    for nature, groupes in (("herbe", [18]), ("culture", CULTURES)):
        g = r[r.code_group.isin(groupes)]
        ouv = shapely.buffer(shapely.buffer(g.geometry.values, -10), 10)
        ha = shapely.area(ouv) / 1e4
        classe = pd.cut(ha, CLASSES_HA, right=False, labels=False)
        avant = r1[r1.code_group.isin(groupes)].geometry.values
        arbre = shapely.STRtree(avant)
        for c in range(len(CLASSES_HA) - 1):
            idx = np.flatnonzero(classe == c)
            idx = hasard.permutation(idx)[:3 * PAR_CLASSE]
            if nature == "herbe":   # prairie permanente aussi l'année d'avant, sur au moins 90 % du morceau
                il, ir = arbre.query(ouv[idx], predicate="intersects")
                couvert = np.zeros(len(idx))
                for i, grp in pd.Series(ir).groupby(il):
                    couvert[i] = shapely.area(shapely.intersection(
                        ouv[idx[i]], shapely.union_all(avant[grp.values]))) / 1e4
                idx = idx[couvert >= 0.9 * ha[idx]]
            idx = idx[:PAR_CLASSE]
            out.append(gpd.GeoDataFrame({"nature": nature, "classe": c, "ha": ha[idx]},
                                        geometry=ouv[idx], crs=r.crs))
            print(nature, CLASSES_HA[c], len(idx), flush=True)
    out = gpd.GeoDataFrame(pd.concat(out, ignore_index=True), crs=r.crs)
    out.to_parquet(f)
    return out


def etalonner(annee=2025):
    """Mesure les étalons (sans réseau) ; leurs états vont dans DOSSIER/annee/etats_etalons.parquet."""
    e = etalons(annee)
    m = mesurer({"etalons": e}, annee)["etalons"]
    out = pd.DataFrame(e.drop(columns="geometry")).join(etats(e, m))
    out.to_parquet(DOSSIER / str(annee) / "etats_etalons.parquet")
    return out


def _taux(d, etat, k):
    """Part de la surface classée `etat`, par classe de taille (tableau de k valeurs)."""
    t = d.ha.where(d.etat == etat, 0).groupby(d.classe).sum() / d.groupby("classe").ha.sum()
    return t.reindex(range(k)).values


def _herbe(e, c, k):
    """Herbe estimée dans les morceaux c, classe de taille par classe de taille : le couvert permanent
    observé, moins ce qu'y mettraient des cultures, divisé par la part de l'herbe sûre que la règle
    classe en couvert permanent. couvert = h·tH·A + (1 − h)·tC·A  ⇒  herbe = (couvert − tC·A) / (tH − tC)."""
    tH = _taux(e[e.nature == "herbe"], "couvert permanent", k)
    tC = _taux(e[e.nature == "culture"], "couvert permanent", k)
    out = {}
    for nom, s in (("total", c), ("jamais", c[c.jamais]), ("deja", c[~c.jamais])):
        A = s.groupby("classe").ha.sum().reindex(range(k)).fillna(0).values
        cp = s.ha.where(s.etat == "couvert permanent", 0).groupby(s.classe).sum().reindex(range(k)).fillna(0).values
        out[nom] = float(((cp - tC * A) / (tH - tC)).sum())
    return out


def resumer(annee=2025, tirages=300):
    """Les chiffres de l'herbe hors registre PAC pour la page Objectif 2030, écrits dans
    verification/sentinel2/<annee>/herbe_hors_pac.json (versionné, lu par l'application). Intervalle à
    95 % : tirages avec remise des étalons (par nature et classe) et des morceaux (par classe)."""
    from .sentinel import DOSSIER as VERIF
    D = DOSSIER / str(annee)
    c = pd.read_parquet(D / "etats_cibles.parquet")
    e = pd.read_parquet(D / "etats_etalons.parquet")
    t = pd.read_csv(D / "etats_temoins.csv")
    k = len(CLASSES_HA) - 1
    c["classe"] = pd.cut(c.ha, CLASSES_HA, right=False, labels=False)
    c["jamais"] = c.part_deja_declaree < 0.5
    point = _herbe(e, c, k)
    hasard = np.random.default_rng(1)
    ge = [g for _, g in e.groupby(["nature", "classe"])]
    gc = [g for _, g in c.groupby("classe")]
    tt = []
    for _ in range(tirages):
        eb = pd.concat([g.iloc[hasard.integers(0, len(g), len(g))] for g in ge])
        cb = pd.concat([g.iloc[hasard.integers(0, len(g), len(g))] for g in gc])
        tt.append(_herbe(eb, cb, k))
    tt = pd.DataFrame(tt)
    tranchent = t[(t.en_ligne != "indéterminé") & (t.hors_ligne != "indéterminé")]

    def parts(d):
        return {s: round(100 * v, 1) for s, v in (d.groupby("etat").ha.sum() / d.ha.sum()).items()}

    r = {"annee": annee, "images": len([i for i in catalogue(annee) if i["tuile"] in TUILES]),
         "morceaux": len(c), "ha_etat": {s: int(round(v)) for s, v in c.groupby("etat").ha.sum().items()},
         "estimation": {n: int(round(v)) for n, v in point.items()},
         "intervalle": {n: [int(round(tt[n].quantile(0.025))), int(round(tt[n].quantile(0.975)))] for n in point},
         "tirages": tirages,
         "etalons": {n: int((e.nature == n).sum()) for n in ("herbe", "culture")},
         "etalons_pct": {n: parts(e[e.nature == n]) for n in ("herbe", "culture")},
         "temoins": len(t), "temoins_meme_etat_pct": round(100 * (t.en_ligne == t.hors_ligne).mean(), 1),
         "temoins_tranchent": len(tranchent),
         "temoins_tranchent_accord": int((tranchent.en_ligne == tranchent.hors_ligne).sum())}
    if (D / "etats_etalons_bois.parquet").exists():
        from .donnees import rpg
        r["courbe"] = courbes(annee)
        reg = rpg(annee)
        # Herbe du registre hors prairies permanentes, que la statistique agricole compte peut-être en
        # surface toujours en herbe : surfaces pastorales (SPH, SPL) et vergers (VRG, dont prés-vergers)
        r["registre_autre_herbe"] = {k: int(round(reg.surf_parc[reg.code_cultu.isin(v)].sum()))
                                     for k, v in (("pastorales", ["SPH", "SPL"]), ("vergers", ["VRG"]))}
        r["photos"] = controle_photos(annee)
        r["origines"] = resume_origines(annee)
        if r["photos"]:     # intervalle à 95 % (Wilson) de la part de prés parmi les sorties avant 2023
            from .sentinel import wilson
            x = r["photos"]["sortie avant 2023"]
            r["photos_intervalle"] = [round(100 * v) for v in wilson(x.get("prairie", 0), sum(x.values()))]
        r["agreste"] = series_agreste(annee)
        u = herbe_autres_usages()
        r["herbe_ign_usages"] = {us: int(u.loc[us, "Normandie"]) for us in u.index}
    f = VERIF / str(annee) / "herbe_hors_pac.json"
    f.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    return r


# --- Classement par la courbe NDVI de l'année ------------------------------------------------------
# La règle à seuils prend une partie des bois, landes et roseaux pour de l'herbe (étalons « bois » :
# 13 % classés couvert permanent) et laisse un quart de l'herbe sûre en zone grise. On classe donc aussi
# chaque morceau d'après toute sa courbe NDVI de l'année, appris sur trois natures connues : l'herbe
# sûre, les cultures sûres (étalons ci-dessus) et la forêt et les broussailles de la carte IGN hors PAC.
FORETS = {"CS2.1.1.1": "bois", "CS2.1.2": "arbustes"}
GRAINE_BOIS = 2030


def etalons_bois(annee=2025):
    """Morceaux de forêt de feuillus (PAR_CLASSE par classe de taille) et de broussailles (le tiers) de
    la carte IGN, hors registre PAC de l'année, même ouverture de 10 m. Colonnes : nature, classe, ha."""
    import shapely
    from .donnees import ocsge, rpg
    f = DOSSIER / f"etalons_bois_{annee}.parquet"
    if f.exists():
        return gpd.read_parquet(f)
    mill = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))["ocsge"]["millesimes"]
    arbre = shapely.STRtree(rpg(annee).geometry.values)
    o = pd.concat([ocsge(dep, max(int(x) for x in ms)) for dep, ms in sorted(mill.items())], ignore_index=True)
    o = o[o.code_cs.isin(list(FORETS))]
    ouv = shapely.buffer(shapely.buffer(o.geometry.values, -10), 10)
    hors = ~np.isin(np.arange(len(ouv)), arbre.query(ouv, predicate="intersects")[0])
    ha = shapely.area(ouv) / 1e4
    classe = pd.cut(ha, CLASSES_HA, right=False, labels=False)
    hasard = np.random.default_rng(GRAINE_BOIS)
    out = []
    for cs, nature in FORETS.items():
        for c in range(len(CLASSES_HA) - 1):
            idx = np.flatnonzero((classe == c) & hors & (o.code_cs.values == cs))
            idx = hasard.permutation(idx)[:PAR_CLASSE if nature == "bois" else PAR_CLASSE // 3]
            out.append(gpd.GeoDataFrame({"nature": nature, "classe": c, "ha": ha[idx]}, geometry=ouv[idx], crs=o.crs))
    out = gpd.GeoDataFrame(pd.concat(out, ignore_index=True), crs=o.crs)
    out.to_parquet(f)
    return out


def etalonner_bois(annee=2025):
    """Mesure les étalons bois (sans réseau) ; leurs états vont dans DOSSIER/annee/etats_etalons_bois.parquet."""
    e = etalons_bois(annee)
    m = mesurer({"etalons_bois": e}, annee)["etalons_bois"]
    out = pd.DataFrame(e.drop(columns="geometry")).join(etats(e, m))
    out.to_parquet(DOSSIER / str(annee) / "etats_etalons_bois.parquet")
    return out


def _traits(m, n):
    """Par géométrie : NDVI médian de chaque mois, quantiles de l'année, nombre d'images basses."""
    m = m.assign(mois=m.date.str[5:7].astype(int))
    mens = m.pivot_table(index="k", columns="mois", values="ndvi", aggfunc="median").reindex(columns=range(1, 13))
    mens.columns = [f"m{c:02d}" for c in mens.columns]
    g = m.groupby("k").ndvi
    t = pd.DataFrame({"q05": g.quantile(.05), "q10": g.quantile(.1), "q25": g.quantile(.25), "q50": g.median(),
                      "q90": g.quantile(.9), "bas": m.ndvi.lt(.25).groupby(m.k).sum(),
                      "n": g.size(), "ete_min": m[m.mois.between(6, 9)].groupby("k").ndvi.min(),
                      "hiver_med": m[m.mois.isin([12, 1, 2])].groupby("k").ndvi.median()})
    return t.join(mens).reindex(range(n))


def derniere_declaration(annee=2025):
    """Pour chaque morceau d'herbe hors PAC : la dernière année (2018 à annee-1) où son point intérieur
    était dans une parcelle du registre, et le groupe de culture de cette année-là. Mis en cache."""
    from .donnees import rpg
    f = DOSSIER / str(annee) / "historique_cibles.parquet"
    if f.exists():
        return pd.read_parquet(f)
    g = cibles(annee)
    pt = gpd.GeoDataFrame(geometry=g.geometry.representative_point().values, crs=g.crs)
    ans = list(range(2018, annee))
    for a in ans:
        j = gpd.sjoin(pt, rpg(a)[["code_group", "geometry"]], how="left", predicate="within")
        pt[f"g{a}"] = j[~j.index.duplicated()].code_group.reindex(pt.index).values
    cols = [f"g{a}" for a in ans]
    vu = pt[cols].notna()
    pt["derniere"] = vu.iloc[:, ::-1].idxmax(axis=1).where(vu.any(axis=1)).str[1:]
    pt["groupe_dernier"] = [r[f"g{int(d)}"] if isinstance(d, str) else np.nan
                            for d, r in zip(pt.derniere, pt[cols].to_dict("records"))]
    out = pd.DataFrame(pt.drop(columns="geometry"))
    out.to_parquet(f)
    return out


def courbes(annee=2025):
    """Classe chaque morceau d'herbe hors PAC (herbe, culture, bois) par sa courbe NDVI, avec un
    classement appris sur les étalons (validation croisée à 5 plis). Range ensuite l'herbe reconnue par
    origine : jamais déclarée, sortie du registre depuis la PAC 2023 (dernière déclaration annee-3 ou
    après), sortie avant, année inconnue. Écrit DOSSIER/annee/cibles_bilan.parquet ; rend le résumé."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    D = DOSSIER / str(annee)
    e, b, c = (pd.read_parquet(D / f) for f in ("etats_etalons.parquet", "etats_etalons_bois.parquet",
                                                  "etats_cibles.parquet"))
    X = pd.concat([_traits(pd.read_parquet(D / "mesures_etalons.parquet"), len(e)),
                   _traits(pd.read_parquet(D / "mesures_etalons_bois.parquet"), len(b))], ignore_index=True)
    Xc = _traits(pd.read_parquet(D / "mesures_cibles.parquet"), len(c))
    E = pd.concat([e, b], ignore_index=True)
    E["nature"] = E.nature.replace({"arbustes": "bois"})
    X["ha"], Xc["ha"] = np.log(E.ha.values), np.log(c.ha.values)
    ok = (X.n.fillna(0) >= IMAGES_MIN_COURBE).values
    E, X = E[ok].reset_index(drop=True), X[ok].reset_index(drop=True)
    mod = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.06, random_state=0)
    p = cross_val_predict(mod, X, E.nature.values, cv=StratifiedKFold(5, shuffle=True, random_state=0),
                          method="predict_proba")
    noms = np.array(sorted(set(E.nature)))
    E["pred"] = noms[p.argmax(1)]
    juste = {n: round(100 * d.ha[d.pred == n].sum() / d.ha.sum(), 1) for n, d in E.groupby("nature")}
    # Ligne = vraie nature, colonne = nature prédite, en % de la surface de la ligne
    confusion = {n: {m: round(100 * d.ha[d.pred == m].sum() / d.ha.sum(), 2) for m in noms}
                 for n, d in E.groupby("nature")}
    mod.fit(X, E.nature.values)
    c["pred"] = np.where(Xc.n.fillna(0) < IMAGES_MIN_COURBE, "sans image", noms[mod.predict_proba(Xc).argmax(1)])
    h = derniere_declaration(annee)
    c["derniere"], c["groupe_dernier"] = h.derniere.values, h.groupe_dernier.values
    recente = [str(a) for a in range(annee - 3, annee)]
    c["groupe"] = np.select([c.part_deja_declaree < .5, c.derniere.isin(recente), c.derniere.notna()],
                            ["jamais", "sortie depuis 2023", "sortie avant 2023"], "inconnue")
    c.to_parquet(D / "cibles_bilan.parquet")
    hb = c[c.pred == "herbe"]
    # Composition corrigée des erreurs du classement : observé = Mᵀ · vrai (M en parts de surface)
    M = np.array([[confusion[n][m] / 100 for m in noms] for n in noms])
    obs = c[c.pred != "sans image"].groupby("pred").ha.sum().reindex(noms).fillna(0).values
    vrai = np.linalg.solve(M.T, obs)
    return {"validation_pct": juste, "confusion_pct": confusion,
            "corrige": {n: int(round(v)) for n, v in zip(noms, vrai)},
            "etalons": {n: int((E.nature == n).sum()) for n in noms},
            "ha_nature": {n: int(round(v)) for n, v in c.groupby("pred").ha.sum().items()},
            "herbe_par_etat": {n: int(round(v)) for n, v in hb.groupby("etat").ha.sum().items()},
            "herbe_par_origine": {n: int(round(v)) for n, v in hb.groupby("groupe").ha.sum().items()},
            "herbe_derniere_annee": {n: int(round(v)) for n, v in hb[hb.derniere.notna()].groupby("derniere").ha.sum().items()}}


def _union_par(idx, geos, n):
    """Union des géométries `geos` regroupées par `idx` (indices 0..n-1) ; None là où rien."""
    out = np.full(n, None, dtype=object)
    if len(idx) == 0:
        return out
    ordre = np.argsort(idx, kind="stable")
    idx, geos = idx[ordre], geos[ordre]
    debuts = np.flatnonzero(np.r_[True, idx[1:] != idx[:-1]])
    fins = np.r_[debuts[1:], len(idx)]
    seul = fins - debuts == 1
    out[idx[debuts[seul]]] = geos[debuts[seul]]
    for d, f in zip(debuts[~seul], fins[~seul]):
        try:
            out[idx[d]] = shapely.union_all(geos[d:f])
        except shapely.errors.GEOSException:
            out[idx[d]] = shapely.union_all(shapely.make_valid(geos[d:f]), grid_size=0.01)
    return out


def origines(annee=2025, k=None):
    """Origine EXACTE, en surface, de chaque morceau d'herbe hors PAC (classé herbe par sa courbe) : pour
    chaque année y de annee-1 à 2018, la surface du morceau dont la DERNIÈRE déclaration au registre est
    l'année y (dans le registre y, dans aucun registre après), et la part de celle-ci déclarée cette
    année-là en prairie permanente (groupe 18). Le reste n'a jamais été déclaré de 2018 à annee-1.
    Géométrie entière, pas un point au centre. Cache : DOSSIER/annee/origines_cibles.parquet."""
    from .donnees import rpg
    f = DOSSIER / str(annee) / "origines_cibles.parquet"
    if k is None and f.exists():
        return pd.read_parquet(f)
    c = pd.read_parquet(DOSSIER / str(annee) / "cibles_bilan.parquet")
    sel = np.flatnonzero((c.pred == "herbe").values) if k is None else np.asarray(k)
    geo = shapely.make_valid(cibles(annee).geometry.values[sel])
    n = len(geo)
    out = pd.DataFrame({"k": sel, "ha": shapely.area(geo) / 1e4})
    deja = np.full(n, None, dtype=object)            # union des registres des années déjà vues (après y)
    for y in range(annee - 1, 2017, -1):
        r = rpg(y)
        rg, pp = shapely.make_valid(r.geometry.values), (r.code_group.values == 18)
        il, ir = shapely.STRtree(rg).query(geo, predicate="intersects")
        dedans = _union_par(il, rg[ir], n)
        dedans_pp = _union_par(il[pp[ir]], rg[ir[pp[ir]]], n)
        m = np.array([g is not None for g in dedans])
        mp = np.array([g is not None for g in dedans_pp])
        avant = np.array([g is not None for g in deja])

        def morceau(z, msk):
            """morceau ∩ z, moins ce qui est déjà dans un registre plus récent."""
            a = np.zeros(n)
            i = np.flatnonzero(msk)
            try:
                x = shapely.intersection(geo[i], z[i])
            except shapely.errors.GEOSException:
                x = shapely.intersection(geo[i], shapely.make_valid(z[i]), grid_size=0.01)
            j = avant[i]
            if j.any():
                try:
                    x[j] = shapely.difference(x[j], deja[i][j])
                except shapely.errors.GEOSException:
                    x[j] = shapely.difference(shapely.make_valid(x[j]), shapely.make_valid(deja[i][j]), grid_size=0.01)
            a[i] = shapely.area(x) / 1e4
            return a, i, x

        out[f"derniere_{y}"], i, x = morceau(dedans, m)
        out[f"derniere_pp_{y}"] = morceau(dedans_pp, mp)[0]
        nouv = deja[i]
        vide = np.array([g is None for g in nouv])
        nouv[vide] = x[vide]
        if (~vide).any():
            try:
                nouv[~vide] = shapely.union(nouv[~vide], x[~vide])
            except shapely.errors.GEOSException:
                nouv[~vide] = shapely.union(shapely.make_valid(nouv[~vide]), shapely.make_valid(x[~vide]), grid_size=0.01)
        deja[i] = nouv
        avant = np.array([g is not None for g in deja])
        print(y, round(out[f"derniere_{y}"].sum()), "ha", flush=True)
    out["jamais"] = out.ha - out[[f"derniere_{y}" for y in range(2018, annee)]].sum(axis=1)
    if k is None:
        out.to_parquet(f)
    return out


def resume_origines(annee=2025):
    """Les hectares d'herbe hors PAC par origine exacte (origines), en tout et par département : jamais
    déclarés de 2018 à annee-1 ; dernière déclaration avant la PAC 2023 (2018 à 2021) ; depuis (2022 à
    annee-1). Avec la part déclarée en prairie permanente la dernière année."""
    o = origines(annee)
    c = pd.read_parquet(DOSSIER / str(annee) / "cibles_bilan.parquet")
    o["dep"] = c.dep.values[o.k.values]
    avant, depuis = range(2018, 2022), range(2022, annee)
    o["avant_2023"] = o[[f"derniere_{y}" for y in avant]].sum(axis=1)
    o["avant_2023_pp"] = o[[f"derniere_pp_{y}" for y in avant]].sum(axis=1)
    o["depuis_2023"] = o[[f"derniere_{y}" for y in depuis]].sum(axis=1)
    o["depuis_2023_pp"] = o[[f"derniere_pp_{y}" for y in depuis]].sum(axis=1)
    cols = ["jamais", "avant_2023", "avant_2023_pp", "depuis_2023", "depuis_2023_pp"]

    def rond(d):
        return {k: int(round(v)) for k, v in d.items()}
    return {"total": rond(o[cols].sum()),
            "par_annee": {str(y): int(round(o[f"derniere_{y}"].sum())) for y in range(2018, annee)},
            "par_annee_pp": {str(y): int(round(o[f"derniere_pp_{y}"].sum())) for y in range(2018, annee)},
            "par_dep": {d: rond(x[cols].sum()) for d, x in o.groupby("dep")},
            "part_moins_1ha_avant_2023": round(100 * o.avant_2023[o.ha < 1].sum() / o.avant_2023.sum(), 1)}


def series_agreste(annee=2025, depuis=2018):
    """Statistique agricole (séries longues) : herbe des exploitations, hors exploitations, et prairies
    permanentes du registre PAC, par année ; et l'herbe hors exploitations par département (poste 30 de
    la feuille TER du fichier départemental)."""
    import zipfile
    from .donnees import SOURCES, prairies
    t = pd.read_csv(DATA / SOURCES["saa_series"]["fichier"]).set_index("annee").loc[depuis:annee]
    ans = {str(a): {"expl": int(t.loc[a, "sth_exploitations"]), "hors": int(t.loc[a, "sth_hors_exploitations"]),
                    "registre_pp": int(round(prairies(a).surf_parc.sum()))} for a in t.index}
    z = DATA / "agreste_saa" / "SAA-SeriesLongues-2010-2025.zip"
    dep = {}
    if z.exists():
        with zipfile.ZipFile(z) as f, f.open("SAA_2010-2025_provisoires_donnees_departementales.xlsx") as x:
            d = pd.read_excel(x, sheet_name="TER", header=5)
        d = d[d.LIB_REG2.astype(str).str.startswith("28 ") & d.LIB_SAA.astype(str).str.startswith("30 ")]
        for _, l in d.iterrows():
            dep[str(l.LIB_DEP)[1:3]] = {str(a): int(l[f"SURF_{a}"]) for a in range(depuis, annee + 1)}
    return {"annees": ans, "hors_par_dep": dep}


def herbe_autres_usages():
    """Surface de couvert herbacé (CS2.2.1) de la carte IGN par usage et par département, registre PAC
    compris. Les usages autres qu'agricole (US1.1) et sans usage (US6.3) n'ont pas été cherchés au
    satellite : résidentiel (US5), tertiaire (US3), réseaux (US4), etc. Cache : DOSSIER/herbe_ign_usages.csv."""
    f = DOSSIER / "herbe_ign_usages.csv"
    if f.exists():
        return pd.read_csv(f, index_col=0)
    from .donnees import ocsge
    mill = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))["ocsge"]["millesimes"]
    out = {}
    for dep, ms in sorted(mill.items()):
        o = ocsge(dep, max(int(x) for x in ms))
        h = o[o.code_cs == "CS2.2.1"]
        out[dep] = pd.Series(shapely.area(h.geometry.values) / 1e4, index=h.code_us.values).groupby(level=0).sum().round()
    t = pd.DataFrame(out).fillna(0).astype(int)
    t["Normandie"] = t.sum(axis=1)
    t.to_csv(f)
    return t


IMAGES_MIN_COURBE = 6
PHOTOS = Path(__file__).resolve().parents[1] / "verification" / "sentinel2"


def controle_photos(annee=2025):
    """Le contrôle à l'aveugle sur photos aériennes IGN (scripts/photos_herbe_hors_pac.py) : pour chaque
    groupe d'origine EXACT du morceau (celui de la plus grande part de sa surface, d'après origines), le
    nombre de morceaux jugés prairie, friche, mixte ou douteux."""
    d = PHOTOS / str(annee) / "controle_photos"
    if not (d / "avis.csv").exists():
        return None
    t = pd.read_csv(d / "cle.csv").merge(pd.read_csv(d / "avis.csv"), on="n")
    o = origines(annee).set_index("k").reindex(t.k.values)
    parts = pd.DataFrame({"sortie avant 2023": o[[f"derniere_{y}" for y in range(2018, 2022)]].sum(axis=1).values,
                          "sortie depuis 2023": o[[f"derniere_{y}" for y in range(2022, annee)]].sum(axis=1).values,
                          "jamais": o.jamais.values})
    t["groupe"] = parts.idxmax(axis=1).values
    return {g: {a: int(n) for a, n in x.avis.value_counts().items()} for g, x in t.groupby("groupe")}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "resumer":
        print(json.dumps(resumer(int(sys.argv[2]) if len(sys.argv) > 2 else 2025), ensure_ascii=False, indent=1))
    elif len(sys.argv) > 1 and sys.argv[1] == "etalonner_bois":
        etalonner_bois(int(sys.argv[2]) if len(sys.argv) > 2 else 2025)
    elif len(sys.argv) > 1 and sys.argv[1] == "etalonner":
        etalonner(int(sys.argv[2]) if len(sys.argv) > 2 else 2025)
    else:
        nuit(int(sys.argv[1]) if len(sys.argv) > 1 else 2025)
