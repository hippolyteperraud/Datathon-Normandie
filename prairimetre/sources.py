"""Catalogue des sources : où chaque fichier de data/ se télécharge, et ce qu'il doit contenir.

Modes d'accès :
- "archive_ign" : archive .7z du service de téléchargement IGN (Atom), cherchée par motif ;
- "wfs" : flux WFS paginé, limité à la Normandie ;
- "api_json" : table JSON d'une API ouverte ;
- "manuel" : pas d'accès scriptable stable ; on télécharge le fichier à la main, puis
  « python -m prairimetre importer <source> <fichier> » le met au format.
Toute source peut aussi être importée depuis un fichier, même si elle a un accès automatique.

Dans les chemins et les noms de couche, {annee}, {dep} et {millesime} sont remplacés à l'usage.
« colonnes » : colonnes obligatoires, vérifiées à l'import (noms en minuscules).
"""
from .config import REGION

WFS_IGN = "https://data.geopf.fr/wfs/ows"
WFS_SANDRE = "https://services.sandre.eaufrance.fr/geo/zgr"
PATRINAT = "MNHN / PatriNat"
DREAL = "DREAL Normandie"
LO = "Licence Ouverte 2.0"
# Pages lisibles des flux WFS (l'adresse d'un flux, elle, renvoie une erreur dans un navigateur)
PAGE_RPG = "https://geoservices.ign.fr/rpg"
PAGE_BCAE = "https://cartes.gouv.fr/rechercher-une-donnee/dataset/IGNF_BCAE"
PAGE_INPN = "https://inpn.mnhn.fr/referentiels-donnees"
DATA_GOUV = "https://www.data.gouv.fr/datasets/"


def _wfs(fichier, couche, producteur, lien, url=WFS_IGN, annuelle=False, colonnes=()):
    return dict(mode="wfs", fichier=fichier, couche=couche, url=url, producteur=producteur,
                licence=LO, page=f"{url} (couche {couche})", lien=lien, annuelle=annuelle,
                colonnes=list(colonnes))


def _manuel(fichier, producteur, page, colonnes=(), licence=LO):
    return dict(mode="manuel", fichier=fichier, producteur=producteur, licence=licence, page=page,
                annuelle=False, colonnes=list(colonnes))


