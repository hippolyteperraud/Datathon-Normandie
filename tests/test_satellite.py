"""Tests unitaires du module de télédétection satellitaire (Sentinel-2 / Theia OSO).

Exécution :
    python -m unittest tests/test_satellite.py
"""
import unittest

from prairimetre.satellite import (
    auditer_30_parcelles,
    calculer_ndvi,
    classifier_profil_ndvi,
    diagnostic_zone_noire,
    redresser_pertes_sorties,
    synthese_audit,
)


class TestSatellite(unittest.TestCase):

    def test_calcul_ndvi_valeurs_nominales(self):
        # Sol nu / minéral : NIR proche du rouge
        self.assertAlmostEqual(calculer_ndvi(0.25, 0.25), 0.0)
        # Végétation active dense : NIR fort, Rouge absorbé par chlorophylle
        self.assertAlmostEqual(calculer_ndvi(0.8, 0.2), 0.6)
        # Eau libre : NIR absorbé
        self.assertAlmostEqual(calculer_ndvi(0.05, 0.15), -0.5)

    def test_calcul_ndvi_denominateur_nul(self):
        self.assertEqual(calculer_ndvi(0.0, 0.0), 0.0)

    def test_classification_profil_prairie_permanente(self):
        # Profil typique d'une prairie normande : couvert permanent, pic printanier
        profil_prairie = [0.45, 0.48, 0.62, 0.68, 0.65, 0.60, 0.55, 0.54, 0.58, 0.55, 0.48, 0.44]
        cat, conf = classifier_profil_ndvi(profil_prairie)
        self.assertIn("herbe", cat)
        self.assertGreater(conf, 0.80)

    def test_classification_profil_culture_labour(self):
        # Profil maïs : sol nu au printemps (0.18), forte montée en été (0.80), puis labour
        profil_culture = [0.35, 0.30, 0.18, 0.22, 0.55, 0.78, 0.82, 0.70, 0.40, 0.20, 0.30, 0.32]
        cat, conf = classifier_profil_ndvi(profil_culture)
        self.assertIn("culture", cat)
        self.assertGreater(conf, 0.85)

    def test_classification_profil_artificiel(self):
        # Surface bâtie : NDVI très bas et plat
        profil_bati = [0.15, 0.16, 0.18, 0.20, 0.19, 0.18, 0.17, 0.16, 0.15, 0.15, 0.14, 0.15]
        cat, conf = classifier_profil_ndvi(profil_bati)
        self.assertEqual(cat, "artificialisé")

    def test_synthese_audit_30_parcelles(self):
        parcelles = auditer_30_parcelles()
        self.assertEqual(len(parcelles), 30)

        synth = synthese_audit(parcelles)
        self.assertEqual(synth["nombre_total"], 30)
        self.assertGreater(synth["surface_totale_ha"], 100.0)
        # En Normandie, le maintien réel en herbe des sorties PAC dépasse 75 %
        self.assertGreater(synth["part_herbe_surface_pct"], 75.0)
        # La somme des catégories doit égaler le total
        somme_nb = (synth["nb_maintenues_herbe"] + synth["nb_retournees_culture"] +
                    synth["nb_boisees_friches"] + synth["nb_artificialisees"])
        self.assertEqual(somme_nb, 30)

    def test_redressement_regional_55539_ha(self):
        redressement = redresser_pertes_sorties(55539.0)
        self.assertEqual(redressement["surface_sorties_declarees_ha"], 55539.0)
        # Plus de 35 000 ha doivent être identifiés comme toujours en herbe
        self.assertGreater(redressement["estimation_herbe_maintenue_ha"], 35000.0)
        self.assertLess(redressement["fourchette_herbe_min_ha"], redressement["estimation_herbe_maintenue_ha"])
        self.assertGreater(redressement["fourchette_herbe_max_ha"], redressement["estimation_herbe_maintenue_ha"])
        # Somme maintenue + vraies pertes = total
        self.assertAlmostEqual(
            redressement["estimation_herbe_maintenue_ha"] + redressement["estimation_vraies_pertes_ha"],
            55539.0,
            delta=5.0
        )

    def test_diagnostic_zone_noire(self):
        diag = diagnostic_zone_noire("14001", "Ablon")
        self.assertEqual(diag["code_insee"], "14001")
        self.assertIn("prairies physiques détectées hors PAC", diag["verdict_satellite"])


if __name__ == "__main__":
    unittest.main()
