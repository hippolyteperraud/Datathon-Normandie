"""Les années à part du registre (onglet Technique) : 2018→2019 et 2022→2023, repérées par le calcul,
expliquées par des sources officielles (references.py), et le ratio de la PAC.

Une année est à part quand ses sorties de la déclaration dépassent le double d'une année ordinaire,
son retournement 1,75 fois, ou la part de ses sorties déclarées de nouveau ensuite 1,75 fois (année
ordinaire = médiane des autres)."""
import altair as alt
import pandas as pd
import streamlit as st

from commun import AXE_FR, DEPARTEMENTS, OFFICIEL, bornes, evaluation, ha, nombre, table
from references import AGRICULTEUR_ACTIF, FIN_AUTORISATION_2019, RATIOS, REFERENCE_RATIO

ORANGE = "#f0a202"


def _fois_ordinaire(v):
    return pd.Series([x / v.drop(i).median() if pd.notna(x) else float("nan") for i, x in v.items()],
                     index=v.index)


def _annees():
    a0, an = bornes()
    serie, suivi, saa = table("serie_region"), table("suivi_sorties"), evaluation("saa")
    s = serie.assign(fin=serie.periode.str[-4:].astype(int))
    s["libelle"] = s.periode.str.replace("-", "→")
    s = s.merge(suivi[suivi.dep == "région"].drop(columns=["dep", "fin"]), on="periode", how="left")
    s["part_revenue"] = (s.redeclares_ha / s.sortis_ha).where(s.fin < an)
    s["fois_sorties"] = _fois_ordinaire(s.sortie_non_declare)
    s["fois_retournement"] = _fois_ordinaire(s.sortie_culture)
    s["trou"] = _fois_ordinaire(s.part_revenue) > 1.75
    s["sorties_fortes"] = s.fois_sorties > 2
    s["retournement_fort"] = s.fois_retournement > 1.75
    if saa is not None:
        s = s.merge(saa[["annee", "saa_variation"]], left_on="fin", right_on="annee", how="left")
    else:
        s["saa_variation"] = float("nan")
    return s, suivi, an


def _draaf(periode, suivi):
    p = suivi[(suivi.periode == periode) & (suivi.dep != "région")].set_index("dep").sortis_ha
    d = pd.DataFrame([{"département": DEPARTEMENTS.get(k, k), "source": src, "ha": v, "valeur": ha(v)}
                      for k, draaf in AGRICULTEUR_ACTIF["prairies_par_dep_ha"].items()
                      for src, v in (("DRAAF Normandie", draaf), ("Prairimètre", p.get(k, 0)))])
    return alt.Chart(d).mark_bar(cornerRadiusEnd=3, height=10).encode(
        y=alt.Y("département:N", title=None, sort=None, axis=alt.Axis(labelOverlap=False)),
        yOffset="source:N", x=alt.X("ha:Q", title="hectares sortis", axis=alt.Axis(labelExpr=AXE_FR)),
        color=alt.Color("source:N", title=None, legend=alt.Legend(orient="bottom"),
                        scale=alt.Scale(range=["#8a897f", ORANGE])),
        tooltip=[alt.Tooltip("département:N"), alt.Tooltip("source:N"),
                 alt.Tooltip("valeur:N", title="ha")]).properties(height=240)


def afficher():
    s, suivi, an = _annees()
    ordinaire_retour = s.part_revenue[~s.trou].median()
    for _, r in s[s.sorties_fortes | s.retournement_fort | s.trou].iterrows():
        points = []
        if r.retournement_fort:
            points.append(f"{ha(r.sortie_culture)} retournés en culture, {nombre(r.fois_retournement, 1)} "
                          "fois une année ordinaire.")
            if r.fin == 2019:
                points.append("C'est l'année où retourner une prairie ne demande plus d'autorisation en "
                              f"Normandie ([{FIN_AUTORISATION_2019['texte']}]({FIN_AUTORISATION_2019['lien']})) : "
                              "lien très probable, pas démontré.")
        if r.sorties_fortes:
            points.append(f"{ha(r.sortie_non_declare)} sortis de la déclaration, {nombre(r.fois_sorties, 1)} "
                          f"fois une année ordinaire, à {nombre(100 * r.entieres_ha / r.sortis_ha, 0)} ha sur "
                          "100 en parcelles entières.")
            if r.fin == 2023:
                aa = AGRICULTEUR_ACTIF
                points.append(f"La PAC réserve désormais ses aides aux « agriculteurs actifs » : "
                              f"{nombre(aa['sortants'])} exploitations sortent, dont près de "
                              f"{aa['part_67_ans_pct']} sur 100 ont un chef de 67 ans ou plus "
                              f"([{aa['texte']}]({aa['lien']})).")
        if r.trou:
            points.append(f"{nombre(100 * r.part_revenue, 0)} ha sur 100 des surfaces sorties reviennent "
                          f"ensuite, contre {nombre(100 * ordinaire_retour, 0)} d'habitude : le registre publié "
                          "cette année-là était incomplet (surtout l'Orne et la Seine-Maritime). Explication "
                          "probable, non confirmée : il donne l'état connu au 1er janvier suivant, sans les "
                          "dossiers pas encore instruits.")
        if pd.notna(r.saa_variation):
            meme_sens = (r.saa_variation < 0) == (r.solde < 0)
            points.append(f"Statistique agricole : {ha(r.saa_variation, signe=True)} (registre : "
                          f"{ha(r.solde, signe=True)}) : "
                          + ("la perte est réelle." if meme_sens else "elle ne voit pas cette perte."))
        with st.container(border=True):
            st.markdown(f"**{r.libelle}**\n" + "\n".join(f"- {p}" for p in points))
            if r.fin == 2023:
                st.altair_chart(_draaf(r.periode, suivi), width="stretch")

    st.markdown("**Le ratio de la PAC ne donne plus l'alerte.** Il compare la part des prairies dans la "
                f"surface agricole déclarée à celle de {REFERENCE_RATIO}.\n"
                + "\n".join(f"- {r['annee']} : recul de {nombre(-r['evolution_pct'], 2)} % (référence "
                            f"{nombre(r['reference_pct'], 2)} %), {r['consequence']} "
                            f"([{r['texte']}]({r['lien']}))." for r in RATIOS)
                + f"\n- {OFFICIEL['date']} : recul de {nombre(-OFFICIEL['ratio_evol_pct'], 2)} % "
                  f"({OFFICIEL['source']}).\n\nLa référence {REFERENCE_RATIO} a été recalculée en 2024 : le "
                  "recul de 2023 s'efface. L'objectif se suit donc avec la statistique agricole.")
