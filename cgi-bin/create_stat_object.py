#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import time
import urllib.parse

print("Content-Type: text/html; charset=utf-8\n")

MAX_UNIVERSES = 3
UNIVERSE_DIR = "cgi-bin/universes/"
DB_PATH = "cgi-bin/objets.db"

def get_param(name, default=""):
    """Récupère les paramètres de l'URL"""
    qs = os.environ.get("QUERY_STRING", "")
    params = urllib.parse.parse_qs(qs, keep_blank_values=True)
    return params.get(name, [default])[0]

def ensure_dir(path):
    """Assure que le répertoire existe"""
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)

def list_universes():
    """Liste les univers existants"""
    ensure_dir(UNIVERSE_DIR)
    universes = []
    for fn in os.listdir(UNIVERSE_DIR):
        if fn.startswith("universe_") and fn.endswith(".db"):
            uid = fn.replace("universe_", "").replace(".db", "")
            universe_name = get_universe_name(uid)
            if universe_name != "Nom inconnu":
                universes.append((universe_name, uid))
    return universes

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
        print(f"<!-- Erreur lors de la récupération du nom de l'univers : {e} -->")
    return "Nom inconnu"

def universe_path(universe_id):
    """Retourne le chemin vers le fichier SQLite de l'univers"""
    safe = "".join([c for c in universe_id if c.isalnum() or c in ("-", "_")])
    return os.path.join(UNIVERSE_DIR, f"universe_{safe}.db")

def create_universe(name):
    """Crée un nouvel univers basé sur la BDD originale"""
    ensure_dir(UNIVERSE_DIR)
    universes = list_universes()
    if len(universes) >= MAX_UNIVERSES:
        return (False, "Maximum 3 univers atteints.")

    name = (name or "").strip()
    if not name or name == "Nom inconnu":
        return (False, "Nom manquant ou invalide.")

    # ID basé sur le timestamp
    uid = str(int(time.time()))
    
    # Chemin vers la nouvelle BDD de l'univers
    new_universe_path = universe_path(uid)
    
    try:
        # Vérifier que la BDD source existe
        if not os.path.exists(DB_PATH):
            return (False, f"La base de données source n'existe pas : {DB_PATH}")
        
        # Créer la connexion à la nouvelle BDD
        conn_new = sqlite3.connect(new_universe_path)
        cur_new = conn_new.cursor()
        
        # Se connecter à la BDD source
        conn_source = sqlite3.connect(DB_PATH)
        cur_source = conn_source.cursor()
        
        # Récupérer la structure de la table Prix_Objets
        cur_source.execute("PRAGMA table_info(Prix_Objets)")
        columns_info = cur_source.fetchall()
        
        if not columns_info:
            conn_source.close()
            conn_new.close()
            return (False, "La table Prix_Objets n'existe pas dans la BDD source")
        
        # Créer la structure de la table stat_objects
        columns_def = []
        for col in columns_info:
            col_name = col[1]
            col_type = col[2]
            columns_def.append(f"[{col_name}] {col_type}")
        
        create_table_sql = f"CREATE TABLE stat_objects ({', '.join(columns_def)})"
        cur_new.execute(create_table_sql)
        
        # Copier toutes les données
        cur_source.execute("SELECT * FROM Prix_Objets")
        rows = cur_source.fetchall()
        
        if rows:
            # Préparer l'insertion
            placeholders = ','.join(['?' for _ in columns_info])
            insert_sql = f"INSERT INTO stat_objects VALUES ({placeholders})"
            cur_new.executemany(insert_sql, rows)
        
        # Ajouter la colonne liaison
        cur_new.execute("ALTER TABLE stat_objects ADD COLUMN liaison TEXT DEFAULT 'null'")
        
        conn_new.commit()
        conn_source.close()
        conn_new.close()
        
        # Enregistrer le nom de l'univers
        names_file = os.path.join(UNIVERSE_DIR, "univers_names.txt")
        with open(names_file, "a", encoding="utf-8") as f:
            f.write(f"{uid},{name}\n")
        
        return (True, uid)
        
    except Exception as e:
        # Nettoyer en cas d'erreur
        if os.path.exists(new_universe_path):
            os.remove(new_universe_path)
        return (False, f"Impossible de créer l'univers : {e}")

