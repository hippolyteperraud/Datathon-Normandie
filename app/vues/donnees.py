"""Où aller voir : où aller voir les prairies sorties de la déclaration, pour savoir si l'herbe est
encore là. Visées : les communes qui portent la moitié des sorties ; prioritaires celles où la réponse
peut changer la liste des communes où l'on retourne le plus. Puis ce que le satellite y voit déjà
(images Sentinel-2, prairimetre/sentinel.py, preuves dans verification/sentinel2/)."""
import pandas as pd
import pydeck as pdk
import streamlit as st

from commun import (ACTIONS, HORS, bornes, communes_carte, communes_moitie, deck, exiger_sorties, ha,
                    hex_rgb, legende, nombre, pct, selection_carte, table)

exiger_sorties()
a0, an = bornes()
t = table("communes")

sorties = t.devenues_non_declare
part_sortie = sorties / t[f"pp_{a0}"]
# Les communes, de la plus touchée à la moins touchée, qui portent ensemble la moitié des sorties
rang = sorties[t.statut == "calculé"].sort_values(ascending=False)
moitie = rang.index[:int((rang.cumsum() / rang.sum() < 0.5).sum() + 1)]
liste_payer = set(communes_moitie(t))
# Hors de la liste, la réponse décide si la commune y entre ; dans la liste, elle n'y change rien
prioritaires = [i for i in moitie if i not in liste_payer]
secondaires = [i for i in moitie if i in liste_payer]
payer = ACTIONS["payer"]["titre"]

st.title("Où aller voir nos prairies")
st.subheader("Celles sorties de la déclaration : l'herbe est-elle encore là ?")


def chiffre(colonne, titre, valeur, note):
    colonne.metric(titre, valeur, note, delta_color="off", delta_arrow="off", border=True,
                   height="stretch")


c1, c2 = st.columns(2)
# La vérification par images Sentinel-2, si elle a tourné : l'échantillon tiré au hasard parmi toutes
# les sorties, et les parcelles mesurées une à une dans les communes à aller voir
try:
    from prairimetre.sentinel import DOSSIER as DOSSIER_SAT, FICHIER_COMMUNES, bilan as bilan_sat
    echantillon = bilan_sat(pd.read_csv(DOSSIER_SAT / "parcelles.csv",
                                        dtype={"id_rpg": str, "insee": str}))["30 parcelles"]
    mesures = pd.read_csv(FICHIER_COMMUNES, dtype={"id_rpg": str, "insee": str})         if FICHIER_COMMUNES.exists() else None
except FileNotFoundError:
    echantillon, mesures = None, None
chiffre(c1, f"Sorties de la déclaration depuis {a0}", ha(sorties.sum()),
        f"encore vertes : {echantillon['couvert']} parcelles sur {echantillon['tranchees']} (satellite)"
        if echantillon and echantillon["tranchees"] else "encore en herbe : ne sait pas")
chiffre(c2, "Communes à aller voir", nombre(len(moitie)),
        f"{ha(sorties[moitie].sum())}, la moitié des sorties")

FORT, CLAIR = ACTIONS["verifier"]["couleur"], "#f6b89c"
fort, clair = set(prioritaires), set(secondaires)
PRIORITES = {"prioritaire": ("Prioritaire", FORT, sorties[prioritaires].sum(), len(prioritaires)),
             "secondaire": ("Secondaire", CLAIR, sorties[secondaires].sum(), len(secondaires))}

zone_carte = st.container()  # la carte au-dessus de sa légende, qui décide de ce qu'elle montre
# La légende se clique : chaque bouton garde son carré de couleur, vide quand il est éteint
st.html("<style>"
        ".st-key-legende_priorite button[data-variant='pills'] {display: inline-flex; "
        "align-items: center;}"
        ".st-key-legende_priorite button[data-variant='pills']::before {content: ''; width: 12px; "
        "height: 12px; border-radius: 3px; margin-right: 6px; "
        "border: 1px solid rgba(128,128,128,0.45);}"
        ".st-key-legende_priorite button[aria-pressed='false'] {opacity: 0.6;}"
        + "".join(f".st-key-legende_priorite button[aria-pressed='true']"
                  f":nth-of-type({n})::before {{background: {c};}}"
                  for n, (_, c, _, _) in enumerate(PRIORITES.values(), 1))
        + "</style>")
