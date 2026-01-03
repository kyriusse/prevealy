#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
liaison.py
----------
PAGE "LIAISON" (univers)

Objectif simple:
- ETAPE 1: construire un reseau (objets lies entre eux)
- ETAPE 2: creer un evenement qui impacte une selection
          -> propagation automatique sur tout le reseau

Contraintes:
- Sans JavaScript (formulaires GET + reload)
- Variables en francais
- Commentaires partout (sauf evidences)
"""

import os
import sqlite3
import urllib.parse
import html
import difflib


# ============================================================
# En-tete CGI obligatoire
# ============================================================
print("Content-Type: text/html; charset=utf-8\n")


# ============================================================
# Constantes
# ============================================================
DOSSIER_UNIVERS = "cgi-bin/universes/"


# ============================================================
# Utils: lire parametre GET
# ============================================================
def lire_parametre_get(nom, defaut=""):
    """Retourne la valeur GET (?nom=...) ou defaut si absent."""
    query_string = os.environ.get("QUERY_STRING", "")
    parametres = urllib.parse.parse_qs(query_string, keep_blank_values=True)
    return parametres.get(nom, [defaut])[0]


# ============================================================
# Utils: echappement HTML
# ============================================================
def echapper_html(texte):
    """Echappe un texte pour eviter d'injecter du HTML."""
    return html.escape("" if texte is None else str(texte))


# ============================================================
# Utils: chemin BDD univers
# ============================================================
def construire_chemin_univers(uid):
    """Construit le chemin de BDD univers avec uid nettoye."""
    uid_sain = "".join([c for c in uid if c.isalnum() or c in ("-", "_")])
    return os.path.join(DOSSIER_UNIVERS, "universe_" + uid_sain + ".db")


# ============================================================
# Utils: nom univers
# ============================================================
def recuperer_nom_univers(uid):
    """Lit univers_names.txt et renvoie le nom correspondant."""
    try:
        chemin_fichier = os.path.join(DOSSIER_UNIVERS, "univers_names.txt")
        if os.path.exists(chemin_fichier):
            with open(chemin_fichier, "r", encoding="utf-8") as f:
                for ligne in f:
                    if "," in ligne:
                        uid_lu, nom_lu = ligne.strip().split(",", 1)
                        if uid_lu == uid:
                            return nom_lu
    except Exception:
        pass
    return "Nom inconnu"


# ============================================================
# Utils: detecter colonnes stat_objects (id + Objet)
# ============================================================
def detecter_colonnes_stat_objects(connexion):
    """Detecte les colonnes clefs de stat_objects."""
    cur = connexion.cursor()
    cur.execute("PRAGMA table_info(stat_objects)")
    infos = cur.fetchall()

    colonne_id = None
    colonne_nom = None

    for col in infos:
        nom_col = col[1]
        nom_min = (nom_col or "").lower()
        if nom_min == "id":
            colonne_id = nom_col
        elif nom_min == "objet":
            colonne_nom = nom_col

    # Fallbacks si structure differente
    if colonne_id is None and infos:
        colonne_id = infos[0][1]
    if colonne_nom is None and len(infos) >= 2:
        colonne_nom = infos[1][1]

    return colonne_id, colonne_nom


# ============================================================
# Tables monde
# ============================================================
def creer_tables_monde_si_besoin(connexion):
    """Cree les tables reseau + evenements + impacts si elles n'existent pas."""
    cur = connexion.cursor()

    # Graphe objet <-> objet
    cur.execute("""
        CREATE TABLE IF NOT EXISTS liaisons_objets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_objet_id INTEGER NOT NULL,
            cible_objet_id INTEGER NOT NULL,
            type_lien TEXT NOT NULL DEFAULT 'associe',
            poids REAL NOT NULL DEFAULT 1.0,
            commentaire TEXT NOT NULL DEFAULT '',
            date_creation TEXT DEFAULT (datetime('now'))
        )
    """)

    # Definition evenements
    cur.execute("""
        CREATE TABLE IF NOT EXISTS evenements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            poids_global REAL NOT NULL DEFAULT 1.0,
            intensite REAL NOT NULL DEFAULT 1.0,
            duree INTEGER NOT NULL DEFAULT 1,
            probabilite REAL NOT NULL DEFAULT 1.0,
            tags TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            date_creation TEXT DEFAULT (datetime('now'))
        )
    """)

    # Impacts calcules d'un evenement sur le graphe (propagation)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS impacts_evenements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evenement_id INTEGER NOT NULL,
            objet_id INTEGER NOT NULL,
            niveau INTEGER NOT NULL DEFAULT 0,
            poids_final REAL NOT NULL DEFAULT 1.0,
            role TEXT NOT NULL DEFAULT 'impacte',
            origine TEXT NOT NULL DEFAULT 'direct',
            commentaire TEXT NOT NULL DEFAULT '',
            date_creation TEXT DEFAULT (datetime('now')),
            UNIQUE(evenement_id, objet_id)
        )
    """)

    connexion.commit()


# ============================================================
# Utils: objets
# ============================================================
def rechercher_objets(connexion, colonne_id, colonne_nom, texte, limite=25):
    """Recherche simple (LIKE) dans stat_objects."""
    cur = connexion.cursor()
    motif = "%" + (texte or "").strip() + "%"
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
    return cur.fetchall()


def recuperer_nom_objet(connexion, colonne_id, colonne_nom, objet_id):
    """Retourne le nom d'un objet (ou vide si introuvable)."""
    cur = connexion.cursor()
    cur.execute(
        f"SELECT [{colonne_nom}] FROM stat_objects WHERE [{colonne_id}] = ?",
        (objet_id,)
    )
    ligne = cur.fetchone()
    return ligne[0] if ligne and ligne[0] is not None else ""


