# stats_utils.py

def valeur_valide(valeur):
    """Retourne un float positif ou None"""
    try:
        valeur = float(valeur)
        if valeur <= 0:
            return None
        return valeur
    except:
        return None


def facteur_speculation(speculation):
    mapping = {
        "Très faible": 0.95,
        "Faible": 0.98,
        "Moyenne": 1.00,
        "Forte": 1.08,
        "Hyper Forte": 1.20
    }
    return mapping.get(speculation, 1.00)


def facteur_utilisation(utilisation):
    mapping = {
        "Quotidien +": 0.97,
        "Quotidien": 0.99,
        "Moyen": 1.00,
        "Occasionnelle": 1.05,
        "Rarissime": 1.15
    }
    return mapping.get(utilisation, 1.00)


def calculer_courbe_evolution(
    prix_2000,
    prix_actuel,
    coef_prevision,
    speculation,
    taux_utilisation,
    annee_depart=2000, #initialisation u0
    annee_fin=2035, #arrêt du calcule / rapelle 2025+ = prévision
    pas=5 #+ 5 (ans)
):
    """
    Genere une courbe d'evolution robuste pour tous les objets.
    """

    prix_actuel = valeur_valide(prix_actuel)
    prix_2000 = valeur_valide(prix_2000)

    if prix_actuel is None:
        return []

    nombre_annees = annee_fin - annee_depart
    points = []

    # --- Cas 1 : historique disponible ---
    if prix_2000:
        taux_annuel = (prix_actuel / prix_2000) ** (1 / nombre_annees) - 1

    # --- Cas 2 : reconstruction theorique ---
    else:
        coef_prevision = valeur_valide(coef_prevision) or 1.02
        facteur = facteur_speculation(speculation) * facteur_utilisation(taux_utilisation)
        taux_annuel = coef_prevision * facteur - 1
        prix_2000 = prix_actuel / ((1 + taux_annuel) ** nombre_annees)

    # --- Construction de la courbe ---
    for annee in range(annee_depart, annee_fin + 1, pas):
        n = annee - annee_depart
        prix = prix_2000 * ((1 + taux_annuel) ** n)
        points.append((annee, round(prix, 2)))

    return points

# ============================================================
# Nouveaux outils pour la simulation deterministe (sim_calc)
# ============================================================

def calculer_stats_min_max_moyenne(valeurs):
    """
    Retourne un petit resume statistique:
    - moyenne, min, max
    Si liste vide -> (None, None, None)
    """
    if not valeurs:
        return (None, None, None)
    try:
        vmin = min(valeurs)
        vmax = max(valeurs)
        vmoy = sum(valeurs) / float(len(valeurs))
        return (vmoy, vmin, vmax)
    except Exception:
        return (None, None, None)


def _echapper_xml(texte):
    """Echappe minimal pour SVG/XML."""
    if texte is None:
        return ""
    s = str(texte)
    s = s.replace("&", "&amp;")
    s = s.replace("<", "&lt;")
    s = s.replace(">", "&gt;")
    s = s.replace('"', "&quot;")
    return s


