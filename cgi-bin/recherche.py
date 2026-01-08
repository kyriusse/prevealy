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
CLE_ACCES_UNSPLASH = "Z-alaucSBZjnArcjCj3H0hWhxpt31Va448B0X4ozdzM"

# ---------- FONCTION TRADUCTION FR → EN (LibreTranslate) ----------
def traduire_fr_vers_en(texte):
    """Traduit un texte du français vers l'anglais via LibreTranslate."""
    try:
        donnees = urllib.parse.urlencode(
            {
                "q": texte,
                "source": "fr",
                "target": "en",
                "format": "text",
            }
        ).encode("utf-8")

        requete = urllib.request.Request(
            "https://libretranslate.com/translate",
            data=donnees,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        with urllib.request.urlopen(requete, timeout=5) as reponse:
            resultat = json.loads(reponse.read().decode("utf-8"))
            return resultat.get("translatedText", texte)

    except Exception:
        return texte

# ---------- ENTÊTE HTML ----------
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
def recuperer_parametre(nom, defaut=""):
    """Récupère un paramètre depuis la query string."""
    chaine_requete = os.environ.get("QUERY_STRING", "")
    parametres = urllib.parse.parse_qs(chaine_requete, keep_blank_values=True)
    return parametres.get(nom, [defaut])[0]

requete = recuperer_parametre("q")

if not requete:
    print("<h2>Aucune recherche</h2></body></html>")
    sys.exit()

requete_minuscule = requete.lower()

# ---------- BDD ----------
CHEMIN_BDD = "cgi-bin/objets.db"
connexion = sqlite3.connect(CHEMIN_BDD)
curseur = connexion.cursor()

curseur.execute("SELECT Objet, Famille, Type FROM Prix_Objets")
lignes = curseur.fetchall()
objets = lignes

# ---------- RECHERCHE TOLÉRANTE ----------
resultats = []

for objet, famille, type_objet in objets:
    score_recherche = 0
    objet_minuscule = objet.lower()

    for mot in requete_minuscule.split():
        if mot in objet_minuscule:
            score_recherche += 2
        elif difflib.SequenceMatcher(None, mot, objet_minuscule).ratio() > 0.6:
            score_recherche += 1

    if score_recherche > 0:
        resultats.append((score_recherche, objet, famille, type_objet))
        
resultats.sort(reverse=True)
resultats = resultats[:6]


if not resultats:
    print(page_no_resultat())
    sys.exit()

# ---------- UNSPLASH ----------
def recuperer_image_unsplash(objet, famille, type_objet):
    """Récupère une image Unsplash en fonction de l'objet."""
    # 1 Nettoyage : enlever les parenthèses
    objet_nettoye = re.sub(r"\s*\(.*?\)", "", objet).strip()

    # 2 Traduction
    objet_en = traduire_fr_vers_en(objet_nettoye)
    famille_en = traduire_fr_vers_en(famille) if famille else ""
    type_en = traduire_fr_vers_en(type_objet) if type_objet else ""

    # 3 Construction requête intelligente
    requete = f"{objet_en} {type_en} {famille_en} product isolated"

    try:
        parametres_requete = urllib.parse.urlencode(
            {
                "query": requete,
                "per_page": 1,
                "orientation": "squarish",
                "content_filter": "high",
            }
        )

        requete_http = urllib.request.Request(
            f"https://api.unsplash.com/search/photos?{parametres_requete}",
            headers={"Authorization": f"Client-ID {CLE_ACCES_UNSPLASH}"},
        )

        with urllib.request.urlopen(requete_http, timeout=5) as reponse:
            donnees = json.loads(reponse.read().decode("utf-8"))
            if donnees.get("results"):
                return donnees["results"][0]["urls"]["regular"]

    except Exception:
        pass

    return "/no_image.png"

# ---------- AFFICHAGE ----------
print("<div class='results'>")

for _, objet, famille, type_objet in resultats:
    image = recuperer_image_unsplash(objet, famille, type_objet)

    print(f"""
    <a href="/cgi-bin/objet.py?nom={urllib.parse.quote(objet)}&img={urllib.parse.quote(image)}">
        <div class="card">
            <img src="{image}">
            <h2>{objet}</h2>
        </div>
    </a>
    """)

print("</div>")
print("</body></html>")
connexion.close()