def recuperer_tous_les_noms(connexion, colonne_nom):
    """Liste tous les noms (pour suggestions)."""
    cur = connexion.cursor()
    cur.execute(
        f"""
        SELECT [{colonne_nom}]
        FROM stat_objects
        WHERE [{colonne_nom}] IS NOT NULL
          AND TRIM([{colonne_nom}]) != ''
        """
    )
    return [r[0] for r in cur.fetchall()]


def suggestions_mot_proche(texte, noms, max_suggestions=8):
    """Suggestions proches, ex: stylode -> stylo."""
    if not texte:
        return []
    return difflib.get_close_matches(texte, noms, n=max_suggestions, cutoff=0.60)


# ============================================================
# Utils: IDs selection (GET)
# ============================================================
def ids_depuis_chaine(chaine):
    """Transforme '1,2,3' -> [1,2,3]."""
    resultat = []
    for morceau in (chaine or "").split(","):
        morceau = morceau.strip()
        if morceau.isdigit():
            v = int(morceau)
            if v not in resultat:
                resultat.append(v)
    return resultat


def chaine_depuis_ids(liste_ids):
    """Transforme [1,2,3] -> '1,2,3'."""
    return ",".join([str(x) for x in (liste_ids or [])])


# ============================================================
# Utils: reseau (liaisons)
# ============================================================
def ajouter_liaison_objets(connexion, source_id, cible_id, type_lien, poids, commentaire, symetrique=True):
    """Ajoute liaison source->cible, et aussi cible->source si symetrique."""
    cur = connexion.cursor()

    cur.execute(
        """
        INSERT INTO liaisons_objets (source_objet_id, cible_objet_id, type_lien, poids, commentaire)
        VALUES (?, ?, ?, ?, ?)
        """,
        (source_id, cible_id, type_lien, poids, commentaire)
    )

    if symetrique:
        cur.execute(
            """
            INSERT INTO liaisons_objets (source_objet_id, cible_objet_id, type_lien, poids, commentaire)
            VALUES (?, ?, ?, ?, ?)
            """,
            (cible_id, source_id, type_lien, poids, commentaire)
        )

    connexion.commit()


def lister_liaisons_objets(connexion, source_id):
    """Liste liaisons sortantes d'un objet source."""
    cur = connexion.cursor()
    cur.execute(
        """
        SELECT id, cible_objet_id, type_lien, poids, commentaire, date_creation
        FROM liaisons_objets
        WHERE source_objet_id = ?
        ORDER BY id DESC
        """,
        (source_id,)
    )
    return cur.fetchall()


def supprimer_liaison_objets(connexion, liaison_id):
    """Supprime une ligne de liaison."""
    cur = connexion.cursor()
    cur.execute("DELETE FROM liaisons_objets WHERE id = ?", (liaison_id,))
    connexion.commit()


def voisins_objet(connexion, objet_id):
    """Retourne les voisins directs (niveau 1)."""
    cur = connexion.cursor()
    cur.execute(
        "SELECT cible_objet_id FROM liaisons_objets WHERE source_objet_id = ?",
        (objet_id,)
    )
    return [r[0] for r in cur.fetchall()]


