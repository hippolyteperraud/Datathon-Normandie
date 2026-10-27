"""Prairimètre : récupérer TOUTES les données utilisées par le projet, en une commande.

    python importer_donnees.py                    # tout (≈ 6,7 Go ; plusieurs heures la 1re fois)
    python importer_donnees.py --liste            # quoi, d'où, vers où, sans rien télécharger
    python importer_donnees.py --seulement lucas znieff1
    python importer_donnees.py --avec-officielle  # + couche officielle des prairies (≈ 6 h de plus)
    python importer_donnees.py --puis-calculer    # enchaîne le calcul des indicateurs

Chaque source est trouvée à sa source officielle (service de téléchargement de l'IGN, API de
data.gouv.fr, Eurostat), téléchargée, recadrée sur la Normandie, vérifiée (colonnes attendues),
puis rangée dans data/ et tracée dans data/manifest.json (date, empreinte). Une source en panne
n'arrête pas les autres : son fichier actuel est conservé et le bilan final le dit.

Toutes les données sont ouvertes (Licence Ouverte 2.0 ; LUCAS : Eurostat, réutilisation libre).
Le traitement lui-même est celui du moteur (paquet prairimetre/) : ce fichier ne fait que dire
où trouver chaque donnée.
"""
import argparse
import re
import sys
import tempfile
import time
from pathlib import Path

from prairimetre import config
from prairimetre.importer import importer
from prairimetre.sources import SOURCES, ZONAGES_WFS
from prairimetre.telecharger import (ATOM_IGN, _get, _telecharger, annees_publiees,
                                     nettoyer_tmp, telecharger)

DATAGOUV = "https://www.data.gouv.fr/api/1/datasets"
EUROSTAT_LUCAS = "https://ec.europa.eu/eurostat/web/lucas/database/2022"
DEPARTEMENTS = config.DEPARTEMENTS


# --- Où trouver chaque fichier -----------------------------------------------------------------

def ressources_ign(famille):
    """Noms des archives d'une famille du service de téléchargement de l'IGN."""
    noms, page = [], 1
    while True:
        r = _get(f"{ATOM_IGN}/{famille}", params={"page": page, "limit": 50}).text
        noms += re.findall(r'title="([^"]+_\d{4}-\d{2}-\d{2})"', r)
        if page >= int(re.search(r'gpf_dl:pagecount="(\d+)"', r).group(1)):
            return sorted(set(noms))
        page += 1


def archive_ign(famille, motif):
    """Adresse de l'archive la plus récente dont le nom correspond au motif."""
    noms = [n for n in ressources_ign(famille) if re.search(motif, n)]
    if not noms:
        raise RuntimeError(f"aucune archive {famille} ne correspond à {motif}")
    nom = max(noms, key=lambda n: n[-10:])  # date de fin du nom : la plus récente
    return f"{ATOM_IGN.replace('resource', 'download')}/{famille}/{nom}/{nom}.7z", nom


def ressource_datagouv(jeu, choisir):
    """Adresse d'une ressource d'un jeu data.gouv.fr (choisir : ressource -> bool)."""
    d = _get(f"{DATAGOUV}/{jeu}/").json()
    trouve = [r for r in d["resources"] if choisir(r)]
    if not trouve:
        raise RuntimeError(f"ressource introuvable dans le jeu « {d.get('title', jeu)} »")
    return trouve[0]["url"]


def archive_atom(r):
    """Archive complète du jeu (« Téléchargement simple (Atom) ») des services de l'État."""
    return "atomArchive" in r["url"]


def lucas_france():
    r = _get(EUROSTAT_LUCAS).text
    lien = re.search(r'href="([^"]*FR_LUCAS_2022\.csv[^"]*)"', r)
    if not lien:
        raise RuntimeError("fichier FR_LUCAS_2022.csv introuvable sur la page Eurostat")
    return "https://ec.europa.eu" + lien.group(1) if lien.group(1).startswith("/") else lien.group(1)


# Sources téléchargées par un fichier puis importées : nom -> (fonction qui donne l'adresse,
# extension du fichier téléchargé). L'ordre compte : les communes servent à recadrer le reste.
FICHIERS = {
    "communes": (lambda: archive_ign("ADMIN-EXPRESS-COG", r"GPKG_LAMB93_FXX_\d{4}")[0], ".7z"),
    "conso_enaf": (lambda: ressource_datagouv("6a01b9280dd2d45907e5fc61",
                                              lambda r: r["title"] == "conso_com.csv"), ".csv"),
    "saa_prairies": (lambda: ressource_datagouv(
        "pourcentage-devolution-annuelle-de-la-surface-en-prairie-permanente-et-temporaire",
        lambda r: "departement" in r["title"].lower()), ".csv"),
    "lucas": (lucas_france, ".csv"),
    "znieff1": (lambda: ressource_datagouv(
        "zones-naturelles-dinteret-ecologique-faunistique-et-floristique-de-type-1-de-normandie",
        archive_atom), ".zip"),
    "zones_humides_dreal": (lambda: ressource_datagouv("zones-humides-normandie", archive_atom),
                            ".zip"),
    "par7_zones_humides_est": (lambda: ressource_datagouv(
        "zones-humides-des-petites-regions-agricoles-est-7par-normandie-1", archive_atom), ".zip"),
    "srce_reservoirs": (lambda: ressource_datagouv("srce-reservoirs-de-biodiversite-normandie",
                                                   archive_atom), ".zip"),
    "habitats_natura2000": (lambda: ressource_datagouv(
        "carte-de-synthese-des-habitats-dans-les-sites-natura-2000-de-normandie-occidentale-14-50-"
        "61-version-20260325", archive_atom), ".zip"),
}
ORDRE = (["communes", "epci_noms", "rpg"] + [n for n in FICHIERS if n != "communes"]
         + ["ocsge"] + ZONAGES_WFS + ["pp_officiel"])


