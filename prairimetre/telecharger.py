"""Téléchargement des sources et tenue du manifest (data/manifest.json).

Chaque fichier écrit dans data/ est tracé : source, date, nombre d'objets, empreinte SHA-256.
Après un téléchargement, les fichiers du cache qui en dépendent sont supprimés.
"""
import hashlib
import json
import re
import shutil
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd
import py7zr
import pyogrio
import requests
import truststore
from py7zr.io import Py7zIO, WriterFactory

from .config import BBOX, CACHE, DATA, MANIFEST, REGION
from .sources import SOURCES, WFS_IGN, ZONAGES_WFS

truststore.inject_into_ssl()  # certificats du système (sinon échec TLS sur data.geopf.fr)
ATOM_IGN = "https://data.geopf.fr/telechargement/resource"
_session = requests.Session()
_session.headers["User-Agent"] = "prairimetre (datathon Normandie 2026)"


class DelaiDepasse(requests.RequestException):
    """La réponse dure plus longtemps que le délai total autorisé."""


def _get(url, duree_max=600, **kw):
    """GET avec nouvel essai. Le délai de requests ne borne que les silences ; un serveur qui
    envoie quelques octets de temps en temps bloquerait sans fin (vu le 25/10 sur le WFS IGN).
    La requête tourne donc dans un fil de travail, abandonné au bout de duree_max secondes."""
    timeout = kw.pop("timeout", 120)
    for essai in range(4):
        resultat = {}

        def requete():
            try:
                r = requests.get(url, timeout=timeout, headers=_session.headers, **kw)
                r.raise_for_status()
                resultat["r"] = r
            except Exception as e:  # transmise au fil principal
                resultat["e"] = e

        fil = threading.Thread(target=requete, daemon=True)
        fil.start()
        fil.join(duree_max)
        try:
            if fil.is_alive():
                raise DelaiDepasse(f"plus de {duree_max} s pour {url}")
            if "e" in resultat:
                raise resultat["e"]
            return resultat["r"]
        except requests.RequestException:
            if essai == 3:
                raise
            time.sleep(5 * (essai + 1))


# --- Service de téléchargement IGN (archives) -----------------------------------------------

def ressources_ign(famille):
    """Noms de toutes les ressources d'une famille (ex. RPG) publiées par l'IGN."""
    noms, page = [], 1
    while True:
        r = _get(f"{ATOM_IGN}/{famille}", params={"page": page, "limit": 50}).text
        noms += re.findall(rf'title="({famille}_[^"]+)"', r)
        total = int(re.search(r'gpf_dl:pagecount="(\d+)"', r).group(1))
        if page >= total:
            return sorted(set(noms))
        page += 1


def trouver_ressource(famille, motif):
    """Ressource IGN correspondant au motif ; GeoPackage préféré au Shapefile."""
    trouve = [n for n in ressources_ign(famille) if re.search(motif, n)]
    if not trouve:
        return None
    return sorted(trouve, key=lambda n: ("GPKG" not in n, n))[0]


def annees_publiees():
    """Millésimes RPG de la région (config.REGION) disponibles au téléchargement."""
    noms = [n for n in ressources_ign("RPG") if REGION in n]
    return sorted({int(m.group(1)) for n in noms if (m := re.search(rf"{REGION}[-_](\d{{4}})", n))})


def _telecharger(url, dest):
    """Téléchargement en flux, sans tout charger en mémoire."""
    with _session.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        taille = int(r.headers.get("Content-Length", 0))
        with open(dest, "wb") as f:
            for i, bloc in enumerate(r.iter_content(1 << 20)):
                f.write(bloc)
                if taille and i % 100 == 0:
                    print(f"\r   {f.tell() / 1e6:,.0f} / {taille / 1e6:,.0f} Mo", end="", flush=True)
    print()


