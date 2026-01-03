# sim_calc.py
# Simulation deterministe par calcul
# ASCII only

import sqlite3
import math

# ---------------------------------
# Helpers
# ---------------------------------
def is_number(v):
    return isinstance(v, (int, float))

def safe_float(v):
    if isinstance(v, (int, float)):
        return float(v)
    return None

def approx_min_max(mean):
    # fallback if min/max missing
    return mean * 0.85, mean * 1.15

# ---------------------------------
# Core simulation
# ---------------------------------
def run_simulation_calc(db_path, basket, years=10):
    """
    db_path : path to universe_<uid>.db
    basket  : dict { rowid: qty }
    years   : projection horizon (int)

    return dict (standardized result)
    """

    result = {
        "type": "CALC",
        "years": years,
        "total": {
            "mean": 0.0,
            "min": 0.0,
            "max": 0.0
        },
        "projection": {
            "mean": 0.0,
            "min": 0.0,
            "max": 0.0
        },
        "details": [],
        "warnings": []
    }

    if not basket:
        result["warnings"].append("Panier vide")
        return result

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Fetch columns
    cur.execute("PRAGMA table_info(stat_objects)")
    cols_info = cur.fetchall()
    columns = [c[1] for c in cols_info]

    # Column detection
    def find_col(keys):
        for c in columns:
            cl = c.lower()
            for k in keys:
                if k in cl:
                    return c
        return None

    name_col = find_col(["objet", "nom", "name", "designation"])
    mean_col = find_col(["prix_moyen", "mean"])
    min_col  = find_col(["prix_min", "min"])
    max_col  = find_col(["prix_max", "max"])
    coef_col = find_col(["coef", "augmentation", "evol"])

    # Iterate basket
    for rowid, qty in basket.items():
        try:
            cur.execute(
                "SELECT * FROM stat_objects WHERE rowid = ?",
                (rowid,)
            )
            row = cur.fetchone()
        except Exception:
            continue

        if not row:
            result["warnings"].append(f"Objet {rowid} introuvable")
            continue

        data = dict(zip(columns, row))

        name = data.get(name_col, f"Objet {rowid}")
        qty = int(qty)

        mean = safe_float(data.get(mean_col)) if mean_col else None
        vmin = safe_float(data.get(min_col)) if min_col else None
        vmax = safe_float(data.get(max_col)) if max_col else None
        coef = safe_float(data.get(coef_col)) if coef_col else 1.0

        detail = {
            "rowid": rowid,
            "name": name,
            "qty": qty,
            "status": "OK"
        }

        # Price validation
        if mean is None:
            detail["status"] = "UNKNOWN"
            result["warnings"].append(f"{name} : prix moyen inconnu")
            result["details"].append(detail)
            continue

        # Min / Max fallback
        if vmin is None or vmax is None:
            vmin, vmax = approx_min_max(mean)

        # Totals (current)
        result["total"]["mean"] += qty * mean
        result["total"]["min"]  += qty * vmin
        result["total"]["max"]  += qty * vmax

        # Projection
        coef = coef if coef and coef > 0 else 1.0
        proj_factor = math.pow(coef, years)

        result["projection"]["mean"] += qty * mean * proj_factor
        result["projection"]["min"]  += qty * vmin  * proj_factor
        result["projection"]["max"]  += qty * vmax  * proj_factor

        # Detail enrichment
        detail.update({
            "mean": mean,
            "min": vmin,
            "max": vmax,
            "coef": coef
        })

        result["details"].append(detail)

    conn.close()

    return result


# ---------------------------------
# Standalone test (optional)
# ---------------------------------
if __name__ == "__main__":
    # Example manual test
    db = "universe_test.db"
    basket = {
        1: 10,
        3: 5,
        7: 2
    }
    res = run_simulation_calc(db, basket, years=10)
    from pprint import pprint
    pprint(res)


