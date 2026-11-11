"""Contrôle à l'œil du verdict satellite : un humain regarde quelques parcelles et dit ce qu'il voit.

Le code range chaque prairie sortie de la déclaration en « couvert permanent », « labourée », « bâti ou
minéral » ou « indéterminé » d'après le NDVI de 2025 (prairimetre/sentinel.py). Ici, on tire au
hasard quelques-unes de ces parcelles et on fabrique UN fichier HTML autonome (images comprises) :
pour chaque parcelle, la photo aérienne de l'IGN et des images Sentinel-2 de 2025 en couleurs
naturelles, contour en jaune. La personne répond SANS connaître le verdict du code (il ne s'affiche
qu'après sa réponse), puis télécharge ses réponses en CSV.

Depuis la racine du projet :
    python scripts/controle_humain.py preparer            # 10 parcelles -> controle_humain/paquet_01.html
    python scripts/controle_humain.py preparer --n 30     # un paquet plus gros (jamais les mêmes parcelles)
    python scripts/controle_humain.py comparer reponses_paquet_01.csv   # accord humain / code

Les réponses sont ajoutées à verification/sentinel2/controle_humain/reponses.csv (une ligne par
parcelle et par personne).
"""
import argparse
import base64
import io
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

import pandas as pd  # noqa: E402
import truststore  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from prairimetre import sentinel  # noqa: E402

truststore.inject_into_ssl()  # certificats du système (sinon échec TLS sur ce réseau)
sys.stdout.reconfigure(encoding="utf-8")

DOSSIER = sentinel.DOSSIER / "controle_humain"
FICHIER_REPONSES = DOSSIER / "reponses.csv"
GRAINE = 2030
# Part de chaque verdict du code dans un paquet : on regarde surtout ce que le code affirme
PARTS = {"couvert permanent": 0.4, "labourée": 0.3, "bâti ou minéral": 0.1, "indéterminé": 0.2}
REPONSES = {
    "herbe": "En herbe toute l'année",
    "labouree": "Labourée ou cultivée (terre nue à un moment)",
    "bois": "Bois, haies, broussailles, friche",
    "batie": "Bâtie, goudronnée, cour de ferme",
    "ne_sait_pas": "Impossible à dire",
}
# Réponses qui confirment chaque verdict du code. « Bois, friche » confirme le SIGNAL « couvert
# permanent » (vert toute l'année, jamais labouré) mais ce n'est pas de l'herbe : compté à part.
CONFIRME = {"couvert permanent": {"herbe", "bois"}, "labourée": {"labouree"},
            "bâti ou minéral": {"batie"}}
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.",
        "déc."]
S2_PX, IGN_PX = 256, 512


# --- Tirage ---------------------------------------------------------------------------------------
def _deja_tirees():
    ids = set()
    for f in DOSSIER.glob("paquet_*.csv"):
        ids |= set(pd.read_csv(f, dtype={"id_rpg": str}).id_rpg)
    return ids


def tirer(n, graine):
    p = pd.read_csv(sentinel.bloc()[0], dtype={"id_rpg": str, "insee": str})
    p = p[~p.id_rpg.isin(_deja_tirees())]
    effectifs = {e: max(1, round(n * part)) for e, part in PARTS.items()}
    while sum(effectifs.values()) > n:  # les arrondis : on retire au plus gros groupe
        effectifs[max(effectifs, key=effectifs.get)] -= 1
    morceaux = [p[p.etat == e].sample(min(k, (p.etat == e).sum()), random_state=graine)
                for e, k in effectifs.items()]
    # Ordre mélangé : le verdict du code ne doit pas se deviner à la position
    return pd.concat(morceaux).sample(frac=1, random_state=graine).reset_index(drop=True)


def contours(t):
    """Le contour mesuré par le code : la parcelle de la première année, ou seulement sa part sortie
    quand elle n'est sortie qu'en partie (même règle que verifier_communes : sortie à 90 % ou plus =
    parcelle entière)."""
    from prairimetre.donnees import prairies
    a0, an = sentinel.periode()
    g = prairies(a0)
    g = g[g.id_parcel.astype(str).isin(t.id_rpg)].copy()
    g["id_rpg"] = g.id_parcel.astype(str)
    g = g.drop_duplicates("id_rpg").set_index("id_rpg").loc[t.id_rpg]
    part = sentinel._part_sortie(g, an)
    g["geometry"] = [x if not x.is_empty and x.area < 0.9 * geo.area else geo
                     for x, geo in zip(part, g.geometry)]
    return g


