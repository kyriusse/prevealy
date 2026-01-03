#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
liaison.py
----------
Page "Liaison" (dans un univers).

But:
- Permet de creer des liaisons entre objets (et aussi vers des "entites" libres: evenement, psychologie, etc.)
- Sans JavaScript: tout fonctionne par formulaires GET + rechargement de page
- Stockage propre dans la BDD de l'univers: table "liaisons" (cree si besoin)
- Compatible avec l'existant: la colonne stat_objects.liaison existe deja (ajoutee a la creation d'univers)

Fonctionnement general:
1) Choisir un objet source (via recherche + liste de resultats)
2) Ajouter une liaison (type cible, nom cible, type de lien, poids/coef, commentaire)
3) Afficher / supprimer les liaisons de l'objet source
4) Garder les liens de navigation (retour simulation / dashboard univers)

Contraintes:
- Variables en francais
- Commentaires partout (sauf vraiment evident)
- Anti-injection HTML (html.escape)
- On reste dans un univers (uid obligatoire)
"""

import os              # Acces aux variables d'environnement et aux chemins
import sqlite3         # Acces aux bases SQLite
import urllib.parse    # Lecture / encodage des parametres URL
import html            # Echappement HTML
import difflib         # Suggestions "mot proche" en cas d'erreur de saisie


# ============================================================
# En-tete HTTP CGI obligatoire (sinon page blanche)
# ============================================================
print("Content-Type: text/html; charset=utf-8\n")


# ============================================================
# Constantes projet
# ============================================================
DOSSIER_UNIVERS = "cgi-bin/universes/"  # Dossier contenant les BDD par univers


# ============================================================
# Utils: lecture parametre GET
# ============================================================
def lire_parametre_get(nom, defaut=""):
    """Lit un parametre GET dans QUERY_STRING (ex: ?uid=123)."""
    query_string = os.environ.get("QUERY_STRING", "")                         # Query string brute
    parametres = urllib.parse.parse_qs(query_string, keep_blank_values=True)  # Parse en dict
    return parametres.get(nom, [defaut])[0]                                   # Premiere valeur ou defaut


# ============================================================
# Utils: echappement HTML (securite)
# ============================================================
def echapper_html(texte):
    """Echappe un texte pour eviter l'injection HTML dans la page."""
    return html.escape("" if texte is None else str(texte))


# ============================================================
# Utils: uid -> chemin de la BDD univers
# ============================================================
def construire_chemin_univers(uid):
    """
    Construit le chemin de la BDD sqlite d'un univers a partir de uid.
    Nettoyage basique: on n'autorise que alnum + '-' + '_'.
    """
    uid_sain = "".join([c for c in uid if c.isalnum() or c in ("-", "_")])     # Nettoyage anti ../
    return os.path.join(DOSSIER_UNIVERS, "universe_" + uid_sain + ".db")       # Chemin final


# ============================================================
# Utils: lecture nom univers (univers_names.txt)
# ============================================================
def recuperer_nom_univers(uid):
    """
    Lit univers_names.txt (format: uid,nom) et renvoie le nom associe.
    Si introuvable -> "Nom inconnu".
    """
    try:
        chemin_fichier = os.path.join(DOSSIER_UNIVERS, "univers_names.txt")    # Fichier des noms
        if os.path.exists(chemin_fichier):                                    # Evite exception
            with open(chemin_fichier, "r", encoding="utf-8") as f:            # Lecture utf-8
                for ligne in f:                                               # Parcours des lignes
                    if "," in ligne:                                          # Format attendu
                        uid_lu, nom_lu = ligne.strip().split(",", 1)          # Split en 2
                        if uid_lu == uid:                                     # Match uid
                            return nom_lu                                     # Nom trouve
    except Exception:
        # En cas d'erreur (permission, fichier corrompu...), on ignore
        pass

    return "Nom inconnu"                                                      # Valeur par defaut


