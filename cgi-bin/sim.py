#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""

Menu / page de simulation deterministe "de base".

But:
- Choisir quoi projeter (objets / famille / type)
- Choisir le nombre d annees
- Ajouter des evenements a un planning (annee d arrivee + coef effet)
- Tenir compte des liaisons via le moteur (sim_calc.py)
- Afficher une courbe (SVG sans JS) + un resume lisible

Contraintes:
- CGI pur
- Sans JavaScript
- Variables et fonctions en francais
- Beaucoup de commentaires
"""

import os
import sqlite3
import urllib.parse
import html
import difflib

from sim_calc import executer_simulation, detecter_colonnes_statistiques
from stats_utils import generer_svg_courbes


# ============================================================
# En tete CGI obligatoire
# ============================================================
print("Content-Type: text/html; charset=utf-8\n")


# ============================================================
# Constantes
# ============================================================
DOSSIER_UNIVERS = "cgi-bin/universes/"


# ============================================================
# Utils GET
# ============================================================

def lire_parametre_get(nom, defaut=""):
    """Lit un parametre GET (?nom=...) et renvoie une seule valeur."""
    qs = os.environ.get("QUERY_STRING", "")
    params = urllib.parse.parse_qs(qs, keep_blank_values=True)
    return params.get(nom, [defaut])[0]


def echapper_html(texte):
    """Echappe texte pour HTML (anti injection)."""
    return html.escape("" if texte is None else str(texte))


def construire_chemin_univers(uid):
    """Construit le chemin du fichier SQLite d un univers."""
    uid_sain = "".join([c for c in uid if c.isalnum() or c in ("-", "_")])
    return os.path.join(DOSSIER_UNIVERS, "universe_" + uid_sain + ".db")


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


def ids_depuis_chaine(chaine):
    """Transforme '1,2,3' -> [1,2,3] (uniques)."""
    resultat = []
    for morceau in (chaine or "").split(","):
        m = morceau.strip()
        if m.isdigit():
            v = int(m)
            if v not in resultat:
                resultat.append(v)
    return resultat


def chaine_depuis_ids(liste_ids):
    """Transforme [1,2,3] -> '1,2,3'."""
    return ",".join([str(x) for x in (liste_ids or [])])


def planning_depuis_chaine(chaine):
    """
    Transforme 'eid:annee:cp:cc,eid:annee:cp:cc' -> liste tuples.
    Exemple: '12:0:0.9:1.0,15:3:1.1:1.0'
    """
    resultat = []
    for bloc in (chaine or "").split(","):
        bloc = bloc.strip()
        if not bloc:
            continue
        parts = bloc.split(":")
        if len(parts) < 2:
            continue
        eid = parts[0].strip()
        ar = parts[1].strip()
        cp = parts[2].strip() if len(parts) >= 3 else "1.0"
        cc = parts[3].strip() if len(parts) >= 4 else "1.0"
        if eid.isdigit():
            resultat.append((ar, int(eid), cp, cc))
    return resultat


def planning_vers_chaine(planning):
    """Inverse de planning_depuis_chaine."""
    blocs = []
    for (ar, eid, cp, cc) in (planning or []):
        blocs.append("{}:{}:{}:{}".format(ar, eid, cp, cc))
    return ",".join(blocs)


def suggestion_mot_proche(texte, noms, max_suggestions=8):
    """Suggestions proches (fallback)."""
    if not texte:
        return []
    return difflib.get_close_matches(texte, noms, n=max_suggestions, cutoff=0.60)


# ============================================================
# Contexte univers
# ============================================================

uid = lire_parametre_get("uid", "").strip()
if not uid:
    print("<h1>Erreur: univers non specifie</h1>")
    raise SystemExit

uid_encode = urllib.parse.quote(uid)
nom_univers = recuperer_nom_univers(uid)

chemin_bdd = construire_chemin_univers(uid)
if not os.path.exists(chemin_bdd):
    print("<h1>Erreur: BDD univers introuvable</h1>")
    print("<p>Chemin attendu: {}</p>".format(echapper_html(chemin_bdd)))
    raise SystemExit

connexion = sqlite3.connect(chemin_bdd)
colonnes = detecter_colonnes_statistiques(connexion)

if not colonnes.get("id") or not colonnes.get("nom"):
    print("<h1>Erreur: stat_objects invalide (id/nom manquants)</h1>")
    connexion.close()
    raise SystemExit


# ============================================================
# Parametres UI
# ============================================================

action = lire_parametre_get("action", "").strip()

# Selection manuelle (objets)
selection_ids_texte = lire_parametre_get("selection_ids", "").strip()
selection_ids = ids_depuis_chaine(selection_ids_texte)

# Recherche d objets
recherche_objet = lire_parametre_get("recherche_objet", "").strip()

# Famille / Type
famille_choisie = lire_parametre_get("famille", "").strip()
type_choisi = lire_parametre_get("type", "").strip()

# Nombre d annees + annee depart
nb_annees_str = lire_parametre_get("nb_annees", "10").strip()
annee_depart_str = lire_parametre_get("annee_depart", "2026").strip()

# Planning evenements (stocke dans l URL)
planning_texte = lire_parametre_get("planning", "").strip()
planning = planning_depuis_chaine(planning_texte)

# Champs "ajouter un evenement"
evenement_ajout_id_str = lire_parametre_get("evenement_ajout_id", "").strip()
evenement_ajout_annee_str = lire_parametre_get("evenement_ajout_annee", "0").strip()
evenement_ajout_coef_prix_str = lire_parametre_get("evenement_ajout_coef_prix", "1.0").strip()
evenement_ajout_coef_ca_str = lire_parametre_get("evenement_ajout_coef_ca", "1.0").strip()


# ============================================================
# Messages utilisateur
# ============================================================

message_ok = ""
message_erreur = ""


# ============================================================
# Actions selection
# ============================================================

if action == "ajouter_selection":
    oid_str = lire_parametre_get("objet_ajout_id", "").strip()
    if oid_str.isdigit():
        oid = int(oid_str)
        if oid not in selection_ids:
            selection_ids.append(oid)
        message_ok = "Objet ajoute a la selection."
    else:
        message_erreur = "Objet invalide (ajout)."

if action == "retirer_selection":
    oid_str = lire_parametre_get("objet_retire_id", "").strip()
    if oid_str.isdigit():
        oid = int(oid_str)
        selection_ids = [x for x in selection_ids if x != oid]
        message_ok = "Objet retire."
    else:
        message_erreur = "Objet invalide (retrait)."

selection_ids_texte = chaine_depuis_ids(selection_ids)


# ============================================================
# Actions planning evenements
# ============================================================

if action == "ajouter_planning":
    if not evenement_ajout_id_str.isdigit():
        message_erreur = "Choisis un evenement valide."
    else:
        eid = int(evenement_ajout_id_str)
        # Stockage annee_relative (int), coef_prix, coef_ca
        ar = evenement_ajout_annee_str.strip()
        cp = evenement_ajout_coef_prix_str.strip()
        cc = evenement_ajout_coef_ca_str.strip()
        planning.append((ar, eid, cp, cc))
        planning_texte = planning_vers_chaine(planning)
        message_ok = "Evenement ajoute au planning."

if action == "vider_planning":
    planning = []
    planning_texte = ""
    message_ok = "Planning vide."

if action == "supprimer_planning":
    idx_str = lire_parametre_get("planning_idx", "").strip()
    if idx_str.isdigit():
        idx = int(idx_str)
        if 0 <= idx < len(planning):
            planning.pop(idx)
            planning_texte = planning_vers_chaine(planning)
            message_ok = "Evenement retire du planning."
        else:
            message_erreur = "Index planning invalide."
    else:
        message_erreur = "Index planning invalide."


# ============================================================
# Lire liste familles / types (pour menus)
# ============================================================

def lister_distinct(conn, nom_col):
    """Liste des valeurs distinctes (non vides) d une colonne."""
    if not nom_col:
        return []
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT DISTINCT [{c}] FROM stat_objects WHERE [{c}] IS NOT NULL AND TRIM([{c}]) != '' ORDER BY [{c}] COLLATE NOCASE".format(
                c=nom_col
            )
        )
        return [r[0] for r in cur.fetchall()]
    except Exception:
        return []


familles = lister_distinct(connexion, colonnes.get("famille"))
types = lister_distinct(connexion, colonnes.get("type"))


# ============================================================
# Recherche objets (liste + suggestions)
# ============================================================

resultats_recherche = []
suggestions = []

if recherche_objet:
    cur = connexion.cursor()
    try:
        motif = "%" + recherche_objet + "%"
        cur.execute(
            "SELECT [{idc}], [{nomc}] FROM stat_objects WHERE [{nomc}] LIKE ? ORDER BY [{nomc}] COLLATE NOCASE LIMIT 25".format(
                idc=colonnes["id"], nomc=colonnes["nom"]
            ),
            (motif,)
        )
        resultats_recherche = cur.fetchall()
    except Exception:
        resultats_recherche = []

    # Si rien, proposer un mot proche
    if not resultats_recherche:
        try:
            cur.execute(
                "SELECT [{nomc}] FROM stat_objects WHERE [{nomc}] IS NOT NULL AND TRIM([{nomc}]) != ''".format(
                    nomc=colonnes["nom"]
                )
            )
            noms = [r[0] for r in cur.fetchall()]
            suggestions = suggestion_mot_proche(recherche_objet, noms, max_suggestions=8)
        except Exception:
            suggestions = []


# ============================================================
# Lire liste evenements (pour planning)
# ============================================================

def lister_evenements(conn):
    """Liste evenements recents."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, nom FROM evenements ORDER BY id DESC LIMIT 120")
        return cur.fetchall()
    except Exception:
        return []

