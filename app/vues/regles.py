"""2. Recommandations, en « constat → donc ». À gauche, cinq initiatives : la question et son verdict,
UN chiffre déjà traduit (« 7× moins », « autant », « 1 pour 4 ») avec sa phrase, puis la recommandation
qu'il appuie. À droite, une idée nouvelle testée sur nos données : protéger les jeunes prairies. Le
détail des mesures (hectares sur 100, périodes, textes) est dans les bulles d'aide.
Tout est lu dans sorties/ (evaluation_terrain, evaluation_zonages, evaluation_robustesse,
evaluation_bcae2, evaluation_jeunes, serie_region, communes) et dans app/references.py. Tient sur un
écran sans dérouler (vérifié en 1440×900 et 1366×768)."""
import streamlit as st

from commun import (FLUX_COULEURS, GAIN_MINIMUM_HA, HORS, bornes, communes_carte, communes_exemples,
                    comparaison, deck, evaluation, exiger_sorties, ha, hex_rgb, nombre, selection_carte,
                    table, titre_figure)
from prairimetre.config import RECENT
from references import RATIOS

exiger_sorties()
a0, an = bornes()
terrain = evaluation("terrain")
zon = evaluation("zonages", index_col=0)
bcae2 = evaluation("bcae2")
jeunes = evaluation("jeunes")
if terrain is None or zon is None or "sur_100_dedans" not in terrain:
    st.info("Résultats manquants : lancez « Relancer les calculs » dans Technique.")
    st.stop()

VERT, ROUGE = FLUX_COULEURS["prairie permanente"], FLUX_COULEURS["culture"]
ORANGE, GRIS_T = "#e0a02a", "#9a998f"
N_COMMUNES = 211  # les communes où l'on retourne le plus (la moitié du retournement récent)
# verdict -> (badge, couleur du badge, couleur du grand chiffre)
VERDICTS = {"oui": ("Oui", "green", "#3fb07a"), "un": ("Oui, sur 1 an", "green", "#3fb07a"),
            "non": ("Non", "red", ROUGE), "tot": ("Trop tôt", "gray", GRIS_T),
            "lent": ("Trop lent", "orange", ORANGE)}
COLS = [0.7, 1.32, 0.1, 1.28]

