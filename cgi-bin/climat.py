#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import csv
import urllib.parse
import html

print("Content-Type: text/html; charset=utf-8\n")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "owid-co2-data.csv")


def esc(s):
    return html.escape("" if s is None else str(s))


def get_param(name, default=""):
    qs = os.environ.get("QUERY_STRING", "")
    params = urllib.parse.parse_qs(qs, keep_blank_values=True)
    return params.get(name, [default])[0]


PREFERRED = [
    "co2",
    "co2_per_capita",
    "methane",
    "nitrous_oxide",
    "total_ghg",
]


def read_header(csv_path):
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        return next(r)


def choose_indicators(header):
    hset = set(header)
    out = [c for c in PREFERRED if c in hset]
    if out:
        return out

    # fallback: take a few numeric columns (skip basics)
    blacklist = set(["country", "entity", "year", "iso_code"])
    for c in header:
        if c in blacklist:
            continue
        out.append(c)
        if len(out) >= 10:
            break
    return out


def load_entity_series(csv_path, entity, indicator):
    """
    Returns list of (year:int, value:str) sorted by year asc.
    Only rows where Entity == entity (exact match).
    """
    rows = []
    if not entity:
        return rows

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        dr = csv.DictReader(f)
        for row in dr:
            ent = (row.get("country") or row.get("entity") or row.get("Entity") or "").strip()
            if ent != entity:
                continue

            y = row.get("year") or row.get("Year")
            v = row.get(indicator)

            if y is None or y.strip() == "":
                continue
            if v is None or str(v).strip() == "":
                continue

            try:
                yi = int(float(y))
            except Exception:
                continue

            rows.append((yi, v))

    rows.sort(key=lambda x: x[0])
    return rows


def fmt_num(v):
    try:
        f = float(v)
        s = ("%0.6f" % f).rstrip("0").rstrip(".")
        return s
    except Exception:
        return str(v)


# -------------------------
# MAIN
# -------------------------
if not os.path.exists(CSV_PATH):
    print("<h2>OWID CSV error</h2>")
    print("<p>File not found:</p>")
    print("<pre>%s</pre>" % esc(CSV_PATH))
    print("<p>Files in cgi-bin:</p>")
    try:
        print("<pre>%s</pre>" % esc("\n".join(sorted(os.listdir(BASE_DIR)))))
    except Exception:
        pass
    raise SystemExit

header = read_header(CSV_PATH)

# detect entity column name
# OWID csv usually uses "country" + "year"
ENTITY_COL = "country" if "country" in header else ("entity" if "entity" in header else "")

if not ENTITY_COL or ("year" not in header):
    print("<h2>OWID CSV error</h2>")
    print("<p>CSV header does not contain required columns.</p>")
    print("<p>Need at least: country/entity + year</p>")
    print("<pre>%s</pre>" % esc(", ".join(header)))
    raise SystemExit

indicators = choose_indicators(header)

entity = get_param("entity", "World").strip()
indicator = get_param("indicator", indicators[0] if indicators else "co2").strip()

if indicator not in indicators and indicators:
    indicator = indicators[0]

series = load_entity_series(CSV_PATH, entity, indicator)

last_year = None
last_val = None
if series:
    last_year, last_val = series[-1]

# last 20 rows desc
last_rows = list(reversed(series[-20:]))

indicator_opts = "\n".join(
    ['<option value="%s"%s>%s</option>' % (esc(c), (" selected" if c == indicator else ""), esc(c)) for c in indicators]
)

print(r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Privealy Climat</title>
<style>
:root{
  --txt:#ffffff;
  --muted:rgba(255,255,255,0.72);
  --muted2:rgba(255,255,255,0.55);
  --card: rgba(255,255,255,0.10);
  --card2: rgba(255,255,255,0.06);
  --line: rgba(255,255,255,0.16);
  --shadow: rgba(0,0,0,0.68);
  --gold: rgba(255,232,180,0.85);
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
    linear-gradient(180deg, rgba(0,0,0,0.40), rgba(0,0,0,0.90)),
    url('/fond.png');
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
}

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
    radial-gradient(1px 1px at 92% 84%, rgba(255,255,255,0.75), transparent 60%);
  animation: twinkle 4.2s ease-in-out infinite;
}
@keyframes twinkle{
  0%{ opacity: 0.40; transform: translateY(0px); }
  50%{ opacity: 0.70; transform: translateY(-2px); }
  100%{ opacity: 0.40; transform: translateY(0px); }
}

.topbar{
  position: relative;
  z-index: 2;
  width: min(1100px, 94vw);
  margin: 22px auto 0;
  padding: 0 4px;
  display:flex;
  align-items:flex-end;
  justify-content: space-between;
  gap: 14px;
}

.brand{
  margin:0;
  font-size: 30px;
  letter-spacing: 4px;
  text-transform: uppercase;
}

.motto{
  margin-top: 10px;
  font-size: 12px;
  letter-spacing: 3px;
  text-transform: uppercase;
  color: var(--muted);
}

.back_btn_gris{
  display:inline-block;
  width: 58px;
  height: 58px;
  background-image: url('/back_btn_gris.png');
  background-size: contain;
  background-repeat: no-repeat;
  background-position: center;
  opacity: 0.88;
  transition: transform 0.18s ease, opacity 0.18s ease;
}
.back_btn_gris:hover{
  transform: scale(1.08);
  opacity: 1;
}

