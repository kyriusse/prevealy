#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sqlite3
import html

print("Content-type: text/html; charset=utf-8\n")

# Chemin de la base de données principale
CHEMIN_BDD = "cgi-bin/objets.db"

def echapper_html(texte):
    """Échappe le texte pour un affichage HTML sûr."""
    return html.escape("" if texte is None else str(texte))

def valeurs_distinctes(colonne):
    """Retourne les valeurs distinctes d'une colonne de la table Prix_Objets."""
    try:
        connexion = sqlite3.connect(CHEMIN_BDD)
        curseur = connexion.cursor()
        curseur.execute(
            f"SELECT DISTINCT {colonne} FROM Prix_Objets "
            f"WHERE {colonne} IS NOT NULL AND TRIM({colonne}) != '' "
            f"ORDER BY {colonne} COLLATE NOCASE"
        )
        valeurs = [ligne[0] for ligne in curseur.fetchall()]
        connexion.close()
        return valeurs
    except Exception:
        return []

# Chargement des valeurs pour les listes déroulantes
familles = valeurs_distinctes("Famille")
types_objet = valeurs_distinctes("Type")
speculations = valeurs_distinctes("Speculation")

options_famille = "\n".join(
    [f'<option value="{echapper_html(valeur)}">{echapper_html(valeur)}</option>' for valeur in familles]
)
options_type = "\n".join(
    [f'<option value="{echapper_html(valeur)}">{echapper_html(valeur)}</option>' for valeur in types_objet]
)
options_speculation = "\n".join(
    [f'<option value="{echapper_html(valeur)}">{echapper_html(valeur)}</option>' for valeur in speculations]
)

