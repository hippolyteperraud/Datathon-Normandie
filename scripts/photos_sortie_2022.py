"""Contrôle à l'aveugle des prairies sorties de la PAC en 2022 (lancer scripts/verifier_sortie_2022.py en
premier) : 24 morceaux d'au moins 1 ha de prairie permanente 2021 plus jamais déclarée, toujours herbe au
satellite en 2025, mélangés à 24 prairies permanentes déclarées en 2024 et 2025 (témoins). Planches de 4
photos aériennes IGN ; la clé est dans cle.csv, les avis se notent à la main dans avis.csv SANS la clé.

    python scripts/photos_sortie_2022.py verification/sentinel2/2025/controle_photos_sortie_2022"""
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
o = pd.read_parquet(DOSSIER / "2025" / "verif_2021.parquet")
apres = o[["in2022", "in2023", "in2024"]].max(axis=1)
ok = o[(o.pp2021 >= .5 * o.ha) & (apres < .1 * o.ha) & (o.ha >= 1)]
g = cibles(2025)
e = gpd.read_parquet(DOSSIER / "etalons_2025.parquet")
e = e[(e.nature == "herbe") & (e.ha >= 1)]
rng = np.random.default_rng(11)
geos = [(g.geometry.iloc[k], "sortie 2022", h) for k, h in zip(rng.choice(ok.k.values, 24, replace=False), [0]*24)]
ie = rng.choice(len(e), 24, replace=False)
geos += [(e.geometry.iloc[i], "declaree 2025", 0) for i in ie]
geos = [geos[j] for j in rng.permutation(len(geos))]
geo = [x[0] for x in geos]
cle = pd.DataFrame({"n": range(1, len(geos) + 1), "groupe": [x[1] for x in geos]})
cle["ha"] = [round(x.area / 1e4, 2) for x in geo]
w = gpd.GeoSeries(geo, crs=2154).to_crs(4326).representative_point()
cle["lat"], cle["lon"] = w.y.round(5).values, w.x.round(5).values
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
