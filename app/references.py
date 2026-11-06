"""Chiffres et faits officiels qui expliquent les années à part du registre. Chacun garde sa source
exacte : ce ne sont pas des résultats du projet, mais ce qui permet de les comprendre. Ils ne sont
affichés que si les données du moteur montrent l'année concernée comme à part."""

# Le ratio officiel de prairies permanentes (BCAE 1), tel que publié chaque année au Journal officiel
RATIOS = [
    {"annee": 2023, "ratio_pct": 32.68, "reference_pct": 34.93, "evolution_pct": -6.45,
     "consequence": "autorisation préalable pour retourner une prairie, et obligation de "
                    "réimplanter les prairies retournées",
     "texte": "Arrêté du 31 octobre 2023, JORF n° 0254 du 1er novembre 2023",
     "lien": "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000048297174"},
    {"annee": 2024, "ratio_pct": 32.54, "reference_pct": 32.94, "evolution_pct": -1.21,
     "consequence": "aucune obligation",
     "texte": "Arrêté du 3 décembre 2024, JORF n° 0287 du 5 décembre 2024 (référence 2018 "
              "« retraitée », règlement délégué (UE) 2024/1235)",
     "lien": "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000050732250"},
]

# 2022 -> 2023 : la nouvelle PAC réserve les aides aux « agriculteurs actifs » (assurés à l'ATEXA ;
# après 67 ans, sans avoir fait valoir leurs droits à la retraite)
AGRICULTEUR_ACTIF = {
    "baisse_declarants_pct": 19, "sortants": 5391, "nouveaux": 985,
    "part_67_ans_pct": 60, "surface_perdue_ha": 32616, "prairies_sorties_ha": 29000,
    "part_prairies_pct": 90,
    # Prairies permanentes sorties du champ de la PAC, par département (graphique de la note)
    "prairies_par_dep_ha": {"14": 7056, "27": 2204, "50": 10189, "61": 6191, "76": 3709},
    "texte": "DRAAF Normandie, Agreste Conjoncture n° 55, décembre 2024, p. 4 (données ASP)",
    "lien": "https://draaf.normandie.agriculture.gouv.fr/"
            "conjoncture-mensuelle-agricole-decembre-2024-a4275.html",
}

# 2018 -> 2019 : la Normandie sort du régime d'autorisation de retournement des prairies
FIN_AUTORISATION_2019 = {
    "texte": "Arrêté du 13 novembre 2018, cité dans la réponse du ministère à la question écrite "
             "n° 08515 (Sénat, 2019)",
    "lien": "https://www.senat.fr/questions/base/2019/qSEQ19010615S.html",
}