liste_evenements = lister_evenements(connexion)


# ============================================================
# Construire liste finale d objets a projeter
# ============================================================

def construire_ids_projection(conn, col, selection, famille, type_obj):
    """
    Regle:
    - si selection non vide => base = selection
    - sinon si famille/type choisis => base = tous objets famille/type
    - sinon => vide (l utilisateur doit choisir quelque chose)
    """
    if selection:
        return list(selection)

    # Famille prioritaire si fournie
    if famille and col.get("famille"):
        cur = conn.cursor()
        cur.execute(
            "SELECT [{idc}] FROM stat_objects WHERE [{fc}] = ?".format(
                idc=col["id"], fc=col["famille"]
            ),
            (famille,)
        )
        return [r[0] for r in cur.fetchall()]

    # Type si fourni
    if type_obj and col.get("type"):
        cur = conn.cursor()
        cur.execute(
            "SELECT [{idc}] FROM stat_objects WHERE [{tc}] = ?".format(
                idc=col["id"], tc=col["type"]
            ),
            (type_obj,)
        )
        return [r[0] for r in cur.fetchall()]

    return []


ids_projection = construire_ids_projection(connexion, colonnes, selection_ids, famille_choisie, type_choisi)


# ============================================================
# Lancer simulation si demande
# ============================================================

