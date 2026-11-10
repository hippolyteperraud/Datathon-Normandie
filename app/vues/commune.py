"""Ma commune : la carte de ses prairies, sans tableau de chiffres (l'objectif se suit à l'échelle de
la région, sur Objectif 2030). L'échelle à gauche range les couleurs en trois familles : en herbe, pas
en herbe, à vérifier sur le terrain, chacune avec son nombre de parcelles et leurs hectares ; un clic
sur une couleur l'affiche ou la masque.
Les parcelles sont extraites à la demande par le moteur."""
import pandas as pd
import streamlit as st

from commun import FLUX_COULEURS, bornes, deck, exiger_sorties, ha, hex_rgb, nombre, table
from prairimetre.indicateurs import parcelles_commune
from prairimetre.sentinel import SURFACE_MIN_HA
from prairimetre.sentinel import mesures as mesures_satellite

exiger_sorties()
a0, an = bornes()
t = table("communes")

# Sur cette page, pas de petits boutons d'outils au survol des cartes et des graphiques
# (télécharger, plein écran, copier).
st.markdown("""
<style>
[data-testid="stElementToolbar"], [data-testid="stElementToolbarButton"],
button[title="View fullscreen"], .vega-embed details { display: none !important; }
/* La page tient sur un écran, sans dérouler : la carte, à droite dès le haut de la page, prend la
   hauteur de l'écran moins le menu et les marges (environ 150 px), et jamais moins de 360 px. Streamlit fixe la hauteur de la carte et de
   ses cadres (hauteur et flex-basis) : on les remplace toutes. */
[data-testid="stElementContainer"]:has([data-testid="stDeckGlJsonChart"]),
[data-testid="stFullScreenFrame"]:has(> [data-testid="stDeckGlJsonChart"]),
[data-testid="stDeckGlJsonChart"], [data-testid="stDeckGlJsonChart"] > div {
  height: max(360px, calc(100vh - 150px)) !important; flex: 0 0 auto !important; }
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

# Tout tient sur un écran : à gauche le choix de la commune, son nom, puis l'échelle ; à droite la
# carte, sur toute la hauteur
echelle, carte = st.columns([1, 2.3], gap="medium")
with echelle:
    insee = st.selectbox("Commune (nom ou code postal)", options, key="commune", format_func=libelle)
r = t.loc[insee]
echelle.markdown(f"## {r.nom_officiel}")
echelle.caption(", ".join([r.epci_nom, f"département {r.dep}"]
                          + ([f"Parc naturel régional {r.pnr}"] if isinstance(r.pnr, str) else [])))

# La carte ne calcule aucun taux : elle s'affiche dès qu'il y a plus de HERBE_MIN_HA de prairies sur la
# carte (celles de la première année, plus celles ajoutées depuis), même dans les petites communes que
# les taux écartent (moins de 20 ha)
HERBE_MIN_HA = 1
sur_carte = r[f"pp_{a0}"] + sum(r.get(f"venues_{x}", 0) for x in
                                ("culture", "non_declare", "temporaire", "reste"))
if not sur_carte > HERBE_MIN_HA:
    carte.info("Pas de carte pour cette commune : "
               + ("aucune prairie permanente déclarée" if sur_carte == 0 else
                  f"{'moins de 1 ha' if sur_carte < 1 else ha(sur_carte)} de prairie permanente déclarée")
               + f" entre {a0} et {an} (il en faut plus de {HERBE_MIN_HA} ha).")
    st.stop()

# --- La carte et son échelle : en herbe, pas en herbe, à vérifier -----------------------------------
# Chaque prairie de la première année, et chaque prairie ajoutée, a une seule couleur (celle de la plus
# grande part de sa surface). Les prairies sorties de la déclaration sont rangées selon ce qu'en dit le
# satellite : restées vertes (en herbe), labourées ou bâties (pas en herbe), ou à vérifier sur le
# terrain (le satellite ne tranche pas, ou la part sortie est trop petite pour être mesurée).
vus = mesures_satellite()
vus = vus[vus.insee == insee].set_index("id_rpg").etat
FAMILLES = {  # famille -> [(clé, étiquette, couleur)] ; les verts sont en herbe
    "En herbe": [("toujours", "toujours en prairie", FLUX_COULEURS["prairie permanente"]),
                 ("verte", "sortie, restée verte", "#c3d63a"),
                 ("temporaire", "devenue prairie temporaire", "#4fb0a0"),
                 ("ajoutee", f"ajoutée depuis {a0}", "#5cc04a")],
    "Pas en herbe": [("culture", "retournée en culture", FLUX_COULEURS["culture"]),
                     ("labouree", "sortie, labourée", "#7a4a2a"),
                     ("batie", "sortie, bâtie", "#3b3b3b"),
                     ("autre", "bois, lande, autre", "#9c8f7a")],
    "À vérifier sur le terrain": [("verifier", "sortie, on ne sait pas", FLUX_COULEURS["non déclaré"])]}
ETIQUETTE = {cle: e for f in FAMILLES.values() for cle, e, _ in f}
COULEUR = {cle: c for f in FAMILLES.values() for cle, _, c in f}
AIDE = {"toujours": f"Encore déclarée en prairie permanente en {an}.",
        "verte": f"Plus déclarée à la PAC, mais verte sans labour toute l'année {an} sur les images "
                 "Sentinel-2 (herbe ou friche : le satellite ne les distingue pas).",
        "temporaire": f"Déclarée en prairie temporaire en {an} : encore en herbe, mais elle peut être "
                      "labourée à tout moment.",
        "ajoutee": f"Prairie permanente déclarée en {an} sur une parcelle qui ne l'était pas en {a0}.",
        "culture": f"Une culture est déclarée à la place en {an}.",
        "labouree": f"Plus déclarée, et passée par le sol nu en {an} sur les images Sentinel-2.",
        "batie": f"Plus déclarée, et sans végétation toute l'année {an} sur les images Sentinel-2.",
        "autre": f"Déclarée en {an} en bois, lande, jachère ou autre surface.",
        "verifier": "Plus déclarée, et le satellite ne dit rien : signal entre prairie et labour, ou "
                    f"part sortie de moins de {nombre(SURFACE_MIN_HA, 2)} ha (trop peu de pixels)."}

disparues, nouvelles = parcelles(insee, an)
AVANT = {"culture": "une culture", "non déclaré": "non déclarée",
         "prairie temporaire": "une prairie temporaire"}
SATELLITE = {"couvert permanent": "verte", "labourée": "labouree", "bâti ou minéral": "batie"}
g0, g1 = disparues.copy(), nouvelles.copy()
etat = g0.id_parcel.astype(str).map(vus)
g0["cle"] = g0.devenir.map({"prairie permanente": "toujours", "culture": "culture",
                            "prairie temporaire": "temporaire"}).fillna("autre")
sortie = g0.devenir == "non déclaré"
g0.loc[sortie, "cle"] = etat[sortie].map(SATELLITE).fillna("verifier")
g0["avant"] = ""
g0.loc[sortie & etat.notna(), "avant"] = f"<br/>vu du satellite en {an}"
g1["cle"] = "ajoutee"
g1["avant"] = g1.origine.map(lambda x: f"<br/>en {a0} : {AVANT.get(x, 'bois, lande…')}")
tout = pd.concat([g0, g1])
if tout.empty:
    carte.info("Aucune parcelle à afficher.")
    choix = []
else:
    presentes_toutes = set(tout.cle)
    st.html("<style>"
            "[class*='st-key-echelle_'] button[data-variant='pills'] {display: inline-flex; "
            "align-items: center;}"
            "[class*='st-key-echelle_'] button[data-variant='pills']::before {content: ''; width: 13px; "
            "height: 13px; border-radius: 3px; margin-right: 7px; flex: none;}"
            "[class*='st-key-echelle_'] button[aria-pressed='false'] {opacity: 0.45;}"
            "[class*='st-key-echelle_'] [data-testid='stButtonGroup'] > div {flex-wrap: wrap; "
            "overflow: visible; row-gap: 0.3rem;}"
            "[class*='st-key-echelle_'] button[data-variant='pills'] {max-width: 100%; height: auto;}"
            + "".join(f".st-key-echelle_{k}_{insee} button[data-variant='pills']:nth-of-type({n})::before "
                      f"{{background: {c};}}"
                      for k, famille in enumerate(FAMILLES.values())
                      for n, (_, _, c) in enumerate([x for x in famille if x[0] in presentes_toutes], 1))
            + "</style>")
    choix = []
    with echelle:
        for k, (nom, famille) in enumerate(FAMILLES.items()):
            presentes = [cle for cle, _, _ in famille if cle in presentes_toutes]
            # Le nombre de parcelles et leurs hectares, comme sur la carte : chaque parcelle compte
            # en entier dans la couleur de la plus grande part de sa surface
            dans = tout[tout.cle.isin(presentes)]
            s = dans.ha.sum()
            st.markdown(f"**{nom}** · {nombre(len(dans))} parcelle{'s' if len(dans) > 1 else ''}, "
                        + (ha(s) if s >= 1 else f"{s:.2f} ha".replace(".", ","))
                        if presentes else f"**{nom}** · aucune parcelle",
                        help=" ".join(f"**{ETIQUETTE[c]}** : {AIDE[c]}" for c, _, _ in famille))
            if presentes:
                choix += st.pills(nom, presentes, selection_mode="multi", default=presentes,
                                  format_func=ETIQUETTE.get,
                                  key=f"echelle_{k}_{insee}", label_visibility="collapsed")
    couches = []
    for g, nom in ((g0, "prairies_debut"), (g1, "prairies_ajoutees")):  # ajoutées par-dessus
        g = g[g.cle.isin(choix)].copy()
        if len(g):
            g["libelle"] = g.cle.map(ETIQUETTE)
            g["couleur"] = [hex_rgb(COULEUR[x]) for x in g.cle]
            g["t_ha"] = g.ha.map(lambda x: ha(x) if x >= 1 else f"{x:.2f} ha".replace(".", ","))
            couches.append((g[["libelle", "t_ha", "avant", "couleur", "geometry"]], nom))
    # La vue est calculée sur toutes les parcelles : masquer une couleur ne déplace pas la carte
    carte.pydeck_chart(deck(couches, tout, "<b>{libelle}</b><br/>{t_ha}{avant}", hauteur=720),
                       width="stretch", height=720)
    if not choix:
        carte.caption("Aucune couleur sélectionnée : cliquez sur une couleur pour la voir.")