st.html("""<style>
.rc-c {display:flex; align-items:center; gap:12px}
.rc-big {font-size:1.75rem; font-weight:800; line-height:1; white-space:nowrap; min-width:7.2rem; flex:0 0 auto}
.rc-c.rc-v {flex-direction:column; align-items:flex-start; gap:4px}
.rc-v .rc-big {min-width:0}
.rc-p {font-size:0.86rem; line-height:1.25; opacity:0.9}
.rc-q {font-size:1rem; font-weight:700; line-height:1.25}
.rc-r {font-size:0.97rem; font-weight:700; line-height:1.25}
.rc-k {font-size:0.84rem; opacity:0.75; line-height:1.25}
.rc-f {font-size:1.6rem; opacity:0.45; text-align:center}
.rc-h {font-size:0.72rem; text-transform:uppercase; letter-spacing:0.06em; opacity:0.55; font-weight:600}
.rc-idee {font-size:1.25rem; font-weight:800; line-height:1.2; margin:0.15rem 0 0.3rem}
/* les cadres des lignes (clé « rcl_… ») : marges et espaces resserrés */
[class*="st-key-rcl_"] {padding: 0.45rem 0.95rem !important;}
[class*="st-key-rcl_"] [data-testid="stVerticalBlock"] {gap: 0.35rem;}
[class*="st-key-rcl_"] p {margin-bottom: 0.1rem;}
[class*="st-key-rcl_"] button {min-height: 1.6rem; padding-top: 0; padding-bottom: 0;}
/* Les cinq lignes se partagent la hauteur libre de l'écran (menu, en-têtes et marges ôtés) : plus
   aérées sur un grand écran, jamais plus hautes que ce qui tient sans dérouler */
[class*="st-key-rcl_"] {min-height: calc((100vh - 220px) / 5); justify-content: center;}
/* Le cadre de l'idée commence au niveau de la première ligne, pas des en-têtes */
.st-key-idee {margin-top: 41px;}
.st-key-idee {background: rgba(42,140,90,0.10); border: 1px solid rgba(42,140,90,0.55) !important;
              border-radius: 0.6rem; padding: 0.65rem 1rem !important;}
.st-key-idee [data-testid="stVerticalBlock"] {gap: 0.3rem;}
/* Les deux encadrés de droite (l'idée, l'eau) tiennent ensemble à côté des cinq lignes : texte serré */
.st-key-idee p, .st-key-eau p {line-height: 1.3;}
/* la colonne ne les écrase pas : le cadre suit toujours son texte */
.st-key-idee, .st-key-eau {flex-shrink: 0;}
.st-key-idee .rc-big, .st-key-eau .rc-big {font-size: 1.45rem;}
.st-key-idee .rc-idee, .st-key-eau .rc-idee {font-size: 1.1rem; margin: 0 0 0.1rem;}
.st-key-idee .rc-p, .st-key-eau .rc-p {font-size: 0.82rem;}
/* L'encadré de l'eau : le même, en bleu, juste sous l'idée nouvelle */
.st-key-eau {background: rgba(42,120,214,0.10); border: 1px solid rgba(42,120,214,0.55) !important;
             border-radius: 0.6rem; padding: 0.65rem 1rem !important; margin-top: 0.2rem;}
.st-key-eau [data-testid="stVerticalBlock"] {gap: 0.3rem;}
.st-key-eau button {min-height: 1.6rem; padding-top: 0; padding-bottom: 0;}
.rc-non {color:#c2452d; font-weight:700; font-size:0.84rem; line-height:1.25}
@media (prefers-color-scheme: dark) {.rc-non {color:#ff8a73}}
[data-testid="stMainBlockContainer"] {padding-top: 3.6rem !important; padding-bottom: 0.3rem !important;}
[data-testid="stMainBlockContainer"] > div > [data-testid="stVerticalBlock"] {gap: 0.4rem;}
</style>""")


def constat(gros, phrase, couleur, aide=None, vertical=False):
    """Le chiffre déjà traduit, et sa phrase juste à côté ; le détail est dans la bulle d'aide."""
    st.markdown(f"<div class='rc-c{' rc-v' if vertical else ''}'><span class='rc-big' style='color:{couleur}'>{gros}</span>"
                f"<span class='rc-p'>{phrase}</span></div>", unsafe_allow_html=True, help=aide)


def ligne(question, verdict, gros, phrase, aide, reco, chiffre="", bouton=None, aide_reco=None):
    """Une initiative : question et verdict | constat | → | recommandation."""
    nom, badge, couleur = VERDICTS[verdict]
    with st.container(border=True, key=f"rcl_{abs(hash(question))}"):
        c1, c2, c3, c4 = st.columns(COLS, gap="small", vertical_alignment="center")
        c1.markdown(f"<span class='rc-q'>{question}</span>  \n:{badge}-badge[{nom}]", unsafe_allow_html=True)
        with c2:
            constat(gros, phrase, couleur, aide)
        c3.html("<div class='rc-f'>→</div>")
        with c4:
            st.markdown(f"<span class='rc-r'>{reco}</span>"
                        + (f"  \n<span class='rc-k'>{chiffre}</span>" if chiffre else ""), unsafe_allow_html=True)
            if bouton:
                bouton()


def fois(x):
    return f"{nombre(x, 0)}×"


NOTE = (f"Tout est mesuré sur le registre PAC {a0} → {an}. Les comparaisons montrent ce qui va avec moins de "
        "retournement, pas une preuve de cause. Les recommandations ne sont pas testées sur le terrain. Le "
        "détail de chaque chiffre est dans sa bulle ; les calculs dans Technique → Preuves.")
gauche, droite = st.columns([2.3, 1.05], gap="medium")

tc = table("communes")
calc = tc[tc.statut == "calculé"]
top = calc.loc[calc.retourne_recent.nlargest(N_COMMUNES).index]