resultat_simulation = None
svg = ""

if action == "simuler":
    if not ids_projection:
        message_erreur = "Choisis au moins un objet (selection), ou une famille, ou un type."
    else:
        resultat_simulation = executer_simulation(
            connexion=connexion,
            ids_projection=ids_projection,
            nb_annees=nb_annees_str,
            annee_depart=annee_depart_str,
            planning_evenements=planning
        )

        if resultat_simulation:
            # Courbe globale prix total
            pts_prix_total = []
            for i, annee in enumerate(resultat_simulation.get("annees", [])):
                pts_prix_total.append((annee, resultat_simulation.get("prix_moyen_total", [])[i]))

            # Courbe globale ca total (si dispo)
            pts_ca_total = []
            for i, annee in enumerate(resultat_simulation.get("annees", [])):
                pts_ca_total.append((annee, resultat_simulation.get("ca_total", [])[i]))

            series = {
                "Prix moyen total": pts_prix_total
            }

            # Afficher le CA seulement si non nul
            if pts_ca_total and max([p[1] for p in pts_ca_total]) > 0:
                series["CA total"] = pts_ca_total

            svg = generer_svg_courbes(series, titre="Simulation - {}".format(nom_univers))


# ============================================================
# HTML / CSS (DA mystique proche accueil)
# ============================================================

