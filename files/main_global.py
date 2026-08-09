# ============================================================
#  main_global.py — Orchestrateur GLOBAL du planning
#
#  Enchaîne les deux pipelines dans l'ordre :
#     1. PIPELINE POLY  (main_poly)  → planning_csv_ss
#     2. PIPELINE PÉDO  (main_pedo)  → planning_csv_pedo
#
#  La Pédo dépend de la Poly (elle lit planning_csv_ss pour les
#  disponibilités réelles), d'où l'ordre imposé.
#
#  Usage :
#     python3 main_global.py
# ============================================================

import time

import main_poly
import main_pedo


def _banniere(txt):
    print("\n" + "█" * 70)
    print(f"  {txt}")
    print("█" * 70)


def main():
    debut = time.time()
    _banniere("GÉNÉRATION COMPLÈTE DU PLANNING (POLY + PÉDO)")

    # 1. Poly
    _banniere("PHASE 1/2 — POLY")
    main_poly.executer()

    # 2. Pédo (dépend de planning_csv_ss produit par la Poly)
    _banniere("PHASE 2/2 — PÉDO")
    ok = main_pedo.executer(export=True)
    if not ok:
        _banniere("ARRÊT : prérequis Pédo manquants")
        return

    duree = time.time() - debut
    _banniere(f"PLANNING COMPLET GÉNÉRÉ en {duree:.1f}s")
    print("  Poly : planning_csv_ss/")
    print("  Pédo : planning_csv_pedo/")
    print("  Vérifications : python3 test_poly.py  et  python3 test_pedo.py")


if __name__ == "__main__":
    main()
