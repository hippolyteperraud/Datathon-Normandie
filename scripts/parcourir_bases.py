import os
import glob
import pandas as pd
import geopandas as gpd

print("=" * 60)
print("     EXPLORATION ET PARCOURS DES BASES DE DONNÉES EAU (NORMANDIE)")
print("=" * 60 + "\n")

hubeau_path = "data/raw/qualite_eau_hubeau/stations_normandie.csv"

if os.path.exists(hubeau_path):
    print("📊 [1] ANALYSE DE LA BASE HUBEAU (Stations)")
    print(f"   - Fichier : {hubeau_path}")
    
    df_hubeau = pd.read_csv(hubeau_path, sep=';', low_memory=False, on_bad_lines='skip')
    
    print(f"   - Nombre total de stations : {len(df_hubeau)}")
    print(f"   - Nombre de variables (colonnes) : {len(df_hubeau.columns)}")
    
    if 'code_departement' in df_hubeau.columns:
        print("\n   📈 Répartition des stations par département :")
        dept_counts = df_hubeau['code_departement'].value_counts().sort_index()
        for dept, count in dept_counts.items():
            print(f"      * Département {dept} : {count} stations")
            
    print("\n   🔍 Aperçu des 3 premières stations :")
    colonnes_utiles = [c for c in ['code_station', 'libelle_station', 'code_departement', 'commune'] if c in df_hubeau.columns]
    print(df_hubeau[colonnes_utiles].head(3).to_string(index=False))
else:
    print(f"⚠️ Fichier Hubeau introuvable à l'emplacement : {hubeau_path}")

print("\n" + "-" * 60 + "\n")

gpkg_files = glob.glob("data/raw/**/*.gpkg", recursive=True)

if gpkg_files:
    for path in gpkg_files:
        if "zones_vulnerables" in path:
            continue
            
        print(f"🗺️ [2] ANALYSE DE LA COUCHE GÉOGRAPHIQUE AAC")
        print(f"   - Fichier : {path}")
        
        try:
            gdf_aac = gpd.read_file(path)
            print(f"   - Nombre d'entités (périmètres AAC) : {len(gdf_aac)}")
            print(f"   - Système de coordonnées (CRS) : {gdf_aac.crs}")
            print(f"   - Attributs disponibles : {list(gdf_aac.columns)}")
            
            print("\n   🔍 Aperçu des 3 premières aires de captage :")
            sample_cols = [c for c in ['nom_aac', 'nom', 'code_aac', 'id_aac'] if c in gdf_aac.columns]
            if not sample_cols:
                sample_cols = [gdf_aac.columns[0]]
            print(gdf_aac[sample_cols].head(3).to_string(index=False))
            
        except Exception as e:
            print(f"   ❌ Erreur de lecture du fichier géopackage : {e}")
else:
    print("⚠️ Aucun fichier .gpkg (AAC) trouvé dans data/raw/")

print("\n" + "=" * 60)
print("     FIN DE L'INSPECTION")
print("=" * 60)