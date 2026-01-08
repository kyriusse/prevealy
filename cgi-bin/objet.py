#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import math
import sqlite3
import urllib.parse

from stats_utils import calculer_courbe_evolution

print("Content-Type: text/html; charset=utf-8\n")

# ==================================================
# Lecture des paramètres GET (remplace cgi)
# ==================================================
def get_param(name, default=""):
    qs = os.environ.get("QUERY_STRING", "")
    params = urllib.parse.parse_qs(qs, keep_blank_values=True)
    return params.get(name, [default])[0]

# ---------- Récupération paramètres ----------
nom = get_param("nom")
img = get_param("img")

if not nom:
    print("<h2>Objet introuvable</h2>")
    sys.exit()

nom = urllib.parse.unquote(nom)
img = urllib.parse.unquote(img) if img else "/no_image.png"

# ---------- BDD ----------
DB_PATH = "cgi-bin/objets.db"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("SELECT * FROM Prix_Objets WHERE Objet = ?", (nom,))
row = cur.fetchone()

if not row:
    conn.close()
    print("<h2>Objet non trouvé</h2>")
    sys.exit()

colonnes = [desc[0] for desc in cur.description]
data = dict(zip(colonnes, row))
conn.close()

# ---------- Courbe via stats_utils ----------
courbe = calculer_courbe_evolution(
    prix_2000=data.get("Prix_2000_EUR"),
    prix_actuel=data.get("Prix_Moyen_Actuel"),
    coef_prevision=data.get("Coef_Aug_Prev"),
    speculation=data.get("Speculation"),
    taux_utilisation=data.get("Taux_Utilisation")
)

# ---------- Isolation des données ----------
PRIX_MOYEN_COL = "Prix_Moyen_Actuel"
prix_moyen = data.pop(PRIX_MOYEN_COL, None)
data.pop("Objet", None)

# ---------- Répartition stats ----------
stats_list = list(data.items())
split_point = math.ceil(len(stats_list) / 2)
stats_col1 = stats_list[:split_point]
stats_col2 = stats_list[split_point:]

# ---------- HTML du prix moyen ----------
prix_moyen_content = ""
if prix_moyen is not None:
    prix_moyen_content = f"""
        <div class="average-price-box">
            <div class="price-button">
                {prix_moyen}
            </div>
        </div>
    """

# ==================================================
# HTML
# ==================================================
print(f"""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{nom}</title>

<style>
body {{
    margin: 0;
    padding: 0;
    font-family: Arial, sans-serif;
    background: url('/fond_page_objet.png') repeat center;
    background-size: 100%;
    color: #90EE90;
}}

h1 {{
    font-size: 2em;
    color: white;
    margin-top: 10px;
}}

.back-btn {{
    position:absolute;
    top:20px;
    left:20px;
    width:64px;
    height:64px;
    background:url('/bouton_retour_page_objet.png') no-repeat center;
    background-size:contain;
    transition:transform 0.2s ease;
}}
.back-btn:hover {{
    transform:scale(1.1);
}}

.grid-container {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    grid-template-rows: auto 1fr 1fr;
    gap: 20px;
    max-width: 1200px;
    margin: 0 auto;
    padding: 100px 40px 40px 40px;
}}

.grid-container > h1 {{
    grid-column: 1 / span 3;
    text-align: center;
}}

.center-content {{
    grid-column: 2 / 3;
    grid-row: 2 / 4;
    display: flex;
    flex-direction: column;
    align-items: center;
}}

.image-box {{
    margin-bottom: 25px;
}}

.image-box img {{
    max-width: 250px;
    width: 100%;
    border-radius: 18px;
    box-shadow: 0 0 15px rgba(0,255,127,0.5);
}}

.stats-frame-1 {{
    grid-column: 1 / 2;
    grid-row: 2 / 3;
    background: url('/cadre_vert_objet.png') no-repeat center center;
    background-size: 100% 100%;
    padding: 30px;
}}

.stats-frame-2 {{
    grid-column: 3 / 4;
    grid-row: 2 / 3;
    background: url('/cadre_vert_objet_2.png') no-repeat center center;
    background-size: 100% 100%;
    padding: 30px;
}}

.average-price-box {{
    height: 90px;
}}

.price-button {{
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
    background: url('/btn_vert.png') no-repeat center center;
    background-size: 100% 100%;
    color: white;
    font-size: 1.5em;
    font-weight: bold;
    min-width: 250px;
}}

.stat-item {{
    margin: 8px 0;
    font-size: 1.1em;
}}

.stat-item span {{
    font-weight: bold;
    color: white;
}}

.chart-frame {{
    grid-column: 3 / 4;
    grid-row: 3 / 4;
    border: 1px solid #90EE90;
    border-radius: 10px;
    padding: 20px;
    text-align: center;
}}
</style>
</head>

<body>

<a href="/cgi-bin/index.py" class="back-btn"></a>

<div class="grid-container">
    <h1>{nom}</h1>

    <div class="stats-frame-1">
""")

