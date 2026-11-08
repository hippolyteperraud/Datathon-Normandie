"""Vérification automatique par images Sentinel-2 : l'herbe est-elle encore là ?

Données ouvertes, sans compte : les images Sentinel-2 niveau 2A (programme Copernicus de l'Union
européenne, licence ouverte) servies par le catalogue public de Microsoft Planetary Computer.
Pour chaque parcelle et chaque image de l'année, le service calcule sur le contour de la parcelle :
- la carte de classification de scène (SCL, ESA), qui sert à écarter les nuages et les ombres ;
- le NDVI moyen, (proche infrarouge B08 − rouge B04) / (B08 + B04).
Une image est « sans nuage » si nuages, ombres et pixels manquants couvrent moins de 5 % de la
parcelle.

Comment la règle a été choisie (tout est gardé dans le fichier de preuves) :
1. Une première règle, fixée à l'avance (une seule image en sol nu suffit à dire « labourée »), a
   été testée sur 40 témoins dont le registre donne la réponse. Elle a échoué : 11 prairies sur 20
   vues labourées, à cause d'images isolées que la classification de l'ESA met à tort en sol nu.
2. La règle a été corrigée sur ces 40 témoins (« réglage ») pour ne plus dépendre d'une image
   isolée : elle regarde le bas de la distribution du NDVI sur l'année.
3. Elle est validée sur 40 AUTRES témoins tirés au hasard, jamais regardés avant (« validation ») :
   c'est ce taux d'erreur qui est annoncé.

Règle retenue, sur les images sans nuage de l'année (au moins 6) :
- « bâti ou minéral » : NDVI médian sous 0,25 et jamais au-dessus de 0,40 ;
- « labourée » : au moins 3 images au NDVI sous 0,25, ou 10e centile du NDVI sous 0,27 ;
- « couvert permanent » : 10e centile du NDVI d'au moins 0,36 et au plus une image sous 0,25.
  Une prairie, une friche herbacée, une luzerne ou un boisement donnent ce signal : le satellite
  ne les sépare pas sûrement ;
- sinon : « indéterminé » (zone grise, non comptée).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
DOSSIER = RACINE / "verification" / "sentinel2"
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
DONNEES = "https://planetarycomputer.microsoft.com/api/data/v1/item"
COLLECTION = "sentinel-2-l2a"
GRAINE = 2026              # tirages au hasard reproductibles
GRAINE_VALIDATION = 2027

PROPRE_MAX = 0.05          # part maximale de nuages, ombres, pixels manquants sur la parcelle
IMAGES_MIN = 6
NDVI_BAS = 0.25            # sous ce NDVI, l'image montre du sol nu
IMAGES_BASSES_LABOUR = 3   # à partir de 3 images basses : labour
Q10_LABOUR = 0.27          # 10e centile du NDVI sous ce seuil : labour
Q10_COUVERT = 0.36         # 10e centile du NDVI au-dessus : couvert permanent
NDVI_VERT = 0.40
# Première règle, abandonnée (gardée pour les preuves)
AVANT_NU_MIN, AVANT_PART_VERTE = 0.5, 0.8
# Classes SCL (ESA) à écarter : manquant, défaut, ombre de nuage, nuages, cirrus, neige
SCL_SALE = {0, 1, 3, 8, 9, 10, 11}
SCL_NU = 5


# --- Accès au service -------------------------------------------------------------------------
def _post(url, corps, essais=4):
    """Une requête ; on réessaie si le réseau flanche. Une réponse d'erreur du serveur (HTTP) n'est
    réessayée qu'une fois : elle tient d'ordinaire à l'image elle-même ; sauf « trop de requêtes »
    (429), qui tient au débit : on attend et on réessaie comme pour le réseau."""
    req = urllib.request.Request(url, json.dumps(corps).encode(), {"Content-Type": "application/json"})
    for i in range(essais):
        try:
            return json.load(urllib.request.urlopen(req, timeout=45))
        except urllib.error.HTTPError as e:
            if i == essais - 1 or (e.code != 429 and i >= 1):
                raise
            time.sleep(10 * (i + 1) if e.code == 429 else 2)
        except Exception:
            if i == essais - 1:
                raise
            time.sleep(2 * (i + 1))


def images(geometrie, annee, nuages_max=40):
    """Images Sentinel-2 de l'année qui couvrent la parcelle : pour chaque date, la liste des images
    (une par tuile ; une parcelle au bord de deux tuiles en a deux)."""
    corps = {"collections": [COLLECTION], "intersects": geometrie,
             "datetime": f"{annee}-01-01/{annee}-12-31",
             "query": {"eo:cloud_cover": {"lt": nuages_max}}, "limit": 300}
    par_date = {}
    for f in sorted(_post(STAC, corps)["features"], key=lambda f: f["properties"]["datetime"]):
        par_date.setdefault(f["properties"]["datetime"][:10], []).append(f["id"])
    return list(par_date.items())


def mesurer(item, geometrie):
    """Pour une image et une parcelle : parts SCL (nuages ? sol nu ?) puis NDVI moyen si l'image
    est sans nuage."""
    feat = {"type": "Feature", "geometry": geometrie, "properties": {}}
    base = f"{DONNEES}/statistics?collection={COLLECTION}&item={item}"
    scl = _post(base + "&assets=SCL&categorical=true", feat)["properties"]["statistics"]["SCL_b1"]
    valeurs, effectifs = scl["histogram"][1], scl["histogram"][0]
    total = scl["count"]  # pixels dans la parcelle (les « masqués » sont hors du contour)
    parts = {int(v): n / total for v, n in zip(valeurs, effectifs)} if total else {}
    sale = sum(p for v, p in parts.items() if v in SCL_SALE) if total else 1.0
    utile = 1 - sale
    nu = parts.get(SCL_NU, 0) / utile if utile > 0 else float("nan")
    ndvi = float("nan")
    if sale < PROPRE_MAX:
        expr = urllib.parse.urlencode({"expression": "(B08-B04)/(B08+B04)", "asset_as_band": "true"})
        s = _post(f"{base}&{expr}", feat)["properties"]["statistics"]
        ndvi = next(iter(s.values()))["mean"]
    return {"item": item, "part_sale": sale, "part_sol_nu": nu, "ndvi": ndvi}


def _tuile(item):
    return item.split("_")[4] if item.count("_") >= 4 else item


def profil(geometrie, annee):
    """Une ligne par date de l'année : date, image, parts SCL, NDVI (images sans nuage). Au bord de
    deux tuiles, le service refuse souvent l'une d'elles (erreur HTTP) : on prend alors l'autre, et
    la tuile refusée passe en dernier pour les dates suivantes. Une date où toutes les tuiles sont
    refusées reste tracée (erreur « HTTP … ») et ne compte pas ; une coupure du réseau est notée
    « réseau : … » et fait reprendre la parcelle."""
    lignes, refusees = [], set()
    for date, items in images(geometrie, annee):
        items = sorted(items, key=lambda i: _tuile(i) in refusees)
        for k, item in enumerate(items):
            try:
                lignes.append({"date": date, **mesurer(item, geometrie)})
                break
            except urllib.error.HTTPError as e:
                refusees.add(_tuile(item))
                if k == len(items) - 1:
                    lignes.append({"date": date, "item": item, "erreur": f"HTTP {e.code}"})
            except Exception as e:
                lignes.append({"date": date, "item": item, "erreur": f"réseau : {str(e)[:100]}"})
                break
    return pd.DataFrame(lignes)


def _reseau_coupe(p):
    """Vrai si le profil a souffert d'une coupure du réseau (la parcelle sera reprise)."""
    return "erreur" in p and p.erreur.fillna("").str.startswith("réseau").any()