# ============================================================
# Utils: ouvrir connexion sur l'univers
# ============================================================
def ouvrir_connexion_univers(uid):
    """Ouvre une connexion sqlite sur la BDD de l'univers."""
    chemin_bdd = construire_chemin_univers(uid)                                # Chemin BDD
    return sqlite3.connect(chemin_bdd)                                         # Connexion sqlite


# ============================================================
# Utils: s'assurer que la table "liaisons" existe
# ============================================================
def creer_table_liaisons_si_besoin(conn):
    """
    Cree une table 'liaisons' si elle n'existe pas encore.
    Cette table stocke toutes les liaisons de maniere propre (au lieu d'un texte vague).
    """
    cur = conn.cursor()                                                       # Curseur SQL

    # Table simple mais extensible:
    # - source_objet_id: id dans stat_objects
    # - cible_type: Objet / Evenement / Psychologie / Autre
    # - cible_nom: texte (ou nom d'objet si cible_type=Objet)
    # - lien_type: type de relation (ex: "compose", "influence", "cause", etc.)
    # - poids: coefficient (float) utile pour simulation Three / propagation
    # - commentaire: note libre
    # - date_creation: timestamp texte (utile pour debug/historique)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS liaisons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_objet_id INTEGER NOT NULL,
            cible_type TEXT NOT NULL,
            cible_nom TEXT NOT NULL,
            lien_type TEXT NOT NULL,
            poids REAL DEFAULT 1.0,
            commentaire TEXT DEFAULT '',
            date_creation TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()                                                              # Valide creation


# ============================================================
# Utils: trouver les noms de colonnes utiles dans stat_objects
# ============================================================
def colonnes_stat_objects(conn):
    """
    Retourne un dict contenant:
    - colonne_id: colonne "id" (souvent 'id')
    - colonne_nom: colonne nom objet (souvent 'Objet')
    - colonne_liaison: colonne 'liaison' (ajoutee dans create_stat_object)
    """
    cur = conn.cursor()                                                       # Curseur SQL
    cur.execute("PRAGMA table_info(stat_objects)")                             # Infos colonnes
    infos = cur.fetchall()                                                    # Liste (cid, name, type, ...)

    # Valeurs detectees (on cherche en insensible a la casse)
    colonne_id = None                                                         # id objet
    colonne_nom = None                                                        # nom objet
    colonne_liaison = None                                                    # champ texte liaison

    for col in infos:                                                         # Parcours colonnes
        nom_col = col[1]                                                      # Nom de colonne
        nom_min = (nom_col or "").lower()                                     # lower pour comparaison

        if nom_min == "id":                                                   # colonne id
            colonne_id = nom_col
        elif nom_min == "objet":                                              # colonne nom objet
            colonne_nom = nom_col
        elif nom_min == "liaison":                                            # colonne liaison (texte)
            colonne_liaison = nom_col

    # On renvoie un dict (facile a utiliser ensuite)
    return {
        "colonne_id": colonne_id,
        "colonne_nom": colonne_nom,
        "colonne_liaison": colonne_liaison
    }


# ============================================================
# Utils: recuperer un objet par id
# ============================================================
def recuperer_objet_par_id(conn, colonne_id, colonne_nom, objet_id):
    """Retourne (id, nom) ou None si introuvable."""
    cur = conn.cursor()                                                       # Curseur
    cur.execute(
        f"SELECT [{colonne_id}], [{colonne_nom}] FROM stat_objects WHERE [{colonne_id}] = ?",
        (objet_id,)
    )
    return cur.fetchone()                                                     # (id, nom) ou None


# ============================================================
# Utils: rechercher des objets par texte
# ============================================================
def rechercher_objets(conn, colonne_id, colonne_nom, texte_recherche, limite=25):
    """
    Recherche dans stat_objects les objets dont le nom contient texte_recherche (LIKE).
    Retourne une liste de tuples (id, nom).
    """
    cur = conn.cursor()                                                       # Curseur
    motif = "%" + texte_recherche.strip() + "%"                                # Motif LIKE
    cur.execute(
        f"""
        SELECT [{colonne_id}], [{colonne_nom}]
        FROM stat_objects
        WHERE [{colonne_nom}] IS NOT NULL
          AND TRIM([{colonne_nom}]) != ''
          AND [{colonne_nom}] LIKE ?
        ORDER BY [{colonne_nom}] COLLATE NOCASE
        LIMIT ?
        """,
        (motif, limite)
    )
    return cur.fetchall()                                                     # Liste (id, nom)


