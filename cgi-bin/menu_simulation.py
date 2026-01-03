#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
simulation.py
-------------
Menu "Simulation" d'un univers.

Demande:
- Design sombre + PLUS mysterieux (plus "rituel", plus profond, plus atmospherique)
- Toujours proche du style page d'accueil
- Sans JavaScript
- Variables en francais
- Fichier tres commente
- Ajouter des boutons visibles de redirection vers les pages (Acceder / Bientot)

Notes:
- Cette page ne calcule rien, c'est un menu.
- L'uid est obligatoire (on est dans un univers).
"""

import os              # Variables d'environnement, chemins
import sqlite3         # Lecture BDD SQLite
import urllib.parse    # Gestion des parametres URL
import html            # Echappement HTML (anti-injection)


# ============================================================
# En-tete HTTP CGI obligatoire
# ============================================================
print("Content-Type: text/html; charset=utf-8\n")


# ============================================================
# Constantes projet
# ============================================================
DOSSIER_UNIVERS = "cgi-bin/universes/"  # Dossier contenant les BDD des univers


# ============================================================
# Utils: lecture parametre GET
# ============================================================
def lire_parametre_get(nom, defaut=""):
    """Recupere un parametre GET dans QUERY_STRING (ex: ?uid=123)."""
    query_string = os.environ.get("QUERY_STRING", "")  # Texte brut apres '?'
    parametres = urllib.parse.parse_qs(query_string, keep_blank_values=True)  # Dictionnaire des params
    return parametres.get(nom, [defaut])[0]  # Premiere valeur ou defaut


# ============================================================
# Utils: securite HTML
# ============================================================
def echapper_html(texte):
    """Echappe un texte pour eviter l'injection HTML."""
    return html.escape("" if texte is None else str(texte))


# ============================================================
# Utils: chemin BDD univers
# ============================================================
def construire_chemin_univers(uid):
    """
    Construit le chemin du fichier sqlite d'un univers.
    Nettoyage basique de l'uid pour eviter les chemins malveillants.
    """
    uid_sain = "".join([c for c in uid if c.isalnum() or c in ("-", "_")])
    return os.path.join(DOSSIER_UNIVERS, "universe_" + uid_sain + ".db")


# ============================================================
# Utils: recupere le nom d'un univers
# ============================================================
def recuperer_nom_univers(uid):
    """Lit univers_names.txt (format uid,nom) et renvoie le nom."""
    try:
        chemin = os.path.join(DOSSIER_UNIVERS, "univers_names.txt")
        if os.path.exists(chemin):
            with open(chemin, "r", encoding="utf-8") as f:
                for ligne in f:
                    if "," in ligne:
                        uid_lu, nom_lu = ligne.strip().split(",", 1)
                        if uid_lu == uid:
                            return nom_lu
    except Exception:
        pass
    return "Nom inconnu"


# ============================================================
# Utils: verifier table stat_objects
# ============================================================
def verifier_univers(uid):
    """Verifie que la BDD existe et que stat_objects est present."""
    chemin_bdd = construire_chemin_univers(uid)

    if not os.path.exists(chemin_bdd):
        return False, "Fichier univers introuvable."

    try:
        conn = sqlite3.connect(chemin_bdd)
        cur = conn.cursor()

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stat_objects'")
        if not cur.fetchone():
            conn.close()
            return False, "Table stat_objects absente."

        cur.execute("SELECT COUNT(*) FROM stat_objects")
        nb = cur.fetchone()[0]

        conn.close()
        return True, "Univers charge : " + str(nb) + " objets."
    except Exception as e:
        return False, "Erreur BDD : " + str(e)


# ============================================================
# Utils: verifier si une page CGI existe
# ============================================================
def page_cgi_existe(nom_fichier):
    """Retourne True si cgi-bin/<nom_fichier> existe."""
    return os.path.exists(os.path.join("cgi-bin", nom_fichier))


# ============================================================
# Lecture du contexte univers (uid obligatoire)
# ============================================================
uid = lire_parametre_get("uid", "")

# Si uid absent, on affiche une erreur simple (pas de menu possible)
if not uid:
    print("<h1>Erreur : univers non specifie</h1>")
    raise SystemExit

nom_univers = recuperer_nom_univers(uid)              # Nom affiche
ok_bdd, message_bdd = verifier_univers(uid)           # Etat BDD
uid_encode = urllib.parse.quote(uid)                  # uid encode pour URL