# --- Herbe ou friche ? La carte annuelle d'occupation du sol (Impact Observatory, 10 m, ouverte) -----
# Elle range les prairies entretenues (fauchées, pâturées) avec les cultures : seule, elle ne sépare
# pas l'herbe des cultures (testé sur les témoins). Mais une parcelle verte toute l'année, sans
# labour, rangée en « végétation basse entretenue », est une prairie ; « herbe et broussailles » peut
# être une prairie extensive ou une friche ; « arbres » est un boisement ou une friche ligneuse.
IO_COLLECTION, IO_ANNEE = "io-lulc-annual-v02", 2023
IO_CLASSES = {1: "eau", 2: "arbres", 4: "végétation inondée", 5: "végétation basse entretenue",
              7: "bâti", 8: "sol nu", 11: "herbe et broussailles"}


def occupation(geometrie, annee=IO_ANNEE):
    """Classe d'occupation du sol majoritaire sur la parcelle, l'année donnée."""
    items = _post(STAC, {"collections": [IO_COLLECTION], "intersects": geometrie,
                         "datetime": f"{annee}-01-01/{annee}-12-31", "limit": 1})["features"]
    if not items:
        return None
    st = _post(f"{DONNEES}/statistics?collection={IO_COLLECTION}&item={items[0]['id']}"
               "&assets=data&categorical=true", {"type": "Feature", "geometry": geometrie,
                                                 "properties": {}})["properties"]["statistics"]
    h = next(iter(st.values()))["histogram"]
    return IO_CLASSES.get(int(h[1][int(np.argmax(h[0]))]), "autre") if sum(h[0]) else None


# --- La règle -----------------------------------------------------------------------------------
def _propres(p):
    if p.empty or "part_sale" not in p:
        return p.iloc[0:0]
    return p[(p.part_sale < PROPRE_MAX) & p.ndvi.notna()]