# --- Récupération ------------------------------------------------------------------------------

def depuis_fichier(nom, **params):
    url, ext = FICHIERS[nom][0](), FICHIERS[nom][1]
    print(f"   source : {url}")
    with tempfile.TemporaryDirectory(dir=config.DATA.parent, prefix="tmp_") as tmp:
        fichier = Path(tmp) / f"{nom}{ext}"
        _telecharger(url, fichier)
        importer(nom, fichier, **params)


def ocsge():
    """Dernier millésime OCS GE de chaque département normand."""
    for dep in DEPARTEMENTS:
        url, archive = archive_ign("OCSGE", rf"^OCS-GE_\d-\d__GPKG_LAMB93_D0{dep}_\d{{4}}")
        millesime = int(archive[-10:-6])
        print(f"\n== ocsge {dep} {millesime}\n   source : {url}")
        with tempfile.TemporaryDirectory(dir=config.DATA.parent, prefix="tmp_") as tmp:
            fichier = Path(tmp) / f"ocsge_{dep}.7z"
            _telecharger(url, fichier)
            importer("ocsge", fichier, dep=dep, millesime=millesime)


def annees_rpg():
    return [a for a in annees_publiees() if a >= config.ANNEE_DEBUT]


def recuperer(nom):
    if nom == "rpg":
        for a in annees_rpg():
            telecharger("rpg", a)
    elif nom == "pp_officiel":
        for a in config.annees():
            telecharger("pp_officiel", a)
    elif nom == "ocsge":
        ocsge()
    elif nom in FICHIERS:
        print(f"\n== {nom}")
        depuis_fichier(nom)
    else:  # WFS et API : le moteur sait faire
        telecharger(nom)


def lister():
    print(f"{'source':32} {'producteur':40} accès")
    for nom in ORDRE:
        s = SOURCES[nom]
        acces = ("archives IGN, une par année" if nom == "rpg" else
                 "archives IGN, une par département" if nom == "ocsge" else
                 "archive IGN" if nom == "communes" else
                 "fichier data.gouv.fr" if nom in FICHIERS and nom != "lucas" else
                 "fichier Eurostat" if nom == "lucas" else
                 "flux WFS" if s["mode"] == "wfs" else "API")
        print(f"{nom:32} {s['producteur'][:40]:40} {acces}  ->  data/{s['fichier']}")
    print("\nNon téléchargés (sites qui refusent les scripts, documents de référence seulement) : "
          "voir data/manifest.json, entrée « references ».")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--liste", action="store_true", help="afficher les sources, sans télécharger")
    p.add_argument("--seulement", nargs="+", choices=ORDRE, metavar="SOURCE",
                   help="ne récupérer que ces sources (noms : voir --liste)")
    p.add_argument("--avec-officielle", action="store_true",
                   help="récupérer aussi la couche officielle des prairies (contrôle, ≈ 6 h)")
    p.add_argument("--puis-calculer", action="store_true",
                   help="lancer ensuite le calcul des indicateurs et l'évaluation")
    args = p.parse_args()
    if args.liste:
        return lister()

    noms = args.seulement or [n for n in ORDRE if n != "pp_officiel" or args.avec_officielle]
    config.DATA.mkdir(parents=True, exist_ok=True)
    bilan, debut = {}, time.time()
    for nom in noms:
        t0 = time.time()
        try:
            recuperer(nom)
            bilan[nom] = f"OK ({time.time() - t0:,.0f} s)"
        except (Exception, SystemExit) as e:  # une source en panne n'arrête pas les autres
            bilan[nom] = f"ÉCHEC : {str(e)[:150]} (fichier actuel conservé)"
            print(f"   ÉCHEC {nom} : {e}")
        finally:
            nettoyer_tmp()

    print(f"\n=== Bilan ({(time.time() - debut) / 60:,.0f} min) ===")
    for nom, etat in bilan.items():
        print(f"   {nom:32} {etat}")
    echecs = [n for n, e in bilan.items() if e.startswith("ÉCHEC")]
    if args.puis_calculer and not echecs:
        import subprocess
        for commande in ("controler", "calculer", "evaluer"):
            subprocess.run([sys.executable, "-X", "utf8", "-m", "prairimetre", commande],
                           check=True)
    elif echecs:
        print("\nRelancer plus tard pour ces sources : python importer_donnees.py --seulement "
              + " ".join(echecs))
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())
