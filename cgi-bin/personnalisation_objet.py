# Script CGI execute par le serveur web
# Encodage UTF-8 pour accepter les accents

import os  # Acces aux variables d'environnement et chemins
import sqlite3  # Acces a la base SQLite
import urllib.parse  # Lecture / encodage des parametres URL
import difflib  # Recherche floue (similarite entre chaines)
import html  # Echappement HTML (anti-injection)

print("Content-Type: text/html; charset=utf-8\n")  # En-tete HTTP obligatoire pour un CGI

UNIVERSE_DIR = "cgi-bin/universes/"  # Dossier contenant les BDD des univers

# ---------------------------
# Utils (parametres / securite / BDD)
# ---------------------------

def lire_parametre_get(name, default=""):  # Fonction: lire un parametre GET dans l'URL
    qs = os.environ.get("QUERY_STRING", "")  # Recupere la query string brute
    params = urllib.parse.parse_qs(qs, keep_blank_values=True)  # Parse les parametres ?a=...&b=...
    return params.get(name, [default])[0]  # Renvoie la premiere valeur ou le defaut

def chemin_univers(universe_id):  # Fonction: construit le chemin du fichier .db d'un univers
    safe = "".join([c for c in universe_id if c.isalnum() or c in ("-", "_")])  # Nettoie l'ID (anti-chemin)
    return os.path.join(UNIVERSE_DIR, f"universe_{safe}.db")  # Chemin final vers la BDD

def echapper_html(s):  # Fonction: echappe une valeur pour l'afficher en HTML sans risque
    return html.escape("" if s is None else str(s))  # Transforme en string + escape HTML

def assurer_colonne(db_path, table, col_name, col_def_sql):  # Fonction: s'assure qu'une colonne existe
    conn = None  # Variable connexion (pour fermer proprement)
    try:  # Bloc protegeant contre les erreurs
        conn = sqlite3.connect(db_path)  # Ouvre la connexion SQLite
        cur = conn.cursor()  # Cree un curseur
        cur.execute(f"PRAGMA table_info({table})")  # Liste les colonnes de la table
        cols = [r[1] for r in cur.fetchall()]  # Extrait les noms de colonnes
        if col_name not in cols:  # Si la colonne n'existe pas
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def_sql}")  # Ajoute la colonne
            conn.commit()  # Valide la modification
        return True  # Ok
    except Exception:  # Si erreur (table inexistante, fichier manquant, etc.)
        return False  # Echec
    finally:  # Toujours execute
        if conn is not None:  # Si connexion ouverte
            conn.close()  # Ferme la connexion

def assurer_id_stat_rempli(db_path):  # Fonction: garantit id_stat existe et est rempli pour les anciennes lignes
    conn = None  # Variable connexion
    try:  # Bloc protegeant contre les erreurs
        conn = sqlite3.connect(db_path)  # Ouvre SQLite
        cur = conn.cursor()  # Cree un curseur

        cur.execute("PRAGMA table_info(stat_objects)")  # Liste colonnes de stat_objects
        cols = [r[1] for r in cur.fetchall()]  # Recupere noms colonnes
        if "id_stat" not in cols:  # Si la colonne id_stat n'existe pas
            cur.execute("ALTER TABLE stat_objects ADD COLUMN id_stat INTEGER")  # Ajoute id_stat
            conn.commit()  # Valide

        cur.execute("UPDATE stat_objects SET id_stat = rowid WHERE id_stat IS NULL")  # Remplit id_stat manquant
        conn.commit()  # Valide la mise a jour
        return True  # Ok
    except Exception:  # Si erreur
        return False  # Echec
    finally:  # Toujours execute
        if conn is not None:  # Si connexion ouverte
            conn.close()  # Ferme

def lire_colonnes_stat_objects(db_path):  # Fonction: recupere la liste des colonnes de stat_objects
    conn = None  # Variable connexion
    try:  # Bloc protegeant
        conn = sqlite3.connect(db_path)  # Ouvre SQLite
        cur = conn.cursor()  # Curseur
        cur.execute("PRAGMA table_info(stat_objects)")  # Colonnes
        cols = [r[1] for r in cur.fetchall()]  # Noms colonnes
        return cols  # Retourne la liste
    except Exception:  # Si erreur
        return []  # Liste vide
    finally:  # Toujours execute
        if conn is not None:  # Si connexion ouverte
            conn.close()  # Ferme

