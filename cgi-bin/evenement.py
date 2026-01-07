#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
evenement.py
------------
PAGE "EVENEMENT" (univers) - version plus simple + exploitable pour les simulations.

Changements demandes:
- Ep (Parametrique):
  - On n oblige PLUS a selectionner des objets.
  - "Appliquer a" (portee) avec choix:
      * tout (defaut si rien)
      * famille (1 famille)
      * type (1 type)
      * liste (objets precis, ajoutables par recherche)
- Ea (Algorithmique):
  - Version 1 SIMPLE: "Si Evenement A est actif/inactif -> faire ..."
  - Faire = (Activer / Desactiver / Changer probabilite) sur un evenement P
  - Optionnel: probabilite de declenchement de la regle (Ea)

Toujours:
- Sans JavaScript (GET + reload)
- Variables / fonctions en francais
- Beaucoup de commentaires
- Design mystique proche des autres pages

Stockage (important pour sim_calc.py):
- Table evenements: meta
- Table parametres_evenements: cle/valeur standardisees

Parametres utiles (exemples):
- Pour Ep:
    type_mode=parametrique
    appliquer_portee=tout|famille|type|liste
    appliquer_famille=...
    appliquer_type=...
    appliquer_objets_ids=1,2,3
    action=coef_evolution|mult_prix_moyen|delta_prix_moyen|mult_CA
    valeur=...
    probabilite=0.8   (optionnel, par defaut 1.0)
- Pour Ea:
    type_mode=algorithmique
    regle_probabilite=1.0
    si_evenement_id=12
    si_etat=actif|inactif
    faire_type=activer|desactiver|changer_probabilite
    faire_evenement_id=33
    faire_probabilite=0.3

Note:
- "Actif/Inactif" d un evenement est une notion de simulation.
  Ici, on enregistre la regle. La simulation definira comment elle gere l etat.