r0 = an - RECENT
gain, _ = communes_exemples(tc)


def carte_communes(couleur, info, legende, aide, cle, titre):
    """Carte des communes en grand (dans une fenêtre) : couleur et info par code INSEE, les autres en
    gris ; un clic sur une commune ouvre sa fiche."""
    g = communes_carte().copy()
    g["couleur"] = [hex_rgb(couleur[k]) if k in couleur else hex_rgb(HORS, 55) for k in g.insee]
    g["valeur"] = g.insee.map(lambda k: info.get(k, ""))
    titre_figure(titre, aide=aide + " Un clic sur une commune ouvre sa fiche.")
    evt = st.pydeck_chart(deck([(g[["insee", "nom_officiel", "couleur", "valeur", "geometry"]], cle)], g,
                               "<b>{nom_officiel}</b><br/>{valeur}", hauteur=560, zoom=7.1),
                          on_select="rerun", selection_mode="single-object", width="stretch", height=560, key=cle)
    # La légende sous la carte
    st.markdown("<div style='font-size:.9rem;margin-top:-.4rem'>" + legende
                + f' &nbsp; <span style="color:{HORS}">■</span> les autres</div>', unsafe_allow_html=True)
    clic = selection_carte(evt, cle, "insee")
    if clic and clic != st.session_state.get(f"_clic_{cle}"):  # un clic ne compte qu'une fois
        st.session_state[f"_clic_{cle}"] = clic
        st.session_state["commune"] = clic
        st.switch_page("vues/commune.py")


@st.dialog(f"Les {N_COMMUNES} communes où l'on retourne le plus", width="large")
def carte_211():
    part = top.retourne_recent.sum() / tc.retourne_recent.sum()
    carte_communes({k: ROUGE for k in top.index},
                   {k: f"{ha(v)} retournés de {r0} à {an}" for k, v in top.retourne_recent.items()},
                   f'<span style="color:{ROUGE}">■</span> {nombre(N_COMMUNES)} communes : '
                   f'{nombre(100 * part, 0)} ha sur 100 du retournement de {r0} à {an}',
                   f"Les communes classées par hectares de prairies retournés en culture de {r0} à {an} ; "
                   f"les {nombre(N_COMMUNES)} premières font la moitié du retournement.", "carte_211",
                   f"Les communes où l'on a retourné le plus de prairies en culture, {r0}→{an}")


@st.dialog("Les communes qui recréent de l'herbe", width="large")
def carte_exemples():
    # Seules les communes qui recréent de l'herbe : celles qui « ne perdent rien » ont peu de prairies
    # (médiane 34 ha contre 162 ha) et ne répondent pas à la question « recréer de l'herbe ».
    carte_communes({k: VERT for k in gain.index},
                   {k: f"{ha(v, signe=True)} de prairies sur d'anciennes cultures depuis {a0}" for k, v in gain.items()},
                   f'<span style="color:{VERT}">■</span> {nombre(len(gain))} communes gagnent au moins '
                   f'{GAIN_MINIMUM_HA} ha de prairie sur d\'anciennes cultures ({ha(gain.sum())} en tout)',
                   f"Depuis {a0}, gain net de ce qui a été perdu. Les nouvelles déclarations et les prairies "
                   "temporaires devenues permanentes ne comptent pas comme un gain.", "carte_exemples",
                   f"Les communes qui ont gagné des prairies sur d'anciennes cultures depuis {a0}")


def bouton(texte, ouvrir):
    return lambda: st.button(texte, icon=":material/map:", type="tertiary", key=f"b_{ouvrir.__name__}") and ouvrir()


