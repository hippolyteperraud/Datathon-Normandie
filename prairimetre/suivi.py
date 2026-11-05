"""Suivi des prairies parcelle à parcelle, par croisement des géométries.

Les id_parcel du RPG ne sont pas stables d'une année à l'autre : on suit la surface.
- devenir(a0, a1) : pour chaque prairie de a0, ce qu'est devenue sa surface en a1 ;
- origine(a0, a1) : pour chaque prairie de a1, ce qu'était sa surface en a0.
Chaque résultat est mis en cache : une nouvelle année ne recalcule que ce qui la concerne.
"""
import numpy as np
import pandas as pd
import shapely

from .config import CACHE
from .donnees import communes, prairies, rpg

CULTURES = set(range(1, 17)) | {24, 25}  # céréales, oléo-protéagineux, fourrages, légumes...
CATEGORIES = ["prairie permanente", "prairie temporaire", "culture", "boisement",
              "estive, lande", "autre", "non déclaré"]


def categorie(code_group, code_cultu):
    """Catégorie d'occupation d'une parcelle RPG."""
    cg = code_group.astype("Int64")
    cat = pd.Series("autre", index=code_group.index, dtype="object")
    cat[cg == 18] = "prairie permanente"
    cat[cg == 19] = "prairie temporaire"
    cat[cg.isin(CULTURES)] = "culture"
    cat[cg == 17] = "estive, lande"
    cat[code_cultu.isin(["BOR", "BTA", "TCR"])] = "boisement"
    return cat


def croiser(gauche, droite, pas=20000):
    """Surface (ha) de chaque objet de gauche couverte par chaque catégorie de droite ;
    la surface non couverte va dans « non déclaré »."""
    arbre = shapely.STRtree(droite.geometry.values)
    cats = droite["categorie"].to_numpy()
    morceaux = []
    for i in range(0, len(gauche), pas):
        geo = gauche.geometry.values[i:i + pas]
        il, ir = arbre.query(geo, predicate="intersects")
        surf = shapely.area(shapely.intersection(geo[il], droite.geometry.values[ir])) / 1e4
        morceaux.append(pd.DataFrame({"i": il + i, "cat": cats[ir], "ha": surf}))
    m = pd.concat(morceaux)
    m = m[m.ha > 0].pivot_table(index="i", columns="cat", values="ha", aggfunc="sum")
    m = m.reindex(range(len(gauche))).fillna(0.0)
    ha = shapely.area(gauche.geometry.values) / 1e4
    # Les parcelles de droite se recouvrent parfois un peu : on borne à la surface de départ
    total = m.sum(axis=1).to_numpy()
    m = m.mul(np.where(total > ha, ha / np.maximum(total, 1e-9), 1.0), axis=0)
    m["non déclaré"] = np.clip(ha - m.sum(axis=1).to_numpy(), 0, None)
    m.insert(0, "ha", ha)
    return m


def avec_commune(g):
    """Commune de chaque parcelle (par son point intérieur)."""
    pts = g[["geometry"]].copy()
    pts["geometry"] = g.geometry.representative_point()
    j = pts.sjoin(communes()[["insee", "dep", "geometry"]], how="left", predicate="within")
    return j[~j.index.duplicated()][["insee", "dep"]]


_MEMOIRE_SUIVI = {}


def _croisement(nom, prairies_de, rpg_de):
    if nom in _MEMOIRE_SUIVI:
        return _MEMOIRE_SUIVI[nom]
    f = CACHE / f"{nom}.parquet"
    if f.exists():
        out = pd.read_parquet(f)
    else:
        g = prairies(prairies_de)
        d = rpg(rpg_de)
        d["categorie"] = categorie(d["code_group"], d["code_cultu"])
        m = croiser(g, d)
        m.index = g.index
        out = pd.concat([g[["code_cultu"]], avec_commune(g), m], axis=1)
        out.to_parquet(f)
    for c in CATEGORIES:  # mêmes colonnes quelle que soit l'année
        if c not in out:
            out[c] = 0.0
    _MEMOIRE_SUIVI[nom] = out
    return out


def devenir(a0, a1):
    """Une ligne par prairie de a0 (même index que prairies(a0)) : surface et destination en a1."""
    return _croisement(f"devenir_{a0}_{a1}", a0, a1)


def origine(a0, a1):
    """Une ligne par prairie de a1 (même index que prairies(a1)) : ce qu'était sa surface en a0."""
    return _croisement(f"origine_{a0}_{a1}", a1, a0)
