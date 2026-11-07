"""Ma commune : quatre chiffres, la carte de ses prairies (les couleurs se cliquent pour les
afficher ou les masquer), et un bouton « Détails » qui ouvre une fenêtre : un seul graphique avec
les chiffres dedans, et les définitions.
Les parcelles sont extraites à la demande par le moteur."""
import altair as alt
import pandas as pd
import streamlit as st

from commun import (FLUX_COULEURS, bornes, deck, exiger_sorties, ha, hex_rgb, motif_manquant,
                    nombre, pct, table)
from prairimetre.config import RECENT
from prairimetre.indicateurs import parcelles_commune

exiger_sorties()
a0, an = bornes()
r0 = an - RECENT
t, z = table("communes"), table("communes_zones").set_index(["insee", "zone"])
ZONES = {"zones humides": "Zones humides",
         "sites protégés": "Sites protégés",
         "prairies sensibles": "Prairies sensibles",
         "ZNIEFF": "ZNIEFF de type 1",
         "captages": "Captages d'eau potable",
         "habitats": "Habitats d'intérêt européen"}

# Sur cette page, pas de petits boutons d'outils au survol des cartes et des graphiques
# (télécharger, plein écran, copier) : ce qui est utile est dans « Détails ».
st.markdown("""
<style>
[data-testid="stElementToolbar"], [data-testid="stElementToolbarButton"],
button[title="View fullscreen"], .vega-embed details { display: none !important; }
</style>""", unsafe_allow_html=True)


@st.cache_data(show_spinner="Le moteur extrait les parcelles de la commune…")
def parcelles(insee, annee):
    """Parcelles de la commune ; l'année des résultats fait partie de la clé du cache, pour
    qu'un nouveau registre soit pris en compte sans redémarrer l'application."""
    disparues, nouvelles = parcelles_commune(insee)
    return disparues.to_crs(4326), nouvelles.to_crs(4326)


def libelle(i):
    """« Rouen (76000, 76100) » : le code postal, pas le code INSEE."""
    cp = t.loc[i, "codes_postaux"] if "codes_postaux" in t else None
    return f"{t.loc[i, 'nom_officiel']} ({cp if isinstance(cp, str) else 'code INSEE ' + i})"


options = t.sort_values("nom_officiel").index.tolist()
if st.session_state.get("commune") not in options:  # 1re visite : la commune qui retourne le plus
    st.session_state["commune"] = t.rang_hectares.idxmin()
insee = st.selectbox("Commune (nom ou code postal)", options, key="commune", format_func=libelle)
r = t.loc[insee]
pp0, ppn = r[f"pp_{a0}"], r[f"pp_{an}"]

st.title(r.nom_officiel)
st.caption(", ".join([r.epci_nom, f"département {r.dep}"]
                     + ([f"Parc naturel régional {r.pnr}"] if isinstance(r.pnr, str) else [])))

# --- Quatre chiffres, rien d'autre ------------------------------------------------------------------
motif = motif_manquant(r.statut)
if motif:
    st.info(f"Pas de diagnostic pour cette commune. {motif} Prairies déclarées : {ha(pp0)} en "
            f"{a0}, {ha(ppn)} en {an}.")
    st.stop()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric(f"Prairies déclarées en {an}", ha(ppn), border=True, height="stretch")
c2.metric(f"Retournées en culture depuis {a0}", ha(r.devenues_culture), border=True,
          height="stretch")
c3.metric(f"Sorties de la déclaration depuis {a0}", ha(r.devenues_non_declare), border=True,
          height="stretch")
c4.metric(f"Ajoutées depuis {a0}", ha(r.apparues), border=True, height="stretch")
# Cinquième chiffre : l'évolution des prairies par rapport à l'année de départ, rouge si elle
# recule, vert si elle progresse (seul le pourcentage, comme les autres chiffres)
evol = r.solde_taux
if pd.notna(evol) and round(100 * evol) != 0:
    texte_evol = pct(evol, 0, signe=True)
    couleur_evol = FLUX_COULEURS["culture"] if evol < 0 else FLUX_COULEURS["prairie permanente"]
else:
    texte_evol, couleur_evol = pct(0, 0), "inherit"
with c5.container(border=True, height="stretch"):
    st.markdown(
        f'<div style="font-size:0.875rem;opacity:0.7">Évolution par rapport à {a0}</div>'
        f'<div style="font-size:2.25rem;line-height:1.3;color:{couleur_evol}">{texte_evol}</div>',
        unsafe_allow_html=True)

