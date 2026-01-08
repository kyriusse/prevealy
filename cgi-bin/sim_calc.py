# sim_calc.py
# Moteur de simulation deterministe (sans CGI, sans HTML)
#
# Objectif:
# - Interpreter une projection sur N annees
# - Appliquer les "evenements" (Ep principalement)
# - Tenir compte des liaisons (propagation)
#
# IMPORTANT:
# - Ce fichier ne doit jamais faire de print HTML
# - Il doit juste fournir des fonctions "propres" reutilisables

from stats_utils import facteur_speculation, facteur_utilisation


# ============================================================
# Constantes moteur
# ============================================================

# Limite de propagation dans le reseau (liaisons_objets)
PROFONDEUR_RESEAU_MAX = 6

# Attenuation sur la propagation (niveau 1 -> *0.70, niveau 2 -> *0.70^2, ...)
ATTENUATION_RESEAU = 0.70

# Croissance annuelle par defaut si on ne sait pas faire mieux
TAUX_PRIX_DEFAUT = 0.02
TAUX_CA_DEFAUT = 0.01


# ============================================================
# Outils internes: conversion robuste
# ============================================================

def _float_robuste(texte, defaut=0.0):
    """Convertit en float, accepte virgule, sinon defaut."""
    try:
        return float(str(texte).replace(",", "."))
    except Exception:
        return defaut


def _int_robuste(texte, defaut=0):
    """Convertit en int, sinon defaut."""
    try:
        return int(str(texte))
    except Exception:
        return defaut


# ============================================================
# Detection colonnes utiles dans stat_objects
# ============================================================

def detecter_colonnes_statistiques(connexion, nom_table="stat_objects"):
    """
    Detecte des colonnes probables:
    - id
    - nom (objet)
    - prix_moyen, prix_min, prix_max
    - ca
    - famille, type
    - speculation, taux_utilisation, coef_aug_prev

    Retourne: dict {cle_interne: nom_colonne_sqlite_ou_None}
    """
    cur = connexion.cursor()
    cur.execute("PRAGMA table_info({})".format(nom_table))
    infos = cur.fetchall()

    # Liste de colonnes presentes (en minuscules) -> vrai nom
    mapping_present = {}
    for col in infos:
        nom_col = col[1]
        if nom_col is not None:
            mapping_present[str(nom_col).lower()] = nom_col

    def prendre(*candidats):
        """Renvoie la premiere colonne existante parmi candidats."""
        for c in candidats:
            cc = str(c).lower()
            if cc in mapping_present:
                return mapping_present[cc]
        return None

    colonnes = {}
    colonnes["id"] = prendre("id")
    colonnes["nom"] = prendre("objet", "nom", "name")
    colonnes["prix_moyen"] = prendre("prix_moyen", "prix_moyen_actuel", "prixmoyen", "prix")
    colonnes["prix_min"] = prendre("prix_min", "prix_min_eur", "min", "prixmin")
    colonnes["prix_max"] = prendre("prix_max", "prix_max_eur", "max", "prixmax")
    colonnes["ca"] = prendre("ca", "ca_2025_2035_mdeur", "chiffre_affaires", "chiffreaffaires")
    colonnes["famille"] = prendre("famille")
    colonnes["type"] = prendre("type")
    colonnes["speculation"] = prendre("speculation")
    colonnes["taux_utilisation"] = prendre("taux_utilisation", "utilisation")
    colonnes["coef_aug_prev"] = prendre("coef_aug_prev", "coef_augmentation", "coef")

    return colonnes


# ============================================================
# Lecture objets / selection (objets, famille, type)
# ============================================================

def lister_objets_par_ids(connexion, colonnes, ids_objets, nom_table="stat_objects"):
    """Retourne liste de dict pour chaque objet id."""
    if not ids_objets:
        return []

    # IMPORTANT: requete parametree (IN) sans injection
    placeholders = ",".join(["?"] * len(ids_objets))
    cur = connexion.cursor()

    cols_sql = []
    for cle, nom_col in colonnes.items():
        if nom_col:
            cols_sql.append("[{}]".format(nom_col))

    if not cols_sql:
        return []

    requete = "SELECT {} FROM {} WHERE [{}] IN ({})".format(
        ", ".join(cols_sql),
        nom_table,
        colonnes["id"],
        placeholders
    )
    cur.execute(requete, tuple(ids_objets))
    lignes = cur.fetchall()

    # Recomposer en dict
    resultat = []
    for lig in lignes:
        d = {}
        for i, nom_col in enumerate(cols_sql):
            # nom_col = "[xxx]" -> extraire xxx
            cle_reelle = nom_col.strip("[]")
            d[cle_reelle] = lig[i]
        resultat.append(d)

    return resultat