print("""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Simulation - {nom}</title>
<style>
body {{
  margin:0;
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

.bouton-liaison {{
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
  text-align:center;
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
  display:grid;
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
  margin:0 0 12px 0;
  font-size: 18px;
}}

.label {{
  display:block;
  margin: 10px 0 6px 0;
  font-size: 12px;
  opacity: 0.90;
}}

.champ-texte, .champ-select, textarea {{
  width:100%;
  box-sizing:border-box;
  padding: 12px;
  border-radius: 14px;
  background: rgba(0,0,0,0.28);
  color:#ffffff;
  border: 1px solid rgba(255,255,255,0.12);
  outline:none;
}}
textarea {{ min-height: 70px; resize: vertical; }}

.ligne-actions {{
  margin-top: 14px;
  display:flex;
  gap: 10px;
  justify-content:flex-end;
  align-items:center;
  flex-wrap:wrap;
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
  overflow:auto;
}}

.ligne-resultat {{
  display:flex;
  justify-content:space-between;
  align-items:center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}}
.ligne-resultat:last-child {{ border-bottom:none; }}

.petit {{
  font-size:12px;
  opacity:0.82;
}}

.table {{
  width:100%;
  border-collapse:collapse;
  margin-top:10px;
  font-size:13px;
}}
.table th, .table td {{
  text-align:left;
  padding: 10px 8px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  vertical-align:top;
}}

.lien-supprimer {{
  color: rgba(255,170,170,0.95);
  text-decoration:none;
  border: 1px solid rgba(255,120,120,0.30);
  padding: 6px 10px;
  border-radius: 999px;
  display:inline-block;
}}
</style>
</head>

<body>
<a class="bouton-retour" href="/cgi-bin/univers_dashboard.py?uid={uid}" title="Retour"></a>
<a class="bouton-liaison" href="/cgi-bin/liaison.py?uid={uid}" title="Liaison">Liaison</a>

<div class="panel">
  <h1>Simulation (deterministe)</h1>
  <div class="ligne-univers">
    Univers : <strong>{nom}</strong> &nbsp;|&nbsp; ID : {uid_brut}
  </div>
""".format(
    nom=echapper_html(nom_univers),
    uid=uid_encode,
    uid_brut=echapper_html(uid)
))

# Messages
if message_ok:
    print('<div class="message ok">{}</div>'.format(echapper_html(message_ok)))
if message_erreur:
    print('<div class="message bad">{}</div>'.format(echapper_html(message_erreur)))

print("""
  <div class="grille">
    <div class="carte">
      <h2>1) Choisir quoi projeter</h2>

      <div class="message">
        Regle: si tu as une selection, elle est prioritaire. Sinon tu peux choisir une famille ou un type.
      </div>

      <form method="get" action="/cgi-bin/sim.py">
        <input type="hidden" name="uid" value="{uid}">
        <input type="hidden" name="selection_ids" value="{sel}">
        <input type="hidden" name="planning" value="{planning}">
        <label class="label">Recherche objet</label>
        <input class="champ-texte" type="text" name="recherche_objet" value="{rech}" placeholder="Ex: stylo, mur...">
        <div class="ligne-actions">
          <button class="bouton" type="submit">Chercher</button>
          <a class="bouton bouton-secondaire" href="/cgi-bin/sim.py?uid={uid}">Reset</a>
        </div>
      </form>
""".format(
    uid=uid_encode,
    sel=echapper_html(selection_ids_texte),
    planning=echapper_html(planning_texte),
    rech=echapper_html(recherche_objet)
))

