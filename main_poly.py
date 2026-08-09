# ============================================================
#  main_poly.py — Orchestrateur du pipeline POLY
#
#  Enchaîne les étapes de génération du planning Poly :
#     1. main            (planning salle + capacité + équité + export)
#                          → planning_csv
#     2. examens         → planning_csv_examens
#     3. restantes       → planning_csv_restantes
#     4. finalisation    → planning_csv_final
#     5. service_sanitaire → planning_csv_ss
#
#  Chaque étape lit le dossier produit par la précédente et écrit le
#  sien (dossiers intermédiaires conservés pour la traçabilité).
#  La sortie finale, planning_csv_ss, est l'entrée du pipeline Pédo.
#
#  Usage :
#     python3 main_poly.py
# ============================================================

import os
import sys
import time

import main as poly_main
import examens
import restantes
import finalisation
import service_sanitaire

DOSSIER_FINAL = "planning_csv_ss"


def _titre(txt):
    print("\n" + "=" * 70)
    print(f"  {txt}")
    print("=" * 70)


def _etape(n, total, libelle, dossier_sortie):
    print(f"\n{'─' * 70}")
    print(f"  ÉTAPE {n}/{total} — {libelle}")
    print(f"     → produit : {dossier_sortie}/")
    print(f"{'─' * 70}")


def _compter(dossier):
    if os.path.isdir(dossier):
        return len([f for f in os.listdir(dossier) if f.endswith(".csv")])
    return 0


def executer():
    debut = time.time()
    _titre("PIPELINE POLY")

    total = 5

    # ── 1. Planning salle de base ───────────────────────────
    _etape(1, total, "Planning salle (main)", "planning_csv")
    t0 = time.time()
    poly_main.main()
    print(f"\n  ⏱  {time.time() - t0:.1f}s — planning_csv : "
          f"{_compter('planning_csv')} fichiers")

    # ── 2. Examens ──────────────────────────────────────────
    _etape(2, total, "Examens (examens)", "planning_csv_examens")
    t0 = time.time()
    examens.traiter_examens(inplace=False)
    print(f"\n  ⏱  {time.time() - t0:.1f}s — planning_csv_examens : "
          f"{_compter('planning_csv_examens')} fichiers")

    # ── 3. Vacations restantes ──────────────────────────────
    _etape(3, total, "Vacations restantes (restantes)", "planning_csv_restantes")
    t0 = time.time()
    restantes.traiter_restantes(inplace=False)
    print(f"\n  ⏱  {time.time() - t0:.1f}s — planning_csv_restantes : "
          f"{_compter('planning_csv_restantes')} fichiers")

    # ── 4. Finalisation ─────────────────────────────────────
    _etape(4, total, "Finalisation (finalisation)", "planning_csv_final")
    t0 = time.time()
    finalisation.finaliser_tout()
    print(f"\n  ⏱  {time.time() - t0:.1f}s — planning_csv_final : "
          f"{_compter('planning_csv_final')} fichiers")

    # ── 5. Service sanitaire ────────────────────────────────
    _etape(5, total, "Service sanitaire (service_sanitaire)", "planning_csv_ss")
    t0 = time.time()
    groupes = service_sanitaire.construire()
    service_sanitaire.exporter(groupes)
    print(f"\n  ⏱  {time.time() - t0:.1f}s — planning_csv_ss : "
          f"{_compter('planning_csv_ss')} fichiers")

    duree = time.time() - debut
    _titre(f"PIPELINE POLY TERMINÉ en {duree:.1f}s")
    print(f"  Sortie finale : '{DOSSIER_FINAL}/' "
          f"({_compter(DOSSIER_FINAL)} fichiers)")
    print(f"  C'est l'entrée du pipeline Pédo (main_pedo.py).")
    print(f"  Pour vérifier : python3 test_poly.py")


def main():
    executer()


if __name__ == "__main__":
    main()