def lister_ids_objets_par_famille(connexion, colonnes, famille, nom_table="stat_objects"):
    """Retourne ids de la famille donnee."""
    if not famille or not colonnes.get("famille"):
        return []
    cur = connexion.cursor()
    cur.execute(
        "SELECT [{}] FROM {} WHERE [{}] = ?".format(
            colonnes["id"], nom_table, colonnes["famille"]
        ),
        (famille,)
    )
    return [r[0] for r in cur.fetchall()]


def lister_ids_objets_par_type(connexion, colonnes, type_objet, nom_table="stat_objects"):
    """Retourne ids du type donne."""
    if not type_objet or not colonnes.get("type"):
        return []
    cur = connexion.cursor()
    cur.execute(
        "SELECT [{}] FROM {} WHERE [{}] = ?".format(
            colonnes["id"], nom_table, colonnes["type"]
        ),
        (type_objet,)
    )
    return [r[0] for r in cur.fetchall()]


# ============================================================
# Reseau: liaisons_objets (propagation)
# ============================================================

def voisins_objet(connexion, objet_id):
    """
    Retourne la liste des voisins directs d un objet via liaisons_objets.
    IMPORTANT: on suppose la table creee par liaison.py
    """
    cur = connexion.cursor()
    try:
        # Priorite: table liaisons_applicables (nouveau)
        cur.execute(
            """
            SELECT source_id, cible_id, implication
            FROM liaisons_applicables
            WHERE type_applicable = 'O' AND (source_id = ? OR cible_id = ?)
            """,
            (objet_id, objet_id)
        )
        voisins = []
        for sid, cid, impl in cur.fetchall():
            if sid == objet_id:
                voisins.append(cid)
            elif impl == "<->" and cid == objet_id:
                voisins.append(sid)
        if voisins:
            return list(dict.fromkeys(voisins))
    except Exception:
        pass

    try:
        cur.execute(
            "SELECT cible_objet_id FROM liaisons_objets WHERE source_objet_id = ?",
            (objet_id,)
        )
        return [r[0] for r in cur.fetchall()]
    except Exception:
        return []


def calculer_propagation_reseau(connexion, objets_depart, profondeur_max=PROFONDEUR_RESEAU_MAX, attenuation=ATTENUATION_RESEAU):
    """
    Propagation BFS:
    - niveau 0: objets_depart
    - niveau n: voisins de niveau n-1
    - poids = attenuation^niveau

    Retour:
    - dict objet_id -> (niveau, poids)
    """
    if profondeur_max < 0:
        profondeur_max = 0
    if attenuation < 0.0:
        attenuation = 0.0
    if attenuation > 1.0:
        attenuation = 1.0

    resultat = {}
    file_bfs = []

    for oid in (objets_depart or []):
        resultat[oid] = (0, 1.0)
        file_bfs.append((oid, 0))

    # BFS classique
    while file_bfs:
        courant, niv = file_bfs.pop(0)

        if niv >= profondeur_max:
            continue

        niv_suiv = niv + 1
        poids_suiv = (attenuation ** niv_suiv)

        for v in voisins_objet(connexion, courant):
            if v is None:
                continue

            if v not in resultat:
                resultat[v] = (niv_suiv, poids_suiv)
                file_bfs.append((v, niv_suiv))
            else:
                ancien_niv, ancien_poids = resultat[v]
                # Garder le plus proche, ou le plus fort a niveau egal
                if niv_suiv < ancien_niv:
                    resultat[v] = (niv_suiv, poids_suiv)
                    file_bfs.append((v, niv_suiv))
                elif niv_suiv == ancien_niv and poids_suiv > ancien_poids:
                    resultat[v] = (niv_suiv, poids_suiv)

    return resultat


# ============================================================
# Evenements
# ============================================================