# ============================================================
# Definition des panels (menu simulation)
# ============================================================
panels = [
    {
        "titre": "Liaison",
        "badge": "Noyau (Prively 1.1)",
        "description": (
            "Lie des objets entre eux, mais aussi a des evenements, psychologie, etc. "
            "Outil complexe pour construire un monde coherent."
        ),
        "fichier": "liaison.py"
    },
    {
        "titre": "Simulation Calcule",
        "badge": "Deterministe (Beta)",
        "description": (
            "Simulation deterministe basee sur prix, quantites et coefficients. "
            "Calcule total moyen, min/max et projection a N annees."
        ),
        "fichier": "sim_calc.py"
    },
    {
        "titre": "Simulation Monte Carlo",
        "badge": "Probabiliste",
        "description": (
            "Simulation probabiliste par tirages aleatoires entre min/max. "
            "Permet d'evaluer le risque et l'incertitude."
        ),
        "fichier": "simulation_monte_carlo.py"
    },
    {
        "titre": "Simulation Three",
        "badge": "Paroxysme",
        "description": (
            "Utilise la liaison a son maximum. "
            "Interactions avancees, propagation, dependances multiples."
        ),
        "fichier": "simulation_three.py"
    }
]


# ============================================================
# Impression HTML + CSS (theme "mystique")
# ============================================================
print(f"""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Simulation - {echapper_html(nom_univers)}</title>

<style>
/* ============================================================
   THEME "MYSTIQUE" (plus profond que la version precedente)
   - Couleurs: noir/violet + or discret
   - Atmosphere: brume + halo + lueurs
   - Toujours sans image obligatoire (sauf bouton retour)
   ============================================================ */

/* ----- Fond global: plusieurs couches pour donner un effet "rituel" ----- */
body {{
    margin: 0;
    font-family: Arial, sans-serif;
    color: #ffffff;
    min-height: 100vh;

    background:
        /* Halo or discret (comme une bougie tres lointaine) */
        radial-gradient(900px 600px at 18% 18%, rgba(255,216,106,0.12), rgba(0,0,0,0) 62%),

        /* Halo violet (mystique) */
        radial-gradient(800px 520px at 82% 18%, rgba(190,120,255,0.20), rgba(0,0,0,0) 60%),

        /* Brume cyan tres faible */
        radial-gradient(900px 650px at 55% 85%, rgba(110,255,220,0.06), rgba(0,0,0,0) 62%),

        /* Bande sombre verticale (profondeur) */
        linear-gradient(180deg, #05020a 0%, #0b0615 45%, #120a22 100%);
}}

/* ----- Surcouche "grain" (simule un voile) ----- */
body:before {{
    content: "";
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    pointer-events: none;

    /* Voile sombre + micro contraste */
    background: radial-gradient(900px 500px at 50% 30%, rgba(255,255,255,0.04), rgba(0,0,0,0) 60%);
    opacity: 0.60;
}}

/* ----- Bouton retour ----- */
.bouton-retour {{
    position: fixed;
    top: 20px;
    left: 20px;
    width: 64px;
    height: 64px;
    background: url('/back_btn_violet.png') no-repeat center/contain;
    cursor: pointer;
    transition: transform 0.2s ease;
}}
.bouton-retour:hover {{
    transform: scale(1.08);
}}

/* ----- Panel principal: "autel" ----- */
.panel {{
    width: 1120px;
    height: 720px;
    margin: 55px auto;
    padding: 54px;
    box-sizing: border-box;

    border-radius: 30px;

    /* Fond sombre translucide */
    background: rgba(14, 6, 26, 0.72);

    /* Double bordure: or externe + violet interne */
    border: 1px solid rgba(255,216,106,0.20);
    box-shadow:
        0 30px 70px rgba(0,0,0,0.62),
        inset 0 1px 2px rgba(255,255,255,0.06),
        inset 0 0 0 1px rgba(190,120,255,0.10);
}}

/* ----- Titre principal ----- */
h1 {{
    margin: 0;
    text-align: center;
    color: #FFD86A;
    letter-spacing: 0.8px;
}}

/* ----- Ligne univers ----- */
.ligne-univers {{
    text-align: center;
    margin-top: 10px;
    font-size: 14px;
    color: rgba(255,255,255,0.84);
    opacity: 0.92;
}}

/* ----- Etat BDD ----- */
.info {{
    margin: 18px 0 24px 0;
    padding: 12px 16px;
    border-radius: 14px;

    /* Fond sombre */
    background: rgba(0,0,0,0.28);

    /* Bordure tres discrète */
    border: 1px solid rgba(255,255,255,0.10);

    font-size: 13px;
}}
.info.ok {{
    border-color: rgba(120,255,180,0.30);
}}
.info.bad {{
    border-color: rgba(255,120,120,0.30);
}}

/* ----- Grille de panels ----- */
.grille {{
    margin-top: 8px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
}}

/* ----- Panel carte ----- */
.carte {{
    height: 205px;
    padding: 22px;
    box-sizing: border-box;
    border-radius: 24px;

    /* Fond violet sombre "encre" */
    background:
        radial-gradient(700px 260px at 20% 20%, rgba(255,216,106,0.06), rgba(0,0,0,0) 60%),
        linear-gradient(180deg, rgba(70,28,120,0.58), rgba(45,16,85,0.58));

    /* Bordure fine + glow discret */
    border: 1px solid rgba(255,255,255,0.10);
    box-shadow:
        0 18px 36px rgba(0,0,0,0.50),
        inset 0 1px 2px rgba(255,255,255,0.05);

    transition: transform 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease;
}}
.carte:hover {{
    transform: translateY(-3px);
    border-color: rgba(255,216,106,0.36);
    box-shadow:
        0 20px 44px rgba(0,0,0,0.55),
        inset 0 1px 2px rgba(255,255,255,0.06);
}}

/* ----- Entete carte (titre + badge) ----- */
.entete-carte {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
}}

.entete-carte h2 {{
    margin: 0;
    font-size: 21px;
    color: rgba(255,255,255,0.96);
}}

/* ----- Badge ----- */
.badge {{
    font-size: 11px;
    padding: 6px 12px;
    border-radius: 999px;
    background: rgba(255,216,106,0.14);
    border: 1px solid rgba(255,216,106,0.30);
    color: #FFD86A;
    white-space: nowrap;
}}

/* ----- Description ----- */
.description-carte {{
    margin-top: 14px;
    line-height: 1.35;
    font-size: 14px;
    color: rgba(255,255,255,0.82);
}}

/* ----- Zone boutons ----- */
.zone-actions {{
    margin-top: 18px;
    display: flex;
    align-items: center;
    justify-content: flex-end;
}}

/* ----- Bouton "Acceder" (or/violet) ----- */
.bouton-action {{
    display: inline-block;
    padding: 10px 18px;
    border-radius: 999px;
    text-decoration: none;
    font-size: 13px;

    color: #FFD86A;
    background: rgba(255,216,106,0.12);
    border: 1px solid rgba(255,216,106,0.38);

    transition: transform 0.12s ease, background 0.12s ease, border-color 0.12s ease;
}}
.bouton-action:hover {{
    transform: translateY(-1px);
    background: rgba(255,216,106,0.18);
    border-color: rgba(255,216,106,0.48);
}}

/* ----- Bouton inactif (Bientot) ----- */
.bouton-action.inactif {{
    opacity: 0.55;
    pointer-events: none;
}}

/* ----- Carte inactive (si page absente) ----- */
.carte.inactive {{
    opacity: 0.60;
    filter: grayscale(0.22);
}}
.carte.inactive:hover {{
    transform: none;
    border-color: rgba(255,255,255,0.10);
}}

/* ----- Note bas ----- */
.note-bas {{
    margin-top: 18px;
    text-align: center;
    opacity: 0.62;
    font-size: 12px;
    color: rgba(255,255,255,0.78);
}}
</style>
</head>

<body>

<!-- Retour vers le dashboard de l'univers -->
<a class="bouton-retour" href="/cgi-bin/univers_dashboard.py?uid={uid_encode}" title="Retour"></a>

<div class="panel">

    <!-- Titre -->
    <h1>Simulation</h1>

    <!-- Contexte univers -->
    <div class="ligne-univers">
        Univers : <strong>{echapper_html(nom_univers)}</strong>
        &nbsp;|&nbsp;
        ID : {echapper_html(uid)}
    </div>

    <!-- Etat BDD -->
    <div class="info {'ok' if ok_bdd else 'bad'}">
        {echapper_html(message_bdd)}
    </div>

    <!-- Grille des panels -->
    <div class="grille">
""")

