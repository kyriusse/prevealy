#!/usr/bin/python3
# -*- coding: utf-8 -*-

print("Content-type: text/html; charset=utf-8\n")

print("""
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Stats</title>

<style>
body {
    background-image: url('/fond_violet_page_stats.png');
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    margin: 0;
    padding-top: 10vh;
    font-family: Arial, sans-serif;
    color: white;
    display: flex;
    flex-direction: column;
    align-items: center;
    min-height: 100vh;
}

h1 {
    margin-bottom: 30px;
    font-size: 3em;
    text-shadow: 0 0 10px rgba(255,255,255,0.5);
}

.button-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 25px;
    width: 95%;
    max-width: 1400px;
}

.tool-link {
    display: block;
    width: 100%;
    height: 180px;
    transition: transform 0.15s;
}

.tool-link:hover {
    transform: scale(1.03);
}

.tool-link img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    display: block;
}

.back-btn {
    margin-top: 50px;
    padding: 10px 20px;
    color: #ccc;
    border: 1px solid #ccc;
    border-radius: 5px;
    text-decoration: none;
}
.back-btn:hover {
    color: white;
}
</style>
</head>

<body>

<h1>Stats</h1>

<div class="button-grid">

    <a href="recherche_populaire.py" class="tool-link">
        <img src="/recherche_populaire.png" alt="Recherche Populaire">
    </a>

    <a href="filtre_simple.py" class="tool-link">
        <img src="/btn_filtre_simple.png" alt="Recherche par condition">
    </a>

    <a href="calculs_classements.py" class="tool-link">
        <img src="/calcule_classement_recherche_principale.png" alt="Calculs et classements">
    </a>

</div>

<a href="index.py" class="back-btn">← Retour à l'accueil</a>

</body>
</html>
""")
