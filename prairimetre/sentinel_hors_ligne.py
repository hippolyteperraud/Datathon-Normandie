"""Sentinel-2 hors ligne : on télécharge UNE fois les images de l'année sur la Normandie, puis toutes
les mesures se font sans réseau, avec la même règle que sentinel.py (sentinel.classer).

Ce qu'on garde de chaque image (même catalogue public que sentinel.py : Microsoft Planetary Computer,
Sentinel-2 L2A, images de l'année à moins de 40 % de nuages) :
- le NDVI à 10 m, (B08 − B04) / (B08 + B04) sur les valeurs brutes, exactement comme le calcule le
  service dans sentinel.py (la règle a été réglée et validée sur ces valeurs), rangé sur un octet :
  valeur = round((NDVI + 1) × 100), 255 = pas de donnée ;
- la classification de scène (SCL, ESA) à 20 m, pour écarter nuages et ombres.
Seule la partie de chaque image qui couvre la Normandie est lue et gardée (fichiers compressés).

    python -m prairimetre.sentinel_hors_ligne telecharger 2025     # avec réseau, reprend où il en était
"""
from __future__ import annotations

import json
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import shape

from .donnees import DATA, region
from .sentinel import COLLECTION, STAC, _post

DOSSIER = DATA / "sentinel2"
JETON = "https://planetarycomputer.microsoft.com/api/sas/v1/token/" + COLLECTION
NUAGES_MAX = 40
_jeton = {"valeur": None, "date": 0.0}
_verrou = threading.Lock()


def jeton():
    """Jeton d'accès public aux fichiers (sans compte), renouvelé toutes les 20 minutes."""
    with _verrou:
        if time.time() - _jeton["date"] > 1200:
            for essai in range(6):
                try:
                    _jeton["valeur"] = json.load(urllib.request.urlopen(JETON, timeout=60))["token"]
                    _jeton["date"] = time.time()
                    break
                except Exception:
                    time.sleep(10 * (essai + 1))
        return _jeton["valeur"]


def contour(marge=300):
    """La Normandie, élargie de 300 m, en WGS84 (pour le catalogue) et en Lambert-93."""
    r = region().buffer(marge).simplify(100)
    return gpd.GeoSeries(r, crs=region().crs)


def catalogue(annee):
    """Toutes les images de l'année qui touchent la Normandie (pages suivies jusqu'au bout)."""
    f = DOSSIER / str(annee) / "catalogue.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    geo = json.loads(contour().to_crs(4326).simplify(0.01).to_json())["features"][0]["geometry"]
    corps = {"collections": [COLLECTION], "intersects": geo,
             "datetime": f"{annee}-01-01/{annee}-12-31",
             "query": {"eo:cloud_cover": {"lt": NUAGES_MAX}}, "limit": 500}
    items = []
    while corps:
        rep = _post(STAC, corps)
        items += rep["features"]
        suite = [l for l in rep.get("links", []) if l.get("rel") == "next"]
        corps = suite[0].get("body") if suite else None
    garde = [{"id": i["id"], "date": i["properties"]["datetime"][:10],
              "tuile": i["properties"].get("s2:mgrs_tile"),
              "epsg": i["properties"].get("proj:epsg") or int(str(i["properties"].get("proj:code")).split(":")[-1]),
              "nuages": i["properties"]["eo:cloud_cover"], "geometrie": i["geometry"],
              "B04": i["assets"]["B04"]["href"], "B08": i["assets"]["B08"]["href"],
              "SCL": i["assets"]["SCL"]["href"]} for i in items]
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(garde), encoding="utf-8")
    return garde


def fichiers(item, annee):
    d = DOSSIER / str(annee) / item["tuile"]
    return d / f"{item['date']}_{item['id']}_ndvi.tif", d / f"{item['date']}_{item['id']}_scl.tif"