# ============================================================
# Utils: liste de tous les noms (pour suggestions difflib)
# ============================================================
def tous_les_noms_objets(conn, colonne_nom):
    """Recupere tous les noms d'objets (utile pour suggestions)."""
    cur = conn.cursor()                                                       # Curseur
    cur.execute(
        f"""
        SELECT [{colonne_nom}]
        FROM stat_objects
        WHERE [{colonne_nom}] IS NOT NULL
          AND TRIM([{colonne_nom}]) != ''
        """
    )
    return [r[0] for r in cur.fetchall()]                                      # Liste de noms


# ============================================================
# Utils: generer suggestions "mot proche"
# ============================================================
def suggestions(texte, liste_noms, max_suggestions=6):
    """
    Retourne une liste de suggestions proches du texte.
    Exemple: "stylode" -> ["stylo", ...]
    """
    if not texte:
        return []
    # get_close_matches renvoie des chaines proches (ratio de similarite)
    return difflib.get_close_matches(texte, liste_noms, n=max_suggestions, cutoff=0.60)


# ============================================================
# Utils: lister liaisons d'un objet source
# ============================================================
def lister_liaisons(conn, source_objet_id):
    """Retourne toutes les liaisons d'un objet source (liste de tuples)."""
    cur = conn.cursor()                                                       # Curseur
    cur.execute(
        """
        SELECT id, cible_type, cible_nom, lien_type, poids, commentaire, date_creation
        FROM liaisons
        WHERE source_objet_id = ?
        ORDER BY id DESC
        """,
        (source_objet_id,)
    )
    return cur.fetchall()