with gauche:
    for col, txt in zip(st.columns(COLS, gap="small"),
                        ("Ce qu'on a testé", "Ce qu'on a trouvé", "", "Donc, on recommande")):
        if txt:
            col.markdown(f"<span class='rc-h' style='padding-left:0.95rem'>{txt}</span>",
                         unsafe_allow_html=True, help=NOTE if txt == "Ce qu'on a testé" else None)

    # 1. L'interdiction de retourner (prairies sensibles, BCAE 9), à terrain égal
    t = terrain.set_index("comparaison")
    i = t[t.index.str.contains("Natura")].iloc[0]
    evite = top.retourne.sum() * (1 - i.sur_100_dedans / i.sur_100_a_cote)
    ligne("Interdire de retourner ?", "oui",
          f"{fois(i.sur_100_a_cote / i.sur_100_dedans)} moins",
          "de prairies retournées là où c'est interdit, qu'à côté sur le même terrain",
          f"Sur 100 ha de prairie, {nombre(i.sur_100_dedans, 1)} ha retournés de {a0} à {an} là où c'est "
          f"interdit (prairies sensibles, BCAE 9), contre {nombre(i.sur_100_a_cote, 1)} ha pour les autres "
          "prairies des mêmes sites Natura 2000, dans les mêmes communes : même terrain, seule la règle change. "
          f"L'interdiction couvre {nombre(100 * zon.loc['prairies_sensibles', 'part_des_prairies'], 0)} ha "
          "de prairie sur 100.",
          f"L'étendre aux {N_COMMUNES} communes qui retournent le plus",
          f"environ {ha(round(evite, -3))} gardés en herbe depuis {a0}",
          bouton(f"Voir les {nombre(N_COMMUNES)} communes", carte_211),
          aide_reco=f"Ces {nombre(N_COMMUNES)} communes ont retourné {ha(top.retourne.sum())} de prairies de {a0} "
                    f"à {an}. Là où c'est interdit, on retourne {nombre(i.sur_100_dedans, 1)} ha sur 100 au lieu de "
                    f"{nombre(i.sur_100_a_cote, 1)} : avec le même effet, il en serait resté environ "
                    f"{ha(round(evite, -3))} en herbe. Un ordre de grandeur, pas une mesure.")

    # 2. L'autorisation préalable dans toute la région (ratio régional)
    s = table("serie_region").set_index("periode")
    s["v"] = 100 * s.sortie_culture / s.depart
    per = list(s.index)
    textes = {f"{r['annee']}-{r['annee'] + 1}": r["texte"] for r in RATIOS
              if r["consequence"] != "aucune obligation"}
    stricte = [p for p in per if p in textes]
    if stricte:
        p = stricte[0]
        autres = s.drop(index=stricte).v
        suiv = per[per.index(p) + 1] if per.index(p) + 1 < len(per) else None
        ligne("Autorisation régionale ?", "un",
              f"{fois(autres.mean() / s.loc[p, 'v'])} moins",
              f"de retournement l'année où il fallait une autorisation ({p[:4]}-{p[7:]})",
              f"Sur 100 ha de prairie, {nombre(s.loc[p, 'v'], 1)} ha retournés en {p[:4]}-{p[7:]}, sous "
              f"autorisation ({textes[p]}), contre {nombre(autres.min(), 1)} à {nombre(autres.max(), 1)} ha "
              "les autres années. Une seule année pleine : d'autres causes ont pu jouer.",
              "Ne pas la lever trop vite",
              (f"l'année de la levée : {ha(s.loc[p, 'sortie_culture'])} → {ha(s.loc[suiv, 'sortie_culture'])} "
               "retournés" if suiv else ""))

    # 3. Un zonage sans obligation : les captages d'eau potable
    sens, _ = comparaison("aires_alimentation_captages")
    if "aires_alimentation_captages" in zon.index and sens:
        c = zon.loc["aires_alimentation_captages"]
        ligne("Zone de captage d'eau, sans règle ?", "non" if sens in ("autant", "plus") else "oui",
              sens.capitalize(),
              "de retournement qu'à côté : être classé ne suffit pas à garder l'herbe",
              f"Aires d'alimentation des captages d'eau potable, classées mais sans obligation de garder "
              f"l'herbe. Sur 100 ha de prairie, {nombre(c.sur_100_dedans, 1)} ha retournés de {a0} à {an} "
              f"au-dessus des captages, contre {nombre(c.sur_100_a_cote, 1)} ha à côté, dans les mêmes "
              f"communes ; {sens} qu'à côté sur toutes les périodes testées.",
              "Y mettre une condition d'herbe",
              f"{ha(c.retourne_ha)} retournés au-dessus des captages depuis {a0}")

    # 4. La BCAE 2 (zones humides et tourbières), en vigueur depuis le 1er janvier 2025
    if bcae2 is not None and bcae2.regle_en_vigueur.any() and "bcae_zones_humides_tourbieres" in zon.index:
        av = bcae2[~bcae2.regle_en_vigueur]
        d, h = 100 * av.taux_dedans.mean(), 100 * av.taux_dehors.mean()
        debut = bcae2[bcae2.regle_en_vigueur].periode.iloc[0][-4:]
        ligne(f"Zones humides ({debut}) ?", "tot",
              f"{fois(h / d)} moins",
              "de retournement qu'ailleurs, déjà avant la règle",
              f"BCAE 2 : au plus un labour en 4 ans dans les zones humides et tourbières, depuis {debut}. "
              f"Avant la règle, {nombre(d, 2)} ha retournés sur 100 ha par an dans ces zones, contre "
              f"{nombre(h, 1)} ha ailleurs. Une seule campagne sous la règle : trop tôt pour mesurer.",
              "Ne pas compter dessus pour 2030",
              f"elle couvre {nombre(100 * zon.loc['bcae_zones_humides_tourbieres', 'part_des_prairies'], 0)} "
              "ha de prairie sur 100")

    # 5. Recréer de l'herbe sur des cultures, et les communes qui le font
    regagne, retourne = tc.venues_culture.sum(), tc.devenues_culture.sum()
    n = retourne / regagne
    ligne("Recréer de l'herbe ?", "lent",
          f"1 pour {nombre(n, 0)}",
          f"1 ha d'herbe recréé sur des cultures pour {nombre(n, 0)} ha retournés depuis {a0}",
          f"De {a0} à {an} : {ha(regagne)} de cultures devenues prairies permanentes, contre {ha(retourne)} "
          "de prairies devenues cultures.",
          f"En recréer {nombre(n, 0)} fois plus", "",
          bouton(f"Voir les {nombre(len(gain))} communes qui y arrivent", carte_exemples))