def _ecrire(chemin, tableau, transform, crs, nodata):
    import rasterio
    tmp = chemin.with_suffix(".part")
    with rasterio.open(tmp, "w", driver="GTiff", width=tableau.shape[1], height=tableau.shape[0], count=1,
                       dtype="uint8", crs=crs, transform=transform, nodata=nodata, compress="deflate",
                       predictor=2, tiled=True, blockxsize=512, blockysize=512) as s:
        s.write(tableau, 1)
    tmp.replace(chemin)


# Tuiles Sentinel-2 retenues (couverture minimale, calculée le 09/11/2026) : elles couvrent toutes les
# prairies de 2018 et toute l'herbe jamais déclarée à la PAC, sauf 0,3 % des morceaux (tuiles 30UYA,
# 31UDQ, 31UDR, laissées de côté pour gagner 186 images). Dans l'ordre : les plus utiles d'abord.
TUILES = ["30UXV", "30UYV", "31UCR", "30UXU", "30UYU", "30UWV", "31UCQ", "30UWA", "30UXA"]
BANDE = 1024   # lignes traitées à la fois (mémoire)


def _rapatrier(url, chemin, essais=8):
    """Copie un fichier distant sur le disque (le module réseau de Python passe par les certificats de
    Windows, ce que GDAL ne sait pas faire ici)."""
    import ssl
    ctx = ssl.create_default_context()
    for essai in range(essais):
        try:
            with urllib.request.urlopen(url, timeout=120, context=ctx) as r, open(chemin, "wb") as f:
                while True:
                    b = r.read(1 << 22)
                    if not b:
                        break
                    f.write(b)
            return
        except Exception:
            time.sleep(min(120, 10 * (essai + 1)))
    raise IOError(f"réseau : {url.split('?')[0][-60:]}")


def telecharger_image(item, annee, normandie):
    """Rapatrie B04, B08 (10 m) et SCL (20 m) d'une image, garde la partie normande en NDVI + SCL,
    puis efface les fichiers bruts."""
    import rasterio
    from rasterio.windows import Window, from_bounds
    f_ndvi, f_scl = fichiers(item, annee)
    if f_ndvi.exists() and f_scl.exists():
        return 0
    f_ndvi.parent.mkdir(parents=True, exist_ok=True)
    emprise = gpd.GeoSeries([shape(item["geometrie"])], crs=4326).to_crs(item["epsg"]).iloc[0]
    zone = normandie.to_crs(item["epsg"]).iloc[0].intersection(emprise)
    if zone.is_empty:
        _ecrire(f_ndvi, np.full((1, 1), 255, np.uint8), rasterio.Affine.identity(), None, 255)
        _ecrire(f_scl, np.zeros((1, 1), np.uint8), rasterio.Affine.identity(), None, 0)
        return 0
    brut = DOSSIER / str(annee) / "_brut"
    brut.mkdir(parents=True, exist_ok=True)
    t = jeton()
    loc = {b: brut / f"{item['id']}_{b}.tif" for b in ("B04", "B08", "SCL")}
    try:
        for b, f in loc.items():
            _rapatrier(f"{item[b]}?{t}", f)
        with rasterio.open(loc["B04"]) as s4, rasterio.open(loc["B08"]) as s8:
            w = from_bounds(*zone.bounds, transform=s4.transform).round_offsets().round_lengths()
            w = w.intersection(Window(0, 0, s4.width, s4.height))
            tr, crs = s4.window_transform(w), s4.crs
            q = np.empty((int(w.height), int(w.width)), np.uint8)
            for l in range(0, int(w.height), BANDE):
                ww = Window(w.col_off, w.row_off + l, w.width, min(BANDE, int(w.height) - l))
                b4 = s4.read(1, window=ww).astype(np.float32)
                b8 = s8.read(1, window=ww).astype(np.float32)
                with np.errstate(divide="ignore", invalid="ignore"):
                    ndvi = (b8 - b4) / (b8 + b4)
                bande = np.clip(np.round((ndvi + 1) * 100), 0, 200)
                bande[(b4 == 0) | (b8 == 0) | ~np.isfinite(ndvi)] = 255
                q[l:l + ww.height] = bande.astype(np.uint8)
        with rasterio.open(loc["SCL"]) as s:
            w = from_bounds(*zone.bounds, transform=s.transform).round_offsets().round_lengths()
            w = w.intersection(Window(0, 0, s.width, s.height))
            scl, tr_scl = s.read(1, window=w), s.window_transform(w)
        _ecrire(f_ndvi, q, tr, crs, 255)
        _ecrire(f_scl, scl.astype(np.uint8), tr_scl, crs, 0)
    finally:
        for f in loc.values():
            f.unlink(missing_ok=True)
    return f_ndvi.stat().st_size + f_scl.stat().st_size


