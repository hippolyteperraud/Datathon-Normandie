"""Contrôles des données : chaque ligne affiche OK ou ECART.

- contrôles génériques, valables pour toute nouvelle année (schéma, cohérence avec l'année
  précédente, égalité avec la couche officielle des prairies permanentes) ;
- valeurs de référence du document « Les données du projet », pour les années déjà connues.
"""
import pyogrio

from .config import DATA, DEPARTEMENTS, annees
from .donnees import communes, enaf, lucas
from .sources import SOURCES

REFERENCES = {  # surfaces groupe 18 (ha) et nombre de parcelles, document du 22/10/2026
    "pp_ha": {2018: 682794, 2019: 665464, 2020: 664630, 2021: 660280,
              2022: 651554, 2023: 622867, 2024: 625394, 2025: 621621},
    "parcelles": {2018: 525160, 2019: 526917, 2020: 539319, 2021: 541007,
                  2022: 545150, 2023: 532211, 2024: 528928, 2025: 530536},
}
COLONNES_RPG = {"annee", "id_parcel", "surf_parc", "code_cultu", "code_group"}


class Rapport:
    def __init__(self):
        self.lignes = []

    def __call__(self, nom, ok, detail=""):
        self.lignes.append((ok, nom, detail))
        print(f"{'OK' if ok else 'ECART':5} {nom:46} {detail}")

    def proche(self, nom, obs, att, tol):
        self(nom, abs(obs - att) <= tol, f"obtenu={obs:>12,.0f}  attendu={att:>12,.0f}")

    @property
    def ecarts(self):
        return sum(not ok for ok, _, _ in self.lignes)


def _rpg_attributs(annee):
    f = DATA / SOURCES["rpg"]["fichier"].format(annee=annee)
    return pyogrio.read_dataframe(f, read_geometry=False), pyogrio.read_info(f)


def controler_rpg(r, annee, precedent=None):
    t, info = _rpg_attributs(annee)
    r(f"RPG {annee} : Lambert-93", info["crs"] == "EPSG:2154", info["crs"])
    manque = COLONNES_RPG - set(t.columns)
    r(f"RPG {annee} : colonnes", not manque, f"manquantes : {sorted(manque)}" if manque else "")
    r(f"RPG {annee} : code_group renseigné", t.code_group.notna().all(),
      f"{t.code_group.isna().sum():,} vides")
    pp = t.loc[t.code_group == 18, "surf_parc"].sum()
    if annee in REFERENCES["pp_ha"]:
        r.proche(f"RPG {annee} : groupe 18 (ha)", pp, REFERENCES["pp_ha"][annee], 1)
        r.proche(f"RPG {annee} : parcelles", len(t), REFERENCES["parcelles"][annee], 0)
    if precedent is not None:
        r(f"RPG {annee} : parcelles à ±10 % de {annee - 1}", abs(len(t) / precedent[0] - 1) < 0.10,
          f"{len(t):,} contre {precedent[0]:,}")
        r(f"RPG {annee} : prairies à ±8 % de {annee - 1}", abs(pp / precedent[1] - 1) < 0.08,
          f"{pp:,.0f} ha contre {precedent[1]:,.0f} ha")
    off = DATA / SOURCES["pp_officiel"]["fichier"].format(annee=annee)
    if off.exists() and "cat_cult_p" in t:
        o = pyogrio.read_dataframe(off, read_geometry=False, columns=["surf_parc"])
        r.proche(f"RPG {annee} : PP = couche officielle (ha)",
                 t.loc[t.cat_cult_p == "PP", "surf_parc"].sum(), o.surf_parc.sum(), 1)
    return len(t), pp


def controler(seulement=None):
    """Lance les contrôles ; seulement = liste d'années RPG à contrôler (sinon toutes)."""
    r = Rapport()
    A = annees()
    precedent = None
    for a in A:
        if seulement is None or a in seulement or a + 1 in seulement:
            precedent = controler_rpg(r, a, precedent if precedent and a - 1 in A else None)
    if seulement is None:
        # Contrôles de cohérence, valables après l'import d'un nouveau découpage communal
        c = communes()
        r("communes : codes INSEE uniques", c.insee.is_unique, f"{len(c):,} communes")
        r("communes : toutes en Normandie", c.dep.isin(DEPARTEMENTS).all(),
          ", ".join(sorted(set(c.dep) - set(DEPARTEMENTS))))
        r("communes : nombre plausible", 2000 <= len(c) <= 3500, f"{len(c):,}")
        e = enaf()
        r("Cerema : toutes les communes retrouvées", c.insee.isin(e.insee).all(),
          f"{int((~c.insee.isin(e.insee)).sum())} manquantes")
        l = lucas()
        part = l.prairie_terrain.mean()
        r("LUCAS : part de points en prairie plausible", 0.2 <= part <= 0.6, f"{part:.0%}")
    print(f"\n{r.ecarts} écart(s) sur {len(r.lignes)} contrôles")
    return r
