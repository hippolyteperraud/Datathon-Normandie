import os
import geopandas as gpd

url_wfs = "https://services.sandre.eaufrance.fr/geo/zva?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=ZoneVuln_delimitation_FXX"

print("Interrogation de l'API WFS des Zones Vulnérables (cela peut prendre quelques secondes pour la France entière)...")

try:
    gdf_zv = gpd.read_file(url_wfs)
    
    print(f"Succès ! Nombre total de zones chargées : {len(gdf_zv)}")
    print("Aperçu des colonnes :", gdf_zv.columns.tolist())
    print(gdf_zv.head(3))
    
    os.makedirs("data/raw/zones_vulnerables", exist_ok=True)
    output_gpkg = "data/raw/zones_vulnerables/zones_vulnerables_france.gpkg"
    gdf_zv.to_file(output_gpkg, driver="GPKG")
    print(f"Fichier sauvegardé en local : {output_gpkg}")

except Exception as e:
    print(f"Erreur lors de la récupération via l'API WFS : {e}")