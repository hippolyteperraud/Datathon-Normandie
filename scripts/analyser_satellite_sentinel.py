"""Où en est la vérification par images satellite des 30 parcelles sorties de la déclaration.

Depuis la racine du projet :
    python scripts/analyser_satellite_sentinel.py             # avancement et résultat
    python scripts/analyser_satellite_sentinel.py --creer     # crée le fichier à remplir
    python scripts/analyser_satellite_sentinel.py --sentinel  # vérification automatique Sentinel-2
                                                              # (~30 min, écrit verification/sentinel2/)

Le fichier à remplir est verification/30_parcelles.csv (séparateur « ; »). Pour chaque parcelle
regardée : la source (ex. « Copernicus Browser, Sentinel-2 L2A »), la date de l'image, puis soit
l'état vu (herbe, culture, ligneux, artificialise, indetermine), soit le NDVI mensuel relevé
(12 valeurs séparées par des espaces), dont le script déduit l'état.
"""
import argparse
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

from prairimetre.satellite import (ETATS, FICHIER_VERIFICATION, PARCELLES_30,  # noqa: E402
                                   creer_fichier_vierge, fourchette_ha, lire_observations,
                                   synthese)


def sorties_declaration_ha():
    """Surface sortie de la déclaration selon le moteur (sorties/bilan_direct.csv), sinon None."""
    chemin = RACINE / "sorties" / "bilan_direct.csv"
    if not chemin.exists():
        return None
    import pandas as pd
    bilan = pd.read_csv(chemin, header=[0, 1], index_col=0)
    return float(bilan.loc["région", ("disparues_devenues", "non déclaré")])


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--creer", action="store_true", help="crée le fichier à remplir")
    parser.add_argument("--sentinel", action="store_true",
                        help="vérification automatique par images Sentinel-2 (données ouvertes)")
    parser.add_argument("--annee", type=int, default=2025, help="année des images (--sentinel)")
    args = parser.parse_args()

    if args.sentinel:
        from prairimetre.sentinel import ecrire_preuves, verifier
        t = verifier(args.annee)
        print(t.groupby(["groupe", "etat"]).size().to_string())
        print(f"Preuves : {ecrire_preuves(t)}")
        return

    if args.creer or not FICHIER_VERIFICATION.exists():
        print(f"Fichier à remplir : {creer_fichier_vierge()}")
    obs = lire_observations()
    print(f"Parcelles observées : {len(obs)} sur {len(PARCELLES_30)}")
    r = synthese(obs)
    if r is None:
        print("Aucune parcelle tranchée : pas encore de résultat.")
        return
    for etat, n in r["par_etat"].items():
        print(f"  {ETATS[etat]} : {n}")
    if r["indeterminees"]:
        print(f"  impossible à trancher : {r['indeterminees']} (non comptées)")
    print(f"Encore en herbe : {r['part_herbe']:.0%} des {r['tranchees']} parcelles tranchées "
          f"(intervalle à 95 % : {r['part_herbe_bas']:.0%} à {r['part_herbe_haut']:.0%})")
    total = sorties_declaration_ha()
    if total:
        bas, haut = fourchette_ha(r, total)
        print(f"Sur les {total:,.0f} ha sortis de la déclaration : entre {bas:,.0f} et "
              f"{haut:,.0f} ha encore en herbe".replace(",", " "))


if __name__ == "__main__":
    main()
