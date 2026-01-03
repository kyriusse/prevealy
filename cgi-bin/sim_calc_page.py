#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import urllib.parse
import html

from sim_calc import run_simulation_calc

print("Content-Type: text/html; charset=utf-8\n")

UNIVERSE_DIR = "cgi-bin/universes/"

def get_param(name, default=""):
    qs = os.environ.get("QUERY_STRING", "")
    params = urllib.parse.parse_qs(qs, keep_blank_values=True)
    return params.get(name, [default])[0]

def esc(s):
    return html.escape("" if s is None else str(s))

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

def get_stat_objects_id_col(conn):
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(stat_objects)")
    cols = cur.fetchall()
    if not cols:
        return None
    return cols[0][1]  # first column name

def ensure_universe_items_table(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Create target table (new schema)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS universe_items (
            obj_id INTEGER NOT NULL,
            qty INTEGER NOT NULL DEFAULT 1
        )
    """)

    # If old schema exists (rowid_objet), migrate once
    cur.execute("PRAGMA table_info(universe_items)")
    cols = [r[1] for r in cur.fetchall()]

    if "rowid_objet" in cols and "obj_id" not in cols:
        # migrate: create new table, copy, swap
        cur.execute("""
            CREATE TABLE IF NOT EXISTS universe_items_new (
                obj_id INTEGER NOT NULL,
                qty INTEGER NOT NULL DEFAULT 1
            )
        """)
        # Copy as-is (rowid_objet -> obj_id). Better than losing data.
        cur.execute("INSERT INTO universe_items_new(obj_id, qty) SELECT rowid_objet, qty FROM universe_items")
        cur.execute("DROP TABLE universe_items")
        cur.execute("ALTER TABLE universe_items_new RENAME TO universe_items")

    conn.commit()
    conn.close()

def load_basket(db_path):
    basket = {}

    if not os.path.exists(db_path):
        return basket, "Fichier univers introuvable"

    ensure_universe_items_table(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # sanity: stat_objects must exist
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stat_objects'")
    if not cur.fetchone():
        conn.close()
        return basket, "Table stat_objects introuvable dans cet univers"

    cur.execute("SELECT obj_id, qty FROM universe_items")
    rows = cur.fetchall()
    conn.close()

    for oid, qty in rows:
        try:
            oid = int(oid)
            qty = int(qty)
        except Exception:
            continue
        if qty > 0:
            basket[oid] = basket.get(oid, 0) + qty

    return basket, None

uid = get_param("uid", "").strip()
years = get_param("years", "10").strip()

try:
    years = int(years)
    if years < 1:
        years = 10
except Exception:
    years = 10

if not uid:
    print("<h1>Erreur : univers non specifie</h1>")
    raise SystemExit

db_path = universe_path(uid)
universe_name = get_universe_name(uid)

basket, basket_err = load_basket(db_path)

result = None
if not basket_err:
    # basket: {obj_id: qty}
    result = run_simulation_calc(db_path, basket, years)

back_href = f"/cgi-bin/menu_simulation.py?uid={urllib.parse.quote(uid)}"

def fmt(v):
    try:
        return f"{float(v):.2f}"
    except Exception:
        return ""

def build_details_rows(details):
    out = []
    for d in details:
        coef = d.get("coef")
        if coef is None:
            coef_str = ""
        else:
            try:
                coef_str = f"{float(coef):.3f}"
            except Exception:
                coef_str = esc(coef)

        out.append(
            "<tr>"
            f"<td class='name'>{esc(d.get('name'))}</td>"
            f"<td>{esc(d.get('qty',''))}</td>"
            f"<td>{fmt(d.get('mean'))}</td>"
            f"<td>{fmt(d.get('min'))}</td>"
            f"<td>{fmt(d.get('max'))}</td>"
            f"<td>{coef_str}</td>"
            f"<td>{esc(d.get('status',''))}</td>"
            "</tr>"
        )
    return "".join(out)

details_html = ""
warnings_html = ""
sections_html = ""

if (not basket_err) and result:
    details_html = build_details_rows(result.get("details", []))

    if result.get("warnings"):
        warnings_html = (
            "<div class='section warn'>"
            "<h3>Warnings</h3><ul>"
            + "".join([f"<li>{esc(w)}</li>" for w in result["warnings"]])
            + "</ul></div>"
        )

    sections_html = f"""
    <div class="section">
        <h2>Totaux actuels</h2>
        <table>
            <tr><th></th><th>Moyen</th><th>Min</th><th>Max</th></tr>
            <tr>
                <td class="name">Total</td>
                <td>{fmt(result["total"]["mean"])}</td>
                <td>{fmt(result["total"]["min"])}</td>
                <td>{fmt(result["total"]["max"])}</td>
            </tr>
        </table>
    </div>

    <div class="section">
        <h2>Projection a {years} ans</h2>
        <table>
            <tr><th></th><th>Moyen</th><th>Min</th><th>Max</th></tr>
            <tr>
                <td class="name">Projection</td>
                <td>{fmt(result["projection"]["mean"])}</td>
                <td>{fmt(result["projection"]["min"])}</td>
                <td>{fmt(result["projection"]["max"])}</td>
            </tr>
        </table>
    </div>

    <div class="section">
        <h2>Detail par objet</h2>
        <table>
            <tr>
                <th style="text-align:left;">Objet</th>
                <th>Qty</th>
                <th>Moyen</th>
                <th>Min</th>
                <th>Max</th>
                <th>Coef</th>
                <th>Status</th>
            </tr>
            {details_html}
        </table>
    </div>

    {warnings_html}
    """

print(f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Simulation par calcul - {esc(universe_name)}</title>

<style>
body {{
    margin: 0;
    font-family: Arial, sans-serif;
    color: white;
    background: url('/create_stat_object.png') center/cover fixed;
    min-height: 100vh;
}}

.back-btn {{
    position: fixed;
    top: 18px;
    left: 18px;
    width: 48px;
    height: 48px;
}}
.back-btn img {{
    width: 48px;
    height: 48px;
}}

.panel {{
    width: 980px;
    margin: 60px auto;
    background: url('/fond_filtre_pannel.png') no-repeat center/100% 100%;
    padding: 50px;
    border-radius: 20px;
}}

h1 {{
    text-align: center;
    margin-top: 0;
    color: #FFD86A;
}}

.section {{
    margin-top: 25px;
    background: rgba(0,0,0,0.45);
    padding: 20px;
    border-radius: 14px;
}}

table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
}}

th, td {{
    padding: 8px 10px;
    border-bottom: 1px solid rgba(255,255,255,0.15);
    text-align: right;
}}

th {{
    color: #FFD86A;
}}

td.name {{
    text-align: left;
}}

.warn {{
    background: rgba(138,42,42,0.45);
    padding: 10px;
    border-radius: 10px;
    margin-top: 10px;
}}

button {{
    padding: 8px 14px;
    border-radius: 10px;
    background: #4a2a50;
    color: white;
    border: none;
    cursor: pointer;
    font-weight: bold;
}}

input {{
    padding: 6px 10px;
    border-radius: 6px;
    border: none;
}}
</style>
</head>

<body>

<a class="back-btn" href="{esc(back_href)}">
    <img src="/back_btn_jaune.png" alt="Retour">
</a>

<div class="panel">
    <h1>Simulation par calcul</h1>
    <div style="text-align:center; opacity:0.85;">
        Univers : <b>{esc(universe_name)}</b> (uid {esc(uid)})
    </div>

    <form method="get" style="text-align:center; margin-top:15px;">
        <input type="hidden" name="uid" value="{esc(uid)}">
        Horizon (annees) :
        <input type="number" name="years" value="{years}" min="1" max="50">
        <button type="submit">Relancer</button>
    </form>

    {"<div class='warn'>" + esc(basket_err) + "</div>" if basket_err else ""}
    {"<div class='warn'>Aucun objet dans le panier (table universe_items vide)</div>" if (not basket_err and not basket) else ""}

    {sections_html}

</div>

</body>
</html>
""")
