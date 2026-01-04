#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
liaison.py
----------
PAGE "LIAISON / RESEAUX" (univers)

Objectif (version "chef d'oeuvre NSI" mais simple a utiliser):
- Creer des liaisons entre "applicables" du meme type:
  - Type O: objets (table stat_objects)
  - Type E: evenements (table evenements, creee ici; evenement.py l'alimentera plus tard)
- Organiser automatiquement ces liaisons en RESEAUX (R1, R2, ...), stockes en base:
  - Un reseau = un groupe de liaisons connectees (composantes connexes)
  - Quand on ajoute une liaison, on:
      * cree un nouveau reseau si besoin
      * ou on etend un reseau existant
      * ou on fusionne 2 reseaux si la liaison relie 2 groupes differents
- Voir les reseaux sous forme "lisible" (texte) pour preparer la simulation.

Contraintes:
- CGI sans JavaScript (GET + reload)
- Variables / fonctions en francais
- Beaucoup de commentaires
- Donnees exploitables plus tard dans simulation (tables propres, champs stables)

Note architecture importante:
- La page "liaison" NE DECLENCHE RIEN.
- Elle construit uniquement la structure (reseaux + liaisons).
- L'execution / propagation / calculs seront faits plus tard dans les pages de simulation.
"""

import os
import sqlite3
import urllib.parse
import html
import datetime


# ============================================================
# En-tete CGI obligatoire (sinon page blanche)
# ============================================================
print("Content-Type: text/html; charset=utf-8\n")


# ============================================================
# Constantes projet
# ============================================================
DOSSIER_UNIVERS = "cgi-bin/universes/"  # Dossier contenant les BDD des univers


# ============================================================
# Utils: securite / params / format
# ============================================================
def lire_parametre_get(nom, defaut=""):
    """
    Lire un parametre GET (?nom=...).
    - keep_blank_values=True: permet de recuperer les champs vides
    """
    query_string = os.environ.get("QUERY_STRING", "")
    params = urllib.parse.parse_qs(query_string, keep_blank_values=True)
    return params.get(nom, [defaut])[0]


def echapper_html(texte):
    """Echappement HTML (anti-injection)."""
    return html.escape("" if texte is None else str(texte))


def encoder_url(texte):
    """Encodage URL (pour reinjecter des valeurs dans des liens)."""
    return urllib.parse.quote("" if texte is None else str(texte))


def ids_depuis_chaine(chaine):
    """Transformer '1,2,3' -> [1,2,3] en eliminant doublons."""
    resultat = []
    for morceau in (chaine or "").split(","):
        morceau = morceau.strip()
        if morceau.isdigit():
            v = int(morceau)
            if v not in resultat:
                resultat.append(v)
    return resultat


def chaine_depuis_ids(liste_ids):
    """Transformer [1,2,3] -> '1,2,3'."""
    return ",".join([str(x) for x in (liste_ids or [])])


def maintenant_texte():
    """Retourne un timestamp lisible (debug / affichage)."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ============================================================
# Utils: univers (chemin + nom)
# ============================================================
def construire_chemin_univers(uid):
    """
    Construit le chemin vers la BDD univers.
    Protection: on filtre uid pour empecher de viser un autre fichier via des caracteres bizarres.
    """
    uid_sain = "".join([c for c in uid if c.isalnum() or c in ("-", "_")])
    return os.path.join(DOSSIER_UNIVERS, "universe_" + uid_sain + ".db")


def recuperer_nom_univers(uid):
    """
    Lit univers_names.txt (format: uid,nom).
    Renvoie "Nom inconnu" si absent.
    """
    try:
        chemin_noms = os.path.join(DOSSIER_UNIVERS, "univers_names.txt")
        if os.path.exists(chemin_noms):
            with open(chemin_noms, "r", encoding="utf-8") as f:
                for ligne in f:
                    if "," in ligne:
                        uid_lu, nom_lu = ligne.strip().split(",", 1)
                        if uid_lu == uid:
                            return nom_lu
    except Exception:
        pass
    return "Nom inconnu"


# ============================================================
# BDD: detection colonnes stat_objects (id + Objet)
# ============================================================
def detecter_colonnes_stat_objects(connexion):
    """
    Detecter les colonnes principales de stat_objects:
    - colonne_id: idealement "id"
    - colonne_nom: idealement "Objet"
    Fallback: si les noms ne matchent pas, on prend les 2 premieres colonnes.
    """
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

    if colonne_id is None and infos:
        colonne_id = infos[0][1]
    if colonne_nom is None and len(infos) >= 2:
        colonne_nom = infos[1][1]

    return colonne_id, colonne_nom


# ============================================================
# BDD: creation tables (evenements + reseaux + liaisons)
# ============================================================
def creer_tables_si_besoin(connexion):
    """
    Tables creees ici car univers db peut etre vide au debut.

    1) evenements:
       - evenement.py alimentera plus tard
       - ici on a juste de quoi les lister / lier

    2) reseaux_applicables:
       - un reseau = un groupe de liaisons connectees
       - un reseau a un type ('O' ou 'E') pour separer objets/evenements

    3) liaisons_applicables:
       - stocke chaque liaison
       - reseau_id permet de regrouper / retrouver vite les reseaux
       - implication ('->' ou '<->') definit la direction
       - precision (type_lien, poids, commentaire) est optionnelle
    """
    cur = connexion.cursor()

    # Table evenements (minimaliste, stable pour futur)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS evenements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            type_evenement TEXT NOT NULL DEFAULT 'E',  -- E, Ec, Ep, Ea plus tard
            definir_comme_E INTEGER NOT NULL DEFAULT 1, -- 1 = visible en simulation
            description TEXT NOT NULL DEFAULT '',
            date_creation TEXT DEFAULT (datetime('now'))
        )
    """)

    # Table reseaux
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reseaux_applicables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type_applicable TEXT NOT NULL,             -- 'O' ou 'E'
            nom TEXT NOT NULL DEFAULT '',              -- optionnel (ex: "R1 - Economie")
            date_creation TEXT DEFAULT (datetime('now'))
        )
    """)

    # Table liaisons
    cur.execute("""
        CREATE TABLE IF NOT EXISTS liaisons_applicables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            type_applicable TEXT NOT NULL,             -- 'O' ou 'E'
            reseau_id INTEGER NOT NULL,                -- cle de regroupement

            source_id INTEGER NOT NULL,
            cible_id INTEGER NOT NULL,

            implication TEXT NOT NULL DEFAULT '->',     -- '->' (implication) / '<->' (equivalence)

            -- Precision optionnelle (si non maitrise, laisser valeurs par defaut)
            type_lien TEXT NOT NULL DEFAULT 'associe',  -- associe / depend / compose / etc.
            poids REAL NOT NULL DEFAULT 1.0,            -- coefficient de force (simulation plus tard)
            commentaire TEXT NOT NULL DEFAULT '',

            date_creation TEXT DEFAULT (datetime('now'))
        )
    """)

    # Index utiles (performance + futures simulations)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_liaisons_type_reseau ON liaisons_applicables(type_applicable, reseau_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_liaisons_source ON liaisons_applicables(type_applicable, source_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_liaisons_cible ON liaisons_applicables(type_applicable, cible_id)")

    connexion.commit()


