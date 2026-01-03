#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sqlite3
import html
import urllib.parse
import os

print("Content-Type: text/html; charset=utf-8\n")

DB_PATH = "cgi-bin/objets.db"

def get_param(name, default=""):
    qs = os.environ.get("QUERY_STRING", "")
    params = urllib.parse.parse_qs(qs, keep_blank_values=True)
    return params.get(name, [default])[0]


# ==================================================
# OUTILS BDD
# ==================================================
def distinct(col):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(f"SELECT DISTINCT {col} FROM Prix_Objets WHERE {col} IS NOT NULL")
    vals = [r[0] for r in cur.fetchall()]
    conn.close()
    return vals

familles = distinct("Famille")
types = distinct("Type")
speculations = distinct("Speculation")

# ==================================================
# LECTURE DES FILTRES
# ==================================================
famille = get_param("famille")
type_ = get_param("type")
speculation = get_param("speculation")
prix_max = get_param("prix_max")


# ==================================================
# CONSTRUCTION SQL
# ==================================================
conditions = []
params = []

if famille:
    conditions.append("Famille = ?")
    params.append(famille)

if type_:
    conditions.append("Type = ?")
    params.append(type_)

if speculation:
    conditions.append("Speculation = ?")
    params.append(speculation)

if prix_max:
    try:
        conditions.append("Prix_Moyen_Actuel <= ?")
        params.append(float(prix_max))
    except ValueError:
        pass

sql = """
SELECT Objet, Famille, Type, Speculation, Prix_Moyen_Actuel
FROM Prix_Objets
"""

if conditions:
    sql += " WHERE " + " AND ".join(conditions)

# ==================================================
# EXECUTION
# ==================================================
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute(sql, params)
rows = cur.fetchall()
conn.close()

# ==================================================
# HTML
# ==================================================
print("""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Recherche facile</title>

<style>
body {
    font-family: Arial, sans-serif;
    color:white;
    margin:0;
    background-image: url('/fond_violet_page_stats.png');
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    background-attachment: fixed;
}

/* ===== BOUTON RETOUR ===== */
.back-btn {
    position:absolute;
    top:20px;
    left:20px;
    width:64px;
    height:64px;
    background-image:url('/back_btn_violet.png');
    background-size:contain;
    background-repeat:no-repeat;
    cursor:pointer;
    transition: transform 0.15s ease;
}
.back-btn:hover {
    transform: scale(1.12);
}

/* ===== PANNEAU ===== */
.panel {
    width:950px;
    height:650px;
    margin:60px auto;
    background-image: url('/fond_filtre_pannel.png');
    background-size:100% 100%;
    background-repeat:no-repeat;
    position:relative;
}

.panel-content {
    position:absolute;
    top:80px;
    left:70px;
    right:70px;
    bottom:70px;
    overflow-y:auto;
}

h1 {
    text-align:center;
    margin-top:0;
}

form {
    display:grid;
    grid-template-columns: 1fr 1fr;
    gap:20px;
}

label { font-weight:bold; }

select, input {
    padding:8px;
    width:100%;
}

button {
    grid-column: span 2;
    padding:12px;
    font-size:1.1em;
    cursor:pointer;
}

.result {
    margin-top:25px;
    background:#1f1223;
    padding:15px;
    border-radius:15px;
}

.item {
    padding:6px 0;
    border-bottom:1px solid #555;
}

.item a {
    color:#90EE90;
    text-decoration:none;
    font-weight:bold;
}

.item a:hover {
    text-decoration:underline;
}
</style>
</head>

<body>

<a href="menu_statistique.py" class="back-btn" title="Retour"></a>

<div class="panel">
<div class="panel-content">

<h1>Recherche facile</h1>

<form method="get">

<div>
<label>Famille</label>
<select name="famille">
<option value="">-- toutes --</option>
""")

for f in familles:
    selected = "selected" if f == famille else ""
    print(f"<option value='{html.escape(f)}' {selected}>{html.escape(f)}</option>")

print("""
</select>
</div>

<div>
<label>Type</label>
<select name="type">
<option value="">-- tous --</option>
""")

for t in types:
    selected = "selected" if t == type_ else ""
    print(f"<option value='{html.escape(t)}' {selected}>{html.escape(t)}</option>")

print("""
</select>
</div>

<div>
<label>Spéculation</label>
<select name="speculation">
<option value="">-- toutes --</option>
""")

for s in speculations:
    selected = "selected" if s == speculation else ""
    print(f"<option value='{html.escape(s)}' {selected}>{html.escape(s)}</option>")

print("""
</select>
</div>

<div>
<label>Prix moyen max (€)</label>
<input type="number" name="prix_max" value="{}">
</div>

<button type="submit">Rechercher</button>

</form>

<div class="result">
<h2>Résultats ({})</h2>
""".format(html.escape(prix_max) if prix_max else "", len(rows)))

for o, f, t, s, p in rows:
    o_url = urllib.parse.quote(o)

    print(f"""
    <div class="item">
        <a href="objet.py?nom={o_url}">{html.escape(o)}</a>
        — {html.escape(f)} / {html.escape(t)}
        — {html.escape(s)}
        — {p} €
    </div>
    """)

print("""
</div>
</div>
</div>

</body>
</html>
""")