# ============================================================
# Utils: evenements + impacts
# ============================================================
def creer_evenement(connexion, nom, poids_global, intensite, duree, probabilite, tags, description):
    """Cree un evenement et renvoie son id."""
    cur = connexion.cursor()
    cur.execute(
        """
        INSERT INTO evenements (nom, poids_global, intensite, duree, probabilite, tags, description)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (nom, poids_global, intensite, duree, probabilite, tags, description)
    )
    connexion.commit()
    return cur.lastrowid


def lister_evenements(connexion, limite=80):
    """Liste les evenements recents."""
    cur = connexion.cursor()
    cur.execute(
        """
        SELECT id, nom, poids_global, intensite, duree, probabilite, tags, date_creation
        FROM evenements
        ORDER BY id DESC
        LIMIT ?
        """,
        (limite,)
    )
    return cur.fetchall()


def lister_impacts_evenement(connexion, evenement_id):
    """Liste les impacts d'un evenement."""
    cur = connexion.cursor()
    cur.execute(
        """
        SELECT id, objet_id, niveau, poids_final, role, origine, commentaire, date_creation
        FROM impacts_evenements
        WHERE evenement_id = ?
        ORDER BY niveau ASC, poids_final DESC
        """,
        (evenement_id,)
    )
    return cur.fetchall()


def supprimer_impact(connexion, impact_id):
    """Supprime un impact."""
    cur = connexion.cursor()
    cur.execute("DELETE FROM impacts_evenements WHERE id = ?", (impact_id,))
    connexion.commit()


def ecrire_impact(connexion, evenement_id, objet_id, niveau, poids_final, role, origine, commentaire):
    """
    Ecrit (ou met a jour) un impact UNIQUE(evenement_id, objet_id).
    Regle:
    - garder le niveau le plus faible
    - garder le poids_final le plus fort
    """
    cur = connexion.cursor()

    cur.execute(
        """
        INSERT OR IGNORE INTO impacts_evenements (evenement_id, objet_id, niveau, poids_final, role, origine, commentaire)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (evenement_id, objet_id, niveau, poids_final, role, origine, commentaire)
    )

    cur.execute(
        """
        UPDATE impacts_evenements
        SET
          niveau = CASE WHEN ? < niveau THEN ? ELSE niveau END,
          poids_final = CASE WHEN ? > poids_final THEN ? ELSE poids_final END
        WHERE evenement_id = ? AND objet_id = ?
        """,
        (niveau, niveau, poids_final, poids_final, evenement_id, objet_id)
    )

    connexion.commit()


# ============================================================
# Propagation (BFS)
# ============================================================
def calculer_propagation(connexion, objets_depart, poids_depart, profondeur_max, attenuation):
    """
    Propagation sur le graphe:
    - niveau 0 = objets_depart
    - voisins niveau 1, etc.
    - poids_final = poids_depart * (attenuation ** niveau)
    """
    if profondeur_max < 0:
        profondeur_max = 0
    if attenuation < 0:
        attenuation = 0.0
    if attenuation > 1.0:
        attenuation = 1.0

    resultat = {}  # objet_id -> (niveau, poids_final)
    file_bfs = []  # (objet_id, niveau)

    for oid in objets_depart:
        resultat[oid] = (0, poids_depart)
        file_bfs.append((oid, 0))

    while file_bfs:
        objet_courant, niveau_courant = file_bfs.pop(0)

        if niveau_courant >= profondeur_max:
            continue

        niveau_suivant = niveau_courant + 1
        poids_suivant = poids_depart * (attenuation ** niveau_suivant)

        for voisin in voisins_objet(connexion, objet_courant):
            if voisin is None:
                continue

            if voisin not in resultat:
                resultat[voisin] = (niveau_suivant, poids_suivant)
                file_bfs.append((voisin, niveau_suivant))
            else:
                ancien_niveau, ancien_poids = resultat[voisin]
                if niveau_suivant < ancien_niveau:
                    resultat[voisin] = (niveau_suivant, poids_suivant)
                    file_bfs.append((voisin, niveau_suivant))
                elif niveau_suivant == ancien_niveau and poids_suivant > ancien_poids:
                    resultat[voisin] = (niveau_suivant, poids_suivant)

    return resultat


# ============================================================
# Contexte univers
# ============================================================
uid = lire_parametre_get("uid", "").strip()
if not uid:
    print("<h1>Erreur : univers non specifie</h1>")
    raise SystemExit

uid_encode = urllib.parse.quote(uid)
nom_univers = recuperer_nom_univers(uid)

chemin_bdd = construire_chemin_univers(uid)
if not os.path.exists(chemin_bdd):
    print("<h1>Erreur : BDD univers introuvable</h1>")
    print("<p>Chemin attendu : " + echapper_html(chemin_bdd) + "</p>")
    raise SystemExit

connexion = sqlite3.connect(chemin_bdd)
creer_tables_monde_si_besoin(connexion)

colonne_id, colonne_nom = detecter_colonnes_stat_objects(connexion)
if not colonne_id or not colonne_nom:
    print("<h1>Erreur : stat_objects invalide</h1>")
    connexion.close()
    raise SystemExit


# ============================================================
# Parametres UI
# ============================================================
action = lire_parametre_get("action", "").strip()

recherche_objet = lire_parametre_get("recherche_objet", "").strip()

selection_ids_texte = lire_parametre_get("selection_ids", "").strip()
selection_ids = ids_depuis_chaine(selection_ids_texte)

objet_source_str = lire_parametre_get("objet_source_id", "").strip()
objet_source_id = int(objet_source_str) if objet_source_str.isdigit() else None

evenement_id_str = lire_parametre_get("evenement_id", "").strip()
evenement_id = int(evenement_id_str) if evenement_id_str.isdigit() else None

evenement_choisi_str = lire_parametre_get("evenement_choisi_id", "").strip()
evenement_choisi_id = int(evenement_choisi_str) if evenement_choisi_str.isdigit() else None


# ============================================================
# Messages utilisateur
# ============================================================
message_ok = ""
message_erreur = ""


# ============================================================
# Actions: selection
# ============================================================
if action == "ajouter_selection":
    oid_str = lire_parametre_get("objet_ajout_id", "").strip()
    if oid_str.isdigit():
        oid = int(oid_str)
        if oid not in selection_ids:
            selection_ids.append(oid)
        message_ok = "Objet ajoute a la selection."
    else:
        message_erreur = "Objet invalide (ajout selection)."

if action == "retirer_selection":
    oid_str = lire_parametre_get("objet_retire_id", "").strip()
    if oid_str.isdigit():
        oid = int(oid_str)
        selection_ids = [x for x in selection_ids if x != oid]
        message_ok = "Objet retire de la selection."
    else:
        message_erreur = "Objet invalide (retrait selection)."

if action == "definir_source":
    oid_str = lire_parametre_get("objet_source_nouveau_id", "").strip()
    if oid_str.isdigit():
        objet_source_id = int(oid_str)
        objet_source_str = str(objet_source_id)
        message_ok = "Objet source defini."
    else:
        message_erreur = "Objet invalide (definir source)."

# Mise a jour chaine selection
selection_ids_texte = chaine_depuis_ids(selection_ids)


# ============================================================
# Action: lier objets
# ============================================================
if action == "lier_objets":
    type_lien = lire_parametre_get("type_lien", "associe").strip()
    poids_str = lire_parametre_get("poids_liaison", "1.0").strip()
    commentaire = lire_parametre_get("commentaire_liaison", "").strip()

    if objet_source_id is None:
        message_erreur = "Etape 1: definis d'abord un objet source (bouton 'Definir source')."
    elif not selection_ids:
        message_erreur = "Etape 1: selection vide. Ajoute des objets avec 'Ajouter'."
    else:
        try:
            poids = float(poids_str.replace(",", "."))
        except Exception:
            poids = 1.0

        try:
            nb = 0
            for cible_id in selection_ids:
                if cible_id != objet_source_id:
                    ajouter_liaison_objets(connexion, objet_source_id, cible_id, type_lien, poids, commentaire, symetrique=True)
                    nb += 1
            message_ok = "Liaisons creees : " + str(nb)
        except Exception as e:
            message_erreur = "Erreur creation liaisons : " + str(e)


# ============================================================
# Action: supprimer liaison
# ============================================================
if action == "supprimer_liaison_objet":
    liaison_id_str = lire_parametre_get("liaison_id", "").strip()
    if liaison_id_str.isdigit():
        try:
            supprimer_liaison_objets(connexion, int(liaison_id_str))
            message_ok = "Liaison supprimee."
        except Exception as e:
            message_erreur = "Erreur suppression : " + str(e)
    else:
        message_erreur = "Id liaison invalide."


# ============================================================
# Parametres evenement (lecture)
# ============================================================
nom_evenement = lire_parametre_get("nom_evenement", "").strip()
poids_global_str = lire_parametre_get("poids_global", "1.0").strip()
intensite_str = lire_parametre_get("intensite", "1.0").strip()

# Options avancees
duree_str = lire_parametre_get("duree", "1").strip()
probabilite_str = lire_parametre_get("probabilite", "1.0").strip()
tags = lire_parametre_get("tags", "").strip()
description = lire_parametre_get("description", "").strip()

# Propagation
role = lire_parametre_get("role", "impacte").strip()
poids_lien_str = lire_parametre_get("poids_lien", "1.0").strip()
profondeur_max_str = lire_parametre_get("profondeur_max", "5").strip()
attenuation_str = lire_parametre_get("attenuation", "0.70").strip()

# Preview calcule uniquement si demande
preview_impacts = None

# Conversions robustes
try:
    poids_global = float(poids_global_str.replace(",", "."))
except Exception:
    poids_global = 1.0

try:
    intensite = float(intensite_str.replace(",", "."))
except Exception:
    intensite = 1.0

try:
    duree = int(duree_str)
except Exception:
    duree = 1

try:
    probabilite = float(probabilite_str.replace(",", "."))
except Exception:
    probabilite = 1.0

try:
    poids_lien = float(poids_lien_str.replace(",", "."))
except Exception:
    poids_lien = 1.0

try:
    profondeur_max = int(profondeur_max_str)
except Exception:
    profondeur_max = 5

try:
    attenuation = float(attenuation_str.replace(",", "."))
except Exception:
    attenuation = 0.70

# Poids depart reel (niveau 0)
poids_depart = poids_global * intensite * poids_lien


# ============================================================
# Actions evenement
# ============================================================
if action == "previsualiser_evenement":
    if not selection_ids:
        message_erreur = "Etape 2: preview impossible, selection vide."
    else:
        preview_impacts = calculer_propagation(connexion, selection_ids, poids_depart, profondeur_max, attenuation)
        message_ok = "Preview: " + str(len(preview_impacts)) + " objets impactes."

if action == "creer_evenement":
    if not nom_evenement:
        message_erreur = "Etape 2: nom evenement manquant."
    elif not selection_ids:
        message_erreur = "Etape 2: selection vide."
    else:
        try:
            nouvel_id = creer_evenement(connexion, nom_evenement, poids_global, intensite, duree, probabilite, tags, description)

            impacts = calculer_propagation(connexion, selection_ids, poids_depart, profondeur_max, attenuation)

            for oid, (niv, poids_calcule) in impacts.items():
                origine = "direct" if niv == 0 else "propagation"
                commentaire_impact = "selection" if niv == 0 else "auto"
                ecrire_impact(connexion, nouvel_id, oid, niv, poids_calcule, role, origine, commentaire_impact)

            evenement_id = nouvel_id
            evenement_id_str = str(nouvel_id)
            message_ok = "Evenement cree: " + nom_evenement + " (impacts: " + str(len(impacts)) + ")"
        except Exception as e:
            message_erreur = "Erreur creation evenement : " + str(e)

if action == "ouvrir_evenement":
    if evenement_choisi_id is not None:
        evenement_id = evenement_choisi_id
        evenement_id_str = str(evenement_choisi_id)
        message_ok = "Evenement ouvert."
    else:
        message_erreur = "Choisis un evenement dans la liste."

if action == "supprimer_impact":
    impact_id_str = lire_parametre_get("impact_id", "").strip()
    if impact_id_str.isdigit():
        try:
            supprimer_impact(connexion, int(impact_id_str))
            message_ok = "Impact supprime."
        except Exception as e:
            message_erreur = "Erreur suppression impact : " + str(e)
    else:
        message_erreur = "Id impact invalide."


# ============================================================
# Donnees affichage: recherche + suggestions
# ============================================================
resultats_recherche = []
liste_suggestions = []

if recherche_objet:
    try:
        resultats_recherche = rechercher_objets(connexion, colonne_id, colonne_nom, recherche_objet, limite=25)
    except Exception:
        resultats_recherche = []

    if not resultats_recherche:
        try:
            noms = recuperer_tous_les_noms(connexion, colonne_nom)
            liste_suggestions = suggestions_mot_proche(recherche_objet, noms, max_suggestions=8)
        except Exception:
            liste_suggestions = []


# ============================================================
# Donnees affichage: source + liaisons
# ============================================================
nom_objet_source = ""
liaisons_objets_source = []

if objet_source_id is not None:
    nom_objet_source = recuperer_nom_objet(connexion, colonne_id, colonne_nom, objet_source_id)
    try:
        liaisons_objets_source = lister_liaisons_objets(connexion, objet_source_id)
    except Exception:
        liaisons_objets_source = []


# ============================================================
# Donnees affichage: evenements + impacts
# ============================================================
liste_evenements = []
try:
    liste_evenements = lister_evenements(connexion, limite=80)
except Exception:
    liste_evenements = []

impacts_evenement = []
if evenement_id is not None:
    try:
        impacts_evenement = lister_impacts_evenement(connexion, evenement_id)
    except Exception:
        impacts_evenement = []


# ============================================================
# Nom evenement ouvert (pour resume)
# ============================================================
nom_evenement_ouvert = ""
if evenement_id is not None:
    for (eid, nom_evt, pg, it, du, pr, tg, dc) in liste_evenements:
        if eid == evenement_id:
            nom_evenement_ouvert = nom_evt
            break


# ============================================================
# Resume
# ============================================================
texte_source_resume = "Aucun"
if objet_source_id is not None:
    texte_source_resume = nom_objet_source + " (#" + str(objet_source_id) + ")"

texte_selection_resume = str(len(selection_ids)) + " objet(s)"

texte_evt_resume = "Aucun"
if evenement_id is not None and nom_evenement_ouvert:
    texte_evt_resume = nom_evenement_ouvert + " (#" + str(evenement_id) + ")"


# ============================================================
# HTML / CSS (mystique + simplifie)
# ============================================================
print(f"""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Liaison - {echapper_html(nom_univers)}</title>

<style>
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
  content:"";
  position:fixed; top:0; left:0; right:0; bottom:0;
  pointer-events:none;
  background: radial-gradient(900px 500px at 50% 30%, rgba(255,255,255,0.04), rgba(0,0,0,0) 60%);
  opacity:0.60;
}}