print(f"""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Privealy Economy</title>

<style>
body {{
    background-image:
        radial-gradient(circle at 35% 25%, rgba(255,255,255,0.14), transparent 42%),
        radial-gradient(circle at 70% 30%, rgba(255,255,255,0.10), transparent 48%),
        radial-gradient(circle at 50% 85%, rgba(255,255,255,0.08), transparent 55%),
        linear-gradient(180deg, rgba(0,0,0,0.20), rgba(0,0,0,0.72)),
        url('/fond.png');
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;

    margin: 0;
    padding: 0;
    font-family: Arial, sans-serif;
    color: #fff;
    height: 100vh;

    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    align-items: center;
}}

    /* ===== BOUTON RETOUR ===== */
.back_btn_gris {{
    position: fixed;
    top: 20px;
    left: 20px;
    width: 64px;
    height: 64px;
    background-image: url('/back_btn_gris.png');
    background-size: contain;
    background-repeat: no-repeat;
    background-position: center;
    cursor: pointer;
    transition: transform 0.2s ease, opacity 0.2s ease;
    opacity: 0.85;
}}

.back_btn_gris:hover {{
    transform: scale(1.1);
    opacity: 1;
}}

.contact-btn {{
    position: fixed;
    bottom: 20px;
    right: 20px;
    padding: 12px 24px;
    font-size: 18px;
    border-radius: 8px;
    border: none;
    background-color: white;
    cursor: pointer;
}}

h1 {{
    margin-bottom: 6px;
    font-size: 42px;
    font-weight: 600;
    letter-spacing: 0.6px;
}}

.subtitle {{
    margin: 0 0 18px 0;
    font-size: 16px;
    color: rgba(255,255,255,0.85);
    letter-spacing: 0.6px;
}}

.search-container {{
    width: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding-bottom: 100px;
}}

.search-controls {{
    width: 70%;
    max-width: 900px;
    display: flex;
    align-items: center;
    gap: 50px;
}}

.search-controls form {{
    flex-grow: 1;
    display: flex;
    align-items: center;
    position: relative;
}}

.search-wrap {{
    flex-grow: 1;
    position: relative;
    display: flex;
}}

input[type="text"] {{
    flex-grow: 1;
    padding: 24px 80px;
    font-size: 27px;
    border-radius: 60px;
    border: 1px solid #ccc;
    outline: none;
    text-align: center;
    position: relative;
    z-index: 2;
}}

input[type="text"]::placeholder {{
    text-align: center;
    color: #999;
}}

.search-wrap::after {{
    content: "";
    position: absolute;
    inset: -6px;
    border-radius: 70px;
    background: linear-gradient(
        90deg,
        rgba(255,255,255,0.0),
        rgba(255,255,255,0.95),
        rgba(255,255,255,0.0)
    );
    background-size: 220% 100%;
    opacity: 0;
    pointer-events: none;
}}

.search-wrap:focus-within::after {{
    opacity: 1;
    animation: glowMove 1.1s linear infinite;
}}

@keyframes glowMove {{
    0%   {{ background-position: 0% 50%; }}
    100% {{ background-position: 220% 50%; }}
}}

.stats-btn {{
    background-color: transparent;
    border: none;
    padding: 0;
    width: 140px;
    height: 140px;
    transition: transform 0.2s ease;
    display: flex;
    justify-content: center;
    align-items: center;
}}

.stats-btn:hover {{
    transform: scale(1.2);
}}

.stats-btn img {{
    width: 110px;
    height: 110px;
}}

.btn-create-stat {{
    flex-shrink: 0;
    width: 140px;
    height: 140px;
    background-image: url('/btn_page_cree_objet_stats.png');
    background-size: contain;
    background-repeat: no-repeat;
    background-position: center;
    border: none;
    cursor: pointer;
    transition: transform 0.2s ease, filter 0.2s ease;
}}

.btn-create-stat:hover {{
    transform: scale(1.15);
    filter: brightness(1.1);
}}

.filter-toggle {{
    display: none;
}}

.tool-btn {{
    background-color: rgba(255, 255, 255, 0.95);
    border: none;
    border-radius: 60px;
    width: 70px;
    height: 70px;
    cursor: pointer;
    display: flex;
    justify-content: center;
    align-items: center;
    transition: 0.2s;
    margin-left: 10px;
    user-select: none;
    position: relative;
    z-index: 1003;
}}

.tool-btn:hover {{
    background-color: white;
    box-shadow: 0px 0px 8px rgba(0,0,0,0.25);
}}

.tool-icon {{
    width: 40px;
    height: 40px;
}}

.filter-toggle:checked + label.tool-btn {{
    background-color: white;
    box-shadow: 0 0 14px rgba(255,255,255,0.35);
    transform: scale(1.03);
}}

.filter-dropdown {{
    position: absolute;
    bottom: 85px;
    right: 0;
    width: 360px;
    background-color: rgba(255, 255, 255, 0.95);
    border-radius: 10px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    padding: 15px;
    z-index: 1002;
    display: none;
    color: #333;
}}

.filter-dropdown label {{
    display: block;
    margin-top: 10px;
    font-weight: bold;
}}

.filter-dropdown select,
.filter-dropdown input {{
    width: 100%;
    padding: 8px;
    margin-top: 5px;
    border-radius: 5px;
    border: 1px solid #ccc;
}}

.filter-dropdown button {{
    width: 100%;
    padding: 10px;
    margin-top: 15px;
    background-color: #000;
    color: white;
    border: none;
    border-radius: 5px;
    cursor: pointer;
}}

.filter-overlay {{
    position: fixed;
    inset: 0;
    background: transparent;
    z-index: 1001;
    display: none;
}}

.filter-toggle:checked ~ .filter-overlay {{
    display: block;
}}
.filter-toggle:checked ~ .filter-dropdown {{
    display: block;
}}

@media (max-width: 900px){{
    .search-controls {{ width: 92%; gap: 24px; }}
}}
</style>
</head>

<body>

<a href="contacter.py">
    <button class="contact-btn">Nous contacter</button>
</a>
<a href="vrai_index.py" class="back_btn_gris" title="Retour"></a>

<div class="search-container">
    <img src="/logo_cube_index.png" alt="logo" style="width:180px;">
    <h1>Privealy Economy</h1>
    <p class="subtitle">Analyse, simulation et classement des objets</p>

    <div class="search-controls">

        <a href="create_stat_object.py"
           class="btn-create-stat"
           title="Créer un objet statistique"></a>

        <form method="get" action="recherche.py">

            <div class="search-wrap">
                <input type="text" name="q" placeholder="Chercher un objet">
            </div>

            <input type="checkbox" id="toggle-filter" class="filter-toggle">

            <label for="toggle-filter" class="tool-btn" title="Filtres">
                <img src="/filtrage_donne.png" class="tool-icon" alt="filtre">
            </label>

            <label for="toggle-filter" class="filter-overlay" aria-hidden="true"></label>

            <div class="filter-dropdown">
                <label>Famille</label>
                <select name="famille">
                    <option value="">Toutes</option>
                    {options_famille}
                </select>

                <label>Type</label>
                <select name="type">
                    <option value="">Tous</option>
                    {options_type}
                </select>

                <label>Spéculation</label>
                <select name="speculation">
                    <option value="">Toutes</option>
                    {options_speculation}
                </select>

                <label>Prix moyen max</label>
                <input type="number" name="prix_moyen_max" min="0" step="1" placeholder="Ex: 500">

                <button type="submit">Appliquer</button>
            </div>

        </form>

        <a href="menu_statistique.py">
            <button type="button" class="stats-btn">
                <img src="/Bouton_menu_statistique.png" alt="stats">
            </button>
        </a>

    </div>
</div>

</body>
</html>
""")