"""

import os
import sqlite3
import urllib.parse
import html


# ============================================================
# En-tete CGI obligatoire
# ============================================================
print("Content-Type: text/html; charset=utf-8\n")


# ============================================================
# Constantes projet
# ============================================================
DOSSIER_UNIVERS = "cgi-bin/universes/"

# Stats d objet exposees (simples + exploitables)
STATS_OBJET = [
    ("Prix_Moyen_Actuel", "Prix moyen (actuel)"),
    ("CA_2025_2035_MDEUR", "CA (2025-2035)"),
]


# ============================================================
# Utils GET / HTML / URL
# ============================================================
def lire_parametre_get(nom, defaut=""):
    """Retourne un parametre GET (?nom=...) ou defaut."""
    qs = os.environ.get("QUERY_STRING", "")
    params = urllib.parse.parse_qs(qs, keep_blank_values=True)
    return params.get(nom, [defaut])[0]


def echapper_html(texte):
    """Echappe HTML (anti injection)."""
    return html.escape("" if texte is None else str(texte))


def encoder_url(texte):
    """Encode URL (reinjecter dans liens)."""
    return urllib.parse.quote("" if texte is None else str(texte))


def ids_depuis_chaine(chaine):
    """Transforme '1,2,3' -> [1,2,3] sans doublons."""
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


def convertir_float(texte, defaut=0.0):
    """Conversion float robuste, accepte virgule."""
    try:
        return float(str(texte).strip().replace(",", "."))
    except Exception:
        return defaut


def convertir_int(texte, defaut=0):
    """Conversion int robuste."""
    try:
        return int(str(texte).strip())
    except Exception:
        return defaut


def construire_chemin_univers(uid):
    """Chemin BDD univers avec uid nettoye."""
    uid_sain = "".join([c for c in uid if c.isalnum() or c in ("-", "_")])
    return os.path.join(DOSSIER_UNIVERS, "universe_" + uid_sain + ".db")


def recuperer_nom_univers(uid):
    """Lit univers_names.txt et renvoie le nom."""
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
# BDD: creation tables
# ============================================================
def colonne_existe(connexion, table, colonne):
    """Verifie si une colonne existe (evite crash ALTER TABLE)."""
    cur = connexion.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    for row in cur.fetchall():
        if row and len(row) >= 2 and (row[1] or "").lower() == colonne.lower():
            return True
    return False


def creer_tables_evenements_si_besoin(connexion):
    """Cree evenements + parametres_evenements si besoin."""
    cur = connexion.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS evenements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            type_evenement TEXT NOT NULL DEFAULT 'E',
            type_detail TEXT NOT NULL DEFAULT '',
            afficher_simulation INTEGER NOT NULL DEFAULT 1,
            description TEXT NOT NULL DEFAULT '',
            date_creation TEXT DEFAULT (datetime('now'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS parametres_evenements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evenement_id INTEGER NOT NULL,
            cle TEXT NOT NULL,
            valeur TEXT NOT NULL DEFAULT '',
            ordre INTEGER NOT NULL DEFAULT 0,
            date_creation TEXT DEFAULT (datetime('now'))
        )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_params_evt ON parametres_evenements(evenement_id, ordre)")
    connexion.commit()

    # Migration douce si ancienne version
    if not colonne_existe(connexion, "evenements", "type_detail"):
        try:
            cur.execute("ALTER TABLE evenements ADD COLUMN type_detail TEXT NOT NULL DEFAULT ''")
            connexion.commit()
        except Exception:
            pass

    if not colonne_existe(connexion, "evenements", "afficher_simulation"):
        try:
            cur.execute("ALTER TABLE evenements ADD COLUMN afficher_simulation INTEGER NOT NULL DEFAULT 1")
            connexion.commit()
        except Exception:
            pass


# ============================================================
# BDD: lecture stat_objects (objets)
# ============================================================
def detecter_colonnes_stat_objects(connexion):
    """Detecte id + Objet dans stat_objects (copie de Prix_Objets)."""
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


def table_existe(connexion, nom_table):
    """Verifie l existence d une table SQLite."""
    cur = connexion.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (nom_table,))
    return True if cur.fetchone() else False


def rechercher_objets(connexion, colonne_id, colonne_nom, texte, limite=25):
    """Recherche LIKE simple dans stat_objects."""
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
    """Nom objet depuis stat_objects."""
    cur = connexion.cursor()
    cur.execute(f"SELECT [{colonne_nom}] FROM stat_objects WHERE [{colonne_id}] = ?", (objet_id,))
    row = cur.fetchone()
    return row[0] if row and row[0] is not None else ""


def lire_stat_objet(connexion, objet_id, champ):
    """Lit une stat numerique d un objet (float ou None)."""
    try:
        cur = connexion.cursor()
        cur.execute(f"SELECT [{champ}] FROM stat_objects WHERE id = ?", (objet_id,))
        row = cur.fetchone()
        if not row:
            return None
        val = row[0]
        if val is None:
            return None
        return float(val)
    except Exception:
        return None


def distinct_texte(connexion, colonne):
    """Liste distincte d une colonne texte si elle existe (Famille / Type)."""
    try:
        cur = connexion.cursor()
        # On tente une requete simple; si colonne inexistante => exception
        cur.execute(
            f"""
            SELECT DISTINCT [{colonne}]
            FROM stat_objects
            WHERE [{colonne}] IS NOT NULL AND TRIM([{colonne}]) != ''
            ORDER BY [{colonne}] COLLATE NOCASE
            """
        )
        return [r[0] for r in cur.fetchall()]
    except Exception:
        return []


# ============================================================
# BDD: evenements + parametres
# ============================================================
def creer_evenement(connexion, nom, type_evenement, type_detail, afficher_simulation, description):
    """Cree un evenement et renvoie son id."""
    cur = connexion.cursor()
    cur.execute(
        """
        INSERT INTO evenements (nom, type_evenement, type_detail, afficher_simulation, description)
        VALUES (?, ?, ?, ?, ?)
        """,
        (nom, type_evenement, type_detail, afficher_simulation, description)
    )
    connexion.commit()
    return cur.lastrowid


def lister_evenements(connexion, limite=200):
    """Liste evenements recents."""
    cur = connexion.cursor()
    cur.execute(
        """
        SELECT id, nom, type_evenement, type_detail, afficher_simulation, date_creation
        FROM evenements
        ORDER BY id DESC
        LIMIT ?
        """,
        (limite,)
    )
    return cur.fetchall()


def supprimer_evenement(connexion, evenement_id):
    """Supprime un evenement + parametres."""
    cur = connexion.cursor()
    cur.execute("DELETE FROM parametres_evenements WHERE evenement_id = ?", (evenement_id,))
    cur.execute("DELETE FROM evenements WHERE id = ?", (evenement_id,))
    connexion.commit()


def remplacer_parametres(connexion, evenement_id, liste_cle_valeur):
    """Remplace tous les parametres d un evenement."""
    cur = connexion.cursor()
    cur.execute("DELETE FROM parametres_evenements WHERE evenement_id = ?", (evenement_id,))
    ordre = 0
    for cle, valeur in (liste_cle_valeur or []):
        if not cle:
            continue
        cur.execute(
            """
            INSERT INTO parametres_evenements (evenement_id, cle, valeur, ordre)
            VALUES (?, ?, ?, ?)
            """,
            (evenement_id, cle, "" if valeur is None else str(valeur), ordre)
        )
        ordre += 1
    connexion.commit()


# ============================================================
# Contexte univers
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
creer_tables_evenements_si_besoin(connexion)

# stat_objects est necessaire pour: recherche objets + familles/types + constats objet
table_stat_objects_ok = table_existe(connexion, "stat_objects")

colonne_id_objet = None
colonne_nom_objet = None
if table_stat_objects_ok:
    colonne_id_objet, colonne_nom_objet = detecter_colonnes_stat_objects(connexion)

# Familles / Types disponibles (si colonnes existent)
liste_familles = distinct_texte(connexion, "Famille") if table_stat_objects_ok else []
liste_types = distinct_texte(connexion, "Type") if table_stat_objects_ok else []


# ============================================================
# Etat UI
# ============================================================
action = (lire_parametre_get("action", "") or "").strip()

# Mode (3 boutons)
mode = (lire_parametre_get("mode", "Ec") or "Ec").strip()
if mode not in ("Ec", "Ep", "Ea"):
    mode = "Ec"

# Champs communs
nom_evenement = (lire_parametre_get("nom_evenement", "") or "").strip()
description = (lire_parametre_get("description", "") or "").strip()

# Afficher simulation
afficher_simulation_str = (lire_parametre_get("afficher_simulation", "1") or "1").strip()
afficher_simulation = 1 if afficher_simulation_str in ("1", "on", "oui", "OUI", "true", "True") else 0

# Probabilite de l evenement (optionnelle)
probabilite_evt_str = (lire_parametre_get("probabilite_evt", "1.0") or "1.0").strip()
probabilite_evt = convertir_float(probabilite_evt_str, 1.0)
if probabilite_evt < 0.0:
    probabilite_evt = 0.0
if probabilite_evt > 1.0:
    probabilite_evt = 1.0

# Recherche objets (utile uniquement si on veut construire une "liste d objets")
recherche_objet = (lire_parametre_get("recherche_objet", "") or "").strip()

# Liste d objets precise (utilisee si portee=liste)
selection_ids_texte = (lire_parametre_get("selection_ids", "") or "").strip()
selection_ids = ids_depuis_chaine(selection_ids_texte)

# -----------------------------
# Ec: Constat
# -----------------------------
type_constat = (lire_parametre_get("type_constat", "objet") or "objet").strip()
if type_constat not in ("objet", "evenement"):
    type_constat = "objet"

champ_constat = (lire_parametre_get("champ_constat", "Prix_Moyen_Actuel") or "Prix_Moyen_Actuel").strip()
operateur_constat = (lire_parametre_get("operateur_constat", "<") or "<").strip()
valeur_constat_str = (lire_parametre_get("valeur_constat", "0") or "0").strip()
valeur_constat = convertir_float(valeur_constat_str, 0.0)

evenement_cible_id_str = (lire_parametre_get("evenement_cible_id", "") or "").strip()
evenement_cible_id = int(evenement_cible_id_str) if evenement_cible_id_str.isdigit() else None

etat_evenement = (lire_parametre_get("etat_evenement", "actif") or "actif").strip()
if etat_evenement not in ("actif", "inactif"):
    etat_evenement = "actif"

# -----------------------------
# Ep: Parametrique
# -----------------------------
appliquer_portee = (lire_parametre_get("appliquer_portee", "") or "").strip()
# Defaut demande: si tu ne fais rien => tout
if appliquer_portee not in ("", "tout", "famille", "type", "liste"):
    appliquer_portee = ""
if appliquer_portee == "":
    appliquer_portee = "tout"

appliquer_famille = (lire_parametre_get("appliquer_famille", "") or "").strip()
appliquer_type = (lire_parametre_get("appliquer_type", "") or "").strip()

action_param = (lire_parametre_get("action_param", "coef_evolution") or "coef_evolution").strip()
if action_param not in ("coef_evolution", "mult_prix_moyen", "delta_prix_moyen", "mult_CA"):
    action_param = "coef_evolution"

valeur_param_str = (lire_parametre_get("valeur_param", "0.0") or "0.0").strip()
valeur_param = convertir_float(valeur_param_str, 0.0)

# -----------------------------
# Ea: Algorithmique (simple "Si ... faire ...")
# -----------------------------
regle_probabilite_str = (lire_parametre_get("regle_probabilite", "1.0") or "1.0").strip()
regle_probabilite = convertir_float(regle_probabilite_str, 1.0)
if regle_probabilite < 0.0:
    regle_probabilite = 0.0
if regle_probabilite > 1.0:
    regle_probabilite = 1.0

si_evenement_id_str = (lire_parametre_get("si_evenement_id", "") or "").strip()
si_evenement_id = int(si_evenement_id_str) if si_evenement_id_str.isdigit() else None

si_etat = (lire_parametre_get("si_etat", "actif") or "actif").strip()
if si_etat not in ("actif", "inactif"):
    si_etat = "actif"

faire_type = (lire_parametre_get("faire_type", "activer") or "activer").strip()
if faire_type not in ("activer", "desactiver", "changer_probabilite"):
    faire_type = "activer"

faire_evenement_id_str = (lire_parametre_get("faire_evenement_id", "") or "").strip()
faire_evenement_id = int(faire_evenement_id_str) if faire_evenement_id_str.isdigit() else None

faire_probabilite_str = (lire_parametre_get("faire_probabilite", "1.0") or "1.0").strip()
faire_probabilite = convertir_float(faire_probabilite_str, 1.0)
if faire_probabilite < 0.0:
    faire_probabilite = 0.0
if faire_probabilite > 1.0:
    faire_probabilite = 1.0

# Parametre U (objet d'evenement, utile pour EA)
parametre_u = (lire_parametre_get("parametre_u", "") or "").strip()


# ============================================================
# Messages UI
# ============================================================
message_ok = ""
message_erreur = ""


# ============================================================
# Actions selection objets (pour portee=liste uniquement)
# ============================================================
if action == "ajouter_selection":
    oid_str = (lire_parametre_get("objet_ajout_id", "") or "").strip()
    if oid_str.isdigit():
        oid = int(oid_str)
        if oid not in selection_ids:
            selection_ids.append(oid)
        message_ok = "Objet ajoute a la liste."
    else:
        message_erreur = "Objet invalide (ajout)."

if action == "retirer_selection":
    oid_str = (lire_parametre_get("objet_retire_id", "") or "").strip()
    if oid_str.isdigit():
        oid = int(oid_str)
        selection_ids = [x for x in selection_ids if x != oid]
        message_ok = "Objet retire."
    else:
        message_erreur = "Objet invalide (retrait)."

if action == "vider_selection":
    selection_ids = []
    message_ok = "Liste videe."

# Mise a jour chaine selection
selection_ids_texte = chaine_depuis_ids(selection_ids)


# ============================================================
# Action: suppression evenement
# ============================================================
if action == "supprimer":
    eid_str = (lire_parametre_get("supprimer_id", "") or "").strip()
    if not eid_str.isdigit():
        message_erreur = "Id suppression invalide."
    else:
        try:
            supprimer_evenement(connexion, int(eid_str))
            message_ok = "Evenement supprime."
        except Exception as e:
            message_erreur = "Erreur suppression: " + str(e)


# ============================================================
# Action: creation evenement (mode Ec/Ep/Ea)
# ============================================================
if action == "creer":
    if not nom_evenement:
        message_erreur = "Nom de l evenement manquant."
    else:
        # Type final:
        # - afficher_simulation=1 => type_evenement='E'
        # - sinon type_evenement=Ec/Ep/Ea
        type_final = "E" if afficher_simulation == 1 else mode
        type_detail = mode  # garde la trace du bouton

        # Parametres communs (probabilite + description)
        parametres = []
        parametres.append(("probabilite", str(probabilite_evt)))
        if description:
            parametres.append(("description", description))

        # -------------------------
        # Ec: Constat
        # -------------------------
        if mode == "Ec":
            parametres.append(("type_mode", "constat"))

            if type_constat == "objet":
                # Constat objet: ici, on garde l idee d une liste (selection_ids).
                # Si vide, on refuse, parce que "constat objet" sans cible n a pas de sens.
                if not table_stat_objects_ok:
                    message_erreur = "Constat objet impossible: stat_objects absent."
                elif not selection_ids:
                    message_erreur = "Constat objet: ajoute au moins un objet (liste)."
                else:
                    parametres.append(("type_constat", "objet"))
                    parametres.append(("objets_ids", selection_ids_texte))
                    parametres.append(("champ", champ_constat))
                    parametres.append(("operateur", operateur_constat))
                    parametres.append(("valeur", str(valeur_constat)))

            else:
                # Constat evenement: on observe l etat d un autre evenement
                if evenement_cible_id is None:
                    message_erreur = "Constat evenement: choisis un evenement cible."
                else:
                    parametres.append(("type_constat", "evenement"))
                    parametres.append(("evenement_cible_id", str(evenement_cible_id)))
                    parametres.append(("etat", etat_evenement))

        # -------------------------
        # Ep: Parametrique
        # -------------------------
        if mode == "Ep" and not message_erreur:
            parametres.append(("type_mode", "parametrique"))

            # Portee par defaut: tout (demande utilisateur)
            parametres.append(("appliquer_portee", appliquer_portee))

            # Si portee famille/type, on stocke la valeur choisie
            if appliquer_portee == "famille":
                if not appliquer_famille:
                    message_erreur = "Parametrique: choisis une famille (ou repasse en 'tout')."
                else:
                    parametres.append(("appliquer_famille", appliquer_famille))

            if appliquer_portee == "type":
                if not appliquer_type:
                    message_erreur = "Parametrique: choisis un type (ou repasse en 'tout')."
                else:
                    parametres.append(("appliquer_type", appliquer_type))

            # Si portee liste: on stocke la liste d objets (si vide => fallback vers tout, comme tu veux)
            if appliquer_portee == "liste":
                if selection_ids:
                    parametres.append(("appliquer_objets_ids", selection_ids_texte))
                else:
                    # Tu as dit: "si tu fais rien c est obligatoirement en tout"
                    # Donc ici, liste vide => on transforme en tout
                    parametres = [p for p in parametres if p[0] != "appliquer_portee"]
                    parametres.append(("appliquer_portee", "tout"))

            # Action parametrique (valeur)
            parametres.append(("action", action_param))
            parametres.append(("valeur", str(valeur_param)))

        # -------------------------
        # Ea: Algorithmique simple "Si ... faire ..."
        # -------------------------
        if mode == "Ea" and not message_erreur:
            parametres.append(("type_mode", "algorithmique"))

            # Probabilite de declenchement de la regle (optionnelle)
            parametres.append(("regle_probabilite", str(regle_probabilite)))

            # Parametre U (optionnel, objet d'evenement)
            if parametre_u:
                parametres.append(("parametre_u", parametre_u))

            # Condition: on impose un evenement A + etat
            if si_evenement_id is None:
                message_erreur = "Algorithmique: choisis l evenement A (condition)."
            else:
                parametres.append(("si_evenement_id", str(si_evenement_id)))
                parametres.append(("si_etat", si_etat))

            # Action: sur evenement P
            if not message_erreur:
                if faire_evenement_id is None:
                    message_erreur = "Algorithmique: choisis l evenement P (action)."
                else:
                    parametres.append(("faire_type", faire_type))
                    parametres.append(("faire_evenement_id", str(faire_evenement_id)))

                    # Si action = changer prob, on stocke la nouvelle prob
                    if faire_type == "changer_probabilite":
                        parametres.append(("faire_probabilite", str(faire_probabilite)))

        # Insertion en BDD si OK
        if not message_erreur:
            try:
                nouvel_id = creer_evenement(
                    connexion,
                    nom_evenement,
                    type_final,
                    type_detail,
                    afficher_simulation,
                    description
                )
                remplacer_parametres(connexion, nouvel_id, parametres)

                message_ok = "Evenement cree (id: " + str(nouvel_id) + ")."

                # Reset minimal pour eviter double-creation sur refresh
                nom_evenement = ""
            except Exception as e:
                message_erreur = "Erreur creation: " + str(e)


# ============================================================
# Donnees affichage (liste evenements + recherche objets)
# ============================================================
liste_evenements = []
try:
    liste_evenements = lister_evenements(connexion, limite=200)
except Exception:
    liste_evenements = []

# Resultats recherche objets (utiles si portee=liste ou constat objet)
resultats_objets = []
if recherche_objet and table_stat_objects_ok and colonne_id_objet and colonne_nom_objet:
    try:
        resultats_objets = rechercher_objets(connexion, colonne_id_objet, colonne_nom_objet, recherche_objet, limite=25)
    except Exception:
        resultats_objets = []


# ============================================================
# Liens navigation
# ============================================================
lien_retour_univers = "/cgi-bin/univers_dashboard.py?uid=" + uid_encode
lien_retour_liaison = "/cgi-bin/liaison.py?uid=" + uid_encode
lien_menu_simulation = "/cgi-bin/menu_simulation.py?uid=" + uid_encode


# ============================================================
# HTML / CSS (mystique, clair)
# NOTE: f-string => CSS doit doubler {{ }}
# ============================================================
print(f"""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Evenement - {echapper_html(nom_univers)}</title>

