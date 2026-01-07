#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import math
import sqlite3
import urllib.parse
import html

from stats_utils import calculer_courbe_evolution

print("Content-Type: text/html; charset=utf-8\n")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EVENTS_DB_PATH = os.path.join(BASE_DIR, "events.db")

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

# ---------- Evenements ----------
def extraire_annee(date_str):
    if not date_str:
        return None
    try:
        return int(str(date_str)[:4])
    except Exception:
        return None


def echapper_xml(texte):
    if texte is None:
        return ""
    return html.escape(str(texte))


evenements = []
try:
    conn_events = sqlite3.connect(EVENTS_DB_PATH)
    cur_events = conn_events.cursor()
    cur_events.execute("""
        SELECT title, description, event_date
        FROM events
        ORDER BY event_date ASC, created_at ASC
    """)
    for title, description, event_date in cur_events.fetchall():
        evenements.append({
            "title": title or "Événement",
            "description": description or "",
            "event_date": event_date or "",
            "event_year": extraire_annee(event_date),
        })
    conn_events.close()
except Exception:
    evenements = []

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

.event-list {{
    margin-top: 12px;
    text-align: left;
    color: rgba(255,255,255,0.8);
    font-size: 0.9em;
}}

.event-list h3 {{
    margin: 10px 0 6px;
    font-size: 1em;
    color: #90EE90;
}}

.event-item {{
    margin-bottom: 6px;
    padding-bottom: 6px;
    border-bottom: 1px dashed rgba(144,238,144,0.3);
}}

.event-item:last-child {{
    border-bottom: none;
}}

.event-date {{
    font-weight: bold;
    color: #FFD86A;
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
annee_min = None
annee_max = None

if courbe:
    largeur, hauteur, marge = 280, 150, 25
    svg_hauteur = hauteur + 30
    prix_min = min(p for _, p in courbe)
    prix_max = max(p for _, p in courbe)
    plage = prix_max - prix_min if prix_max != prix_min else 1

    annee_min = courbe[0][0]
    annee_max = courbe[-1][0]

    def proj_x(annee):
        return marge + ((annee - annee_min) / (annee_max - annee_min)) * (largeur - 2 * marge)

    def proj_y(prix):
        return hauteur - marge - ((prix - prix_min) / plage) * (hauteur - 2 * marge) + offset_y

    def prix_pour_annee(annee):
        for annee_point, prix_point in courbe:
            if annee_point == annee:
                return prix_point
        for i in range(1, len(courbe)):
            annee_0, prix_0 = courbe[i - 1]
            annee_1, prix_1 = courbe[i]
            if annee_0 <= annee <= annee_1:
                ratio = (annee - annee_0) / (annee_1 - annee_0)
                return prix_0 + (prix_1 - prix_0) * ratio
        return None

    points = []
    x_2025 = None

    for annee, prix in courbe:
        x = proj_x(annee)
        y = proj_y(prix)
        points.append(f"{x},{y}")

        if annee == 2025:
            x_2025 = x

    print(f"""
<svg width="100%" height="100%"
     viewBox="0 0 {largeur} {svg_hauteur}"
     preserveAspectRatio="none">

    <!-- Axes -->
    <line x1="{marge}" y1="{hauteur-marge}"
          x2="{largeur-marge}" y2="{hauteur-marge}"
          stroke="#90EE90"/>

    <line x1="{marge}" y1="{marge}"
          x2="{marge}" y2="{hauteur-marge}"
          stroke="#90EE90"/>
""")

    for annee, _ in courbe:
        x = proj_x(annee)
        print(f'<text x="{x-10}" y="{hauteur-5}" font-size="9" fill="#90EE90">{annee}</text>')

    prix_milieu = round(prix_min + (plage / 2), 2)
    y_milieu = proj_y(prix_milieu)

    print(f"""
    <text x="4" y="{marge+8}" font-size="9" fill="#90EE90">{round(prix_max,2)}</text>
    <text x="4" y="{y_milieu+3}" font-size="9" fill="#90EE90">{prix_milieu}</text>
    <text x="4" y="{hauteur-marge}" font-size="9" fill="#90EE90">{round(prix_min,2)}</text>
    <text x="{largeur/2-18}" y="{hauteur+20}" font-size="10" fill="#90EE90">Années</text>
    <text x="10" y="{hauteur/2}" font-size="10" fill="#90EE90" transform="rotate(-90 10 {hauteur/2})">Prix (€)</text>

    <polyline
        points="{' '.join(points)}"
        fill="none"
        stroke="#90EE90"
        stroke-width="3"/>
""")

    for annee, prix in courbe:
        x = proj_x(annee)
        y = proj_y(prix)
        tooltip = echapper_xml(f"Année {annee} • Prix {prix} €")
        print(f"""
    <circle cx="{x}" cy="{y}" r="6" fill="rgba(0,0,0,0)" stroke="none">
        <title>{tooltip}</title>
    </circle>
""")

    for evt in evenements:
        annee_evt = evt.get("event_year")
        if annee_evt is None:
            continue
        if annee_evt < annee_min or annee_evt > annee_max:
            continue
        prix_evt = prix_pour_annee(annee_evt)
        if prix_evt is None:
            continue
        x_evt = proj_x(annee_evt)
        y_evt = proj_y(prix_evt)
        titre_evt = evt.get("title") or "Événement"
        description_evt = evt.get("description") or ""
        date_evt = evt.get("event_date") or str(annee_evt)
        tooltip_evt = echapper_xml(f"{titre_evt} • {date_evt} • Prix {round(prix_evt, 2)} € {description_evt}".strip())
        print(f"""
    <circle cx="{x_evt}" cy="{y_evt}" r="4" fill="#FFD86A" stroke="#FFFFFF" stroke-width="1">
        <title>{tooltip_evt}</title>
    </circle>
""")

    if x_2025 is not None:
        print(f"""

    <line x1="{x_2025}" y1="{marge}"
          x2="{x_2025}" y2="{hauteur-marge}"
          stroke="#ffffff"
          stroke-width="2"/>
""")

    print("""
</svg>
""")

print("""
        <div class="event-list">
            <h3>Événements sur la période</h3>
""")

if evenements:
    for evt in evenements:
        titre_evt = html.escape(evt.get("title") or "Événement")
        description_evt = html.escape(evt.get("description") or "")
        date_evt = html.escape(evt.get("event_date") or "Date inconnue")
        annee_evt = evt.get("event_year")
        hors_periode = ""
        if annee_evt is not None and annee_min is not None and annee_max is not None:
            if annee_evt < annee_min or annee_evt > annee_max:
                hors_periode = " (hors période)"
        print(f"""
            <div class="event-item">
                <div class="event-date">{date_evt}{hors_periode}</div>
                <div><strong>{titre_evt}</strong>{' - ' + description_evt if description_evt else ''}</div>
            </div>
        """)
else:
    print("""
            <div class="event-item">Aucun événement enregistré.</div>
    """)

print("""
        </div>
""")

print("""
    </div>
</div>

</body>
</html>
""")