def classer(p):
    """État d'une parcelle d'après ses images sans nuage de l'année, et la raison en clair."""
    propres = _propres(p)
    n = len(propres)
    if n < IMAGES_MIN:
        return "indéterminé", f"{n} images sans nuage, il en faut {IMAGES_MIN}"
    v = propres.ndvi
    q10, basses = v.quantile(0.1), int((v < NDVI_BAS).sum())
    detail = (f"{n} images, NDVI : 10e centile {q10:.2f}, {basses} sous {NDVI_BAS:.2f}"
              .replace(".", ","))
    if v.median() < NDVI_BAS and v.max() < NDVI_VERT:
        return "bâti ou minéral", detail
    if basses >= IMAGES_BASSES_LABOUR or q10 < Q10_LABOUR:
        d = propres.loc[v.idxmin()]
        return "labourée", f"{detail} ; le plus bas le {d.date} ({d.ndvi:.2f})".replace("0.", "0,")
    if q10 >= Q10_COUVERT and basses <= 1:
        return "couvert permanent", detail
    return "indéterminé", f"{detail} (zone grise)"


def classer_avant(p):
    """La première règle, abandonnée : une seule image en sol nu suffisait à dire « labourée »."""
    propres = _propres(p)
    if len(propres) < IMAGES_MIN:
        return "indéterminé"
    labour = propres[(propres.part_sol_nu > AVANT_NU_MIN) | (propres.ndvi < NDVI_BAS)]
    if len(labour) and propres.ndvi.max() >= NDVI_VERT:
        return "labourée"
    if propres.ndvi.median() < NDVI_BAS:
        return "bâti ou minéral"
    if not len(labour) and (propres.ndvi >= NDVI_VERT).mean() >= AVANT_PART_VERTE:
        return "couvert permanent"
    return "indéterminé"


# --- Les échantillons ----------------------------------------------------------------------------
def _tirer(masque, long, p22, n, graine, nom, exclure=()):
    idx = long.index[masque.values]
    reste = pd.Series(idx[~idx.isin(list(exclure))])
    tires = reste.sample(min(n, len(reste)), random_state=graine).values
    g = p22.loc[tires, ["id_parcel", "geometry"]].copy()
    g["groupe"], g["insee"], g["ha"] = nom, long.loc[tires, "insee"].values, long.loc[tires, "ha"].values
    g["population"], g["population_ha"] = len(idx), long.loc[idx, "ha"].sum()
    return g


def echantillons(n_temoins=20, n_2023=40):
    """Parcelles d'au moins 1 ha, tirées au hasard (graines fixes) :
    - réglage et validation, prairies : prairies de 2022 encore déclarées en prairie permanente en 2025 ;
    - réglage et validation, cultures : prairies de 2022 déclarées en culture en 2025 ;
    - « sortie 2023 » : prairies de 2022 sorties entières de la déclaration en 2023 et toujours
      hors déclaration en 2025 (celles dont dépend l'écart à l'objectif 2030) ;
    - les 30 parcelles tirées pour la vérification à la main (sorties entre 2018 et 2025)."""
    import geopandas as gpd

    from .donnees import prairies
    from .satellite import PARCELLES_30
    from .suivi import devenir
    p22 = prairies(2022)
    court, long = devenir(2022, 2023), devenir(2022, 2025)
    ok = long.insee.notna() & (long.ha >= 1)
    prairie = ok & (long["prairie permanente"] > 0.95 * long.ha)
    culture = ok & (long.culture > 0.95 * long.ha)
    sortie = ok & (court["non déclaré"] > 0.9 * court.ha) & (long["non déclaré"] > 0.9 * long.ha)
    reg_p = _tirer(prairie, long, p22, n_temoins, GRAINE, "réglage prairie")
    reg_c = _tirer(culture, long, p22, n_temoins, GRAINE, "réglage culture")
    morceaux = [reg_p, reg_c,
                _tirer(prairie, long, p22, n_temoins, GRAINE_VALIDATION, "validation prairie",
                       exclure=reg_p.index),
                _tirer(culture, long, p22, n_temoins, GRAINE_VALIDATION, "validation culture",
                       exclure=reg_c.index),
                _tirer(sortie, long, p22, n_2023, GRAINE, "sortie 2023")]
    p18 = prairies(2018)
    ids = {str(p[6]): p[0] for p in PARCELLES_30}
    m = p18[p18.id_parcel.astype(str).isin(ids)][["id_parcel", "geometry"]].copy()
    m["groupe"], m["numero"] = "30 parcelles", m.id_parcel.astype(str).map(ids)
    m["ha"] = m.geometry.area / 1e4
    morceaux.append(m)
    return gpd.GeoDataFrame(pd.concat(morceaux, ignore_index=True), geometry="geometry", crs=p22.crs)


