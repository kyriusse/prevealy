#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import urllib.parse
import html

print("Content-Type: text/html; charset=utf-8\n")

REPERTOIRE_UNIVERS = "cgi-bin/universes/"

def recuperer_parametre(nom, defaut=""):
    """Récupère un paramètre depuis la query string."""
    chaine_requete = os.environ.get("QUERY_STRING", "")
    parametres = urllib.parse.parse_qs(chaine_requete, keep_blank_values=True)
    return parametres.get(nom, [defaut])[0]

def chemin_univers(identifiant_univers):
    """Construit un chemin sécurisé vers une base d'univers."""
    identifiant_securise = "".join(
        [caractere for caractere in identifiant_univers if caractere.isalnum() or caractere in ("-", "_")]
    )
    return os.path.join(REPERTOIRE_UNIVERS, f"universe_{identifiant_securise}.db")

def recuperer_nom_univers(identifiant_univers):
    """Retourne le nom d'un univers à partir de son identifiant."""
    try:
        fichier_noms = os.path.join(REPERTOIRE_UNIVERS, "univers_names.txt")
        if os.path.exists(fichier_noms):
            with open(fichier_noms, "r", encoding="utf-8") as fichier:
                for ligne in fichier:
                    if "," in ligne:
                        identifiant, nom = ligne.strip().split(",", 1)
                        if identifiant == identifiant_univers:
                            return nom
    except Exception:
        pass
    return "Nom inconnu"

def recuperer_infos_table(chemin_bdd, nom_table):
    """Récupère les informations de colonnes d'une table."""
    connexion = sqlite3.connect(chemin_bdd)
    curseur = connexion.cursor()
    curseur.execute(f"PRAGMA table_info({nom_table})")
    infos = curseur.fetchall()
    connexion.close()
    return infos

def recuperer_noms_colonnes(chemin_bdd, nom_table):
    """Retourne la liste des noms de colonnes d'une table."""
    try:
        infos = recuperer_infos_table(chemin_bdd, nom_table)
        return [colonne[1] for colonne in infos]
    except Exception:
        return []

def moyenne_intelligente(ligne, index_depart=3):
    """Calcule une moyenne sur les colonnes numériques d'une ligne."""
    valeurs = [
        valeur for valeur in ligne[index_depart:] if valeur is not None and isinstance(valeur, (int, float))
    ]
    if not valeurs:
        return 0.0
    return sum(valeurs) / len(valeurs)

def trouver_colonne(colonnes, candidats):
    """Trouve une colonne par correspondance de nom."""
    colonnes_minuscule = {colonne.lower(): colonne for colonne in colonnes}
    for candidat in candidats:
        if candidat.lower() in colonnes_minuscule:
            return colonnes_minuscule[candidat.lower()]
    return None

def trouver_colonne_nom(colonnes):
    """Trouve la colonne correspondant au nom d'objet."""
    for colonne in colonnes:
        colonne_minuscule = colonne.lower()
        if "objet" in colonne_minuscule or "nom" in colonne_minuscule or "name" in colonne_minuscule:
            return colonne
    return colonnes[1] if len(colonnes) > 1 else colonnes[0]

def trouver_colonne_type(colonnes):
    """Trouve la colonne correspondant au type d'objet."""
    for colonne in colonnes:
        colonne_minuscule = colonne.lower()
        if colonne_minuscule in ("type", "types"):
            return colonne
    # parfois "Type_" etc
    for colonne in colonnes:
        if "type" in colonne.lower():
            return colonne
    return None

def trouver_colonne_prix(colonnes):
    """Trouve la colonne correspondant au prix."""
    for colonne in colonnes:
        colonne_minuscule = colonne.lower()
        if "prix" in colonne_minuscule or "price" in colonne_minuscule:
            return colonne
    return None

