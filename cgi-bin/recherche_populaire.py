#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import html
import urllib.parse

print("Content-Type: text/html; charset=utf-8\n")

DB_PATH = "cgi-bin/objets.db"

# ==================================================
# Lecture des paramètres GET (remplace cgi)
# ==================================================
def get_param(name, default=""):
    qs = os.environ.get("QUERY_STRING", "")
    params = urllib.parse.parse_qs(qs, keep_blank_values=True)
    return params.get(name, [default])[0]

choix = get_param("choix", "")

# ==========================
# REQUETES POPULAIRES
# ==========================
requetes = {
    "cher": {
        "titre": "Objets les plus chers",
        "sql": """
            SELECT Objet, Prix_Moyen_Actuel
            FROM Prix_Objets
            WHERE Prix_Moyen_Actuel IS NOT NULL
            ORDER BY Prix_Moyen_Actuel DESC
            LIMIT 10
        """,
        "label": "Prix moyen (EUR)"
    },
    "evolution": {
        "titre": "Plus forte evolution depuis 2000",
        "sql": """
            SELECT Objet, Coef_Total_2000_2025
            FROM Prix_Objets
            WHERE Coef_Total_2000_2025 IS NOT NULL
            ORDER BY Coef_Total_2000_2025 DESC
            LIMIT 10
        """,
        "label": "Coefficient evolution"
    },
    "quotidien": {
        "titre": "Objets du quotidien",
        "sql": """
            SELECT Objet, Taux_Utilisation
            FROM Prix_Objets
            WHERE Taux_Utilisation LIKE 'Quotidien%'
            LIMIT 10
        """,
        "label": "Utilisation"
    },
    "tech": {
        "titre": "Marches technologiques",
        "sql": """
            SELECT Objet, Famille
            FROM Prix_Objets
            WHERE Famille LIKE '%Numérique%' OR Famille LIKE '%Technologie%'
            LIMIT 10
        """,
        "label": "Famille"
    },
    "speculation": {
        "titre": "Objets a forte speculation",
        "sql": """
            SELECT Objet, Speculation
            FROM Prix_Objets
            WHERE Speculation LIKE 'Forte%'
            LIMIT 10
        """,
        "label": "Speculation"
    },
    "ca": {
        "titre": "Plus gros CA futur",
        "sql": """
            SELECT Objet, CA_2025_2035_MDEUR
            FROM Prix_Objets
            WHERE CA_2025_2035_MDEUR IS NOT NULL
            ORDER BY CA_2025_2035_MDEUR DESC
            LIMIT 10
        """,
        "label": "CA futur (MdEUR)"
    }
}

rows = []
titre_resultat = ""
label_col = ""

if choix in requetes:
    req = requetes[choix]
    titre_resultat = req["titre"]
    label_col = req["label"]

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(req["sql"])
    rows = cur.fetchall()
    conn.close()

# ==========================
# HTML
# ==========================
print("""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Recherches populaires</title>

<style>
body {
    margin:0;
    font-family:Arial, sans-serif;
    color:white;
    background:url('/fond_violet_page_stats.png') repeat center;
    background-size:100%;
}

.back-btn {
    position:absolute;
    top:20px;
    left:20px;
    width:64px;
    height:64px;
    background:url('/back_btn_violet.png') no-repeat center;
    background-size:contain;
    transition:transform 0.2s ease;
}

.back-btn:hover {
    transform:scale(1.1);
}

.panel {
    width:900px;
    margin:60px auto;
    background:url('/fond_filtre_pannel.png') no-repeat center;
    background-size:100% 100%;
    padding:50px;
}

h1 {
    text-align:center;
    margin-top:0;
}

.buttons {
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:15px;
    margin-bottom:30px;
}

.buttons a {
    display:block;
    padding:12px;
    text-align:center;
    background:#4a2a50;
    color:white;
    text-decoration:none;
    border-radius:10px;
}

.buttons a:hover {
    background:#5e3466;
}

table {
    width:100%;
    border-collapse:collapse;
}

th, td {
    padding:8px;
    border-bottom:1px solid #555;
}
</style>
</head>

<body>

<a href="/cgi-bin/menu_statistique.py" class="back-btn"></a>

<div class="panel">
<h1>Recherches populaires</h1>

<div class="buttons">
    <a href="?choix=cher">Objets les plus chers 💰</a>
    <a href="?choix=evolution">Plus forte evolution 📈</a>
    <a href="?choix=quotidien">Objets du quotidien 🪑</a>
    <a href="?choix=tech">Marches technologiques</a>
    <a href="?choix=speculation">Forte speculation</a>
    <a href="?choix=ca">Plus gros CA futur</a>
</div>
""")

if rows:
    print(f"<h2>{html.escape(titre_resultat)}</h2>")
    print("<table>")
    print(f"<tr><th>Objet</th><th>{html.escape(label_col)}</th></tr>")

    for o, v in rows:
        o_url = urllib.parse.quote(o)
        print(f"""
        <tr>
            <td>
                <a href="/cgi-bin/objet.py?nom={o_url}"
                   style="color:#90EE90; text-decoration:none;">
                    {html.escape(o)}
                </a>
            </td>
            <td>{html.escape(str(v))}</td>
        </tr>
        """)

    print("</table>")

print("""
</div>
</body>
</html>
""")