def trouver_colonne_nom(columns):  # Fonction: tente de trouver la colonne "nom d'objet"
    for c in columns:  # Parcourt toutes les colonnes
        cl = c.lower()  # Version minuscule
        if ("objet" in cl) or ("nom" in cl) or ("name" in cl) or ("designation" in cl):  # Heuristique nom
            return c  # Retourne la meilleure colonne
    return columns[1] if len(columns) > 1 else (columns[0] if columns else None)  # Secours

def trouver_colonne_type(columns):  # Fonction: tente de trouver la colonne de type
    for c in columns:  # Parcourt
        if c.lower() in ("type", "types"):  # Match exact courant
            return c  # Ok
    for c in columns:  # Deuxieme passe
        if "type" in c.lower():  # Match partiel
            return c  # Ok
    return None  # Introuvable

def trouver_colonne_famille(columns):  # Fonction: tente de trouver la colonne famille
    for c in columns:  # Parcourt
        if "famil" in c.lower():  # Match sur "famil" (famille/family)
            return c  # Ok
    return None  # Introuvable

def trouver_colonne_prix(columns):  # Fonction: tente de trouver la colonne prix
    for c in columns:  # Parcourt
        cl = c.lower()  # Minuscule
        if ("prix" in cl) or ("price" in cl):  # Match prix/price
            return c  # Ok
    return None  # Introuvable

# ---------------------------
# Search (inclut TOUT, y compris objets crees et lies)
# Cle de selection: rowid (fiable).
# ---------------------------

def chercher_objets_flou(db_path, search_term):  # Fonction: recherche floue dans stat_objects
    try:  # Bloc protegeant
        conn = sqlite3.connect(db_path)  # Ouvre SQLite
        cur = conn.cursor()  # Curseur

        cols = lire_colonnes_stat_objects(db_path)  # Recupere colonnes de stat_objects
        if not cols:  # Si table introuvable / vide
            conn.close()  # Ferme
            return []  # Rien

        name_col = trouver_colonne_nom(cols)  # Trouve la colonne nom
        if not name_col:  # Si introuvable
            conn.close()  # Ferme
            return []  # Rien

        cur.execute(f"SELECT rowid, [{name_col}] FROM stat_objects")  # Prend rowid + nom
        all_objects = cur.fetchall()  # Liste (rowid, nom)
        conn.close()  # Ferme (important en CGI)

        if not search_term or len(search_term.strip()) < 2:  # Meme regle: pas de recherche < 2 caracteres
            return []  # Rien

        st = search_term.lower().strip()  # Normalise le terme
        matches = []  # Resultats
        for rid, oname in all_objects:  # Parcourt tous les objets
            if oname is None:  # Ignore les noms nuls
                continue  # Suite
            ratio = difflib.SequenceMatcher(None, st, str(oname).lower()).ratio()  # Similarite 0..1
            if ratio > 0.3:  # Meme seuil que ton code
                matches.append((rid, oname, ratio))  # Stocke match

        matches.sort(key=lambda x: x[2], reverse=True)  # Tri par score
        return matches[:8]  # Top 8 (meme limite)
    except Exception:  # Si erreur
        return []  # Rien

# ---------------------------
# Counts parsing (compact)
# Format: "rowid:qty,rowid:qty"
# Exemple: "12:3,7:1"
# ---------------------------

def parse_counts(compact_str):  # Fonction: transforme "12:3,7:1" en dict {12:3, 7:1}
    counts = {}  # Dictionnaire resultat
    if not compact_str:  # Si vide
        return counts  # Retourne vide
    parts = [p.strip() for p in compact_str.split(",") if p.strip()]  # Separe par virgule + nettoie
    for p in parts:  # Parcourt chaque morceau
        if ":" not in p:  # Si format invalide
            continue  # Ignore
        a, b = p.split(":", 1)  # Separe rowid et qty
        try:  # Conversion en int
            rid = int(a.strip())  # Rowid
            cnt = int(b.strip())  # Quantite
        except Exception:  # Si conversion impossible
            continue  # Ignore
        if cnt < 1:  # Regle: minimum 1
            cnt = 1  # Force a 1
        counts[rid] = cnt  # Stocke
    return counts  # Retour