def lire_evenement(connexion, evenement_id):
    """
    Lit un evenement dans la table evenements.
    Fonction robuste: si colonnes manquent, on renvoie quand meme un dict.
    """
    cur = connexion.cursor()
    try:
        cur.execute("PRAGMA table_info(evenements)")
        info_cols = cur.fetchall()
        colonnes = [c[1] for c in info_cols]
    except Exception:
        colonnes = []

    if not colonnes:
        return None

    # Construire requete SELECT avec toutes les colonnes presentes
    cols_sql = ", ".join(["[{}]".format(c) for c in colonnes])
    try:
        cur.execute("SELECT {} FROM evenements WHERE id = ?".format(cols_sql), (evenement_id,))
        lig = cur.fetchone()
    except Exception:
        return None

    if not lig:
        return None

    evt = {}
    for i, c in enumerate(colonnes):
        evt[c] = lig[i]
    return evt


def lire_impacts_evenement(connexion, evenement_id):
    """
    Lit la table impacts_evenements (cree par liaison.py).
    Retour:
    - dict objet_id -> poids_final (probabilite incluse si disponible)
    """
    cur = connexion.cursor()
    try:
        # Support colonne probabilite si presente
        cur.execute("PRAGMA table_info(impacts_evenements)")
        colonnes = [c[1] for c in cur.fetchall()]
        if "probabilite" in colonnes:
            cur.execute(
                "SELECT objet_id, poids_final, probabilite FROM impacts_evenements WHERE evenement_id = ?",
                (evenement_id,)
            )
            d = {}
            for oid, p, prob in cur.fetchall():
                poids = _float_robuste(p, 1.0)
                probabilite = _float_robuste(prob, 1.0)
                d[oid] = max(0.0, min(1.0, poids * probabilite))
            return d
        cur.execute(
            "SELECT objet_id, poids_final FROM impacts_evenements WHERE evenement_id = ?",
            (evenement_id,)
        )
        d = {}
        for oid, p in cur.fetchall():
            d[oid] = _float_robuste(p, 1.0)
        return d
    except Exception:
        return {}


def lire_parametres_evenement(connexion, evenement_id):
    """Lit la table parametres_evenements sous forme dict."""
    cur = connexion.cursor()
    try:
        cur.execute(
            "SELECT cle, valeur FROM parametres_evenements WHERE evenement_id = ? ORDER BY ordre ASC",
            (evenement_id,)
        )
        d = {}
        for cle, val in cur.fetchall():
            if cle:
                d[str(cle)] = val
        return d
    except Exception:
        return {}


def _ids_depuis_chaine(chaine):
    """Transforme '1,2,3' -> [1,2,3]."""
    resultat = []
    for morceau in (chaine or "").split(","):
        m = morceau.strip()
        if m.isdigit():
            v = int(m)
            if v not in resultat:
                resultat.append(v)
    return resultat


def _lister_tous_objets(connexion, colonnes):
    """Liste tous les ids d objets."""
    if not colonnes.get("id"):
        return []
    cur = connexion.cursor()
    try:
        cur.execute("SELECT [{}] FROM stat_objects".format(colonnes["id"]))
        return [r[0] for r in cur.fetchall()]
    except Exception:
        return []


def determiner_impacts_depuis_parametres(connexion, colonnes, params):
    """
    Construit un dict objet_id -> poids (1.0) a partir des parametres Ep.
    """
    if not params:
        return {}
    portee = str(params.get("appliquer_portee", "tout") or "tout")
    ids = []
    if portee == "liste":
        ids = _ids_depuis_chaine(params.get("appliquer_objets_ids", ""))
    elif portee == "famille":
        ids = lister_ids_objets_par_famille(connexion, colonnes, params.get("appliquer_famille", ""))
    elif portee == "type":
        ids = lister_ids_objets_par_type(connexion, colonnes, params.get("appliquer_type", ""))
    else:
        ids = _lister_tous_objets(connexion, colonnes)

    impacts = {}
    for oid in ids:
        impacts[oid] = 1.0
    return impacts


def _extraire_valeur_evt(evt, *noms_possibles, defaut=None):
    """Extrait une valeur d un dict evt via plusieurs noms possibles."""
    if not evt:
        return defaut
    # Essayer exact
    for n in noms_possibles:
        if n in evt:
            return evt.get(n)
    # Essayer en insensible a la casse
    lower_map = {}
    for k in evt.keys():
        lower_map[str(k).lower()] = k
    for n in noms_possibles:
        kk = lower_map.get(str(n).lower())
        if kk is not None:
            return evt.get(kk)
    return defaut


# ============================================================
# Etat interne d un objet pendant la simulation
# ============================================================

