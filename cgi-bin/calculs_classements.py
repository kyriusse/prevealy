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

# ==========================
# PARAMETRES UTILISATEUR
# ==========================
type_classement = get_param("type", "top")
critere = get_param("critere", "prix")
filtre_mode = get_param("filtre_mode", "aucun")
filtre_valeur = get_param("filtre_valeur", "")

try:
    limite = int(get_param("limite", "10"))
except ValueError:
    limite = 10
limite = min(limite, 10)

if type_classement not in ("top", "flop"):
    type_classement = "top"

# ==========================
# MAPPING CRITERES SQL
# ==========================
criteres_sql = {
    "prix": ("Prix_Moyen_Actuel", "Prix moyen"),
    "aug": ("Coef_Total_2000_2025", "Coef évolution"),
    "ca": ("CA_2025_2035_MDEUR", "CA futur (MdEUR)")
}

if critere not in criteres_sql:
    critere = "prix"

colonne, label_colonne = criteres_sql[critere]
ordre = "DESC" if type_classement == "top" else "ASC"

# ==========================
# FILTRE SQL
# ==========================
conditions = [f"{colonne} IS NOT NULL"]
params = []

if filtre_mode == "famille" and filtre_valeur:
    conditions.append("Famille = ?")
    params.append(filtre_valeur)
elif filtre_mode == "type" and filtre_valeur:
    conditions.append("Type = ?")
    params.append(filtre_valeur)
else:
    filtre_mode = "aucun"
    filtre_valeur = ""

where_sql = " AND ".join(conditions)

# ==========================
# REQUETE SQL
# ==========================
sql = f"""
SELECT Objet, {colonne}, Famille, Type
FROM Prix_Objets
WHERE {where_sql}
ORDER BY {colonne} {ordre}
LIMIT ?
"""

params.append(limite)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute(sql, params)
rows = cur.fetchall()
conn.close()

# ==========================
# LISTES POUR SELECT
# ==========================
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("SELECT DISTINCT Famille FROM Prix_Objets WHERE Famille IS NOT NULL")
familles = [r[0] for r in cur.fetchall()]
cur.execute("SELECT DISTINCT Type FROM Prix_Objets WHERE Type IS NOT NULL")
types = [r[0] for r in cur.fetchall()]
conn.close()

# ==========================
# HTML
# ==========================
print(f"""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Classements</title>

<style>
body {{
    margin:0;
    font-family:Arial, sans-serif;
    color:white;
    background-image:url('/fond_classement.png');
    background-size:cover;
}}

.back-btn {{
    position:absolute;
    top:20px;
    left:20px;
    width:64px;
    height:64px;
    background:url('/back_btn_violet.png') no-repeat center;
    background-size:contain;
    transition:transform 0.2s ease;
}}
.back-btn:hover {{
    transform:scale(1.1);
}}

.panel {{
    width:1100px;
    height:650px;
    margin:80px auto;
    background-image:url('/pannel_classement.png');
    background-size:100% 100%;
    position:relative;
}}

.panel-content {{
    position:absolute;
    top:110px;
    left:100px;
    right:100px;
    bottom:100px;
    overflow-y:auto;
}}

h1 {{ text-align:center; margin-top:0; }}

form {{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:12px;
    margin-bottom:15px;
}}

select, button {{ padding:6px; }}

table {{
    width:100%;
    border-collapse:collapse;
}}

th, td {{
    padding:6px;
    border-bottom:1px solid #555;
}}

.medal {{
    font-size:1.2em;
}}

a.obj-link {{
    color:#90EE90;
    text-decoration:none;
    font-weight:bold;
}}

a.obj-link:hover {{
    text-decoration:underline;
}}
</style>
</head>

<body>

<a href="/cgi-bin/menu_statistique.py" class="back-btn"></a>

<div class="panel">
<div class="panel-content">

<h1>Classements</h1>

<form method="get">

<select name="type">
    <option value="top" {"selected" if type_classement=="top" else ""}>TOP</option>
    <option value="flop" {"selected" if type_classement=="flop" else ""}>FLOP</option>
</select>

<select name="critere">
    <option value="prix" {"selected" if critere=="prix" else ""}>Prix moyen</option>
    <option value="aug" {"selected" if critere=="aug" else ""}>Évolution</option>
    <option value="ca"  {"selected" if critere=="ca"  else ""}>CA futur</option>
</select>

<select name="filtre_mode">
    <option value="aucun"  {"selected" if filtre_mode=="aucun" else ""}>Aucun filtre</option>
    <option value="famille" {"selected" if filtre_mode=="famille" else ""}>Par famille</option>
    <option value="type" {"selected" if filtre_mode=="type" else ""}>Par type</option>
</select>

<select name="filtre_valeur">
    <option value="">--</option>
""")

for f in familles:
    sel = "selected" if (filtre_mode == "famille" and filtre_valeur == f) else ""
    print(f"<option value='{html.escape(f)}' {sel}>{html.escape(f)}</option>")

for t in types:
    sel = "selected" if (filtre_mode == "type" and filtre_valeur == t) else ""
    print(f"<option value='{html.escape(t)}' {sel}>{html.escape(t)}</option>")

print(f"""
</select>

<button type="submit">Afficher</button>
</form>

<table>
<tr>
<th>#</th>
<th></th>
<th>Objet</th>
<th>{html.escape(label_colonne)}</th>
<th>Famille</th>
<th>Type</th>
</tr>
""")

for i, (obj, val, fam, typ) in enumerate(rows, start=1):
    medal = ""
    if type_classement == "top":
        if i == 1:
            medal = "🥇"
        elif i == 2:
            medal = "🥈"
        elif i == 3:
            medal = "🥉"

    obj_url = urllib.parse.quote(obj)

    print(f"""
    <tr>
        <td>{i}</td>
        <td class="medal">{medal}</td>
        <td>
            <a class="obj-link" href="/cgi-bin/objet.py?nom={obj_url}">
                {html.escape(obj)}
            </a>
        </td>
        <td>{html.escape(str(val))}</td>
        <td>{html.escape(fam) if fam else '-'}</td>
        <td>{html.escape(typ) if typ else '-'}</td>
    </tr>
    """)

print("""
</table>

</div>
</div>

</body>
</html>
""")
