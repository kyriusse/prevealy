#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import urllib.parse
import difflib
import html

print("Content-Type: text/html; charset=utf-8\n")

UNIVERSE_DIR = "cgi-bin/universes/"

# ---------------------------
# Utils
# ---------------------------
def get_param(name, default=""):
    qs = os.environ.get("QUERY_STRING", "")
    params = urllib.parse.parse_qs(qs, keep_blank_values=True)
    return params.get(name, [default])[0]

def universe_path(universe_id):
    safe = "".join([c for c in universe_id if c.isalnum() or c in ("-", "_")])
    return os.path.join(UNIVERSE_DIR, f"universe_{safe}.db")

def esc(s):
    return html.escape("" if s is None else str(s))

def ensure_column(db_path, table, col_name, col_def_sql):
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(f"PRAGMA table_info({table})")
        cols = [r[1] for r in cur.fetchall()]
        if col_name not in cols:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def_sql}")
            conn.commit()
        return True
    except Exception:
        return False
    finally:
        if conn is not None:
            conn.close()

def ensure_id_stat_filled(db_path):
    """
    Ensure id_stat exists and is filled for older rows.
    We use rowid to populate missing id_stat values.
    """
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        cur.execute("PRAGMA table_info(stat_objects)")
        cols = [r[1] for r in cur.fetchall()]
        if "id_stat" not in cols:
            cur.execute("ALTER TABLE stat_objects ADD COLUMN id_stat INTEGER")
            conn.commit()

        # fill missing id_stat using rowid
        cur.execute("UPDATE stat_objects SET id_stat = rowid WHERE id_stat IS NULL")
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        if conn is not None:
            conn.close()

def get_columns(db_path):
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(stat_objects)")
        cols = [r[1] for r in cur.fetchall()]
        return cols
    except Exception:
        return []
    finally:
        if conn is not None:
            conn.close()

def find_name_col(columns):
    for c in columns:
        cl = c.lower()
        if ("objet" in cl) or ("nom" in cl) or ("name" in cl) or ("designation" in cl):
            return c
    return columns[1] if len(columns) > 1 else (columns[0] if columns else None)

def find_type_col(columns):
    for c in columns:
        if c.lower() in ("type", "types"):
            return c
    for c in columns:
        if "type" in c.lower():
            return c
    return None

def find_family_col(columns):
    for c in columns:
        if "famil" in c.lower():
            return c
    return None

def find_price_col(columns):
    for c in columns:
        cl = c.lower()
        if ("prix" in cl) or ("price" in cl):
            return c
    return None

# ---------------------------
# Search (now includes EVERYTHING, including created objects and linked ones)
# We use rowid as the selection key (reliable).
# ---------------------------
def search_objects(db_path, search_term):
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        cols = get_columns(db_path)
        if not cols:
            conn.close()
            return []

        name_col = find_name_col(cols)
        if not name_col:
            conn.close()
            return []

        # Include all rows (no liaison filter)
        cur.execute(f"SELECT rowid, [{name_col}] FROM stat_objects")
        all_objects = cur.fetchall()
        conn.close()

        if not search_term or len(search_term.strip()) < 2:
            return []

        st = search_term.lower().strip()
        matches = []
        for rid, oname in all_objects:
            if oname is None:
                continue
            ratio = difflib.SequenceMatcher(None, st, str(oname).lower()).ratio()
            if ratio > 0.3:
                matches.append((rid, oname, ratio))

        matches.sort(key=lambda x: x[2], reverse=True)
        return matches[:8]
    except Exception:
        return []

# ---------------------------
# Counts parsing (compact)
# Format: "rowid:qty,rowid:qty"
# Example: "12:3,7:1"
# ---------------------------
def parse_counts(compact_str):
    counts = {}
    if not compact_str:
        return counts
    parts = [p.strip() for p in compact_str.split(",") if p.strip()]
    for p in parts:
        if ":" not in p:
            continue
        a, b = p.split(":", 1)
        try:
            rid = int(a.strip())
            cnt = int(b.strip())
        except Exception:
            continue
        if cnt < 1:
            cnt = 1
        counts[rid] = cnt
    return counts

