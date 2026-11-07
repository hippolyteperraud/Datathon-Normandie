"""Tests du module de vérification par images satellite (sans données réelles).

    python -m unittest tests/test_satellite.py
"""
import tempfile
import unittest
from pathlib import Path

from prairimetre.satellite import (PARCELLES_30, calculer_ndvi, classer_profil_ndvi,
                                   creer_fichier_vierge, fourchette_ha, intervalle_wilson,
                                   lire_observations, synthese)


class Ndvi(unittest.TestCase):
    def test_valeurs(self):
        self.assertAlmostEqual(calculer_ndvi(0.25, 0.25), 0.0)
        self.assertAlmostEqual(calculer_ndvi(0.8, 0.2), 0.6)
        self.assertAlmostEqual(calculer_ndvi(0.05, 0.15), -0.5)
        self.assertEqual(calculer_ndvi(0.0, 0.0), 0.0)

    def test_profils_types(self):
        prairie = [0.45, 0.48, 0.62, 0.68, 0.65, 0.60, 0.55, 0.54, 0.58, 0.55, 0.48, 0.44]
        mais = [0.35, 0.30, 0.18, 0.22, 0.55, 0.78, 0.82, 0.70, 0.40, 0.20, 0.30, 0.32]
        bati = [0.15, 0.16, 0.18, 0.20, 0.19, 0.18, 0.17, 0.16, 0.15, 0.15, 0.14, 0.15]
        foret = [0.70, 0.72, 0.80, 0.85, 0.86, 0.85, 0.84, 0.83, 0.80, 0.75, 0.72, 0.70]
        self.assertEqual(classer_profil_ndvi(prairie), "herbe")
        self.assertEqual(classer_profil_ndvi(mais), "culture")
        self.assertEqual(classer_profil_ndvi(bati), "artificialise")
        self.assertEqual(classer_profil_ndvi(foret), "ligneux")
        self.assertEqual(classer_profil_ndvi([0.5, 0.6]), "indetermine")  # trop peu de mois


class Observations(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin = Path(self.dossier.name) / "30_parcelles.csv"
        creer_fichier_vierge(self.chemin)

    def tearDown(self):
        self.dossier.cleanup()

    def remplir(self, lignes):
        texte = self.chemin.read_text(encoding="utf-8-sig").splitlines()
        for num, (etat, source, date, ndvi) in lignes.items():
            champs = texte[num].split(";")
            champs[7:11] = [etat, source, date, ndvi]
            texte[num] = ";".join(champs)
        self.chemin.write_text("\n".join(texte) + "\n", encoding="utf-8-sig")

    def test_fichier_vierge_sans_resultat(self):
        self.assertEqual(len(self.chemin.read_text(encoding="utf-8-sig").splitlines()),
                         len(PARCELLES_30) + 1)
        self.assertEqual(lire_observations(self.chemin), [])
        self.assertIsNone(synthese([]))

    def test_ne_jamais_ecraser(self):
        self.remplir({1: ("herbe", "IGN", "2025-06-01", "")})
        creer_fichier_vierge(self.chemin)
        self.assertEqual(len(lire_observations(self.chemin)), 1)

    def test_observation_sans_source_refusee(self):
        self.remplir({1: ("herbe", "", "", "")})
        with self.assertRaises(ValueError):
            lire_observations(self.chemin)

    def test_etat_inconnu_refuse(self):
        self.remplir({1: ("verte", "IGN", "2025-06-01", "")})
        with self.assertRaises(ValueError):
            lire_observations(self.chemin)

    def test_etat_deduit_du_ndvi(self):
        profil = "0.45 0.48 0.62 0.68 0.65 0.60 0.55 0.54 0.58 0.55 0.48 0.44"
        self.remplir({2: ("", "Sentinel-2 L2A", "2025", profil)})
        (o,) = lire_observations(self.chemin)
        self.assertEqual((o["etat"], o["methode"]), ("herbe", "NDVI"))

    def test_synthese_et_fourchette(self):
        self.remplir({1: ("herbe", "IGN", "2025-06-01", ""), 2: ("herbe", "IGN", "2025-06-01", ""),
                      3: ("culture", "IGN", "2025-06-01", ""),
                      4: ("indetermine", "IGN", "2025-06-01", "")})
        r = synthese(lire_observations(self.chemin))
        self.assertEqual((r["observees"], r["tranchees"], r["indeterminees"]), (4, 3, 1))
        self.assertAlmostEqual(r["part_herbe"], 2 / 3)
        self.assertLess(r["part_herbe_bas"], r["part_herbe"])
        self.assertGreater(r["part_herbe_haut"], r["part_herbe"])
        bas, haut = fourchette_ha(r, 1000)
        self.assertLess(bas, haut)


class RegleSentinel(unittest.TestCase):
    """La règle automatique sur des profils inventés (sans appel au service)."""

    @staticmethod
    def profil(ndvi, nu=None, sale=None):
        import pandas as pd
        n = len(ndvi)
        return pd.DataFrame({"date": [f"2025-{1 + i % 12:02d}-01" for i in range(n)], "item": "x",
                             "part_sale": sale or [0.0] * n, "part_sol_nu": nu or [0.0] * n,
                             "ndvi": ndvi})

    def test_prairie(self):
        from prairimetre.sentinel import classer
        self.assertEqual(classer(self.profil([0.5, 0.6, 0.62, 0.55, 0.48, 0.5, 0.52]))[0],
                         "couvert permanent")

    def test_labour(self):
        from prairimetre.sentinel import classer
        p = self.profil([0.4, 0.18, 0.2, 0.5, 0.8, 0.7, 0.3], nu=[0, 0.9, 0.8, 0, 0, 0, 0.1])
        self.assertEqual(classer(p)[0], "labourée")

    def test_trop_de_nuages(self):
        from prairimetre.sentinel import classer
        p = self.profil([0.5] * 8, sale=[0.5] * 8)
        self.assertEqual(classer(p)[0], "indéterminé")

    def test_bati(self):
        from prairimetre.sentinel import classer
        self.assertEqual(classer(self.profil([0.1, 0.12, 0.15, 0.11, 0.1, 0.13]))[0], "bâti ou minéral")


class Wilson(unittest.TestCase):
    def test_bornes(self):
        self.assertEqual(intervalle_wilson(0, 0), (0.0, 1.0))
        bas, haut = intervalle_wilson(24, 30)
        self.assertTrue(0.6 < bas < 0.8 < haut < 0.95)


if __name__ == "__main__":
    unittest.main()
