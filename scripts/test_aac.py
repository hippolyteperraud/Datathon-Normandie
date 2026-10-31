import geopandas as gpd


chemin_fichier = "data/raw/aac_normandie/AAC.gpkg"

gdf_aac = gpd.read_file(chemin_fichier)

print(f"Système de coordonnées : {gdf_aac.crs}")
print(f"Aires dans tout le fichier : {len(gdf_aac)}")
print("Aires par bassin administratif :")
print(gdf_aac["NomCircAdminBassin"].value_counts(dropna=False).to_string())