# --- Images ---------------------------------------------------------------------------------------
def _lire(url, essais=3):
    for i in range(essais):
        try:
            return urllib.request.urlopen(url, timeout=60).read()
        except Exception:
            if i == essais - 1:
                raise


def _cadre(geo):
    """Carré autour de la parcelle (en Lambert-93), marge comprise, en degrés (lon/lat)."""
    import geopandas as gpd
    from shapely.geometry import box
    x0, y0, x1, y1 = geo.bounds
    cx, cy, c = (x0 + x1) / 2, (y0 + y1) / 2, max(x1 - x0, y1 - y0) * 0.8 + 80
    carre = gpd.GeoSeries([box(cx - c, cy - c, cx + c, cy + c)], crs=2154).to_crs(4326)
    return carre.total_bounds  # lon0, lat0, lon1, lat1


def _anneaux(geo4326):
    polys = geo4326.geoms if geo4326.geom_type == "MultiPolygon" else [geo4326]
    for pl in polys:
        yield pl.exterior.coords
        for r in pl.interiors:
            yield r.coords


def _dessiner(octets, geo4326, cadre, taille):
    lon0, lat0, lon1, lat1 = cadre
    im = Image.open(io.BytesIO(octets)).convert("RGB").resize((taille, taille), Image.NEAREST)
    d = ImageDraw.Draw(im)
    for anneau in _anneaux(geo4326):
        pts = [((x - lon0) / (lon1 - lon0) * taille, (lat1 - y) / (lat1 - lat0) * taille)
               for x, y in anneau]
        d.line(pts + pts[:1], fill=(255, 230, 0), width=2)
    b = io.BytesIO()
    im.save(b, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def photo_ign(geo4326, cadre):
    lon0, lat0, lon1, lat1 = cadre
    url = ("https://data.geopf.fr/wms-r?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap"
           "&LAYERS=ORTHOIMAGERY.ORTHOPHOTOS&STYLES=&CRS=EPSG:4326"
           f"&BBOX={lat0},{lon0},{lat1},{lon1}&WIDTH={IGN_PX}&HEIGHT={IGN_PX}&FORMAT=image/jpeg")
    return _dessiner(_lire(url), geo4326, cadre, IGN_PX)


def vignette_s2(item, geo4326, cadre):
    lon0, lat0, lon1, lat1 = cadre
    url = (f"{sentinel.DONNEES}/bbox/{lon0},{lat0},{lon1},{lat1}/{S2_PX}x{S2_PX}.png"
           f"?collection={sentinel.COLLECTION}&item={item}&assets=visual"
           "&asset_bidx=visual|1,2,3&nodata=0")
    return _dessiner(_lire(url), geo4326, cadre, S2_PX)


def dates_a_montrer(imgs):
    """Images sans nuage sur la parcelle : une par tranche de deux mois (la plus proche du milieu de
    la tranche), plus celle où le NDVI est le plus bas (le moment où un labour se verrait)."""
    propres = sentinel._propres(imgs).copy()
    if propres.empty:
        return propres
    propres["jour"] = pd.to_datetime(propres.date).dt.dayofyear
    choix = []
    for debut in range(0, 365, 61):
        tranche = propres[(propres.jour > debut) & (propres.jour <= debut + 61)]
        if len(tranche):
            choix.append((tranche.jour - (debut + 30)).abs().idxmin())
    choix.append(propres.ndvi.idxmin())
    return propres.loc[sorted(set(choix))].sort_values("date")


def _date_fr(d):
    d = pd.Timestamp(d)
    return f"{d.day} {MOIS[d.month - 1]}"


def fiche(r, geo, imgs):
    import geopandas as gpd
    geo4326 = gpd.GeoSeries([geo], crs=2154).to_crs(4326).iloc[0]
    cadre = _cadre(geo)
    montrer = dates_a_montrer(imgs)
    s2 = []
    for _, i in montrer.iterrows():
        try:
            s2.append({"date": _date_fr(i.date), "img": vignette_s2(i["item"], geo4326, cadre)})
        except Exception as e:
            print(f"  {r.id_rpg} : image du {i.date} illisible ({str(e)[:60]})", flush=True)
    propres = sentinel._propres(imgs)
    lat, lon = r.latitude, r.longitude
    return {
        "id": r.id_rpg, "insee": r.insee, "ha": float(r.ha), "etat": r.etat, "raison": r.raison,
        "ign": photo_ign(geo4326, cadre), "s2": s2,
        "ndvi": [[int(pd.Timestamp(d).dayofyear), round(float(v), 3)]
                 for d, v in zip(propres.date, propres.ndvi)],
        "lien_ign": (f"https://cartes.gouv.fr/explorer-les-cartes/?c={lon},{lat}&z=17"
                     "&l0=ORTHOIMAGERY.ORTHOPHOTOS::GEOPORTAIL:OGC:WMTS(1)&permalink=yes"),
        "lien_s2": f"https://browser.dataspace.copernicus.eu/?zoom=16&lat={lat}&lng={lon}",
    }


def preparer(n, graine):
    DOSSIER.mkdir(parents=True, exist_ok=True)
    numero = len(list(DOSSIER.glob("paquet_*.csv"))) + 1
    nom = f"paquet_{numero:02d}"
    t = tirer(n, graine + numero)
    print(f"{nom} : {len(t)} parcelles tirées ({', '.join(f'{k} {e}' for e, k in t.etat.value_counts().items())})")
    g = contours(t)
    toutes = pd.read_csv(sentinel.bloc()[1], dtype={"id_rpg": str}, low_memory=False)
    toutes = toutes[toutes.id_rpg.isin(t.id_rpg)]

    def une(r):
        return fiche(r, g.geometry[r.id_rpg], toutes[toutes.id_rpg == r.id_rpg])

    with ThreadPoolExecutor(4) as pool:
        fiches = list(pool.map(une, (r for _, r in t.iterrows())))
    page = PAGE.replace("__PAQUET__", nom).replace("__DONNEES__", json.dumps(
        {"paquet": nom, "reponses": REPONSES, "parcelles": fiches}, ensure_ascii=False))
    html = DOSSIER / f"{nom}.html"
    html.write_text(page, encoding="utf-8")
    t[["id_rpg", "insee", "ha", "etat"]].assign(graine=graine + numero,
                                                prepare_le=datetime.now().strftime("%Y-%m-%d")
                                                ).to_csv(DOSSIER / f"{nom}.csv", index=False)
    print(f"Écrit : {html.relative_to(RACINE)} ({html.stat().st_size / 1e6:.1f} Mo). "
          "À envoyer tel quel : il s'ouvre dans n'importe quel navigateur, sans internet.")


# --- Comparaison ----------------------------------------------------------------------------------
def comparer(fichiers):
    nouvelles = pd.concat([pd.read_csv(f, dtype={"id_rpg": str}, encoding="utf-8-sig") for f in fichiers])
    if FICHIER_REPONSES.exists():
        anciennes = pd.read_csv(FICHIER_REPONSES, dtype={"id_rpg": str})
        nouvelles = pd.concat([anciennes, nouvelles])
    r = nouvelles.drop_duplicates(["id_rpg", "controleur"], keep="last")
    r.to_csv(FICHIER_REPONSES, index=False)
    p = pd.read_csv(sentinel.bloc()[0], dtype={"id_rpg": str})[["id_rpg", "etat", "latitude", "longitude"]]
    r = r.drop(columns=["etat_code"], errors="ignore").merge(p, on="id_rpg", how="left")
    print(f"{len(r)} réponses ({r.controleur.nunique()} personne(s)), gardées dans "
          f"{FICHIER_REPONSES.relative_to(RACINE)}\n")
    vu = r[r.reponse != "ne_sait_pas"]
    tranches = vu[vu.etat.isin(CONFIRME)]
    accord = tranches.apply(lambda x: x.reponse in CONFIRME[x.etat], axis=1)
    for e in PARTS:
        s = r[r.etat == e]
        if s.empty:
            continue
        lignes = s.reponse.map(REPONSES).value_counts()
        print(f"Le code dit « {e} » ({len(s)}) : " + " ; ".join(f"{k} {v}" for v, k in lignes.items()))
    if len(tranches):
        bas, haut = sentinel.wilson(int(accord.sum()), len(tranches))
        print(f"\nAccord sur les parcelles que le code tranche et que l'œil tranche : {int(accord.sum())} "
              f"sur {len(tranches)} (intervalle à 95 % : {bas * 100:.0f} % à {haut * 100:.0f} %).")
        bois = (tranches.etat.eq("couvert permanent") & tranches.reponse.eq("bois")).sum()
        if bois:
            print(f"Dont {bois} « couvert permanent » vus en bois ou friche : vert, mais pas de l'herbe.")
    desaccords = tranches[~accord]
    if len(desaccords):
        print("\nDésaccords, à revoir :")
        for _, x in desaccords.iterrows():
            print(f"  {x.id_rpg} : code « {x.etat} », vu « {REPONSES[x.reponse]} » "
                  f"{('— ' + x.commentaire) if isinstance(x.commentaire, str) and x.commentaire else ''}"
                  f"\n    https://cartes.gouv.fr/explorer-les-cartes/?c={x.longitude},{x.latitude}&z=17"
                  "&l0=ORTHOIMAGERY.ORTHOPHOTOS::GEOPORTAIL:OGC:WMTS(1)&permalink=yes")
    indet = vu[vu.etat == "indéterminé"]
    if len(indet):
        print(f"\nIndéterminés par le code, tranchés à l'œil : {len(indet)} sur "
              f"{(r.etat == 'indéterminé').sum()} — " + " ; ".join(
                  f"{REPONSES[v]} {k}" for v, k in indet.reponse.value_counts().items()))


PAGE = r"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Contrôle à l'œil — __PAQUET__</title>
<style>
:root{--fond:#f6f7f4;--carte:#fff;--texte:#1d2a1f;--doux:#5d6b60;--trait:#dfe4dc;--vert:#2f7d3b;--rouge:#b3412f;--bleu:#2b5d8a}
@media (prefers-color-scheme: dark){:root{--fond:#141814;--carte:#1e241f;--texte:#e7ece6;--doux:#9aa69c;--trait:#333d35;--vert:#6cc27a;--rouge:#e58a78;--bleu:#7fb0de}}
*{box-sizing:border-box}body{margin:0;background:var(--fond);color:var(--texte);font:15px/1.45 system-ui,Segoe UI,sans-serif}
header{display:flex;gap:16px;align-items:center;justify-content:space-between;padding:12px 20px;border-bottom:1px solid var(--trait);flex-wrap:wrap}
h1{font-size:18px;margin:0}main{max-width:1200px;margin:0 auto;padding:16px 20px}
.consigne{color:var(--doux);margin:0 0 12px}
.grille{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);gap:16px}
@media (max-width:820px){.grille{grid-template-columns:1fr}}
.boite{background:var(--carte);border:1px solid var(--trait);border-radius:10px;padding:12px}
.boite h2{font-size:14px;margin:0 0 8px;color:var(--doux);font-weight:600}
.ign img{width:100%;max-width:62vh;margin:0 auto;border-radius:6px;display:block}
.verdict svg{max-width:640px;display:block}
.s2{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:8px}
.s2 figure{margin:0}.s2 img{width:100%;border-radius:6px;display:block;image-rendering:pixelated}
.s2 figcaption{font-size:12px;color:var(--doux);text-align:center}
.choix{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}
.choix button{font:inherit;padding:9px 14px;border-radius:8px;border:1px solid var(--trait);background:var(--carte);color:var(--texte);cursor:pointer}
.choix button:hover:not(:disabled){border-color:var(--bleu)}
.choix button.pris{background:var(--bleu);color:#fff;border-color:var(--bleu)}
.choix button:disabled:not(.pris){opacity:.45;cursor:default}
textarea,input{font:inherit;width:100%;padding:8px;border-radius:8px;border:1px solid var(--trait);background:var(--carte);color:var(--texte)}
.verdict{margin-top:12px;padding:12px;border-radius:10px;border:2px solid var(--trait)}
.verdict.ok{border-color:var(--vert)}.verdict.non{border-color:var(--rouge)}
.badge{font-weight:700}.ok .badge{color:var(--vert)}.non .badge{color:var(--rouge)}
.nav{display:flex;justify-content:space-between;align-items:center;margin-top:16px;gap:8px}
.nav button,.gros{font:inherit;padding:9px 16px;border-radius:8px;border:0;background:var(--texte);color:var(--fond);cursor:pointer}
.nav button:disabled{opacity:.3;cursor:default}
.points{display:flex;gap:4px;flex-wrap:wrap}.points span{width:10px;height:10px;border-radius:50%;background:var(--trait)}
.points span.fait{background:var(--bleu)}.points span.ici{outline:2px solid var(--texte)}
a{color:var(--bleu)}svg text{fill:var(--doux);font-size:11px}
.cache{display:none}
</style></head><body>
<header><h1>Contrôle à l'œil des parcelles — <span id="titre"></span></h1>
<label style="display:flex;gap:8px;align-items:center">Ton prénom <input id="nom" style="width:160px"></label></header>
<main>
<p class="consigne">Pour chaque parcelle (contour jaune) : regarde la photo aérienne et les images satellite de 2025, puis dis ce qu'était la parcelle <b>en 2025</b>. De la terre brune sur au moins une date = labourée. Le verdict du code s'affiche seulement après ta réponse.</p>
<div id="fiche"></div>
<div class="nav"><button id="prec">← Précédente</button><div class="points" id="points"></div><button id="suiv">Suivante →</button></div>
<div id="fin" class="boite cache" style="margin-top:16px"></div>
</main>
<script>
const D = __DONNEES__;
const P = D.parcelles, CLE = "controle_" + D.paquet;
const CONFIRME = {"couvert permanent":["herbe","bois"],"labourée":["labouree"],"bâti ou minéral":["batie"]};
let R = {}, i = 0;
try { R = JSON.parse(localStorage.getItem(CLE) || "{}"); } catch (e) {}
try { document.getElementById("nom").value = localStorage.getItem("controle_nom") || ""; } catch (e) {}
document.getElementById("nom").oninput = e => { try { localStorage.setItem("controle_nom", e.target.value); } catch (x) {} };
document.getElementById("titre").textContent = D.paquet.replace("_", " ") + " (" + P.length + " parcelles)";
const garder = () => { try { localStorage.setItem(CLE, JSON.stringify(R)); } catch (e) {} };
const ha = x => x.toLocaleString("fr-FR", {maximumFractionDigits: 2}) + " ha";

function courbe(pts) {
  const W = 520, H = 150, g = 30, x = j => g + (j / 365) * (W - g - 8), y = v => 8 + (1 - Math.max(-0.1, Math.min(1, v)) / 1) * (H - 30);
  let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="NDVI de 2025">`;
  [0, 0.25, 0.5, 0.75].forEach(v => s += `<line x1="${g}" x2="${W-8}" y1="${y(v)}" y2="${y(v)}" stroke="currentColor" stroke-opacity="${v==0.25?0.6:0.12}" ${v==0.25?'stroke-dasharray="4 3"':''}/><text x="2" y="${y(v)+4}">${String(v).replace(".", ",")}</text>`);
  ["janv.","avr.","juil.","oct."].forEach((m, k) => s += `<text x="${x(k*91)+2}" y="${H-4}">${m}</text>`);
  s += `<polyline fill="none" stroke="var(--bleu)" stroke-width="1.5" points="${pts.map(p => x(p[0])+","+y(p[1])).join(" ")}"/>`;
  pts.forEach(p => s += `<circle cx="${x(p[0])}" cy="${y(p[1])}" r="3" fill="${p[1] < 0.25 ? "var(--rouge)" : "var(--vert)"}"/>`);
  return s + "</svg>";
}

function afficher() {
  const p = P[i], r = R[p.id];
  let h = `<div class="grille"><div class="boite ign"><h2>Photo aérienne IGN (la plus récente, parfois avant 2025) · ${ha(p.ha)}</h2><img src="${p.ign}" alt="Photo aérienne"></div>
  <div class="boite"><h2>Satellite Sentinel-2, 2025 (pixels de 10 m)</h2><div class="s2">${p.s2.map(s => `<figure><img src="${s.img}" alt="Image du ${s.date}"><figcaption>${s.date}</figcaption></figure>`).join("") || "Aucune image sans nuage."}</div></div></div>
  <div class="boite" style="margin-top:16px"><h2>Parcelle ${i+1} sur ${P.length} : en 2025, elle était…</h2><div class="choix">`;
  for (const [k, lib] of Object.entries(D.reponses)) h += `<button data-k="${k}" class="${r && r.reponse == k ? "pris" : ""}" ${r ? "disabled" : ""}>${lib}</button>`;
  h += `</div><textarea id="com" rows="2" placeholder="Commentaire (facultatif) : ce qui t'a fait hésiter…">${r ? (r.commentaire || "") : ""}</textarea>`;
  if (r) {
    const conf = CONFIRME[p.etat], ok = conf && conf.includes(r.reponse);
    const cls = !conf || r.reponse == "ne_sait_pas" ? "" : ok ? "ok" : "non";
    const mot = !conf ? "Le code n'avait pas tranché : ta réponse le complète." : r.reponse == "ne_sait_pas" ? "Pas comparé." : ok ? "D'accord avec le code." : "Pas d'accord avec le code.";
    h += `<div class="verdict ${cls}"><div>Le code a dit : <b>${p.etat}</b> — <span class="badge">${mot}</span></div>
    <div style="color:var(--doux);font-size:13px">${p.raison}</div>${courbe(p.ndvi)}
    <div style="font-size:13px">Indice de végétation (NDVI) de chaque image sans nuage ; point rouge = terre nue (sous 0,25). Revoir : <a href="${p.lien_ign}" target="_blank">Géoportail</a> · <a href="${p.lien_s2}" target="_blank">Copernicus Browser</a> · parcelle ${p.id}, commune ${p.insee}</div></div>`;
  }
  h += `</div>`;
  document.getElementById("fiche").innerHTML = h;
  document.querySelectorAll(".choix button").forEach(b => b.onclick = () => {
    R[p.id] = {reponse: b.dataset.k, commentaire: document.getElementById("com").value, heure: new Date().toISOString()};
    garder(); afficher();
  });
  document.getElementById("com").oninput = e => { if (R[p.id]) { R[p.id].commentaire = e.target.value; garder(); } };
  document.getElementById("prec").disabled = i == 0;
  document.getElementById("suiv").textContent = i == P.length - 1 ? "Terminer →" : "Suivante →";
  document.getElementById("points").innerHTML = P.map((q, k) => `<span class="${R[q.id] ? "fait" : ""} ${k == i ? "ici" : ""}" title="Parcelle ${k+1}"></span>`).join("");
  document.querySelectorAll("#points span").forEach((s, k) => s.onclick = () => { i = k; fin(false); afficher(); });
}

function fin(montrer) {
  const f = document.getElementById("fin");
  f.classList.toggle("cache", !montrer);
  if (!montrer) return;
  const faits = P.filter(p => R[p.id]);
  const comp = faits.filter(p => CONFIRME[p.etat] && R[p.id].reponse != "ne_sait_pas");
  const ok = comp.filter(p => CONFIRME[p.etat].includes(R[p.id].reponse));
  f.innerHTML = `<h2 style="margin-top:0">${faits.length} parcelles sur ${P.length} regardées</h2>
  <p>D'accord avec le code sur <b>${ok.length} sur ${comp.length}</b> parcelles comparables.${faits.length < P.length ? " Il en reste à faire (points gris)." : ""}</p>
  <button class="gros" id="tele">Télécharger mes réponses (CSV)</button> <span style="color:var(--doux)">puis envoie le fichier à Hippolyte.</span>`;
  document.getElementById("tele").onclick = () => {
    const nom = (document.getElementById("nom").value || "anonyme").replace(/[,;\n]/g, " ");
    const q = s => '"' + String(s || "").replace(/"/g, '""') + '"';
    const lignes = ["paquet,id_rpg,controleur,reponse,commentaire,etat_code,heure"].concat(
      faits.map(p => [D.paquet, p.id, q(nom), R[p.id].reponse, q(R[p.id].commentaire), q(p.etat), R[p.id].heure].join(",")));
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + lignes.join("\n")], {type: "text/csv"}));
    a.download = "reponses_" + D.paquet + "_" + nom.replace(/\s+/g, "_") + ".csv"; a.click();
  };
  f.scrollIntoView({behavior: "smooth"});
}

document.getElementById("prec").onclick = () => { if (i > 0) { i--; fin(false); afficher(); } };
document.getElementById("suiv").onclick = () => { if (i < P.length - 1) { i++; afficher(); window.scrollTo(0, 0); } else fin(true); };
afficher();
</script></body></html>
"""


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = a.add_subparsers(dest="commande", required=True)
    p1 = s.add_parser("preparer", help="tirer des parcelles et écrire le fichier HTML à envoyer")
    p1.add_argument("--n", type=int, default=10)
    p1.add_argument("--graine", type=int, default=GRAINE)
    p2 = s.add_parser("comparer", help="lire les réponses CSV et les comparer au code")
    p2.add_argument("fichiers", nargs="+")
    args = a.parse_args()
    if args.commande == "preparer":
        preparer(args.n, args.graine)
    else:
        comparer(args.fichiers)
