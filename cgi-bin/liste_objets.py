#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import urllib.parse
import html

print("Content-Type: text/html; charset=utf-8\n")

UNIVERSE_DIR = "cgi-bin/universes/"

def get_param(name, default=""):
    qs = os.environ.get("QUERY_STRING", "")
    params = urllib.parse.parse_qs(qs, keep_blank_values=True)
    return params.get(name, [default])[0]

def universe_path(universe_id):
    safe = "".join([c for c in universe_id if c.isalnum() or c in ("-", "_")])
    return os.path.join(UNIVERSE_DIR, f"universe_{safe}.db")

def get_universe_name(universe_id):
    try:
        names_file = os.path.join(UNIVERSE_DIR, "univers_names.txt")
        if os.path.exists(names_file):
            with open(names_file, "r", encoding="utf-8") as f:
                for line in f:
                    if "," in line:
                        uid, name = line.strip().split(",", 1)
                        if uid == universe_id:
                            return name
    except Exception:
        pass
    return "Nom inconnu"

def get_table_info(u_path, table_name):
    conn = sqlite3.connect(u_path)
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name})")
    info = cur.fetchall()
    conn.close()
    return info

def get_column_names(u_path, table_name):
    try:
        info = get_table_info(u_path, table_name)
        return [col[1] for col in info]
    except Exception:
        return []

def smart_average(row, start_index=3):
    values = [v for v in row[start_index:] if v is not None and isinstance(v, (int, float))]
    if not values:
        return 0.0
    return sum(values) / len(values)

def find_column(columns, candidates):
    cols_lower = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand.lower() in cols_lower:
            return cols_lower[cand.lower()]
    return None

def find_name_column(columns):
    for c in columns:
        cl = c.lower()
        if "objet" in cl or "nom" in cl or "name" in cl:
            return c
    return columns[1] if len(columns) > 1 else columns[0]

def find_type_column(columns):
    for c in columns:
        cl = c.lower()
        if cl in ("type", "types"):
            return c
    # parfois "Type_" etc
    for c in columns:
        if "type" in c.lower():
            return c
    return None

def find_price_column(columns):
    for c in columns:
        cl = c.lower()
        if "prix" in cl or "price" in cl:
            return c
    return None

def get_created_objects(universe_id):
    u_path = universe_path(universe_id)
    try:
        columns = get_column_names(u_path, "stat_objects")
        if not columns:
            return []

        type_col = find_type_column(columns)
        name_col = find_name_column(columns)

        # On recupere rowid pour supprimer proprement
        conn = sqlite3.connect(u_path)
        cur = conn.cursor()

        if type_col:
            cur.execute(
                f"""
                SELECT rowid, *
                FROM stat_objects
                WHERE [{type_col}] IN ('Fusion', 'Moyenne ponderee', 'Moyenne pondérée')
                ORDER BY rowid DESC
                """
            )
        else:
            # fallback: liste tout
            cur.execute("SELECT rowid, * FROM stat_objects ORDER BY rowid DESC")

        rows = cur.fetchall()
        conn.close()

        price_col = find_price_column(columns)
        # columns correspond a "*" (sans rowid)
        # row schema: (rowid, col0, col1, col2, ...)
        processed = []
        for r in rows:
            rid = r[0]
            row = list(r[1:])  # les vraies colonnes

            # Trouver index name/type dans row
            try:
                name_idx = columns.index(name_col)
            except Exception:
                name_idx = 0
            try:
                type_idx = columns.index(type_col) if type_col else 2
            except Exception:
                type_idx = 2

            obj_name = row[name_idx] if name_idx < len(row) else "Sans nom"
            obj_type = row[type_idx] if type_idx < len(row) else ""

            # moyenne auto sur les colonnes a partir de l index 3 (comme ton code)
            avg_value = smart_average(row, start_index=3)

            display_price = None
            if price_col:
                try:
                    price_idx = columns.index(price_col)
                    val = row[price_idx] if price_idx < len(row) else None
                    if isinstance(val, (int, float)):
                        display_price = float(val)
                except Exception:
                    display_price = None

            if display_price is None:
                display_price = float(avg_value)

            processed.append((rid, obj_name, obj_type, display_price))

        return processed

    except Exception:
        return []

