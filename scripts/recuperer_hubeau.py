import os
import pandas as pd

os.makedirs("data/raw/qualite_eau_hubeau", exist_ok=True)

deps = ["14", "27", "50", "61", "76"]
dfs = []

print("Téléchargement direct des stations Hubeau (Format CSV) pour la Normandie...")

for dep in deps:
    url = f"https://hubeau.eaufrance.fr/api/v2/qualite_rivieres/station_pc.csv?code_departement={dep}"
    
    try:
        df_dep = pd.read_csv(url, sep=';', on_bad_lines='skip', low_memory=False)
        dfs.append(df_dep)
        print(f"-> Département {dep} : {len(df_dep)} stations récupérées.")
    except Exception as e:
        print(f"-> Erreur pour le département {dep} : {e}")

if dfs:
    df_normandie = pd.concat(dfs, ignore_index=True)
    output_path = "data/raw/qualite_eau_hubeau/stations_normandie.csv"
    df_normandie.to_csv(output_path, index=False)
    print(f"\nFichier final sauvegardé avec succès : {output_path} ({len(df_normandie)} stations au total)")
else:
    print("Aucune donnée récupérée.")