def construire_etat_objets_initial(connexion, colonnes, ids_objets):
    """
    Construit un etat initial minimal:
    etat[objet_id] = {
      "nom": ...,
      "prix_moyen": ...,
      "prix_min": ...,
      "prix_max": ...,
      "ca": ...,
      "famille": ...,
      "type": ...,
      "speculation": ...,
      "taux_utilisation": ...,
      "coef_aug_prev": ...
    }
    """
    etat = {}
    if not ids_objets:
        return etat

    # Requete par id, avec colonnes disponibles
    placeholders = ",".join(["?"] * len(ids_objets))

    champs = []
    for cle in ["id", "nom", "prix_moyen", "prix_min", "prix_max", "ca", "famille", "type", "speculation", "taux_utilisation", "coef_aug_prev"]:
        if colonnes.get(cle):
            champs.append("[{}]".format(colonnes[cle]))

    if not champs or not colonnes.get("id"):
        return etat

    cur = connexion.cursor()
    requete = "SELECT {} FROM stat_objects WHERE [{}] IN ({})".format(
        ", ".join(champs),
        colonnes["id"],
        placeholders
    )
    cur.execute(requete, tuple(ids_objets))
    lignes = cur.fetchall()

    # Indices utiles: on reconstruit a partir de "champs"
    # Exemple: champs = ["[id]","[Objet]","[Prix_Moyen_Actuel]"]
    champs_net = [c.strip("[]") for c in champs]

    for lig in lignes:
        d = {}
        for i, nom_col in enumerate(champs_net):
            d[nom_col] = lig[i]

        # Recuperer l id
        objet_id = None
        try:
            objet_id = d.get(colonnes["id"])
        except Exception:
            objet_id = None

        if objet_id is None:
            continue

        # Recuperer valeurs connues (fallback 0.0)
        nom = d.get(colonnes["nom"]) if colonnes.get("nom") else ""
        prix_moyen = _float_robuste(d.get(colonnes["prix_moyen"]), 0.0) if colonnes.get("prix_moyen") else 0.0
        prix_min = _float_robuste(d.get(colonnes["prix_min"]), prix_moyen) if colonnes.get("prix_min") else prix_moyen
        prix_max = _float_robuste(d.get(colonnes["prix_max"]), prix_moyen) if colonnes.get("prix_max") else prix_moyen
        ca = _float_robuste(d.get(colonnes["ca"]), 0.0) if colonnes.get("ca") else 0.0

        famille = d.get(colonnes["famille"]) if colonnes.get("famille") else ""
        type_obj = d.get(colonnes["type"]) if colonnes.get("type") else ""
        speculation = d.get(colonnes["speculation"]) if colonnes.get("speculation") else ""
        taux_util = d.get(colonnes["taux_utilisation"]) if colonnes.get("taux_utilisation") else ""
        coef_aug = _float_robuste(d.get(colonnes["coef_aug_prev"]), 1.02) if colonnes.get("coef_aug_prev") else 1.02

        etat[int(objet_id)] = {
            "nom": "" if nom is None else str(nom),
            "prix_moyen": prix_moyen,
            "prix_min": prix_min,
            "prix_max": prix_max,
            "ca": ca,
            "famille": "" if famille is None else str(famille),
            "type": "" if type_obj is None else str(type_obj),
            "speculation": "" if speculation is None else str(speculation),
            "taux_utilisation": "" if taux_util is None else str(taux_util),
            "coef_aug_prev": coef_aug
        }

    return etat


# ============================================================
# Base evolution annuelle (hors evenements)
# ============================================================

def appliquer_croissance_annuelle(etat_objet):
    """
    Applique une croissance simple:
    - prix: via coef_aug_prev + facteurs spec/util si dispo
    - ca: petite croissance defaut
    """
    if not etat_objet:
        return

    coef = _float_robuste(etat_objet.get("coef_aug_prev"), 1.02)

    # Facteurs "soft"
    fs = facteur_speculation(etat_objet.get("speculation"))
    fu = facteur_utilisation(etat_objet.get("taux_utilisation"))

    # Coefficient annuel final (defaut 1.02)
    coef_final = coef * fs * fu
    if coef_final <= 0:
        coef_final = 1.0

    # Prix
    etat_objet["prix_moyen"] = max(0.0, etat_objet.get("prix_moyen", 0.0) * coef_final)
    etat_objet["prix_min"] = max(0.0, etat_objet.get("prix_min", 0.0) * coef_final)
    etat_objet["prix_max"] = max(0.0, etat_objet.get("prix_max", 0.0) * coef_final)

    # CA (defaut)
    ca = _float_robuste(etat_objet.get("ca"), 0.0)
    etat_objet["ca"] = max(0.0, ca * (1.0 + TAUX_CA_DEFAUT))