def verifier(annee=2025, travailleurs=6):
    """Mesure toutes les parcelles des échantillons sur l'année et écrit les preuves dans
    verification/sentinel2/ : parcelles.csv (une ligne par parcelle : état, raison, état selon la
    première règle) et images.csv (une ligne par parcelle et par image, la trace de chaque mesure).
    Les parcelles déjà mesurées (images.csv) ne sont pas redemandées au service."""
    DOSSIER.mkdir(parents=True, exist_ok=True)
    e = echantillons().reset_index(drop=True)
    e["id_rpg"] = e.id_parcel.astype(str)
    wgs = e.to_crs(4326)
    deja = {}
    f_images = DOSSIER / "images.csv"
    if f_images.exists():
        im = pd.read_csv(f_images, dtype={"id_rpg": str})
        deja = {k: g.drop(columns=["groupe", "id_rpg"]) for k, g in im.groupby("id_rpg")}

    def un(i):
        k = e.id_rpg[i]
        geo = json.loads(json.dumps(wgs.geometry[i].__geo_interface__))
        try:
            occ = occupation(geo)
        except Exception:
            occ = None
        return i, (deja[k] if k in deja else profil(geo, annee)), occ

    with ThreadPoolExecutor(travailleurs) as pool:
        resultats = {i: (p, o) for i, p, o in pool.map(un, range(len(e)))}
    profils = {i: p for i, (p, _) in resultats.items()}
    lignes, traces = [], []
    for i, r in e.iterrows():
        p = profils[i]
        etat, raison = classer(p)
        c = wgs.geometry[i].representative_point()
        lignes.append({"groupe": r.groupe, "id_rpg": r.id_rpg,
                       "numero": r.numero if pd.notna(r.get("numero")) else None,
                       "insee": r.insee if pd.notna(r.get("insee")) else None, "ha": round(r.ha, 2),
                       "latitude": round(c.y, 5), "longitude": round(c.x, 5),
                       "images": len(p), "images_sans_nuage": len(_propres(p)),
                       "etat": etat, "raison": raison, "etat_premiere_regle": classer_avant(p),
                       f"occupation_{IO_ANNEE}": resultats[i][1],
                       "population": r.get("population"), "population_ha": r.get("population_ha")})
        if len(p):
            traces.append(p.assign(groupe=r.groupe, id_rpg=r.id_rpg))
    t = pd.DataFrame(lignes)
    t.to_csv(DOSSIER / "parcelles.csv", index=False, encoding="utf-8")
    pd.concat(traces).to_csv(f_images, index=False, encoding="utf-8")
    (DOSSIER / "parametres.json").write_text(json.dumps({
        "annee_images": annee, "source": "Sentinel-2 L2A (Copernicus), Microsoft Planetary Computer",
        "stac": STAC, "donnees": DONNEES, "graines": [GRAINE, GRAINE_VALIDATION],
        "propre_max": PROPRE_MAX, "images_min": IMAGES_MIN, "ndvi_bas": NDVI_BAS,
        "images_basses_labour": IMAGES_BASSES_LABOUR, "q10_labour": Q10_LABOUR,
        "q10_couvert": Q10_COUVERT, "date_calcul": time.strftime("%Y-%m-%d")},
        ensure_ascii=False, indent=2), encoding="utf-8")
    return t


# --- Le résultat --------------------------------------------------------------------------------
def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 1.0
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    m = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, c - m), min(1.0, c + m)


def _temoins(t, etape, colonne="etat"):
    p, c = t[t.groupe == f"{etape} prairie"][colonne], t[t.groupe == f"{etape} culture"][colonne]
    return {"prairies": len(p), "cultures": len(c),
            "prairie_couvert": int((p == "couvert permanent").sum()),
            "prairie_labouree": int((p == "labourée").sum()),
            "prairie_indet": int((p == "indéterminé").sum()),
            "culture_labouree": int((c == "labourée").sum()),
            "culture_couvert": int((c == "couvert permanent").sum()),
            "culture_indet": int((c == "indéterminé").sum())}


def bilan(t):
    """Taux d'erreur sur les témoins (première règle, réglage, validation), part en couvert
    permanent dans chaque groupe avec son intervalle à 95 %, hectares pour les sorties de 2023.
    L'erreur de la règle compte aussi dans la fourchette : elle est élargie par les erreurs
    mesurées en validation."""
    out = {"premiere_regle": _temoins(t, "réglage", "etat_premiere_regle"),
           "reglage": _temoins(t, "réglage"), "validation": _temoins(t, "validation")}
    v = out["validation"]
    # Erreurs croisées en validation : une prairie vue labourée, une culture vue en couvert
    out["erreurs_validation"] = v["prairie_labouree"] + v["culture_couvert"]
    out["tranchees_validation"] = (v["prairies"] - v["prairie_indet"]) + (v["cultures"] - v["culture_indet"])
    col = f"occupation_{IO_ANNEE}"
    if col in t:
        vertes = t[(t.groupe == "sortie 2023") & (t.etat == "couvert permanent")]
        out["occupation_vertes_2023"] = vertes[col].fillna("inconnue").value_counts().to_dict()
    f_photos = DOSSIER / "photo_interpretation.csv"
    if f_photos.exists():
        ph = pd.read_csv(f_photos, dtype={"id_rpg": str})
        out["photos"] = ph.lecture.value_counts().to_dict()
    for g in ("sortie 2023", "30 parcelles"):
        s = t[t.groupe == g]
        tranchees = s[s.etat != "indéterminé"]
        k, n = int((tranchees.etat == "couvert permanent").sum()), len(tranchees)
        bas, haut = wilson(k, n)
        pop = s.population_ha.dropna()
        out[g] = {"parcelles": len(s), "tranchees": n, "couvert": k,
                  "labourees": int((tranchees.etat == "labourée").sum()),
                  "bati": int((tranchees.etat == "bâti ou minéral").sum()),
                  "part": k / n if n else float("nan"), "bas": bas, "haut": haut,
                  "population_ha": float(pop.iloc[0]) if len(pop) else None}
    return out