# --- La nouvelle idée, testée sur nos données : protéger les jeunes prairies -----------------------
with droite, st.container(key="idee"):
    st.html("<div class='rc-h'>Une idée nouvelle, testée sur nos données</div>"
            "<div class='rc-idee'>Protéger les jeunes prairies</div>")
    if jeunes is None:
        st.info("Test pas encore calculé : lancez « Relancer les calculs » dans Technique.")
    else:
        j = jeunes[jeunes.coupure == jeunes.coupure.max()].set_index("origine")
        a, c_, f_ = int(j.annee_origine.iloc[0]), int(j.coupure.iloc[0]), int(j.fin.iloc[0])
        vieilles = j.loc["prairie permanente", "sur_100"]
        jeune = j.loc[["prairie temporaire", "culture"]]
        # les deux chiffres côte à côte : l'encadré de l'eau tient en dessous, sans dérouler
        k1, k2 = st.columns(2, gap="small")
        with k1:
            constat(f"{fois(jeune.retourne.sum() / jeune.ha.sum() * 100 / vieilles)} plus",
                    "de retournement pour une jeune prairie permanente", ROUGE,
                    f"Prairies permanentes de {c_}, rangées selon ce qu'elles étaient en {a} ; retournées de {c_} à "
                    f"{f_}, sur 100 ha : {nombre(vieilles, 1)} ha si elles étaient déjà prairies permanentes, "
                    f"{nombre(j.loc['prairie temporaire', 'sur_100'], 1)} ha si elles étaient prairies temporaires, "
                    f"{nombre(j.loc['culture', 'sur_100'], 1)} ha si elles étaient cultures. Une prairie temporaire "
                    "devient permanente après 5 ans d'herbe.", vertical=True)
        with k2:
            constat(f"{nombre(100 * jeune.part_du_retournement.sum(), 0)} sur 100",
                    f"des hectares retournés, alors qu'elles font "
                    f"{nombre(100 * jeune.part_des_prairies.sum(), 0)} sur 100 des prairies", ROUGE, vertical=True)
        autres = jeunes[jeunes.coupure != c_]
        if len(autres):
            r = autres.set_index("origine")
            st.markdown(":green-badge[Même résultat sur 2 périodes]",
                        help=f"Avec {int(r.coupure.iloc[0])} → {f_} : déjà prairie "
                             f"{nombre(r.loc['prairie permanente', 'sur_100'], 1)} ha, prairie temporaire "
                             f"{nombre(r.loc['prairie temporaire', 'sur_100'], 1)} ha, culture "
                             f"{nombre(r.loc['culture', 'sur_100'], 1)} ha retournés sur 100.")
        st.html("<div class='rc-h'>Donc, on recommande</div>")
        st.markdown(f"<span class='rc-r'>Un contrat dès qu'une prairie devient permanente</span>  \n"
                    f"<span class='rc-k'>{ha(jeune.ha.sum())} à suivre, repérables chaque année dans le "
                    "registre PAC</span>", unsafe_allow_html=True)