# ---------- Stats colonne 1 ----------
for col, val in stats_col1:
    print(f'<p class="stat-item"><span>{col} :</span> {val}</p>')

# ---------- Centre ----------
print(f"""
    </div>

    <div class="center-content">
        <div class="image-box">
            <img src="{img}" onerror="this.src='/no_image.png'">
        </div>
        {prix_moyen_content}
    </div>

    <div class="stats-frame-2">
""")

# ---------- Stats colonne 2 ----------
for col, val in stats_col2:
    print(f'<p class="stat-item"><span>{col} :</span> {val}</p>')

# ---------- Chart frame ----------
print("""
    </div>

    <div class="chart-frame">
        <p>Évolution des prix</p>
""")

# ==================================================
# SVG – VERSION ORIGINALE (INCHANGÉE)
# ==================================================
offset_y = 0

if courbe:
    largeur, hauteur, marge = 280, 150, 25
    prix_min = min(p for _, p in courbe)
    prix_max = max(p for _, p in courbe)
    plage = prix_max - prix_min if prix_max != prix_min else 1

    points = []
    x_2025 = None

    for i, (annee, prix) in enumerate(courbe):
        x = marge + i * (largeur - 2*marge) / (len(courbe)-1)
        y = hauteur - marge - ((prix - prix_min) / plage) * (hauteur - 2*marge) + offset_y
        points.append(f"{x},{y}")

        if annee == 2025:
            x_2025 = x

    print(f"""
<svg width="100%" height="100%"
     viewBox="0 +20 {largeur} {hauteur}"
     preserveAspectRatio="none">

    <!-- Axes -->
    <line x1="{marge}" y1="{hauteur-marge}"
          x2="{largeur-marge}" y2="{hauteur-marge}"
          stroke="#90EE90"/>

    <line x1="{marge}" y1="{marge}"
          x2="{marge}" y2="{hauteur-marge}"
          stroke="#90EE90"/>
""")

    for i, (annee, _) in enumerate(courbe):
        x = marge + i * (largeur - 2*marge) / (len(courbe)-1)
        print(f'<text x="{x-10}" y="{hauteur-5}" font-size="9" fill="#90EE90">{annee}</text>')

    print(f"""
    <text x="4" y="{marge+8}" font-size="9" fill="#90EE90">{round(prix_max,2)}</text>
    <text x="4" y="{hauteur-marge}" font-size="9" fill="#90EE90">{round(prix_min,2)}</text>

    <polyline
        points="{' '.join(points)}"
        fill="none"
        stroke="#90EE90"
        stroke-width="3"/>

    <line x1="{x_2025}" y1="{marge}"
          x2="{x_2025}" y2="{hauteur-marge}"
          stroke="#ffffff"
          stroke-width="2"/>
</svg>
""")

print("""
    </div>
</div>

</body>
</html>
""")