# Resultats recherche
if recherche_objet:
    if resultats_recherche:
        print('<div class="zone-resultats">')
        for oid, nom_obj in resultats_recherche:
            lien_ajout = (
                "/cgi-bin/sim.py?uid={uid}"
                "&action=ajouter_selection"
                "&objet_ajout_id={oid}"
                "&recherche_objet={rech}"
                "&selection_ids={sel}"
                "&planning={planning}"
                "&famille={fam}"
                "&type={typ}"
                "&nb_annees={na}"
                "&annee_depart={ad}"
            ).format(
                uid=uid_encode,
                oid=int(oid),
                rech=urllib.parse.quote(recherche_objet),
                sel=urllib.parse.quote(selection_ids_texte),
                planning=urllib.parse.quote(planning_texte),
                fam=urllib.parse.quote(famille_choisie),
                typ=urllib.parse.quote(type_choisi),
                na=urllib.parse.quote(nb_annees_str),
                ad=urllib.parse.quote(annee_depart_str)
            )
            print("""
            <div class="ligne-resultat">
              <div>
                <strong>{nom}</strong>
                <span class="petit">(# {oid})</span>
              </div>
              <a class="bouton" href="{lien}">Ajouter</a>
            </div>
            """.format(nom=echapper_html(nom_obj), oid=echapper_html(oid), lien=lien_ajout))
        print("</div>")
    else:
        print('<div class="message bad">Aucun resultat pour "{t}".</div>'.format(t=echapper_html(recherche_objet)))
        if suggestions:
            print('<div class="message">Suggestions:</div>')
            print('<div class="zone-resultats">')
            for s in suggestions:
                lien_s = (
                    "/cgi-bin/sim.py?uid={uid}"
                    "&recherche_objet={rech}"
                    "&selection_ids={sel}"
                    "&planning={planning}"
                ).format(
                    uid=uid_encode,
                    rech=urllib.parse.quote(s),
                    sel=urllib.parse.quote(selection_ids_texte),
                    planning=urllib.parse.quote(planning_texte)
                )
                print('<div class="ligne-resultat"><div>{}</div><a class="bouton bouton-secondaire" href="{}">Utiliser</a></div>'.format(
                    echapper_html(s), lien_s
                ))
            print('</div>')

# Afficher selection
print("<h2 style='margin-top:20px;'>Selection</h2>")
if not selection_ids:
    print('<div class="message">Selection vide (tu peux aussi utiliser Famille/Type).</div>')
else:
    print('<div class="zone-resultats">')
    # Charger noms via requete simple
    cur = connexion.cursor()
    for oid in selection_ids:
        nom_obj = ""
        try:
            cur.execute(
                "SELECT [{nomc}] FROM stat_objects WHERE [{idc}] = ?".format(
                    nomc=colonnes["nom"], idc=colonnes["id"]
                ),
                (oid,)
            )
            lig = cur.fetchone()
            if lig and lig[0] is not None:
                nom_obj = str(lig[0])
        except Exception:
            nom_obj = ""

        lien_retire = (
            "/cgi-bin/sim.py?uid={uid}"
            "&action=retirer_selection"
            "&objet_retire_id={oid}"
            "&recherche_objet={rech}"
            "&selection_ids={sel}"
            "&planning={planning}"
            "&famille={fam}"
            "&type={typ}"
            "&nb_annees={na}"
            "&annee_depart={ad}"
        ).format(
            uid=uid_encode,
            oid=int(oid),
            rech=urllib.parse.quote(recherche_objet),
            sel=urllib.parse.quote(selection_ids_texte),
            planning=urllib.parse.quote(planning_texte),
            fam=urllib.parse.quote(famille_choisie),
            typ=urllib.parse.quote(type_choisi),
            na=urllib.parse.quote(nb_annees_str),
            ad=urllib.parse.quote(annee_depart_str)
        )

        print("""
        <div class="ligne-resultat">
          <div><strong>{nom}</strong> <span class="petit">(# {oid})</span></div>
          <a class="bouton bouton-secondaire" href="{lien}">Retirer</a>
        </div>
        """.format(nom=echapper_html(nom_obj), oid=echapper_html(oid), lien=lien_retire))
    print("</div>")

# Famille / Type (fallback si pas selection)
print("""
  <form method="get" action="/cgi-bin/sim.py" style="margin-top:16px;">
    <input type="hidden" name="uid" value="{uid}">
    <input type="hidden" name="selection_ids" value="{sel}">
    <input type="hidden" name="planning" value="{planning}">
    <label class="label">Famille (si selection vide)</label>
    <select class="champ-select" name="famille">
      <option value="">(aucune)</option>
""".format(uid=uid_encode, sel=echapper_html(selection_ids_texte), planning=echapper_html(planning_texte)))

for f in familles:
    sel = 'selected' if famille_choisie == str(f) else ''
    print('<option value="{v}" {s}>{v}</option>'.format(v=echapper_html(f), s=sel))

print("""
    </select>

    <label class="label">Type (si selection vide)</label>
    <select class="champ-select" name="type">
      <option value="">(aucun)</option>
""")

