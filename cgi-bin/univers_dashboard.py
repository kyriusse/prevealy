#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import sqlite3
import urllib.parse
import html

# ---------------------------------
# CGI: en-tete HTTP obligatoire
# ---------------------------------
print("Content-Type: text/html; charset=utf-8\n")

# Dossier ou sont stockes les univers (BDD par univers)
UNIVERSE_DIR = "cgi-bin/universes/"


# ---------------------------------
# Utils (securite HTML + params)
# ---------------------------------
def esc(s):
    """Echappe le texte pour eviter d'injecter du HTML."""
    return html.escape("" if s is None else str(s))

def get_param(name, default=""):
    """Recupere un parametre GET (?uid=...)."""
    qs = os.environ.get("QUERY_STRING", "")
    params = urllib.parse.parse_qs(qs, keep_blank_values=True)
    return params.get(name, [default])[0]


# ---------------------------------
# Acces aux fichiers univers
# ---------------------------------
def universe_path(universe_id):
    """
    Construit un chemin safe vers universe_<uid>.db
    On garde uniquement lettres/chiffres/_/-
    """
    safe = "".join([c for c in universe_id if c.isalnum() or c in ("-", "_")])
    return os.path.join(UNIVERSE_DIR, "universe_%s.db" % safe)

def get_universe_name(universe_id):
    """Lit univers_names.txt pour afficher un nom humain."""
    try:
        names_file = os.path.join(UNIVERSE_DIR, "univers_names.txt")
        if os.path.exists(names_file):
            with open(names_file, "r", encoding="utf-8") as f:
                for line in f:
                    if "," in line:
                        uid, name = line.strip().split(",", 1)
                        if uid == universe_id:
                            return name
    except Exception:
        pass
    return "Nom inconnu"


# ---------------------------------
# Verif BDD (stat_objects)
# ---------------------------------
def check_stat_objects_table(universe_id):
    """
    Verifie:
      - le fichier db existe
      - la table stat_objects existe
      - donne le count + les colonnes
    """
    upath = universe_path(universe_id)

    if not os.path.exists(upath):
        return False, "Le fichier de l'univers n'existe pas : %s" % upath

    try:
        conn = sqlite3.connect(upath)
        cur = conn.cursor()

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stat_objects'")
        if not cur.fetchone():
            conn.close()
            return False, "La table 'stat_objects' n'existe pas dans cet univers."

        cur.execute("SELECT COUNT(*) FROM stat_objects")
        count = cur.fetchone()[0]

        cur.execute("PRAGMA table_info(stat_objects)")
        columns = [col[1] for col in cur.fetchall()]

        conn.close()
        return True, "Table OK : %d objets, colonnes : %s" % (count, ", ".join(columns))

    except Exception as e:
        return False, "Erreur lors de la verification : %s" % str(e)


# ---------------------------------
# MAIN
# ---------------------------------
uid = get_param("uid", "").strip()

# Si pas d'uid -> page erreur
if not uid:
    print("""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Erreur</title>
<style>
body{ margin:0; font-family:Arial,sans-serif; background:#0b0b10; color:#fff; padding:24px; }
a{ color:#FFD86A; font-weight:bold; text-decoration:none; }
</style>
</head>
<body>
<h1>Erreur : Aucun univers specifie</h1>
<a href="create_stat_object.py">Retour</a>
</body>
</html>
""")
    raise SystemExit

universe_name = get_universe_name(uid)
table_ok, table_msg = check_stat_objects_table(uid)