ERREURS_DE_SUITE = 12   # au-delà, la connexion est coupée : on s'arrête (relancer pour reprendre)


def telecharger(annee=2025, travailleurs=6):
    """Toutes les images de l'année ; ce qui est déjà là n'est pas refait (reprise après coupure).
    Ordre : les images les moins nuageuses d'abord, toutes tuiles confondues. Si la connexion coupe
    avant la fin, chaque tuile a déjà ses meilleures images. S'arrête seul si la connexion coupe."""
    items = catalogue(annee)
    normandie = contour()
    journal = DOSSIER / str(annee) / "journal.txt"
    items = sorted((i for i in items if i["tuile"] in TUILES), key=lambda i: (i["nuages"], TUILES.index(i["tuile"])))
    reste = [i for i in items if not all(f.exists() for f in fichiers(i, annee))]
    debut, total, faits, erreurs, de_suite = time.time(), 0, 0, 0, 0
    arret = threading.Event()

    def note(texte):
        print(texte, flush=True)
        with open(journal, "a", encoding="utf-8") as j:
            j.write(time.strftime("%H:%M:%S ") + texte + "\n")

    def une(i):
        if arret.is_set():
            return None
        return telecharger_image(i, annee, normandie)

    note(f"{len(items)} images dans le catalogue, {len(items) - len(reste)} déjà là, {len(reste)} à télécharger")
    with ThreadPoolExecutor(travailleurs) as ex:
        futurs = {ex.submit(une, i): i for i in reste}
        for fu in as_completed(futurs):
            try:
                r = fu.result()
                if r is None:
                    continue
                total += r
                faits += 1
                de_suite = 0
            except Exception as e:
                erreurs += 1
                de_suite += 1
                note(f"ERREUR {futurs[fu]['id']} : {str(e)[:200]}")
                if de_suite >= ERREURS_DE_SUITE and not arret.is_set():
                    arret.set()
                    note("Connexion coupée : arrêt du téléchargement (relancer pour reprendre)")
            if (faits + erreurs) % 10 == 0 and faits + erreurs:
                m = (time.time() - debut) / 60
                note(f"{faits + erreurs} / {len(reste)} images, {erreurs} erreurs, {total / 1e9:.1f} Go gardés, "
                     f"{m:.0f} min (reste environ {m / (faits + erreurs) * (len(reste) - faits - erreurs):.0f} min)")
    note(f"FINI : {faits} images téléchargées, {erreurs} erreurs")
    for f in (DOSSIER / str(annee) / "_brut").glob("*"):
        f.unlink(missing_ok=True)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "telecharger":
        telecharger(int(sys.argv[2]) if len(sys.argv) > 2 else 2025)
    elif len(sys.argv) >= 2 and sys.argv[1] == "tout":
        # Ce qui tourne cette nuit : télécharger tant que la connexion tient, puis tout calculer sans réseau
        a = int(sys.argv[2]) if len(sys.argv) > 2 else 2025
        try:
            telecharger(a)
        finally:
            from .sentinel_nuit import nuit
            nuit(a)
