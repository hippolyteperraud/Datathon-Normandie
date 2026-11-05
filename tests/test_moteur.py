"""Tests du moteur sur de petites données inventées (rapides, sans data/).

    python -m unittest discover tests
"""
import unittest

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from prairimetre.donnees import code5
from prairimetre.evaluation import etat_ocsge
from prairimetre.satellite import (
    auditer_30_parcelles,
    calculer_ndvi,
    classifier_profil_ndvi,
    diagnostic_zone_noire,
    synthese_audit,
)
from prairimetre.suivi import categorie, croiser


def carres(*boites, categories=None):
    g = gpd.GeoDataFrame(geometry=[box(*b) for b in boites], crs=2154)
    if categories is not None:
        g["categorie"] = categories
    return g


class Codes(unittest.TestCase):
    def test_code_insee_sur_cinq_caracteres(self):
        s = pd.Series([14118, "1001", " 76540 ", "14118.0"])
        self.assertEqual(code5(s).tolist(), ["14118", "01001", "76540", "14118"])

    def test_categories_rpg(self):
        cg = pd.Series([18, 19, 2, 17, 28, 28])
        cu = pd.Series(["PPH", "PTR", "MIS", "LDH", "BOR", "SNE"])
        self.assertEqual(categorie(cg, cu).tolist(), [
            "prairie permanente", "prairie temporaire", "culture", "estive, lande",
            "boisement", "autre"])


class Croisement(unittest.TestCase):
    """Une prairie de 1 ha (100 m x 100 m) dont la moitié devient culture."""

    def setUp(self):
        self.prairie = carres((0, 0, 100, 100))

    def test_moitie_retournee_moitie_non_declaree(self):
        droite = carres((0, 0, 50, 100), categories=["culture"])
        m = croiser(self.prairie, droite)
        self.assertAlmostEqual(m.ha.iloc[0], 1.0)
        self.assertAlmostEqual(m.culture.iloc[0], 0.5)
        self.assertAlmostEqual(m["non déclaré"].iloc[0], 0.5)

    def test_recouvrement_borne_a_la_surface(self):
        # deux parcelles qui se recouvrent : la somme ne dépasse jamais la surface de départ
        droite = carres((0, 0, 100, 100), (0, 0, 100, 100), categories=["culture", "culture"])
        m = croiser(self.prairie, droite)
        self.assertAlmostEqual(m.culture.iloc[0], 1.0)
        self.assertAlmostEqual(m["non déclaré"].iloc[0], 0.0)

    def test_prairie_sans_voisin(self):
        droite = carres((500, 500, 600, 600), categories=["culture"])
        m = croiser(self.prairie, droite)
        self.assertAlmostEqual(m["non déclaré"].iloc[0], 1.0)

    def test_bilan_conserve_la_surface(self):
        droite = carres((0, 0, 30, 100), (30, 0, 80, 100),
                        categories=["prairie permanente", "culture"])
        m = croiser(self.prairie, droite)
        self.assertTrue(np.isclose(m.drop(columns="ha").sum(axis=1), m.ha).all())


class Ocsge(unittest.TestCase):
    def test_herbe_agricole_ou_non(self):
        cs = pd.Series(["CS2.2.1", "CS2.2.1", "CS1.1.1.1", "CS2.1.1.1", "CS1.2.2"])
        us = pd.Series(["US1.1", "US5", "US2", "US1.1", "US6.3"])
        self.assertEqual(etat_ocsge(cs, us).tolist(), [
            "herbe, usage agricole", "herbe, autre usage", "artificialisé", "ligneux", "autre"])


class Satellite(unittest.TestCase):
    def test_calcul_ndvi(self):
        self.assertAlmostEqual(calculer_ndvi(0.45, 0.05), 0.80)
        self.assertEqual(calculer_ndvi(0.0, 0.0), 0.0)

    def test_classification_profils_phenologiques(self):
        # Prairie permanente : NDVI stable toute l'année (pas de sol nu, faible amplitude)
        profil_prairie = [0.48, 0.50, 0.58, 0.66, 0.70, 0.65, 0.58, 0.55, 0.60, 0.56, 0.52, 0.49]
        cat_p, conf_p = classifier_profil_ndvi(profil_prairie)
        self.assertIn("maintien en herbe", cat_p)
        self.assertGreaterEqual(conf_p, 0.85)

        # Culture annuelle (labour + fort pic)
        profil_culture = [0.18, 0.15, 0.22, 0.45, 0.78, 0.82, 0.60, 0.20, 0.16, 0.19, 0.21, 0.18]
        cat_c, conf_c = classifier_profil_ndvi(profil_culture)
        self.assertIn("culture annuelle", cat_c)
        self.assertGreaterEqual(conf_c, 0.90)

        # Surface bâtie / artificialisée
        profil_bati = [0.12, 0.14, 0.15, 0.18, 0.20, 0.19, 0.17, 0.16, 0.15, 0.14, 0.13, 0.12]
        cat_b, _ = classifier_profil_ndvi(profil_bati)
        self.assertEqual(cat_b, "artificialisé")

    def test_audit_et_diagnostic_zone_noire(self):
        audit = auditer_30_parcelles()
        self.assertEqual(len(audit), 30)
        synth = synthese_audit(audit)
        self.assertEqual(synth["nb_maintenues_herbe"], 24)
        self.assertAlmostEqual(synth["part_herbe_surface_pct"], 81.6)
        diag = diagnostic_zone_noire("14118", "Caen")
        self.assertEqual(diag["classe_satellite"], "herbe_non_pac")


if __name__ == "__main__":
    unittest.main()
