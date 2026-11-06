"""Import d'un fichier téléchargé à la main, pour n'importe quelle source du catalogue.

    python -m prairimetre importer communes ADMIN-EXPRESS-COG_2027.7z
    python -m prairimetre importer ocsge OCS-GE_14_2026.gpkg --dep 14 --millesime 2026
    python -m prairimetre importer rpg RPG_R28_2026.7z --annee 2026

Formats acceptés : .gpkg, .shp, .geojson, .csv, et les archives .zip et .7z (le bon fichier
y est cherché). Étapes : lecture, colonnes en minuscules, Lambert-93, géométries valides,
recadrage sur la Normandie, vérification des colonnes obligatoires, écriture à sa place dans
data/, trace dans le manifest, cache vidé. Rien n'est écrit si une vérification échoue.
"""
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio

from .config import DATA, DEPARTEMENTS, MANIFEST
from .sources import SOURCES
from .telecharger import destination, ecrire, extraire, invalider, normaliser_rpg, noter

GEO = (".gpkg", ".shp", ".geojson", ".json")
# Fichier ou couche à chercher dans une archive qui en contient plusieurs
INDICES = {"communes": r"(?i)^commune(s)?(_|\.|$)", "rpg": r"(?i)parcelles",
           "ocsge": r"(?i)occupation|ocs"}


