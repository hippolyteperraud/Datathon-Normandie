"""Ligne de commande : python -m prairimetre <commande>.

Les trois commandes du quotidien :
    etat                          ce qui est en local, ce qui est publié, quoi faire
    mettre-a-jour [--annee A]     nouveau RPG : télécharger, contrôler, recalculer, évaluer
                                  (sans --annee : le dernier millésime publié par l'IGN ;
                                  --avec-officielle : + couche officielle, très lente)
    importer SOURCE FICHIER       un fichier téléchargé à la main (communes, OCS GE...)
                                  [--annee A] [--dep 14 --millesime 2026]

Les commandes détaillées :
    telecharger SOURCE [--annee]  une source du catalogue ; « zonages » = tous les zonages
    controler [--annee A]         contrôles OK / ECART
    calculer                      compteur et boussole -> sorties/
    evaluer [--rapide]            zonages, concentration, prédiction, certitude, SAA...
    livrer [--avec-donnees]       paquet de remise local (zip) : code, résultats, manifest
"""
import argparse
import sys
import time

from . import config


def etat(_):
    from .sources import SOURCES
    from .telecharger import annees_publiees, derniere_date
    locales = config.annees()
    print(f"RPG en local      : {locales[0]}-{locales[-1]} ({len(locales)} millésimes)"
          if locales else "RPG en local      : aucun")
    try:
        publiees = annees_publiees()
        nouvelles = [a for a in publiees if not locales or a > locales[-1]]
        print(f"RPG publiés (IGN) : jusqu'à {publiees[-1]}"
              + (f"  -> NOUVEAU : lancer « python -m prairimetre mettre-a-jour »"
                 if nouvelles else "  -> à jour"))
    except Exception as e:  # pas de réseau : on affiche quand même l'état local
        print(f"RPG publiés (IGN) : service injoignable ({type(e).__name__})")
    print("\nSources (dernière mise à jour ; comment la refaire) :")
    for nom, s in SOURCES.items():
        comment = (f"importer {nom} <fichier>" if s["mode"] == "manuel"
                   else "mettre-a-jour" if s["annuelle"] else f"telecharger {nom}")
        print(f"   {nom:32} {derniere_date(nom) or 'absent':12} {comment}")


def telecharger(args):
    from .telecharger import nettoyer_tmp, telecharger as t
    try:
        for a in args.annee or [None]:
            t(args.source, a)
    finally:
        nettoyer_tmp()


def importer(args):
    from .importer import importer as i
    from .telecharger import nettoyer_tmp
    try:
        i(args.source, args.fichier, annee=args.annee, dep=args.dep, millesime=args.millesime)
    finally:
        nettoyer_tmp()


def controler(args):
    from .controles import controler as c
    if c(args.annee).ecarts:
        print("Des écarts ont été trouvés : vérifier les données avant de recalculer.")
        sys.exit(1)


def calculer(_):
    from .indicateurs import calculer as c
    t = c()
    A = config.annees()
    print(f"\n{len(t)} communes, prairies {A[0]} -> {A[-1]} : "
          f"{t[f'pp_{A[0]}'].sum():,.0f} -> {t[f'pp_{A[-1]}'].sum():,.0f} ha")
    print(t.mecanisme.value_counts().to_string())


def evaluer(args):
    from .evaluation import evaluer as e
    e(avec_certitude=not args.rapide)


def livrer(args):
    """Paquet de remise, en local (rien n'est envoyé nulle part) : livraison/prairimetre_<date>.zip.
    Sans --avec-donnees : code, résultats (sorties/), manifest des données et documents ; les
    données se retéléchargent avec « python importer_donnees.py »."""
    import zipfile
    from datetime import date
    r = config.RACINE
    dossiers = ["prairimetre", "app", "tests", "docs", ".streamlit", "sorties"] \
        + (["data"] if args.avec_donnees else [])
    fichiers = ["README.md", "requirements.txt", "LICENSE", "importer_donnees.py"]
    sortie = r / "livraison" / f"prairimetre_{date.today():%Y%m%d}.zip"
    sortie.parent.mkdir(exist_ok=True)
    n = 0
    with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as z:
        chemins = [r / f for f in fichiers] + [config.MANIFEST] \
            + [f for d in dossiers for f in (r / d).rglob("*")]
        for f in chemins:
            if f.is_file() and "__pycache__" not in f.parts and "_hors_perimetre" not in f.parts:
                z.write(f, f.relative_to(r))
                n += 1
    print(f"{sortie} : {n} fichiers, {sortie.stat().st_size / 1e6:,.1f} Mo")