class _Fichier(Py7zIO):
    def __init__(self, chemin):
        self.f, self.n = open(chemin, "wb"), 0

    def write(self, s):
        self.n += len(s)
        return self.f.write(s)

    def read(self, size=None):
        return b""

    def seek(self, offset, whence=0):
        return self.f.seek(offset, whence)

    def flush(self):
        self.f.flush()

    def size(self):
        return self.n

    def close(self):
        self.f.close()


class _APlat(WriterFactory):
    """Écrit chaque membre sous son seul nom (les chemins des archives IGN dépassent
    la limite de longueur de Windows)."""
    def __init__(self, dossier):
        self.dossier, self.ecrits = Path(dossier), {}

    def create(self, nom):
        chemin = self.dossier / Path(nom).name
        self.ecrits[chemin] = _Fichier(chemin)
        return self.ecrits[chemin]


def extraire(archive, membre, dossier):
    """Extrait à plat les membres de l'archive dont le nom correspond au motif."""
    fabrique = _APlat(dossier)
    with py7zr.SevenZipFile(archive) as a:
        cibles = [n for n in a.getnames() if re.search(membre, n)]
        a.extract(targets=cibles, factory=fabrique)
    for f in fabrique.ecrits.values():
        f.f.close()
    return list(fabrique.ecrits)


# --- WFS ----------------------------------------------------------------------------------

def couche_wfs(motif, url):
    """Nom exact d'une couche WFS à partir d'un motif (regex) cherché dans le catalogue."""
    if not any(c in motif for c in "\\[]+*"):
        return motif
    cap = _get(url, params={"SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetCapabilities"}).text
    noms = re.findall(r"<(?:wfs:)?Name>([^<]+)</(?:wfs:)?Name>", cap)
    trouve = [n for n in noms if re.fullmatch(motif, n)]
    return trouve[0] if trouve else None


def wfs(couche, url, bbox=BBOX, page=5000):
    """Tous les objets d'une couche WFS dans l'emprise, par pages."""
    base = {"SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature", "TYPENAMES": couche,
            "BBOX": ",".join(map(str, bbox)) + ",urn:ogc:def:crs:EPSG::2154"}
    n = int(re.search(r'numberMatched="(\d+)"',
                      _get(url, params={**base, "RESULTTYPE": "hits"}).text).group(1))
    morceaux = []
    # Le Sandre n'accepte plus « application/json » (octobre 2026) : variante GeoJSON en repli
    formats = ["application/json", "application/json; subtype=geojson"]
    for debut in range(0, n, page):
        print(f"\r   {couche} : {debut:,} / {n:,} objets", end="", flush=True)
        try:
            r = _get(url, params={**base, "SRSNAME": "EPSG:2154", "OUTPUTFORMAT": formats[0],
                                  "COUNT": page, "STARTINDEX": debut})
        except requests.HTTPError as e:
            if e.response is None or e.response.status_code != 400 or len(formats) == 1:
                raise
            formats.pop(0)
            r = _get(url, params={**base, "SRSNAME": "EPSG:2154", "OUTPUTFORMAT": formats[0],
                                  "COUNT": page, "STARTINDEX": debut})
        j = r.json()["features"]
        g = gpd.GeoDataFrame.from_features(j, crs=2154)
        g["_id"] = [f.get("id") for f in j]
        morceaux.append(g)
    print(f"\r   {couche} : {n:,} objets" + " " * 20)
    g = pd.concat(morceaux, ignore_index=True)
    if g["_id"].notna().all():  # doublons entre pages ; certains serveurs (Sandre) n'ont pas d'id
        g = g.drop_duplicates("_id")
    g = g.drop(columns="_id")
    g.columns = [c.lower() if c != "geometry" else c for c in g.columns]
    return g.set_geometry("geometry")


# --- Normalisation et écriture ---------------------------------------------------------------

def normaliser_rpg(g, annee):
    """Même format pour toutes les années : colonnes en minuscules, colonne annee, code_group entier."""
    g = g.rename(columns={c: c.lower() for c in g.columns if c != "geometry"})
    if g.crs is None or g.crs.to_epsg() != 2154:
        g = g.to_crs(2154)
    g["code_group"] = pd.to_numeric(g["code_group"], errors="coerce").astype("Int64")
    g.insert(0, "annee", annee)
    return g