# --- Le fichier de preuves ------------------------------------------------------------------------
def _liens(lat, lon):
    cop = f"https://browser.dataspace.copernicus.eu/?zoom=16&lat={lat}&lng={lon}"
    ign = (f"https://www.geoportail.gouv.fr/carte?c={lon},{lat}&z=17"
           "&l0=ORTHOIMAGERY.ORTHOPHOTOS::GEOPORTAIL:OGC:WMTS(1)&permalink=yes")
    return f"[Sentinel-2]({cop}) · [photo IGN]({ign})"


def _n(k, mot):
    """« 1 vue », « 3 vues » : accord du mot qui suit le nombre."""
    return f"{k} {mot}{'s' if k > 1 else ''}"


def _ligne_temoins(x):
    return (f"- prairies (encore déclarées en prairie permanente) : **{x['prairie_couvert']} sur "
            f"{x['prairies']}** vues en couvert permanent, **{_n(x['prairie_labouree'], 'vue')} "
            f"labourée{'s' if x['prairie_labouree'] > 1 else ''} à tort**, "
            f"{_n(x['prairie_indet'], 'indéterminée')} ;\n"
            f"- cultures (prairies devenues cultures) : **{x['culture_labouree']} sur {x['cultures']}** "
            f"vues labourées, **{_n(x['culture_couvert'], 'vue')} en couvert à tort**, "
            f"{_n(x['culture_indet'], 'indéterminée')}.")