# ---------------------------
# Compute aggregated row for ALL columns
# Regles:
# - fusion: somme des champs numeriques (avec qty), sinon "?"
# - moyenne: moyenne ponderee des champs numeriques (avec qty), sinon "?"
# - si aucune valeur numerique: "?"
# ---------------------------

def calculer_agregats(db_path, selected_counts, method):  # Fonction: calcule un dict col->valeur pour l'objet statistique
    # IMPORTANT: ici c'etait un bug dans ta version: lire_parametre_get(db_path) ne peut pas marcher.
    cols = lire_colonnes_stat_objects(db_path)  # Colonnes de stat_objects
    if not cols:  # Si rien
        return {}, []  # Retour vide

    conn = sqlite3.connect(db_path)  # Ouvre SQLite
    cur = conn.cursor()  # Curseur

    rowids = list(selected_counts.keys())  # Liste des rowid selectionnes
    if not rowids:  # Si rien
        conn.close()  # Ferme
        return {}, cols  # Retour

    placeholders = ",".join(["?"] * len(rowids))  # "?, ?, ?" pour la requete
    cur.execute(f"SELECT rowid, * FROM stat_objects WHERE rowid IN ({placeholders})", rowids)  # Recupere les lignes
    rows = cur.fetchall()  # Toutes les lignes selectionnees
    conn.close()  # Ferme

    data = {}  # Map rowid -> liste des valeurs (sans rowid)
    for r in rows:  # Parcourt chaque ligne
        rid = r[0]  # rowid
        data[rid] = list(r[1:])  # valeurs des colonnes

    agg = {}  # Dictionnaire resultat col -> valeur

    for i, col in enumerate(cols):  # Pour chaque colonne
        nums = []  # Valeurs numeriques * poids
        weights = []  # Poids
        for rid, w in selected_counts.items():  # Pour chaque objet selectionne
            if rid not in data:  # Si rowid absent (cas rare)
                continue  # Ignore
            v = data[rid][i] if i < len(data[rid]) else None  # Valeur de la colonne
            if isinstance(v, (int, float)):  # Regle: numeric uniquement
                nums.append(float(v) * float(w))  # Ajoute valeur ponderee
                weights.append(int(w))  # Ajoute poids

        if not nums:  # Si aucune valeur numerique
            agg[col] = "?"  # Impossible
            continue  # Colonne suivante

        total_sum = sum(nums)  # Somme ponderee
        total_w = sum(weights)  # Somme des poids

        if method == "fusion":  # Si fusion
            agg[col] = total_sum  # Somme
        else:  # Sinon moyenne ponderee
            agg[col] = (total_sum / float(total_w)) if total_w > 0 else "?"  # Moyenne

    return agg, cols  # Retourne dict + colonnes

def prochain_id_stat(db_path):  # Fonction: calcule le prochain id_stat
    conn = None  # Connexion
    try:  # Bloc protegeant
        conn = sqlite3.connect(db_path)  # Ouvre
        cur = conn.cursor()  # Curseur
        cur.execute("SELECT COALESCE(MAX(id_stat), 0) + 1 FROM stat_objects")  # Max + 1
        v = cur.fetchone()[0]  # Recupere le resultat
        return int(v)  # Renvoie int
    except Exception:  # Si erreur
        return None  # Pas d'id
    finally:  # Toujours execute
        if conn is not None:  # Si ouvert
            conn.close()  # Ferme

# ---------------------------
# creer_objet_statistique
# ---------------------------