# ============================================================
# Impression des panels avec boutons de redirection
# ============================================================
for panel in panels:
    # Lecture champs panel
    titre = panel["titre"]
    badge = panel["badge"]
    description = panel["description"]
    fichier = panel["fichier"]

    # Determine si la page existe
    existe = page_cgi_existe(fichier)

    # Construit le bouton selon l'etat
    if existe:
        lien = "/cgi-bin/" + fichier + "?uid=" + uid_encode
        bouton_html = f'<a class="bouton-action" href="{lien}">Acceder</a>'
        classe_carte = "carte"
    else:
        bouton_html = '<span class="bouton-action inactif">Bientot</span>'
        classe_carte = "carte inactive"

    # Impression HTML d'un panel
    print(f"""
        <div class="{classe_carte}">
            <div class="entete-carte">
                <h2>{echapper_html(titre)}</h2>
                <span class="badge">{echapper_html(badge)}</span>
            </div>

            <div class="description-carte">
                {echapper_html(description)}
            </div>

            <div class="zone-actions">
                {bouton_html}
            </div>
        </div>
    """)

# ============================================================
# Fin HTML
# ============================================================
print("""
    </div>

    <div class="note-bas">
        Astuce : on est dans un univers. Les simulations utiliseront la BDD de l'univers (stat_objects).
    </div>

</div>

</body>
</html>
""")
