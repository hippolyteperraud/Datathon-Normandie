"""2. Ce qui marche : l'interdiction de retourner (mesurée à terrain égal), les communes où ça va bien,
et ce qu'il faut faire. Tout tient sur un écran (sorties/evaluation_terrain.csv, evaluation_zonages.csv,
evaluation_classes.csv, communes.csv)."""
import altair as alt
import pandas as pd
import streamlit as st

from commun import (FLUX_COULEURS, GAIN_MINIMUM_HA, HORS, bornes, communes_carte, communes_exemples,
                    comparaison, deck, evaluation, exiger_sorties, ha, hex_rgb, nombre,
                    selection_carte, table)

exiger_sorties()
a0, an = bornes()
terrain = evaluation("terrain")
zon = evaluation("zonages", index_col=0)
cl = evaluation("classes", index_col=0)
_, captages = comparaison("aires_alimentation_captages")
if terrain is None or zon is None or cl is None:
    st.info("Résultats manquants : lancez « Relancer les calculs » dans Technique.")
    st.stop()

r = terrain.set_index("comparaison").rapport_meme_commune
seul = r[r.index.str.startswith("inventaires")].iloc[0]
n2000 = r[r.index.str.contains("Natura")].iloc[0]
humides = r[r.index.str.contains("zones humides")].iloc[0]
sensibles = zon.loc["prairies_sensibles", "part_des_prairies"]
hors = cl.loc["aucun zonage", "part_du_retournement"]
t = table("communes")
gain, gardent = communes_exemples(t)
VERT, VERT_CLAIR = FLUX_COULEURS["prairie permanente"], "#8fc93a"

st.title("Ce qui marche")
st.markdown(f"### Interdire le retournement marche, et {nombre(len(gain) + len(gardent))} communes "
            "gagnent ou gardent leurs prairies.")

gauche, droite = st.columns([1, 1.2], gap="large")

# --- L'interdiction : combien de fois moins de retournement qu'à côté ------------------------------
with gauche:
    st.markdown(f"**À terrain égal, {nombre(1 / n2000, 0)} à {nombre(1 / humides, 0)} fois moins de "
                f"retournement là où il est interdit. Mais l'interdiction ne couvre que "
                f"{nombre(100 * sensibles, 0)} ha de prairies sur 100.**")
    lignes = [("dans les sites Natura 2000", "prairies sensibles, interdiction", n2000, VERT),
              ("dans les zones humides", "prairies sensibles, interdiction", humides, VERT)]
    if len(captages):
        lignes.append(("au-dessus des captages d'eau", "aucune règle", captages.mean(), "#c2452d"))
    d = pd.DataFrame([{"ou": o, "quoi": q, "fois": 1 / v, "couleur": c,
                       "texte": "autant qu'à côté" if 0.85 < v < 1.2 else f"{nombre(1 / v, 0)} fois moins"}
                      for o, q, v, c in lignes])
    base = alt.Chart(d).encode(
        y=alt.Y("ou:N", sort=None, title=None,
                axis=alt.Axis(labelLimit=260, labelFontSize=13, ticks=False, domain=False, labelPadding=8)),
        x=alt.X("fois:Q", title=None, axis=None, scale=alt.Scale(domain=[0, d.fois.max() * 1.45])))
    barres = base.mark_bar(height=24, cornerRadiusEnd=4).encode(
        color=alt.Color("couleur:N", scale=None),
        tooltip=[alt.Tooltip("quoi:N", title=" "), alt.Tooltip("texte:N", title="retournement")])
    sombre = st.context.theme.type == "dark"
    textes = base.mark_text(align="left", dx=8, fontSize=14, fontWeight="bold",
                            color="#e8e7e0" if sombre else "#33332f").encode(text="texte:N")
    st.altair_chart((barres + textes).properties(height=52 * len(d)), width="stretch")
    st.caption(f"Retournement comparé aux autres prairies du même site ou de la même commune. Le terrain "
               f"joue aussi (sans aucune règle, les prairies d'inventaire sont {nombre(1 / seul, 1)} fois "
               f"moins retournées), mais l'interdiction agit en plus. {nombre(100 * hors, 0)} ha sur 100 "
               "du retournement se font hors de tout zonage. Détail : Technique → Preuves.")