.bouton-retour {{
  position: fixed;
  top: 20px;
  left: 20px;
  width: 64px;
  height: 64px;
  background: url('/back_btn_violet.png') no-repeat center/contain;
}}

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
}}

.panel {{
  width: 1280px;
  margin: 55px auto;
  padding: 54px;
  box-sizing: border-box;
  border-radius: 30px;
  background: rgba(14, 6, 26, 0.72);
  border: 1px solid rgba(255,216,106,0.20);
  box-shadow: 0 30px 70px rgba(0,0,0,0.62);
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
  grid-template-columns: 1.05fr 0.95fr;
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
  box-shadow: 0 18px 36px rgba(0,0,0,0.50);
}}

.carte h2 {{
  margin: 0 0 12px 0;
  font-size: 18px;
}}

.label {{
  display:block;
  margin: 10px 0 6px 0;
  font-size: 12px;
  opacity: 0.90;
}}

.champ-texte, .champ-select, textarea {{
  width: 100%;
  box-sizing: border-box;
  padding: 12px;
  border-radius: 14px;
  background: rgba(0,0,0,0.28);
  color: #ffffff;
  border: 1px solid rgba(255,255,255,0.12);
  outline: none;
}}
textarea {{ min-height: 80px; resize: vertical; }}

.ligne-actions {{
  margin-top: 14px;
  display:flex;
  gap: 10px;
  justify-content: flex-end;
  align-items:center;
  flex-wrap: wrap;
}}