def _empreinte(f):
    h = hashlib.sha256()
    with open(f, "rb") as fh:
        for bloc in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()[:16]


def noter(nom, fichier, objets, annee=None, **infos):
    """Ajoute ou met à jour une entrée du manifest."""
    m = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    s = SOURCES.get(nom, {})
    e = m.setdefault(nom, {})
    rel = str(fichier.relative_to(DATA)).replace("\\", "/")
    e.update(producteur=s.get("producteur"), licence=s.get("licence"), page=s.get("page"),
             date=datetime.now(timezone.utc).isoformat(timespec="seconds"), **infos)
    e["fichiers"] = sorted(set(e.get("fichiers", [])) | {rel})
    e.setdefault("empreintes", {})[rel] = _empreinte(fichier)
    if annee is None:
        e["objets"] = objets
    else:
        e.setdefault("par_annee", {})[str(annee)] = objets
        e["objets"] = sum(e["par_annee"].values())
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")


def destination(nom, **params):
    """Chemin du fichier d'une source dans data/ ({annee}, {dep}, {millesime} remplacés)."""
    return DATA / SOURCES[nom]["fichier"].format(**params)


def ecrire(g, nom, annee=None, infos=None, **params):
    """Écrit une couche à sa place dans data/, la trace dans le manifest, vide le cache lié."""
    dest = destination(nom, annee=annee, **params)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.stem + ".tmp.gpkg")
    tmp.unlink(missing_ok=True)
    g.to_file(tmp, layer="parcelles" if nom == "rpg" else dest.stem, engine="pyogrio")
    tmp.replace(dest)
    noter(nom, dest, len(g), annee=annee, **(infos or {}))
    invalider(nom, annee, **params)
    print(f"   -> {dest.relative_to(DATA.parent)} ({len(g):,} objets)")
    return dest


def invalider(nom, annee=None, **params):
    """Supprime du cache tout ce qui a été calculé à partir d'une source qui vient de changer.
    Les zonages entrent dans les tables zonages_<année> ; les communes, dans tous les croisements."""
    from .donnees import ZONAGES
    if nom == "rpg":
        motifs = [f"pp_{annee}", f"rpg_{annee}", f"devenir_*{annee}*", f"origine_*{annee}*",
                  f"zonages_{annee}", f"rpg_insee_{annee}", f"cultures_*{annee}*"]
    elif nom == "communes":
        motifs = ["communes_v2", "region", "devenir_*", "origine_*", "zonages_*", "rpg_insee_*",
                  "cultures_*", "carte_*"]
    elif nom in ZONAGES or nom == "plu_zonage":
        motifs = [f"prio_{nom}", "prio_plu_zone_n" if nom == "plu_zonage" else "", "zonages_*",
                  "carte_captages" if nom == "aires_alimentation_captages" else ""]
    elif nom == "habitats_natura2000":
        motifs = ["habitats_prairiaux"]
    elif nom == "ocsge":
        motifs = [f"ocsge_{params.get('dep')}_{params.get('millesime')}"]
    else:
        motifs = [nom]
    for motif in filter(None, motifs):
        for f in CACHE.glob(motif + ".parquet"):
            f.unlink()


def derniere_date(nom):
    """Date du dernier téléchargement ou import d'une source, d'après le manifest."""
    if not MANIFEST.exists():
        return None
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    motif = re.sub(r"\\\{\w+\\\}", "[^/]+", re.escape(SOURCES[nom]["fichier"]))
    dates = [e["date"][:10] for e in m.values() if e.get("date")
             and any(re.fullmatch(motif, f) for f in e.get("fichiers", []))]
    return max(dates, default=None)


# --- Points d'entrée ------------------------------------------------------------------------