# --- Les communes où ça va bien -----------------------------------------------------------------
with droite:
    st.markdown(f"**Depuis {a0}, {nombre(len(gain))} communes gagnent des prairies, "
                f"{nombre(len(gardent))} n'en perdent aucune.**")
    couleur = {i: VERT_CLAIR for i in gardent} | {i: VERT for i in gain.index}

    def info(i):
        if i in gain.index:
            return f"{ha(gain[i], signe=True)} de prairies sur d'anciennes cultures depuis {a0}"
        return f"aucune prairie perdue depuis {a0}" if i in couleur else ""

    g = communes_carte().copy()
    g["couleur"] = [hex_rgb(couleur[i]) if i in couleur else hex_rgb(HORS, 55) for i in g.insee]
    g["valeur"] = g.insee.map(info)
    CLE = "carte_exemples"
    evt = st.pydeck_chart(deck([(g[["insee", "nom_officiel", "couleur", "valeur", "geometry"]], CLE)], g,
                               "<b>{nom_officiel}</b><br/>{valeur}", hauteur=280, zoom=6.25),
                          on_select="rerun", selection_mode="single-object", width="stretch", height=280,
                          key=CLE)
    st.markdown(
        f'<span style="color:{VERT}">■</span> gagnent au moins {GAIN_MINIMUM_HA} ha sur d\'anciennes '
        f'cultures &nbsp; <span style="color:{VERT_CLAIR}">■</span> ne perdent rien &nbsp; '
        f'<span style="color:{HORS}">■</span> les autres', unsafe_allow_html=True,
        help="Un clic sur une commune ouvre sa fiche. Les nouvelles déclarations et les prairies "
             "temporaires devenues permanentes ne comptent pas comme un gain.")
    clic = selection_carte(evt, CLE, "insee")
    if clic and clic != st.session_state.get(f"_clic_{CLE}"):  # un clic ne compte qu'une fois
        st.session_state[f"_clic_{CLE}"] = clic
        st.session_state["commune"] = clic
        st.switch_page("vues/commune.py")

# --- Ce qu'il faut faire : quatre actions, chacune tirée des résultats -----------------------------
st.subheader("Ce qu'il faut faire")
try:
    from prairimetre.sentinel import resume_mesures
    sat = resume_mesures()
except FileNotFoundError:
    sat = None
actions = [("Suivre l'objectif avec la statistique agricole",
            "La part de l'herbe dans la surface agricole, chaque année. Le registre PAC dit où l'on perd, "
            "pas combien.", "vues/objectif.py"),
           ("Étendre l'interdiction de retourner",
            f"Elle ne couvre que {nombre(100 * sensibles, 0)} ha sur 100"
            + (" ; au-dessus des captages d'eau, rien ne retient l'herbe." if len(captages) and
               0.85 < captages.mean() < 1.2 else "."), None),
           ("Regarder chaque commune",
            "Sur la carte : ce qui est en herbe, ce qui ne l'est plus, ce qu'il faut aller vérifier.",
            "vues/commune.py"),
           ("Vérifier par satellite les prairies sorties",
            (f"{round(100 * sat['ha_verts'] / sat['ha'])} ha sur 100 restent verts : ne pas les compter "
             "comme perdues trop vite." if sat else "Avant de les compter comme perdues."),
            "vues/technique.py")]
for col, (titre, texte, page) in zip(st.columns(4), actions):
    with col.container(border=True, height="stretch"):
        st.markdown(f"**{titre}**  \n{texte}")
        if page:
            try:  # le lien n'existe que dans l'appli lancée par accueil.py (menu)
                st.page_link(page, label="Voir", icon=":material/arrow_forward:")
            except st.errors.StreamlitAPIException:
                pass
