# stats_utils.py

def valeur_valide(valeur):
    """Retourne un float positif ou None"""
    try:
        valeur = float(valeur)
        if valeur <= 0:
            return None
        return valeur
    except:
        return None


def facteur_speculation(speculation):
    mapping = {
        "Très faible": 0.95,
        "Faible": 0.98,
        "Moyenne": 1.00,
        "Forte": 1.08,
        "Hyper Forte": 1.20
    }
    return mapping.get(speculation, 1.00)


def facteur_utilisation(utilisation):
    mapping = {
        "Quotidien +": 0.97,
        "Quotidien": 0.99,
        "Moyen": 1.00,
        "Occasionnelle": 1.05,
        "Rarissime": 1.15
    }
    return mapping.get(utilisation, 1.00)


def calculer_courbe_evolution(
    prix_2000,
    prix_actuel,
    coef_prevision,
    speculation,
    taux_utilisation,
    annee_depart=2000, #initialisation u0
    annee_fin=2035, #arrêt du calcule / rapelle 2025+ = prévision
    pas=5 #+ 5 (ans)
):
    """
    Genere une courbe d'evolution robuste pour tous les objets.
    """

    prix_actuel = valeur_valide(prix_actuel)
    prix_2000 = valeur_valide(prix_2000)

    if prix_actuel is None:
        return []

    nombre_annees = annee_fin - annee_depart
    points = []

    # --- Cas 1 : historique disponible ---
    if prix_2000:
        taux_annuel = (prix_actuel / prix_2000) ** (1 / nombre_annees) - 1

    # --- Cas 2 : reconstruction theorique ---
    else:
        coef_prevision = valeur_valide(coef_prevision) or 1.02
        facteur = facteur_speculation(speculation) * facteur_utilisation(taux_utilisation)
        taux_annuel = coef_prevision * facteur - 1
        prix_2000 = prix_actuel / ((1 + taux_annuel) ** nombre_annees)

    # --- Construction de la courbe ---
    for annee in range(annee_depart, annee_fin + 1, pas):
        n = annee - annee_depart
        prix = prix_2000 * ((1 + taux_annuel) ** n)
        points.append((annee, round(prix, 2)))

    return points