def creer_objet_statistique(db_path, name, compact_counts, method):  # Fonction: cree un objet statistique en base
    counts = parse_counts(compact_counts)  # Parse la liste selectionnee
    if not counts:  # Si rien selectionne
        return False, "Aucun objet selectionne."  # Meme message

    # IMPORTANT: ici c'etait aussi un bug dans ta version: lire_parametre_get(db_path) ne peut pas marcher.
    cols = lire_colonnes_stat_objects(db_path)  # Colonnes stat_objects
    if not cols:  # Si table introuvable
        return False, "Table stat_objects introuvable."  # Meme message

    name_col = trouver_colonne_nom(cols)  # Colonne du nom
    type_col = trouver_colonne_type(cols)  # Colonne type
    family_col = trouver_colonne_famille(cols)  # Colonne famille
    price_col = trouver_colonne_prix(cols)  # Colonne prix (optionnelle)

    if not name_col:  # Si pas de colonne nom
        return False, "Colonne nom introuvable."  # Meme message

    agg, cols = calculer_agregats(db_path, counts, method)  # Calcule les champs agreges

    assurer_colonne(db_path, "stat_objects", "liaison", "TEXT DEFAULT 'null'")  # Garantit liaison
    assurer_id_stat_rempli(db_path)  # Garantit id_stat present + rempli

    agg[name_col] = name  # Force le nom de l'objet cree
    agg["liaison"] = "null"  # Force liaison a "null"

    new_id = prochain_id_stat(db_path)  # Prochain id_stat
    if new_id is not None:  # Si calcule
        agg["id_stat"] = new_id  # Applique

    if type_col:  # Si colonne type existe
        if method == "fusion":  # Si fusion
            agg[type_col] = "Fusion"  # Texte
        else:  # Sinon
            agg[type_col] = "Moyenne ponderee"  # Texte

    if family_col:  # Si colonne famille existe
        agg[family_col] = "Objet statistique"  # Force

    if price_col and price_col not in agg:  # Si prix existe mais pas calcule (cas securite)
        agg[price_col] = "?"  # Met "?"

    # IMPORTANT: on n'ecrase pas la premiere colonne d'origine (souvent un id/cle metier)
    if len(cols) >= 1:  # Si au moins une colonne
        cols_to_insert = cols[1:]  # On ignore cols[0]
    else:  # Sinon
        cols_to_insert = cols[:]  # Rien a ignorer

    insert_cols = []  # Colonnes a inserer
    insert_vals = []  # Valeurs a inserer

    for c in cols_to_insert:  # Parcourt les colonnes a inserer
        insert_cols.append(c)  # Ajoute la colonne
        insert_vals.append(agg.get(c, "?"))  # Ajoute la valeur ou "?"

    # Securite: si liaison/id_stat etaient dans cols mais pas dans cols_to_insert
    for extra in ("liaison", "id_stat"):  # Colonnes meta
        if extra in cols and extra not in cols_to_insert:  # Si existe et pas deja prevu
            insert_cols.append(extra)  # Ajoute colonne
            insert_vals.append(agg.get(extra, "?"))  # Ajoute valeur

    cols_sql = ",".join([f"[{c}]" for c in insert_cols])  # Colonnes entre crochets
    ph = ",".join(["?"] * len(insert_vals))  # Placeholders

    conn = None  # Connexion
    try:  # Bloc protegeant
        conn = sqlite3.connect(db_path)  # Ouvre
        cur = conn.cursor()  # Curseur
        cur.execute(f"INSERT INTO stat_objects ({cols_sql}) VALUES ({ph})", insert_vals)  # Insertion

        if method == "fusion":  # Si fusion
            if "liaison" in cols:  # Si colonne liaison existe
                cur.execute(  # Mise a jour liaison pour les objets utilises
                    f"UPDATE stat_objects SET liaison = ? WHERE rowid IN ({','.join(['?']*len(counts))})",
                    [f"lie a {name}"] + list(counts.keys())
                )

        conn.commit()  # Valide
        return True, "Objet cree avec succes !"  # Meme message
    except Exception as e:  # Si erreur SQL
        return False, f"Erreur: {e}"  # Meme format
    finally:  # Toujours execute
        if conn is not None:  # Si ouvert
            conn.close()  # Ferme

# ---------------------------
# Main (logique CGI)
# ---------------------------

universe_id = lire_parametre_get("uid", "")  # Recupere l'id de l'univers
action = lire_parametre_get("action", "")  # Recupere l'action demandee

db_path = chemin_univers(universe_id)  # Calcule le chemin du fichier .db

if universe_id:  # Si universe_id fourni
    assurer_colonne(db_path, "stat_objects", "liaison", "TEXT DEFAULT 'null'")  # S'assure liaison existe
    assurer_id_stat_rempli(db_path)  # S'assure id_stat existe et rempli

msg = ""  # Message a afficher
msg_class = "ok"  # Classe CSS du message