# --- Carte des prairies : la légende est le filtre -------------------------------------------------
st.subheader("Carte des prairies")
bouton_details = st.button("Détails de la commune", icon=":material/info:", key="details")

disparues, nouvelles = parcelles(insee, an)
DEVENIR = {"prairie permanente": "toujours en prairie", "culture": "retournée en culture",
           "non déclaré": "sortie de la déclaration",
           "prairie temporaire": "devenue prairie temporaire"}
AVANT = {"culture": "une culture", "non déclaré": "non déclarée",
         "prairie temporaire": "une prairie temporaire"}
autre, ajoutee = "autre (bois, lande…)", f"ajoutée depuis {a0}"
couleurs = ({DEVENIR[c]: FLUX_COULEURS[c] for c in DEVENIR}
            | {autre: FLUX_COULEURS["autre"], ajoutee: FLUX_COULEURS["ajoutée"]})
# Un carré de la couleur de la parcelle devant chaque étiquette de la légende
CARRES = {FLUX_COULEURS["prairie permanente"]: "🟩", FLUX_COULEURS["culture"]: "🟥",
          FLUX_COULEURS["non déclaré"]: "🟧", FLUX_COULEURS["prairie temporaire"]: "🟦",
          FLUX_COULEURS["autre"]: "⬛", FLUX_COULEURS["ajoutée"]: "🟪"}
g0, g1 = disparues.copy(), nouvelles.copy()
g0["libelle"] = g0.devenir.map(lambda x: DEVENIR.get(x, autre))
g1["libelle"] = ajoutee
g1["avant"] = g1.origine.map(lambda x: f"<br/>en {a0} : {AVANT.get(x, 'bois, lande…')}")
g0["avant"] = ""
tout = pd.concat([g0, g1])
if tout.empty:
    st.info("Aucune parcelle à afficher.")
else:
    nombres = tout.libelle.value_counts()
    presentes = [c for c in couleurs if c in nombres.index]
    choix = st.pills(
        "Couleurs affichées", presentes, selection_mode="multi", default=presentes,
        format_func=lambda c: f"{CARRES[couleurs[c]]} {c} ({nombre(nombres[c])})",
        key=f"couleurs_{insee}_{an}", label_visibility="collapsed")
    st.caption("Cliquez sur une couleur pour l'afficher ou la masquer sur la carte.")
    couches = []
    for g, nom in ((g0, "prairies_debut"), (g1, "prairies_ajoutees")):  # ajoutées par-dessus
        g = g[g.libelle.isin(choix)].copy()
        if len(g):
            g["couleur"] = [hex_rgb(couleurs[x]) for x in g.libelle]
            g["t_ha"] = g.ha.map(lambda x: ha(x) if x >= 1 else f"{x:.2f} ha".replace(".", ","))
            couches.append((g[["libelle", "t_ha", "avant", "couleur", "geometry"]], nom))
    # La vue est calculée sur toutes les parcelles : masquer une couleur ne déplace pas la carte
    st.pydeck_chart(deck(couches, tout, "<b>{libelle}</b><br/>{t_ha}{avant}", hauteur=480),
                    width="stretch")
    if not choix:
        st.caption("Aucune couleur sélectionnée : cliquez sur une couleur pour la voir.")
st.caption("Parcelles du registre parcellaire graphique (IGN) : donnée publique et anonyme, "
           "sans nom d'exploitant. La couleur d'une parcelle est celle de la plus grande "
           "part de sa surface.")

# --- Détails : une fenêtre, un seul graphique, les chiffres dedans -------------------------------------
# Les pertes à gauche, partant toutes de zéro : les barres se comparent d'une ligne à l'autre.
SEGMENTS = [("culture", "retournée en culture", FLUX_COULEURS["culture"], "#ffffff"),
            ("non_declare", "sortie de la déclaration", FLUX_COULEURS["non déclaré"], "#1f1f1f"),
            ("autre", "autre (temporaire, bois…)", FLUX_COULEURS["autre"], "#ffffff"),
            ("toujours", "toujours en prairie", FLUX_COULEURS["prairie permanente"], "#ffffff")]
COMMUNE = "Toute la commune"
LARGEUR = 700  # largeur approximative des barres en pixels : sert à savoir si un chiffre y tient

