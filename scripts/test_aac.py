import geopandas as gpd

chemin_fichier = "data/raw/aac_normandie/AAC.gpkg"

gdf_aac = gpd.read_file(chemin_fichier)

print("Nombre de captages chargés :", len(gdf_aac))
print("Colonnes disponibles :", gdf_aac.columns.tolist())
print(gdf_aac.head(2))