# ---------------------------
# Compute aggregated row for ALL columns
# Rules:
# - method fusion: sum numeric fields (with qty), otherwise "?"
# - method moyenne: weighted avg numeric fields (with qty), otherwise "?"
# - if no numeric values for a field: "?"
# ---------------------------
def compute_aggregates(db_path, selected_counts, method):
    """
    Returns dict: col_name -> value (float for numeric, "?" for impossible)
    Also returns cols list.
    """
    cols = get_columns(db_path)
    if not cols:
        return {}, []

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # fetch selected rows by rowid
    rowids = list(selected_counts.keys())
    if not rowids:
        conn.close()
        return {}, cols

    placeholders = ",".join(["?"] * len(rowids))
    cur.execute(f"SELECT rowid, * FROM stat_objects WHERE rowid IN ({placeholders})", rowids)
    rows = cur.fetchall()
    conn.close()

    # rows schema: (rowid, col0, col1, col2, ...)
    # Map rowid -> list(values)
    data = {}
    for r in rows:
        rid = r[0]
        data[rid] = list(r[1:])

    # Determine numeric aggregation per column index
    # For each col i, scan values of selected rows; if any int/float => numeric column
    agg = {}

    for i, col in enumerate(cols):
        # gather numeric values with weights
        nums = []
        weights = []
        for rid, w in selected_counts.items():
            if rid not in data:
                continue
            v = data[rid][i] if i < len(data[rid]) else None
            if isinstance(v, (int, float)):
                nums.append(float(v) * float(w))
                weights.append(int(w))

        if not nums:
            agg[col] = "?"
            continue

        total_sum = sum(nums)
        total_w = sum(weights)

        if method == "fusion":
            agg[col] = total_sum
        else:
            agg[col] = (total_sum / float(total_w)) if total_w > 0 else "?"

    return agg, cols

def next_id_stat(db_path):
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(id_stat), 0) + 1 FROM stat_objects")
        v = cur.fetchone()[0]
        return int(v)
    except Exception:
        return None
    finally:
        if conn is not None:
            conn.close()

# ---------------------------
# Create object stat (insert full row with computed columns)
# - Ensures: liaison column exists, id_stat exists and filled
# - Sets:
#   name_col = name
#   type_col = "Fusion" or "Moyenne ponderee"
#   family_col = "Objet statistique"
#   liaison = "null"
#   id_stat = next integer
# - For other cols: computed numeric or "?"
# ---------------------------
def create_stat_object(db_path, name, compact_counts, method):
    counts = parse_counts(compact_counts)
    if not counts:
        return False, "Aucun objet selectionne."

    cols = get_columns(db_path)
    if not cols:
        return False, "Table stat_objects introuvable."

    name_col = find_name_col(cols)
    type_col = find_type_col(cols)
    family_col = find_family_col(cols)
    price_col = find_price_col(cols)

    if not name_col:
        return False, "Colonne nom introuvable."

    agg, cols = compute_aggregates(db_path, counts, method)

    # Ensure mandatory meta columns exist
    ensure_column(db_path, "stat_objects", "liaison", "TEXT DEFAULT 'null'")
    ensure_id_stat_filled(db_path)

    # Override / set some fields
    agg[name_col] = name
    agg["liaison"] = "null"

    # id_stat
    new_id = next_id_stat(db_path)
    if new_id is not None:
        agg["id_stat"] = new_id

    # type / family
    if type_col:
        if method == "fusion":
            agg[type_col] = "Fusion"
        else:
            agg[type_col] = "Moyenne ponderee"
    if family_col:
        agg[family_col] = "Objet statistique"

    # If price column exists and was "?" but we had numeric elsewhere, keep computed behavior.
    # If price_col exists and method fusion => sum, moyenne => avg (already done by compute_aggregates)
    if price_col and price_col not in agg:
        agg[price_col] = "?"

    # Build INSERT: include all columns we can write (excluding the original first PK if any)
    # We will insert only columns that exist in table.
    insert_cols = []
    insert_vals = []
    for c in cols:
        # skip original first column if you want (unknown PK). But we keep it: if it's not numeric we will set "?"
        # safer: do not touch first column if it is an original PK used by your dataset
        # => skip cols[0]
        pass

    # IMPORTANT: avoid overwriting the dataset's original "id" if it exists as cols[0]
    # We insert all columns EXCEPT cols[0] (original id/Objet etc).
    # This keeps SQLite assigning NULL/default to that column if allowed.
    if len(cols) >= 1:
        cols_to_insert = cols[1:]
    else:
        cols_to_insert = cols[:]

    for c in cols_to_insert:
        insert_cols.append(c)
        v = agg.get(c, "?")
        insert_vals.append(v)

    # Ensure liaison/id_stat included if they exist and are not in cols_to_insert
    # (in case liaison/id_stat were at index 0 for some reason)
    for extra in ("liaison", "id_stat"):
        if extra in cols and extra not in cols_to_insert:
            insert_cols.append(extra)
            insert_vals.append(agg.get(extra, "?"))

    cols_sql = ",".join([f"[{c}]" for c in insert_cols])
    ph = ",".join(["?"] * len(insert_vals))

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(f"INSERT INTO stat_objects ({cols_sql}) VALUES ({ph})", insert_vals)

        # If fusion: mark used objects as linked (optional; you had that behavior)
        if method == "fusion":
            # only if column exists
            if "liaison" in cols:
                cur.execute(
                    f"UPDATE stat_objects SET liaison = ? WHERE rowid IN ({','.join(['?']*len(counts))})",
                    [f"lie a {name}"] + list(counts.keys())
                )

        conn.commit()
        return True, "Objet cree avec succes !"
    except Exception as e:
        return False, f"Erreur: {e}"
    finally:
        if conn is not None:
            conn.close()

