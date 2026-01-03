import http.server
import os
#si problème, penser à changer de port.
PORT = 578
server_address = ("", PORT)

handler = http.server.CGIHTTPRequestHandler


handler.cgi_directories = ["/cgi-bin"]

# Si autre problème, exécuter des scripts à la racine (déconseiller) 
# handler.cgi_directories = ["/cgi-bin", "/"] 
# ----------------------

print("Serveur actif sur le port :", PORT)
print("Racine du serveur dans", os.getcwd())

httpd = http.server.HTTPServer(server_address, handler)
httpd.serve_forever()

#http://localhost:578/cgi-bin/vrai_index.py
     
