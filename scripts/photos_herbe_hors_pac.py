"""Photos aériennes IGN d'un échantillon de morceaux d'herbe hors PAC, mélangés au hasard (sans dire à
quel groupe ils appartiennent) : 24 « sortis du registre avant 2023 » (non comptés par Agreste) et 24
« sortis depuis 2023 » (comptés par Agreste). Planches de 4 photos ; la clé est dans cle.csv. Les avis (prairie, friche, mixte, douteux) se notent
à la main dans avis.csv, en regardant les planches SANS la clé.

    python scripts/photos_herbe_hors_pac.py verification/sentinel2/2025/controle_photos"""
import io
import sys
import urllib.request
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import truststore
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, ".")
truststore.inject_into_ssl()
from prairimetre.sentinel_hors_ligne import DOSSIER  # noqa: E402
from prairimetre.sentinel_nuit import cibles  # noqa: E402

SORTIE = Path(sys.argv[1])
SORTIE.mkdir(exist_ok=True)
c = pd.read_parquet(DOSSIER / "2025" / "cibles_bilan.parquet")
g = cibles(2025)
rng = np.random.default_rng(7)
choix = []
for grp in ("sortie avant 2023", "sortie depuis 2023"):
    idx = np.flatnonzero(((c.groupe == grp) & (c.pred == "herbe") & (c.ha >= 1)).values)
    choix += [(i, grp) for i in rng.choice(idx, 24, replace=False)]
ordre = rng.permutation(len(choix))
choix = [choix[k] for k in ordre]
cle = pd.DataFrame({"n": range(1, len(choix) + 1), "k": [i for i, _ in choix], "groupe": [gr for _, gr in choix]})
geo = g.geometry.iloc[cle.k.values].reset_index(drop=True)
cle["ha"] = c.ha.values[cle.k.values].round(2)
cle["etat"] = c.etat.values[cle.k.values]
w = gpd.GeoSeries(geo, crs=g.crs).to_crs(4326)
cle["lat"], cle["lon"] = w.representative_point().y.round(5).values, w.representative_point().x.round(5).values
cle.to_csv(SORTIE / "cle.csv", index=False)
PX = 420


def photo(n, geo_l93):
    x0, y0, x1, y1 = geo_l93.bounds
    cx, cy, cote = (x0 + x1) / 2, (y0 + y1) / 2, max(x1 - x0, y1 - y0) * 0.75 + 60
    cadre = gpd.GeoSeries.from_xy([cx - cote, cx + cote], [cy - cote, cy + cote], crs=2154).to_crs(4326)
    lon0, lon1, lat0, lat1 = cadre.x[0], cadre.x[1], cadre.y[0], cadre.y[1]
    url = ("https://data.geopf.fr/wms-r?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=ORTHOIMAGERY.ORTHOPHOTOS"
           f"&STYLES=&CRS=EPSG:4326&BBOX={lat0},{lon0},{lat1},{lon1}&WIDTH={PX}&HEIGHT={PX}&FORMAT=image/jpeg")
    import time
    for essai in range(6):
        try:
            im = Image.open(io.BytesIO(urllib.request.urlopen(url, timeout=60).read())).convert("RGB")
            break
        except Exception:
            if essai == 5:
                raise
            time.sleep(3 * (essai + 1))
    d = ImageDraw.Draw(im)
    g4 = gpd.GeoSeries([geo_l93], crs=2154).to_crs(4326).iloc[0]
    for pl in (g4.geoms if g4.geom_type == "MultiPolygon" else [g4]):
        pts = [((x - lon0) / (lon1 - lon0) * PX, (lat1 - y) / (lat1 - lat0) * PX) for x, y in pl.exterior.coords]
        d.line(pts, fill=(255, 230, 0), width=3)
    d.rectangle([0, 0, 120, 26], fill=(0, 0, 0))
    d.text((6, 4), f"n{n}  {cle.ha[n - 1]} ha", fill=(255, 255, 255), font=ImageFont.load_default(18))
    return im


for p in range(0, len(cle), 4):
    planche = Image.new("RGB", (2 * PX + 6, 2 * PX + 6), "white")
    for j in range(4):
        if p + j < len(cle):
            planche.paste(photo(p + j + 1, geo[p + j]), ((j % 2) * (PX + 6), (j // 2) * (PX + 6)))
    planche.save(SORTIE / f"planche_{p // 4 + 1:02d}.jpg", quality=85)
    print("planche", p // 4 + 1, flush=True)