SOURCES = {
    # --- Sources annuelles : à retélécharger à chaque millésime -----------------------------
    "rpg": dict(
        mode="archive_ign", famille="RPG",
        motif=rf"_LAMB93_{REGION}[-_]{{annee}}([-_]|$)",  # la version change (2-0, 2-2, 4-0...)
        membre=r"(?i)(rpg_parcelles|parcelles_graphiques)\.(gpkg|shp|shx|dbf|prj|cpg)$",
        secours="RPG.{annee}:parcelles_graphiques",  # WFS si l'archive n'est pas encore publiée
        fichier="rpg/rpg_{annee}.gpkg", producteur="IGN / ASP", licence=LO,
        page=PAGE_RPG, annuelle=True,
        colonnes=["id_parcel", "surf_parc", "code_cultu", "code_group"]),
    "pp_officiel": _wfs(
        "certitude/prairies_permanentes_officielles_{annee}.gpkg",
        r"IGNF_RPG_PRAIRIES-PERMANENTES_{annee}:\w+",  # nom de couche variable : cherché dans le catalogue
        "IGN / ASP", PAGE_RPG, annuelle=True, colonnes=["num_parcel", "surf_parc"]),

    # --- Zonages de priorité (WFS) : à rafraîchir de temps en temps -------------------------
    "prairies_sensibles": _wfs("priorite/prairies_sensibles.gpkg",
                               "PRAIRIES.SENSIBLES.BCAE:prairies_sensibles", "MASA / IGN", PAGE_BCAE),
    "bcae_zones_humides_tourbieres": _wfs("priorite/bcae_zones_humides_tourbieres.gpkg",
                                          "TOURBIERES_ZONES-HUMIDES.BCAE:bcae", "MASA / IGN",
                                          PAGE_BCAE),
    "natura2000_sic": _wfs("priorite/natura2000_sic.gpkg", "patrinat_sic:sic", PATRINAT, PAGE_INPN),
    "natura2000_zps": _wfs("priorite/natura2000_zps.gpkg", "patrinat_zps:zps", PATRINAT, PAGE_INPN),
    "pnr": _wfs("priorite/pnr.gpkg", "patrinat_pnr:pnr", PATRINAT, PAGE_INPN, colonnes=["nom_site"]),
    "rnn": _wfs("priorite/rnn.gpkg", "patrinat_rnn:rnn", PATRINAT, PAGE_INPN),
    "rnr": _wfs("priorite/rnr.gpkg", "patrinat_rnr:rnr", PATRINAT, PAGE_INPN),
    "cen": _wfs("priorite/cen.gpkg", "patrinat_cen:cen", PATRINAT, PAGE_INPN),
    "apb": _wfs("priorite/apb.gpkg", "patrinat_apb:apb", PATRINAT, PAGE_INPN),
    "plu_zonage": _wfs("priorite/plu_zonage.gpkg", "wfs_du:zone_urba",
                       "DGALN / IGN (Géoportail de l'urbanisme)",
                       "https://www.geoportail-urbanisme.gouv.fr/", colonnes=["typezone"]),
    "aires_alimentation_captages": _wfs(
        "priorite/aires_alimentation_captages.gpkg", "sa:AAC_FXX", "Sandre",
        DATA_GOUV + "aires-dalimentation-de-captages-france-entiere-1", url=WFS_SANDRE,
        colonnes=["cdaac", "nomdeaacadministratif", "commandaac", "adminaac", "ptp",
                  "nomcircadminbassin"]),

    # --- Référentiel administratif (API ouverte) ----------------------------------------------
    "epci_noms": dict(mode="api_json", url="https://geo.api.gouv.fr/epcis?fields=nom,code",
                      fichier="communes/epci.csv", producteur="IGN / INSEE (API Découpage administratif)",
                      licence=LO, page="https://geo.api.gouv.fr/decoupage-administratif",
                      annuelle=False, colonnes=["nom", "code"]),
    "codes_postaux": dict(mode="api_json",
                          url="https://geo.api.gouv.fr/communes?codeRegion=28"
                              "&fields=code,nom,codesPostaux&format=json",
                          fichier="communes/codes_postaux.csv",
                          producteur="La Poste / INSEE (API Découpage administratif)",
                          licence=LO, page="https://geo.api.gouv.fr/decoupage-administratif",
                          annuelle=False, colonnes=["code", "codespostaux"]),

    # --- Sources sans accès scriptable stable : import depuis un fichier téléchargé ---------
    "communes": _manuel(
        "communes/communes_normandie.gpkg", "IGN (ADMIN EXPRESS)",
        "https://cartes.gouv.fr/rechercher-une-donnee/dataset/IGNF_ADMIN-EXPRESS",
        colonnes=["code_insee", "nom_officiel", "population", "codes_siren_des_epci"]),
    "ocsge": _manuel("ocsge/ocsge_{dep}_{millesime}.gpkg", "IGN (OCS GE)",
                     "https://data.geopf.fr/telechargement/resource/OCSGE",
                     colonnes=["code_cs", "code_us"]),
    "saa_prairies": _manuel(
        "certitude/saa_evolution_prairies.csv", "Agreste (statistique agricole annuelle)",
        "https://www.data.gouv.fr/datasets/pourcentage-devolution-annuelle-de-la-surface-en-"
        "prairie-permanente-et-temporaire",
        colonnes=["date_mesure", "geocode_departement", "type_prairie", "numerateur",
                  "denominateur"]),
    "saa_series": _manuel(
        "agreste_saa/saa_region.csv", "Agreste (statistique agricole annuelle, séries longues)",
        "https://agreste.agriculture.gouv.fr/agreste-web/disaron/SAA-SeriesLongues/detail/",
        colonnes=["annee", "sth_exploitations", "sth_hors_exploitations", "sau_region"]),
    "habitats_natura2000": _manuel(
        "priorite/habitats_natura2000_occidentale.gpkg", "DREAL Normandie / CBN de Brest",
        "https://www.data.gouv.fr/datasets/carte-de-synthese-des-habitats-dans-les-sites-"
        "natura-2000-de-normandie-occidentale-14-50-61-version-20260325",
        colonnes=["nat2000", "etatcons"]),
    "zones_humides_dreal": _manuel("priorite/zones_humides_dreal.gpkg", DREAL,
                                   DATA_GOUV + "zones-humides-normandie"),
    "par7_zones_humides_est": _manuel(
        "priorite/par7_zones_humides_est.gpkg", DREAL,
        DATA_GOUV + "zones-humides-des-petites-regions-agricoles-est-7par-normandie-1"),
    "srce_reservoirs": _manuel("priorite/srce_reservoirs.gpkg", DREAL,
                               DATA_GOUV + "srce-reservoirs-de-biodiversite-normandie"),
    "znieff1": _manuel(
        "priorite/znieff1.gpkg", DREAL,
        "https://www.data.gouv.fr/datasets/zones-naturelles-dinteret-ecologique-"
        "faunistique-et-floristique-de-type-1-de-normandie"),
}

ZONAGES_WFS = [n for n, s in SOURCES.items() if s["mode"] == "wfs" and not s["annuelle"]]
