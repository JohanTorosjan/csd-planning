# ============================================================
#  test_urgences.py — Vérification et exploration des urgences
#
#  Quatre volets :
#   1) EXEMPLES INDIVIDUELS : pour chaque promo, 2 étudiants tirés au
#      hasard par type, avec leur parcours d'urgences dans l'année
#      (nombre, répartition semaine par semaine, écart moyen).
#   2) ÉQUITÉ PAR PROMO : distribution du nombre de vacations, min/max,
#      moyenne, écart-type ; étalement (écart moyen entre vacations).
#   3) REMPLISSAGE DES SALLES : nb de vacations couvertes, complétude
#      (toujours 10 étudiants ?), vacations par semaine.
#   4) COMPOSITIONS : combien de chaque type (6/4, 5, 6/5/4, …).
#
#  Lecture seule : lit planning_csv_urgences.
#
#  Usage : python3 test_urgences.py
#          python3 test_urgences.py --seed 42
# ============================================================

import os
import csv
import sys
import random
import statistics
from collections import defaultdict, Counter

from etudiants import ETUDIANTS

import pedo_groupes as pg

DOSSIER = "planning_csv_urgences"
COLONNES = pg.COLONNES
IDX = pg.IDX

try:
    from etudiants import NOMS
except Exception:
    NOMS = {}


def _ordre(s):
    return s if s >= 36 else s + 100


JOUR_OFFSET = {"lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3,
               "vendredi": 4, "samedi": 5, "dimanche": 6}


def instant(sem, col):
    jour, moment = col
    base = _ordre(sem) * 14
    base += JOUR_OFFSET.get(jour, 0) * 2
    base += 1 if moment == "AM" else 0
    return base


def est_urgence(cell):
    return "Urgences" in cell


def compo_de(cell):
    """'Urgences (6/4)' -> '6/4'."""
    if "(" in cell and ")" in cell:
        return cell[cell.index("(") + 1:cell.index(")")]
    return ""


# ============================================================
#  Chargement
# ============================================================

def charger():
    """{code: {sem: ligne}} + liste des vacations d'urgences par étudiant."""
    data = {}
    urgences = defaultdict(list)          # code -> [(sem, col)]
    for nom in os.listdir(DOSSIER):
        if not nom.endswith(".csv"):
            continue
        code = nom[:-4]
        info = ETUDIANTS.get(code, {})
        if info.get("erasmus") or info.get("annee") not in (4, 5, 6):
            continue
        lignes = {}
        with open(os.path.join(DOSSIER, nom), encoding="utf-8") as f:
            for l in csv.reader(f):
                if len(l) >= 12 and l[0].isdigit():
                    sem = int(l[0])
                    lignes[sem] = l
                    for col in COLONNES:
                        if est_urgence(l[IDX[col]]):
                            urgences[code].append((sem, col))
        data[code] = lignes
    return data, urgences


# ============================================================
#  Volet 1 : exemples individuels
# ============================================================

def ecart_moyen(places):
    if len(places) < 2:
        return None
    insts = sorted(instant(s, c) for s, c in places)
    return statistics.mean((insts[k] - insts[k - 1]) / 14
                           for k in range(1, len(insts)))


def exemples_individuels(urgences, rng):
    print("=" * 70)
    print("  VOLET 1 — EXEMPLES INDIVIDUELS (parcours d'urgences)")
    print("=" * 70)

    par_at = defaultdict(list)
    for code, info in ETUDIANTS.items():
        if info.get("erasmus"):
            continue
        a = info.get("annee")
        t = info.get("type")
        if a in (4, 5, 6):
            par_at[(a, t)].append(code)

    for annee in (4, 5, 6):
        print(f"\n{'─' * 70}")
        print(f"  PROMO {annee}A")
        print(f"{'─' * 70}")
        types = sorted(t for (a, t) in par_at if a == annee)
        for t in types:
            codes = par_at[(annee, t)]
            for code in rng.sample(codes, min(2, len(codes))):
                places = sorted(urgences.get(code, []),
                                key=lambda x: instant(x[0], x[1]))
                nom = NOMS.get(code, "")
                em = ecart_moyen(places)
                em_str = f", écart moyen {em:.1f} sem" if em else ""
                print(f"\n  ● {code} (type {t}{', ' + nom if nom else ''}) "
                      f"— {len(places)} vacations{em_str}")
                if not places:
                    print("      (aucune urgence)")
                    continue
                ligne = [f"s{sem}{col[0][:3]}{col[1]}" for sem, col in places]
                for k in range(0, len(ligne), 8):
                    print("      " + "  ".join(ligne[k:k + 8]))