def ecrire_preuves(t=None):
    """verification/sentinel2/preuves.md : comment la règle a été choisie, ses erreurs mesurées,
    les résultats avec leur marge d'erreur, et une ligne par parcelle avec de quoi la revérifier."""
    if t is None:
        t = pd.read_csv(DOSSIER / "parcelles.csv", dtype={"insee": str, "id_rpg": str})
    par = json.loads((DOSSIER / "parametres.json").read_text(encoding="utf-8"))
    b = bilan(t)
    f = lambda x: f"{x:,.0f}".replace(",", " ")
    v = lambda x: f"{x:.2f}".replace(".", ",")
    l = [f"# Preuves : vérification par images Sentinel-2 ({par['annee_images']})", "",
         f"Calcul du {par['date_calcul']}. Images : {par['source']}, ouvertes, sans compte. Code : "
         "`prairimetre/sentinel.py`. Refaire : `python scripts/analyser_satellite_sentinel.py --sentinel`.",
         "", "Les témoins sont des parcelles dont le registre lui-même donne la réponse en "
         f"{par['annee_images']}.", "",
         "## 1. Première règle, fixée à l'avance : abandonnée", "",
         "Une seule image en sol nu suffisait à dire « labourée ». Sur les 40 témoins de réglage :", "",
         _ligne_temoins(b["premiere_regle"]), "",
         "Cause : certains jours (le 12 janvier 2025 surtout), la classification de l'ESA met des "
         "prairies en sol nu. Une image isolée ne suffit donc pas.", "",
         "## 2. Règle corrigée sur ces 40 témoins (réglage)", "",
         "Elle regarde le bas de la distribution du NDVI sur l'année (10e centile, nombre d'images "
         f"sous {v(par['ndvi_bas'])}) : labourée si au moins {par['images_basses_labour']} images sous "
         f"{v(par['ndvi_bas'])} ou 10e centile sous {v(par['q10_labour'])} ; couvert permanent si 10e "
         f"centile d'au moins {v(par['q10_couvert'])} ; entre les deux, indéterminé.", "",
         _ligne_temoins(b["reglage"]), "",
         "Ces chiffres sont flatteurs : la règle a été choisie en les regardant.", "",
         "## 3. Validation sur 40 autres témoins, jamais regardés : le vrai taux d'erreur", "",
         _ligne_temoins(b["validation"]), "",
         f"**{b['erreurs_validation']} erreurs sur {b['tranchees_validation']} parcelles tranchées.** "
         "Les indéterminées ne sont comptées ni d'un côté ni de l'autre.", ""]
    for g, titre in (("sortie 2023", "4. Les prairies sorties de la PAC en 2023, toujours hors "
                                     "déclaration en 2025"),
                     ("30 parcelles", "5. Les 30 parcelles de la vérification à la main (sorties "
                                      "entre 2018 et 2025)")):
        r = b[g]
        l += [f"## {titre}", "",
              f"{r['parcelles']} parcelles regardées, {r['tranchees']} tranchées : "
              f"**{r['couvert']} en couvert permanent**, {r['labourees']} labourées, {r['bati']} bâties "
              "ou minérales."]
        if r["tranchees"]:
            l.append(f"Part en couvert permanent : **{100 * r['part']:.0f} %** (intervalle à 95 % : "
                     f"{100 * r['bas']:.0f} à {100 * r['haut']:.0f} %, sans compter l'erreur de la règle).")
        if r.get("population_ha"):
            l.append(f"Rapportée aux {f(r['population_ha'])} ha de la population tirée (parcelles d'au "
                     f"moins 1 ha) : entre {f(r['bas'] * r['population_ha'])} et "
                     f"{f(r['haut'] * r['population_ha'])} ha encore couverts.")
        l.append("")
    occ, ph = b.get("occupation_vertes_2023"), b.get("photos")
    if occ:
        l += ["## Herbe ou friche ?", "",
              f"Les prairies sorties en 2023 restées vertes, selon la carte annuelle d'occupation du sol "
              f"d'Impact Observatory ({IO_ANNEE}, 10 m, licence CC-BY) : "
              + ", ".join(f"{v} {k}" for k, v in occ.items()) + ". Cette carte range les prairies "
              "entretenues avec les cultures (testé : 35 témoins prairie sur 40) ; sans labour vu par "
              "Sentinel-2, « végétation basse entretenue » veut donc dire prairie fauchée ou pâturée."]
        if ph:
            l.append("Les cas douteux (« herbe et broussailles », « bâti ») ont été regardés sur la photo "
                     "aérienne de l'IGN (`photos/`, `photo_interpretation.csv`, lecture par Claude, "
                     "assistant IA, à confirmer) : " + ", ".join(f"{v} {k}" for k, v in ph.items()) + ".")
        l.append("")
    l += ["## 6. Limites", "",
          "- « Couvert permanent » veut dire : vert toute l'année, sans période de sol nu. Une prairie, "
          "une friche, une luzerne ou un jeune boisement donnent ce signal. Les liens vers la photo IGN "
          "permettent de trancher à l'œil.",
          "- Le contour est celui de la parcelle déclarée avant la sortie ; s'il a changé, le bord peut "
          "mélanger deux usages.",
          f"- Une seule année d'images ({par['annee_images']}) : un labour d'une autre année ne se voit pas.",
          "- Parcelles d'au moins 1 ha : en dessous, trop peu de pixels de 10 m.",
          "- Échantillons tirés au hasard : la marge d'erreur dépend du nombre de parcelles tranchées.",
          "", "## 7. Parcelle par parcelle", "",
          "| groupe | parcelle RPG | commune | ha | images sans nuage | état | raison | 1re règle | revoir |",
          "|---|---|---|---|---|---|---|---|---|"]
    for _, r in t.iterrows():
        commune = r.insee if isinstance(r.insee, str) else (f"n° {int(r.numero)}" if pd.notna(r.numero) else "")
        l.append(f"| {r.groupe} | {r.id_rpg} | {commune} | {r.ha:.1f} | {r.images_sans_nuage} | "
                 f"{r.etat} | {r.raison} | {r.etat_premiere_regle} | {_liens(r.latitude, r.longitude)} |")
    l += ["", "Chaque mesure (date, image, part de nuages, part de sol nu, NDVI) est dans "
          "`images.csv` ; les réglages dans `parametres.json`."]
    (DOSSIER / "preuves.md").write_text("\n".join(l) + "\n", encoding="utf-8")
    return DOSSIER / "preuves.md"


# --- Toutes les prairies sorties de la déclaration -------------------------------------------------
def periode():
    """Première et dernière année du registre installé : les prairies de la première année, sorties de
    la déclaration la dernière, sont regardées sur les images de la dernière."""
    from .config import annees
    A = annees()
    return A[0], A[-1]


def bloc(annee=None):
    """Les deux fichiers du bloc des mesures pour une année d'images : (parcelles, images). Les images
    (une ligne par parcelle et par image, ~600 000 lignes) sont compressées sans perte (gzip, lu et
    complété directement par pandas)."""
    annee = annee or periode()[1]
    return DOSSIER / str(annee) / "parcelles.csv", DOSSIER / str(annee) / "images.csv.gz"


def mesures(annee=None):
    """Le bloc des mesures d'une année (une ligne par parcelle), vide s'il n'existe pas."""
    f = bloc(annee)[0]
    if not f.exists():
        return pd.DataFrame(columns=["id_rpg", "insee", "ha", "etat"])
    return pd.read_csv(f, dtype={"insee": str, "id_rpg": str}).drop_duplicates("id_rpg")


def communes_a_aller_voir():
    """Les communes qui portent la moitié des sorties de la déclaration (comme la page Où aller voir),
    prioritaires d'abord : celles qui ne sont pas dans la liste des communes où l'on retourne le plus,
    où la réponse peut changer la décision."""
    from .config import SORTIES
    t = pd.read_csv(SORTIES / "communes.csv", dtype={"insee": str}).set_index("insee")
    calc = t[t.statut == "calculé"]
    rang = calc.devenues_non_declare.sort_values(ascending=False)
    moitie = list(rang.index[:int((rang.cumsum() / rang.sum() < 0.5).sum() + 1)])
    ret = calc.retourne_recent.sort_values(ascending=False)
    liste = set(ret.index[:int((ret.cumsum() / ret.sum() < 0.5).sum() + 1)])
    return [i for i in moitie if i not in liste], [i for i in moitie if i in liste]


