#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
sim_calc.py
-----------
Simulation deterministe (base) dans un univers.

Principe:
- On utilise les donnees "objets" (prix, quantite, coefficient...) de la BDD univers.
- On peut activer 0..n evenements.
- Chaque evenement fournit une liste d'impacts (impacts_evenements):
  objet_id -> poids_final (deja calcule par liaison.py)
- Effet deterministe simple:
  valeur_effective_objet = valeur_base_objet * (1 + somme_poids_final_evenements_actifs_sur_objet)

Sorties:
- Total moyen, min, max (si on a des colonnes de type min/max, sinon on duplique le moyen)
- Projection a N annees avec un taux annuel fixe (optionnel)

Contraintes:
- Sans JavaScript
- Variables en francais
- Commentaires partout (sauf evidences)
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

    if colonne_id is None and infos:
        colonne_id = infos[0][1]
    if colonne_nom is None and len(infos) >= 2:
        colonne_nom = infos[1][1]

    return colonne_id, colonne_nom


# ============================================================
# Utils: inspecter tables/colonnes
# ============================================================
def table_existe(connexion, nom_table):
    """Retourne True si une table existe dans la BDD."""
    cur = connexion.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (nom_table,))
    return cur.fetchone() is not None


def colonnes_table(connexion, nom_table):
    """Retourne la liste des colonnes d une table."""
    cur = connexion.cursor()
    cur.execute(f"PRAGMA table_info({nom_table})")
    return [r[1] for r in cur.fetchall()]


# ============================================================
# Lecture evenements / impacts
# ============================================================
def lister_evenements(connexion, limite=200):
    """Liste les evenements."""
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


def lire_impacts_evenements_actifs(connexion, liste_evenements_actifs):
    """
    Retourne un dictionnaire:
      objet_id -> somme_poids_final
    en sommant les poids_final de impacts_evenements pour les evenements actifs.
    """
    if not liste_evenements_actifs:
        return {}

    cur = connexion.cursor()

    # Construction d une clause IN sure (placeholders)
    placeholders = ",".join(["?"] * len(liste_evenements_actifs))

    cur.execute(
        f"""
        SELECT objet_id, SUM(poids_final)
        FROM impacts_evenements
        WHERE evenement_id IN ({placeholders})
        GROUP BY objet_id
        """,
        tuple(liste_evenements_actifs)
    )

    resultat = {}
    for (oid, somme_poids) in cur.fetchall():
        resultat[int(oid)] = float(somme_poids) if somme_poids is not None else 0.0

    return resultat


# ============================================================
# Lecture "valeur base" d un objet
# ============================================================
def lire_valeurs_base_objet(connexion, colonne_id, objet_id):
    """
    Retourne (moyen, mini, maxi).

    Cette fonction essaie d etre robuste:
    - si tu as une table de prix type Prix_Objets dans l univers, adapte ici.
    - sinon fallback: valeur=1.0

    IMPORTANT:
    - On essaye d utiliser:
      * prix_moyen (ou prix) 
      * prix_min / prix_max
      * quantite
      * coefficient

    Si une colonne manque, on prend une valeur par defaut.
    """
    # Valeurs par defaut
    prix_moyen = 1.0
    prix_min = None
    prix_max = None
    quantite = 1.0
    coefficient = 1.0

    # Cas 1: si une table "stat_objects" porte deja ces infos (selon ton schema)
    # On detecte quelques noms possibles de colonnes.
    colonnes = colonnes_table(connexion, "stat_objects")

    # Petites fonctions internes (evite repetition)
    def lire_colonne_si_existe(nom_colonne):
        return nom_colonne if nom_colonne in colonnes else None

    # Noms possibles
    col_prix = lire_colonne_si_existe("prix") or lire_colonne_si_existe("Prix") or lire_colonne_si_existe("prix_moyen") or lire_colonne_si_existe("Prix_moyen")
    col_prix_min = lire_colonne_si_existe("prix_min") or lire_colonne_si_existe("Prix_min")
    col_prix_max = lire_colonne_si_existe("prix_max") or lire_colonne_si_existe("Prix_max")
    col_quantite = lire_colonne_si_existe("quantite") or lire_colonne_si_existe("Quantite")
    col_coef = lire_colonne_si_existe("coefficient") or lire_colonne_si_existe("Coefficient") or lire_colonne_si_existe("coef") or lire_colonne_si_existe("Coef")

    # Si au moins un champ semble exister, on lit la ligne
    if col_prix or col_quantite or col_coef or col_prix_min or col_prix_max:
        cur = connexion.cursor()
        cur.execute(f"SELECT * FROM stat_objects WHERE [{colonne_id}] = ?", (objet_id,))
        row = cur.fetchone()
        if row:
            # Recuperation via mapping index
            # On construit un dict colonne->valeur
            cur.execute("SELECT * FROM stat_objects LIMIT 1")
            # Trick: utiliser cursor.description pour nommer les colonnes
            cur.execute(f"SELECT * FROM stat_objects WHERE [{colonne_id}] = ? LIMIT 1", (objet_id,))
            desc = [d[0] for d in cur.description]
            ligne = cur.fetchone()
            if ligne:
                d = {}
                for i in range(len(desc)):
                    d[desc[i]] = ligne[i]

                def to_float(v, defaut):
                    try:
                        if v is None:
                            return defaut
                        return float(str(v).replace(",", "."))
                    except Exception:
                        return defaut

                if col_prix and col_prix in d:
                    prix_moyen = to_float(d.get(col_prix), 1.0)
                if col_prix_min and col_prix_min in d:
                    prix_min = to_float(d.get(col_prix_min), None)
                if col_prix_max and col_prix_max in d:
                    prix_max = to_float(d.get(col_prix_max), None)
                if col_quantite and col_quantite in d:
                    quantite = to_float(d.get(col_quantite), 1.0)
                if col_coef and col_coef in d:
                    coefficient = to_float(d.get(col_coef), 1.0)

    # Calcul valeur base
    valeur_moy = prix_moyen * quantite * coefficient

    # Si min/max absents, on les derive du moyen
    if prix_min is None:
        valeur_min = valeur_moy
    else:
        valeur_min = prix_min * quantite * coefficient

    if prix_max is None:
        valeur_max = valeur_moy
    else:
        valeur_max = prix_max * quantite * coefficient

    return valeur_moy, valeur_min, valeur_max


