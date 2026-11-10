"""Chiffres et faits officiels qui expliquent les années à part du registre. Chacun garde sa source
exacte : ce ne sont pas des résultats du projet, mais ce qui permet de les comprendre. Ils ne sont
affichés que si les données du moteur montrent l'année concernée comme à part."""

# L'objectif régional, tel qu'écrit dans la Stratégie régionale pour la biodiversité (SRB)
OBJECTIF_REGIONAL = {
    "objectif": "Atteindre zéro perte nette de prairies permanentes à l'échelle normande à "
                "l’horizon 2030",
    # Citations mot pour mot de la fiche (texte copié dans data/references/pdf.txt)
    "cible": "Maintenir les prairies permanentes à 39% de la Surface Agricole Utile (Agreste, 2020, "
             "données 2019)",
    "periode": "Maintenir autant de prairies permanentes entre 2021 et 2030",
    "indicateur": "Surface des prairies permanentes : 39% de la Surface Agricole Utile (Agreste, 2020, "
                  "données 2019)",
    "part_sau_pct": 39,
    # La cible a été fixée sur les chiffres 2019 publiés en 2020 ; Agreste a depuis révisé ses
    # séries (cohérence avec le recensement agricole 2020) : voir la part 2019 dans les séries longues
    "annee_cible": 2019,
    "texte": "Stratégie régionale pour la biodiversité Normandie 2030, objectif III.5, p. 47",
    "lien": "https://www.normandie.fr/sites/default/files/2023-05/srb-normandie-fiches-objectifs.pdf",
}

# Le suivi officiel de l'objectif, tel que la Région le publie : part de la STH dans la SAU d'après la
# statistique agricole annuelle (SAA), référence 2021. Recalculée sur les séries longues Agreste
# 2010-2025, la part 2021 vaut 37,69 % (778 625 / 2 066 023) : le bilan écrit 37,6 %.
SUIVI_SRB = {
    "annee_reference": 2021,
    "parts_pct": {2021: 37.6, 2024: 37.4},
    "sth_ha": {2021: 778625, 2024: 770754},
    "texte": "Région Normandie, premier bilan 2022-2024 de la Stratégie régionale pour la biodiversité "
             "(réponse des mentors du datathon, novembre 2026)",
    # Citations mot pour mot de la réponse
    "citations": ["Notre année de référence est 2021 (37,6% ; 778 625 ha).",
                  "… un ratio de 37,4% de STH par rapport à la SAU (770 754 ha) en 2024."],
    # Ce que le bilan dit de 2023 (hausse de la STH dans la SAA, chute dans le registre PAC)
    "lecture_2023": "La chute brutale enregistrée par le registre PAC au printemps 2023 met du temps à "
                    "être digérée et validée dans les modèles de la statistique agricole.",
}

# Le ratio officiel de prairies permanentes (BCAE 1), publié chaque année au Journal officiel. Il se
# compare toujours à l'année 2018 (règlement délégué (UE) 2022/126, article 48)
REFERENCE_RATIO = 2018
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
