#!/usr/bin/env python3
print("Content-Type: text/html; charset=utf-8\n")

print("""
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>Nous contacter</title>
  <style>
    body {
      margin: 0;
      padding: 0;
      background-image: url('/roblox.png');
      background-repeat: no-repeat;
      background-size: 100% 100%;
      background-position: center;
      background-attachment: fixed;
      font-family: Arial, sans-serif;
      color: white;
    }

    .logo {
      display: block;
      margin: 80px auto;
      transform: scale(1.3);
      transform-origin: center center;
    }

    /* BOUTON BACK HOME */
    .back-btn {
      position: fixed;
      bottom: 180px;
      left: 50%;
      transform: translateX(-50%);
      padding: 14px 36px;
      font-size: 48px;
      font-weight: 600;
      background-color: rgba(0, 0, 0, 0.7);
      color: white;
      border: none;
      border-radius: 999px;
      cursor: pointer;
      transition: all 0.25s ease;
    }

    .back-btn:hover {
      background-color: rgba(255, 255, 255, 0.9);
      color: black;
    }

  </style>
</head>

<body>

  <img src="/NON.png" class="logo">

  <a href="/cgi-bin/index.py">
    <button class="back-btn">Back Home</button>
  </a>

</body>
</html>
""")