for t in types:
    sel = 'selected' if type_choisi == str(t) else ''
    print('<option value="{v}" {s}>{v}</option>'.format(v=echapper_html(t), s=sel))

print("""
    </select>

    <div class="ligne-actions">
      <button class="bouton bouton-secondaire" type="submit">Appliquer</button>
    </div>
  </form>

</div> <!-- fin carte gauche -->


<div class="carte">
  <h2>2) Planning + Simulation</h2>

  <div class="message">
    Tu ajoutes des evenements a une annee d arrivee (0 = maintenant).
    Chaque evenement applique un coef sur prix et/ou CA, en respectant les impacts + liaisons.
  </div>

  <form method="get" action="/cgi-bin/sim.py">
    <input type="hidden" name="uid" value="{uid}">
    <input type="hidden" name="selection_ids" value="{sel}">
    <input type="hidden" name="recherche_objet" value="{rech}">
    <input type="hidden" name="famille" value="{fam}">
    <input type="hidden" name="type" value="{typ}">
    <input type="hidden" name="planning" value="{planning}">

    <label class="label">Annee depart</label>
    <input class="champ-texte" type="text" name="annee_depart" value="{ad}">

    <label class="label">Nombre d annees</label>
    <input class="champ-texte" type="text" name="nb_annees" value="{na}">
""".format(
    uid=uid_encode,
    sel=echapper_html(selection_ids_texte),
    rech=echapper_html(recherche_objet),
    fam=echapper_html(famille_choisie),
    typ=echapper_html(type_choisi),
    planning=echapper_html(planning_texte),
    ad=echapper_html(annee_depart_str),
    na=echapper_html(nb_annees_str)
))

# Ajouter un evenement au planning
print("""
    <details style="margin-top:12px; padding:10px 12px; border-radius:14px; background: rgba(0,0,0,0.18); border: 1px solid rgba(255,255,255,0.10);">
      <summary style="cursor:pointer;">Ajouter un evenement</summary>

      <input type="hidden" name="action" value="ajouter_planning">

      <label class="label">Evenement</label>
      <select class="champ-select" name="evenement_ajout_id">
        <option value="">(choisir)</option>
""")

for eid, nom_evt in liste_evenements:
    print('<option value="{id}">{nom} (# {id})</option>'.format(
        id=int(eid), nom=echapper_html(nom_evt)
    ))

print("""
      </select>

      <label class="label">Arrivee (annee relative)</label>
      <input class="champ-texte" type="text" name="evenement_ajout_annee" value="0">

      <label class="label">Coef prix (ex: 0.90 / 1.10)</label>
      <input class="champ-texte" type="text" name="evenement_ajout_coef_prix" value="1.0">

      <label class="label">Coef CA (ex: 0.95 / 1.05)</label>
      <input class="champ-texte" type="text" name="evenement_ajout_coef_ca" value="1.0">

      <div class="ligne-actions">
        <button class="bouton" type="submit">Ajouter au planning</button>
      </div>
    </details>
  </form>
""")

# Afficher planning
print("<h2 style='margin-top:18px;'>Planning</h2>")
if not planning:
    print('<div class="message">Aucun evenement planifie.</div>')
