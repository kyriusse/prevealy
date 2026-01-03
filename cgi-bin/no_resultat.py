def page_no_resultat():
    return """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Pas intéressant</title>

<style>
body {
  margin: 0;
  height: 100vh;

  /* FOND IMAGE */
  background: url('/fond_rouge.png') no-repeat center center;
  background-size: 100% 100%;

  display: flex;
  justify-content: center;
  align-items: center;
  font-family: Arial, sans-serif;
  color: white;
}

.container {
  text-align: center;
  margin-top: 100px;
}

.spirale {
  width: 300px;
  margin-bottom: 100px;
}

h1 {
  font-size: 56px;
  margin-bottom: 40px;
}

.btn-img {
  display: block;
  margin: 18px auto;
  width: 360px;
  cursor: pointer;
  transition: 0.2s;
}

.btn-img:hover {
  transform: scale(1.05);
}

/* BOUTON TEXTE SANS FOND */
.contact-link {
  display: block;
  margin-top: 35px;
  font-size: 26px;
  color: white;
  text-decoration: none;
  background: none;
  cursor: pointer;
  transition: 0.2s;
}

.contact-link:hover {
  text-decoration: underline;
  opacity: 0.8;
}

a {
  text-decoration: none;
}
</style>
</head>

<body>
  <div class="container">

    <img src="/spirale.png" class="spirale">

    <h1>Pas intéressant</h1>

    <a href="/cgi-bin/index.py">
      <img src="/btn_home.png" class="btn-img">
    </a>

    <a href="/cgi-bin/contacter.py" class="contact-link">
      Nous contacter
    </a>

  </div>
</body>
</html>"""