# ============================================================
# BDD: objets (recherche + nom)
# ============================================================
def rechercher_objets(connexion, colonne_id, colonne_nom, texte, limite=25):
    """Recherche LIKE sur le nom d'objet dans stat_objects."""
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


def nom_objet_par_id(connexion, colonne_id, colonne_nom, objet_id):
    """Nom d'un objet via id."""
    cur = connexion.cursor()
    cur.execute(f"SELECT [{colonne_nom}] FROM stat_objects WHERE [{colonne_id}] = ?", (objet_id,))
    row = cur.fetchone()
    return row[0] if row and row[0] is not None else ""


# ============================================================
# BDD: evenements (recherche + nom)
# ============================================================
def rechercher_evenements(connexion, texte, limite=25):
    """Recherche LIKE sur le nom d'evenement."""
    cur = connexion.cursor()
    motif = "%" + (texte or "").strip() + "%"
    cur.execute(
        """
        SELECT id, nom, type_evenement
        FROM evenements
        WHERE nom IS NOT NULL
          AND TRIM(nom) != ''
          AND nom LIKE ?
        ORDER BY nom COLLATE NOCASE
        LIMIT ?
        """,
        (motif, limite)
    )
    return cur.fetchall()


def nom_evenement_par_id(connexion, evenement_id):
    """Nom d'un evenement via id."""
    cur = connexion.cursor()
    cur.execute("SELECT nom FROM evenements WHERE id = ?", (evenement_id,))
    row = cur.fetchone()
    return row[0] if row and row[0] is not None else ""


# ============================================================
# BDD: reseaux (creation / detection / fusion)
# ============================================================
def creer_reseau(connexion, type_applicable):
    """Creer un reseau et renvoyer son id."""
    cur = connexion.cursor()
    cur.execute("INSERT INTO reseaux_applicables (type_applicable, nom) VALUES (?, ?)", (type_applicable, ""))
    connexion.commit()
    return cur.lastrowid


def reseaux_pour_element(connexion, type_applicable, element_id):
    """
    Retourne la liste des reseau_id qui contiennent element_id.
    - element_id apparait soit en source_id soit en cible_id.
    Normalement, un element devrait se retrouver dans 0 ou 1 reseau,
    mais on reste robuste au cas ou.
    """
    cur = connexion.cursor()
    cur.execute(
        """
        SELECT DISTINCT reseau_id
        FROM liaisons_applicables
        WHERE type_applicable = ?
          AND (source_id = ? OR cible_id = ?)
        """,
        (type_applicable, element_id, element_id)
    )
    return [r[0] for r in cur.fetchall()]


def fusionner_reseaux(connexion, type_applicable, reseau_garde, reseau_supprime):
    """
    Fusion:
    - on met toutes les liaisons de reseau_supprime dans reseau_garde
    - on supprime la ligne reseau_supprime (propre)
    """
    cur = connexion.cursor()

    # Mise a jour des liaisons
    cur.execute(
        """
        UPDATE liaisons_applicables
        SET reseau_id = ?
        WHERE type_applicable = ? AND reseau_id = ?
        """,
        (reseau_garde, type_applicable, reseau_supprime)
    )

    # Suppression du reseau "vide" (ou devenu inutile)
    cur.execute(
        "DELETE FROM reseaux_applicables WHERE id = ? AND type_applicable = ?",
        (reseau_supprime, type_applicable)
    )

    connexion.commit()


def choisir_reseau_pour_nouvelle_liaison(connexion, type_applicable, source_id, cible_id):
    """
    Determine le reseau_id a utiliser lors de l'insertion d'une nouvelle liaison.

    Cas:
    - Aucun des deux n'est dans un reseau -> creer un nouveau reseau
    - Un seul est dans un reseau -> reutiliser ce reseau
    - Les deux sont dans des reseaux differents -> fusionner
    """
    reseaux_source = reseaux_pour_element(connexion, type_applicable, source_id)
    reseaux_cible = reseaux_pour_element(connexion, type_applicable, cible_id)

    # On prend des ensembles pour simplifier
    set_source = set(reseaux_source)
    set_cible = set(reseaux_cible)
    union = set_source.union(set_cible)

    if not union:
        # Aucun reseau existant -> nouveau
        return creer_reseau(connexion, type_applicable)

    if len(union) == 1:
        # Meme reseau (ou un seul cote)
        return list(union)[0]

    # Plusieurs reseaux -> fusion en gardant le plus petit id (choix stable)
    reseau_garde = min(union)
    for r in sorted(union):
        if r != reseau_garde:
            fusionner_reseaux(connexion, type_applicable, reseau_garde, r)

    return reseau_garde