if action == "search":  # Mode "suggestions" (appel AJAX)
    term = lire_parametre_get("search", "")  # Terme de recherche
    results = chercher_objets_flou(db_path, term)  # Resultats
    if results:  # Si on a des suggestions
        for rid, oname, _ in results:  # Pour chaque suggestion
            safe_name = str(oname).replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')  # Echappe JS
            print(f"<div class='suggest-item' onclick=\"ajouter_objet({rid}, '{safe_name}')\">{echapper_html(oname)}</div>")  # HTML
    else:  # Sinon
        print("<div class='suggest-empty'>Aucune proposition</div>")  # Message vide
    raise SystemExit  # IMPORTANT: ne pas rendre la page complete en mode search

if action == "create":  # Mode creation d'objet
    new_name = lire_parametre_get("name", "").strip()  # Nom saisi
    counts_compact = lire_parametre_get("object_counts", "").strip()  # Liste compacte rowid:qty
    method = lire_parametre_get("method", "moyenne").strip()  # Methode (moyenne/fusion)

    if new_name and counts_compact:  # Si on a les infos
        ok, msg = creer_objet_statistique(db_path, new_name, counts_compact, method)  # Cree l'objet
        msg_class = "ok" if ok else "err"  # Classe du message
    else:  # Sinon
        msg = "Nom ou liste d'objets manquants."  # Message d'erreur
        msg_class = "err"  # Classe d'erreur

back_href = f"/cgi-bin/univers_dashboard.py?uid={urllib.parse.quote(universe_id)}"  # Lien retour

# ---------------------------
# HTML (page complete)
# ---------------------------

print(f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Creation d'objet statistique</title>

<style>
/* ------------------------------------------------------------
   THEME GLOBAL
   - fond + texte
   - harmonise avec vos pages "panel"
------------------------------------------------------------ */
:root {{
    --txt: #ffffff;
    --muted: rgba(255,255,255,0.75);
    --panel-bg: rgba(0,0,0,0.40);
    --line: rgba(255,255,255,0.10);
    --focus: rgba(255, 232, 180, 0.85); /* petit rappel "jaune" */
    --btn: rgba(74, 42, 80, 0.92);
    --btn-hover: rgba(94, 52, 102, 0.95);
    --danger: #a83434;
}}

body {{
    margin: 0; /* Supprime les marges par defaut */
    font-family: Arial, sans-serif; /* Police simple */
    color: var(--txt); /* Texte blanc */
    background-image: url('/create_stat_object.png'); /* Image de fond */
    background-size: cover; /* Remplit l'ecran */
    background-position: center; /* Centre */
    background-repeat: no-repeat; /* Pas de repetition */
    min-height: 100vh; /* Hauteur mini */
}}

/* ------------------------------------------------------------
   BOUTON RETOUR (jaune) - plus petit + hover propre
------------------------------------------------------------ */
.back-btn {{
    position: fixed; /* Reste visible */
    top: 18px; /* Marge haut */
    left: 18px; /* Marge gauche */
    width: 52px; /* Plus petit qu'avant */
    height: 52px; /* Plus petit qu'avant */
    display: block; /* Bloc */
    background: url('/back_btn_jaune.png') no-repeat center; /* Image bouton */
    background-size: contain; /* Contient */
    transition: transform 0.18s ease, filter 0.18s ease; /* Animation douce */
    filter: drop-shadow(0 6px 14px rgba(0,0,0,0.45)); /* Ombre */
    z-index: 999; /* Au dessus du panel */
}}
.back-btn:hover {{
    transform: scale(1.08); /* Petit zoom, pas agressif */
    filter: drop-shadow(0 8px 18px rgba(0,0,0,0.55)) brightness(1.05);
}}

/* ------------------------------------------------------------
   PANNEAU CENTRAL
------------------------------------------------------------ */
.panel {{
    width: 920px; /* Largeur stable */
    margin: 72px auto; /* Centre + espace top */
    background: url('/fond_filtre_pannel.png') no-repeat center; /* Panel */
    background-size: 100% 100%; /* Etire */
    padding: 46px 52px; /* Air autour */
    border-radius: 22px; /* Arrondis */
    box-sizing: border-box; /* Evite debordement */
}}

/* Titre */
h1 {{
    text-align: center; /* Centre */
    margin: 0 0 22px 0; /* Espace dessous */
    letter-spacing: 0.3px; /* Micro style */
}}

/* ------------------------------------------------------------
   FORMULAIRES / CHAMPS
------------------------------------------------------------ */
label {{
    display:block; /* Sur une ligne */
    margin: 14px 0 8px; /* Espace */
    font-weight: bold; /* Gras */
    color: var(--txt); /* Blanc */
}}

input[type=text] {{
    width: 100%; /* Pleine largeur */
    padding: 12px 14px; /* Confort */
    border-radius: 12px; /* Arrondi moderne */
    border: 1px solid rgba(255,255,255,0.10); /* Bordure douce */
    background: rgba(0,0,0,0.38); /* Fond sombre */
    color: var(--txt); /* Texte blanc */
    outline: none; /* Pas de contour bleu */
    font-size: 14px; /* Taille */
    box-sizing: border-box; /* Stable */
}}
input[type=text]::placeholder {{
    color: rgba(255,255,255,0.55); /* Placeholder doux */
}}
input[type=text]:focus {{
    border-color: rgba(255,232,180,0.55); /* Focus jaune doux */
    box-shadow: 0 0 0 3px rgba(255,232,180,0.14); /* Halo */
}}

select {{
    width: 100%; /* Pleine largeur */
    padding: 12px 14px; /* Confort */
    border-radius: 12px; /* Arrondi */
    border: 1px solid rgba(255,255,255,0.10); /* Bordure */
    background: rgba(0,0,0,0.38); /* Fond */
    color: var(--txt); /* Texte */
    outline: none; /* Pas de contour */
    box-sizing: border-box; /* Stable */
}}
select:focus {{
    border-color: rgba(255,232,180,0.55); /* Focus */
    box-shadow: 0 0 0 3px rgba(255,232,180,0.14); /* Halo */
}}

/* ------------------------------------------------------------
   SUGGESTIONS (resultats de recherche)
------------------------------------------------------------ */
#suggestions {{
    margin-top: 10px; /* Espace */
    background: rgba(0,0,0,0.42); /* Fond */
    border: 1px solid rgba(255,255,255,0.08); /* Bordure douce */
    border-radius: 14px; /* Arrondi */
    padding: 8px; /* Air */
    min-height: 24px; /* Hauteur mini */
}}

