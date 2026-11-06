"""Vérification par images satellite des prairies sorties de la déclaration.

Le registre parcellaire (RPG) ne dit pas ce que deviennent les prairies qui sortent de la
déclaration PAC (55 539 ha entre 2018 et 2025) : encore en herbe, labourées sans être déclarées,
boisées ou construites ? Ce module sert à le vérifier sur un échantillon de parcelles, à partir
d'observations réelles et traçables.

Principe :
1. L'échantillon : 30 parcelles tirées au hasard (6 par département) parmi les prairies de 2018
   d'au moins 1 ha sorties à au moins 90 % de la déclaration en 2025 (docs/verification_parcelles.md).
2. L'observation : pour chaque parcelle, on remplit une ligne de `verification/30_parcelles.csv`,
   avec la source et la date de l'image regardée (Copernicus Browser pour Sentinel-2, photos
   aériennes de l'IGN...). Soit on note l'état vu sur l'image, soit on donne le profil NDVI
   mensuel relevé sur la parcelle, et le module en déduit l'état.
3. Le résultat : la part des parcelles vérifiées encore en herbe, avec sa marge d'erreur, puis
   la fourchette en hectares sur l'ensemble des sorties.

Aucun résultat n'est écrit dans ce fichier : tant qu'une parcelle n'est pas observée, elle ne
compte pas. Une ligne sans source ni date est refusée.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
FICHIER_VERIFICATION = RACINE / "verification" / "30_parcelles.csv"

# États retenus pour répondre à « perdue ou pas » ; « indéterminé » n'est compté nulle part
ETATS = {
    "herbe": "encore en herbe",
    "culture": "labourée, mise en culture",
    "ligneux": "boisée ou en friche",
    "artificialise": "construite ou imperméabilisée",
    "indetermine": "impossible à trancher sur l'image",
}
COLONNES = ["numero", "commune", "departement", "surface_ha", "latitude", "longitude",
            "id_rpg_2018", "etat", "source", "date_image", "ndvi_mensuel", "commentaire"]

# --- L'échantillon (docs/verification_parcelles.md) : coordonnées d'un point dans la parcelle 2018 --
PARCELLES_30 = [
    (1, "Auvillars", "Calvados", 1.4, 49.19573, 0.06876, "1168774"),
    (2, "Cesny-les-Sources", "Calvados", 1.5, 48.98542, -0.43148, "1134018"),
    (3, "Merville-Franceville-Plage", "Calvados", 2.3, 49.27245, -0.2085, "1180949"),
    (4, "Noues de Sienne", "Calvados", 1.7, 48.78307, -0.99246, "5451643"),
    (5, "Osmanville", "Calvados", 7.7, 49.32014, -1.08036, "1141169"),
    (6, "Saint-Pierre-en-Auge", "Calvados", 23.6, 49.0226, 0.08237, "1121367"),
    (7, "Aclou", "Eure", 2.9, 49.17273, 0.70425, "2646907"),
    (8, "Hauville", "Eure", 2.9, 49.40995, 0.74688, "2658246"),
    (9, "Honguemare-Guenouville", "Eure", 1.8, 49.37604, 0.8253, "2640602"),
    (10, "Saint-Pierre-des-Ifs", "Eure", 4.7, 49.27017, 0.60174, "12066494"),
    (11, "Toutainville", "Eure", 2.6, 49.35792, 0.47512, "2621322"),
    (12, "Étréville", "Eure", 9.2, 49.38912, 0.65567, "2636334"),
    (13, "Auxais", "Manche", 1.3, 49.2144, -1.29858, "12850743"),
    (14, "Bourguenolles", "Manche", 1.2, 48.79285, -1.30243, "5397815"),
    (15, "Isigny-le-Buat", "Manche", 1.9, 48.60356, -1.25063, "5396655"),
    (16, "La Haye", "Manche", 1.5, 49.29026, -1.63189, "5526153"),
    (17, "Romagny Fontenay", "Manche", 4.9, 48.63159, -0.97569, "10558939"),
    (18, "Surtainville", "Manche", 1.2, 49.4522, -1.79034, "5473529"),
    (19, "Héloup", "Orne", 5.6, 48.39492, 0.0526, "6541894"),
    (20, "Joué-du-Bois", "Orne", 1.8, 48.58334, -0.25474, "6566337"),
    (21, "Le Sap-André", "Orne", 2.3, 48.83192, 0.37701, "6500165"),
    (22, "Longny les Villages", "Orne", 7.7, 48.57975, 0.80867, "6504022"),
    (23, "Saint-Brice-sous-Rânes", "Orne", 1.6, 48.67485, -0.18668, "6532267"),
    (24, "Saint-Evroult-de-Montfort", "Orne", 7.6, 48.82431, 0.28417, "10835542"),
    (25, "La Feuillie", "Seine-Maritime", 5.7, 49.46846, 1.51798, "7985243"),
    (26, "Les Grandes-Ventes", "Seine-Maritime", 2.5, 49.76343, 1.19901, "7995912"),
    (27, "Mesnil-Mauger", "Seine-Maritime", 4.8, 49.67362, 1.51606, "8028173"),
    (28, "Saint-Martin-aux-Buneaux", "Seine-Maritime", 1.1, 49.82092, 0.54489, "8024333"),
    (29, "Saint-Vigor-d'Ymonville", "Seine-Maritime", 4.4, 49.4753, 0.37564, "7994820"),
    (30, "Vieux-Rouen-sur-Bresle", "Seine-Maritime", 4.7, 49.84093, 1.72137, "13504377"),
]


# --- NDVI : l'indice de végétation tiré des bandes rouge (B04) et proche infrarouge (B08) -----
# Seuils de départ, À CALIBRER : avant de s'en servir, les vérifier sur des parcelles dont on
# connaît la réponse (prairies déclarées en 2025, parcelles de maïs ou de blé déclarées en 2025).
NDVI_SOL_NU = 0.25            # en dessous : sol nu (labour) ou surface minérale
NDVI_HERBE_MIN = 0.40         # une prairie reste au-dessus toute l'année
AMPLITUDE_MAX_PRAIRIE = 0.28  # une prairie varie peu d'un mois à l'autre
NDVI_BATI_MAX = 0.28          # une surface construite ne dépasse jamais ce niveau
NDVI_LIGNEUX_MIN = 0.65       # un boisement reste très vert toute l'année


def calculer_ndvi(nir: float, rouge: float) -> float:
    """NDVI = (PIR − rouge) / (PIR + rouge), borné à [−1, 1] ; 0 si les deux bandes sont nulles."""
    s = nir + rouge
    return 0.0 if s <= 0 else max(-1.0, min(1.0, (nir - rouge) / s))


def classer_profil_ndvi(profil: list[float]) -> str:
    """État d'une parcelle d'après son NDVI mensuel (au moins 6 mois d'une même année).
    Renvoie une clé de ETATS ; « indetermine » quand le profil ne tranche pas."""
    if len(profil) < 6:
        return "indetermine"
    mini, maxi = min(profil), max(profil)
    if maxi < NDVI_BATI_MAX:
        return "artificialise"
    if mini < NDVI_SOL_NU:
        return "culture"          # un passage en sol nu : labour
    if mini >= NDVI_LIGNEUX_MIN:
        return "ligneux"
    if mini >= NDVI_HERBE_MIN and maxi - mini <= AMPLITUDE_MAX_PRAIRIE:
        return "herbe"
    return "indetermine"


# --- Le fichier d'observations ----------------------------------------------------------------
def creer_fichier_vierge(chemin: Path = FICHIER_VERIFICATION) -> Path:
    """Écrit le fichier à remplir (les 30 parcelles, colonnes d'observation vides), sans jamais
    écraser un fichier existant."""
    if chemin.exists():
        return chemin
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(COLONNES)
        for p in PARCELLES_30:
            w.writerow([*p, "", "", "", "", ""])
    return chemin


def _profil(texte: str) -> list[float]:
    return [float(x.replace(",", ".")) for x in texte.replace("|", " ").split()] if texte else []


def lire_observations(chemin: Path = FICHIER_VERIFICATION) -> list[dict]:
    """Les parcelles observées : celles qui ont une source, une date d'image, et un état (noté,
    ou déduit du profil NDVI). Les autres ne sont pas renvoyées. Une erreur est levée pour un
    état inconnu ou une observation sans source ni date, plutôt que de l'ignorer en silence."""
    if not chemin.exists():
        return []
    vues = []
    with chemin.open(encoding="utf-8-sig", newline="") as f:
        for ligne in csv.DictReader(f, delimiter=";"):
            ligne = {k: (v or "").strip() for k, v in ligne.items()}
            etat, profil = ligne["etat"].lower(), _profil(ligne["ndvi_mensuel"])
            if not etat and not profil:
                continue  # pas encore observée
            if not (ligne["source"] and ligne["date_image"]):
                raise ValueError(f"parcelle {ligne['numero']} : il faut la source et la date de "
                                 "l'image pour qu'elle compte")
            if not etat:
                etat, ligne["methode"] = classer_profil_ndvi(profil), "NDVI"
            else:
                ligne["methode"] = "lecture de l'image"
            if etat not in ETATS:
                raise ValueError(f"parcelle {ligne['numero']} : état « {etat} » inconnu, "
                                 f"attendu : {', '.join(ETATS)}")
            ligne["etat"], ligne["surface_ha"] = etat, float(ligne["surface_ha"].replace(",", "."))
            vues.append(ligne)
    return vues


# --- Le résultat ------------------------------------------------------------------------------
def intervalle_wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalle de confiance à 95 % d'une proportion k/n (Wilson : juste même pour n petit)."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    marge = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - marge), min(1.0, centre + marge)


def synthese(observations: list[dict]) -> dict | None:
    """Combien de parcelles tranchées sont encore en herbe, avec la marge d'erreur ; None tant
    qu'aucune parcelle n'est tranchée. Les « indéterminé » sont comptées à part."""
    tranchees = [o for o in observations if o["etat"] != "indetermine"]
    if not tranchees:
        return None
    n, k = len(tranchees), sum(o["etat"] == "herbe" for o in tranchees)
    bas, haut = intervalle_wilson(k, n)
    return {"observees": len(observations), "tranchees": n,
            "indeterminees": len(observations) - n,
            "par_etat": {e: sum(o["etat"] == e for o in tranchees) for e in ETATS
                         if e != "indetermine"},
            "part_herbe": k / n, "part_herbe_bas": bas, "part_herbe_haut": haut}


def fourchette_ha(resultat: dict, sorties_ha: float) -> tuple[float, float]:
    """Hectares encore en herbe parmi toutes les sorties, bornes de l'intervalle à 95 %.
    Limite : l'échantillon compte 6 parcelles par département, pas en proportion des sorties de
    chaque département, et seulement des parcelles d'au moins 1 ha sorties à 90 % ou plus."""
    return sorties_ha * resultat["part_herbe_bas"], sorties_ha * resultat["part_herbe_haut"]
