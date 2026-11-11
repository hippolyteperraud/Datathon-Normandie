"""L'eau : les nitrates des rivières normandes et les prairies au-dessus des captages d'eau potable.

Lecture seule, sans réseau. Les mesures sont téléchargées par scripts/analyser_nitrates.py (API Hubeau,
qualité des cours d'eau : nitrates, analyses validées) dans data/raw/qualite_eau_hubeau/ ; les aires
d'alimentation de captage (Sandre) sont dans data/raw/aac_normandie/AAC.gpkg ; les prairies au-dessus
des captages viennent des sorties du moteur (captages.csv, evaluation_zonages.csv, evaluation_robustesse.csv).

Règles pour que les chiffres soient sûrs :
- une station pèse autant qu'une autre : on prend d'abord la médiane de ses analyses de l'année ;
- on ne compare que les MÊMES stations entre deux périodes de trois ans (au moins deux années mesurées
  dans chaque période), car les stations suivies changent d'une année à l'autre ;
- la tendance est refaite sur plusieurs découpages de périodes, et testée contre le hasard (test du
  signe : sans tendance, autant de stations monteraient que baisseraient).
"""
from math import comb

import pandas as pd

from .config import DATA, SORTIES

DOSSIER_HUBEAU = DATA / "raw" / "qualite_eau_hubeau"
STATIONS = DOSSIER_HUBEAU / "stations_normandie.csv"
AAC = DATA / "raw" / "aac_normandie" / "AAC.gpkg"
# Limite de qualité des nitrates dans l'eau destinée à la consommation humaine (directive (UE)
# 2020/2184 ; arrêté du 11 janvier 2007) : 50 mg/L. Elle s'applique à l'eau du robinet, pas aux
# rivières : elle sert ici de repère.
LIMITE_POTABLE = 50
FENETRE = 3      # années par période comparée
ANNEES_MIN = 2   # années mesurées au moins dans chaque période


def fichier_mesures():
    """Le fichier de mesures le plus récent (nitrates_<début>_<fin>.csv), ou None."""
    f = sorted(DOSSIER_HUBEAU.glob("nitrates_*_*.csv"))
    return f[-1] if f else None


def mesures():
    """Une ligne par analyse retenue (date, station, résultat en mg(NO3)/L)."""
    f = fichier_mesures()
    if f is None:
        return pd.DataFrame(columns=["code_station", "annee", "resultat"])
    m = pd.read_csv(f, sep=";", encoding="utf-8-sig", dtype={"code_station": str, "code_departement": str})
    m["annee"] = m.date_prelevement.str[:4].astype(int)
    return m


def stations():
    """Stations de mesure : nom, cours d'eau, commune, département, coordonnées (WGS84)."""
    s = pd.read_csv(STATIONS, dtype=str, low_memory=False).drop_duplicates("code_station")
    s["longitude"], s["latitude"] = pd.to_numeric(s.longitude), pd.to_numeric(s.latitude)
    return s.set_index("code_station")[["libelle_station", "nom_cours_eau", "libelle_commune",
                                        "code_departement", "longitude", "latitude"]]


def par_station_annee(m=None):
    """Médiane des analyses de chaque station, chaque année (stations en lignes, années en colonnes)."""
    m = mesures() if m is None else m
    return m.groupby(["code_station", "annee"]).resultat.median().unstack()


def comparer(sa, debut, fin):
    """Variation de chaque station entre deux périodes (médiane des années de chaque période), pour les
    stations mesurées au moins ANNEES_MIN années dans chacune."""
    a, b = sa.reindex(columns=list(debut)), sa.reindex(columns=list(fin))
    ok = (a.notna().sum(axis=1) >= ANNEES_MIN) & (b.notna().sum(axis=1) >= ANNEES_MIN)
    return pd.DataFrame({"avant": a[ok].median(axis=1), "apres": b[ok].median(axis=1)}) \
        .assign(variation=lambda x: x.apres - x.avant)


def hasard(hausse, baisse):
    """Probabilité d'avoir au moins autant de hausses si chaque station avait autant de chances de
    monter que de baisser (test du signe, unilatéral)."""
    n = hausse + baisse
    return sum(comb(n, i) for i in range(hausse, n + 1)) / 2 ** n if n else 1.0


def periodes(sa):
    """Les deux périodes principales : les FENETRE premières et les FENETRE dernières années."""
    A = sorted(sa.columns)
    return tuple(A[:FENETRE]), tuple(A[-FENETRE:])


def tendance():
    """Les stations comparables entre la première et la dernière période, avec leur description."""
    sa = par_station_annee()
    debut, fin = periodes(sa)
    t = comparer(sa, debut, fin).join(stations(), how="left")
    t["sens"] = pd.cut(t.variation, [-float("inf"), -0.0001, 0.0001, float("inf")],
                       labels=["en baisse", "stable", "en hausse"])
    return t, debut, fin


def robustesse():
    """La même comparaison sur plusieurs découpages de périodes : la tendance tient-elle ?"""
    sa = par_station_annee()
    A = sorted(sa.columns)
    if len(A) < 2 * FENETRE:
        return pd.DataFrame()
    decoupages = {(tuple(A[i:i + FENETRE]), tuple(A[j:j + FENETRE]))
                  for i, j in [(0, len(A) - FENETRE), (1, len(A) - FENETRE - 1),
                               (0, len(A) - FENETRE - 3), (2, len(A) - FENETRE)]
                  if 0 <= i and i + FENETRE <= j and j + FENETRE <= len(A)}
    lignes = []
    for d, f in sorted(decoupages):
        v = comparer(sa, d, f).variation
        h, b = int((v > 0).sum()), int((v < 0).sum())
        lignes.append({"avant": f"{d[0]}-{d[-1]}", "apres": f"{f[0]}-{f[-1]}", "stations": len(v),
                       "variation_mediane": v.median(), "en_hausse": h, "en_baisse": b,
                       "hasard": hasard(h, b)})
    return pd.DataFrame(lignes)


def depassements():
    """Chaque année : stations mesurées, et combien ont une médiane annuelle au-dessus de la limite."""
    sa = par_station_annee()
    return pd.DataFrame({"stations": sa.notna().sum(), "au_dessus": (sa > LIMITE_POTABLE).sum()}) \
        .rename_axis("annee")


def noms_captages():
    """Nom de chaque aire d'alimentation de captage (Sandre), par code."""
    import pyogrio
    a = pyogrio.read_dataframe(AAC, read_geometry=False,
                               columns=["CdAAC", "NomDeAACAdministratif", "NomDeAACUsage"])
    nom = a.NomDeAACUsage.where(a.NomDeAACUsage.fillna("").str.strip() != "", a.NomDeAACAdministratif)
    return pd.Series(nom.values, index=a.CdAAC.astype(str))


def captages():
    """Les aires de captage de Normandie (sorties du moteur), avec leur nom lisible."""
    c = pd.read_csv(SORTIES / "captages.csv", dtype={"aac": str}).set_index("aac")
    if AAC.exists():
        c["nom"] = noms_captages().reindex(c.index).fillna(c.nom.astype(str))
    return c