# ---------------------------------
# HTML + CSS (design)
# ---------------------------------
print(f"""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Menu de l'univers - {esc(universe_name)}</title>

<style>
/* -------------------------------------------------
   THEME
   ------------------------------------------------- */
:root{{
  --txt:#ffffff;
  --muted:rgba(255,255,255,0.74);
  --gold:#FFD86A;

  --shadow: rgba(0,0,0,0.72);

  --btnA: #4a2a50;
  --btnB: #5e3466;

  --okBg: rgba(42, 138, 42, 0.34);
  --okBd: rgba(100, 255, 100, 0.45);

  --errBg: rgba(138, 42, 42, 0.34);
  --errBd: rgba(255, 100, 100, 0.45);

  /* Position approx de la planete (ajuste si besoin) */
  --planetX: 50%;
  --planetY: 52%;
}}

*{{ box-sizing:border-box; }}
html, body{{ height:100%; }}

/* -------------------------------------------------
   FOND ( image légérement changée )
   ------------------------------------------------- */
body {{
  margin: 0;
  font-family: Arial, sans-serif;
  color: var(--txt);
  min-height: 100vh;
  overflow:hidden;

  background-image: url('/fond_galactique_objet_2.png');
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  position: relative;
}}

/* Vignette: sombre sur les bords, plus clair au centre (planete) */
body::before{{
  content:"";
  position: fixed;
  inset:0;
  pointer-events:none;
  z-index: 0;
  background:
    radial-gradient(circle at var(--planetX) var(--planetY),
      rgba(0,0,0,0.00),
      rgba(0,0,0,0.82) 78%),
    linear-gradient(180deg, rgba(0,0,0,0.10), rgba(0,0,0,0.42));
}}

/* ---------------------Etoiles discretes ----------------------*/
.stars{{
  position: fixed;
  inset: 0;
  pointer-events:none;
  z-index: 0;
  opacity: 0.22;
  background-image:
    radial-gradient(1px 1px at 12% 18%, rgba(255,255,255,0.85), transparent 60%),
    radial-gradient(1px 1px at 28% 62%, rgba(255,255,255,0.65), transparent 60%),
    radial-gradient(1px 1px at 44% 28%, rgba(255,255,255,0.75), transparent 60%),
    radial-gradient(1px 1px at 74% 64%, rgba(255,255,255,0.65), transparent 60%),
    radial-gradient(1px 1px at 92% 84%, rgba(255,255,255,0.65), transparent 60%);
  animation: twinkle 4.6s ease-in-out infinite;
}}
@keyframes twinkle{{
  0%{{ opacity: 0.18; transform: translateY(0px); }}
  50%{{ opacity: 0.30; transform: translateY(-2px); }}
  100%{{ opacity: 0.18; transform: translateY(0px); }}
}}

/* -------------------------------------------------
   DINGUERIES :
   - glow pulse sur la planete
   - anneaux HUD qui tournent
   - scan beam
   ------------------------------------------------- */
.fx {{
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 1;
}}

/* Glow: rend la planete plus "mise en valeur" */
.fx-glow{{
  background:
    radial-gradient(circle at var(--planetX) var(--planetY),
      rgba(255,216,106,0.30),
      rgba(255,216,106,0.10) 32%,
      transparent 58%);
  mix-blend-mode: screen;
  animation: glowPulse 3.6s ease-in-out infinite;
  opacity: 0.70;
}}
@keyframes glowPulse{{
  0%{{ transform: scale(1.00); opacity: 0.55; }}
  50%{{ transform: scale(1.02); opacity: 0.85; }}
  100%{{ transform: scale(1.00); opacity: 0.55; }}
}}

/* Anneaux: effet "interface sci-fi" */
.fx-rings{{
  opacity: 0.55;
  mix-blend-mode: screen;
}}
.fx-rings::before,
.fx-rings::after{{
  content:"";
  position: absolute;
  left: var(--planetX);
  top: var(--planetY);
  transform: translate(-50%, -50%);
  border-radius: 999px;
  border: 1px solid rgba(255,216,106,0.18);
  box-shadow: 0 0 40px rgba(255,216,106,0.10);
}}
.fx-rings::before{{
  width: 820px;
  height: 820px;
  border-color: rgba(255,216,106,0.14);
  animation: ringSpinA 18s linear infinite;
}}
.fx-rings::after{{
  width: 640px;
  height: 640px;
  border-color: rgba(255,216,106,0.18);
  animation: ringSpinB 28s linear infinite reverse;
}}
@keyframes ringSpinA{{
  from{{ transform: translate(-50%, -50%) rotate(0deg); }}
  to  {{ transform: translate(-50%, -50%) rotate(360deg); }}
}}
@keyframes ringSpinB{{
  from{{ transform: translate(-50%, -50%) rotate(0deg); }}
  to  {{ transform: translate(-50%, -50%) rotate(360deg); }}
}}

/* Scan: fais un balayage autour de la planete */
.fx-scan{{
  opacity: 0.60;
  mix-blend-mode: screen;
}}
.fx-scan::before{{
  content:"";
  position:absolute;
  left: var(--planetX);
  top: var(--planetY);
  width: 980px;
  height: 980px;
  transform: translate(-50%, -50%);
  border-radius: 999px;
  background:
    conic-gradient(from 0deg,
      transparent 0deg,
      rgba(255,216,106,0.00) 20deg,
      rgba(255,216,106,0.18) 28deg,
      rgba(255,216,106,0.00) 36deg,
      transparent 60deg);
  animation: sweep 4.2s linear infinite;
}}
@keyframes sweep{{
  from{{ transform: translate(-50%, -50%) rotate(0deg); }}
  to  {{ transform: translate(-50%, -50%) rotate(360deg); }}
}}

/* -------------------------------------------------
   BOUTON RETOUR
   ------------------------------------------------- */
.back-btn {{
  position: fixed;
  top: 18px;
  left: 18px;
  width: 64px;
  height: 64px;
  
  display: block;              /* important */
  z-index: 999999;             /* au-dessus de tout */
  pointer-events: auto;        /* re-autorise le clic */

  background-image: url('/back_btn_jaune.png');
  background-size: contain;
  background-repeat: no-repeat;
  background-position: center;

  cursor: pointer;
  transition: transform 0.18s ease, opacity 0.18s ease;
  opacity: 0.92;
}}
.back-btn:hover {{
  transform: scale(1.08);
  opacity: 1;
}}

/* -------------------------------------------------
   PANEL CENTRAL (glass + shine)
   ------------------------------------------------- */
.wrap{{
  position: relative;
  z-index: 3;
  height: 100vh;
  display:flex;
  align-items:center;
  justify-content:center;
  padding: 24px;
}}

.panel {{
  width: min(920px, 94vw);
  padding: 34px 34px;
  border-radius: 32px;

  background:
    radial-gradient(circle at 30% 20%, rgba(255,216,106,0.12), transparent 44%),
    radial-gradient(circle at 70% 80%, rgba(190,120,255,0.08), transparent 52%),
    linear-gradient(180deg, rgba(15,15,20,0.70), rgba(7,7,10,0.88));

  border: 1px solid rgba(255,216,106,0.22);
  box-shadow: 0 40px 140px var(--shadow);

  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);

  position: relative;
  overflow: hidden;
}}

/* Reflet qui passe sur le panel */
.panel::before{{
  content:"";
  position:absolute;
  top:-50%;
  left:-40%;
  width: 60%;
  height: 220%;
  background: linear-gradient(90deg, transparent, rgba(255,216,106,0.14), transparent);
  transform: rotate(22deg);
  animation: shine 5.8s ease-in-out infinite;
  pointer-events:none;
}}
@keyframes shine{{
  0%{{ transform: translateX(-45%) rotate(22deg); opacity: 0.0; }}
  18%{{ opacity: 0.65; }}
  50%{{ opacity: 0.18; }}
  100%{{ transform: translateX(260%) rotate(22deg); opacity: 0.0; }}
}}

h1 {{
  text-align: center;
  margin: 0;
  color: var(--gold);
  letter-spacing: 2px;
}}

.universe-info {{
  margin-top: 12px;
  text-align: center;
  color: var(--muted);
  letter-spacing: 2px;
  text-transform: uppercase;
  font-size: 12px;
  line-height: 1.6;
}}

.hr{{
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255,216,106,0.28), rgba(255,255,255,0.10), rgba(255,216,106,0.28), transparent);
  margin: 18px 0;
}}

.info-box {{
  background: rgba(0, 0, 0, 0.28);
  padding: 14px 14px;
  border-radius: 14px;
  margin: 18px 0 22px;
  border: 1px solid rgba(255, 216, 106, 0.26);
  color: rgba(255,255,255,0.92);
  line-height: 1.6;
  word-break: break-word;
}}

.error {{
  background: var(--errBg);
  border-color: var(--errBd);
}}

.success {{
  background: var(--okBg);
  border-color: var(--okBd);
}}

/* ======= Boutons (nouveau style) ======= */
.btn{{
  width: 100%;
  padding: 18px 20px;
  border-radius: 16px;
  margin-top: 16px;   /* espace au-dessus */

  font-size: 15px;
  font-weight: 800;
  letter-spacing: 2px;
  text-transform: uppercase;

  cursor: pointer;
  position: relative;
  overflow: hidden;

  border: none;
  transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}}

/* Creation d'objet = bouton principal (or) */
.btn-create{{
  color: #1a1206;
  background: linear-gradient(135deg, #FFD86A, #ffefb0);
  box-shadow: 0 0 0 rgba(255,216,106,0.0);
}}
.btn-create::after{{
  content:"";
  position:absolute;
  inset:-40%;
  background: radial-gradient(circle, rgba(255,255,255,0.45), transparent 60%);
  opacity: 0;
  transition: opacity 0.25s ease;
}}
.btn-create:hover{{
  transform: scale(1.03);
  box-shadow: 0 0 60px rgba(255,216,106,0.45), 0 0 120px rgba(255,216,106,0.18);
  background: linear-gradient(135deg, #FFD86A, #ffefb0);
}}
.btn-create:hover::after{{
  opacity: 1;
}}

/* Simulation = bouton secondaire (violet) */
.btn-sim{{
  color: #ffffff;
  background: linear-gradient(135deg, #4a2a50, #6a3b73);
  border: 1px solid rgba(255,255,255,0.22);
}}
.btn-sim:hover{{
  transform: scale(1.02);
  box-shadow: 0 0 40px rgba(190,120,255,0.35);
}}


button:hover {{
  background: var(--btnB);
  transform: scale(1.02);
  box-shadow: 0 0 50px rgba(255,216,106,0.16);
}}

@media (max-width: 520px){{
  .panel{{ padding: 24px 18px; border-radius: 24px; }}
  h1{{ font-size: 20px; }}
  .back-btn{{ width: 56px; height: 56px; }}
  .fx-rings::before{{ width: 620px; height: 620px; }}
  .fx-rings::after{{ width: 500px; height: 500px; }}
  .fx-scan::before{{ width: 760px; height: 760px; }}
}}
</style>
</head>

<body>
<div class="stars"></div>

<!-- Couches effets (planete) -->
<div class="fx fx-glow"></div>
<div class="fx fx-rings"></div>
<div class="fx fx-scan"></div>

<!-- Bouton retour: lien relatif (corrige) -->
<a href="create_stat_object.py" class="back-btn" title="Retour"></a>

<div class="wrap">
  <div class="panel">

    <h1>Menu de l'univers</h1>

    <div class="universe-info">
      <strong>{esc(universe_name)}</strong><br>
      <small>ID: {esc(uid)}</small>
    </div>

    <div class="hr"></div>

    <div class="info-box {"success" if table_ok else "error"}">
      {esc(table_msg)}
    </div>

    <form method="get" action="personnalisation_objet.py">
      <input type="hidden" name="uid" value="{esc(uid)}">
      <button type="submit" class="btn btn-create">Creation d'objet</button>
    </form>

    <form method="get" action="menu_simulation.py">
      <input type="hidden" name="uid" value="{esc(uid)}">
      <button type="submit" class="btn btn-sim">Simulation (beta)</button>
    </form>

  </div>
</div>

</body>
</html>
""")