else:
    print('<table class="table">')
    print('<tr><th>#</th><th>Evenement</th><th>Annee</th><th>Coef prix</th><th>Coef CA</th><th></th></tr>')
    # Build map id->nom
    map_evt = {}
    for eid, nom_evt in liste_evenements:
        map_evt[int(eid)] = str(nom_evt)

    for i, (ar, eid, cp, cc) in enumerate(planning):
        nom_evt = map_evt.get(int(eid), "Evenement")
        lien_suppr = (
            "/cgi-bin/sim.py?uid={uid}"
            "&action=supprimer_planning"
            "&planning_idx={idx}"
            "&selection_ids={sel}"
            "&planning={planning}"
            "&recherche_objet={rech}"
            "&famille={fam}"
            "&type={typ}"
            "&nb_annees={na}"
            "&annee_depart={ad}"
        ).format(
            uid=uid_encode,
            idx=i,
            sel=urllib.parse.quote(selection_ids_texte),
            planning=urllib.parse.quote(planning_texte),
            rech=urllib.parse.quote(recherche_objet),
            fam=urllib.parse.quote(famille_choisie),
            typ=urllib.parse.quote(type_choisi),
            na=urllib.parse.quote(nb_annees_str),
            ad=urllib.parse.quote(annee_depart_str)
        )
        print("""
        <tr>
          <td>{i}</td>
          <td>{nom} <span class="petit">(# {eid})</span></td>
          <td>{ar}</td>
          <td>{cp}</td>
          <td>{cc}</td>
          <td><a class="lien-supprimer" href="{lien}">Supprimer</a></td>
        </tr>
        """.format(
            i=echapper_html(i),
            nom=echapper_html(nom_evt),
            eid=echapper_html(eid),
            ar=echapper_html(ar),
            cp=echapper_html(cp),
            cc=echapper_html(cc),
            lien=lien_suppr
        ))
    print("</table>")

    lien_vider = (
        "/cgi-bin/sim.py?uid={uid}"
        "&action=vider_planning"
        "&selection_ids={sel}"
        "&planning={planning}"
        "&recherche_objet={rech}"
        "&famille={fam}"
        "&type={typ}"
        "&nb_annees={na}"
        "&annee_depart={ad}"
    ).format(
        uid=uid_encode,
        sel=urllib.parse.quote(selection_ids_texte),
        planning=urllib.parse.quote(planning_texte),
        rech=urllib.parse.quote(recherche_objet),
        fam=urllib.parse.quote(famille_choisie),
        typ=urllib.parse.quote(type_choisi),
        na=urllib.parse.quote(nb_annees_str),
        ad=urllib.parse.quote(annee_depart_str)
    )
    print('<div class="ligne-actions"><a class="bouton bouton-secondaire" href="{l}">Vider</a></div>'.format(l=lien_vider))

# Bouton simuler
lien_simuler = (
    "/cgi-bin/sim.py?uid={uid}"
    "&action=simuler"
    "&selection_ids={sel}"
    "&planning={planning}"
    "&recherche_objet={rech}"
    "&famille={fam}"
    "&type={typ}"
    "&nb_annees={na}"
    "&annee_depart={ad}"
).format(
    uid=uid_encode,
    sel=urllib.parse.quote(selection_ids_texte),
    planning=urllib.parse.quote(planning_texte),
    rech=urllib.parse.quote(recherche_objet),
    fam=urllib.parse.quote(famille_choisie),
    typ=urllib.parse.quote(type_choisi),
    na=urllib.parse.quote(nb_annees_str),
    ad=urllib.parse.quote(annee_depart_str)
)
print('<div class="ligne-actions" style="margin-top:16px;"><a class="bouton" href="{l}">Lancer simulation</a></div>'.format(l=lien_simuler))

# Affichage resultat (SVG + tableau)
if resultat_simulation:
    print('<h2 style="margin-top:20px;">Resultat</h2>')
    print('<div class="message">Courbe globale (prix moyen total, et CA total si disponible).</div>')
    if svg:
        print('<div style="margin-top:10px; border-radius:18px; overflow:hidden; border:1px solid rgba(255,255,255,0.10);">{}</div>'.format(svg))

    # Tableau global
    annees = resultat_simulation.get("annees", [])
    prix_total = resultat_simulation.get("prix_moyen_total", [])
    ca_total = resultat_simulation.get("ca_total", [])

    print('<details style="margin-top:12px; padding:10px 12px; border-radius:14px; background: rgba(0,0,0,0.18); border: 1px solid rgba(255,255,255,0.10);" open>')
    print('<summary style="cursor:pointer;">Tableau global (par annee)</summary>')
    print('<table class="table">')
    print('<tr><th>Annee</th><th>Prix moyen total</th><th>CA total</th></tr>')
    for i in range(0, len(annees)):
        print('<tr><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
            echapper_html(annees[i]),
            echapper_html(prix_total[i] if i < len(prix_total) else ""),
            echapper_html(ca_total[i] if i < len(ca_total) else "")
        ))
    print('</table>')
    print('</details>')

print("""
</div> <!-- fin carte droite -->
</div> <!-- fin grille -->
</div> <!-- fin panel -->
</body>
</html>
""")

connexion.close()