visibles = st.pills(
    "Priorité", list(PRIORITES), selection_mode="multi", default=list(PRIORITES),
    format_func=lambda p: f"{PRIORITES[p][0]} : {ha(PRIORITES[p][2])}, "
                          f"{nombre(PRIORITES[p][3])} communes",
    key="legende_priorite",
    help=f"Ces communes portent la moitié des sorties. **Prioritaire** : la commune n'est pas "
         f"dans « {payer} » ; si ces prairies sont perdues, elle peut y entrer : aller voir "
         f"peut changer la décision. **Secondaire** : la commune est déjà dans « {payer} » : "
         "aller voir ne change pas la décision.")
fort_vu = fort if "prioritaire" in visibles else set()
clair_vu = clair if "secondaire" in visibles else set()

g = communes_carte().copy()
g["couleur"] = [hex_rgb(FORT) if i in fort_vu else hex_rgb(CLAIR) if i in clair_vu
                else hex_rgb(HORS, 200) for i in g.insee]
g["valeur"] = g.insee.map(lambda i: f"{ha(sorties[i])} sortis, {pct(part_sortie[i], 0)} de ses prairies")
CLE = "carte_sorties"
evt = zone_carte.pydeck_chart(deck([(g[["insee", "nom_officiel", "couleur", "valeur", "geometry"]], CLE)],
                                   g, "<b>{nom_officiel}</b><br/>{valeur}"),
                              on_select="rerun", selection_mode="single-object", width="stretch",
                              key=CLE)
# Un clic ne compte qu'une fois (la sélection de la carte persiste d'un rechargement à l'autre)
clic = selection_carte(evt, CLE, "insee")
if clic and clic != st.session_state.get(f"_clic_{CLE}"):
    st.session_state[f"_clic_{CLE}"] = clic
    st.session_state["commune"] = clic
    st.switch_page("vues/commune.py")

# La liste des communes à aller voir, téléchargeable
export = pd.DataFrame({
    "insee": moitie, "commune": t.nom_officiel[moitie].values, "departement": t.dep[moitie].values,
    "sorties_declaration_ha": sorties[moitie].round(0).values,
    f"part_des_prairies_{a0}_pct": (100 * part_sortie[moitie]).round(0).values,
    "priorite": ["prioritaire" if i in fort else "secondaire" for i in moitie]})
st.download_button(f"Télécharger la liste ({nombre(len(export))} communes, CSV)",
                   export.to_csv(sep=";", decimal=",", index=False).encode("utf-8-sig"),
                   "prairimetre_communes_a_aller_voir.csv", "text/csv", icon=":material/download:",
                   key="dl_communes_a_aller_voir")


# --- Vu du satellite ----------------------------------------------------------------------------
st.subheader("Vu du satellite")
PREUVES = "verification/sentinel2/preuves.md"
if mesures is None or mesures.empty:
    st.markdown("La mesure des prairies sorties, commune par commune, n'a pas encore tourné "
                "(`python scripts/analyser_satellite_sentinel.py --sentinel`).")