d = pd.DataFrame([{"prairies": pp0, "toujours": r.devenues_reste, "culture": r.devenues_culture,
                   "non_declare": r.devenues_non_declare,
                   "autre": max(pp0 - r.devenues_reste - r.devenues_culture
                                - r.devenues_non_declare, 0)}]
                 + [z.loc[(insee, zone), ["prairies", "toujours", "culture", "non_declare",
                                          "autre"]].to_dict() for zone in ZONES],
                 index=[COMMUNE, *ZONES.values()]).rename_axis("nom").reset_index()
# Une zone sans prairie, ou que la source ne couvre pas (habitats), n'a rien à montrer
masquees = d[~(d.prairies.fillna(0).round() > 0)].nom.tolist()
d = d[d.prairies.fillna(0).round() > 0]

lignes = []
for x in d.itertuples():
    valeurs = {cle: max(getattr(x, cle), 0) for cle, *_ in SEGMENTS}
    total = max(sum(valeurs.values()), 1e-9)
    debut = 0
    for cle, nom, _, couleur_texte in SEGMENTS:
        part = valeurs[cle] / total
        texte, court = ha(valeurs[cle]), nombre(valeurs[cle])
        place = part * LARGEUR  # le chiffre s'écrit avec « ha » s'il tient, sans l'unité sinon
        etiquette = (texte if place >= 8 * len(texte) + 10
                     else court if place >= 8 * len(court) + 10 else "")
        lignes.append({"nom": x.nom, "devenir": nom, "t_ha": texte, "part": pct(part, 0),
                       "debut": debut, "fin": debut + part, "milieu": debut + part / 2,
                       "etiquette": etiquette, "couleur_texte": couleur_texte})
        debut += part
segments = pd.DataFrame(lignes)
totaux = pd.DataFrame({"nom": d.nom, "total": d.prairies.map(ha), "x": 1.0})


def details():
    st.markdown(
        f"**{'−' if ppn < pp0 else '+'}{nombre(abs(ppn - pp0))} ha** de prairies déclarées depuis "
        f"{a0} ({pct(r.solde_taux, 0, signe=True)}) · **{nombre(r.retourne_recent)} ha** "
        f"retournés en culture sur {r0}–{an}")
    sombre = st.context.theme.type == "dark"
    x = alt.X("debut:Q", axis=None, scale=alt.Scale(domain=[0, 1.22], nice=False))
    y = alt.Y("nom:N", sort=d.nom.tolist(), title=None, axis=alt.Axis(
        labelLimit=240, labelOverlap=False, labelFontSize=13, ticks=False, domain=False,
        labelFontWeight=alt.expr(f"datum.value == '{COMMUNE}' ? 700 : 400")))
    barres = alt.Chart(segments).mark_bar(
        height=28, stroke="#0e1117" if sombre else "#ffffff", strokeWidth=1).encode(
        x=x, x2="fin:Q", y=y,
        color=alt.Color("devenir:N", legend=None, scale=alt.Scale(
            domain=[s[1] for s in SEGMENTS], range=[s[2] for s in SEGMENTS])),
        tooltip=[alt.Tooltip("nom:N", title=" "), alt.Tooltip("devenir:N", title="devenir"),
                 alt.Tooltip("t_ha:N", title="surface"), alt.Tooltip("part:N", title="part")])
    etiquettes = alt.Chart(segments).mark_text(fontSize=12, fontWeight="bold").encode(
        x=alt.X("milieu:Q", axis=None, scale=alt.Scale(domain=[0, 1.22], nice=False)), y=y,
        text="etiquette:N", color=alt.Color("couleur_texte:N", scale=None, legend=None))
    fin = alt.Chart(totaux).mark_text(align="left", dx=8, fontSize=12,
                                      color="#d6d5cd" if sombre else "#52514e").encode(
        x=alt.X("x:Q", axis=None, scale=alt.Scale(domain=[0, 1.22], nice=False)), y=y,
        text="total:N")
    st.altair_chart((barres + etiquettes + fin).properties(height=38 * len(d)), width="stretch")
    st.markdown(
        f"🟥 **Retournée en culture** : une culture est déclarée à la place. Perte certaine.  \n"
        f"🟧 **Sortie de la déclaration** : plus déclarée, l'herbe est peut-être encore là.  \n"
        f"⬛ **Autre** : prairie temporaire, bois…  \n"
        f"🟩 **Toujours en prairie**")
    st.caption("Chiffres en hectares. Une prairie peut être dans plusieurs zones : ne pas "
               "additionner les lignes."
               + (f" Masquées : zones sans prairie ou sans donnée ({', '.join(masquees)})."
                  if masquees else ""))


if bouton_details:
    st.dialog(f"Détails : {r.nom_officiel}", width="large")(details)()