def recuperer_objets_crees(identifiant_univers):
    """Liste les objets créés dans un univers."""
    chemin_bdd = chemin_univers(identifiant_univers)
    try:
        colonnes = recuperer_noms_colonnes(chemin_bdd, "stat_objects")
        if not colonnes:
            return []

        colonne_type = trouver_colonne_type(colonnes)
        colonne_nom = trouver_colonne_nom(colonnes)

        # On recupere rowid pour supprimer proprement
        connexion = sqlite3.connect(chemin_bdd)
        curseur = connexion.cursor()

        if colonne_type:
            curseur.execute(
                f"""
                SELECT rowid, *
                FROM stat_objects
                WHERE [{colonne_type}] IN ('Fusion', 'Moyenne ponderee', 'Moyenne pondérée')
                ORDER BY rowid DESC
                """
            )
        else:
            # repli : liste tout
            curseur.execute("SELECT rowid, * FROM stat_objects ORDER BY rowid DESC")

        lignes = curseur.fetchall()
        connexion.close()

        colonne_prix = trouver_colonne_prix(colonnes)
        # Les colonnes correspondent à "*" (sans rowid)
        # Schéma : (rowid, col0, col1, col2, ...)
        objets_traites = []
        for ligne in lignes:
            identifiant = ligne[0]
            donnees = list(ligne[1:])  # les vraies colonnes

            # Trouver l'index du nom et du type dans la ligne
            try:
                index_nom = colonnes.index(colonne_nom)
            except Exception:
                index_nom = 0
            try:
                index_type = colonnes.index(colonne_type) if colonne_type else 2
            except Exception:
                index_type = 2

            nom_objet = donnees[index_nom] if index_nom < len(donnees) else "Sans nom"
            type_objet = donnees[index_type] if index_type < len(donnees) else ""

            # moyenne auto sur les colonnes a partir de l index 3 (comme ton code)
            moyenne = moyenne_intelligente(donnees, index_depart=3)

            prix_affichage = None
            if colonne_prix:
                try:
                    index_prix = colonnes.index(colonne_prix)
                    valeur = donnees[index_prix] if index_prix < len(donnees) else None
                    if isinstance(valeur, (int, float)):
                        prix_affichage = float(valeur)
                except Exception:
                    prix_affichage = None

            if prix_affichage is None:
                prix_affichage = float(moyenne)

            objets_traites.append((identifiant, nom_objet, type_objet, prix_affichage))

        return objets_traites

    except Exception:
        return []

def supprimer_objet(identifiant_univers, valeur_rowid):
    """Supprime un objet créé dans un univers."""
    chemin_bdd = chemin_univers(identifiant_univers)
    valeur_rowid = str(valeur_rowid).strip()
    try:
        identifiant = int(valeur_rowid)
    except Exception:
        return False

    try:
        colonnes = recuperer_noms_colonnes(chemin_bdd, "stat_objects")
        if not colonnes:
            return False

        colonne_nom = trouver_colonne_nom(colonnes)

        connexion = sqlite3.connect(chemin_bdd)
        curseur = connexion.cursor()

        # Recuperer le nom AVANT suppression (pour nettoyer liaison)
        curseur.execute(f"SELECT [{colonne_nom}] FROM stat_objects WHERE rowid = ?", (identifiant,))
        resultat = curseur.fetchone()
        if not resultat:
            connexion.close()
            return False

        nom_objet = resultat[0]

        # Nettoyage liaison (si colonne existe)
        colonne_liaison = None
        for colonne in colonnes:
            if colonne.lower() == "liaison":
                colonne_liaison = colonne
                break

        if colonne_liaison:
            # Supporter plusieurs formats eventuels
            candidats = [
                f"lie a {nom_objet}",
                f"lié à {nom_objet}",
                f"lie a {str(nom_objet)}",
                f"lié à {str(nom_objet)}",
            ]
            curseur.execute(
                f"""
                UPDATE stat_objects
                SET [{colonne_liaison}] = 'null'
                WHERE [{colonne_liaison}] IN ({",".join(["?"] * len(candidats))})
                """,
                tuple(candidats),
            )

        # Suppression par rowid (fiable)
        curseur.execute("DELETE FROM stat_objects WHERE rowid = ?", (identifiant,))
        connexion.commit()
        connexion.close()
        return True

    except Exception:
        try:
            connexion.close()
        except Exception:
            pass
        return False