def delete_universe(universe_id):
    """Supprime un univers en effaçant son fichier SQLite et son nom"""
    path = universe_path(universe_id)
    if os.path.exists(path):
        os.remove(path)
    
    # Supprimer le nom de l'univers dans le fichier de noms
    names_file = os.path.join(UNIVERSE_DIR, "univers_names.txt")
    if os.path.exists(names_file):
        with open(names_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        with open(names_file, "w", encoding="utf-8") as f:
            for line in lines:
                if not line.startswith(f"{universe_id},"):
                    f.write(line)
    return True

# ------------------------------
# Actions
# ------------------------------
action = get_param("action", "")
new_name = get_param("new_name", "")
uid_to_delete = get_param("uid_to_delete", "")

msg = ""
if action == "create":
    ok, res = create_universe(new_name)
    if ok:
        msg = f"Univers '{new_name}' créé avec succès !"
    else:
        msg = res

if action == "delete" and uid_to_delete:
    if delete_universe(uid_to_delete):
        msg = "Univers supprimé avec succès."
    else:
        msg = "Erreur lors de la suppression de l'univers."

universes = list_universes()

# ------------------------------
# HTML
# ------------------------------
print("""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Univers statistique</title>

<style>
body {
    margin:0;
    font-family:Arial, sans-serif;
    color:white;
    background-image:url('/grand_fond_jaune.png');
    background-size:cover;
    background-position:center;
    background-repeat:no-repeat;
}

.back-btn {
    position:absolute;
    top:20px;
    left:20px;
    width:64px;
    height:64px;
    background-image:url('/back_btn_jaune.png');
    background-size:contain;
    background-repeat:no-repeat;
    cursor:pointer;
    transition:transform 0.2s ease;
}
.back-btn:hover { transform:scale(1.1); }

.panel {
    width:900px;
    height:650px;
    margin:80px auto;
    background-image:url('/panel_jaune_stylise.png');
    background-size:100% 100%;
    background-repeat:no-repeat;
    position:relative;
    
}

.panel-content {
    position:absolute;
    top:190px;
    left:80px;
    right:80px;
    bottom:60px;
    overflow-y:auto;

    display:flex;
    flex-direction:column;
    gap:18px;
}

.msg {
    background: rgba(0,0,0,0.55);          /* PLUS SOMBRE */
    padding:12px 14px;
    border-radius:12px;
    border:1px solid rgba(0,0,0,0.6);      /* contour noir */
    box-shadow:
        inset 0 1px 2px rgba(255,255,255,0.15),
        0 2px 6px rgba(0,0,0,0.5);
}


.create-box {
    padding:16px;
    border-radius:16px;
    background: rgba(0,0,0,0.50);          /* PLUS SOMBRE */
    border:1px solid rgba(0,0,0,0.6);
    box-shadow:
        inset 0 1px 3px rgba(255,255,255,0.12),
        0 3px 8px rgba(0,0,0,0.6);
}


.create-box form {
    display:flex;
    gap:10px;
    align-items:center;
}

.create-box input {
    flex:1;
    padding:10px;
    border-radius:10px;
    border:none;
}

.create-box button {
    padding:10px 14px;
    border-radius:10px;
    border:none;
    cursor:pointer;
    background:#4a2a50;
    color:white;
}
.create-box button:hover { background:#5e3466; }

.universe-list {
    background: rgba(0,0,0,0.50);          /* PLUS SOMBRE */
    border-radius:16px;
    padding:16px;
    border:1px solid rgba(0,0,0,0.6);
    box-shadow:
        inset 0 1px 3px rgba(255,255,255,0.12),
        0 3px 8px rgba(0,0,0,0.6);
}


.universe-item {
    display:flex;
    justify-content:space-between;
    align-items:center;
    padding:10px;
    border-bottom:1px solid rgba(255,255,255,0.15);
}
.universe-item:last-child { border-bottom:none; }

.universe-item a {
    color:#90EE90;
    text-decoration:none;
    font-weight:bold;
}
.universe-item a:hover { text-decoration:underline; }

.delete-btn {
    padding:8px 12px;
    border-radius:8px;
    border:none;
    cursor:pointer;
    background:#8a2a2a;
    color:white;
}
.delete-btn:hover { background:#a83434; }

.small {
    opacity:0.85;
    font-size:0.95em;
}
</style>
</head>

<body>

<a href="/cgi-bin/index.py" class="back-btn" title="Retour"></a>

<div class="panel">
  <div class="panel-content">

""")

if msg:
    print('<div class="msg">' + msg + "</div>")

# bloc creation
disabled = "disabled" if len(universes) >= 3 else ""
placeholder = "Nom de l'univers (max 3)" if len(universes) < 3 else "Max 3 univers atteints"
print(f"""
    <div class="create-box">
      <form method="get" action="/cgi-bin/create_stat_object.py">
        <input type="hidden" name="action" value="create">
        <input type="text" name="new_name" placeholder="{placeholder}" {disabled}>
        <button type="submit" {disabled}>Créer un univers</button>
      </form>
      <div class="small">Un univers statistique permet de créer des objets fictifs sans modifier la BDD.</div>
    </div>
""")

# liste univers
print('<div class="universe-list">')
if not universes:
    print("<div>Aucun univers créé pour le moment.</div>")
else:
    for u, uid in universes:
        uid_encoded = urllib.parse.quote(uid)
        print(f"""
        <div class="universe-item">
          <div>
            <a href="/cgi-bin/univers_dashboard.py?uid={uid_encoded}">{u}</a>
            <div class="small">ID: {uid}</div>
          </div>
          <div>
            <form method="get" action="/cgi-bin/create_stat_object.py" style="display:inline;">
                <input type="hidden" name="uid_to_delete" value="{uid_encoded}">
                <input type="hidden" name="action" value="delete">
                <button type="submit" class="delete-btn" onclick="return confirm('Êtes-vous sûr de vouloir supprimer cet univers ?')">Supprimer</button>
            </form>
          </div>
        </div>
        """)

print("</div>")

print("""
  </div>
</div>

</body>
</html>
""")