# ---------------------------
# Main
# ---------------------------
universe_id = get_param("uid", "")
action = get_param("action", "")

db_path = universe_path(universe_id)

# ensure columns
if universe_id:
    ensure_column(db_path, "stat_objects", "liaison", "TEXT DEFAULT 'null'")
    ensure_id_stat_filled(db_path)

msg = ""
msg_class = "ok"

if action == "search":
    term = get_param("search", "")
    results = search_objects(db_path, term)
    if results:
        for rid, oname, _ in results:
            safe_name = str(oname).replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')
            print(f"<div class='suggest-item' onclick=\"addObject({rid}, '{safe_name}')\">{esc(oname)}</div>")
    else:
        print("<div class='suggest-empty'>Aucune proposition</div>")
    raise SystemExit

if action == "create":
    new_name = get_param("name", "").strip()
    counts_compact = get_param("object_counts", "").strip()
    method = get_param("method", "moyenne").strip()

    if new_name and counts_compact:
        ok, msg = create_stat_object(db_path, new_name, counts_compact, method)
        msg_class = "ok" if ok else "err"
    else:
        msg = "Nom ou liste d'objets manquants."
        msg_class = "err"

# Back target (adjust if needed)
back_href = f"/cgi-bin/univers_dashboard.py?uid={urllib.parse.quote(universe_id)}"

# ---------------------------
# HTML
# ---------------------------
print(f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Creation d'objet statistique</title>
<style>
body {{
    margin: 0;
    font-family: Arial, sans-serif;
    color: white;
    background-image: url('/create_stat_object.png');
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    min-height: 100vh;
}}

.back-btn {{
    position: fixed;
    top: 18px;
    left: 18px;
    width: 48px;
    height: 48px;
    z-index: 50;
}}
.back-btn img {{
    width: 48px;
    height: 48px;
    display: block;
}}

.panel {{
    width: 900px;
    margin: 60px auto;
    background: url('/fond_filtre_pannel.png') no-repeat center;
    background-size: 100% 100%;
    padding: 50px;
    border-radius: 20px;
}}

h1 {{ text-align: center; margin-top: 0; }}

label {{ display:block; margin: 15px 0 6px; font-weight: bold; }}

input[type=text] {{
    width: 100%;
    padding: 12px;
    border-radius: 6px;
    border: none;
    outline: none;
    font-size: 14px;
}}

#suggestions {{
    margin-top: 8px;
    background: rgba(0,0,0,0.55);
    border-radius: 10px;
    padding: 8px;
    min-height: 24px;
}}

.suggest-item {{
    padding: 8px 10px;
    border-radius: 8px;
    cursor: pointer;
}}
.suggest-item:hover {{
    background: rgba(255,255,255,0.08);
}}

.suggest-empty {{
    color: #bbb;
    font-size: 12px;
    padding: 6px 10px;
}}

.selected-box {{
    margin-top: 25px;
    padding: 18px;
    background: rgba(0,0,0,0.45);
    border-radius: 14px;
}}

.selected-item {{
    display:flex;
    justify-content: space-between;
    align-items:center;
    background: rgba(255,255,255,0.06);
    border-radius: 10px;
    padding: 10px 12px;
    margin-top: 10px;
}}

.left {{
    display:flex;
    align-items:center;
    gap: 10px;
}}

.badge {{
    display:inline-block;
    padding: 4px 8px;
    border-radius: 999px;
    background: rgba(255,255,255,0.12);
    font-size: 12px;
}}

.qty {{
    width: 76px;
    padding: 6px 8px;
    border-radius: 8px;
    border: none;
    outline: none;
}}

.btn-del {{
    background: #a83434;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    cursor:pointer;
}}

select {{
    width: 100%;
    padding: 12px;
    border-radius: 6px;
    border: none;
    outline: none;
}}

.btn-main {{
    margin-top: 18px;
    padding: 12px 18px;
    border-radius: 10px;
    border: none;
    cursor:pointer;
    background: rgba(120,80,160,0.9);
    color:white;
    font-weight:bold;
}}

.msg {{
    margin-top: 15px;
    padding: 10px;
    border-radius: 8px;
    text-align:center;
}}
.msg.ok {{ background: rgba(0,128,0,0.35); }}
.msg.err {{ background: rgba(128,0,0,0.35); }}
</style>

