"""Vérification INDÉPENDANTE des origines de l'herbe hors PAC (prairimetre.sentinel_nuit.origines).

origines() découpe chaque morceau par géométrie. Ici, autre méthode : des points tirés au hasard, de
façon uniforme sur la surface de l'herbe hors PAC ; pour chaque point, la dernière année de 2018 à 2024
où il est dans une parcelle du registre. La part des points de chaque groupe, multipliée par la surface
totale, doit retomber sur les chiffres de origines() à l'erreur de tirage près.

    PYTHONPATH=. python scripts/verifier_origines.py
"""
import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from prairimetre.donnees import rpg
from prairimetre.sentinel_hors_ligne import DOSSIER
from prairimetre.sentinel_nuit import cibles, resume_origines

N = 30000
c = pd.read_parquet(DOSSIER / "2025" / "cibles_bilan.parquet")
k = np.flatnonzero((c.pred == "herbe").values)
geo = shapely.make_valid(cibles(2025).geometry.values[k])
aire = shapely.area(geo)
hasard = np.random.default_rng(42)
tires = hasard.choice(len(geo), N, p=aire / aire.sum())
pts = np.empty(N, dtype=object)
reste = np.arange(N)
while len(reste):       # un point uniforme dans chaque morceau tiré (rejet dans le rectangle englobant)
    b = shapely.bounds(geo[tires[reste]])
    x = hasard.uniform(b[:, 0], b[:, 2])
    y = hasard.uniform(b[:, 1], b[:, 3])
    p = shapely.points(x, y)
    ok = shapely.contains(geo[tires[reste]], p)
    pts[reste[ok]] = p[ok]
    reste = reste[~ok]
pt = gpd.GeoDataFrame(geometry=pts, crs=cibles(2025).crs)
derniere = np.full(N, 0)
pp_derniere = np.zeros(N, dtype=bool)
for a in range(2018, 2025):
    r = rpg(a)[["code_group", "geometry"]]
    j = gpd.sjoin(pt, r, how="inner", predicate="within")
    j = j[~j.index.duplicated()]
    derniere[j.index.values] = a
    pp_derniere[j.index.values] = (j.code_group.values == 18)
total = aire.sum() / 1e4
grp = np.select([derniere == 0, derniere <= 2021], ["jamais", "avant_2023"], "depuis_2023")
ref = resume_origines(2025)["total"]
print(f"{N} points, herbe hors PAC {total:,.0f} ha")
for g in ("jamais", "avant_2023", "depuis_2023"):
    p = (grp == g).mean()
    se = np.sqrt(p * (1 - p) / N) * total
    print(f"{g:12s} points : {p * total:9,.0f} ha (± {1.96 * se:,.0f})   origines() : {ref[g]:9,.0f} ha")
p = ((grp == "avant_2023") & pp_derniere).mean()
print(f"avant_2023 en prairie permanente : {p * total:,.0f} ha   origines() : {ref['avant_2023_pp']:,} ha")