# ============================================================
#  Volet 2 : équité par promo
# ============================================================

def equite_par_promo(urgences):
    print("\n" + "=" * 70)
    print("  VOLET 2 — ÉQUITÉ ET ÉTALEMENT PAR PROMO")
    print("=" * 70)

    for annee in (4, 5, 6):
        codes = [c for c, i in ETUDIANTS.items()
                 if i.get("annee") == annee and not i.get("erasmus")]
        vals = [len(urgences.get(c, [])) for c in codes]
        if not vals:
            continue
        print(f"\n  {annee}A ({len(vals)} étudiants) :")
        print(f"     vacations/étudiant : min={min(vals)}, max={max(vals)}, "
              f"moy={statistics.mean(vals):.1f}, σ={statistics.pstdev(vals):.2f}")
        # distribution
        dist = Counter(vals)
        detail = "  ".join(f"{n}:{dist[n]}" for n in sorted(dist))
        print(f"     distribution (nb vac : nb étud.) : {detail}")
        # étalement
        ecarts = [ecart_moyen(urgences.get(c, [])) for c in codes]
        ecarts = [e for e in ecarts if e is not None]
        if ecarts:
            print(f"     étalement (écart moyen entre 2 vac.) : "
                  f"{statistics.mean(ecarts):.1f} sem "
                  f"(min {min(ecarts):.1f}, max {max(ecarts):.1f})")


# ============================================================
#  Volet 3 : remplissage des salles
# ============================================================

def remplissage(data, urgences):
    print("\n" + "=" * 70)
    print("  VOLET 3 — REMPLISSAGE DES SALLES")
    print("=" * 70)

    # compter les étudiants par vacation
    par_vacation = defaultdict(lambda: {4: 0, 5: 0, 6: 0})
    for code, places in urgences.items():
        a = ETUDIANTS[code]["annee"]
        for sem, col in places:
            par_vacation[(sem, col)][a] += 1

    totaux = [sum(v.values()) for v in par_vacation.values()]
    print(f"\n  Vacations d'urgences couvertes : {len(par_vacation)}")
    if totaux:
        pleines = sum(1 for t in totaux if t == 10)
        print(f"     complètes (10 étudiants) : {pleines} "
              f"({100 * pleines / len(totaux):.0f} %)")
        incompletes = [t for t in totaux if t != 10]
        if incompletes:
            print(f"     incomplètes : {len(incompletes)} "
                  f"(tailles {sorted(set(incompletes))})")
        print(f"     total places pourvues : {sum(totaux)}")

    # nombre de vacations par semaine
    par_sem = defaultdict(int)
    for (sem, col) in par_vacation:
        par_sem[sem] += 1
    sems = sorted(par_sem, key=_ordre)
    print(f"\n  Vacations couvertes par semaine :")
    for k in range(0, len(sems), 9):
        bloc = sems[k:k + 9]
        print("     " + "  ".join(f"s{s}:{par_sem[s]}" for s in bloc))


# ============================================================
#  Volet 4 : compositions
# ============================================================

def compositions(data):
    print("\n" + "=" * 70)
    print("  VOLET 4 — COMPOSITIONS DES VACATIONS")
    print("=" * 70)

    # une vacation = (sem, col) ; on lit la compo depuis n'importe quelle
    # cellule urgence de cette vacation
    vues = {}
    for code, lignes in data.items():
        for sem, l in lignes.items():
            for col in COLONNES:
                if est_urgence(l[IDX[col]]):
                    vues[(sem, col)] = compo_de(l[IDX[col]])

    compo_count = Counter(vues.values())
    total = sum(compo_count.values())
    print(f"\n  {total} vacations, répartition des compositions :\n")
    for lib, n in compo_count.most_common():
        barre = "█" * round(30 * n / total)
        print(f"     {lib:8s} : {n:4d} ({100 * n / total:4.1f} %) {barre}")


def main():
    seed = None
    if "--seed" in sys.argv:
        i = sys.argv.index("--seed")
        if i + 1 < len(sys.argv):
            seed = int(sys.argv[i + 1])
    rng = random.Random(seed)

    if not os.path.isdir(DOSSIER):
        print(f"⚠️  Dossier '{DOSSIER}' introuvable. "
              f"Lance d'abord : python3 urgences.py --export")
        return

    data, urgences = charger()

    exemples_individuels(urgences, rng)
    equite_par_promo(urgences)
    remplissage(data, urgences)
    compositions(data)


if __name__ == "__main__":
    main()