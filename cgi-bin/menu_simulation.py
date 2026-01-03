#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""

Menu "Simulation" d'un univers.

Style:
- Sombre / mystique (proche page d'accueil)
- Violet profond + or discret
- Sans JavaScript
- Tres commente
- Variables en francais uniquement

Fonction:
- Menu central pour acceder aux outils de simulation
- UID obligatoire (on est dans un univers)
- Boutons visibles de redirection vers les pages
"""

import os              # Acces systeme / chemins
import sqlite3         # Lecture des bases SQLite
import urllib.parse    # Gestion des parametres URL
import html            # Securite HTML (echappement)


# ============================================================
# En-tete HTTP CGI obligatoire
# ============================================================
print("Content-Type: text/html; charset=utf-8\n")


# ============================================================
# Constantes projet
# ============================================================
DOSSIER_UNIVERS = "cgi-bin/universes/"


# ============================================================
# Utils: lecture parametre GET
# ============================================================
def lire_parametre_get(nom, defaut=""):
    """Recupere un parametre GET depuis l'URL."""
    query_string = os.environ.get("QUERY_STRING", "")
    parametres = urllib.parse.parse_qs(query_string, keep_blank_values=True)
    return parametres.get(nom, [defaut])[0]


# ============================================================
# Utils: securite HTML
# ============================================================
def echapper_html(texte):
    """Echappe une valeur pour eviter l'injection HTML."""
    return html.escape("" if texte is None else str(texte))


# ============================================================
# Utils: chemin BDD univers
# ============================================================
def chemin_bdd_univers(uid):
    """Construit le chemin de la BDD d'un univers."""
    uid_sain = "".join([c for c in uid if c.isalnum() or c in ("-", "_")])
    return os.path.join(DOSSIER_UNIVERS, "universe_" + uid_sain + ".db")


# ============================================================
# Utils: nom univers
# ============================================================
def nom_univers(uid):
    """Recupere le nom humain de l'univers."""
    try:
        chemin = os.path.join(DOSSIER_UNIVERS, "univers_names.txt")
        if os.path.exists(chemin):
            with open(chemin, "r", encoding="utf-8") as f:
                for ligne in f:
                    if "," in ligne:
                        uid_lu, nom = ligne.strip().split(",", 1)
                        if uid_lu == uid:
                            return nom
    except Exception:
        pass
    return "Nom inconnu"


# ============================================================
# Utils: verification BDD
# ============================================================
def verifier_univers(uid):
    """Verifie que la table stat_objects existe."""
    chemin_bdd = chemin_bdd_univers(uid)

    if not os.path.exists(chemin_bdd):
        return False, "Fichier univers introuvable."

    try:
        conn = sqlite3.connect(chemin_bdd)
        cur = conn.cursor()

        cur.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='stat_objects'"
        )

        if not cur.fetchone():
            conn.close()
            return False, "Table stat_objects absente."

        cur.execute("SELECT COUNT(*) FROM stat_objects")
        nb = cur.fetchone()[0]

        conn.close()
        return True, f"Univers charge : {nb} objets."
    except Exception as e:
        return False, "Erreur BDD : " + str(e)


# ============================================================
# Utils: page CGI existe
# ============================================================
def page_existe(nom_fichier):
    """Verifie si une page CGI existe."""
    return os.path.exists(os.path.join("cgi-bin", nom_fichier))


# ============================================================
# Lecture contexte
# ============================================================
uid = lire_parametre_get("uid", "")

if not uid:
    print("<h1>Erreur : univers non specifie</h1>")
    raise SystemExit

nom_univ = nom_univers(uid)
ok_bdd, message_bdd = verifier_univers(uid)
uid_encode = urllib.parse.quote(uid)


# ============================================================
# Definition des panels
# ============================================================
panels = [
    {
        "titre": "Liaison",
        "badge": "Noyau",
        "description": "Creation de liens entre objets, evenements et psychologies.",
        "fichier": "liaison.py"
    },
    {
        "titre": "Simulation Calcule",
        "badge": "Deterministe",
        "description": "Calculs deterministes bases sur prix, quantites et coefficients.",
        "fichier": "simulation_calcule.py"
    },
    {
        "titre": "Simulation Monte Carlo",
        "badge": "Probabiliste",
        "description": "Simulation aleatoire pour evaluer risque et incertitude.",
        "fichier": "simulation_monte_carlo.py"
    },
    {
        "titre": "Simulation Three",
        "badge": "Paroxysme",
        "description": "Simulation avancee basee sur des liaisons complexes.",
        "fichier": "simulation_three.py"
    }
]


# ============================================================
# HTML + CSS
# ============================================================
print(f"""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Simulation - {echapper_html(nom_univ)}</title>

<style>
body {{
    margin: 0;
    font-family: Arial, sans-serif;
    color: white;
    background:
        radial-gradient(900px 500px at 20% 10%, rgba(255,216,106,0.10), transparent 60%),
        linear-gradient(180deg, #07040d, #120a1f);
}}

.bouton-retour {{
    position: fixed;
    top: 20px;
    left: 20px;
    width: 64px;
    height: 64px;
    background: url('/back_btn_violet.png') no-repeat center/contain;
}}

.panel {{
    width: 1120px;
    margin: 60px auto;
    padding: 50px;
    background: rgba(24,10,40,0.78);
    border-radius: 28px;
    border: 1px solid rgba(255,216,106,0.25);
}}

h1 {{
    text-align: center;
    color: #FFD86A;
}}

.info {{
    margin: 20px 0;
    padding: 12px;
    background: rgba(0,0,0,0.35);
    border-radius: 12px;
}}

.grille {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
}}

.carte {{
    padding: 22px;
    border-radius: 22px;
    background: rgba(62,24,108,0.65);
    border: 1px solid rgba(255,255,255,0.12);
}}

.entete {{
    display: flex;
    justify-content: space-between;
    align-items: center;
}}

.badge {{
    font-size: 11px;
    padding: 6px 12px;
    border-radius: 999px;
    background: rgba(255,216,106,0.18);
    border: 1px solid rgba(255,216,106,0.35);
    color: #FFD86A;
}}

.description {{
    margin: 14px 0 20px 0;
    opacity: 0.85;
}}

.bouton {{
    display: inline-block;
    padding: 10px 18px;
    border-radius: 999px;
    text-decoration: none;
    font-size: 13px;
    background: rgba(255,216,106,0.18);
    border: 1px solid rgba(255,216,106,0.45);
    color: #FFD86A;
}}

.bouton.inactif {{
    opacity: 0.5;
    pointer-events: none;
}}
</style>
</head>

<body>

<a class="bouton-retour" href="/cgi-bin/univers_dashboard.py?uid={uid_encode}"></a>

<div class="panel">
<h1>Simulation</h1>

<div class="info">{echapper_html(message_bdd)}</div>

<div class="grille">
""")

# ============================================================
# Panels dynamiques avec boutons
# ============================================================
for p in panels:
    existe = page_existe(p["fichier"])

    if existe:
        lien = f"/cgi-bin/{p['fichier']}?uid={uid_encode}"
        bouton = f'<a class="bouton" href="{lien}">Acceder</a>'
    else:
        bouton = '<span class="bouton inactif">Bientot</span>'

    print(f"""
    <div class="carte">
        <div class="entete">
            <h2>{echapper_html(p['titre'])}</h2>
            <span class="badge">{echapper_html(p['badge'])}</span>
        </div>
        <div class="description">{echapper_html(p['description'])}</div>
        {bouton}
    </div>
    """)

print("""
</div>
</div>
</body>
</html>
""")