# ============================================================
# Application d un evenement parametrie (Ep) sur l etat
# ============================================================

def appliquer_evenement_parametrique(
    etat,
    evenement,
    impacts,
    propagation,
    coef_prix=1.0,
    coef_ca=1.0,
    action_param="coef_evolution",
    valeur_param=1.0,
    probabilite_evt=1.0
):
    """
    Applique un evenement parametrie.
    - impacts: dict objet_id -> poids_final (table impacts_evenements)
    - propagation: dict objet_id -> (niveau, poids_reseau) (liaisons)
    - coef_prix / coef_ca: coefficients globaux (ex: 0.9 => -10%)

    Strategie "safe":
    - Pour chaque objet impacte:
        coef_local = 1 + (coef_global - 1) * poids_total
      avec poids_total = poids_final * poids_reseau
      (poids_reseau = 1 si pas dans la propagation)
    """
    if not etat or not evenement:
        return

    # Si pas d impacts, rien a appliquer
    if not impacts:
        return

    # Adapter coefficients selon action
    coef_prix_action = coef_prix
    coef_ca_action = coef_ca
    delta_prix = 0.0

    if action_param == "coef_evolution":
        coef_prix_action *= _float_robuste(valeur_param, 1.0)
        coef_ca_action *= _float_robuste(valeur_param, 1.0)
    elif action_param == "mult_prix_moyen":
        coef_prix_action *= _float_robuste(valeur_param, 1.0)
    elif action_param == "delta_prix_moyen":
        delta_prix = _float_robuste(valeur_param, 0.0)
    elif action_param == "mult_CA":
        coef_ca_action *= _float_robuste(valeur_param, 1.0)

    # Probabilite (on la traduit en poids)
    prob_evt = _float_robuste(probabilite_evt, 1.0)
    if prob_evt < 0.0:
        prob_evt = 0.0
    if prob_evt > 1.0:
        prob_evt = 1.0

    for oid, poids_impact in impacts.items():
        if oid not in etat:
            # Si l objet n est pas dans la projection, on ignore (on reste deterministe)
            continue

        # Poids reseau (liaison): si l objet est proche des objets de depart, il est plus affecte
        poids_reseau = 1.0
        if propagation and oid in propagation:
            poids_reseau = _float_robuste(propagation[oid][1], 1.0)

        poids_total = _float_robuste(poids_impact, 1.0) * poids_reseau * prob_evt
        if poids_total < 0.0:
            poids_total = 0.0
        if poids_total > 1.0:
            # On limite pour eviter des delires
            poids_total = 1.0

        # Coeff local prix / ca
        coef_local_prix = 1.0 + (coef_prix_action - 1.0) * poids_total
        coef_local_ca = 1.0 + (coef_ca_action - 1.0) * poids_total

        # Appliquer a l etat
        etat[oid]["prix_moyen"] = max(0.0, etat[oid]["prix_moyen"] * coef_local_prix + delta_prix * poids_total)
        etat[oid]["prix_min"] = max(0.0, etat[oid]["prix_min"] * coef_local_prix + delta_prix * poids_total)
        etat[oid]["prix_max"] = max(0.0, etat[oid]["prix_max"] * coef_local_prix + delta_prix * poids_total)
        etat[oid]["ca"] = max(0.0, etat[oid]["ca"] * coef_local_ca)


# ============================================================
# Simulation principale
# ============================================================