.suggest-item {{
    padding: 10px 12px; /* Zone cliquable */
    border-radius: 12px; /* Arrondi */
    cursor: pointer; /* Main */
    transition: background 0.12s ease, transform 0.12s ease; /* Hover doux */
}}
.suggest-item:hover {{
    background: rgba(255,255,255,0.08); /* Hover */
    transform: translateY(-1px); /* Micro lift */
}}

.suggest-empty {{
    color: rgba(255,255,255,0.60); /* Texte doux */
    font-size: 12px; /* Petit */
    padding: 8px 10px; /* Air */
}}

/* ------------------------------------------------------------
   LISTE DES OBJETS SELECTIONNES
------------------------------------------------------------ */
.selected-box {{
    margin-top: 22px; /* Espace */
    padding: 16px; /* Air */
    background: rgba(0,0,0,0.36); /* Fond */
    border: 1px solid rgba(255,255,255,0.08); /* Bordure */
    border-radius: 16px; /* Arrondi */
}}

.selected-item {{
    display:flex; /* Ligne */
    justify-content: space-between; /* Bouton a droite */
    align-items:center; /* Alignement */
    background: rgba(255,255,255,0.06); /* Fond item */
    border: 1px solid rgba(255,255,255,0.08); /* Bordure item */
    border-radius: 14px; /* Arrondi */
    padding: 10px 12px; /* Air */
    margin-top: 10px; /* Espace */
}}

.left {{
    display:flex; /* Ligne */
    align-items:center; /* Centrage */
    gap: 10px; /* Espacement */
    min-width: 0; /* Pour eviter debordement */
}}

.left b {{
    display:block; /* Bloc */
    max-width: 380px; /* Coupe les noms trop longs */
    white-space: nowrap; /* Sur une ligne */
    overflow: hidden; /* Cache */
    text-overflow: ellipsis; /* ... */
}}

.badge {{
    display:inline-block; /* Petit badge */
    padding: 4px 10px; /* Air */
    border-radius: 999px; /* Pilule */
    background: rgba(255,232,180,0.16); /* Jaune doux */
    border: 1px solid rgba(255,232,180,0.22); /* Bordure */
    font-size: 12px; /* Petit */
    color: rgba(255,232,180,0.95); /* Texte jaune */
}}