# ============================================================
# BDD: liaisons (insert / delete / list)
# ============================================================
def inserer_liaison(connexion, type_applicable, reseau_id, source_id, cible_id,
                    implication, type_lien, poids, commentaire):
    """Insertion d'une liaison (simple) dans le reseau cible."""
    cur = connexion.cursor()
    cur.execute(
        """
        INSERT INTO liaisons_applicables (
            type_applicable, reseau_id,
            source_id, cible_id,
            implication, type_lien, poids, commentaire
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (type_applicable, reseau_id, source_id, cible_id, implication, type_lien, poids, commentaire)
    )
    connexion.commit()


def supprimer_liaison(connexion, type_applicable, liaison_id):
    """
    Supprime une liaison.
    Note:
    - On ne "redecoupe" pas les reseaux automatiquement (trop couteux / complexe)
    - La simulation peut ignorer les reseaux vides
    - Le menu "Voir reseaux" reste fiable, mais un reseau pourrait devenir "disperse"
      si on supprime beaucoup. (Cas rare / acceptable, ou on fera un "rebuild" plus tard.)
    """
    cur = connexion.cursor()
    cur.execute(
        "DELETE FROM liaisons_applicables WHERE type_applicable = ? AND id = ?",
        (type_applicable, liaison_id)
    )
    connexion.commit()


def lister_liaisons(connexion, type_applicable, limite=250):
    """Liste les liaisons recentes d'un type (O/E)."""
    cur = connexion.cursor()
    cur.execute(
        """
        SELECT id, reseau_id, source_id, cible_id, implication, type_lien, poids, commentaire, date_creation
        FROM liaisons_applicables
        WHERE type_applicable = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (type_applicable, limite)
    )
    return cur.fetchall()


def lister_reseaux_ids(connexion, type_applicable):
    """Liste les reseaux existants pour un type, tries par id."""
    cur = connexion.cursor()
    cur.execute(
        """
        SELECT id
        FROM reseaux_applicables
        WHERE type_applicable = ?
        ORDER BY id ASC
        """,
        (type_applicable,)
    )
    return [r[0] for r in cur.fetchall()]


def liaisons_par_reseau(connexion, type_applicable, reseau_id):
    """Retourne toutes les liaisons d'un reseau."""
    cur = connexion.cursor()
    cur.execute(
        """
        SELECT id, source_id, cible_id, implication, type_lien, poids, commentaire
        FROM liaisons_applicables
        WHERE type_applicable = ? AND reseau_id = ?
        ORDER BY id ASC
        """,
        (type_applicable, reseau_id)
    )
    return cur.fetchall()


# ============================================================
# "Voir reseaux": construction d'un texte lisible
# ============================================================
def nom_element(type_applicable, connexion, colonne_id_objet, colonne_nom_objet, element_id):
    """Nom lisible d'un element selon type (objet / evenement)."""
    if type_applicable == "O":
        n = nom_objet_par_id(connexion, colonne_id_objet, colonne_nom_objet, element_id)
        return (n or "").strip()
    n = nom_evenement_par_id(connexion, element_id)
    return (n or "").strip()


def resumer_reseau_lisible(type_applicable, connexion, colonne_id_objet, colonne_nom_objet, reseau_id):
    """
    Objectif: produire un rendu "humain" proche de ton exemple, sans graphe.

    Idee (simple mais efficace):
    - On cherche des "noeuds centraux" (cibles) recevant plusieurs implications '->'.
      Exemple: stylo->4c + mur->4c => cible centrale = 4c, sources = {stylo, mur}
    - On affiche d'abord ces groupes sous forme:
        S(a,b) -> C
      ou si une seule source:
        a -> C
    - Puis on affiche les equivalences (<->) rattachees:
        C <-> X

    Remarque:
    - Ce n'est pas un solveur parfait de graphes.
    - Mais c'est lisible, stable, et suffisant pour un "aperçu reseau".
    """
    liaisons = liaisons_par_reseau(connexion, type_applicable, reseau_id)
    if not liaisons:
        return "Reseau vide."

    # Comptage des implications vers chaque cible
    sources_par_cible = {}  # cible_id -> set(source_id)
    equivalences = []       # (a,b) pour <->

    for (_lid, sid, cid, impl, _tl, _pw, _comm) in liaisons:
        if impl == "<->":
            equivalences.append((sid, cid))
            # Une equivalence peut aussi servir de "connexion",
            # mais on la montrera a part pour garder un texte clair.
        else:
            sources_par_cible.setdefault(cid, set()).add(sid)

    # Cibles triees: celles qui ont le plus de sources en premier
    cibles_triees = sorted(sources_par_cible.keys(), key=lambda c: (-len(sources_par_cible[c]), c))

    # Construction de segments texte
    segments = []

    # On conserve un set des elements deja mentionnes (pour limiter les repetitions)
    deja = set()

    for cible_id in cibles_triees:
        sources = sorted(list(sources_par_cible[cible_id]))
        nom_cible = nom_element(type_applicable, connexion, colonne_id_objet, colonne_nom_objet, cible_id) or ("#" + str(cible_id))

        if len(sources) >= 2:
            noms_sources = []
            for sid in sources:
                noms_sources.append(nom_element(type_applicable, connexion, colonne_id_objet, colonne_nom_objet, sid) or ("#" + str(sid)))
                deja.add(sid)
            deja.add(cible_id)
            segments.append("S(" + ", ".join(noms_sources) + ") -> " + nom_cible)
        elif len(sources) == 1:
            sid = sources[0]
            nom_source = nom_element(type_applicable, connexion, colonne_id_objet, colonne_nom_objet, sid) or ("#" + str(sid))
            deja.add(sid)
            deja.add(cible_id)
            segments.append(nom_source + " -> " + nom_cible)

    # Ajout equivalences de facon simple
    # On essaye de les accrocher a un segment existant (si possible) en fin de phrase.
    for (a, b) in equivalences:
        nom_a = nom_element(type_applicable, connexion, colonne_id_objet, colonne_nom_objet, a) or ("#" + str(a))
        nom_b = nom_element(type_applicable, connexion, colonne_id_objet, colonne_nom_objet, b) or ("#" + str(b))
        deja.add(a)
        deja.add(b)

        # Si un des deux est deja mentionne, on affiche "X <-> Y" dans la suite
        segments.append(nom_a + " <-> " + nom_b)

    # Si segments est vide (cas: reseau uniquement en equivalences), on affiche les equivalences
    if not segments:
        if equivalences:
            segments = [ (nom_element(type_applicable, connexion, colonne_id_objet, colonne_nom_objet, a) or ("#" + str(a)))
                         + " <-> " +
                         (nom_element(type_applicable, connexion, colonne_id_objet, colonne_nom_objet, b) or ("#" + str(b)))
                         for (a, b) in equivalences ]
        else:
            segments = ["Reseau sans structure lisible."]

    # Assemblage final (style "R1: ...")
    texte = " ; ".join([s for s in segments if s.strip()])
    return texte if texte else "Reseau."


# ============================================================
# Chargement contexte univers
# ============================================================
uid = (lire_parametre_get("uid", "") or "").strip()
if not uid:
    print("<h1>Erreur : univers non specifie</h1>")
    raise SystemExit

uid_encode = encoder_url(uid)
nom_univers = recuperer_nom_univers(uid)

chemin_bdd = construire_chemin_univers(uid)
if not os.path.exists(chemin_bdd):
    print("<h1>Erreur : BDD univers introuvable</h1>")
    print("<p>Chemin attendu : " + echapper_html(chemin_bdd) + "</p>")
    raise SystemExit

connexion = sqlite3.connect(chemin_bdd)
creer_tables_si_besoin(connexion)

# Table objets requise si on veut lier des objets
colonne_id_objet, colonne_nom_objet = detecter_colonnes_stat_objects(connexion)
if not colonne_id_objet or not colonne_nom_objet:
    print("<h1>Erreur : table stat_objects invalide</h1>")
    connexion.close()
    raise SystemExit


# ============================================================
# Parametres UI (tout en GET)
# ============================================================
action = (lire_parametre_get("action", "") or "").strip()

# Mode reseau: O (objets) / E (evenements)
type_applicable = (lire_parametre_get("type_applicable", "O") or "O").strip().upper()
if type_applicable not in ("O", "E"):
    type_applicable = "O"

# Recherche unique (depend du mode)
texte_recherche = (lire_parametre_get("recherche", "") or "").strip()

# Source + cibles (liste)
source_id_str = (lire_parametre_get("source_id", "") or "").strip()
source_id = int(source_id_str) if source_id_str.isdigit() else None

cibles_ids_str = (lire_parametre_get("cibles_ids", "") or "").strip()
cibles_ids = ids_depuis_chaine(cibles_ids_str)

# Implication (obligatoire)
implication = (lire_parametre_get("implication", "->") or "->").strip()
if implication not in ("->", "<->"):
    implication = "->"

# Precision (optionnelle)
type_lien = (lire_parametre_get("type_lien", "associe") or "associe").strip()
poids_str = (lire_parametre_get("poids", "1.0") or "1.0").strip()
commentaire = (lire_parametre_get("commentaire", "") or "").strip()

# Convertir poids (robuste)
try:
    poids = float(poids_str.replace(",", "."))
except Exception:
    poids = 1.0

# Onglet / vue (priorite aux boutons)
vue = (lire_parametre_get("vue", "liaison") or "liaison").strip().lower()
if vue not in ("liaison", "reseaux", "liste"):
    vue = "liaison"


# ============================================================
# Messages UI
# ============================================================
message_ok = ""
message_erreur = ""


# ============================================================
# Actions: definir source / ajouter cible / retirer cible / vider
# ============================================================
if action == "definir_source":
    nid = (lire_parametre_get("nouveau_source_id", "") or "").strip()
    if nid.isdigit():
        source_id = int(nid)
        message_ok = "Source definie."
    else:
        message_erreur = "Source invalide."

if action == "ajouter_cible":
    nid = (lire_parametre_get("ajout_id", "") or "").strip()
    if nid.isdigit():
        cid = int(nid)
        if cid not in cibles_ids:
            cibles_ids.append(cid)
        message_ok = "Cible ajoutee."
    else:
        message_erreur = "Cible invalide."

if action == "retirer_cible":
    nid = (lire_parametre_get("retire_id", "") or "").strip()
    if nid.isdigit():
        cid = int(nid)
        cibles_ids = [x for x in cibles_ids if x != cid]
        message_ok = "Cible retiree."
    else:
        message_erreur = "Cible invalide."

if action == "vider_cibles":
    cibles_ids = []
    message_ok = "Cibles videes."

# Mettre a jour la chaine apres actions
cibles_ids_str = chaine_depuis_ids(cibles_ids)


# ============================================================
# Action: creer liaison (simple uniquement)
# ============================================================
if action == "creer_liaison":
    if source_id is None:
        message_erreur = "Aucune source selectionnee."
    elif not cibles_ids:
        message_erreur = "Aucune cible selectionnee."
    else:
        try:
            nb = 0
            for cid in cibles_ids:
                if cid == source_id:
                    continue  # eviter lien vers soi
                reseau_id = choisir_reseau_pour_nouvelle_liaison(connexion, type_applicable, source_id, cid)
                inserer_liaison(
                    connexion,
                    type_applicable=type_applicable,
                    reseau_id=reseau_id,
                    source_id=source_id,
                    cible_id=cid,
                    implication=implication,
                    type_lien=(type_lien or "associe"),
                    poids=poids,
                    commentaire=commentaire
                )
                nb += 1
            message_ok = "Liaison(s) creee(s): " + str(nb)
        except Exception as e:
            message_erreur = "Erreur creation liaison: " + str(e)

# Action: supprimer liaison
if action == "supprimer_liaison":
    lid = (lire_parametre_get("liaison_id", "") or "").strip()
    if lid.isdigit():
        try:
            supprimer_liaison(connexion, type_applicable, int(lid))
            message_ok = "Liaison supprimee."
        except Exception as e:
            message_erreur = "Erreur suppression: " + str(e)
    else:
        message_erreur = "Id liaison invalide."


# ============================================================
# Preparations affichage: noms source/cibles
# ============================================================
def nom_element_affichage(type_applicable, element_id):
    """Nom + id pour affichage UI."""
    if element_id is None:
        return ""
    if type_applicable == "O":
        n = nom_objet_par_id(connexion, colonne_id_objet, colonne_nom_objet, element_id)
    else:
        n = nom_evenement_par_id(connexion, element_id)
    n = (n or "").strip()
    if not n:
        n = "Element"
    return n + " (#" + str(element_id) + ")"


nom_source = nom_element_affichage(type_applicable, source_id) if source_id is not None else ""
noms_cibles = [(cid, nom_element_affichage(type_applicable, cid)) for cid in cibles_ids]


# ============================================================
# Recherche (selon mode)
# ============================================================
resultats_recherche = []
if texte_recherche:
    try:
        if type_applicable == "O":
            resultats_recherche = rechercher_objets(connexion, colonne_id_objet, colonne_nom_objet, texte_recherche, limite=25)
        else:
            resultats_recherche = rechercher_evenements(connexion, texte_recherche, limite=25)
    except Exception:
        resultats_recherche = []


# ============================================================
# Liste liaisons (pour onglet "liste")
# ============================================================
liaisons_recentes = []
try:
    liaisons_recentes = lister_liaisons(connexion, type_applicable, limite=250)
except Exception:
    liaisons_recentes = []


# ============================================================
# Liste reseaux (pour "voir les reseaux")
# ============================================================
reseaux_ids = []
try:
    reseaux_ids = lister_reseaux_ids(connexion, type_applicable)
except Exception:
    reseaux_ids = []


# ============================================================
# Construction etat URL commun (pour ne rien perdre)
# ============================================================
def url_etat_commun():
    """
    Etat minimal a conserver a chaque clic:
    - uid + type_applicable
    - source + cibles + recherche
    - implication + precision
    - vue (pour rester dans le bon onglet)
    """
    return (
        "uid=" + uid_encode +
        "&type_applicable=" + encoder_url(type_applicable) +
        "&source_id=" + encoder_url("" if source_id is None else str(source_id)) +
        "&cibles_ids=" + encoder_url(cibles_ids_str) +
        "&recherche=" + encoder_url(texte_recherche) +
        "&implication=" + encoder_url(implication) +
        "&type_lien=" + encoder_url(type_lien) +
        "&poids=" + encoder_url(poids_str) +
        "&commentaire=" + encoder_url(commentaire) +
        "&vue=" + encoder_url(vue)
    )


etat = url_etat_commun()


# ============================================================
# Liens navigation (haut de page)
# ============================================================
lien_retour_univers = "/cgi-bin/univers_dashboard.py?uid=" + uid_encode
lien_menu_simulation = "/cgi-bin/simulation.py?uid=" + uid_encode
lien_evenement = "/cgi-bin/evenement.py?uid=" + uid_encode  # a coder plus tard


# ============================================================
# UI: debut HTML + CSS (design mystique, mais plus clair)
# IMPORTANT: dans une f-string, les { } de CSS doivent etre doubles {{ }}
# ============================================================
print(f"""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Liaison - {echapper_html(nom_univers)}</title>

<style>
/* ============================================================
   Fond mystique mais lisible (contraste un peu augmente)
   ============================================================ */
body {{
  margin: 0;
  font-family: Arial, sans-serif;
  color: #ffffff;
  min-height: 100vh;
  background:
    radial-gradient(900px 600px at 18% 18%, rgba(255,216,106,0.10), rgba(0,0,0,0) 62%),
    radial-gradient(800px 520px at 82% 18%, rgba(190,120,255,0.18), rgba(0,0,0,0) 60%),
    radial-gradient(900px 650px at 55% 85%, rgba(110,255,220,0.05), rgba(0,0,0,0) 62%),
    linear-gradient(180deg, #05020a 0%, #0b0615 45%, #120a22 100%);
}}
body:before {{
  content:"";
  position: fixed; top:0; left:0; right:0; bottom:0;
  pointer-events: none;
  background: radial-gradient(900px 500px at 50% 30%, rgba(255,255,255,0.05), rgba(0,0,0,0) 60%);
  opacity: 0.60;
}}

/* ============================================================
   Boutons fixes (navigation)
   ============================================================ */
.bouton-retour {{
  position: fixed;
  top: 20px;
  left: 20px;
  width: 64px;
  height: 64px;
  background: url('/back_btn_violet.png') no-repeat center/contain;
}}
.bouton-top {{
  position: fixed;
  right: 20px;
  padding: 12px 18px;
  border-radius: 999px;
  text-decoration: none;
  font-size: 13px;
  box-shadow: 0 12px 28px rgba(0,0,0,0.45);
}}
.bouton-simulation {{
  top: 20px;
  color: #FFD86A;
  background: rgba(255,216,106,0.10);
  border: 1px solid rgba(255,216,106,0.34);
}}
.bouton-evenement {{
  top: 72px;
  color: rgba(255,255,255,0.88);
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.16);
}}

/* ============================================================
   Panel principal
   ============================================================ */
.panel {{
  width: 1280px;
  margin: 55px auto;
  padding: 54px;
  box-sizing: border-box;
  border-radius: 30px;
  background: rgba(14, 6, 26, 0.76);
  border: 1px solid rgba(255,216,106,0.22);
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
  color: rgba(255,255,255,0.86);
}}

/* ============================================================
   Messages (ok / erreur)
   ============================================================ */
.message {{
  margin: 18px 0 0 0;
  padding: 12px 16px;
  border-radius: 14px;
  background: rgba(0,0,0,0.30);
  border: 1px solid rgba(255,255,255,0.10);
  font-size: 13px;
}}
.message.ok {{ border-color: rgba(120,255,180,0.34); }}
.message.bad {{ border-color: rgba(255,120,120,0.34); }}

/* ============================================================
   Barre de boutons (priorite aux actions)
   ============================================================ */
.barre-actions {{
  margin-top: 22px;
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 14px;
}}

.bouton-carte {{
  display: block;
  padding: 14px 18px;
  border-radius: 18px;
  text-decoration: none;
  color: rgba(255,255,255,0.92);
  background:
    radial-gradient(700px 260px at 20% 20%, rgba(255,216,106,0.06), rgba(0,0,0,0) 60%),
    linear-gradient(180deg, rgba(70,28,120,0.58), rgba(45,16,85,0.58));
  border: 1px solid rgba(255,255,255,0.10);
  box-shadow: 0 18px 36px rgba(0,0,0,0.50);
}}
.bouton-carte.actif {{
  border-color: rgba(255,216,106,0.34);
}}
.bouton-carte .titre {{
  font-weight: bold;
  color: #FFD86A;
}}
.bouton-carte .desc {{
  margin-top: 6px;
  font-size: 12px;
  opacity: 0.82;
}}

/* ============================================================
   Grille contenus
   ============================================================ */
.grille {{
  margin-top: 18px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}}

.carte {{
  border-radius: 24px;
  padding: 22px;
  box-sizing: border-box;
  background:
    radial-gradient(700px 260px at 20% 20%, rgba(255,216,106,0.05), rgba(0,0,0,0) 60%),
    linear-gradient(180deg, rgba(70,28,120,0.56), rgba(45,16,85,0.56));
  border: 1px solid rgba(255,255,255,0.10);
  box-shadow: 0 18px 36px rgba(0,0,0,0.50);
}}

.carte h2 {{
  margin: 0 0 12px 0;
  font-size: 18px;
}}

.label {{
  display: block;
  margin: 10px 0 6px 0;
  font-size: 12px;
  opacity: 0.92;
}}

.champ-texte, .champ-select {{
  width: 100%;
  box-sizing: border-box;
  padding: 12px;
  border-radius: 14px;
  background: rgba(0,0,0,0.28);
  color: #ffffff;
  border: 1px solid rgba(255,255,255,0.12);
  outline: none;
}}

.ligne-actions {{
  margin-top: 12px;
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  align-items: center;
  flex-wrap: wrap;
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
  max-height: 260px;
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

.lien-supprimer {{
  color: rgba(255,170,170,0.95);
  text-decoration: none;
  border: 1px solid rgba(255,120,120,0.30);
  padding: 6px 10px;
  border-radius: 999px;
  display: inline-block;
}}

details {{
  margin-top: 14px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(0,0,0,0.18);
  border: 1px solid rgba(255,255,255,0.10);
}}
summary {{
  cursor: pointer;
  color: rgba(255,255,255,0.92);
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
</style>
</head>

<body>

<a class="bouton-retour" href="{lien_retour_univers}" title="Retour"></a>
<a class="bouton-top bouton-simulation" href="{lien_menu_simulation}" title="Menu Simulation">Menu Simulation</a>
<a class="bouton-top bouton-evenement" href="{lien_evenement}" title="Creer un evenement">Creer un evenement</a>

<div class="panel">
  <h1>Liaison / Reseaux</h1>

  <div class="ligne-univers">
    Univers : <strong>{echapper_html(nom_univers)}</strong>
    &nbsp;|&nbsp; ID : {echapper_html(uid)}
    &nbsp;|&nbsp; Mode : <strong>{'Objets' if type_applicable=='O' else 'Evenements'}</strong>
  </div>
""")

# Messages (feedback utilisateur)
if message_ok:
    print(f'<div class="message ok">{echapper_html(message_ok)}</div>')
if message_erreur:
    print(f'<div class="message bad">{echapper_html(message_erreur)}</div>')

# ============================================================
# Barre d'onglets (boutons cartes)
# - Liaison: ecran principal (choisir source/cible + creer)
# - Voir reseaux: resume "R1: ..."
# - Liste liaisons: table brute (debug / suppression)
# ============================================================
lien_vue_liaison = "/cgi-bin/liaison.py?" + etat.replace("&vue=" + encoder_url(vue), "&vue=liaison")
lien_vue_reseaux = "/cgi-bin/liaison.py?" + etat.replace("&vue=" + encoder_url(vue), "&vue=reseaux")
lien_vue_liste = "/cgi-bin/liaison.py?" + etat.replace("&vue=" + encoder_url(vue), "&vue=liste")

print(f"""
  <div class="barre-actions">
    <a class="bouton-carte {'actif' if vue=='liaison' else ''}" href="{lien_vue_liaison}">
      <div class="titre">Ajouter une liaison</div>
      <div class="desc">Choisir source + cible(s), puis creer.</div>
    </a>

    <a class="bouton-carte {'actif' if vue=='reseaux' else ''}" href="{lien_vue_reseaux}">
      <div class="titre">Voir les reseaux</div>
      <div class="desc">R1: S(a,b) -> C <-> X (resume lisible).</div>
    </a>

    <a class="bouton-carte {'actif' if vue=='liste' else ''}" href="{lien_vue_liste}">
      <div class="titre">Liste des liaisons</div>
      <div class="desc">Vue brute + suppression.</div>
    </a>
  </div>
""")

# ============================================================
# VUE 1: "liaison" (ecran principal, interface plus simple)
# ============================================================
if vue == "liaison":
    # Liens pour changer mode (Objets / Evenements)
    lien_mode_objets = "/cgi-bin/liaison.py?uid=" + uid_encode + "&type_applicable=O&vue=liaison"
    lien_mode_evenements = "/cgi-bin/liaison.py?uid=" + uid_encode + "&type_applicable=E&vue=liaison"

    print(f"""
    <div class="grille">

      <!-- ===============================
           Colonne gauche: Recherche
           =============================== -->
      <div class="carte">
        <h2>1) Trouver une source / des cibles</h2>

        <div class="message">
          Clique sur <strong>Source</strong> pour definir la source,
          puis sur <strong>+ Cible</strong> pour ajouter des cibles.
        </div>

        <!-- Boutons mode objets/evenements (simples, pas de JS) -->
        <div class="ligne-actions">
          <a class="bouton {'bouton-secondaire' if type_applicable!='O' else ''}" href="{lien_mode_objets}">Mode Objets</a>
          <a class="bouton {'bouton-secondaire' if type_applicable!='E' else ''}" href="{lien_mode_evenements}">Mode Evenements</a>
        </div>

        <!-- Formulaire recherche -->
        <form method="get" action="/cgi-bin/liaison.py">
          <input type="hidden" name="uid" value="{echapper_html(uid)}">
          <input type="hidden" name="type_applicable" value="{echapper_html(type_applicable)}">
          <input type="hidden" name="vue" value="liaison">

          <!-- Conserver selections -->
          <input type="hidden" name="source_id" value="{echapper_html('' if source_id is None else str(source_id))}">
          <input type="hidden" name="cibles_ids" value="{echapper_html(cibles_ids_str)}">

          <!-- Conserver options -->
          <input type="hidden" name="implication" value="{echapper_html(implication)}">
          <input type="hidden" name="type_lien" value="{echapper_html(type_lien)}">
          <input type="hidden" name="poids" value="{echapper_html(poids_str)}">
          <input type="hidden" name="commentaire" value="{echapper_html(commentaire)}">

          <label class="label">Recherche</label>
          <input class="champ-texte" type="text" name="recherche"
                 value="{echapper_html(texte_recherche)}"
                 placeholder="Ex: stylo, mur, guerre froide...">

          <div class="ligne-actions">
            <button class="bouton" type="submit">Chercher</button>
            <a class="bouton bouton-secondaire" href="/cgi-bin/liaison.py?uid={uid_encode}&type_applicable={type_applicable}&vue=liaison">Reset</a>
          </div>
        </form>
    """)

    # Affichage resultats recherche
    if texte_recherche:
        print('<div class="zone-resultats">')
        if not resultats_recherche:
            print(f'<div class="petit">Aucun resultat pour "{echapper_html(texte_recherche)}".</div>')
        else:
            for ligne in resultats_recherche:
                # Selon type, le tuple n'a pas la meme forme
                if type_applicable == "O":
                    element_id = int(ligne[0])
                    element_nom = str(ligne[1])
                    label_type = "Objet"
                else:
                    element_id = int(ligne[0])
                    element_nom = str(ligne[1])
                    label_type = "Evt"

                # Lien definir source
                lien_source = "/cgi-bin/liaison.py?" + etat + "&action=definir_source&nouveau_source_id=" + str(element_id)
                # Lien ajouter cible
                lien_cible = "/cgi-bin/liaison.py?" + etat + "&action=ajouter_cible&ajout_id=" + str(element_id)

                print(f"""
                  <div class="ligne-resultat">
                    <div>
                      <strong>{echapper_html(element_nom)}</strong>
                      <span class="petit">({label_type} #{echapper_html(element_id)})</span>
                    </div>
                    <div style="display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end;">
                      <a class="bouton bouton-secondaire" href="{lien_source}">Source</a>
                      <a class="bouton" href="{lien_cible}">+ Cible</a>
                    </div>
                  </div>
                """)
        print("</div>")

    # Affichage source/cibles (claire)
    print("<h2 style='margin-top:18px;'>Etat actuel</h2>")

    if source_id is None:
        print('<div class="message bad">Source: aucune. (Clique "Source" dans les resultats)</div>')
    else:
        print(f'<div class="message ok">Source: <strong>{echapper_html(nom_source)}</strong></div>')

    if not noms_cibles:
        print('<div class="message">Cibles: aucune. (Clique "+ Cible" dans les resultats)</div>')
    else:
        print('<div class="message">Cibles: <strong>' + echapper_html(str(len(noms_cibles))) + '</strong></div>')
        print('<div class="zone-resultats">')
        for (cid, lib) in noms_cibles:
            lien_retire = "/cgi-bin/liaison.py?" + etat + "&action=retirer_cible&retire_id=" + str(cid)
            print(f"""
              <div class="ligne-resultat">
                <div><strong>{echapper_html(lib)}</strong></div>
                <a class="bouton bouton-secondaire" href="{lien_retire}">Retirer</a>
              </div>
            """)
        print("</div>")
        lien_vider = "/cgi-bin/liaison.py?" + etat + "&action=vider_cibles"
        print(f'<div class="ligne-actions"><a class="bouton bouton-secondaire" href="{lien_vider}">Vider les cibles</a></div>')

    print("""
      </div> <!-- fin carte gauche -->
    """)

    # Colonne droite: creation liaison (boutons en priorite)
    print(f"""
      <!-- ===============================
           Colonne droite: Creation liaison
           =============================== -->
      <div class="carte">
        <h2>2) Creer la liaison</h2>

        <div class="message">
          <strong>Implication</strong> = direction de propagation (structure).<br>
          <strong>Precision</strong> (optionnel) = details (poids, type de lien, commentaire).
        </div>

        <!-- Form creation (GET) -->
        <form method="get" action="/cgi-bin/liaison.py">
          <input type="hidden" name="uid" value="{echapper_html(uid)}">
          <input type="hidden" name="type_applicable" value="{echapper_html(type_applicable)}">
          <input type="hidden" name="vue" value="liaison">

          <!-- Conserver selections -->
          <input type="hidden" name="source_id" value="{echapper_html('' if source_id is None else str(source_id))}">
          <input type="hidden" name="cibles_ids" value="{echapper_html(cibles_ids_str)}">
          <input type="hidden" name="recherche" value="{echapper_html(texte_recherche)}">

          <label class="label">Implication (obligatoire)</label>
          <div class="ligne-actions" style="justify-content:flex-start;">
            <!-- Deux boutons: on simule un "radio" sans JS -->
            <a class="bouton {'bouton-secondaire' if implication!='->' else ''}"
               href="/cgi-bin/liaison.py?{etat}&implication=->">Implication (->)</a>

            <a class="bouton {'bouton-secondaire' if implication!='<->' else ''}"
               href="/cgi-bin/liaison.py?{etat}&implication=%3C-%3E">Equivalence (<->)</a>
          </div>

          <!-- Precision optionnelle (pliee) -->
          <details>
            <summary>Precision (optionnel)</summary>

            <label class="label">Type de lien</label>
            <select class="champ-select" name="type_lien">
              <option value="associe" {"selected" if type_lien=="associe" else ""}>associe (defaut)</option>
              <option value="depend" {"selected" if type_lien=="depend" else ""}>depend</option>
              <option value="compose" {"selected" if type_lien=="compose" else ""}>compose</option>
              <option value="cause" {"selected" if type_lien=="cause" else ""}>cause</option>
              <option value="oppose" {"selected" if type_lien=="oppose" else ""}>oppose</option>
              <option value="influence" {"selected" if type_lien=="influence" else ""}>influence</option>
            </select>

            <label class="label">Poids</label>
            <input class="champ-texte" type="text" name="poids" value="{echapper_html(poids_str)}" placeholder="1.0">

            <label class="label">Commentaire</label>
            <input class="champ-texte" type="text" name="commentaire" value="{echapper_html(commentaire)}" placeholder="Optionnel">
          </details>

          <!-- Bouton principal (priorite) -->
          <div class="ligne-actions">
            <button class="bouton" type="submit" name="action" value="creer_liaison">Creer la liaison</button>
          </div>

          <div class="message" style="margin-top:10px;">
            Astuce: si tu ne maitrises pas la precision, n ouvre pas le bloc.
            Par defaut: <strong>associe</strong>, poids <strong>1.0</strong>.
          </div>
        </form>

        <div class="message" style="margin-top:10px;">
          Tu veux voir le resultat comme "R1: S(a,b) -> C <-> X" ? Clique sur <strong>Voir les reseaux</strong>.
        </div>

      </div> <!-- fin carte droite -->

    </div> <!-- fin grille -->
    """)

# ============================================================
# VUE 2: "reseaux" (chef d'oeuvre: resume lisible par reseau)
# ============================================================
elif vue == "reseaux":
    print("""
    <div class="carte" style="margin-top:18px;">
      <h2>Voir les reseaux</h2>

      <div class="message">
        Chaque reseau (R1, R2...) est construit automatiquement a partir des liaisons.
        Exemple: <strong>R1: S(stylo, mur) -> Stylos 4 couleurs <-> Barre de fer</strong>
      </div>
    """)

    if not reseaux_ids:
        print('<div class="message">Aucun reseau pour le moment. Cree une liaison pour commencer.</div>')
    else:
        # On affiche une liste de "cartes" reseau (sans JS, juste du HTML)
        for rid in reseaux_ids:
            # Construire un texte lisible
            texte = resumer_reseau_lisible(type_applicable, connexion, colonne_id_objet, colonne_nom_objet, rid)

            # Nombre de liaisons dans le reseau (utile pour savoir si c'est vide)
            nb_liaisons = 0
            try:
                nb_liaisons = len(liaisons_par_reseau(connexion, type_applicable, rid))
            except Exception:
                nb_liaisons = 0

            # On ignore les reseaux totalement vides (cas rare)
            if nb_liaisons <= 0:
                continue

            print(f"""
              <details style="margin-top:12px;">
                <summary><strong>R{echapper_html(rid)}</strong> &nbsp; <span class="petit">{echapper_html(nb_liaisons)} liaison(s)</span></summary>

                <div class="message" style="margin-top:10px;">
                  <strong>R{echapper_html(rid)}:</strong> {echapper_html(texte)}
                </div>

                <div class="petit">
                  Note: ce resume est un "aperçu lisible". La simulation utilisera les liaisons exactes.
                </div>
              </details>
            """)

    print("</div>")  # fin carte

# ============================================================
# VUE 3: "liste" (table brute, suppression)
# ============================================================
else:
    print("""
    <div class="carte" style="margin-top:18px;">
      <h2>Liste des liaisons</h2>

      <div class="message">
        Vue brute (utile pour debug et suppression).
        La simulation lira ces lignes telles quelles.
      </div>
    """)

    if not liaisons_recentes:
        print('<div class="message">Aucune liaison.</div>')
    else:
        print("""
        <table class="table">
          <tr>
            <th>ID</th>
            <th>Reseau</th>
            <th>Source</th>
            <th>Cible</th>
            <th>Implication</th>
            <th>Precision</th>
            <th></th>
          </tr>
        """)

        for (lid, rid, sid, cid, impl, tl, pw, comm, dc) in liaisons_recentes:
            lib_source = nom_element_affichage(type_applicable, sid)
            lib_cible = nom_element_affichage(type_applicable, cid)

            # Lien suppression (conserve etat)
            lien_suppr = "/cgi-bin/liaison.py?" + etat + "&action=supprimer_liaison&liaison_id=" + str(lid)

            # Petit bloc precision lisible
            precision_txt = (tl or "associe") + " / " + str(pw)
            if (comm or "").strip():
                precision_txt += " / " + comm.strip()

            print(f"""
              <tr>
                <td>{echapper_html(lid)}</td>
                <td>R{echapper_html(rid)}</td>
                <td>{echapper_html(lib_source)}</td>
                <td>{echapper_html(lib_cible)}</td>
                <td>{echapper_html(impl)}</td>
                <td class="petit">{echapper_html(precision_txt)}</td>
                <td><a class="lien-supprimer" href="{lien_suppr}">Supprimer</a></td>
              </tr>
            """)

        print("</table>")

    print("</div>")  # fin carte

# ============================================================
# Fin page
# ============================================================
print("""
</div> <!-- fin panel -->
</body>
</html>
""")

connexion.close()