else:
    VERT_SAT, VERT_CLAIR, ROUGE_SAT = "#2e7d4f", "#a8d5a2", "#c9512f"
    tr = mesures[mesures.etat != "indéterminé"]
    vertes = tr.ha.where(tr.etat == "couvert permanent", 0)
    par = tr.assign(vert=vertes).groupby("insee").agg(n=("ha", "size"), ha_tr=("ha", "sum"),
                                                      ha_vert=("vert", "sum"))
    par["part"] = par.ha_vert / par.ha_tr
    # Une commune est « répondue » si au moins 2 parcelles y sont tranchées
    par["verdict"] = "à préciser"
    par.loc[(par.n >= 2) & (par.part >= 0.95), "verdict"] = "restées vertes"
    par.loc[(par.n >= 2) & (par.part < 0.8), "verdict"] = "labours vus"
    vert_ha = tr.loc[tr.etat == "couvert permanent", "ha"].sum()
    lab_ha = tr.loc[tr.etat == "labourée", "ha"].sum()
    st.markdown(
        f"Chaque prairie sortie d'au moins 1 ha est regardée sur toutes les images Sentinel-2 sans nuage "
        f"de {an} : verte toute l'année, ou passée par le sol nu d'un labour. La règle a été validée sur "
        f"des parcelles dont le registre donne la réponse. Vert ne veut pas forcément dire herbe : une "
        f"friche donne le même signal. Preuves : `{PREUVES}`.")
    s1, s2, s3 = st.columns(3)
    chiffre(s1, "Prairies sorties mesurées", nombre(len(mesures)),
            f"{ha(mesures.ha.sum())} dans {nombre(mesures.insee.nunique())} communes")
    chiffre(s2, "Restées vertes toute l'année", ha(vert_ha),
            f"{nombre(100 * vert_ha / max(vert_ha + lab_ha, 1), 0)} ha sur 100 tranchés")
    chiffre(s3, "Labourées", ha(lab_ha),
            f"{nombre(int((mesures.etat == 'indéterminé').sum()))} parcelles indéterminées (nuages)")

    classes = {"restées vertes": VERT_SAT, "à préciser": VERT_CLAIR, "labours vus": ROUGE_SAT}
    gs = communes_carte().copy()
    gs = gs[gs.insee.isin(set(moitie) | set(mesures.insee))].copy()
    gs["verdict"] = gs.insee.map(par.verdict).fillna("pas encore mesurée")
    gs["couleur"] = [hex_rgb(classes[v]) if v in classes else hex_rgb(HORS, 200) for v in gs.verdict]
    gs["valeur"] = [f"{v} : {nombre(100 * par.part[i], 0)} ha sur 100 restés verts "
                    f"({nombre(par.n[i])} parcelles)" if i in par.index else v
                    for i, v in zip(gs.insee, gs.verdict)]
    pts = mesures.assign(couleur=[hex_rgb({"couvert permanent": VERT_SAT, "labourée": ROUGE_SAT}
                                          .get(e, "#8a897f"), 235) for e in mesures.etat],
                         nom_officiel=mesures.insee.map(t.nom_officiel),
                         valeur=[f"{e}, {ha(h)}" for e, h in zip(mesures.etat, mesures.ha)])
    carte = deck([(gs[["insee", "nom_officiel", "couleur", "valeur", "geometry"]], "sat_communes")], gs,
                 "<b>{nom_officiel}</b><br/>{valeur}")
    carte.layers.append(pdk.Layer("ScatterplotLayer", data=pts[["longitude", "latitude", "couleur",
                                                                "nom_officiel", "valeur"]],
                                  get_position=["longitude", "latitude"], get_fill_color="couleur",
                                  get_radius=180, radius_min_pixels=2.5, pickable=True,
                                  stroked=True, get_line_color=[255, 255, 255], line_width_min_pixels=0.5))
    st.pydeck_chart(carte, width="stretch", key="carte_satellite")
    legende([(VERT_SAT, "prairies sorties restées vertes (95 ha sur 100 ou plus)"),
             (VERT_CLAIR, "à préciser (moins de 2 parcelles, ou entre 80 et 95)"),
             (ROUGE_SAT, "labours vus (moins de 80 ha sur 100 restés verts)"),
             (HORS, "pas encore mesurée")])
    dec = par[par.index.isin(prioritaires)].verdict.value_counts()
    st.markdown(
        f"**Ce que ça change.** Parmi les {nombre(len(prioritaires))} communes prioritaires, le satellite "
        f"voit les prairies sorties restées vertes dans **{nombre(dec.get('restées vertes', 0))}** : elles "
        f"n'entrent pas dans « {payer} », inutile d'y aller pour ça. Il voit des labours dans "
        f"**{nombre(dec.get('labours vus', 0))}** : à aller voir en premier. "
        f"{nombre(len(prioritaires) - dec.get('restées vertes', 0) - dec.get('labours vus', 0))} restent "
        "à préciser ou à mesurer.")