def generer_svg_courbes(
    series,
    titre="Simulation",
    largeur=980,
    hauteur=320,
    marge=42
):
    """
    Genere un SVG simple (sans JS) pour afficher des courbes.

    Parametre:
    - series: dict { "NomSerie": [(x, y), (x, y), ...], ... }

    Sortie:
    - string contenant du SVG complet

    Notes:
    - Pas de couleurs imposees "artistiques"; on utilise des strokes differents simples.
    - Si une serie est vide, elle n est pas tracee.
    """

    # --- Rassembler tous les points pour determiner bornes globales ---
    xs = []
    ys = []
    for nom, pts in (series or {}).items():
        for (x, y) in (pts or []):
            try:
                xs.append(float(x))
                ys.append(float(y))
            except Exception:
                pass

    # --- Si rien a tracer, retourner un SVG "vide" lisible ---
    if not xs or not ys:
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">'
            '<rect x="0" y="0" width="{w}" height="{h}" fill="rgba(0,0,0,0.18)"/>'
            '<text x="20" y="40" fill="white" font-family="Arial" font-size="16">Aucune donnee</text>'
            '</svg>'
        ).format(w=int(largeur), h=int(hauteur))

    xmin = min(xs)
    xmax = max(xs)
    ymin = min(ys)
    ymax = max(ys)

    # --- Eviter division par zero si plage nulle ---
    if xmax == xmin:
        xmax = xmin + 1.0
    if ymax == ymin:
        ymax = ymin + 1.0

    # --- Fonctions de projection (x,y) -> (px,py) dans le SVG ---
    zone_w = float(largeur - 2 * marge)
    zone_h = float(hauteur - 2 * marge)

    def proj_x(x):
        return marge + ((float(x) - xmin) / (xmax - xmin)) * zone_w

    def proj_y(y):
        # y augmente vers le bas en SVG -> on inverse
        return marge + zone_h - ((float(y) - ymin) / (ymax - ymin)) * zone_h

    # --- Styles simples pour distinguer quelques courbes ---
    styles = [
        "stroke: rgba(255,216,106,0.95); stroke-width: 2.4; fill: none;",
        "stroke: rgba(190,120,255,0.90); stroke-width: 2.2; fill: none;",
        "stroke: rgba(110,255,220,0.85); stroke-width: 2.0; fill: none;",
        "stroke: rgba(255,140,140,0.85); stroke-width: 2.0; fill: none;",
    ]

    # --- Debut SVG ---
    svg = []
    svg.append('<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">'.format(
        w=int(largeur), h=int(hauteur)
    ))

    # Fond
    svg.append('<defs>')
    svg.append(
        '<linearGradient id="fond" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="rgba(10,6,18,0.90)"/>'
        '<stop offset="100%" stop-color="rgba(18,10,34,0.90)"/>'
        '</linearGradient>'
    )
    svg.append('</defs>')
    svg.append('<rect x="0" y="0" width="{w}" height="{h}" rx="18" ry="18" fill="url(#fond)"/>'.format(
        w=int(largeur), h=int(hauteur)
    ))

    # Grille legere
    for i in range(0, 6):
        y = marge + (zone_h * i / 5.0)
        svg.append('<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="rgba(255,255,255,0.08)" stroke-width="1"/>'.format(
            x1=int(marge), x2=int(largeur - marge), y=int(y)
        ))
    for i in range(0, 8):
        x = marge + (zone_w * i / 7.0)
        svg.append('<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>'.format(
            x=int(x), y1=int(marge), y2=int(hauteur - marge)
        ))

    # Titre
    svg.append('<text x="{x}" y="{y}" fill="rgba(255,216,106,0.95)" font-family="Arial" font-size="16">'.format(
        x=int(marge), y=int(marge - 14)
    ) + _echapper_xml(titre) + '</text>')

    # Axes (labels min/max)
    svg.append('<text x="{x}" y="{y}" fill="rgba(255,255,255,0.70)" font-family="Arial" font-size="12">y: {v}</text>'.format(
        x=int(marge), y=int(hauteur - 10), v=_echapper_xml(round(ymin, 2))
    ))
    svg.append('<text x="{x}" y="{y}" fill="rgba(255,255,255,0.70)" font-family="Arial" font-size="12">y: {v}</text>'.format(
        x=int(marge), y=int(marge + 12), v=_echapper_xml(round(ymax, 2))
    ))

    # Tracer chaque serie
    idx = 0
    legend_y = marge + 18
    legend_x = int(largeur - marge - 260)

    for nom, pts in (series or {}).items():
        if not pts:
            continue

        style = styles[idx % len(styles)]
        idx += 1

        # Construire points polyline
        coord = []
        for (x, y) in pts:
            try:
                px = proj_x(x)
                py = proj_y(y)
                coord.append("{},{}".format(round(px, 2), round(py, 2)))
            except Exception:
                pass

        if coord:
            svg.append('<polyline points="{p}" style="{s}"/>'.format(
                p=" ".join(coord),
                s=style
            ))

        # Legende (simple)
        svg.append('<rect x="{x}" y="{y}" width="12" height="12" fill="none" stroke="rgba(255,255,255,0.12)"/>'.format(
            x=legend_x, y=int(legend_y - 10)
        ))
        svg.append('<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" style="{s}"/>'.format(
            x1=legend_x, x2=legend_x + 12, y=int(legend_y - 4), s=style
        ))
        svg.append('<text x="{x}" y="{y}" fill="rgba(255,255,255,0.82)" font-family="Arial" font-size="12">{t}</text>'.format(
            x=legend_x + 18, y=int(legend_y),
            t=_echapper_xml(nom)
        ))
        legend_y += 18

    svg.append('</svg>')
    return "\n".join(svg)
