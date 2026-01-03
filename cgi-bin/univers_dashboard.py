#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import urllib.parse

print("Content-Type: text/html; charset=utf-8\n")

UNIVERSE_DIR = "cgi-bin/universes/"

def get_param(name, default=""):
    qs = os.environ.get("QUERY_STRING", "")
    params = urllib.parse.parse_qs(qs, keep_blank_values=True)
    return params.get(name, [default])[0]

def universe_path(universe_id):
    """Retourne le chemin vers le fichier SQLite de l'univers"""
    safe = "".join([c for c in universe_id if c.isalnum() or c in ("-", "_")])
    return os.path.join(UNIVERSE_DIR, f"universe_{safe}.db")

def get_universe_name(universe_id):
    """Retourne le nom de l'univers en fonction de son ID"""
    try:
        names_file = os.path.join(UNIVERSE_DIR, "univers_names.txt")
        if os.path.exists(names_file):
            with open(names_file, "r", encoding="utf-8") as f:
                for line in f:
                    if "," in line:
                        uid, name = line.strip().split(",", 1)
                        if uid == universe_id:
                            return name
    except Exception as e:
        return "Nom inconnu"
    return "Nom inconnu"

def check_stat_objects_table(universe_id):
    """Vérifie si la table stat_objects existe et contient des données"""
    universe_path_ = universe_path(universe_id)
    
    if not os.path.exists(universe_path_):
        return False, f"Le fichier de l'univers n'existe pas : {universe_path_}"
    
    try:
        conn = sqlite3.connect(universe_path_)
        cur = conn.cursor()
        
        # Vérifier si la table existe
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stat_objects'")
        if not cur.fetchone():
            conn.close()
            return False, "La table 'stat_objects' n'existe pas dans cet univers."
        
        # Compter les objets
        cur.execute("SELECT COUNT(*) FROM stat_objects")
        count = cur.fetchone()[0]
        
        # Lister les colonnes
        cur.execute("PRAGMA table_info(stat_objects)")
        columns = [col[1] for col in cur.fetchall()]
        
        conn.close()
        return True, f"Table OK : {count} objets, colonnes : {', '.join(columns)}"
        
    except Exception as e:
        return False, f"Erreur lors de la vérification : {e}"

# ------------------------------
# Actions
# ------------------------------
uid = get_param("uid", "")

if not uid:
    print("""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Erreur</title>
</head>
<body>
<h1>Erreur : Aucun univers spécifié</h1>
<a href="/cgi-bin/create_stat_object.py">Retour</a>
</body>
</html>
""")
    exit()

universe_name = get_universe_name(uid)
table_ok, table_msg = check_stat_objects_table(uid)

# ------------------------------
# HTML
# ------------------------------
print(f"""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Menu de l'univers - {universe_name}</title>

<style>
body {{
    margin: 0;
    font-family: Arial, sans-serif;
    color: white;
    background-image: url('/fond_galactique_objet_2.png');
    background-size: cover;
    background-position: center;
    min-height: 100vh;
}}

.panel {{
    width: 900px;
    margin: 60px auto;
    background: url('/panel_jaune_noir.png') no-repeat center;
    background-size: 100% 100%;
    padding: 50px;
    box-sizing: border-box;
}}

h1 {{
    text-align: center;
    margin-top: 0;
    color: #FFD86A;
}}

.form-box {{
    padding: 20px;
}}

button {{
    width: 100%;
    padding: 15px 20px;
    border-radius: 10px;
    background: #4a2a50;
    color: white;
    border: none;
    cursor: pointer;
    margin-top: 15px;
    font-size: 16px;
    font-weight: bold;
}}

button:hover {{
    background: #5e3466;
}}

.back-btn {{
    position: fixed;
    top: 20px;
    left: 20px;
    width: 64px;
    height: 64px;
    background-image: url('/back_btn_violet.png');
    background-size: contain;
    background-repeat: no-repeat;
    cursor: pointer;
    transition: transform 0.2s ease;
}}

.back-btn:hover {{
    transform: scale(1.1);
}}

.info-box {{
    background: rgba(0, 0, 0, 0.4);
    padding: 15px;
    border-radius: 10px;
    margin: 20px 0;
    border: 1px solid rgba(255, 216, 106, 0.3);
}}

.error {{
    background: rgba(138, 42, 42, 0.4);
    border-color: rgba(255, 100, 100, 0.5);
}}

.success {{
    background: rgba(42, 138, 42, 0.4);
    border-color: rgba(100, 255, 100, 0.5);
}}

.universe-info {{
    margin-bottom: 20px;
    text-align: center;
    opacity: 0.8;
}}
</style>
</head>

<body>

<a href="/cgi-bin/create_stat_object.py" class="back-btn" title="Retour"></a>

<div class="panel">
  <div class="form-box">
    <h1>Menu de l'univers</h1>
    
    <div class="universe-info">
        <strong>{universe_name}</strong><br>
        <small>ID: {uid}</small>
    </div>

    <div class="info-box {'success' if table_ok else 'error'}">
      {table_msg}
    </div>

    <form method="get" action="/cgi-bin/personnalisation_objet.py">
      <input type="hidden" name="uid" value="{uid}">
      <button type="submit">Création d'objet</button>
    </form>

    <form method="get" action="/cgi-bin/menu_simulation.py">
      <input type="hidden" name="uid" value="{uid}">
      <button type="submit">Simulation (à venir)</button>
    </form>
  </div>
</div>

</body>
</html>
""")