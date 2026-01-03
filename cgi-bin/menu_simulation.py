#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import urllib.parse
import html

print("Content-Type: text/html; charset=utf-8\n")

UNIVERSE_DIR = "cgi-bin/universes/"

def get_param(name, default=""):
    qs = os.environ.get("QUERY_STRING", "")
    params = urllib.parse.parse_qs(qs, keep_blank_values=True)
    return params.get(name, [default])[0]

def esc(s):
    return html.escape("" if s is None else str(s))

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

uid = get_param("uid", "").strip()
universe_name = get_universe_name(uid)

back_href = f"/cgi-bin/univers_dashboard.py?uid={urllib.parse.quote(uid)}"

# IMPORTANT: si sim_calc_page.py est dans cgi-bin/ (a plat)
calc_href = f"/cgi-bin/sim_calc_page.py?uid={urllib.parse.quote(uid)}"

html_output = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Simulation - {esc(universe_name)}</title>

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
    background: url('/fond_filtre_pannel.png') no-repeat center/100% 100%;
    padding: 50px;
    border-radius: 20px;
    min-height: 520px;
}}

h1 {{
    text-align: center;
    margin: 0 0 6px 0;
}}

.sub {{
    text-align: center;
    color: rgba(255,255,255,0.8);
    margin-bottom: 30px;
}}

.grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 18px;
}}

.card {{
    background: rgba(0,0,0,0.55);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 16px;
    padding: 18px;
}}

.card h2 {{
    margin: 0 0 8px 0;
    font-size: 18px;
    color: #FFD86A;
}}

.card p {{
    margin: 0 0 14px 0;
    color: rgba(255,255,255,0.85);
    font-size: 13px;
    line-height: 1.35;
}}

.btn {{
    display: inline-block;
    text-decoration: none;
    padding: 10px 14px;
    border-radius: 10px;
    font-weight: bold;
    background: rgba(120,80,160,0.9);
    color: white;
}}

.btn:active {{
    transform: translateY(1px);
}}

.btn-disabled {{
    display: inline-block;
    padding: 10px 14px;
    border-radius: 10px;
    font-weight: bold;
    background: rgba(120,120,120,0.35);
    color: rgba(255,255,255,0.55);
    border: 1px solid rgba(255,255,255,0.08);
    cursor: not-allowed;
}}

.small {{
    font-size: 12px;
    color: rgba(255,255,255,0.7);
    margin-top: 10px;
}}
</style>
</head>

<body>

<a class="back-btn" href="{esc(back_href)}">
    <img src="/back_btn_jaune.png" alt="Retour">
</a>

<div class="panel">
    <h1>Menu Simulation</h1>
    <div class="sub">
        Univers : <b>{esc(universe_name)}</b><br>
        <span style="font-size:12px;opacity:0.7">uid : {esc(uid)}</span>
    </div>

    <div class="grid">
        <div class="card">
            <h2>Simulation par calcul (CALC)</h2>
            <p>
                Simulation deterministe basee sur les prix, quantites et coefficients.
                Calcule un total moyen, min/max et une projection a N annees.
            </p>
            <a class="btn" href="{esc(calc_href)}">Lancer</a>
            <div class="small">Simulation de reference.</div>
        </div>

        <div class="card">
            <h2>Simulation Monte Carlo</h2>
            <p>
                Simulation probabiliste par tirages aleatoires entre min/max.
                Permet d evaluer le risque et l incertitude.
            </p>
            <span class="btn-disabled">Bientot</span>
        </div>

        <div class="card">
            <h2>Simulation par scenarios</h2>
            <p>
                Application de facteurs globaux (inflation, crise, optimisme)
                pour comparer plusieurs futurs possibles.
            </p>
            <span class="btn-disabled">Bientot</span>
        </div>

        <div class="card">
            <h2>Comparateur d univers</h2>
            <p>
                Compare plusieurs univers sur leurs couts, projections
                et repartitions.
            </p>
            <span class="btn-disabled">Bientot</span>
        </div>
    </div>
</div>

</body>
</html>
"""

print(html_output)