def mettre_a_jour(args):
    from .telecharger import annees_publiees, nettoyer_tmp, telecharger as t
    annee = args.annee
    if annee is None:
        annee = annees_publiees()[-1]
        if annee in config.annees():
            print(f"Déjà à jour : le dernier RPG publié ({annee}) est en local.")
            return
        print(f"Dernier millésime publié par l'IGN : {annee}")
    try:
        t("rpg", annee)
        # La couche officielle ne sert qu'à un contrôle, et son WFS est très lent (près de 6 h
        # mesurées le 25/10/2026) : on ne la télécharge que sur demande.
        if args.avec_officielle:
            try:
                t("pp_officiel", annee)
            except (SystemExit, Exception) as e:  # paraît parfois après le RPG, ou panne
                print(f"\n   (sans couche officielle pour l'instant : {e} ; elle ne sert qu'au "
                      "contrôle, la mise à jour continue)")
    finally:
        nettoyer_tmp()
    args.annee = [annee]
    controler(args)
    calculer(args)
    args.rapide = False
    evaluer(args)


def main():
    p = argparse.ArgumentParser(prog="python -m prairimetre", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="commande", required=True)
    sp.add_parser("etat").set_defaults(f=etat)
    m = sp.add_parser("mettre-a-jour")
    m.add_argument("--annee", type=int)
    m.add_argument("--avec-officielle", action="store_true",
                   help="télécharger aussi la couche officielle des prairies (contrôle, ~6 h)")
    m.set_defaults(f=mettre_a_jour)
    i = sp.add_parser("importer")
    i.add_argument("source")
    i.add_argument("fichier")
    i.add_argument("--annee", type=int)
    i.add_argument("--dep")
    i.add_argument("--millesime", type=int)
    i.set_defaults(f=importer)
    t = sp.add_parser("telecharger")
    t.add_argument("source")
    t.add_argument("--annee", type=int, nargs="*")
    t.set_defaults(f=telecharger)
    c = sp.add_parser("controler")
    c.add_argument("--annee", type=int, nargs="*")
    c.set_defaults(f=controler)
    sp.add_parser("calculer").set_defaults(f=calculer)
    e = sp.add_parser("evaluer")
    e.add_argument("--rapide", action="store_true", help="sans le test de certitude (OCS GE)")
    e.set_defaults(f=evaluer)
    lv = sp.add_parser("livrer")
    lv.add_argument("--avec-donnees", action="store_true", help="joindre data/ (plusieurs Go)")
    lv.set_defaults(f=livrer)
    args = p.parse_args()
    debut = time.time()
    args.f(args)
    duree = time.time() - debut
    print(f"\n({duree:,.0f} s)")
    if args.commande in ("calculer", "evaluer", "mettre-a-jour"):
        sobriete(args.commande, duree)


def sobriete(commande, duree):
    """Trace la durée de chaque calcul et le volume des données (sorties/sobriete.csv)."""
    from datetime import datetime

    def taille(d):  # en Mo, sans les données écartées du périmètre
        return sum(f.stat().st_size for f in d.rglob("*")
                   if f.is_file() and "_hors_perimetre" not in f.parts) / 1e6
    f = config.SORTIES / "sobriete.csv"
    neuf = not f.exists()
    with f.open("a", encoding="utf-8") as o:
        if neuf:
            o.write("date,commande,duree_s,data_mo,cache_mo,sorties_mo\n")
        o.write(f"{datetime.now():%Y-%m-%d %H:%M},{commande},{duree:.0f},"
                f"{taille(config.DATA):.0f},{taille(config.CACHE):.0f},"
                f"{taille(config.SORTIES):.1f}\n")


if __name__ == "__main__":
    main()