.qty {{
    width: 80px; /* Largeur */
    padding: 7px 8px; /* Air */
    border-radius: 12px; /* Arrondi */
    border: 1px solid rgba(255,255,255,0.10); /* Bordure */
    outline: none; /* Pas de contour */
    background: rgba(0,0,0,0.32); /* Fond */
    color: var(--txt); /* Texte */
}}

.btn-del {{
    background: rgba(168,52,52,0.95); /* Rouge */
    color: white; /* Texte */
    border: none; /* Pas de bordure */
    border-radius: 12px; /* Arrondi */
    padding: 9px 14px; /* Air */
    cursor:pointer; /* Main */
    transition: transform 0.12s ease, filter 0.12s ease; /* Hover */
}}
.btn-del:hover {{
    transform: scale(1.03); /* Petit zoom */
    filter: brightness(1.05); /* Leger */
}}

/* ------------------------------------------------------------
   BOUTON PRINCIPAL (creer)
------------------------------------------------------------ */
.btn-main {{
    width: 100%; /* Pleine largeur */
    margin-top: 18px; /* Espace */
    padding: 13px 18px; /* Air */
    border-radius: 14px; /* Arrondi */
    border: none; /* Sans bordure */
    cursor:pointer; /* Main */
    background: var(--btn); /* Violet */
    color:white; /* Blanc */
    font-weight:bold; /* Gras */
    letter-spacing: 0.2px; /* Micro style */
    transition: transform 0.12s ease, background 0.12s ease, filter 0.12s ease; /* Hover */
}}
.btn-main:hover {{
    background: var(--btn-hover); /* Violet hover */
    transform: translateY(-1px); /* Lift */
    filter: brightness(1.03); /* Leger */
}}

/* ------------------------------------------------------------
   MESSAGE (OK / ERREUR)
------------------------------------------------------------ */
.msg {{
    margin-top: 16px; /* Espace */
    padding: 12px 14px; /* Air */
    border-radius: 14px; /* Arrondi */
    text-align:center; /* Centre */
    border: 1px solid rgba(255,255,255,0.10); /* Bordure */
}}
.msg.ok {{
    background: rgba(0,128,0,0.28); /* Vert transparent */
}}
.msg.err {{
    background: rgba(128,0,0,0.28); /* Rouge transparent */
}}

/* ------------------------------------------------------------
   LIEN "liste des objets"
------------------------------------------------------------ */
.lien-liste {{
    display:inline-block; /* Bloc cliquable */
    margin-top: 18px; /* Espace */
    padding: 10px 14px; /* Air */
    border-radius: 12px; /* Arrondi */
    background: rgba(0,0,0,0.30); /* Fond */
    border: 1px solid rgba(255,255,255,0.10); /* Bordure */
    color: rgba(255,255,255,0.92); /* Texte */
    text-decoration:none; /* Pas de soulignement */
    font-weight: bold; /* Gras */
    transition: transform 0.12s ease, background 0.12s ease; /* Hover */
}}
.lien-liste:hover {{
    background: rgba(0,0,0,0.42); /* Hover */
    transform: translateY(-1px); /* Lift */
}}
</style>

<script>
/* ------------------------------------------------------------
   JS (logique identique)
   - juste renommage en francais (variables + fonctions)
------------------------------------------------------------ */

var objets_selectionnes = {{}};  // Dictionnaire: rowid -> {{ nom, quantite }}

function rafraichir_champ_cache() {{
    var morceaux = [];
    for (var k in objets_selectionnes) {{
        if (!objets_selectionnes.hasOwnProperty(k)) continue;
        var v = parseInt(objets_selectionnes[k].quantite, 10);
        if (isNaN(v) || v < 1) v = 1;
        morceaux.push(k + ":" + v);
    }}
    document.getElementById("object_counts").value = morceaux.join(",");
}}