def _deballer(archive, dossier):
    """Extrait à plat une archive .zip ou .7z ; renvoie les fichiers géographiques et CSV."""
    if archive.suffix.lower() == ".7z":
        fichiers = extraire(archive, r"(?i)\.(gpkg|shp|shx|dbf|prj|cpg|geojson|csv)$", dossier)
    else:
        fichiers = []
        with zipfile.ZipFile(archive) as z:
            for membre in z.namelist():
                if re.search(r"(?i)\.(gpkg|shp|shx|dbf|prj|cpg|geojson|csv)$", membre):
                    cible = Path(dossier) / Path(membre).name  # à plat : chemins longs sous Windows
                    with z.open(membre) as src, open(cible, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    fichiers.append(cible)
    return [f for f in fichiers if f.suffix.lower() in GEO + (".csv",)]


def _choisir(fichiers, nom):
    """Le fichier qui correspond à la source : celui dont le nom évoque la source, sinon le
    plus gros."""
    if not fichiers:
        raise SystemExit("Aucun fichier géographique ou CSV trouvé dans l'archive.")
    motif = INDICES.get(nom)
    retenus = [f for f in fichiers if motif and re.search(motif, f.stem)] or fichiers
    return max(retenus, key=lambda f: f.stat().st_size)


def _lire(chemin, nom):
    if chemin.suffix.lower() == ".csv":
        t = pd.read_csv(chemin, sep=None, engine="python", dtype=str)
        t.columns = [c.lower().strip() for c in t.columns]
        return t.apply(lambda c: c.str.strip())
    couches = [c for c, _ in pyogrio.list_layers(chemin)]
    motif = INDICES.get(nom)
    couche = next((c for c in couches if motif and re.search(motif, c)), couches[0])
    try:
        g = gpd.read_file(chemin, layer=couche, engine="pyogrio")
    except UnicodeDecodeError:
        # Un champ texte coupé au milieu d'un caractère accentué (limite de 254 octets des
        # shapefiles, vu sur la carte des habitats Natura 2000) : on écarte ce seul champ
        lisibles = []
        for c in pyogrio.read_info(chemin, layer=couche)["fields"]:
            try:
                pyogrio.read_dataframe(chemin, layer=couche, columns=[c], read_geometry=False)
                lisibles.append(c)
            except UnicodeDecodeError:
                print(f"   champ « {c} » illisible (texte tronqué dans le fichier source) : écarté")
        g = gpd.read_file(chemin, layer=couche, engine="pyogrio", columns=lisibles)
    g = g.rename(columns={c: c.lower() for c in g.columns if c != "geometry"})
    if g.crs is None:
        raise SystemExit(f"{chemin.name} n'a pas de système de coordonnées : impossible à placer.")
    if g.crs.to_epsg() != 2154:
        g = g.to_crs(2154)
    g = g[g.geometry.notna() & ~g.geometry.is_empty].copy()
    return g.set_geometry(g.geometry.make_valid())


def _verifier_colonnes(t, nom):
    manque = [c for c in SOURCES[nom].get("colonnes", []) if c not in t.columns]
    if manque:
        raise SystemExit(f"Colonnes manquantes pour « {nom} » : {manque}.\n"
                         f"Colonnes du fichier : {sorted(c for c in t.columns if c != 'geometry')}")


def _recadrer(t, nom, annee):
    """Garde la Normandie (les fichiers nationaux sont acceptés)."""
    if nom == "communes":
        return t[t.code_insee.astype(str).str.zfill(5).str[:2].isin(DEPARTEMENTS)]
    if nom == "saa_prairies":
        return t[t.geocode_departement.astype(str).str.zfill(2).isin(DEPARTEMENTS)]
    if nom == "rpg":
        return normaliser_rpg(t.drop(columns="annee", errors="ignore"), annee)
    if nom == "pp_officiel":
        rpg = destination("rpg", annee=annee)
        if not rpg.exists():
            raise SystemExit(f"Importer d'abord le RPG {annee} (la couche officielle s'y rattache).")
        ids = set(pyogrio.read_dataframe(rpg, read_geometry=False, columns=["id_parcel"])
                  .id_parcel.astype(str))
        return t[t.num_parcel.astype(str).isin(ids)]
    if nom in ("ocsge", "epci_noms") or not isinstance(t, gpd.GeoDataFrame):
        return t
    if SOURCES[nom]["producteur"].startswith("DREAL Normandie"):
        return t  # couche déjà régionale : gardée telle que publiée (estran compris)
    from .donnees import region
    return t[t.intersects(region().geometry.iloc[0])]


def importer(nom, fichier, annee=None, dep=None, millesime=None):
    if nom not in SOURCES:
        raise SystemExit(f"Source inconnue : « {nom} ». Sources possibles : " + ", ".join(SOURCES))
    s = SOURCES[nom]
    if "{annee}" in s["fichier"] and annee is None:
        raise SystemExit(f"« {nom} » est annuelle : préciser --annee.")
    if nom == "ocsge" and not (dep and millesime):
        raise SystemExit("OCS GE : préciser --dep (ex. 14) et --millesime (ex. 2026).")
    if dep is not None and dep not in DEPARTEMENTS:
        raise SystemExit(f"Département inconnu : {dep} (attendu : {', '.join(DEPARTEMENTS)}).")
    fichier = Path(str(fichier).strip().strip('"').strip("'")).expanduser()
    if not fichier.exists():
        raise SystemExit(f"Fichier introuvable : {fichier}")

    print(f"\n== import de {fichier.name} -> {nom}")
    with tempfile.TemporaryDirectory(dir=DATA.parent, prefix="tmp_") as tmp:
        if fichier.suffix.lower() in (".zip", ".7z"):
            chemin = _choisir(_deballer(fichier, tmp), nom)
            print(f"   fichier retenu dans l'archive : {chemin.name}")
        else:
            chemin = fichier
        t = _lire(chemin, nom)
        _verifier_colonnes(t, nom)
        avant = len(t)
        t = _recadrer(t, nom, annee)
        print(f"   {avant:,} objets lus, {len(t):,} gardés pour la Normandie")
        if t.empty:
            raise SystemExit("Aucun objet en Normandie : fichier ou source mal choisis ? Rien n'a "
                             "été écrit.")
        infos = {"source": f"import manuel de {fichier.name}"}
        if isinstance(t, gpd.GeoDataFrame):
            dest = ecrire(t, nom, annee, infos=infos, dep=dep, millesime=millesime)
        else:
            dest = destination(nom)
            dest.parent.mkdir(parents=True, exist_ok=True)
            t.to_csv(dest, index=False)
            noter(nom, dest, len(t), **infos)
            invalider(nom)
            print(f"   -> {dest.relative_to(DATA.parent)} ({len(t):,} lignes)")
    if nom == "ocsge":
        _noter_millesime(dep, millesime)
    print("\nImport terminé. Étape suivante : python -m prairimetre calculer")
    return dest


def _noter_millesime(dep, millesime):
    """Le test de certitude lit les millésimes OCS GE disponibles dans le manifest."""
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ms = m.setdefault("ocsge", {}).setdefault("millesimes", {}).setdefault(dep, [])
    if str(millesime) not in ms:
        ms.append(str(millesime))
        ms.sort()
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