<style>
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
  position:fixed; top:0; left:0; right:0; bottom:0;
  pointer-events:none;
  background: radial-gradient(900px 500px at 50% 30%, rgba(255,255,255,0.05), rgba(0,0,0,0) 60%);
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

.bouton-top {{
  position: fixed;
  right: 20px;
  padding: 12px 18px;
  border-radius: 999px;
  text-decoration: none;
  font-size: 13px;
  box-shadow: 0 12px 28px rgba(0,0,0,0.45);
}}

.bouton-liaison {{
  top: 20px;
  color: #FFD86A;
  background: rgba(255,216,106,0.10);
  border: 1px solid rgba(255,216,106,0.34);
}}

.bouton-simulation {{
  top: 72px;
  color: rgba(255,255,255,0.90);
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.16);
}}

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
  display:block;
  margin: 10px 0 6px 0;
  font-size: 12px;
  opacity: 0.92;
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

textarea {{
  min-height: 90px;
  resize: vertical;
}}

.ligne-actions {{
  margin-top: 12px;
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

.bouton-mode {{
  padding: 10px 14px;
}}
.bouton-mode.actif {{
  border-color: rgba(255,216,106,0.60);
  background: rgba(255,216,106,0.18);
}}

.zone-resultats {{
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(0,0,0,0.22);
  border: 1px solid rgba(255,255,255,0.10);
  max-height: 260px;
  overflow:auto;
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

.lien-supprimer {{
  color: rgba(255,170,170,0.95);
  text-decoration:none;
  border: 1px solid rgba(255,120,120,0.30);
  padding: 6px 10px;
  border-radius: 999px;
  display:inline-block;
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
  color: rgba(255,255,255,0.92);
}}
</style>
</head>

<body>

<a class="bouton-retour" href="{lien_retour_univers}" title="Retour"></a>
<a class="bouton-top bouton-liaison" href="{lien_retour_liaison}" title="Retour Liaison">Retour Liaison</a>
<a class="bouton-top bouton-simulation" href="{lien_menu_simulation}" title="Menu Simulation">Menu Simulation</a>

<div class="panel">
  <h1>Evenement</h1>

  <div class="ligne-univers">
    Univers : <strong>{echapper_html(nom_univers)}</strong>
    &nbsp;|&nbsp; ID : {echapper_html(uid)}
  </div>
""")

# Messages (feedback)
if message_ok:
    print(f'<div class="message ok">{echapper_html(message_ok)}</div>')
if message_erreur:
    print(f'<div class="message bad">{echapper_html(message_erreur)}</div>')

# Avertissement si pas de stat_objects
if not table_stat_objects_ok:
    print('<div class="message bad">Attention: table stat_objects absente. (Impossible de cibler objets/famille/type.)</div>')

# ============================================================
# UI: creation evenement (gauche)
# ============================================================
print(f"""
  <div class="grille">
    <div class="carte">
      <h2>Creer un evenement</h2>

      <div class="message">
        Ep: par defaut "tout" si tu ne choisis rien.<br>
        Ea: "Si Evenement A ... faire ..." sur un evenement P.
      </div>

      <form method="get" action="/cgi-bin/evenement.py">
        <input type="hidden" name="uid" value="{echapper_html(uid)}">
        <input type="hidden" name="action" value="creer">

        <!-- Etat conserve -->
        <input type="hidden" name="mode" value="{echapper_html(mode)}">
        <input type="hidden" name="type_constat" value="{echapper_html(type_constat)}">
        <input type="hidden" name="selection_ids" value="{echapper_html(selection_ids_texte)}">
        <input type="hidden" name="recherche_objet" value="{echapper_html(recherche_objet)}">

        <label class="label">Nom de l evenement</label>
        <input class="champ-texte" type="text" name="nom_evenement" value="{echapper_html(nom_evenement)}"
               placeholder="Ex: Guerre froide">

        <label class="label">Afficher dans simulation ?</label>
        <select class="champ-select" name="afficher_simulation">
          <option value="1" {"selected" if afficher_simulation==1 else ""}>Oui (type = E)</option>
          <option value="0" {"selected" if afficher_simulation==0 else ""}>Non (type = {echapper_html(mode)})</option>
        </select>

        <label class="label">Probabilite de l evenement (0..1) (optionnel)</label>
        <input class="champ-texte" type="text" name="probabilite_evt" value="{echapper_html(probabilite_evt_str)}"
               placeholder="Ex: 0.8">

        <label class="label">Description (optionnel)</label>
        <textarea name="description" placeholder="Explique...">{echapper_html(description)}</textarea>

        <div class="ligne-actions" style="justify-content:flex-start;">
          <a class="bouton bouton-mode {'actif' if mode=='Ec' else ''}"
             href="/cgi-bin/evenement.py?uid={uid_encode}&mode=Ec&type_constat={encoder_url(type_constat)}&selection_ids={encoder_url(selection_ids_texte)}&recherche_objet={encoder_url(recherche_objet)}">
             Constat (Ec)
          </a>

          <a class="bouton bouton-mode {'actif' if mode=='Ep' else ''}"
             href="/cgi-bin/evenement.py?uid={uid_encode}&mode=Ep&appliquer_portee={encoder_url(appliquer_portee)}&selection_ids={encoder_url(selection_ids_texte)}&recherche_objet={encoder_url(recherche_objet)}">
             Parametrique (Ep)
          </a>

          <a class="bouton bouton-mode {'actif' if mode=='Ea' else ''}"
             href="/cgi-bin/evenement.py?uid={uid_encode}&mode=Ea&selection_ids={encoder_url(selection_ids_texte)}&recherche_objet={encoder_url(recherche_objet)}">
             Algorithmique (Ea)
          </a>
        </div>
""")

# ============================================================
# Sous-bloc selon mode
# ============================================================

# -------------------------
# MODE Ec
# -------------------------
if mode == "Ec":
    # Liste stats
    options_stats = ""
    for (champ, lib) in STATS_OBJET:
        sel = "selected" if champ_constat == champ else ""
        options_stats += f'<option value="{echapper_html(champ)}" {sel}>{echapper_html(lib)}</option>'

    # Operateurs
    options_op = ""
    for op in ("=", "<", ">"):
        sel = "selected" if operateur_constat == op else ""
        options_op += f'<option value="{echapper_html(op)}" {sel}>{echapper_html(op)}</option>'

    # Evenements existants (dropdown)
    options_evt = '<option value="">-- Choisir --</option>'
    for (eid, nom, type_ev, type_det, aff_sim, dc) in liste_evenements:
        sel = "selected" if (evenement_cible_id == eid) else ""
        options_evt += f'<option value="{eid}" {sel}>{echapper_html(nom)} (# {eid})</option>'

    options_etat = ""
    for et in ("actif", "inactif"):
        sel = "selected" if etat_evenement == et else ""
        options_etat += f'<option value="{echapper_html(et)}" {sel}>{echapper_html(et)}</option>'

    print(f"""
        <details open>
          <summary>Constat (Ec)</summary>

          <div class="message" style="margin-top:10px;">
            Constat objet = compare une stat (prix moyen / CA) sur une LISTE d objets.<br>
            Constat evenement = observe l etat (actif/inactif) d un evenement.
          </div>

          <label class="label">Constat sur</label>
          <select class="champ-select" name="type_constat">
            <option value="objet" {"selected" if type_constat=="objet" else ""}>Objet (liste)</option>
            <option value="evenement" {"selected" if type_constat=="evenement" else ""}>Evenement (etat)</option>
          </select>

          <details style="margin-top:10px;" {"open" if type_constat=="objet" else ""}>
            <summary>Regle sur OBJET</summary>

            <label class="label">Stat</label>
            <select class="champ-select" name="champ_constat">{options_stats}</select>

            <label class="label">Operateur</label>
            <select class="champ-select" name="operateur_constat">{options_op}</select>

            <label class="label">Valeur</label>
            <input class="champ-texte" type="text" name="valeur_constat" value="{echapper_html(valeur_constat_str)}">

            <div class="message" style="margin-top:10px;">
              Cible: la liste d objets (colonne droite / selection).
            </div>
          </details>

          <details style="margin-top:10px;" {"open" if type_constat=="evenement" else ""}>
            <summary>Regle sur EVENEMENT</summary>

            <label class="label">Evenement cible</label>
            <select class="champ-select" name="evenement_cible_id">{options_evt}</select>

            <label class="label">Etat attendu</label>
            <select class="champ-select" name="etat_evenement">{options_etat}</select>
          </details>

        </details>
    """)

# -------------------------
# MODE Ep
# -------------------------
if mode == "Ep":
    # Actions parametriques
    options_action = ""
    actions = [
        ("coef_evolution", "Coef evolution (ex: 0.05 = +5%)"),
        ("mult_prix_moyen", "Multiplier prix moyen (ex: 1.10)"),
        ("delta_prix_moyen", "Ajouter au prix moyen (ex: +2)"),
        ("mult_CA", "Multiplier CA (ex: 0.80)"),
    ]
    for code, lib in actions:
        sel = "selected" if action_param == code else ""
        options_action += f'<option value="{echapper_html(code)}" {sel}>{echapper_html(lib)}</option>'

    # Options familles / types
    options_fam = '<option value="">-- Choisir --</option>'
    for f in liste_familles:
        sel = "selected" if appliquer_famille == f else ""
        options_fam += f'<option value="{echapper_html(f)}" {sel}>{echapper_html(f)}</option>'

    options_typ = '<option value="">-- Choisir --</option>'
    for t in liste_types:
        sel = "selected" if appliquer_type == t else ""
        options_typ += f'<option value="{echapper_html(t)}" {sel}>{echapper_html(t)}</option>'

    print(f"""
        <details open>
          <summary>Parametrique (Ep)</summary>

          <div class="message" style="margin-top:10px;">
            "Appliquer a" controle la cible.<br>
            Si tu ne choisis rien: <strong>tout</strong>.
          </div>

          <label class="label">Appliquer a</label>
          <select class="champ-select" name="appliquer_portee">
            <option value="tout" {"selected" if appliquer_portee=="tout" else ""}>Tout (defaut)</option>
            <option value="famille" {"selected" if appliquer_portee=="famille" else ""}>Famille</option>
            <option value="type" {"selected" if appliquer_portee=="type" else ""}>Type</option>
            <option value="liste" {"selected" if appliquer_portee=="liste" else ""}>Objets precis (liste)</option>
          </select>

          <details style="margin-top:10px;" {"open" if appliquer_portee=="famille" else ""}>
            <summary>Choisir une famille</summary>
            <select class="champ-select" name="appliquer_famille">{options_fam}</select>
          </details>

          <details style="margin-top:10px;" {"open" if appliquer_portee=="type" else ""}>
            <summary>Choisir un type</summary>
            <select class="champ-select" name="appliquer_type">{options_typ}</select>
          </details>

          <details style="margin-top:10px;" {"open" if appliquer_portee=="liste" else ""}>
            <summary>Objets precis (liste)</summary>
            <div class="message" style="margin-top:10px;">
              Utilise la colonne droite pour ajouter/retirer des objets.
              Si la liste est vide, on retombe sur "tout".
            </div>
          </details>

          <label class="label">Action</label>
          <select class="champ-select" name="action_param">{options_action}</select>

          <label class="label">Valeur</label>
          <input class="champ-texte" type="text" name="valeur_param" value="{echapper_html(valeur_param_str)}">

        </details>
    """)

# -------------------------
# MODE Ea
# -------------------------
if mode == "Ea":
    # Dropdown evenements (pour A et P)
    options_evt_A = '<option value="">-- Choisir A --</option>'
    options_evt_P = '<option value="">-- Choisir P --</option>'
    for (eid, nom, type_ev, type_det, aff_sim, dc) in liste_evenements:
        selA = "selected" if (si_evenement_id == eid) else ""
        selP = "selected" if (faire_evenement_id == eid) else ""
        options_evt_A += f'<option value="{eid}" {selA}>{echapper_html(nom)} (# {eid})</option>'
        options_evt_P += f'<option value="{eid}" {selP}>{echapper_html(nom)} (# {eid})</option>'

    options_etat = ""
    for et in ("actif", "inactif"):
        sel = "selected" if si_etat == et else ""
        options_etat += f'<option value="{echapper_html(et)}" {sel}>{echapper_html(et)}</option>'

    options_faire = ""
    for ft, lib in (
        ("activer", "Activer P"),
        ("desactiver", "Desactiver P"),
        ("changer_probabilite", "Changer probabilite de P"),
    ):
        sel = "selected" if faire_type == ft else ""
        options_faire += f'<option value="{echapper_html(ft)}" {sel}>{echapper_html(lib)}</option>'

    print(f"""
        <details open>
          <summary>Algorithmique (Ea) - Si ... faire ...</summary>

          <div class="message" style="margin-top:10px;">
            Version 1 simple: si A est actif/inactif, alors on modifie P.<br>
            (C est exactement la base action/reaction pour sim_calc.py.)
          </div>

          <label class="label">Probabilite de declenchement (0..1) (optionnel)</label>
          <input class="champ-texte" type="text" name="regle_probabilite" value="{echapper_html(regle_probabilite_str)}"
                 placeholder="Ex: 0.6">

          <label class="label">Parametre U (optionnel)</label>
          <input class="champ-texte" type="text" name="parametre_u" value="{echapper_html(parametre_u)}"
                 placeholder="Ex: U">

          <details open style="margin-top:10px;">
            <summary>Si ...</summary>

            <label class="label">Evenement A</label>
            <select class="champ-select" name="si_evenement_id">{options_evt_A}</select>

            <label class="label">Etat</label>
            <select class="champ-select" name="si_etat">{options_etat}</select>
          </details>

          <details open style="margin-top:10px;">
            <summary>Faire ...</summary>

            <label class="label">Action</label>
            <select class="champ-select" name="faire_type">{options_faire}</select>

            <label class="label">Evenement P</label>
            <select class="champ-select" name="faire_evenement_id">{options_evt_P}</select>

            <label class="label">Nouvelle probabilite de P (si besoin)</label>
            <input class="champ-texte" type="text" name="faire_probabilite" value="{echapper_html(faire_probabilite_str)}"
                   placeholder="Ex: 0.3">
          </details>

        </details>
    """)

# Bouton creer (commun)
print("""
        <div class="ligne-actions">
          <button class="bouton" type="submit">Creer l evenement</button>
        </div>

      </form>
    </div>
""")

# ============================================================
# Colonne droite: objets (liste) + recherche
# ============================================================
print(f"""
    <div class="carte">
      <h2>Liste d objets (utile pour Ec objet / Ep liste)</h2>

      <div class="message">
        Sans JavaScript: tu recherches, puis tu ajoutes a la liste.<br>
        Cette liste sert uniquement quand tu choisis "liste".
      </div>

      <form method="get" action="/cgi-bin/evenement.py">
        <input type="hidden" name="uid" value="{echapper_html(uid)}">
        <input type="hidden" name="mode" value="{echapper_html(mode)}">
        <input type="hidden" name="type_constat" value="{echapper_html(type_constat)}">
        <input type="hidden" name="selection_ids" value="{echapper_html(selection_ids_texte)}">

        <!-- On conserve aussi les champs Ep/Ea importants pour ne pas perdre l etat -->
        <input type="hidden" name="appliquer_portee" value="{echapper_html(appliquer_portee)}">
        <input type="hidden" name="appliquer_famille" value="{echapper_html(appliquer_famille)}">
        <input type="hidden" name="appliquer_type" value="{echapper_html(appliquer_type)}">

        <label class="label">Recherche objet</label>
        <input class="champ-texte" type="text" name="recherche_objet" value="{echapper_html(recherche_objet)}"
               placeholder="Ex: stylo, mur...">

        <div class="ligne-actions">
          <button class="bouton" type="submit">Chercher</button>
          <a class="bouton bouton-secondaire"
             href="/cgi-bin/evenement.py?uid={uid_encode}&mode={encoder_url(mode)}&type_constat={encoder_url(type_constat)}&selection_ids={encoder_url(selection_ids_texte)}&appliquer_portee={encoder_url(appliquer_portee)}">
             Reset recherche
          </a>
        </div>
      </form>
""")

# Resultats recherche
if recherche_objet:
    if not table_stat_objects_ok:
        print('<div class="message bad">stat_objects absent: impossible de chercher des objets.</div>')
    elif resultats_objets:
        print('<div class="zone-resultats">')
        for (oid, nom) in resultats_objets:
            lien_ajout = (
                "/cgi-bin/evenement.py?uid=" + uid_encode +
                "&mode=" + encoder_url(mode) +
                "&type_constat=" + encoder_url(type_constat) +
                "&action=ajouter_selection" +
                "&objet_ajout_id=" + str(oid) +
                "&recherche_objet=" + encoder_url(recherche_objet) +
                "&selection_ids=" + encoder_url(selection_ids_texte) +
                "&appliquer_portee=" + encoder_url(appliquer_portee) +
                "&appliquer_famille=" + encoder_url(appliquer_famille) +
                "&appliquer_type=" + encoder_url(appliquer_type)
            )

            prix = lire_stat_objet(connexion, int(oid), "Prix_Moyen_Actuel")
            ca = lire_stat_objet(connexion, int(oid), "CA_2025_2035_MDEUR")
            mini = ""
            if prix is not None:
                mini += "Prix~ " + str(round(prix, 3)) + "  "
            if ca is not None:
                mini += "CA~ " + str(round(ca, 3))

            print(f"""
              <div class="ligne-resultat">
                <div>
                  <strong>{echapper_html(nom)}</strong>
                  <span class="petit">(# {echapper_html(oid)})</span><br>
                  <span class="petit">{echapper_html(mini)}</span>
                </div>
                <a class="bouton" href="{lien_ajout}">Ajouter</a>
              </div>
            """)
        print("</div>")
    else:
        print(f'<div class="message bad">Aucun resultat pour "{echapper_html(recherche_objet)}".</div>')

# Liste selection
print('<h2 style="margin-top:18px;">Objets dans la liste</h2>')
if not selection_ids:
    print('<div class="message">Liste vide.</div>')
else:
    print('<div class="zone-resultats">')
    for oid in selection_ids:
        nom = recuperer_nom_objet(connexion, colonne_id_objet, colonne_nom_objet, oid) if table_stat_objects_ok else ""
        lien_retire = (
            "/cgi-bin/evenement.py?uid=" + uid_encode +
            "&mode=" + encoder_url(mode) +
            "&type_constat=" + encoder_url(type_constat) +
            "&action=retirer_selection" +
            "&objet_retire_id=" + str(oid) +
            "&recherche_objet=" + encoder_url(recherche_objet) +
            "&selection_ids=" + encoder_url(selection_ids_texte) +
            "&appliquer_portee=" + encoder_url(appliquer_portee) +
            "&appliquer_famille=" + encoder_url(appliquer_famille) +
            "&appliquer_type=" + encoder_url(appliquer_type)
        )
        print(f"""
          <div class="ligne-resultat">
            <div>
              <strong>{echapper_html(nom)}</strong>
              <span class="petit">(# {echapper_html(oid)})</span>
            </div>
            <a class="bouton bouton-secondaire" href="{lien_retire}">Retirer</a>
          </div>
        """)
    print("</div>")

lien_vider = (
    "/cgi-bin/evenement.py?uid=" + uid_encode +
    "&mode=" + encoder_url(mode) +
    "&type_constat=" + encoder_url(type_constat) +
    "&action=vider_selection" +
    "&recherche_objet=" + encoder_url(recherche_objet) +
    "&selection_ids=" + encoder_url(selection_ids_texte) +
    "&appliquer_portee=" + encoder_url(appliquer_portee) +
    "&appliquer_famille=" + encoder_url(appliquer_famille) +
    "&appliquer_type=" + encoder_url(appliquer_type)
)

print(f"""
      <div class="ligne-actions">
        <a class="bouton bouton-secondaire" href="{lien_vider}">Vider la liste</a>
      </div>

    </div>
  </div>
""")

# ============================================================
# Evenements existants (bas)
# ============================================================
print("""
  <div class="carte" style="margin-top:20px;">
    <h2>Evenements existants</h2>
    <div class="message">
      Ces evenements pourront etre imposes dans sim_calc.py (projection) ou utilises via Ea (action/reaction).
    </div>
""")

if not liste_evenements:
    print('<div class="message">Aucun evenement cree pour le moment.</div>')
else:
    print('<div class="zone-resultats" style="max-height:340px;">')
    for (eid, nom, type_ev, type_det, aff_sim, dc) in liste_evenements:
        badge = "E" if str(type_ev) == "E" else str(type_ev)
        det = str(type_det or "")
        petit_type = badge if badge != "E" else ("E (detail: " + (det if det else "?") + ")")

        lien_suppr = (
            "/cgi-bin/evenement.py?uid=" + uid_encode +
            "&action=supprimer&supprimer_id=" + str(eid) +
            "&mode=" + encoder_url(mode) +
            "&type_constat=" + encoder_url(type_constat) +
            "&selection_ids=" + encoder_url(selection_ids_texte) +
            "&recherche_objet=" + encoder_url(recherche_objet) +
            "&appliquer_portee=" + encoder_url(appliquer_portee)
        )

        print(f"""
          <div class="ligne-resultat">
            <div>
              <strong>{echapper_html(nom)}</strong>
              <span class="petit">(# {echapper_html(eid)} / {echapper_html(petit_type)})</span><br>
              <span class="petit">{echapper_html(dc)}</span>
            </div>
            <a class="lien-supprimer" href="{lien_suppr}">Supprimer</a>
          </div>
        """)
    print("</div>")

print("""
  </div>

</div>
</body>
</html>
""")

connexion.close()