# ============================================================
# Simulation deterministe
# ============================================================
def simuler(connexion, colonne_id, liste_objets_ids, impacts_objets, taux_annuel, nb_annees):
    """
    Calcule:
    - total_moyen, total_min, total_max
    - projection a N annees sur le total_moyen (taux simple)
    """
    total_moyen = 0.0
    total_min = 0.0
    total_max = 0.0

    details = []  # liste lignes pour affichage (objet_id, base, facteur_evt, final)

    for oid in liste_objets_ids:
        base_moy, base_min, base_max = lire_valeurs_base_objet(connexion, colonne_id, oid)

        somme_evt = impacts_objets.get(oid, 0.0)
        facteur_evt = 1.0 + somme_evt

        val_moy = base_moy * facteur_evt
        val_min = base_min * facteur_evt
        val_max = base_max * facteur_evt

        total_moyen += val_moy
        total_min += val_min
        total_max += val_max

        details.append((oid, base_moy, somme_evt, val_moy))

    # Projection (deterministe simple)
    if nb_annees < 0:
        nb_annees = 0

    try:
        taux = float(taux_annuel)
    except Exception:
        taux = 0.0

    total_proj = total_moyen * ((1.0 + taux) ** nb_annees)

    return total_moyen, total_min, total_max, total_proj, details


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

# Verifications minimales
if not table_existe(connexion, "stat_objects"):
    print("<h1>Erreur : table stat_objects introuvable</h1>")
    connexion.close()
    raise SystemExit

colonne_id, colonne_nom = detecter_colonnes_stat_objects(connexion)
if not colonne_id or not colonne_nom:
    print("<h1>Erreur : stat_objects invalide</h1>")
    connexion.close()
    raise SystemExit


# ============================================================
# Parametres UI (sans JS)
# ============================================================
# Evenements actifs: "evt=1&evt=2..."
evenements_actifs = []
for key, vals in urllib.parse.parse_qs(os.environ.get("QUERY_STRING", ""), keep_blank_values=True).items():
    if key == "evt":
        for v in vals:
            if str(v).isdigit():
                evenements_actifs.append(int(v))

# Horizon / taux
nb_annees_str = lire_parametre_get("nb_annees", "5").strip()
taux_str = lire_parametre_get("taux_annuel", "0.00").strip()

try:
    nb_annees = int(nb_annees_str)
except Exception:
    nb_annees = 5

try:
    taux_annuel = float(taux_str.replace(",", "."))
except Exception:
    taux_annuel = 0.0

action = lire_parametre_get("action", "").strip()

message_ok = ""
message_erreur = ""

# Liste evenements pour UI
liste_evenements = []
if table_existe(connexion, "evenements"):
    try:
        liste_evenements = lister_evenements(connexion, limite=200)
    except Exception:
        liste_evenements = []

# Impacts agreges
impacts_objets = {}
if evenements_actifs and table_existe(connexion, "impacts_evenements"):
    try:
        impacts_objets = lire_impacts_evenements_actifs(connexion, evenements_actifs)
    except Exception:
        impacts_objets = {}

# Liste des objets simules: pour une V1 simple, on prend tous les objets de stat_objects
cur = connexion.cursor()
cur.execute(f"SELECT [{colonne_id}] FROM stat_objects")
liste_objets_ids = [int(r[0]) for r in cur.fetchall() if r and r[0] is not None]

