"""Réussite du classement herbe / culture / bois selon la taille des morceaux, avec un intervalle à 95 %.

Refait exactement la validation croisée de prairimetre.sentinel_nuit.courbes (mêmes étalons, mêmes
traits, même modèle, mêmes plis), puis compte, par classe de taille, la part de l'herbe sûre reconnue
comme herbe (en nombre de morceaux : intervalle de Wilson à 95 %) et la surface d'herbe hors PAC
de chaque classe. Écrit la clé « precision_taille » dans verification/sentinel2/<an>/herbe_hors_pac.json.

    python -X utf8 scripts/precision_par_taille.py [année]
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prairimetre import sentinel as sen  # noqa: E402
from prairimetre.sentinel_nuit import DOSSIER, IMAGES_MIN_COURBE, _traits  # noqa: E402

# Les classes affichées : petits morceaux et grands morceaux (seuil 5 ha), et le détail
CLASSES = [(0.1, 0.5, "0,1 à 0,5 ha"), (0.5, 1, "0,5 à 1 ha"), (1, 5, "1 à 5 ha"), (5, np.inf, "5 ha et plus")]
SEUIL = 5


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    m = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (round(100 * (c - m), 1), round(100 * (c + m), 1))


def ligne(d, nom, cibles_ha):
    k, n = int((d.pred == "herbe").sum()), len(d)
    bas, haut = wilson(k, n)
    return {"classe": nom, "morceaux": n, "reconnus": k, "pct": round(100 * k / n, 1) if n else None,
            "ic95": [bas, haut], "ha_hors_pac": int(round(cibles_ha))}


def main(annee=2025):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    D = DOSSIER / str(annee)
    e, b, c = (pd.read_parquet(D / f) for f in ("etats_etalons.parquet", "etats_etalons_bois.parquet",
                                                  "cibles_bilan.parquet"))
    X = pd.concat([_traits(pd.read_parquet(D / "mesures_etalons.parquet"), len(e)),
                   _traits(pd.read_parquet(D / "mesures_etalons_bois.parquet"), len(b))], ignore_index=True)
    E = pd.concat([e, b], ignore_index=True)
    E["nature"] = E.nature.replace({"arbustes": "bois"})
    X["ha"] = np.log(E.ha.values)
    ok = (X.n.fillna(0) >= IMAGES_MIN_COURBE).values
    E, X = E[ok].reset_index(drop=True), X[ok].reset_index(drop=True)
    mod = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.06, random_state=0)
    p = cross_val_predict(mod, X, E.nature.values, cv=StratifiedKFold(5, shuffle=True, random_state=0),
                          method="predict_proba")
    noms = np.array(sorted(set(E.nature)))
    E["pred"] = noms[p.argmax(1)]
    h = E[E.nature == "herbe"]
    hb = c[c.pred == "herbe"]
    juste = round(100 * h.ha[h.pred == "herbe"].sum() / h.ha.sum(), 1)
    print(f"contrôle : herbe reconnue {juste} % de la surface (attendu : validation_pct.herbe)")

    res = {"seuil_ha": SEUIL,
           "petits": ligne(h[h.ha < SEUIL], f"moins de {SEUIL} ha", hb.ha[hb.ha < SEUIL].sum()),
           "grands": ligne(h[h.ha >= SEUIL], f"{SEUIL} ha et plus", hb.ha[hb.ha >= SEUIL].sum()),
           "classes": [ligne(h[(h.ha >= a) & (h.ha < z)], nom, hb.ha[(hb.ha >= a) & (hb.ha < z)].sum())
                       for a, z, nom in CLASSES],
           "herbe_reconnue_surface_pct": juste}
    print(json.dumps(res, ensure_ascii=False, indent=1))
    f = sen.DOSSIER / str(annee) / "herbe_hors_pac.json"
    j = json.loads(f.read_text(encoding="utf-8"))
    j["precision_taille"] = res
    f.write_text(json.dumps(j, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"écrit dans {f}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2025)