.bouton {{
  display:inline-block;
  padding: 10px 18px;
  border-radius: 999px;
  text-decoration:none;
  font-size: 13px;
  cursor:pointer;
  color: #FFD86A;
  background: rgba(255,216,106,0.12);
  border: 1px solid rgba(255,216,106,0.38);
}}
.bouton-secondaire {{
  color: rgba(255,255,255,0.88);
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.14);
}}

.zone-resultats {{
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(0,0,0,0.22);
  border: 1px solid rgba(255,255,255,0.10);
  max-height: 250px;
  overflow: auto;
}}

.ligne-resultat {{
  display:flex;
  justify-content: space-between;
  align-items:center;
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
  display:flex;
  flex-wrap: wrap;
  gap: 8px;
}}

.suggestion {{
  display:inline-block;
  padding: 8px 12px;
  border-radius: 999px;
  text-decoration:none;
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
  text-align:left;
  padding: 10px 8px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  vertical-align: top;
}}

.lien-supprimer {{
  color: rgba(255,170,170,0.95);
  text-decoration:none;
  border: 1px solid rgba(255,120,120,0.30);
  padding: 6px 10px;
  border-radius: 999px;
  display:inline-block;
}}

.resume {{
  display:grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
  margin-top: 18px;
}}
.bloc-resume {{
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(0,0,0,0.22);
  border: 1px solid rgba(255,255,255,0.10);
}}
details {{
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(0,0,0,0.18);
  border: 1px solid rgba(255,255,255,0.10);
}}
summary {{
  cursor: pointer;
  color: rgba(255,255,255,0.90);
}}
</style>
</head>

<body>