# --- Logique de l application ---
identifiant_univers = recuperer_parametre("uid", "")
action = recuperer_parametre("action", "")
identifiant_objet = recuperer_parametre("object_id", "")

message, classe_message = "", ""
if action == "delete" and identifiant_objet:
    if supprimer_objet(identifiant_univers, identifiant_objet):
        message, classe_message = "Objet supprime avec succes !", "success"
    else:
        message, classe_message = "Erreur lors de la suppression.", "error"

nom_univers = recuperer_nom_univers(identifiant_univers)
objets_crees = recuperer_objets_crees(identifiant_univers)

# --- Sortie HTML ---
def echapper_html(texte):
    """Échappe le texte pour un affichage HTML sûr."""
    return html.escape("" if texte is None else str(texte))

sortie_html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <title>Liste des Objets - {echapper_html(nom_univers)}</title>
    <style>
        body {{ margin: 0; font-family: sans-serif; color: white; background: url('/create_stat_object.png') center/cover fixed; }}
        .panel {{ width: 850px; margin: 50px auto; background: url('/fond_filtre_pannel.png') no-repeat center/100% 100%; padding: 40px; min-height: 500px; }}
        h1 {{ text-align: center; }}
        .back-btn {{ position: fixed; top: 20px; left: 20px; width: 45px; height: 45px; background: rgba(74, 42, 80, 0.9); border-radius: 50%; color: white; text-decoration: none; display: flex; align-items: center; justify-content: center; font-size: 20px; }}
        .message {{ padding: 10px; margin-bottom: 20px; border-radius: 4px; text-align: center; background: rgba(0, 128, 0, 0.4); }}
        .message.error {{ background: rgba(128, 0, 0, 0.4); }}
        .object-item {{ display: flex; justify-content: space-between; background: rgba(0,0,0,0.7); margin: 10px 0; padding: 20px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.1); }}
        .obj-title {{ font-size: 1.2em; font-weight: bold; color: #FFD86A; }}
        .obj-type {{ font-size: 0.9em; color: #87CEEB; }}
        .obj-val {{ color: #90EE90; margin-top: 5px; font-weight: bold; }}
        .auto-info {{ font-size: 0.7em; background: #555; padding: 2px 6px; border-radius: 4px; margin-left: 10px; }}
        .delete-btn {{ background: #a83434; color: white; text-decoration: none; padding: 10px 20px; border-radius: 5px; align-self: center; }}
    </style>
</head>
<body>
    <a href="/cgi-bin/personnalisation_objet.py?uid={echapper_html(identifiant_univers)}" class="back-btn">←</a>
    <div class="panel">
        <h1>Objets crees : {echapper_html(nom_univers)}</h1>
        {f'<div class="message {echapper_html(classe_message)}">{echapper_html(message)}</div>' if message else ''}

        <div class="list">
            {"<p style='text-align:center'>Aucun objet dans cet univers.</p>" if not objets_crees else ""}
            {''.join([f'''
            <div class="object-item">
                <div>
                    <div class="obj-title">{echapper_html(obj[1])}</div>
                    <div class="obj-type">Type : {echapper_html(obj[2])}</div>
                    <div class="obj-val">Valeur : {float(obj[3]):.2f} <span class="auto-info">Moyenne Auto</span></div>
                </div>
                <a href="?uid={echapper_html(identifiant_univers)}&action=delete&object_id={urllib.parse.quote(str(obj[0]))}" class="delete-btn" onclick="return confirm('Supprimer cet objet ?')">Supprimer</a>
            </div>
            ''' for obj in objets_crees])}
        </div>
    </div>
</body>
</html>"""

print(sortie_html)
