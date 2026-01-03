    #!/usr/bin/env python3
import sqlite3
import sys
import difflib
import urllib.request
import urllib.parse
import json
from no_resultat import page_no_resultat
import re
import os

print("Content-Type: text/html; charset=utf-8\n")

# 🔑 CLÉ UNSPLASH
UNSPLASH_ACCESS_KEY = "Z-alaucSBZjnArcjCj3H0hWhxpt31Va448B0X4ozdzM"

# ---------- FONCTION TRADUCTION FR → EN (LibreTranslate) ----------
def translate_fr_en(text):
    try:
        data = urllib.parse.urlencode({
            "q": text,
            "source": "fr",
            "target": "en",
            "format": "text"
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://libretranslate.com/translate",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("translatedText", text)

    except:
        return text

# ---------- HTML HEADER ----------
print("""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Résultats</title>
<style>
body {
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 40px;
    background: url('/fond.png') no-repeat center center fixed;
    background-size: cover;
}

.results {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 30px;
}

.card {
    background-color: rgba(75, 75, 75, 0.7);
    border-radius: 16px;
    padding: 20px;
    text-align: center;
    box-shadow: 0 8px 20px rgba(255,255,255,0.15);
    transition: 0.2s;
}

.card:hover {
    transform: translateY(-5px);
}

.card img {
    width: 100%;
    height: 220px;
    object-fit: cover;
    border-radius: 12px;
}

.card h2 {
    margin-top: 15px;
    font-size: 20px;
    color: white;
}

a {
    text-decoration: none;
}
</style>
</head>
<body>
""")

# ---------- RÉCUP RECHERCHE ----------
def get_param(name, default=""):
    qs = os.environ.get("QUERY_STRING", "")
    params = urllib.parse.parse_qs(qs, keep_blank_values=True)
    return params.get(name, [default])[0]

query = get_param("q")

if not query:
    print("<h2>Aucune recherche</h2></body></html>")
    sys.exit()

query_lower = query.lower()

# ---------- BDD ----------
DB_PATH = "cgi-bin/objets.db"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("SELECT Objet, Famille, Type FROM Prix_Objets")
rows = cur.fetchall()
objets = rows

# ---------- RECHERCHE TOLÉRANTE ----------
resultats = []

for objet, famille, type_ in objets:
    score = 0
    objet_lower = objet.lower()

    for mot in query_lower.split():
        if mot in objet_lower:
            score += 2
        elif difflib.SequenceMatcher(None, mot, objet_lower).ratio() > 0.6:
            score += 1

    if score > 0:
        resultats.append((score, objet, famille, type_))
        
resultats.sort(reverse=True)
resultats = resultats[:6]


if not resultats:
    print(page_no_resultat())
    sys.exit()

# ---------- UNSPLASH ----------
def get_unsplash_image(objet, famille, type_):
    # 1Nettoyage : enlever les parenthèse
    objet_clean = re.sub(r"\s*\(.*?\)", "", objet).strip()

    # 2Traduction
    objet_en = translate_fr_en(objet_clean)
    famille_en = translate_fr_en(famille) if famille else ""
    type_en = translate_fr_en(type_) if type_ else ""

    # 3 Construction requête intelligente
    query = f"{objet_en} {type_en} {famille_en} product isolated"

    try:
        params = urllib.parse.urlencode({
            "query": query,
            "per_page": 1,
            "orientation": "squarish",
            "content_filter": "high"
        })

        req = urllib.request.Request(
            f"https://api.unsplash.com/search/photos?{params}",
            headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"}
        )

        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            if data.get("results"):
                return data["results"][0]["urls"]["regular"]

    except:
        pass

    return "/no_image.png"

# ---------- AFFICHAGE ----------
print("<div class='results'>")

for _, objet, famille, type_ in resultats:
    img = get_unsplash_image(objet, famille, type_)

    print(f"""
    <a href="/cgi-bin/objet.py?nom={urllib.parse.quote(objet)}&img={urllib.parse.quote(img)}">
        <div class="card">
            <img src="{img}">
            <h2>{objet}</h2>
        </div>
    </a>
    """)

print("</div>")
print("</body></html>")
conn.close()
