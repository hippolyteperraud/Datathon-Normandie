import os
import glob
import pandas as pd
import geopandas as gpd

print("=== BILAN DE LA TAILLE DE VOS DONNÉES LOCALES ===\n")

hubeau_path = "data/raw/qualite_eau_hubeau/stations_normandie.csv"
if os.path.exists(hubeau_path):
    size_mb = os.path.getsize(hubeau_path) / (1024 * 1024)
    df = pd.read_csv(hubeau_path, sep=';', low_memory=False, on_bad_lines='skip')
    print(f"📁 Fichier : {hubeau_path}")
    print(f"   - Taille sur le disque : {size_mb:.2f} Mo")
    print(f"   - Nombre total de stations : {len(df)}")
    print(f"   - Colonnes disponibles : {len(df.columns)}")
else:
    print(f"⚠️ Fichier Hubeau non trouvé à l'emplacement : {hubeau_path}")

print("-" * 50)

gpkg_files = glob.glob("data/raw/**/*.gpkg", recursive=True)
if gpkg_files:
    for path in gpkg_files:
        size_mb = os.path.getsize(path) / (1024 * 1024)
        try:
            gdf = gpd.read_file(path)
            print(f"🗺️ Fichier géographique : {path}")
            print(f"   - Taille sur le disque : {size_mb:.2f} Mo")
            print(f"   - Nombre d'entités (polygones/lignes) : {len(gdf)}")
            print(f"   - Système de coordonnées (CRS) : {gdf.crs}")
        except Exception as e:
            print(f"🗺️ Fichier {path} ({size_mb:.2f} Mo) - Erreur de lecture : {e}")
else:
    print("⚠️ Aucun fichier .gpkg trouvé dans data/raw/")