# ============================================================
# Utils: ajouter liaison
# ============================================================
def ajouter_liaison(conn, source_objet_id, cible_type, cible_nom, lien_type, poids, commentaire):
    """Insere une liaison en base."""
    cur = conn.cursor()                                                       # Curseur
    cur.execute(
        """
        INSERT INTO liaisons (source_objet_id, cible_type, cible_nom, lien_type, poids, commentaire)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (source_objet_id, cible_type, cible_nom, lien_type, poids, commentaire)
    )
    conn.commit()                                                             # Valide insertion


# ============================================================
# Utils: supprimer liaison
# ============================================================
def supprimer_liaison(conn, liaison_id):
    """Supprime une liaison par id."""
    cur = conn.cursor()                                                       # Curseur
    cur.execute("DELETE FROM liaisons WHERE id = ?", (liaison_id,))            # Delete
    conn.commit()                                                             # Valide suppression


# ============================================================
# 1) Lecture du contexte (uid obligatoire)
# ============================================================
uid = lire_parametre_get("uid", "")                                           # Identifiant univers

# Si pas d'uid, on ne peut pas ouvrir la BDD de l'univers
if not uid:
    print("<h1>Erreur : univers non specifie</h1>")
    raise SystemExit

# Nom humain de l'univers (pour affichage)
nom_univers = recuperer_nom_univers(uid)

# uid encode pour le reutiliser dans les liens
uid_encode = urllib.parse.quote(uid)


# ============================================================
# 2) Ouverture BDD univers + verifs structure
# ============================================================
chemin_bdd = construire_chemin_univers(uid)                                   # Chemin sqlite univers
bdd_existe = os.path.exists(chemin_bdd)                                       # Presence fichier

# Si la BDD univers n'existe pas, on sort proprement
if not bdd_existe:
    print("<h1>Erreur : BDD univers introuvable</h1>")
    print("<p>Chemin attendu : " + echapper_html(chemin_bdd) + "</p>")
    raise SystemExit

# Connexion sqlite (univers)
connexion = ouvrir_connexion_univers(uid)

# On cree la table liaisons si besoin (safe)
creer_table_liaisons_si_besoin(connexion)

# Detection colonnes stat_objects (id/Objet/liaison)
infos_colonnes = colonnes_stat_objects(connexion)

colonne_id = infos_colonnes.get("colonne_id")                                 # Colonne id
colonne_nom = infos_colonnes.get("colonne_nom")                               # Colonne Objet
colonne_liaison = infos_colonnes.get("colonne_liaison")                       # Colonne liaison

# Si la table stat_objects n'est pas conforme, on affiche une erreur
if not colonne_id or not colonne_nom:
    print("<h1>Erreur : table stat_objects invalide</h1>")
    print("<p>Colonnes detectees : " + echapper_html(str(infos_colonnes)) + "</p>")
    connexion.close()
    raise SystemExit


# ============================================================
# 3) Lecture action utilisateur (ajouter/supprimer/chercher/selectionner)
# ============================================================
action = lire_parametre_get("action", "")                                     # action=...

# Champ recherche (objet source a trouver)
recherche = lire_parametre_get("recherche", "").strip()                        # texte saisi

# Objet source selectionne (id) - si vide, on n'affiche pas les liaisons
source_id_str = lire_parametre_get("source_id", "").strip()                   # id sous forme texte
source_id = None                                                              # id en int ou None
if source_id_str.isdigit():                                                   # validation simple
    source_id = int(source_id_str)                                            # conversion


# ============================================================
# 4) Traitement des actions (suppression / ajout)
# ============================================================
message_action = ""                                                           # message utilisateur
erreur_action = ""                                                            # message d'erreur

# --- Suppression d'une liaison (si action=supprimer) ---
if action == "supprimer":
    liaison_id_str = lire_parametre_get("liaison_id", "").strip()             # id liaison
    if liaison_id_str.isdigit():                                              # verif numerique
        try:
            supprimer_liaison(connexion, int(liaison_id_str))                 # suppression BDD
            message_action = "Liaison supprimee."
        except Exception as e:
            erreur_action = "Erreur suppression : " + str(e)
    else:
        erreur_action = "Erreur suppression : id liaison invalide."

# --- Ajout d'une liaison (si action=ajouter) ---
if action == "ajouter":
    # Parametres liaison (issus du formulaire)
    cible_type = lire_parametre_get("cible_type", "Objet").strip()
    cible_nom = lire_parametre_get("cible_nom", "").strip()
    lien_type = lire_parametre_get("lien_type", "associe").strip()
    poids_str = lire_parametre_get("poids", "1.0").strip()
    commentaire = lire_parametre_get("commentaire", "").strip()

    # Validation: source selectionne
    if source_id is None:
        erreur_action = "Impossible d'ajouter: aucun objet source selectionne."
    elif not cible_nom:
        erreur_action = "Impossible d'ajouter: cible vide."
    else:
        # Conversion poids (float) avec securite
        try:
            poids = float(poids_str.replace(",", "."))                        # accepte virgule
        except Exception:
            poids = 1.0                                                       # fallback

        # Ajout en base
        try:
            ajouter_liaison(connexion, source_id, cible_type, cible_nom, lien_type, poids, commentaire)
            message_action = "Liaison ajoutee."
        except Exception as e:
            erreur_action = "Erreur ajout : " + str(e)


# ============================================================
# 5) Recuperation de l'objet source (si selectionne)
# ============================================================
objet_source = None                                                           # tuple (id, nom) ou None
if source_id is not None:
    objet_source = recuperer_objet_par_id(connexion, colonne_id, colonne_nom, source_id)


# ============================================================
# 6) Resultats de recherche (si texte saisi)
# ============================================================
resultats_recherche = []                                                      # liste (id, nom)
liste_suggestions = []                                                        # suggestions difflib

# Si l'utilisateur a saisi quelque chose dans recherche
if recherche:
    # Recherche SQL (LIKE)
    try:
        resultats_recherche = rechercher_objets(connexion, colonne_id, colonne_nom, recherche, limite=30)
    except Exception:
        resultats_recherche = []

    # Si pas de resultat, on propose des mots proches
    if not resultats_recherche:
        try:
            noms = tous_les_noms_objets(connexion, colonne_nom)
            liste_suggestions = suggestions(recherche, noms, max_suggestions=8)
        except Exception:
            liste_suggestions = []


# ============================================================
# 7) Liaisons de l'objet source (si selectionne)
# ============================================================
liaisons_source = []                                                          # liste liaisons
if objet_source:
    try:
        liaisons_source = lister_liaisons(connexion, objet_source[0])          # liaisons pour id source
    except Exception:
        liaisons_source = []


# ============================================================
# 8) HTML (design sombre / mystique, sans JS)
# ============================================================
print(f"""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Liaison - {echapper_html(nom_univers)}</title>

<style>
/* ============================================================
   THEME SOMBRE / MYSTIQUE (coherent avec simulation.py)
   - Fond profond + halos discrets
   - Panels "verre" violet
   - Or en accent
   ============================================================ */

body {{
    margin: 0;
    font-family: Arial, sans-serif;
    color: #ffffff;
    min-height: 100vh;

    background:
        radial-gradient(900px 600px at 18% 18%, rgba(255,216,106,0.12), rgba(0,0,0,0) 62%),
        radial-gradient(800px 520px at 82% 18%, rgba(190,120,255,0.20), rgba(0,0,0,0) 60%),
        radial-gradient(900px 650px at 55% 85%, rgba(110,255,220,0.06), rgba(0,0,0,0) 62%),
        linear-gradient(180deg, #05020a 0%, #0b0615 45%, #120a22 100%);
}}

body:before {{
    content: "";
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    pointer-events: none;
    background: radial-gradient(900px 500px at 50% 30%, rgba(255,255,255,0.04), rgba(0,0,0,0) 60%);
    opacity: 0.60;
}}

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
.bouton-retour:hover {{ transform: scale(1.08); }}

.bouton-simulation {{
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 12px 18px;
    border-radius: 999px;
    text-decoration: none;
    font-size: 13px;

    color: #FFD86A;
    background: rgba(255,216,106,0.10);
    border: 1px solid rgba(255,216,106,0.34);

    box-shadow: 0 12px 28px rgba(0,0,0,0.45);
    transition: transform 0.2s ease, background 0.2s ease;
}}
.bouton-simulation:hover {{
    transform: translateY(-1px);
    background: rgba(255,216,106,0.16);
}}

.panel {{
    width: 1180px;
    margin: 55px auto;
    padding: 54px;
    box-sizing: border-box;

    border-radius: 30px;
    background: rgba(14, 6, 26, 0.72);

    border: 1px solid rgba(255,216,106,0.20);
    box-shadow:
        0 30px 70px rgba(0,0,0,0.62),
        inset 0 1px 2px rgba(255,255,255,0.06),
        inset 0 0 0 1px rgba(190,120,255,0.10);
}}

h1 {{
    margin: 0;
    text-align: center;
    color: #FFD86A;
    letter-spacing: 0.8px;
}}

.ligne-univers {{
    text-align: center;
    margin-top: 10px;
    font-size: 14px;
    color: rgba(255,255,255,0.84);
    opacity: 0.92;
}}

.message {{
    margin: 18px 0 0 0;
    padding: 12px 16px;
    border-radius: 14px;
    background: rgba(0,0,0,0.28);
    border: 1px solid rgba(255,255,255,0.10);
    font-size: 13px;
}}
.message.ok {{ border-color: rgba(120,255,180,0.30); }}
.message.bad {{ border-color: rgba(255,120,120,0.30); }}

.grille {{
    margin-top: 22px;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
}}

.carte {{
    border-radius: 24px;
    padding: 22px;
    box-sizing: border-box;
    background:
        radial-gradient(700px 260px at 20% 20%, rgba(255,216,106,0.06), rgba(0,0,0,0) 60%),
        linear-gradient(180deg, rgba(70,28,120,0.58), rgba(45,16,85,0.58));
    border: 1px solid rgba(255,255,255,0.10);
    box-shadow:
        0 18px 36px rgba(0,0,0,0.50),
        inset 0 1px 2px rgba(255,255,255,0.05);
}}

.carte h2 {{
    margin: 0 0 12px 0;
    font-size: 18px;
    color: rgba(255,255,255,0.96);
}}

.label {{
    display: block;
    margin: 10px 0 6px 0;
    font-size: 12px;
    opacity: 0.90;
}}

.champ-texte, .champ-select {{
    width: 100%;
    box-sizing: border-box;
    padding: 12px 12px;
    border-radius: 14px;

    background: rgba(0,0,0,0.28);
    color: #ffffff;

    border: 1px solid rgba(255,255,255,0.12);
    outline: none;
}}

.champ-texte:focus, .champ-select:focus {{
    border-color: rgba(255,216,106,0.40);
}}

.ligne-actions {{
    margin-top: 14px;
    display: flex;
    gap: 10px;
    justify-content: flex-end;
    align-items: center;
}}

.bouton {{
    display: inline-block;
    padding: 10px 18px;
    border-radius: 999px;
    text-decoration: none;
    font-size: 13px;
    cursor: pointer;

    color: #FFD86A;
    background: rgba(255,216,106,0.12);
    border: 1px solid rgba(255,216,106,0.38);

    transition: transform 0.12s ease, background 0.12s ease, border-color 0.12s ease;
}}
.bouton:hover {{
    transform: translateY(-1px);
    background: rgba(255,216,106,0.18);
    border-color: rgba(255,216,106,0.48);
}}

.bouton-secondaire {{
    color: rgba(255,255,255,0.88);
    background: rgba(255,255,255,0.08);
    border: 1px solid rgba(255,255,255,0.14);
}}
.bouton-secondaire:hover {{
    background: rgba(255,255,255,0.12);
    border-color: rgba(255,255,255,0.22);
}}

.resultats {{
    margin-top: 10px;
    padding: 10px 12px;
    border-radius: 14px;
    background: rgba(0,0,0,0.22);
    border: 1px solid rgba(255,255,255,0.10);
    max-height: 250px;
    overflow: auto;
}}

.ligne-resultat {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    padding: 8px 0;
    border-bottom: 1px solid rgba(255,255,255,0.06);
}}
.ligne-resultat:last-child {{ border-bottom: none; }}

.petit {{
    font-size: 12px;
    opacity: 0.82;
}}

.suggestions {{
    margin-top: 10px;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}}

.suggestion {{
    display: inline-block;
    padding: 8px 12px;
    border-radius: 999px;
    text-decoration: none;
    font-size: 12px;

    color: #FFD86A;
    background: rgba(255,216,106,0.10);
    border: 1px solid rgba(255,216,106,0.28);
}}

.table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
    font-size: 13px;
}}

