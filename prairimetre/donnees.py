"""Lecture des données de data/ avec cache GeoParquet (cache/).

Toutes les géométries sont en Lambert-93 et rendues valides avant tout croisement.
Toutes les jointures communales passent par la clé 'insee' (texte, 5 caractères).
"""
import geopandas as gpd
import pandas as pd

from .config import CACHE, DATA
from .sources import SOURCES

# Trois familles de zonages, à ne pas confondre (question 2) :
# - les RÈGLES qui interdisent ou encadrent le retournement d'une prairie ;
# - les SITES PROTÉGÉS ou gérés, dont le statut ne vise pas directement le labour ;
# - les INVENTAIRES et documents de planification, sans effet juridique sur le labour.
FAMILLES = {
    "regle": ["prairies_sensibles",             # BCAE 9 : retournement interdit
              "bcae_zones_humides_tourbieres",  # BCAE 2 : zones humides et tourbières
              "par7_zones_humides_est"],        # programme nitrates : règle à confirmer
    "site": ["natura2000_sic", "natura2000_zps", "rnn", "rnr", "apb", "cen"],
    "inventaire": ["zones_humides_dreal", "znieff1", "srce_reservoirs", "plu_zone_n"],
}
NOMS_FAMILLES = {"regle": "règle qui encadre le retournement", "site": "site naturel protégé",
                 "inventaire": "inventaire ou zone N de PLU (sans effet sur le labour)"}
ZONAGES_ENJEUX = [n for f in FAMILLES.values() for n in f]
# Zonages qui désignent un acteur sans protéger la prairie (question 3 : avec qui agir ?)
ZONAGES_ACTEURS = ["aires_alimentation_captages", "pnr"]
ZONAGES = ZONAGES_ENJEUX + ZONAGES_ACTEURS
# Habitats prairiaux d'intérêt européen (cartographie Natura 2000, Calvados, Manche, Orne)
HABITATS_PRAIRIAUX = {"6410": "prairies à molinie", "6510": "prairies maigres de fauche",
                      "6430": "mégaphorbiaies", "6210": "pelouses sèches calcaires",
                      "6230": "pelouses à nard"}


def code5(s):
    """Code INSEE -> texte de 5 caractères. À utiliser pour TOUTES les jointures."""
    return s.astype("string").str.strip().str.replace(r"\.0$", "", regex=True).str.zfill(5)


def lire(chemin, **kw):
    """Lecture + Lambert-93 + géométries valides ; ne garde que les polygones s'il y en a."""
    g = gpd.read_file(chemin, engine="pyogrio", **kw)
    if g.crs is not None and g.crs.to_epsg() != 2154:
        g = g.to_crs(2154)
    g = g[g.geometry.notna() & ~g.geometry.is_empty].copy()
    g = g.set_geometry(g.geometry.make_valid())
    if g.geom_type.isin(["Polygon", "MultiPolygon"]).any():
        g = g[g.geom_type.isin(["Polygon", "MultiPolygon"])]
    return g.reset_index(drop=True)


def en_cache(nom, fabrique):
    f = CACHE / f"{nom}.parquet"
    if f.exists():
        return gpd.read_parquet(f)
    g = fabrique()
    g.to_parquet(f)
    return g


def prairies(annee):
    """Prairies permanentes d'une année : code_group == 18.
    2018-2022 = PPH + PRL, à partir de 2023 = PPH seul ; 93,9 % des PRL de 2022 sont
    devenues PPH en 2023, la série reste donc continue."""
    def f():
        chemin = DATA / SOURCES["rpg"]["fichier"].format(annee=annee)
        cols = ["id_parcel", "surf_parc", "code_cultu", "code_group"]
        g = lire(chemin, columns=cols, where="code_group = 18")
        g["code_group"] = 18
        g["annee"] = annee
        return g
    return en_cache(f"pp_{annee}", f)


def rpg(annee):
    """Toutes les parcelles d'une année (pour savoir ce qu'est devenue une prairie)."""
    def f():
        g = lire(DATA / SOURCES["rpg"]["fichier"].format(annee=annee),
                 columns=["surf_parc", "code_cultu", "code_group"])
        g["code_group"] = pd.to_numeric(g["code_group"], errors="coerce").astype("Int64")
        return g
    return en_cache(f"rpg_{annee}", f)