# Le bloc des mesures satellite, rangé par année d'images (verification/sentinel2/<année>/) : une ligne
# par parcelle (parcelles.csv), une ligne par parcelle et par image (images.csv.gz). Une parcelle déjà
# mesurée n'est jamais redemandée : relancer sur d'autres communes ne mesure que les nouvelles parcelles.
FICHIER_VERROU = DOSSIER / "en_cours.json"
VERROU_PERIME_S = 600     # sans nouvelle depuis 10 min, le calcul est considéré comme arrêté
SECONDES_PAR_PARCELLE = 3.5  # mesuré : environ 17 parcelles par minute avec 10 requêtes parallèles


def parcelles_cibles(insees=None):
    """Les prairies de la première année d'au moins 1 ha, sorties à 90 % ou plus de la déclaration la
    dernière année, dans les communes données (toutes par défaut) : index de prairies(première année),
    commune et surface (sans géométrie)."""
    from .suivi import devenir
    a0, an = periode()
    d = devenir(a0, an)
    if insees is None:
        insees = d.insee.dropna().unique()
    m = d.insee.isin(list(insees)) & (d.ha >= 1) & (d["non déclaré"] > 0.9 * d.ha)
    return d.loc[m.values, ["insee", "ha"]]


def deja_mesurees(annee=None):
    """Identifiants des parcelles déjà dans le bloc des mesures de l'année d'images."""
    return set(mesures(annee).id_rpg)


