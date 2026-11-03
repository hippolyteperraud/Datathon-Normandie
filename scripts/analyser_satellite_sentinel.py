"""Outil CLI d'analyse satellitaire Sentinel-2 / Theia OSO pour le Datathon Normandie.

Exécution depuis la racine du projet :
    python scripts/analyser_satellite_sentinel.py
    python scripts/analyser_satellite_sentinel.py --exporter
    python scripts/analyser_satellite_sentinel.py --commune 14024
"""
import argparse
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from prairimetre.satellite import (
    auditer_30_parcelles,
    diagnostic_zone_noire,
    exporter_audit_csv,
    redresser_pertes_sorties,
    synthese_audit,
)


def afficher_audit(parcelles):
    print("=" * 80)
    print("  AUDIT PAR SATELLITE SENTINEL-2 & THEIA OSO (30 PARCELLES ÉCHANTILLONS)")
    print("=" * 80)
    print(f"{'N°':<3} {'Commune':<24} {'Dép':<15} {'Ha':<6} {'NDVI':<6} {'État constaté':<30}")
    print("-" * 85)
    for p in parcelles:
        print(f"{p.numero:<3} {p.commune:<24} {p.departement:<15} {p.surface_ha:<6.1f} {p.ndvi_moyen:<6.2f} {p.etat_constate:<30}")
    print("-" * 85)


def afficher_bilan_regional(redressement):
    print("\n" + "=" * 80)
    print("  BILAN DE REDRESSEMENT RÉGIONAL POUR L'OBJECTIF 2030 (RÉGION NORMANDIE)")
    print("=" * 80)
    print(f"Surface totale sortie du RPG (2018-2025) : {redressement['surface_sorties_declarees_ha']:,.0f} ha")
    print(f"Taux de maintien en herbe estimé (satellite) : {redressement['taux_maintien_estime_pct']} % (± {redressement['marge_erreur_pct']} %)")
    print(f"\n-> Estimation d'herbe toujours présente au sol : {redressement['estimation_herbe_maintenue_ha']:,.0f} ha")
    print(f"   (Fourchette de confiance 95 % : {redressement['fourchette_herbe_min_ha']:,.0f} ha à {redressement['fourchette_herbe_max_ha']:,.0f} ha)")
    print(f"\n-> Estimation des pertes réelles physiques : {redressement['estimation_vraies_pertes_ha']:,.0f} ha")
    details = redressement['detail_pertes']
    print(f"   * Terres labourées / cultures non déclarées : {details['cultures_non_declarees_ha']:,.0f} ha")
    print(f"   * Boisement spontané / friches fermées     : {details['boisement_ou_friches_ha']:,.0f} ha")
    print(f"   * Artificialisation (bâti, chantiers)       : {details['artificialisation_ha']:,.0f} ha")
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exporter", action="store_true", help="Exporte le tableau en CSV dans sorties/")
    parser.add_argument("--commune", type=str, help="Code INSEE d'une commune pour diagnostic de zone noire")
    args = parser.parse_args()

    if args.commune:
        diag = diagnostic_zone_noire(args.commune)
        print(f"\n--- Diagnostic pour la commune {args.commune} ---")
        for k, v in diag.items():
            print(f"  {k} : {v}")
        return

    parcelles = auditer_30_parcelles()
    afficher_audit(parcelles)

    synth = synthese_audit(parcelles)
    print(f"\nSynthèse échantillon (30 parcelles, {synth['surface_totale_ha']} ha) :")
    print(f"  - Maintien en herbe : {synth['nb_maintenues_herbe']}/30 parcelles ({synth['part_herbe_surface_pct']} % de la surface)")
    print(f"  - Labour / culture : {synth['nb_retournees_culture']}/30 parcelles")
    print(f"  - Boisement / friche : {synth['nb_boisees_friches']}/30 parcelles")
    print(f"  - Bâti / artificiel : {synth['nb_artificialisees']}/30 parcelles")

    redressement = redresser_pertes_sorties()
    afficher_bilan_regional(redressement)

    chemin_csv = exporter_audit_csv()
    print(f"Tableau d'audit exporté avec succès dans : {chemin_csv}")


if __name__ == "__main__":
    main()
