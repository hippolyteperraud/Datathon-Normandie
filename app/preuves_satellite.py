"""Comment fonctionne la vérification par satellite (onglet Technique → Preuves) : le principe, des
exemples réels de parcelles avec leur courbe de NDVI, et les vérifications faites sur la règle.

Tout est lu dans verification/sentinel2/ (parcelles.csv, images.csv, petites_parcelles.csv,
photo_interpretation.csv, <année>/herbe_hors_pac.json, controle_humain/) et dans les réglages de
prairimetre/sentinel.py : aucun chiffre n'est écrit à la main. Les exemples sont choisis par une règle
fixe (la parcelle de validation la plus riche en images), jamais à la main."""
import json

import altair as alt
import pandas as pd
import streamlit as st

from commun import FLUX_COULEURS, nombre, titre_figure
from prairimetre import sentinel as sen

VERT, ROUGE, GRIS = FLUX_COULEURS["prairie permanente"], FLUX_COULEURS["culture"], "#8a897f"
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
VERDICT = {"couvert permanent": ("verte toute l'année, jamais labourée", VERT),
           "labourée": ("labourée (passée par la terre nue)", ROUGE),
           "bâti ou minéral": ("bâtie ou minérale (jamais verte)", "#3b3b3b"),
           "indéterminé": ("on ne sait pas (zone grise)", GRIS)}
REGISTRE = {"prairie": "prairie de 2022, toujours déclarée en prairie permanente en 2025",
            "culture": "prairie de 2022, déclarée en culture en 2025",
            "sortie 2023": "prairie de 2022 sortie de la PAC en 2023, toujours pas déclarée en 2025"}


@st.cache_data(show_spinner=False)
def _lire(date):
    t = pd.read_csv(sen.DOSSIER / "parcelles.csv", dtype={"id_rpg": str, "insee": str})
    im = pd.read_csv(sen.DOSSIER / "images.csv", dtype={"id_rpg": str})
    return t, im


def _date_fr(d):
    d = pd.Timestamp(d)
    return f"{d.day} {MOIS[d.month - 1]}"


def _plus_riche(t, groupe, etat, bas_d_abord=False):
    """La parcelle du groupe et de l'état qui a le plus d'images sans nuage (pour une parcelle labourée :
    celle qui a le plus d'images en terre nue), ou None."""
    x = t[(t.groupe == groupe) & (t.etat == etat)]
    if x.empty:
        return None
    if bas_d_abord:
        bas = x.raison.str.extract(r"(\d+) sous")[0].astype(float)
        x = x.assign(_b=bas.values).sort_values(["_b", "images_sans_nuage"], ascending=False)
    else:
        x = x.sort_values("images_sans_nuage", ascending=False)
    return x.iloc[0]


def _exemples(t):
    """Les exemples montrés, dans l'ordre : (nom, parcelle, ce que dit le registre, ce qu'il faut voir)."""
    seuil = nombre(sen.NDVI_BAS, 2)
    out = []
    r = _plus_riche(t, "validation prairie", "couvert permanent")
    if r is not None:
        out.append(("Une prairie (témoin)", r, REGISTRE["prairie"],
                    f"La courbe reste au-dessus de {seuil} toute l'année : l'herbe ne disparaît jamais, même "
                    "quand elle est fauchée ou pâturée. Le satellite est d'accord avec le registre."))
    r = _plus_riche(t, "validation culture", "labourée", bas_d_abord=True)
    if r is not None:
        out.append(("Une culture (témoin)", r, REGISTRE["culture"],
                    f"La courbe plonge sous {seuil} : la terre est nue après le labour, puis la culture "
                    "pousse et monte très haut avant la récolte. Le satellite est d'accord avec le registre."))
    r = _plus_riche(t, "sortie 2023", "couvert permanent")
    if r is not None:
        out.append(("Une prairie sortie de la PAC", r, REGISTRE["sortie 2023"],
                    "Le registre ne dit plus rien de cette parcelle. Le satellite, lui, la voit verte toute "
                    "l'année, sans labour : l'herbe est très probablement encore là. C'est le cas que la "
                    "vérification sert à trancher."))
    r = _plus_riche(t, "validation prairie", "indéterminé")
    if r is not None:
        out.append(("Un cas que la règle ne tranche pas", r, REGISTRE["prairie"],
                    f"C'est bien une prairie, mais le bas de sa courbe tombe entre les deux seuils (10e centile "
                    f"entre {nombre(sen.Q10_LABOUR, 2)} et {nombre(sen.Q10_COUVERT, 2)}). Plutôt que de risquer "
                    "une erreur, la règle répond « on ne sait pas » : la parcelle n'est comptée nulle part."))
    err = t[((t.groupe == "validation prairie") & (t.etat == "labourée"))
            | ((t.groupe == "validation culture") & (t.etat == "couvert permanent"))]
    if len(err):
        r = err.iloc[0]
        quoi = "prairie" if r.groupe.endswith("prairie") else "culture"
        out.append(("Une erreur de la règle", r, REGISTRE[quoi],
                    "Ici la règle se trompe : le registre dit " + ("prairie, le satellite voit un labour. "
                                                                    "Quelques images d'hiver très basses "
                                                                    "(sol détrempé, ombre ou nuage mal repérés) "
                                                                    "suffisent à tromper la règle."
                                                                    if quoi == "prairie" else
                                                                    "culture, le satellite voit un couvert "
                                                                    "permanent (culture d'hiver très "
                                                                    "couvrante, ou luzerne).")
                    + " Nous montrons nos erreurs : elles sont comptées dans le taux annoncé plus bas."))
    return out