function afficher_selection() {{
    var box = document.getElementById("selected_list");
    box.innerHTML = "";

    var cles = Object.keys(objets_selectionnes);
    if (cles.length === 0) {{
        box.innerHTML = "<div style='color:rgba(255,255,255,0.65)'>Aucun objet selectionne.</div>";
        rafraichir_champ_cache();
        return;
    }}

    cles.sort(function(a,b){{ return parseInt(a,10) - parseInt(b,10); }});

    for (var i=0;i<cles.length;i++) {{
        var id = cles[i];
        var item = objets_selectionnes[id];

        var row = document.createElement("div");
        row.className = "selected-item";

        var left = document.createElement("div");
        left.className = "left";

        var nom = document.createElement("div");
        nom.innerHTML = "<b>" + item.nom + "</b>";

        var badge = document.createElement("span");
        badge.className = "badge";
        badge.textContent = "x" + item.quantite;

        var qty = document.createElement("input");
        qty.type = "number";
        qty.min = "1";
        qty.className = "qty";
        qty.value = item.quantite;
        qty.onchange = (function(monId) {{
            return function() {{
                var v = parseInt(this.value, 10);
                if (isNaN(v) || v < 1) v = 1;
                objets_selectionnes[monId].quantite = v;
                afficher_selection();
            }};
        }})(id);

        left.appendChild(nom);
        left.appendChild(badge);
        left.appendChild(qty);

        var del = document.createElement("button");
        del.className = "btn-del";
        del.type = "button";
        del.textContent = "Supprimer";
        del.onclick = (function(monId) {{
            return function() {{
                delete objets_selectionnes[monId];
                afficher_selection();
            }};
        }})(id);

        row.appendChild(left);
        row.appendChild(del);

        box.appendChild(row);
    }}

    rafraichir_champ_cache();
}}

function ajouter_objet(rowid, nom) {{
    var id = String(rowid);
    if (objets_selectionnes[id]) {{
        objets_selectionnes[id].quantite = parseInt(objets_selectionnes[id].quantite, 10) + 1;
    }} else {{
        objets_selectionnes[id] = {{ nom: nom, quantite: 1 }};
    }}
    afficher_selection();
}}

function lancer_recherche() {{
    var q = document.getElementById("search").value;
    var xhr = new XMLHttpRequest();
    xhr.open("GET", "?uid={echapper_html(universe_id)}&action=search&search=" + encodeURIComponent(q), true);
    xhr.onreadystatechange = function() {{
        if (xhr.readyState === 4 && xhr.status === 200) {{
            document.getElementById("suggestions").innerHTML = xhr.responseText;
        }}
    }};
    xhr.send();
}}

function initialiser_page() {{
    afficher_selection();
}}
</script>

</head>
<body onload="initialiser_page()">

<a class="back-btn" href="{echapper_html(back_href)}" title="Retour"></a>

<div class="panel">
    <h1>Creation d'objet statistique</h1>

    <label>Nom de l'objet :</label>
    <input type="text" id="name" placeholder="Ex: Ecole, Bureau, etc.">

    <label>Rechercher des objets :</label>
    <input type="text" id="search" placeholder="Chercher un objet..." onkeyup="lancer_recherche()">

    <div id="suggestions"></div>

    <div class="selected-box">
        <b>Objets selectionnes :</b>
        <div id="selected_list" style="margin-top:10px;"></div>
    </div>

    <label>Methode :</label>
    <select id="method">
        <option value="moyenne">Moyenne ponderee</option>
        <option value="fusion">Fusion (liaison)</option>
    </select>

    <form method="GET" action="" style="margin-top:6px;">
        <input type="hidden" name="uid" value="{echapper_html(universe_id)}">
        <input type="hidden" name="action" value="create">
        <input type="hidden" name="name" id="hidden_name">
        <input type="hidden" name="method" id="hidden_method">
        <input type="hidden" name="object_counts" id="object_counts" value="">
        <button type="submit" class="btn-main" onclick="
            document.getElementById('hidden_name').value = document.getElementById('name').value;
            document.getElementById('hidden_method').value = document.getElementById('method').value;
            rafraichir_champ_cache();
        ">Creer l'objet statistique</button>
    </form>

    {"<div class='msg " + echapper_html(msg_class) + "'>" + echapper_html(msg) + "</div>" if msg else ""}

    <div style="text-align:center;">
        <a class="lien-liste" href="/cgi-bin/liste_objets.py?uid={echapper_html(universe_id)}">Liste des objets crees</a>
    </div>
</div>

</body>
</html>
""")