<a class="bouton-retour" href="/cgi-bin/univers_dashboard.py?uid={uid_encode}" title="Retour"></a>
<a class="bouton-simulation" href="/cgi-bin/simulation.py?uid={uid_encode}" title="Menu Simulation">Menu Simulation</a>

<div class="panel">
  <h1>Liaison</h1>

  <div class="ligne-univers">
    Univers : <strong>{echapper_html(nom_univers)}</strong>
    &nbsp;|&nbsp; ID : {echapper_html(uid)}
  </div>
""")

# Messages
if message_ok:
    print(f'<div class="message ok">{echapper_html(message_ok)}</div>')
if message_erreur:
    print(f'<div class="message bad">{echapper_html(message_erreur)}</div>')

# Resume
print(f"""
  <div class="resume">
    <div class="bloc-resume">
      <div class="petit">Source (pour lier)</div>
      <div><strong>{echapper_html(texte_source_resume)}</strong></div>
    </div>
    <div class="bloc-resume">
      <div class="petit">Selection (utilisee partout)</div>
      <div><strong>{echapper_html(texte_selection_resume)}</strong></div>
    </div>
    <div class="bloc-resume">
      <div class="petit">Evenement ouvert</div>
      <div><strong>{echapper_html(texte_evt_resume)}</strong></div>
    </div>
  </div>

  <div class="grille">
    <!-- Colonne gauche -->
    <div class="carte">
      <h2>0) Trouver des objets</h2>

      <form method="get" action="/cgi-bin/liaison.py">
        <input type="hidden" name="uid" value="{echapper_html(uid)}">
        <input type="hidden" name="selection_ids" value="{echapper_html(selection_ids_texte)}">
        <input type="hidden" name="objet_source_id" value="{echapper_html(objet_source_str)}">
        <input type="hidden" name="evenement_id" value="{echapper_html(evenement_id_str)}">

        <label class="label">Recherche</label>
        <input class="champ-texte" type="text" name="recherche_objet"
               value="{echapper_html(recherche_objet)}"
               placeholder="Ex: ecole, tableau, stylo...">

        <div class="ligne-actions">
          <button class="bouton" type="submit">Chercher</button>
          <a class="bouton bouton-secondaire" href="/cgi-bin/liaison.py?uid={uid_encode}">Reset</a>
        </div>
      </form>
""")

# Resultats recherche
if recherche_objet:
    if resultats_recherche:
        print('<div class="zone-resultats">')
        for (oid, onom) in resultats_recherche:
            lien_ajout = (
                f"/cgi-bin/liaison.py?uid={uid_encode}"
                f"&action=ajouter_selection"
                f"&objet_ajout_id={oid}"
                f"&recherche_objet={urllib.parse.quote(recherche_objet)}"
                f"&selection_ids={urllib.parse.quote(selection_ids_texte)}"
                f"&objet_source_id={urllib.parse.quote(objet_source_str)}"
                f"&evenement_id={urllib.parse.quote(evenement_id_str)}"
            )
            lien_source = (
                f"/cgi-bin/liaison.py?uid={uid_encode}"
                f"&action=definir_source"
                f"&objet_source_nouveau_id={oid}"
                f"&recherche_objet={urllib.parse.quote(recherche_objet)}"
                f"&selection_ids={urllib.parse.quote(selection_ids_texte)}"
                f"&evenement_id={urllib.parse.quote(evenement_id_str)}"
            )
            print(f"""
              <div class="ligne-resultat">
                <div>
                  <strong>{echapper_html(onom)}</strong>
                  <span class="petit">(# {echapper_html(oid)})</span>
                </div>
                <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
                  <a class="bouton bouton-secondaire" href="{lien_source}">Definir source</a>
                  <a class="bouton" href="{lien_ajout}">Ajouter</a>
                </div>
              </div>
            """)
        print("</div>")
    else:
        print(f'<div class="message bad">Aucun resultat pour "{echapper_html(recherche_objet)}".</div>')
        if liste_suggestions:
            print('<div class="suggestions">')
            for s in liste_suggestions:
                lien_s = (
                    f"/cgi-bin/liaison.py?uid={uid_encode}"
                    f"&recherche_objet={urllib.parse.quote(s)}"
                    f"&selection_ids={urllib.parse.quote(selection_ids_texte)}"
                    f"&objet_source_id={urllib.parse.quote(objet_source_str)}"
                    f"&evenement_id={urllib.parse.quote(evenement_id_str)}"
                )
                print(f'<a class="suggestion" href="{lien_s}">{echapper_html(s)}</a>')
            print("</div>")

# Selection
print("<h2 style='margin-top:22px;'>Selection</h2>")
print('<div class="message">La selection sert a: lier, preview, creer evenement.</div>')
if not selection_ids:
    print('<div class="message">Selection vide.</div>')
else:
    print('<div class="zone-resultats">')
    for oid in selection_ids:
        nom_o = recuperer_nom_objet(connexion, colonne_id, colonne_nom, oid)
        lien_retire = (
            f"/cgi-bin/liaison.py?uid={uid_encode}"
            f"&action=retirer_selection"
            f"&objet_retire_id={oid}"
            f"&recherche_objet={urllib.parse.quote(recherche_objet)}"
            f"&selection_ids={urllib.parse.quote(selection_ids_texte)}"
            f"&objet_source_id={urllib.parse.quote(objet_source_str)}"
            f"&evenement_id={urllib.parse.quote(evenement_id_str)}"
        )
        print(f"""
          <div class="ligne-resultat">
            <div>
              <strong>{echapper_html(nom_o)}</strong>
              <span class="petit">(# {echapper_html(oid)})</span>
            </div>
            <a class="bouton bouton-secondaire" href="{lien_retire}">Retirer</a>
          </div>
        """)
    print("</div>")

print("""
    </div>

    <!-- Colonne droite -->
    <div>
      <div class="carte">
        <h2>1) Lier des objets (reseau)</h2>
        <div class="message">1) Definis une source  2) Ajoute des objets  3) Clique "Lier".</div>