def delete_object(universe_id, rowid_value):
    u_path = universe_path(universe_id)
    rowid_value = str(rowid_value).strip()
    try:
        rid = int(rowid_value)
    except Exception:
        return False

    try:
        columns = get_column_names(u_path, "stat_objects")
        if not columns:
            return False

        name_col = find_name_column(columns)

        conn = sqlite3.connect(u_path)
        cur = conn.cursor()

        # Recuperer le nom AVANT suppression (pour nettoyer liaison)
        cur.execute(f"SELECT [{name_col}] FROM stat_objects WHERE rowid = ?", (rid,))
        res = cur.fetchone()
        if not res:
            conn.close()
            return False

        obj_name = res[0]

        # Nettoyage liaison (si colonne existe)
        liaison_col = None
        for c in columns:
            if c.lower() == "liaison":
                liaison_col = c
                break

        if liaison_col:
            # Supporter plusieurs formats eventuels
            candidates = [
                f"lie a {obj_name}",
                f"lié à {obj_name}",
                f"lie a {str(obj_name)}",
                f"lié à {str(obj_name)}",
            ]
            cur.execute(
                f"""
                UPDATE stat_objects
                SET [{liaison_col}] = 'null'
                WHERE [{liaison_col}] IN ({",".join(["?"] * len(candidates))})
                """,
                tuple(candidates),
            )

        # Suppression par rowid (fiable)
        cur.execute("DELETE FROM stat_objects WHERE rowid = ?", (rid,))
        conn.commit()
        conn.close()
        return True

    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return False

# --- Logique de l application ---
universe_id = get_param("uid", "")
action = get_param("action", "")
object_id = get_param("object_id", "")

msg, msg_class = "", ""
if action == "delete" and object_id:
    if delete_object(universe_id, object_id):
        msg, msg_class = "Objet supprime avec succes !", "success"
    else:
        msg, msg_class = "Erreur lors de la suppression.", "error"

universe_name = get_universe_name(universe_id)
created_objects = get_created_objects(universe_id)

# --- Sortie HTML ---
def esc(s):
    return html.escape("" if s is None else str(s))

html_output = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <title>Liste des Objets - {esc(universe_name)}</title>
    <style>
        body {{ margin: 0; font-family: sans-serif; color: white; background: url('/create_stat_object.png') center/cover fixed; }}
        .panel {{ width: 850px; margin: 50px auto; background: url('/fond_filtre_pannel.png') no-repeat center/100% 100%; padding: 40px; min-height: 500px; }}
        h1 {{ text-align: center; }}
        .back-btn {{ position: fixed; top: 20px; left: 20px; width: 45px; height: 45px; background: rgba(74, 42, 80, 0.9); border-radius: 50%; color: white; text-decoration: none; display: flex; align-items: center; justify-content: center; font-size: 20px; }}
        .message {{ padding: 10px; margin-bottom: 20px; border-radius: 4px; text-align: center; background: rgba(0, 128, 0, 0.4); }}
        .message.error {{ background: rgba(128, 0, 0, 0.4); }}
        .object-item {{ display: flex; justify-content: space-between; background: rgba(0,0,0,0.7); margin: 10px 0; padding: 20px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1); }}
        .obj-title {{ font-size: 1.2em; font-weight: bold; color: #FFD86A; }}
        .obj-type {{ font-size: 0.9em; color: #87CEEB; }}
        .obj-val {{ color: #90EE90; margin-top: 5px; font-weight: bold; }}
        .auto-info {{ font-size: 0.7em; background: #555; padding: 2px 6px; border-radius: 4px; margin-left: 10px; }}
        .delete-btn {{ background: #a83434; color: white; text-decoration: none; padding: 10px 20px; border-radius: 5px; align-self: center; }}
    </style>
</head>
<body>
    <a href="/cgi-bin/personnalisation_objet.py?uid={esc(universe_id)}" class="back-btn">←</a>
    <div class="panel">
        <h1>Objets crees : {esc(universe_name)}</h1>
        {f'<div class="message {esc(msg_class)}">{esc(msg)}</div>' if msg else ''}

        <div class="list">
            {"<p style='text-align:center'>Aucun objet dans cet univers.</p>" if not created_objects else ""}
            {''.join([f'''
            <div class="object-item">
                <div>
                    <div class="obj-title">{esc(obj[1])}</div>
                    <div class="obj-type">Type : {esc(obj[2])}</div>
                    <div class="obj-val">Valeur : {float(obj[3]):.2f} <span class="auto-info">Moyenne Auto</span></div>
                </div>
                <a href="?uid={esc(universe_id)}&action=delete&object_id={urllib.parse.quote(str(obj[0]))}" class="delete-btn" onclick="return confirm('Supprimer cet objet ?')">Supprimer</a>
            </div>
            ''' for obj in created_objects])}
        </div>
    </div>
</body>
</html>"""

print(html_output)