def avancement():
    """Le calcul en cours, s'il y en a un (lu par l'application) : None sinon."""
    if not FICHIER_VERROU.exists():
        return None
    try:
        a = json.loads(FICHIER_VERROU.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    return a if time.time() - a.get("maj", 0) < VERROU_PERIME_S else None


def _noter_avancement(**champs):
    a = {**(json.loads(FICHIER_VERROU.read_text(encoding="utf-8")) if FICHIER_VERROU.exists() else {}),
         **champs, "maj": time.time()}
    FICHIER_VERROU.write_text(json.dumps(a, ensure_ascii=False), encoding="utf-8")


COLONNES_IMAGES = ["date", "item", "part_sale", "part_sol_nu", "ndvi", "erreur", "id_rpg"]
ECHECS_DE_SUITE = 30     # au-delà, la connexion est sans doute coupée : pause, puis nouvel essai
PAUSE_S = 600
ESSAIS_MAX = 150         # 150 pauses de 10 min : on attend la connexion jusqu'à 25 h


def verifier_communes(insees=None, annee=None, travailleurs=10):
    """Mesure, image par image, chaque prairie sortie de la déclaration (voir parcelles_cibles) dans
    les communes données ; par défaut toutes. Seules les parcelles absentes du bloc sont mesurées ;
    chacune y est écrite aussitôt, et seulement si toutes ses images ont été lues (sinon elle est
    reprise). Si la connexion coupe (beaucoup d'échecs de suite), le calcul fait une pause de 10 min
    et réessaie, jusqu'à ce que tout soit mesuré. Un seul calcul à la fois (verrou en_cours.json,
    qui sert aussi à suivre l'avancement)."""
    import threading

    from .donnees import prairies
    if avancement():
        raise SystemExit("Une vérification satellite est déjà en cours : attendre qu'elle finisse.")
    a0, an = periode()
    annee = annee or an
    f_parcelles, f_images = bloc(annee)
    f_parcelles.parent.mkdir(parents=True, exist_ok=True)
    prio, second = communes_a_aller_voir()
    if insees is None:
        insees = prio + second
    cibles = parcelles_cibles(insees)
    g = prairies(a0).loc[cibles.index, ["id_parcel", "geometry"]].copy()
    g["insee"], g["ha"] = cibles.insee.values, cibles.ha.values
    g["priorite"] = np.select([g.insee.isin(prio), g.insee.isin(second)],
                              ["prioritaire", "secondaire"], "autre")
    g["id_rpg"] = g.id_parcel.astype(str)
    verrou = threading.Lock()
    etat_calcul = {"faits": 0, "echecs_de_suite": 0, "coupe": False}

    def un(r, geo, point):
        if etat_calcul["coupe"]:
            return
        try:
            p = profil(geo, annee)
        except Exception as e:  # le catalogue ne répond pas : la parcelle sera reprise
            p = pd.DataFrame([{"erreur": f"réseau : {str(e)[:100]}"}])
        if _reseau_coupe(p):  # coupure du réseau : on reprendra la parcelle
            with verrou:
                etat_calcul["echecs_de_suite"] += 1
                if etat_calcul["echecs_de_suite"] >= ECHECS_DE_SUITE:
                    etat_calcul["coupe"] = True
                if etat_calcul["echecs_de_suite"] in (1, ECHECS_DE_SUITE):
                    print(f"Échec ({r.id_rpg}) : {p.erreur.dropna().iloc[0]}", flush=True)
            return
        etat, raison = classer(p)
        ligne = pd.DataFrame([{"id_rpg": r.id_rpg, "insee": r.insee, "priorite": r.priorite,
                               "ha": round(r.ha, 2), "latitude": round(point.y, 5),
                               "longitude": round(point.x, 5), "images": len(p),
                               "images_sans_nuage": len(_propres(p)), "etat": etat, "raison": raison}])
        with verrou:
            ligne.to_csv(f_parcelles, mode="a", index=False, header=not f_parcelles.exists(),
                         encoding="utf-8")
            if len(p):
                p.assign(id_rpg=r.id_rpg).reindex(columns=COLONNES_IMAGES).to_csv(
                    f_images, mode="a", index=False, header=not f_images.exists(), encoding="utf-8")
            etat_calcul["faits"] += 1
            etat_calcul["echecs_de_suite"] = 0
            _noter_avancement(faits=etat_calcul["faits"])

    try:
        for essai in range(ESSAIS_MAX + 1):
            reste = g[~g.id_rpg.isin(deja_mesurees(annee))].sort_values(["priorite", "insee"])
            print(f"{len(g)} parcelles dans {len(set(insees))} communes, {len(g) - len(reste)} déjà "
                  f"mesurées, {len(reste)} à mesurer (environ {len(reste) * SECONDES_PAR_PARCELLE / 60:.0f} "
                  "min)", flush=True)
            if reste.empty:
                return
            wgs = reste.to_crs(4326)
            geos = [json.loads(json.dumps(x.__geo_interface__)) for x in wgs.geometry]
            points = list(wgs.geometry.representative_point())
            etat_calcul.update(echecs_de_suite=0, coupe=False)
            _noter_avancement(total=etat_calcul["faits"] + len(reste), communes=len(set(insees)),
                              debut=time.time() if essai == 0 else
                              json.loads(FICHIER_VERROU.read_text(encoding="utf-8")).get("debut", time.time()),
                              attente=False)
            with ThreadPoolExecutor(travailleurs) as pool:
                for k, _ in enumerate(pool.map(un, (r for _, r in reste.iterrows()), geos, points), 1):
                    if k % 100 == 0:
                        print(f"{k} / {len(reste)}", flush=True)
            if not etat_calcul["coupe"] and g.id_rpg.isin(deja_mesurees(annee)).all():
                return
            # Connexion coupée, ou quelques parcelles à reprendre : pause, en gardant le verrou à jour
            print(f"Connexion coupée ou parcelles à reprendre : nouvel essai dans {PAUSE_S // 60} min "
                  f"({essai + 1}/{ESSAIS_MAX}).", flush=True)
            for _ in range(PAUSE_S // 30):
                _noter_avancement(attente=True)
                time.sleep(30)
        print("Abandon : la connexion n'est pas revenue. Relancer plus tard, rien n'est perdu.", flush=True)
    finally:
        FICHIER_VERROU.unlink(missing_ok=True)


def pourquoi_indetermines(m):
    """Pourquoi les parcelles indéterminées du bloc ne se tranchent pas, en clair, d'après leur raison :
    trop peu d'images sans nuage, ou un signal entre prairie et labour (zone grise de la règle)."""
    r = m.loc[m.etat == "indéterminé", "raison"].fillna("")
    nuages = r.str.contains("il en faut").sum()
    if nuages == 0:
        return "signal entre prairie et labour"
    return "trop peu d'images sans nuage" if nuages == len(r) else "trop de nuages, ou signal entre les deux"


def resume_mesures(insee=None, annee=None):
    """Ce que le bloc des mesures dit des prairies sorties de la déclaration, pour la région ou pour
    une commune : parcelles et hectares mesurés, restés verts, labourés, bâtis ou minéraux,
    indéterminés, et la cible (prairies sorties d'au moins 1 ha). None si rien n'est mesuré."""
    m = mesures(annee)
    if insee is not None:
        m = m[m.insee == insee]
    if m.empty:
        return None
    vert = m.loc[m.etat == "couvert permanent", "ha"].sum()
    lab = m.loc[m.etat == "labourée", "ha"].sum()
    cible = parcelles_cibles(None if insee is None else [insee])
    return {"parcelles": len(m), "ha": m.ha.sum(), "ha_verts": vert, "ha_laboures": lab,
            "ha_batis": m.loc[m.etat == "bâti ou minéral", "ha"].sum(),
            "ha_indetermines": m.loc[m.etat == "indéterminé", "ha"].sum(),
            "pourquoi_indetermines": pourquoi_indetermines(m),
            "part_verte": vert / (vert + lab) if vert + lab else None,
            "cible_parcelles": len(cible), "cible_ha": cible.ha.sum()}