# Resultats simulation
resultats = None

if action == "calculer":
    try:
        total_moy, total_min, total_max, total_proj, details = simuler(
            connexion,
            colonne_id,
            liste_objets_ids,
            impacts_objets,
            taux_annuel,
            nb_annees
        )
        resultats = (total_moy, total_min, total_max, total_proj, details)
        message_ok = "Simulation calculee sur " + str(len(liste_objets_ids)) + " objet(s)."
    except Exception as e:
        message_erreur = "Erreur simulation : " + str(e)


# ============================================================
# HTML / CSS (mystique privealy)
# ============================================================
print(f"""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Simulation Calcule - {echapper_html(nom_univers)}</title>

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
  grid-template-columns: 0.9fr 1.1fr;
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
.champ-texte {{
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
.petit {{
  font-size: 12px;
  opacity: 0.82;
}}
</style>
</head>

<body>
<a class="bouton-retour" href="/cgi-bin/menu_simulation.py?uid={uid_encode}" title="Retour"></a>

<div class="panel">
  <h1>Simulation Calcule</h1>
  <div class="ligne-univers">
    Univers : <strong>{echapper_html(nom_univers)}</strong> &nbsp;|&nbsp; ID : {echapper_html(uid)}
  </div>
""")

if message_ok:
    print(f'<div class="message ok">{echapper_html(message_ok)}</div>')
if message_erreur:
    print(f'<div class="message bad">{echapper_html(message_erreur)}</div>')

print(f"""
  <div class="grille">
    <div class="carte">
      <h2>Parametres</h2>

      <form method="get" action="/cgi-bin/sim_calc.py">
        <input type="hidden" name="uid" value="{echapper_html(uid)}">

        <label class="label">Horizon (annees)</label>
        <input class="champ-texte" type="text" name="nb_annees" value="{echapper_html(nb_annees_str)}">

        <label class="label">Taux annuel (ex: 0.05 = 5%)</label>
        <input class="champ-texte" type="text" name="taux_annuel" value="{echapper_html(taux_str)}">

        <h2 style="margin-top:16px;">Evenements actifs</h2>
""")

# Liste checkbox evenements (sans JS)
if not liste_evenements:
    print('<div class="message">Aucun evenement (cree-les dans Liaison).</div>')
else:
    for (eid, nom_evt, pg, it, du, pr, tg, dc) in liste_evenements:
        coche = "checked" if eid in evenements_actifs else ""
        print(f"""
          <label class="petit" style="display:block; margin-top:8px;">
            <input type="checkbox" name="evt" value="{eid}" {coche}>
            {echapper_html(nom_evt)} <span class="petit">(# {eid})</span>
          </label>
        """)

print("""
        <div class="ligne-actions">
          <button class="bouton" type="submit" name="action" value="calculer">Calculer</button>
          <a class="bouton bouton-secondaire" href="#">(Beta)</a>
        </div>
      </form>
    </div>

    <div class="carte">
      <h2>Resultats</h2>
""")

if resultats is None:
    print('<div class="message">Lance "Calculer" pour obtenir un resultat.</div>')
else:
    total_moy, total_min, total_max, total_proj, details = resultats

    print(f"""
      <div class="message ok">
        <strong>Total moyen:</strong> {echapper_html(round(total_moy, 6))}<br>
        <strong>Total min:</strong> {echapper_html(round(total_min, 6))}<br>
        <strong>Total max:</strong> {echapper_html(round(total_max, 6))}<br>
        <strong>Projection a {echapper_html(nb_annees)} an(s):</strong> {echapper_html(round(total_proj, 6))}
      </div>
    """)

    # Tableau details (limite pour rester lisible)
    print('<div class="message" style="margin-top:12px;">Details (limite 80 lignes)</div>')
    print('<table class="table">')
    print('<tr><th>Objet</th><th>Base</th><th>Somme evt</th><th>Final</th></tr>')

    # On affiche les plus "forts" (final)
    details_trie = sorted(details, key=lambda x: -x[3])
    for (oid, base, somme_evt, final) in details_trie[:80]:
        # Nom objet
        cur = connexion.cursor()
        cur.execute(f"SELECT [{colonne_nom}] FROM stat_objects WHERE [{colonne_id}] = ?", (oid,))
        r = cur.fetchone()
        nom_obj = r[0] if r and r[0] is not None else ""
        print(f"""
          <tr>
            <td>{echapper_html(nom_obj)} <span class="petit">(# {echapper_html(oid)})</span></td>
            <td>{echapper_html(round(base, 6))}</td>
            <td>{echapper_html(round(somme_evt, 6))}</td>
            <td>{echapper_html(round(final, 6))}</td>
          </tr>
        """)

    print("</table>")

print("""
    </div>
  </div>
</div>
</body>
</html>
""")

connexion.close()
