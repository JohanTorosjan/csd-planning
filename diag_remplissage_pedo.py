# ============================================================
#  diag_remplissage_pedo.py — Analyse du remplissage Pédo
#
#  Pour chaque PÉRIODE et chaque CRÉNEAU pédo, affiche :
#    - le remplissage réel de la salle : nb de 5A / 6A / 4A en Pédo
#      (lu dans planning_csv_pedo)
#    - pour chaque promo, la RAISON de non-présence des absents
#      (lu dans planning_csv_ss : cours, stage, férié, Poly, examen...)
#
#  But : vérifier que le placement correspond à l'intention.
#  Lecture seule.
# ============================================================

import os
import csv
from collections import defaultdict, Counter

import pedo_groupes as pg
from etudiants import ETUDIANTS

DOSSIER_PEDO = "planning_csv_pedo"
DOSSIER_SS = "planning_csv_ss"
VIDE = "—"
CRENEAUX = pg.CRENEAUX
IDX = pg.IDX


def _ordre(s):
    return s if s >= 36 else s + 100


def charger(dossier):
    data = {}
    for nom in os.listdir(dossier):
        if nom.endswith(".csv"):
            with open(os.path.join(dossier, nom), encoding="utf-8") as f:
                cells = {}
                for l in csv.reader(f):
                    if len(l) >= 12 and l[0].isdigit():
                        cells[int(l[0])] = l
                data[nom[:-4]] = cells
    return data


def promo(code):
    return ETUDIANTS.get(code, {}).get("annee")


def est_pedo(cell):
    return cell.startswith("Pédo") or "édo-soin" in cell


def motif_absence(cell):
    """Classe la raison pour laquelle un étudiant n'est PAS en pédo
    sur cette cellule."""
    if cell == VIDE:
        return "libre (dispo mais non placé)"
    if "cours" in cell.lower() or "indispo" in cell.lower():
        # extraire le code motif entre parenthèses si présent
        if "(C)" in cell:
            return "cours (C)"
        if "(F)" in cell:
            return "férié (F)"
        if "(E)" in cell or "(ER)" in cell:
            return "examen"
        return "cours/indispo"
    if cell.startswith("Poly"):
        return "Poly"
    if "sanitaire" in cell.lower():
        return "service sanitaire"
    if cell in ("S", "X", "R"):
        return "stage/absence (6A)"
    return f"autre ({cell[:20]})"


def main():
    pedo = charger(DOSSIER_PEDO)
    ss = charger(DOSSIER_SS)
    P = pg.periodes()

    # tous les codes par promo
    par_promo = defaultdict(list)
    for code, info in ETUDIANTS.items():
        if not info.get("erasmus"):
            par_promo[info["annee"]].append(code)

    for per in (1, 2, 3, 4):
        sems = P[per]
        print("\n" + "=" * 70)
        print(f"  PÉRIODE {per}  (semaines {sems[0]}–{sems[-1]}, {len(sems)} sem.)")
        print("=" * 70)

        for cr in CRENEAUX:
            col = IDX[cr]
            # remplissage pédo : compter les demi-journées-étudiant en pédo
            # sur ce créneau, cette période, par promo (moyenne par semaine)
            presence = defaultdict(lambda: defaultdict(int))  # promo -> sem -> nb
            for code, cells in pedo.items():
                pr = promo(code)
                if pr is None or ETUDIANTS.get(code, {}).get("erasmus"):
                    continue
                for s in sems:
                    if s in cells and est_pedo(cells[s][col]):
                        presence[pr][s] += 1

            # moyenne de présence par semaine (remplissage typique)
            def moy_promo(pr):
                if not presence[pr]:
                    return 0
                return sum(presence[pr].values()) / len(sems)

            n5 = moy_promo(5)
            n6 = moy_promo(6)
            n4 = moy_promo(4)
            total = n5 + n6 + n4

            print(f"\n  {cr[0]:9s} {cr[1]:3s}  |  "
                  f"remplissage moyen/sem : 5A={n5:.1f}  6A={n6:.1f}  "
                  f"4A={n4:.1f}  (total {total:.1f}/20)")

            # pour chaque promo faiblement présente, la raison des absents
            for pr, label in ((5, "5A"), (6, "6A"), (4, "4A")):
                # sur une semaine représentative (milieu de période),
                # pourquoi les non-pédo de cette promo ne sont pas là ?
                sem_ref = sems[len(sems) // 2]
                motifs = Counter()
                for code in par_promo[pr]:
                    cells_p = pedo.get(code, {})
                    cells_s = ss.get(code, {})
                    if sem_ref in cells_p and est_pedo(cells_p[sem_ref][col]):
                        continue  # il est en pédo, pas absent
                    # sinon : pourquoi ?
                    cell_ss = cells_s.get(sem_ref, [""] * 12)
                    motifs[motif_absence(cell_ss[col] if len(cell_ss) > col else "")] += 1
                if motifs:
                    detail = ", ".join(f"{n} {m}" for m, n in motifs.most_common())
                    print(f"       {label} absents (sem {sem_ref}) : {detail}")


if __name__ == "__main__":
    main()