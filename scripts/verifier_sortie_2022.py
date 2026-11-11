"""PYTHONPATH=. python scripts/verifier_sortie_2022.py

Vérifie la piste : herbe sortie du registre en 2022 (dernière déclaration 2021), toujours en herbe en 2025.
Géométrie entière (pas seulement le point au centre) : part du morceau dans le registre de chaque année,
et groupe de culture en 2021."""
import geopandas as gpd, numpy as np, pandas as pd, shapely
from prairimetre.sentinel_hors_ligne import DOSSIER
from prairimetre.sentinel_nuit import cibles
from prairimetre.donnees import rpg
D = DOSSIER / "2025"
c = pd.read_parquet(D / "cibles_bilan.parquet")
s = pd.read_parquet(D / "signatures_cibles.parquet")
g = cibles(2025)
sel = np.flatnonzero(((c.groupe == "sortie avant 2023") & (c.derniere == "2021") & (c.pred == "herbe")).values)
geo = g.geometry.values[sel]
A = shapely.area(geo) / 1e4
print("morceaux", len(sel), "ha", round(A.sum()))
out = pd.DataFrame({"k": sel, "ha": A, "etat": c.etat.values[sel], "p_herbe": s.p_herbe.values[sel], "dep": c.dep.values[sel]})
for a in range(2018, 2025):
    r = rpg(a)
    rg, cg = r.geometry.values, r.code_group.values
    t = shapely.STRtree(rg)
    il, ir = t.query(geo, predicate="intersects")
    part = np.zeros(len(geo)); pp = np.zeros(len(geo)); pt19 = np.zeros(len(geo))
    for i, grp in pd.Series(ir).groupby(il):
        inter = shapely.area(shapely.intersection(geo[i], rg[grp.values])) / 1e4
        part[i] = inter.sum(); pp[i] = inter[cg[grp.values] == 18].sum(); pt19[i] = inter[cg[grp.values] == 19].sum()
    out[f"in{a}"], out[f"pp{a}"], out[f"pt{a}"] = part, pp, pt19
out.to_parquet(D / "verif_2021.parquet")
print("\nHa du groupe dans le registre, par année (toutes cultures / prairie permanente 18 / prairie temporaire 19) :")
for a in range(2018, 2025):
    print(a, round(out[f"in{a}"].sum()), round(out[f"pp{a}"].sum()), round(out[f"pt{a}"].sum()))
print("\nÉtat de la règle (ha) :", out.groupby("etat").ha.sum().round().to_dict())
print("p_herbe (ha) :", out.groupby(pd.cut(out.p_herbe, [0, .5, .7, .9, 1])).ha.sum().round().to_dict())
print("par département :", out.groupby("dep").ha.sum().round().to_dict())
# Seulement les morceaux couverts à au moins 50 % par une prairie permanente en 2021 et à moins de 10 % ensuite
ok = (out.pp2021 >= .5 * out.ha) & (out[[f"in{a}" for a in (2022, 2023, 2024)]].max(axis=1) < .1 * out.ha)
print("\nPP 2021 >= 50 % du morceau et < 10 % au registre 2022-2024 :", ok.sum(), "morceaux,", round(out.ha[ok].sum()), "ha")
print("  dont couvert permanent :", round(out.ha[ok & (out.etat == 'couvert permanent')].sum()), "ha")
print("  p_herbe >= 0.9 :", round(out.ha[ok & (out.p_herbe >= .9)].sum()), "ha")