def communes():
    """Communes avec 'insee', 'dep' (2 car.), 'epci' (SIREN) et 'epci_nom'."""
    def f():
        g = lire(DATA / SOURCES["communes"]["fichier"],
                 columns=["code_insee", "nom_officiel", "population", "codes_siren_des_epci"])
        g["insee"] = code5(g["code_insee"])
        g["dep"] = g["insee"].str[:2]
        g["epci"] = g["codes_siren_des_epci"].astype("string")
        return g.drop(columns=["code_insee", "codes_siren_des_epci"])
    g = en_cache("communes_v2", f)
    noms = DATA / SOURCES["epci_noms"]["fichier"]
    if noms.exists():
        n = pd.read_csv(noms, dtype=str).set_index("code").nom
        g["epci_nom"] = g.epci.map(n)
    cp = DATA / SOURCES["codes_postaux"]["fichier"]
    if cp.exists():  # « 76000, 76100 » ; le code INSEE n'est pas le code postal
        c = pd.read_csv(cp, dtype=str)
        g["codes_postaux"] = g.insee.map(c.set_index(code5(c.code)).codesPostaux.str.replace(" ", ", "))
    return g


def region():
    """Contour de la Normandie (union des communes)."""
    return en_cache("region",
                    lambda: communes()[["geometry"]].dissolve().reset_index(drop=True))


def zonage(nom):
    """Zonage de priorité, géométries valides, non recadré (sert aux tests point-dans-polygone).
    'plu_zone_n' = zones N des PLU."""
    def f():
        if nom == "plu_zone_n":
            g = lire(DATA / "priorite/plu_zonage.gpkg", columns=["typezone"])
            return g[g.typezone.astype(str).str.upper().str.startswith("N")][["geometry"]]
        cols = {"pnr": ["nom_site"], "aires_alimentation_captages": [
            "cdaac", "nomdeaacadministratif", "commandaac", "adminaac", "ptp",
            "nomcircadminbassin"]}
        return lire(DATA / f"priorite/{nom}.gpkg", columns=cols.get(nom, []))
    return en_cache(f"prio_{nom}", f)


def habitats_prairiaux():
    """Habitats prairiaux d'intérêt européen cartographiés dans les sites Natura 2000 (14, 50, 61)."""
    def f():
        g = lire(DATA / SOURCES["habitats_natura2000"]["fichier"],
                 columns=["nat2000", "nat2000txt", "etatcons", "code_site"])
        g["code"] = g.nat2000.astype(str).str[:4]
        return g[g.code.isin(HABITATS_PRAIRIAUX)].reset_index(drop=True)
    return en_cache("habitats_prairiaux", f)


def saa():
    """Statistique agricole annuelle : prairies permanentes productives par département et par
    année (source indépendante du RPG). Niveau reconstitué : base de l'année + variation."""
    t = pd.read_csv(DATA / SOURCES["saa_prairies"]["fichier"], dtype={"geocode_departement": str})
    t = t[t.type_prairie == "Prairies naturelles ou semées depuis plus de 5 ans"].copy()
    t["annee"] = t.date_mesure.str[:4].astype(int)
    t["niveau"] = pd.to_numeric(t.denominateur) + pd.to_numeric(t.numerateur)
    return t.rename(columns={"geocode_departement": "dep"})[["annee", "dep", "niveau"]]


def enaf():
    """Consommation d'espaces NAF (Cerema), clé 'insee'."""
    e = pd.read_csv(DATA / SOURCES["conso_enaf"]["fichier"], dtype={"idcom": str})
    e["insee"] = code5(e["idcom"])
    return e


def lucas():
    """Points LUCAS 2022 ; prairie_terrain = couverture observée commençant par E."""
    def f():
        g = lire(DATA / SOURCES["lucas"]["fichier"],
                 columns=["point_id", "survey_lc1", "survey_lu1", "survey_grazing"])
        g["prairie_terrain"] = g["survey_lc1"].astype(str).str.startswith("E")
        return g
    return en_cache("lucas", f)


def ocsge(dep, millesime):
    """OCS GE d'un département (couverture et usage)."""
    return en_cache(f"ocsge_{dep}_{millesime}",
                    lambda: lire(DATA / f"ocsge/ocsge_{dep}_{millesime}.gpkg",
                                 columns=["code_cs", "code_us"]))


def theia_oso(annee):
    """Couche d'occupation des sols Theia OSO issue de Sentinel-2 (classes herbacées 221/222)."""
    def f():
        chemin = DATA / SOURCES["theia_oso"]["fichier"].format(annee=annee)
        return lire(chemin, columns=["classe", "libelle"])
    return en_cache(f"theia_oso_{annee}", f)


def copernicus_grassland():
    """Couche européenne Copernicus HRL Grassland (10 m)."""
    def f():
        chemin = DATA / SOURCES["copernicus_grassland"]["fichier"]
        return lire(chemin, columns=["gra_status", "gra_density"])
    return en_cache("copernicus_grassland", f)