.table th, .table td {{
    text-align: left;
    padding: 10px 8px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    vertical-align: top;
}}

.table th {{
    color: rgba(255,255,255,0.90);
    font-weight: bold;
}}

.lien-supprimer {{
    color: rgba(255,170,170,0.95);
    text-decoration: none;
    border: 1px solid rgba(255,120,120,0.30);
    padding: 6px 10px;
    border-radius: 999px;
    display: inline-block;
}}

.lien-supprimer:hover {{
    background: rgba(255,120,120,0.12);
}}

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

<!-- Retour dashboard univers -->
<a class="bouton-retour" href="/cgi-bin/univers_dashboard.py?uid={uid_encode}" title="Retour"></a>

<!-- Retour menu simulation -->
<a class="bouton-simulation" href="/cgi-bin/simulation.py?uid={uid_encode}" title="Menu Simulation">Menu Simulation</a>

<div class="panel">

    <h1>Liaison</h1>

    <div class="ligne-univers">
        Univers : <strong>{echapper_html(nom_univers)}</strong>
        &nbsp;|&nbsp;
        ID : {echapper_html(uid)}
    </div>
""")

# ============================================================
# Messages action (ok / erreur)
# ============================================================
if message_action:
    print(f'<div class="message ok">{echapper_html(message_action)}</div>')
if erreur_action:
    print(f'<div class="message bad">{echapper_html(erreur_action)}</div>')

# ============================================================
# Grille 2 colonnes:
# - Colonne gauche: selection de l'objet source
# - Colonne droite: gestion des liaisons (si source selectionne)
# ============================================================
print(f"""
    <div class="grille">

        <!-- ===================================================
             Carte 1: Choisir objet source
             =================================================== -->
        <div class="carte">
            <h2>1) Choisir l'objet source</h2>

            <!-- Formulaire recherche (GET) -->
            <form method="get" action="/cgi-bin/liaison.py">
                <!-- On conserve uid pour rester dans le meme univers -->
                <input type="hidden" name="uid" value="{echapper_html(uid)}">

                <!-- Champ de recherche -->
                <label class="label">Recherche (nom d'objet)</label>
                <input class="champ-texte" type="text" name="recherche"
                       value="{echapper_html(recherche)}"
                       placeholder="Ex: stylo, tableau, ecole...">

                <!-- Si un source est deja selectionne, on le conserve -->
                <input type="hidden" name="source_id" value="{echapper_html(source_id_str)}">

                <!-- Boutons -->
                <div class="ligne-actions">
                    <button class="bouton" type="submit">Chercher</button>
                    <a class="bouton bouton-secondaire" href="/cgi-bin/liaison.py?uid={uid_encode}">Reinitialiser</a>
                </div>
            </form>
""")

# ============================================================
# Affichage objet source selectionne (si existe)
# ============================================================
if objet_source:
    print(f"""
            <div class="message ok" style="margin-top:16px;">
                Objet source selectionne : <strong>{echapper_html(objet_source[1])}</strong>
                <span class="petit">(id {echapper_html(objet_source[0])})</span>
            </div>
    """)
else:
    print(f"""
            <div class="message" style="margin-top:16px;">
                Aucun objet source selectionne pour l'instant.
            </div>
    """)

# ============================================================
# Resultats de recherche (si recherche saisie)
# ============================================================
if recherche:
    if resultats_recherche:
        print('<div class="resultats">')
        for (oid, onom) in resultats_recherche:
            # Lien "Choisir" = recharge la page avec source_id = id choisi
            lien_choisir = f"/cgi-bin/liaison.py?uid={uid_encode}&source_id={oid}"
            # On conserve aussi le champ recherche (utile si on veut continuer)
            lien_choisir += "&recherche=" + urllib.parse.quote(recherche)

            print(f"""
                <div class="ligne-resultat">
                    <div>
                        <strong>{echapper_html(onom)}</strong>
                        <span class="petit">(# {echapper_html(oid)})</span>
                    </div>
                    <a class="bouton" href="{lien_choisir}">Choisir</a>
                </div>
            """)
        print('</div>')
    else:
        print(f"""
            <div class="message bad" style="margin-top:12px;">
                Aucun resultat pour "{echapper_html(recherche)}".
            </div>
        """)

        # Suggestions cliquables (si dispo)
        if liste_suggestions:
            print('<div class="suggestions">')
            for s in liste_suggestions:
                lien_s = f"/cgi-bin/liaison.py?uid={uid_encode}&recherche={urllib.parse.quote(s)}"
                # On conserve source_id si present
                if source_id is not None:
                    lien_s += "&source_id=" + str(source_id)
                print(f'<a class="suggestion" href="{lien_s}">{echapper_html(s)}</a>')
            print('</div>')

print("""
        </div>
""")

# ============================================================
# Carte 2: Ajout + liste des liaisons (si source selectionne)
# ============================================================
print("""
        <!-- ===================================================
             Carte 2: Creer / voir les liaisons
             =================================================== -->
        <div class="carte">
            <h2>2) Creer et gerer les liaisons</h2>
""")

# Si pas d'objet source selectionne, on affiche une explication
if not objet_source:
    print("""
            <div class="message">
                Selectionne un objet source a gauche pour afficher et creer des liaisons.
            </div>
        </div>
    </div>
""")
else:
    # Formulaire ajout liaison (GET)
    print(f"""
            <!-- Formulaire ajout liaison -->
            <form method="get" action="/cgi-bin/liaison.py">
                <!-- Toujours conserver uid -->
                <input type="hidden" name="uid" value="{echapper_html(uid)}">

                <!-- Action ajoute -->
                <input type="hidden" name="action" value="ajouter">

                <!-- Objet source selectionne -->
                <input type="hidden" name="source_id" value="{echapper_html(objet_source[0])}">

                <!-- On conserve recherche pour confort -->
                <input type="hidden" name="recherche" value="{echapper_html(recherche)}">

                <label class="label">Type de cible</label>
                <select class="champ-select" name="cible_type">
                    <option value="Objet">Objet</option>
                    <option value="Evenement">Evenement</option>
                    <option value="Psychologie">Psychologie</option>
                    <option value="Lieu">Lieu</option>
                    <option value="Autre">Autre</option>
                </select>

                <label class="label">Nom de la cible (texte libre)</label>
                <input class="champ-texte" type="text" name="cible_nom"
                       placeholder="Ex: Tableau, Guerre froide, Peur du vide...">

                <label class="label">Type de lien</label>
                <select class="champ-select" name="lien_type">
                    <option value="associe">associe</option>
                    <option value="compose">compose</option>
                    <option value="depend">depend</option>
                    <option value="influence">influence</option>
                    <option value="cause">cause</option>
                    <option value="oppose">oppose</option>
                    <option value="amplifie">amplifie</option>
                    <option value="attenue">attenue</option>
                </select>

                <label class="label">Poids / coefficient (ex: 1.0)</label>
                <input class="champ-texte" type="text" name="poids" value="1.0"
                       placeholder="1.0">

                <label class="label">Commentaire (optionnel)</label>
                <input class="champ-texte" type="text" name="commentaire"
                       placeholder="Note libre...">

                <div class="ligne-actions">
                    <button class="bouton" type="submit">Ajouter la liaison</button>
                </div>
            </form>

            <!-- Liste des liaisons existantes -->
            <h2 style="margin-top:22px;">Liaisons de "{echapper_html(objet_source[1])}"</h2>
    """)

    # Si aucune liaison, message sobre
    if not liaisons_source:
        print("""
            <div class="message">
                Aucune liaison pour cet objet (pour l'instant).
            </div>
        """)
    else:
        # Tableau des liaisons
        print("""
            <table class="table">
                <tr>
                    <th>Cible</th>
                    <th>Type de lien</th>
                    <th>Poids</th>
                    <th>Commentaire</th>
                    <th></th>
                </tr>
        """)

        for (lid, ctype, cnom, ltype, poids, comm, datec) in liaisons_source:
            # Lien suppression = action=supprimer + liaison_id + conserver uid + source_id
            lien_suppr = (
                f"/cgi-bin/liaison.py?uid={uid_encode}"
                f"&action=supprimer"
                f"&liaison_id={lid}"
                f"&source_id={objet_source[0]}"
            )
            # On conserve recherche (pour confort)
            if recherche:
                lien_suppr += "&recherche=" + urllib.parse.quote(recherche)

            cible_aff = f"{ctype} : {cnom}"                                     # Texte cible
            poids_aff = "" if poids is None else str(poids)                     # Affichage poids

            print(f"""
                <tr>
                    <td>{echapper_html(cible_aff)}</td>
                    <td>{echapper_html(ltype)}</td>
                    <td>{echapper_html(poids_aff)}</td>
                    <td>{echapper_html(comm)}</td>
                    <td><a class="lien-supprimer" href="{lien_suppr}">Supprimer</a></td>
                </tr>
            """)

        print("""
            </table>
        """)

    # Fermetures bloc droite + grille + panel
    print("""
        </div>
    </div>

    <div class="note-bas">
        Idee: la table "liaisons" est la base pour Simulation Three (propagation, dependances, effets).
    </div>

</div>

</body>
</html>
""")

# ============================================================
# Fermeture connexion sqlite (propre)
# ============================================================
connexion.close()
