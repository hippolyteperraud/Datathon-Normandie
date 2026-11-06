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
from prairimetre.indicateurs import suivi_entre
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


class SuiviSorties(unittest.TestCase):
    """Trois prairies : une sortie entière qui revient, une sortie entière qui ne revient pas,
    une à moitié retournée."""

    def test_sorties_revenues_ou_non(self):
        court = pd.DataFrame({"dep": ["14", "14", "50"], "ha": [2.0, 3.0, 4.0],
                              "non déclaré": [2.0, 3.0, 0.0], "culture": [0.0, 0.0, 2.0]})
        long = court.assign(**{"non déclaré": [0.0, 3.0, 0.0]})
        g = suivi_entre(court, long)
        r = g.loc["région"]
        self.assertAlmostEqual(r.sortis_ha, 5.0)
        self.assertAlmostEqual(r.entieres_ha, 5.0)
        self.assertAlmostEqual(r.toujours_hors_ha, 3.0)
        self.assertAlmostEqual(r.redeclares_ha, 2.0)
        self.assertAlmostEqual(r.retournes_ha, 2.0)
        self.assertAlmostEqual(g.loc["50", "sortis_ha"], 0.0)

    def test_jamais_plus_hors_que_sorti(self):
        # une parcelle qui n'était pas sortie l'année suivante, mais l'est à la fin
        court = pd.DataFrame({"dep": ["61"], "ha": [1.0], "non déclaré": [0.2], "culture": [0.0]})
        long = court.assign(**{"non déclaré": [1.0]})
        r = suivi_entre(court, long).loc["région"]
        self.assertAlmostEqual(r.toujours_hors_ha, 0.2)
        self.assertAlmostEqual(r.entieres_ha, 0.0)


if __name__ == "__main__":
    unittest.main()