.wrap{
  position: relative;
  z-index: 2;
  width: min(1100px, 94vw);
  margin: 18px auto 28px;
  height: calc(100vh - 120px);
  display:flex;
  flex-direction: column;
  gap: 14px;
}

.panel{
  background: linear-gradient(180deg, var(--card), var(--card2));
  border: 1px solid var(--line);
  border-radius: 18px;
  box-shadow: 0 30px 110px var(--shadow);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  padding: 18px;
}

.controls{
  display:flex;
  gap: 12px;
  align-items:center;
  justify-content: space-between;
  flex-wrap: wrap;
}

.formline{
  display:flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items:center;
  width: 100%;
}

.input, select{
  padding: 12px 14px;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.22);
  background: rgba(0,0,0,0.25);
  color: white;
  outline: none;
  font-size: 14px;
}

.input{
  flex: 1;
  min-width: 240px;
}

.btn{
  border: 1px solid rgba(255,255,255,0.22);
  background: rgba(255,255,255,0.92);
  color: #111;
  border-radius: 999px;
  padding: 12px 16px;
  font-weight: 800;
  letter-spacing: 2px;
  text-transform: uppercase;
  cursor: pointer;
  transition: transform 0.16s ease, box-shadow 0.16s ease;
  white-space: nowrap;
}
.btn:hover{
  transform: scale(1.03);
  box-shadow: 0 0 55px rgba(255,232,180,0.16);
}

.kpi{
  display:flex;
  gap: 14px;
  flex-wrap: wrap;
  align-items: stretch;
}

.kpi-box{
  flex: 1;
  min-width: 240px;
  border: 1px solid rgba(255,255,255,0.14);
  background: rgba(0,0,0,0.22);
  border-radius: 16px;
  padding: 14px;
}

.kpi-title{
  font-size: 12px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--muted);
}

.kpi-main{
  margin-top: 8px;
  font-size: 28px;
  font-weight: 900;
  letter-spacing: 0.5px;
}

.kpi-sub{
  margin-top: 6px;
  color: var(--muted2);
  font-size: 12px;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.tablewrap{
  overflow:auto;
  max-height: 46vh;
  padding-right: 4px;
}

table{
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}

th, td{
  text-align: left;
  padding: 10px 8px;
  border-bottom: 1px solid rgba(255,255,255,0.10);
}

th{
  color: rgba(255,255,255,0.86);
  font-size: 12px;
  letter-spacing: 2px;
  text-transform: uppercase;
}

.note{
  margin-top: 10px;
  color: rgba(255,255,255,0.58);
  font-size: 12px;
  letter-spacing: 1px;
}

@media (max-width: 980px){
  .wrap{ height: auto; overflow:auto; padding-bottom: 22px; }
  body{ overflow:auto; }
  .tablewrap{ max-height: none; }
}
</style>
</head>
<body>

<div class="stars"></div>

<div class="topbar">
  <div style="display:flex; align-items:center; gap:12px;">
    <a href="vrai_index.py" class="back_btn_gris" title="Back"></a>
    <div>
      <h1 class="brand">Privealy Climat</h1>
      <div class="motto">Signals, trends, anomalies. The world moves before we see it.</div>
    </div>
  </div>
</div>
""")

print("""
<div class="wrap">

  <div class="panel">
    <div class="controls">
      <form method="get" action="climat.py" class="formline">
        <input class="input" type="text" name="entity" value="%s" placeholder="Entity (ex: World, France, United States)">
        <select name="indicator">
          %s
        </select>
        <button class="btn" type="submit">Load</button>
      </form>
    </div>
    <div class="note">
      Source file: owid-co2-data.csv (in cgi-bin). Exact match on Entity/Country for now.
    </div>
  </div>
""" % (esc(entity), indicator_opts))

# KPI panel
print('<div class="panel"><div class="kpi">')

if series:
    print("""
      <div class="kpi-box">
        <div class="kpi-title">Last known value</div>
        <div class="kpi-main">%s</div>
        <div class="kpi-sub">%s - %s</div>
      </div>
      <div class="kpi-box">
        <div class="kpi-title">Records found</div>
        <div class="kpi-main">%s</div>
        <div class="kpi-sub">From %s to %s</div>
      </div>
    """ % (
        esc(fmt_num(last_val)),
        esc(entity),
        esc(str(last_year)),
        esc(str(len(series))),
        esc(str(series[0][0])),
        esc(str(series[-1][0]))
    ))
else:
    print("""
      <div class="kpi-box">
        <div class="kpi-title">No data found</div>
        <div class="kpi-main">-</div>
        <div class="kpi-sub">Try: World, France, United States, China, India...</div>
      </div>
    """)

print("</div></div>")  # end kpi

# Table
print('<div class="panel"><div style="font-size:12px; letter-spacing:2px; text-transform:uppercase; color: rgba(255,232,180,0.85);">Last 20 years</div>')
print('<div class="tablewrap"><table>')
print("<tr><th>Year</th><th>%s</th></tr>" % esc(indicator))

if last_rows:
    for (y, v) in last_rows:
        print("<tr><td>%s</td><td>%s</td></tr>" % (esc(y), esc(fmt_num(v))))
else:
    print("<tr><td colspan='2' style='color: rgba(255,255,255,0.70);'>No rows.</td></tr>")

print("</table></div>")
print("<div class='note'>Next step: add fuzzy search for entity, graphs, and simple prediction.</div>")
print("</div>")

print("""
</div>
</body>
</html>
""")