def telecharger_rpg(annee):
    s = SOURCES["rpg"]
    nom = trouver_ressource(s["famille"], s["motif"].format(annee=annee))
    if nom is None:
        print(f"   archive {annee} non publiée : essai par le WFS")
        couche = couche_wfs(s["secours"].format(annee=annee), WFS_IGN)
        if couche is None:
            raise SystemExit(f"RPG {annee} introuvable (ni archive, ni WFS).")
        return ecrire(normaliser_rpg(wfs(couche, WFS_IGN), annee),
                      "rpg", annee, infos={"source": f"WFS {couche}"})
    print(f"   archive IGN : {nom}")
    with tempfile.TemporaryDirectory(dir=DATA.parent, prefix="tmp_") as tmp:
        archive = Path(tmp) / "a.7z"
        _telecharger(f"{ATOM_IGN.replace('resource', 'download')}/{s['famille']}/{nom}/{nom}.7z",
                     archive)
        fichiers = extraire(archive, s["membre"], tmp)
        principal = next(f for f in fichiers if f.suffix.lower() in (".gpkg", ".shp"))
        couche = pyogrio.list_layers(principal)[0][0]
        g = gpd.read_file(principal, layer=couche, engine="pyogrio")
        return ecrire(normaliser_rpg(g, annee), "rpg", annee,
                      infos={"source": f"archive IGN {nom}"})


def telecharger_wfs(nom, annee=None):
    s = SOURCES[nom]
    couche = couche_wfs(s["couche"].format(annee=annee), s["url"])
    if couche is None:
        raise SystemExit(f"{nom} {annee or ''} : couche introuvable sur {s['url']}")
    g = wfs(couche, s["url"])
    if nom == "pp_officiel":
        # Même périmètre que le RPG régional : num_parcel = id_parcel du RPG de l'année
        rpg = DATA / SOURCES["rpg"]["fichier"].format(annee=annee)
        ids = set(pyogrio.read_dataframe(rpg, read_geometry=False, columns=["id_parcel"])
                  .id_parcel.astype(str))
        g = g[g.num_parcel.astype(str).isin(ids)]
    else:
        from .donnees import region
        g = g[g.intersects(region().geometry.iloc[0])]
    return ecrire(g, nom, annee, infos={"source": f"WFS {couche}"})


def telecharger(nom, annee=None):
    if nom == "zonages":  # toutes les couches de zonage en une fois
        for z in ZONAGES_WFS:
            try:
                telecharger(z)
            except Exception as e:  # un service en panne ne bloque pas les autres
                print(f"   ÉCHEC {z} : {type(e).__name__} — fichier actuel conservé")
        return None
    if nom not in SOURCES:
        raise SystemExit(f"Source inconnue : « {nom} ». Sources possibles : zonages, "
                         + ", ".join(SOURCES))
    s = SOURCES[nom]
    print(f"\n== {nom} {annee or ''}")
    if s["annuelle"] and annee is None:
        raise SystemExit(f"{nom} est annuelle : préciser --annee.")
    if s["mode"] == "manuel":
        print(f"   Pas de téléchargement automatique. Récupérer le fichier sur {s['page']}\n"
              f"   puis : python -m prairimetre importer {nom} <fichier>")
        return None
    if nom == "rpg":
        return telecharger_rpg(annee)
    if s["mode"] == "api_json":
        return telecharger_api(nom)
    return telecharger_wfs(nom, annee)


def telecharger_api(nom):
    """Table JSON d'une API ouverte, écrite en CSV."""
    s = SOURCES[nom]
    t = pd.DataFrame(_get(s["url"]).json())
    # listes (ex. plusieurs codes postaux pour une commune) : valeurs séparées par une espace
    t = t.apply(lambda c: c.map(lambda v: " ".join(map(str, v)) if isinstance(v, list) else v))
    dest = destination(nom)
    dest.parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(dest, index=False)
    noter(nom, dest, len(t), source=s["url"])
    invalider(nom)
    print(f"   -> {dest.relative_to(DATA.parent)} ({len(t):,} lignes)")
    return dest


def nettoyer_tmp():
    for d in DATA.parent.glob("tmp_*"):
        shutil.rmtree(d, ignore_errors=True)
