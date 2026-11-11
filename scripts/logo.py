"""Fabrique le logo du bandeau (app/assets/logo_prairimetre.png) et l'icône de l'onglet du navigateur
(app/assets/icone_prairimetre.png) à partir de « Prairimètre, logo prairie moderne.png » : le dessin
recadré au plus près, posé sur un fond blanc arrondi (lisible en thème clair comme sombre).

    python scripts/logo.py
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parents[1] / "app" / "assets"
brut = Image.open(ASSETS / "Prairimètre, logo prairie moderne.png").convert("RGBA")
src = Image.new("RGB", brut.size, "white")         # le fond transparent devient blanc
src.paste(brut, (0, 0), brut)
a = np.asarray(src).astype(int)
encre = (a.min(axis=2) < 200)                      # tout ce qui n'est pas blanc
ys, xs = np.nonzero(encre)
x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()


def sur_fond(img, marge, hauteur, rayon):
    """L'image, réduite à `hauteur` px, sur un rectangle blanc arrondi, coins transparents."""
    w, h = img.size
    m = int(marge * h)
    fond = Image.new("RGBA", (w + 2 * m, h + 2 * m), (0, 0, 0, 0))
    masque = Image.new("L", fond.size, 0)
    ImageDraw.Draw(masque).rounded_rectangle([0, 0, fond.size[0] - 1, fond.size[1] - 1],
                                             radius=int(rayon * fond.size[1]), fill=255)
    fond.paste(Image.new("RGBA", fond.size, (255, 255, 255, 255)), (0, 0), masque)
    fond.paste(img.convert("RGBA"), (m, m))
    return fond.resize((round(fond.size[0] * hauteur / fond.size[1]), hauteur), Image.LANCZOS)


sur_fond(src.crop((x0, y0, x1 + 1, y1 + 1)), 0.14, 120, 0.18).save(ASSETS / "logo_prairimetre.png")
# L'emblème seul (la prairie et le repère), à gauche du premier trou blanc entre le dessin et le texte
colonnes = encre[y0:y1 + 1, x0:x1 + 1].any(axis=0)
trou = np.flatnonzero(~colonnes)
fin = trou[0] if len(trou) else colonnes.size
emb = src.crop((x0, y0, x0 + fin, y1 + 1))
cote = max(emb.size)
carre = Image.new("RGB", (cote, cote), "white")
carre.paste(emb, ((cote - emb.size[0]) // 2, (cote - emb.size[1]) // 2))
sur_fond(carre, 0.08, 128, 0.2).save(ASSETS / "icone_prairimetre.png")
print("logo", Image.open(ASSETS / "logo_prairimetre.png").size, "icône", Image.open(ASSETS / "icone_prairimetre.png").size)