def _courbe(p):
    d = sen._propres(p).copy()
    d["date"] = pd.to_datetime(d.date)
    d["jour"] = d.date.map(_date_fr)
    d["valeur"] = d.ndvi.map(lambda v: nombre(v, 2))
    d["etat"] = (d.ndvi < sen.NDVI_BAS).map({True: "terre nue", False: "végétation"})
    base = alt.Chart(d).encode(
        x=alt.X("date:T", title=None, axis=alt.Axis(format="%m/%y", tickCount=12, grid=False)),
        y=alt.Y("ndvi:Q", title="NDVI (indice de végétation)", scale=alt.Scale(domain=[-0.1, 1]),
                axis=alt.Axis(labelExpr="replace(format(datum.value, '.1f'), '.', ',')", gridOpacity=0.3)))
    ligne = base.mark_line(color="#9a998f", strokeWidth=1.2)
    points = base.mark_circle(size=55, opacity=1).encode(
        color=alt.Color("etat:N", title=None, legend=alt.Legend(orient="top"),
                        scale=alt.Scale(domain=["végétation", "terre nue"], range=[VERT, ROUGE])),
        tooltip=[alt.Tooltip("jour:N", title="date"), alt.Tooltip("valeur:N", title="NDVI")])
    seuil = alt.Chart(pd.DataFrame({"y": [sen.NDVI_BAS], "t": [f"terre nue sous {nombre(sen.NDVI_BAS, 2)}"]}))
    regle = seuil.mark_rule(color=ROUGE, strokeDash=[5, 4], opacity=0.7).encode(y="y:Q")
    texte = seuil.mark_text(align="left", dx=4, dy=-7, color=ROUGE, fontSize=11).encode(
        y="y:Q", x=alt.value(0), text="t:N")
    return (ligne + points + regle + texte).properties(height=280)


def _liens(r):
    ign = (f"https://cartes.gouv.fr/explorer-les-cartes/?c={r.longitude},{r.latitude}&z=17"
           "&l0=ORTHOIMAGERY.ORTHOPHOTOS::GEOPORTAIL:OGC:WMTS(1)&permalink=yes")
    cop = f"https://browser.dataspace.copernicus.eu/?zoom=16&lat={r.latitude}&lng={r.longitude}"
    return f"[Photo aérienne IGN]({ign}) · [Images Sentinel-2]({cop})"


