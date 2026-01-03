#!/usr/bin/python3
# -*- coding: utf-8 -*-

print("Content-type: text/html; charset=utf-8\n")

print(r"""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Privealy</title>

<style>
:root{
  --txt: #ffffff;
  --muted: rgba(255,255,255,0.72);
  --muted2: rgba(255,255,255,0.55);

  --shadow: rgba(0,0,0,0.70);

  --gold: rgba(255, 232, 180, 0.90);
  --goldSoft: rgba(255, 232, 180, 0.18);

  --violet: rgba(190, 120, 255, 0.28);
  --cyan: rgba(140, 255, 235, 0.20);

  --line: rgba(255,255,255,0.18);
  --line2: rgba(255,255,255,0.10);
}

*{ box-sizing:border-box; }
html, body{ height:100%; }

body{
  margin:0;
  font-family: Arial, sans-serif;
  color: var(--txt);
  overflow:hidden;
  position: relative;

  background-image:
    radial-gradient(circle at 20% 20%, rgba(255,255,255,0.10), transparent 44%),
    radial-gradient(circle at 80% 30%, rgba(255,255,255,0.07), transparent 52%),
    radial-gradient(circle at 40% 85%, rgba(255,255,255,0.05), transparent 58%),
    radial-gradient(circle at 60% 55%, rgba(190,120,255,0.10), transparent 60%),
    radial-gradient(circle at 30% 60%, rgba(140,255,235,0.06), transparent 55%),
    linear-gradient(180deg, rgba(0,0,0,0.35), rgba(0,0,0,0.88)),
    url('/fond.png');
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;

  display:flex;
  justify-content:center;
  align-items:center;
}

/* VIGNETTE + BRUME */
body::before{
  content:"";
  position: fixed;
  inset:-30px;
  pointer-events:none;
  z-index: 0;
  background:
    radial-gradient(circle at 50% 45%, rgba(255,255,255,0.08), transparent 60%),
    radial-gradient(circle at 25% 75%, rgba(255,255,255,0.05), transparent 58%),
    radial-gradient(circle at 82% 70%, rgba(255,255,255,0.04), transparent 60%),
    radial-gradient(circle at 50% 55%, rgba(0,0,0,0.00), rgba(0,0,0,0.78) 74%);
}

/* ETOILES */
.stars{
  position: fixed;
  inset: 0;
  pointer-events:none;
  z-index: 0;
  opacity: 0.55;
  background-image:
    radial-gradient(1px 1px at 12% 18%, rgba(255,255,255,0.9), transparent 60%),
    radial-gradient(1px 1px at 28% 62%, rgba(255,255,255,0.7), transparent 60%),
    radial-gradient(1px 1px at 44% 28%, rgba(255,255,255,0.85), transparent 60%),
    radial-gradient(1px 1px at 58% 82%, rgba(255,255,255,0.6), transparent 60%),
    radial-gradient(1px 1px at 74% 64%, rgba(255,255,255,0.75), transparent 60%),
    radial-gradient(1px 1px at 86% 22%, rgba(255,255,255,0.8), transparent 60%),
    radial-gradient(1px 1px at 18% 48%, rgba(255,255,255,0.65), transparent 60%),
    radial-gradient(1px 1px at 92% 84%, rgba(255,255,255,0.75), transparent 60%);
  animation: twinkle 4.2s ease-in-out infinite;
}
@keyframes twinkle{
  0%{ opacity: 0.40; transform: translateY(0px); }
  50%{ opacity: 0.70; transform: translateY(-2px); }
  100%{ opacity: 0.40; transform: translateY(0px); }
}

/* FILIGRANE RITUEL */
.runes{
  position: fixed;
  inset: -50px;
  z-index: 0;
  pointer-events:none;
  opacity: 0.10;
  background:
    repeating-linear-gradient(
      112deg,
      rgba(255,255,255,0.0) 0px,
      rgba(255,255,255,0.0) 20px,
      rgba(255,255,255,0.18) 21px,
      rgba(255,255,255,0.0) 22px
    );
  mask-image: radial-gradient(circle at 50% 45%, rgba(0,0,0,1), rgba(0,0,0,0) 66%);
}

/* DUST */
.dust{
  position: fixed;
  inset: 0;
  pointer-events:none;
  z-index: 1;
  opacity: 0.16;
  background:
    radial-gradient(2px 2px at 18% 30%, rgba(255,232,180,0.9), transparent 60%),
    radial-gradient(2px 2px at 72% 38%, rgba(190,120,255,0.8), transparent 60%),
    radial-gradient(2px 2px at 42% 78%, rgba(255,255,255,0.8), transparent 60%),
    radial-gradient(2px 2px at 82% 70%, rgba(140,255,235,0.8), transparent 60%),
    radial-gradient(2px 2px at 30% 62%, rgba(255,255,255,0.7), transparent 60%);
  animation: dustFloat 6.2s ease-in-out infinite;
}
@keyframes dustFloat{
  0%{ transform: translateY(0px); opacity: 0.12; }
  50%{ transform: translateY(-7px); opacity: 0.20; }
  100%{ transform: translateY(0px); opacity: 0.12; }
}

/* ===== SANCTUAIRE ===== */
.sanctuary{
  position: relative;
  z-index: 2;
  width: min(980px, 94vw);
  padding: 26px 20px;
  text-align:center;
}

.brand{
  font-size: 56px;
  font-weight: 700;
  letter-spacing: 6px;
  text-transform: uppercase;
  margin: 0;
  text-shadow: 0 0 26px rgba(255,255,255,0.10);
}

.motto{
  margin-top: 14px;
  font-size: 13px;
  letter-spacing: 4px;
  text-transform: uppercase;
  color: rgba(255,255,255,0.78);
}

.whisper{
  margin: 22px auto 0;
  max-width: 740px;
  font-size: 15px;
  color: rgba(255,255,255,0.70);
  line-height: 1.75;
  letter-spacing: 0.4px;
}

.divider{
  margin: 30px auto 26px;
  width: min(680px, 90%);
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(255,232,180,0.28), rgba(255,255,255,0.14), rgba(255,232,180,0.28), transparent);
  position: relative;
}
.divider::after{
  content:"";
  position:absolute;
  left: 50%;
  top: -9px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  transform: translateX(-50%);
  background: radial-gradient(circle, rgba(255,232,180,0.65), rgba(255,232,180,0.0) 70%);
  box-shadow: 0 0 18px rgba(255,232,180,0.20);
}

/* ===== GRILLE DES PORTAILS ===== */
.portals{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 18px;
  width: min(980px, 94vw);
  margin: 0 auto;
}

.portal{
  position: relative;
  border-radius: 20px;
  padding: 22px 20px;
  text-align: left;

  background:
    radial-gradient(circle at 30% 20%, rgba(255,255,255,0.10), transparent 55%),
    linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.05));

  border: 1px solid rgba(255,255,255,0.14);
  box-shadow: 0 30px 90px rgba(0,0,0,0.55);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);

  overflow:hidden;
  transform: translateY(0px);
  transition: transform 0.18s ease, border-color 0.18s ease;
}

.portal:hover{
  transform: translateY(-4px);
  border-color: rgba(255,232,180,0.30);
}

.portal::before{
  content:"";
  position:absolute;
  inset:-60px;
  background:
    radial-gradient(circle at 30% 25%, rgba(255,232,180,0.14), transparent 50%),
    radial-gradient(circle at 70% 60%, rgba(190,120,255,0.10), transparent 55%);
  opacity: 0.9;
  pointer-events:none;
}

.portal-top{
  position: relative;
  display:flex;
  align-items:center;
  gap: 12px;
}

.portal-sigil{
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: 1px solid rgba(255,255,255,0.20);
  background:
    radial-gradient(circle at 35% 30%, rgba(255,232,180,0.30), rgba(255,232,180,0.05) 55%, transparent 70%),
    radial-gradient(circle at 65% 70%, rgba(140,255,235,0.10), transparent 60%);
  box-shadow: 0 0 22px rgba(255,232,180,0.10);
}

.portal-title{
  position: relative;
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 1px;
  margin: 0;
  text-transform: uppercase;
}

.portal-desc{
  position: relative;
  margin-top: 12px;
  color: rgba(255,255,255,0.72);
  font-size: 14px;
  line-height: 1.6;
  min-height: 60px;
}

.portal-action{
  position: relative;
  margin-top: 18px;
  display:flex;
  justify-content: space-between;
  align-items:center;
  gap: 12px;
}

.portal-btn{
  appearance: none;
  border: 1px solid rgba(255,255,255,0.22);
  background: rgba(255,255,255,0.92);
  color: #111;
  border-radius: 999px;
  padding: 12px 18px;
  font-weight: 800;
  letter-spacing: 2px;
  text-transform: uppercase;
  cursor: pointer;
  transition: transform 0.16s ease, box-shadow 0.16s ease;
  white-space: nowrap;
}

.portal-btn:hover{
  transform: scale(1.04);
  box-shadow: 0 0 55px rgba(255,232,180,0.16);
}

.portal-tag{
  position: relative;
  font-size: 12px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: rgba(255,255,255,0.60);
  border: 1px solid rgba(255,255,255,0.14);
  border-radius: 999px;
  padding: 8px 12px;
  background: rgba(0,0,0,0.18);
}

/* ===== CONTACT ===== */
.contact-btn{
  position: fixed;
  bottom: 20px;
  right: 20px;
  padding: 12px 24px;
  font-size: 18px;
  border-radius: 10px;
  border: none;
  background-color: rgba(255,255,255,0.92);
  cursor: pointer;
  z-index: 3;
}

/* FOOTER */
.footer{
  margin-top: 26px;
  color: rgba(255,255,255,0.52);
  font-size: 12px;
  letter-spacing: 3px;
  text-transform: uppercase;
}

/* RESPONSIVE */
@media (max-width: 980px){
  .portals{ grid-template-columns: 1fr; }
  .portal-desc{ min-height: auto; }
  .brand{ font-size: 44px; }
}
</style>
</head>

<body>

<div class="stars"></div>
<div class="runes"></div>
<div class="dust"></div>

<a href="contacter.py">
  <button class="contact-btn">Nous contacter</button>
</a>

<div class="sanctuary">
  <h1 class="brand">Privealy</h1>
  <div class="motto">Le privilege de savoir</div>

  <div class="whisper">
    Rien ici n'est "donne". Tout se revele.<br>
    Choisis un portail. Observe. Relie. Comprends.
  </div>

  <div class="divider"></div>

  <div class="portals">

    <!-- PORTAIL 1 : ECONOMY -->
    <div class="portal">
      <div class="portal-top">
        <div class="portal-sigil"></div>
        <h2 class="portal-title">Privealy Economy</h2>
      </div>

      <div class="portal-desc">
        Analyse, simulation et classement des objets.
        Trouve les structures cachees dans les prix.
      </div>

      <div class="portal-action">
        <a href="index.py" style="text-decoration:none;">
          <button class="portal-btn">Entrer</button>
        </a>
        <div class="portal-tag">Privealy 1.1</div>
      </div>
    </div>

    <!-- PORTAIL 2 : CLIMAT -->
    <div class="portal">
      <div class="portal-top">
        <div class="portal-sigil"></div>
        <h2 class="portal-title">Privealy Climat</h2>
      </div>

      <div class="portal-desc">
        Signaux, tendances et anomalies.
        Le monde bouge avant qu'on le voie.
      </div>

      <div class="portal-action">
        <a href="climat.py" style="text-decoration:none;">
          <button class="portal-btn">Entrer</button>
        </a>
        <div class="portal-tag">Alpha 0.25 </div>
      </div>
    </div>

    <!-- PORTAIL 3 : EVENT -->
    <div class="portal">
      <div class="portal-top">
        <div class="portal-sigil"></div>
        <h2 class="portal-title">Privealy Event</h2>
      </div>

      <div class="portal-desc">
        Actualites, evenements, correlations.
        Le chaos devient lisible.
      </div>

      <div class="portal-action">
        <a href="event.py" style="text-decoration:none;">
          <button class="portal-btn">Entrer</button>
        </a>
        <div class="portal-tag">Beta</div>
      </div>
    </div>

  </div>

  <div class="footer">Analyse · Simulation · Projection</div>
</div>

</body>
</html>
""")
