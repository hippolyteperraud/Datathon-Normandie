import unittest

from scripts.analyser_nitrates import analyser


def mesure(station, annee, valeur):
    return {
        "code_station": station,
        "libelle_station": station,
        "date_prelevement": f"{annee}-06-01",
        "resultat": valeur,
        "code_unite": "173",
        "symbole_unite": "mg(NO3)/L",
        "code_support": "3",
        "code_fraction": "3",
        "libelle_fraction": "Phase aqueuse",
        "code_qualification": "1",
        "libelle_qualification": "Correcte",
        "code_statut": "3",
        "mnemo_statut": "Donnée contrôlée niveau 2",
    }


class AnalyseNitrates(unittest.TestCase):
    def setUp(self):
        self.stations = {
            "A": {"code_departement": "14", "libelle_departement": "Calvados",
                  "libelle_station": "Station A"},
            "B": {"code_departement": "50", "libelle_departement": "Manche",
                  "libelle_station": "Station B"},
        }

    def test_compare_des_medianes_par_station_et_fenetre(self):
        lignes = [
            mesure("A", 2015, 10), mesure("A", 2015, 30),
            mesure("A", 2016, 20), mesure("A", 2023, 25), mesure("A", 2024, 35),
            mesure("B", 2015, 100), mesure("B", 2016, 100),
            mesure("B", 2023, 80), mesure("B", 2024, 80),
        ]

        retenues, annuel, departements, tendances, resume = analyser(
            lignes, self.stations, 2015, 2025
        )

        self.assertEqual(len(retenues), 9)
        self.assertEqual(annuel[0]["stations"], 2)
        self.assertEqual(annuel[0]["analyses"], 3)
        self.assertEqual(annuel[0]["mediane_des_medianes_station_mg_l"], 60)
        self.assertEqual(len(departements), 8)
        self.assertEqual(len(tendances), 2)
        self.assertEqual(resume[0]["stations_comparables"], 2)
        self.assertEqual(resume[0]["stations_en_hausse"], 1)
        self.assertEqual(resume[0]["stations_en_baisse"], 1)

    def test_ecarte_les_lignes_hors_criteres_de_comparabilite(self):
        invalide = mesure("A", 2020, 12)
        invalide["code_statut"] = "1"

        retenues, annuel, departements, tendances, resume = analyser(
            [mesure("A", 2020, 10), invalide], self.stations, 2015, 2025
        )

        self.assertEqual(len(retenues), 1)
        self.assertEqual(annuel[0]["analyses"], 1)
        self.assertEqual(departements[0]["code_departement"], "14")
        self.assertEqual(tendances, [])
        self.assertEqual(resume[0]["stations_comparables"], 0)

    def test_refuse_deux_fenetres_temporelles_qui_se_chevauchent(self):
        with self.assertRaises(ValueError):
            analyser([], self.stations, 2020, 2024)


if __name__ == "__main__":
    unittest.main()