""")

# Bloc source
if objet_source_id is None:
    print('<div class="message bad">Aucun objet source. Utilise "Definir source" dans les resultats.</div>')
else:
    print(f'<div class="message ok">Source : <strong>{echapper_html(nom_objet_source)}</strong> <span class="petit">(# {echapper_html(objet_source_id)})</span></div>')

# Form liaison
print(f"""
        <form method="get" action="/cgi-bin/liaison.py" style="margin-top:12px;">
          <input type="hidden" name="uid" value="{echapper_html(uid)}">
          <input type="hidden" name="action" value="lier_objets">
          <input type="hidden" name="selection_ids" value="{echapper_html(selection_ids_texte)}">
          <input type="hidden" name="recherche_objet" value="{echapper_html(recherche_objet)}">
          <input type="hidden" name="objet_source_id" value="{echapper_html(objet_source_str)}">
          <input type="hidden" name="evenement_id" value="{echapper_html(evenement_id_str)}">

          <label class="label">Type de lien</label>
          <select class="champ-select" name="type_lien">
            <option value="associe">associe</option>
            <option value="compose">compose</option>
            <option value="depend">depend</option>
            <option value="influence">influence</option>
            <option value="cause">cause</option>
            <option value="oppose">oppose</option>
          </select>

          <details>
            <summary>Options (facultatif)</summary>
            <label class="label">Poids de liaison</label>
            <input class="champ-texte" type="text" name="poids_liaison" value="1.0">

            <label class="label">Commentaire</label>
            <input class="champ-texte" type="text" name="commentaire_liaison" placeholder="Optionnel">
          </details>

          <div class="ligne-actions">
            <button class="bouton" type="submit">Lier la selection a la source</button>
          </div>
        </form>
""")

# Liste liaisons source
if objet_source_id is not None:
    if not liaisons_objets_source:
        print('<div class="message" style="margin-top:10px;">Aucune liaison pour ce source.</div>')
    else:
        print('<details style="margin-top:12px;">')
        print('<summary>Voir les liaisons du source</summary>')
        print('<table class="table">')
        print('<tr><th>Cible</th><th>Type</th><th>Poids</th><th></th></tr>')
        for (lid, cible_id, type_lien, poids, comm, datec) in liaisons_objets_source:
            nom_cible = recuperer_nom_objet(connexion, colonne_id, colonne_nom, cible_id)
            lien_suppr = (
                f"/cgi-bin/liaison.py?uid={uid_encode}"
                f"&action=supprimer_liaison_objet"
                f"&liaison_id={lid}"
                f"&selection_ids={urllib.parse.quote(selection_ids_texte)}"
                f"&recherche_objet={urllib.parse.quote(recherche_objet)}"
                f"&objet_source_id={urllib.parse.quote(objet_source_str)}"
                f"&evenement_id={urllib.parse.quote(evenement_id_str)}"
            )
            print(f"""
              <tr>
                <td>{echapper_html(nom_cible)} <span class="petit">(# {echapper_html(cible_id)})</span></td>
                <td>{echapper_html(type_lien)}</td>
                <td>{echapper_html(poids)}</td>
                <td><a class="lien-supprimer" href="{lien_suppr}">Supprimer</a></td>
              </tr>
            """)
        print("</table>")
        print("</details>")

# ETAPE 2
print(f"""
      </div>

      <div class="carte" style="margin-top:20px;">
        <h2>2) Evenements (impact + propagation)</h2>
        <div class="message">Selection = objets touches (niveau 0). Propagation calculee ensuite.</div>

        <form method="get" action="/cgi-bin/liaison.py">
          <input type="hidden" name="uid" value="{echapper_html(uid)}">
          <input type="hidden" name="selection_ids" value="{echapper_html(selection_ids_texte)}">
          <input type="hidden" name="recherche_objet" value="{echapper_html(recherche_objet)}">
          <input type="hidden" name="objet_source_id" value="{echapper_html(objet_source_str)}">
          <input type="hidden" name="action" value="ouvrir_evenement">

          <label class="label">Evenement a ouvrir</label>
          <select class="champ-select" name="evenement_choisi_id">
