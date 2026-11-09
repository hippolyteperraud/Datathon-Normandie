"""Touches humaines : illustration du bocage, pourquoi les prairies comptent."""
import streamlit as st


def _haie(x0, x1, y, pas=18, r=9):
    """Rangée d'arbres ronds le long d'une ligne de champ."""
    return "".join(
        f'<circle cx="{x}" cy="{y - (i % 3) * 1.5}" r="{r + (i % 2) * 2}" fill="#2f5d3a"/>'
        for i, x in enumerate(range(x0, x1, pas)))


def _vache(x, y, s=1.0):
    """Vache normande stylisée : robe blanche, taches et « lunettes » brunes."""
    return (f'<g transform="translate({x},{y}) scale({s})">'
            '<rect x="0" y="0" width="30" height="15" rx="6" fill="#fdfbf6"/>'
            '<circle cx="9" cy="6" r="4" fill="#7a4a2a"/><circle cx="21" cy="9" r="3" fill="#7a4a2a"/>'
            '<rect x="27" y="-5" width="10" height="10" rx="4" fill="#fdfbf6"/>'
            '<circle cx="33" cy="-1" r="2" fill="#7a4a2a"/>'
            '<path d="M4 15 V22 M10 15 V22 M21 15 V22 M26 15 V22" stroke="#5a4a3a" stroke-width="2"/>'
            '</g>')


def bandeau(titre, sous_titre):
    """Illustration de bocage normand en tête de page (SVG, sans ressource externe)."""
    svg = f"""
<svg viewBox="0 0 1200 230" width="100%" style="display:block"
     role="img" aria-label="Paysage de bocage normand : prairies, haies et vaches">
  <defs><linearGradient id="ciel" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#e4efe6"/><stop offset="1" stop-color="#f7f3e6"/></linearGradient></defs>
  <rect width="1200" height="230" fill="url(#ciel)"/>
  <circle cx="1060" cy="58" r="30" fill="#f2dc9b" opacity="0.85"/>
  <path d="M0 140 C 200 105, 420 132, 620 112 S 1000 92, 1200 120 V230 H0Z" fill="#bcd8b2"/>
  <g transform="translate(905,82)"><rect x="0" y="14" width="22" height="22" fill="#d8d2c4"/>
    <path d="M-2 14 L11 -12 L24 14Z" fill="#8c8578"/><rect x="8" y="24" width="6" height="12" fill="#8c8578"/></g>
  {_haie(40, 520, 128, 20, 7)}{_haie(700, 1180, 112, 20, 7)}
  <path d="M0 172 C 260 140, 520 186, 780 160 S 1060 150, 1200 168 V230 H0Z" fill="#94c18a"/>
  {_haie(0, 380, 160, 22, 10)}{_haie(820, 1200, 160, 22, 10)}
  <path d="M520 164 C 560 190, 600 205, 640 230" stroke="#2f5d3a" stroke-width="9" fill="none"
        stroke-linecap="round" stroke-dasharray="1 15"/>
  <path d="M0 202 C 320 178, 680 214, 1200 192 V230 H0Z" fill="#6fa86c"/>
  <g><rect x="1110" y="140" width="8" height="40" fill="#5b4632"/>
     <circle cx="1114" cy="128" r="30" fill="#2f5d3a"/><circle cx="1092" cy="142" r="20" fill="#3d7347"/></g>
  {_vache(820, 196, 1.1)}{_vache(905, 205, 0.95)}{_vache(1000, 192, 1.05)}
  <text x="40" y="74" font-family="system-ui, -apple-system, 'Segoe UI', sans-serif"
        font-size="44" font-weight="800" fill="#1f3b2a">{titre}</text>
  <text x="42" y="108" font-family="system-ui, -apple-system, 'Segoe UI', sans-serif"
        font-size="19" fill="#2f4a38">{sous_titre}</text>
</svg>"""
    st.markdown(f'<div style="border-radius:14px;overflow:hidden;margin-bottom:0.6rem">{svg}</div>',
                unsafe_allow_html=True)


RAISONS = [
    ("L'eau",
     "Une prairie ne se laboure pas : elle retient nitrates et pesticides avant qu'ils "
     "n'atteignent les captages."),
    ("Le vivant",
     "Fleurs, insectes pollinisateurs, oiseaux du bocage : une prairie ancienne abrite bien plus "
     "d'espèces qu'une culture."),
    ("Le climat",
     "Le sol d'une prairie stocke du carbone ; le retourner en relâche une partie."),
    ("L'élevage et le paysage",
     "L'herbe nourrit les vaches normandes, le camembert et le bocage qui fait la Normandie."),
]


def pourquoi():
    """Pourquoi les prairies comptent, en quatre phrases."""
    for col, (titre, texte) in zip(st.columns(4), RAISONS):
        col.markdown(f"**{titre}**  \n{texte}")