<script>
var selected = {{}};

function refreshHidden() {{
    var parts = [];
    for (var k in selected) {{
        if (!selected.hasOwnProperty(k)) continue;
        var v = parseInt(selected[k].count, 10);
        if (isNaN(v) || v < 1) v = 1;
        parts.push(k + ":" + v);
    }}
    document.getElementById("object_counts").value = parts.join(",");
}}

function renderSelected() {{
    var box = document.getElementById("selected_list");
    box.innerHTML = "";

    var keys = Object.keys(selected);
    if (keys.length === 0) {{
        box.innerHTML = "<div style='color:#bbb'>Aucun objet selectionne.</div>";
        refreshHidden();
        return;
    }}

    keys.sort(function(a,b){{ return parseInt(a,10) - parseInt(b,10); }});

    for (var i=0;i<keys.length;i++) {{
        var id = keys[i];
        var item = selected[id];

        var row = document.createElement("div");
        row.className = "selected-item";

        var left = document.createElement("div");
        left.className = "left";

        var name = document.createElement("div");
        name.innerHTML = "<b>" + item.name + "</b>";

        var badge = document.createElement("span");
        badge.className = "badge";
        badge.textContent = "x" + item.count;

        var qty = document.createElement("input");
        qty.type = "number";
        qty.min = "1";
        qty.className = "qty";
        qty.value = item.count;
        qty.onchange = (function(myId) {{
            return function() {{
                var v = parseInt(this.value, 10);
                if (isNaN(v) || v < 1) v = 1;
                selected[myId].count = v;
                renderSelected();
            }};
        }})(id);

        left.appendChild(name);
        left.appendChild(badge);
        left.appendChild(qty);

        var del = document.createElement("button");
        del.className = "btn-del";
        del.textContent = "Supprimer";
        del.onclick = (function(myId) {{
            return function() {{
                delete selected[myId];
                renderSelected();
            }};
        }})(id);

        row.appendChild(left);
        row.appendChild(del);

        box.appendChild(row);
    }}

    refreshHidden();
}}

function addObject(rowid, name) {{
    var id = String(rowid);
    if (selected[id]) {{
        selected[id].count = parseInt(selected[id].count, 10) + 1;
    }} else {{
        selected[id] = {{ name: name, count: 1 }};
    }}
    renderSelected();
}}

function doSearch() {{
    var q = document.getElementById("search").value;
    var xhr = new XMLHttpRequest();
    xhr.open("GET", "?uid={esc(universe_id)}&action=search&search=" + encodeURIComponent(q), true);
    xhr.onreadystatechange = function() {{
        if (xhr.readyState === 4 && xhr.status === 200) {{
            document.getElementById("suggestions").innerHTML = xhr.responseText;
        }}
    }};
    xhr.send();
}}

function init() {{
    renderSelected();
}}
</script>

</head>
<body onload="init()">

<a class="back-btn" href="{esc(back_href)}"><img src="/back_btn_jaune.png" alt="Retour"></a>

<div class="panel">
    <h1>Creation d'objet statistique</h1>

    <label>Nom de l'objet :</label>
    <input type="text" id="name" placeholder="Ex: Ecole, Bureau, etc.">

    <label>Rechercher des objets :</label>
    <input type="text" id="search" placeholder="Chercher un objet..." onkeyup="doSearch()">

    <div id="suggestions"></div>

    <div class="selected-box">
        <b>Objets selectionnes :</b>
        <div id="selected_list" style="margin-top:10px;"></div>
    </div>

    <label>Methode :</label>
    <select id="method">
        <option value="moyenne">Moyenne ponderee</option>
        <option value="fusion">Fusion (somme)</option>
    </select>

    <form method="GET" action="">
        <input type="hidden" name="uid" value="{esc(universe_id)}">
        <input type="hidden" name="action" value="create">
        <input type="hidden" name="name" id="hidden_name">
        <input type="hidden" name="method" id="hidden_method">
        <input type="hidden" name="object_counts" id="object_counts" value="">
        <button type="submit" class="btn-main" onclick="
            document.getElementById('hidden_name').value = document.getElementById('name').value;
            document.getElementById('hidden_method').value = document.getElementById('method').value;
            refreshHidden();
        ">Creer l'objet statistique</button>
    </form>

    {"<div class='msg " + esc(msg_class) + "'>" + esc(msg) + "</div>" if msg else ""}

    <div style="margin-top:20px; text-align:center;">
        <a href="/cgi-bin/liste_objets.py?uid={esc(universe_id)}" style="color:white; text-decoration:none; font-weight:bold;">Liste des objets crees</a>
    </div>
</div>

</body>
</html>
""")