def executer_simulation(
    connexion,
    ids_projection,
    nb_annees,
    annee_depart,
    planning_evenements
):
    """
    Execute la simulation deterministe.

    Parametres:
    - ids_projection: liste d ids d objets a projeter
    - nb_annees: nombre d annees (ex: 10)
    - annee_depart: annee de depart (ex: 2025)
    - planning_evenements: liste de tuples (annee_relative, evenement_id, coef_prix, coef_ca)

      annee_relative:
        - 0 => arrive a annee_depart
        - 1 => arrive annee_depart+1
        etc.

      coef_prix / coef_ca:
        - 1.0 => aucun effet
        - 0.9 => -10%
        - 1.2 => +20%

    Retour:
    - resultats: dict
        {
          "annees": [annee1, annee2, ...],
          "prix_moyen_total": [..],
          "ca_total": [..],
          "details_objets": { objet_id: { "nom":..., "prix": [(annee,val)], "ca":[...] } }
        }
    """
    colonnes = detecter_colonnes_statistiques(connexion)

    # Securite basique: si id/nom manquent -> simulation impossible
    if not colonnes.get("id") or not colonnes.get("nom"):
        return None

    # Normaliser parametres
    nb_annees = _int_robuste(nb_annees, 1)
    if nb_annees < 1:
        nb_annees = 1
    if nb_annees > 80:
        nb_annees = 80

    annee_depart = _int_robuste(annee_depart, 2025)
    if annee_depart < 2025:
        annee_depart = 2025

    # Construire etat initial
    etat = construire_etat_objets_initial(connexion, colonnes, ids_projection)

    # Si rien charge, retour vide
    if not etat:
        return {
            "annees": [],
            "prix_moyen_total": [],
            "ca_total": [],
            "details_objets": {}
        }

    # Preparer structure de sortie par objet
    details_objets = {}
    for oid, d in etat.items():
        details_objets[oid] = {
            "nom": d.get("nom", ""),
            "prix": [],
            "ca": []
        }

    # Preparer planning: index par annee_relative
    planning_index = {}
    for (ar, eid, cp, cc) in (planning_evenements or []):
        ar = _int_robuste(ar, 0)
        eid = _int_robuste(eid, 0)
        if eid <= 0:
            continue
        # Une annee peut avoir plusieurs evenements
        planning_index.setdefault(ar, []).append((eid, _float_robuste(cp, 1.0), _float_robuste(cc, 1.0)))

    # Sorties globales
    annees = []
    prix_moyen_total = []
    ca_total = []

    # Boucle annees
    for pas in range(0, nb_annees + 1):
        annee = annee_depart + pas

        # 1) appliquer croissance annuelle (sauf a pas=0, on veut l etat "initial")
        if pas > 0:
            for oid in etat.keys():
                appliquer_croissance_annuelle(etat[oid])

        # 2) appliquer evenements prevus cette annee
        if pas in planning_index:
            for (eid, coef_prix, coef_ca) in planning_index[pas]:
                evt = lire_evenement(connexion, eid)
                impacts = lire_impacts_evenement(connexion, eid)
                params_evt = lire_parametres_evenement(connexion, eid)

                # Si impacts absents, on tente de les deduire des parametres Ep
                if not impacts:
                    impacts = determiner_impacts_depuis_parametres(connexion, colonnes, params_evt)

                # Parametres Ep utiles
                action_param = params_evt.get("action", "coef_evolution") if params_evt else "coef_evolution"
                valeur_param = params_evt.get("valeur", "1.0") if params_evt else "1.0"
                probabilite_evt = params_evt.get("probabilite", "1.0") if params_evt else "1.0"

                # Si l utilisateur a lie l evenement a une selection, on propage depuis les "objets touches"
                # Dans impacts_evenements, les objets niveau 0 sont deja dedans, mais on veut aussi tenir compte du reseau
                objets_depart = list(impacts.keys())
                propagation = calculer_propagation_reseau(connexion, objets_depart)

                # Appliquer evenement parametrie (Ep)
                appliquer_evenement_parametrique(
                    etat=etat,
                    evenement=evt,
                    impacts=impacts,
                    propagation=propagation,
                    coef_prix=coef_prix,
                    coef_ca=coef_ca,
                    action_param=action_param,
                    valeur_param=valeur_param,
                    probabilite_evt=probabilite_evt
                )

        # 3) enregistrer courbes
        annees.append(annee)

        total_prix = 0.0
        total_ca = 0.0
        for oid, d in etat.items():
            p = _float_robuste(d.get("prix_moyen"), 0.0)
            c = _float_robuste(d.get("ca"), 0.0)
            total_prix += p
            total_ca += c

            details_objets[oid]["prix"].append((annee, round(p, 2)))
            details_objets[oid]["ca"].append((annee, round(c, 2)))

        prix_moyen_total.append(round(total_prix, 2))
        ca_total.append(round(total_ca, 2))

    return {
        "annees": annees,
        "prix_moyen_total": prix_moyen_total,
        "ca_total": ca_total,
        "details_objets": details_objets
    }
