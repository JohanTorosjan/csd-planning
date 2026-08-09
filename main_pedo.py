# ============================================================
#  main_pedo.py — Orchestrateur du pipeline PÉDO-SOIN
#
#  Enchaîne les étapes de génération du planning Pédo :
#     1. pedo_export      (groupes 5A)
#     2. pedo_6a          (placement 6A)
#     3. pedo_4a          (placement 4A, remplissage)
#     4. pedo_remplissage (comble les trous, équité 5A/6A)
#     5. pedo_periode_56  (rattrapage périodes 5-6)
#
#  Chaque étape lit/écrit planning_csv_pedo (et lit planning_csv_ss
#  pour les disponibilités réelles). Le pipeline PÉDO dépend donc du
#  pipeline POLY : planning_csv_ss doit exister au préalable.
#
#  Usage :
#     python3 main_pedo.py            (exécute tout et exporte)
#     python3 main_pedo.py --apercu   (aperçu, n'écrit rien)
# ============================================================

import os
import sys
import time

import pedo_export
import pedo_6a
import pedo_4a
import pedo_remplissage
import pedo_periode_56

DOSSIER_SS = "planning_csv_ss"
DOSSIER_PEDO = "planning_csv_pedo"

# étapes du pipeline : (libellé, module)
ETAPES = [
    ("Groupes 5A (pedo_export)", pedo_export),
    ("Placement 6A (pedo_6a)", pedo_6a),
    ("Placement 4A (pedo_4a)", pedo_4a),
    ("Remplissage des trous (pedo_remplissage)", pedo_remplissage),
    ("Rattrapage périodes 5-6 (pedo_periode_56)", pedo_periode_56),
]


def _titre(txt):
    print("\n" + "=" * 70)
    print(f"  {txt}")
    print("=" * 70)


def _etape(n, total, libelle):
    print(f"\n{'─' * 70}")
    print(f"  ÉTAPE {n}/{total} — {libelle}")
    print(f"{'─' * 70}")


def verifier_prerequis():
    """La Pédo a besoin de planning_csv_ss (sortie du pipeline Poly)."""
    if not os.path.isdir(DOSSIER_SS):
        print(f"\n⚠️  Le dossier '{DOSSIER_SS}' est introuvable.")
        print("   Le pipeline Pédo lit les disponibilités depuis ce dossier,")
        print("   qui est produit par le pipeline Poly (service_sanitaire).")
        print("   Lance d'abord main_poly.py (ou main_global.py).")
        return False
    n = len([f for f in os.listdir(DOSSIER_SS) if f.endswith(".csv")])
    print(f"  Prérequis OK : '{DOSSIER_SS}' contient {n} fichiers CSV.")
    return True


def executer(export=True):
    debut = time.time()
    _titre("PIPELINE PÉDO-SOIN")

    if not verifier_prerequis():
        return False

    mode = "EXPORT (écriture des CSV)" if export else "APERÇU (aucune écriture)"
    print(f"  Mode : {mode}")

    total = len(ETAPES)
    for i, (libelle, module) in enumerate(ETAPES, start=1):
        _etape(i, total, libelle)
        t0 = time.time()
        module.main(export=export)
        print(f"\n  ⏱  Étape terminée en {time.time() - t0:.1f}s")

    duree = time.time() - debut
    _titre(f"PIPELINE PÉDO TERMINÉ en {duree:.1f}s")
    if export:
        n = len([f for f in os.listdir(DOSSIER_PEDO) if f.endswith(".csv")]) \
            if os.path.isdir(DOSSIER_PEDO) else 0
        print(f"  Planning écrit dans '{DOSSIER_PEDO}/' ({n} fichiers).")
        print(f"  Pour vérifier : python3 test_pedo.py")
    else:
        print("  (aperçu — relancer sans --apercu pour écrire les CSV)")
    return True


def main():
    export = "--apercu" not in sys.argv
    executer(export=export)


if __name__ == "__main__":
    main()