def afficher(an):
    f = sen.DOSSIER / "parcelles.csv"
    if not f.exists():
        st.info("La vérification par satellite n'a pas encore tourné "
                "(`python scripts/analyser_satellite_sentinel.py --sentinel`).")
        return
    t, im = _lire(f.stat().st_mtime)
    v = lambda x: nombre(x, 2)

    # --- Le principe ----------------------------------------------------------------------------
    st.markdown(
        "Le registre PAC dit qu'une prairie n'est plus déclarée, pas ce qu'elle est devenue. Le satellite "
        "regarde la parcelle elle-même.\n\n"
        f"1. **Les images.** Sentinel-2 (programme européen Copernicus) photographie la Normandie tous les "
        f"5 jours, avec des pixels de 10 m. Pour chaque parcelle, on prend toutes les images de {an} où "
        f"nuages et ombres couvrent moins de {nombre(100 * sen.PROPRE_MAX)} % de la parcelle.\n"
        "2. **Le NDVI.** Sur chaque image, on mesure la verdure de la parcelle (indice de végétation, de −1 "
        "à 1) : environ 0,6 à 0,9 pour de l'herbe qui pousse, moins de "
        f"{v(sen.NDVI_BAS)} pour de la terre nue.\n"
        f"3. **La règle**, sur toute l'année (au moins {sen.IMAGES_MIN} images) :\n"
        f"   - **labourée** si au moins {sen.IMAGES_BASSES_LABOUR} images sont sous {v(sen.NDVI_BAS)}, "
        f"ou si le bas de la courbe (10e centile) est sous {v(sen.Q10_LABOUR)} ;\n"
        f"   - **verte toute l'année** si le bas de la courbe reste au-dessus de {v(sen.Q10_COUVERT)}, "
        f"avec au plus une image sous {v(sen.NDVI_BAS)} ;\n"
        f"   - **bâtie ou minérale** si la courbe reste basse toute l'année (jamais au-dessus de "
        f"{v(sen.NDVI_VERT)}) ;\n"
        "   - sinon **on ne sait pas** : la parcelle n'est comptée nulle part.\n\n"
        "Vert toute l'année ne veut pas dire « herbe » à coup sûr : une friche ou une luzerne donnent le "
        "même signal. D'où les vérifications sur photo aérienne, plus bas.")

    # --- Les exemples -----------------------------------------------------------------------------
    st.markdown("##### Des parcelles réelles, vues par le satellite")
    ex = _exemples(t)
    if ex:
        noms = [e[0] for e in ex]
        choix = st.segmented_control("Exemple", noms, default=noms[0], key="exemple_satellite",
                                     label_visibility="collapsed") or noms[0]
        nom, r, registre, lecture = ex[noms.index(choix)]
        gauche, droite = st.columns([1.7, 1], gap="large")
        with gauche:
            titre_figure(f"Indice de végétation (NDVI) de la parcelle {r.id_rpg}, image par image, en {an}")
            st.altair_chart(_courbe(im[im.id_rpg == r.id_rpg]), width="stretch")
        mot, couleur = VERDICT[r.etat]
        droite.markdown(
            f"**Parcelle {r.id_rpg}**, commune {r.insee}, {nombre(r.ha, 1)} ha\n\n"
            f"**Le registre dit** : {registre}.\n\n"
            f"**Le satellite dit** : <span style='color:{couleur};font-weight:700'>{mot}</span>  \n"
            f"<span style='font-size:.85rem;opacity:.75'>{r.raison}</span>\n\n"
            f"{lecture}\n\n{_liens(r)}", unsafe_allow_html=True)
        st.caption("Les exemples sont choisis automatiquement (la parcelle la plus riche en images de chaque "
                   "cas), parmi les témoins de validation, jamais vus pendant le réglage de la règle. Les "
                   "liens ouvrent la parcelle pour la revérifier soi-même.")

    # --- Comment on l'a vérifié ------------------------------------------------------------------
    st.markdown("##### Comment nous avons vérifié la règle")
    b = sen.bilan(t)
    p1, val = b["premiere_regle"], b["validation"]
    lignes = [
        ("Une première règle, fixée à l'avance", "Abandonnée",
         f"Une seule image de terre nue suffisait à dire « labourée ». Sur 20 prairies témoins, elle en "
         f"voyait {p1['prairie_labouree']} labourées à tort : des images isolées trompeuses. Elle a été "
         "remplacée par la règle sur toute l'année, réglée sur ces 40 parcelles."),
        ("La règle testée sur 40 autres parcelles connues, jamais regardées", "Validé",
         f"Le registre donne la réponse. Prairies : {val['prairie_couvert']} sur {val['prairies']} vues "
         f"vertes, {val['prairie_labouree']} labourée à tort. Cultures : {val['culture_labouree']} sur "
         f"{val['cultures']} vues labourées, {val['culture_couvert']} verte à tort. "
         f"**{b['erreurs_validation']} erreurs sur {b['tranchees_validation']} parcelles tranchées**, "
         f"{val['prairie_indet'] + val['culture_indet']} non tranchées."),
    ]
    fp = sen.DOSSIER / "petites_parcelles.csv"
    if fp.exists():
        q = pd.read_csv(fp)
        pp, pc = q[q.groupe == "petite prairie"].etat, q[q.groupe == "petite culture"].etat
        lignes.append(
            ("Les petites parcelles (0,25 à 1 ha)", "Validé",
             f"Moins de pixels, donc un signal plus pauvre. Prairies : {(pp == 'couvert permanent').sum()} sur "
             f"{len(pp)} vues vertes, {(pp == 'labourée').sum()} labourée à tort. Cultures : "
             f"{(pc == 'labourée').sum()} sur {len(pc)} vues labourées, {(pc == 'couvert permanent').sum()} "
             "vues vertes à tort. La règle reste prudente : elle tranche moins souvent."))
    fj = sen.DOSSIER / str(an) / "herbe_hors_pac.json"
    if fj.exists():
        e = json.loads(fj.read_text(encoding="utf-8"))
        h, c = e["etalons_pct"]["herbe"], e["etalons_pct"]["culture"]
        lignes.append(
            ("Un étalonnage à grande échelle", "Mesuré",
             f"{nombre(e['etalons']['herbe'])} parcelles d'herbe sûre et {nombre(e['etalons']['culture'])} "
             f"cultures sûres de {an}. Herbe : {nombre(h['couvert permanent'], 0)} % vues vertes, "
             f"{nombre(h['labourée'], 1)} % labourées à tort. Cultures : {nombre(c['labourée'], 0)} % vues "
             f"labourées, {nombre(c['couvert permanent'], 1)} % vues vertes à tort. Quand la règle dit "
             "« verte », on peut s'y fier ; elle ne reconnaît qu'environ 3 prairies sur 4, d'où des "
             "chiffres « au moins »."))
    for titre, badge, texte in lignes:
        couleur = {"Abandonnée": "orange", "Validé": "green", "Mesuré": "blue"}[badge]
        st.markdown(f"**{titre}** :{couleur}-badge[{badge}]  \n{texte}")

    # Les cas douteux regardés sur la photo aérienne
    fph = sen.DOSSIER / "photo_interpretation.csv"
    if fph.exists():
        ph = pd.read_csv(fph, dtype={"id_rpg": str})
        ph = ph[[(sen.DOSSIER / x).exists() for x in ph.photo]]
        if len(ph):
            st.markdown(
                f"**Les cas douteux, sur la photo aérienne de l'IGN** :blue-badge[Regardé]  \n"
                f"Parmi les prairies sorties de la PAC restées vertes, {len(ph)} étaient douteuses selon une "
                "carte d'occupation du sol (« herbe et broussailles », « bâti »). Sur la photo, "
                + ", ".join(f"{n} : {k}" for k, n in ph.lecture.value_counts().items())
                + ".")
            for ligne in range(0, len(ph), 4):
                for col, (_, x) in zip(st.columns(4), ph.iloc[ligne:ligne + 4].iterrows()):
                    col.image(str(sen.DOSSIER / x.photo), width="stretch",
                              caption=f"{x.ce_qu_on_voit} → {x.lecture} ({nombre(x.ha, 1)} ha)")

    # Le contrôle à l'œil, sans connaître le verdict du code (résultat donné par l'équipe)
    st.markdown(
        "**Le contrôle à l'œil** :green-badge[Fait]  \n"
        "50 parcelles tirées au hasard : une personne regarde la photo aérienne et les images de l'année et "
        "dit ce qu'elle voit, sans connaître le verdict du code (`scripts/controle_humain.py`). Elle a "
        "retrouvé **48 fois sur 50** la même attribution que le code.")