""")

# Options du dropdown evenements
if liste_evenements:
    for (eid, nom_evt, pg, it, du, pr, tg, dc) in liste_evenements:
        sel = "selected" if evenement_id == eid else ""
        print(f'<option value="{eid}" {sel}>{echapper_html(nom_evt)} (# {eid})</option>')
else:
    print('<option value="">Aucun evenement</option>')

print(f"""
          </select>

          <div class="ligne-actions">
            <button class="bouton bouton-secondaire" type="submit">Ouvrir</button>
          </div>
        </form>

        <h2 style="margin-top:18px;">Creer un evenement</h2>

        <form method="get" action="/cgi-bin/liaison.py">
          <input type="hidden" name="uid" value="{echapper_html(uid)}">
          <input type="hidden" name="selection_ids" value="{echapper_html(selection_ids_texte)}">
          <input type="hidden" name="recherche_objet" value="{echapper_html(recherche_objet)}">
          <input type="hidden" name="objet_source_id" value="{echapper_html(objet_source_str)}">
          <input type="hidden" name="evenement_id" value="{echapper_html(evenement_id_str)}">

          <label class="label">Nom</label>
          <input class="champ-texte" type="text" name="nom_evenement" value="{echapper_html(nom_evenement)}" placeholder="Ex: Guerre froide">

          <label class="label">Poids global</label>
          <input class="champ-texte" type="text" name="poids_global" value="{echapper_html(poids_global_str)}">

          <label class="label">Intensite</label>
          <input class="champ-texte" type="text" name="intensite" value="{echapper_html(intensite_str)}">

          <details>
            <summary>Options avancees (facultatif)</summary>

            <label class="label">Duree</label>
            <input class="champ-texte" type="text" name="duree" value="{echapper_html(duree_str)}">

            <label class="label">Probabilite (0..1)</label>
            <input class="champ-texte" type="text" name="probabilite" value="{echapper_html(probabilite_str)}">

            <label class="label">Tags</label>
            <input class="champ-texte" type="text" name="tags" value="{echapper_html(tags)}">

            <label class="label">Description</label>
            <textarea name="description">{echapper_html(description)}</textarea>

            <label class="label">Role</label>
            <select class="champ-select" name="role">
              <option value="impacte" {"selected" if role=="impacte" else ""}>impacte</option>
              <option value="cause" {"selected" if role=="cause" else ""}>cause</option>
              <option value="amplifie" {"selected" if role=="amplifie" else ""}>amplifie</option>
              <option value="attenue" {"selected" if role=="attenue" else ""}>attenue</option>
            </select>

            <label class="label">Poids sur selection (niveau 0)</label>
            <input class="champ-texte" type="text" name="poids_lien" value="{echapper_html(poids_lien_str)}">

            <label class="label">Profondeur max</label>
            <input class="champ-texte" type="text" name="profondeur_max" value="{echapper_html(profondeur_max_str)}">

            <label class="label">Attenuation (0..1)</label>
            <input class="champ-texte" type="text" name="attenuation" value="{echapper_html(attenuation_str)}">
          </details>

          <div class="ligne-actions">
            <button class="bouton bouton-secondaire" type="submit" name="action" value="previsualiser_evenement">Preview</button>
            <button class="bouton" type="submit" name="action" value="creer_evenement">Creer</button>
          </div>

          <div class="message" style="margin-top:10px;">
            Poids depart = poids_global * intensite * poids_lien, puis attenuation^niveau.
          </div>
        </form>
""")

# Preview impacts
if preview_impacts is not None:
    items = list(preview_impacts.items())
    items.sort(key=lambda x: (x[1][0], -x[1][1]))

    print('<details open style="margin-top:12px;">')
    print('<summary>Resultat du preview</summary>')
    print('<table class="table">')
    print('<tr><th>Objet</th><th>Niveau</th><th>Poids final</th></tr>')
    for oid, (niv, pfinal) in items[:150]:
        nom_o = recuperer_nom_objet(connexion, colonne_id, colonne_nom, oid)
        print(f"""
          <tr>
            <td>{echapper_html(nom_o)} <span class="petit">(# {echapper_html(oid)})</span></td>
            <td>{echapper_html(niv)}</td>
            <td>{echapper_html(round(pfinal, 6))}</td>
          </tr>
        """)
    print("</table>")
    if len(items) > 150:
        print('<div class="message">Preview limite a 150 lignes.</div>')
    print("</details>")

# Impacts evenement ouvert
if evenement_id is not None:
    if not impacts_evenement:
        print('<div class="message" style="margin-top:12px;">Aucun impact enregistre pour cet evenement.</div>')
    else:
        print('<details style="margin-top:12px;">')
        print('<summary>Voir les impacts enregistres de l evenement ouvert</summary>')
        print('<table class="table">')
        print('<tr><th>Objet</th><th>Niveau</th><th>Poids</th><th>Origine</th><th></th></tr>')
        for (iid, oid, niv, pfinal, r, origine, comm, dc) in impacts_evenement[:250]:
            nom_o = recuperer_nom_objet(connexion, colonne_id, colonne_nom, oid)
            lien_suppr = (
                f"/cgi-bin/liaison.py?uid={uid_encode}"
                f"&action=supprimer_impact"
                f"&impact_id={iid}"
                f"&evenement_id={evenement_id}"
                f"&selection_ids={urllib.parse.quote(selection_ids_texte)}"
                f"&recherche_objet={urllib.parse.quote(recherche_objet)}"
                f"&objet_source_id={urllib.parse.quote(objet_source_str)}"
            )
            print(f"""
              <tr>
                <td>{echapper_html(nom_o)} <span class="petit">(# {echapper_html(oid)})</span></td>
                <td>{echapper_html(niv)}</td>
                <td>{echapper_html(round(pfinal, 6))}</td>
                <td>{echapper_html(origine)}</td>
                <td><a class="lien-supprimer" href="{lien_suppr}">Supprimer</a></td>
              </tr>
            """)
        print("</table>")
        if len(impacts_evenement) > 250:
            print('<div class="message">Affichage limite a 250 lignes.</div>')
        print("</details>")

print("""
      </div>
    </div>
  </div>
</div>
</body>
</html>
""")

connexion.close()