# --- L'eau : plus de nitrates dans les rivières, moins de prairies, sans lien prouvé ---------------
with droite, st.container(key="eau"):
    from eau_details import nitrates
    nit = nitrates()
    st.html("<div class='rc-h'>L'eau et l'herbe, sur la même décennie</div>"
            "<div class='rc-idee'>Plus de nitrates, moins de prairies</div>")
    if nit is None:
        st.info("Mesures de nitrates absentes : lancer `python scripts/recuperer_hubeau.py`.")
    else:
        t, debut, fin, rob, dep = nit
        hausse, baisse = int((t.sens == "en hausse").sum()), int((t.sens == "en baisse").sum())
        p_avant, p_apres = f"{debut[0]}-{debut[-1]}", f"{fin[0]}-{fin[-1]}"
        pire = rob.hasard.max() if len(rob) else 1.0
        pp0, pp1 = tc[f"pp_{a0}"].sum(), tc[f"pp_{an}"].sum()
        k1, k2 = st.columns(2, gap="small")
        with k1:
            constat(f"+{nombre(t.variation.median(), 1)} mg/L",
                    f"de nitrates dans les rivières, de {p_avant} à {p_apres}", ROUGE,
                    f"Médiane des variations, station par station : {hausse} stations en hausse, {baisse} en "
                    f"baisse, sur les {len(t)} mesurées dans les deux périodes (Hub'Eau). Point de départ : "
                    f"{nombre(t.avant.median(), 0)} mg/L pour la station du milieu.", vertical=True)
        with k2:
            constat(f"−{nombre(100 * (1 - pp1 / pp0), 0)} sur 100",
                    f"de prairies permanentes de {a0} à {an}", ROUGE,
                    f"{ha(pp0)} de prairies permanentes déclarées à la PAC en {a0}, {ha(pp1)} en {an} : "
                    f"{ha(pp1 - pp0, signe=True)}.", vertical=True)
        if len(rob):
            st.markdown(f":blue-badge[{hausse} stations en hausse, {baisse} en baisse]",
                        help="Le résultat ne tient pas au choix des années : "
                             + " ; ".join(f"{r.avant} → {r.apres} : {r.en_hausse} en hausse, {r.en_baisse} en "
                                          f"baisse" for r in rob.itertuples())
                             + ". Autant de hausses par hasard : moins d'une chance sur "
                             f"{nombre(10 ** int(-__import__('math').log10(pire)))} (test du signe).")
        st.markdown("<div class='rc-non'>✕ Les deux vont ensemble, mais le lien n'est pas prouvé</div>",
                    unsafe_allow_html=True,
                    help="Une prairie retient une partie des nitrates, mais ceux des rivières dépendent aussi des "
                         "pluies, des engrais, de l'élevage et de l'assainissement. Rien ici ne montre que la "
                         "perte d'herbe a fait monter les nitrates. Les stations mesurent les rivières, pas l'eau "
                         "du robinet.")
