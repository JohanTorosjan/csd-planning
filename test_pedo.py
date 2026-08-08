# ============================================================
#  test_pedo.py — Vérification et exploration du planning Pédo
#
#  Deux volets :
#   1) EXEMPLES INDIVIDUELS : pour chaque promo, 2 étudiants tirés au
#      hasard par type, avec leur parcours Pédo complet dans l'année
#      (semaines, créneaux, groupes, nombre de séances).
#   2) COMPOSITION DES SALLES : pour chaque période et chaque créneau,
#      la composition des groupes qui l'occupent, la capacité utilisée,
#      et des statistiques (remplissage, équité par promo).
#
#  Lecture seule : n'écrit rien, lit planning_csv_pedo.
#
#  Usage : python3 test_pedo.py
#          python3 test_pedo.py --seed 42   (tirage reproductible)
# ============================================================

import os
import csv
import sys
import random
import statistics
from collections import defaultdict

from etudiants import ETUDIANTS

import pedo_groupes as pg

DOSSIER_PEDO = "planning_csv_pedo"
VIDE = "—"
CAPACITE = 20

CRENEAUX = pg.CRENEAUX
IDX = pg.IDX

# noms (optionnels)
try:
    from etudiants import NOMS
except Exception:
    NOMS = {}


def _ordre(s):
    return s if s >= 36 else s + 100


def periode_de(sem, P):
    for per, sems in P.items():
        if sem in sems:
            return per
    return None


def est_pedo(cell):
    return "édo" in cell


def nom_groupe(cell):
    """Extrait le nom de groupe entre parenthèses, + flag remplissage."""
    nom = cell
    if "(" in cell and ")" in cell:
        nom = cell[cell.index("(") + 1:cell.index(")")]
    flag = " [rempl.]" if "remplissage" in cell else ""
    return nom + flag


# ============================================================
#  Chargement
# ============================================================

def charger():
    data = {}
    for nom in os.listdir(DOSSIER_PEDO):
        if nom.endswith(".csv"):
            with open(os.path.join(DOSSIER_PEDO, nom), encoding="utf-8") as f:
                data[nom[:-4]] = [list(l) for l in csv.reader(f)]
    return data


# ============================================================
#  Volet 1 : exemples individuels
# ============================================================

def parcours_pedo(code, data, P):
    """Liste des séances Pédo d'un étudiant : (semaine, période, créneau, groupe)."""
    lignes = data.get(code, [])
    seances = []
    for l in lignes:
        if len(l) >= 12 and l[0].isdigit():
            sem = int(l[0])
            for cr in CRENEAUX:
                cell = l[IDX[cr]]
                if est_pedo(cell):
                    seances.append((sem, periode_de(sem, P), cr, nom_groupe(cell)))
    seances.sort(key=lambda x: _ordre(x[0]))
    return seances


def exemples_individuels(data, P, rng):
    print("=" * 70)
    print("  VOLET 1 — EXEMPLES INDIVIDUELS (parcours Pédo dans l'année)")
    print("=" * 70)

    # regrouper les codes par (année, type)
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
            echantillon = rng.sample(codes, min(2, len(codes)))
            for code in echantillon:
                nom = NOMS.get(code, "")
                seances = parcours_pedo(code, data, P)
                print(f"\n  ● {code} (type {t}{', ' + nom if nom else ''}) "
                      f"— {len(seances)} séances Pédo")
                if not seances:
                    print("      (aucune séance Pédo)")
                    continue
                # regrouper par période
                par_per = defaultdict(list)
                for sem, per, cr, grp in seances:
                    par_per[per].append((sem, cr, grp))
                for per in sorted(k for k in par_per if k is not None):
                    items = par_per[per]
                    # créneaux/groupes distincts dans la période
                    groupes_per = sorted(set(g for _, _, g in items))
                    sems = sorted(set(s for s, _, _ in items), key=_ordre)
                    print(f"      P{per} ({len(items)} séances) : "
                          f"{', '.join(groupes_per)}")
                    # détail semaines -> créneau
                    detail = "  ".join(
                        f"s{sem}:{cr[0][:3]}{cr[1]}" for sem, cr, _ in
                        sorted(items, key=lambda x: _ordre(x[0])))
                    print(f"         {detail}")


# ============================================================
#  Volet 2 : composition des salles
# ============================================================

def composition_salles(data, P):
    print("\n" + "=" * 70)
    print("  VOLET 2 — COMPOSITION DES SALLES (par période et créneau)")
    print("=" * 70)

    # occupation[(per, cr, sem)] = {promo: nb, groupes: Counter}
    # on parcourt tout le monde
    annee_de = {c: ETUDIANTS[c].get("annee") for c in ETUDIANTS}

    # pour chaque (période, créneau) : par semaine, composition
    occ = defaultdict(lambda: defaultdict(lambda: {4: 0, 5: 0, 6: 0}))
    groupes_occ = defaultdict(lambda: defaultdict(int))  # (per,cr) -> nom -> nb séances
    for code, lignes in data.items():
        info = ETUDIANTS.get(code, {})
        if info.get("erasmus"):
            continue
        a = info.get("annee")
        if a not in (4, 5, 6):
            continue
        for l in lignes:
            if len(l) >= 12 and l[0].isdigit():
                sem = int(l[0])
                per = periode_de(sem, P)
                if per is None:
                    continue
                for cr in CRENEAUX:
                    cell = l[IDX[cr]]
                    if est_pedo(cell):
                        occ[(per, cr)][sem][a] += 1
                        groupes_occ[(per, cr)][nom_groupe(cell)] += 1

    for per in sorted(P):
        sems = P[per]
        used = [(cr) for cr in CRENEAUX if (per, cr) in occ]
        if not used:
            continue
        print(f"\n{'─' * 70}")
        print(f"  PÉRIODE {per}  (semaines {sems[0]}–{sems[-1]}, {len(sems)} sem.)")
        print(f"{'─' * 70}")
        for cr in CRENEAUX:
            key = (per, cr)
            if key not in occ:
                continue
            parsem = occ[key]
            # moyennes de remplissage sur les semaines actives
            actives = [s for s in sems if s in parsem]
            if not actives:
                continue
            tot_par_sem = [sum(parsem[s].values()) for s in actives]
            moy4 = statistics.mean(parsem[s][4] for s in actives)
            moy5 = statistics.mean(parsem[s][5] for s in actives)
            moy6 = statistics.mean(parsem[s][6] for s in actives)
            moy_tot = statistics.mean(tot_par_sem)
            mn, mx = min(tot_par_sem), max(tot_par_sem)
            # groupes qui occupent ce créneau
            grps = groupes_occ[key]
            grp_str = ", ".join(f"{g}({n})" for g, n in
                                sorted(grps.items(), key=lambda x: -x[1]))
            print(f"\n  {cr[0]:9s} {cr[1]:3s} — {len(actives)} semaines actives")
            print(f"     remplissage moyen : 5A={moy5:.1f} 6A={moy6:.1f} "
                  f"4A={moy4:.1f}  total {moy_tot:.1f}/{CAPACITE} "
                  f"(min {mn}, max {mx})")
            print(f"     groupes (séances) : {grp_str}")


# ============================================================
#  Stats globales
# ============================================================

def stats_globales(data, P):
    print("\n" + "=" * 70)
    print("  STATISTIQUES GLOBALES")
    print("=" * 70)

    seances = defaultdict(int)
    for code, lignes in data.items():
        info = ETUDIANTS.get(code, {})
        if info.get("erasmus"):
            continue
        for l in lignes:
            if len(l) >= 12 and l[0].isdigit():
                for cr in CRENEAUX:
                    if est_pedo(l[IDX[cr]]):
                        seances[code] += 1

    for annee in (4, 5, 6):
        codes = [c for c, i in ETUDIANTS.items()
                 if i.get("annee") == annee and not i.get("erasmus")]
        vals = [seances.get(c, 0) for c in codes]
        if not vals:
            continue
        print(f"\n  {annee}A ({len(vals)} étudiants) :")
        print(f"     séances Pédo/an : min={min(vals)}, max={max(vals)}, "
              f"moy={statistics.mean(vals):.1f}, "
              f"méd={statistics.median(vals):.0f}, "
              f"σ={statistics.pstdev(vals):.2f}")

    # remplissage global : créneaux-semaines pleins
    occ = defaultdict(int)
    utilise = set()
    for code, lignes in data.items():
        info = ETUDIANTS.get(code, {})
        if info.get("erasmus"):
            continue
        for l in lignes:
            if len(l) >= 12 and l[0].isdigit():
                sem = int(l[0])
                for cr in CRENEAUX:
                    if est_pedo(l[IDX[cr]]):
                        occ[(sem, cr)] += 1
                        utilise.add((sem, cr))
    pleins = sum(1 for k in utilise if occ[k] >= CAPACITE)
    vides = sum(CAPACITE - occ[k] for k in utilise if occ[k] < CAPACITE)
    total_seances = sum(occ.values())
    print(f"\n  Remplissage salle :")
    print(f"     créneaux-semaines utilisés : {len(utilise)}")
    print(f"     pleins (20/20) : {pleins} "
          f"({100 * pleins / max(1, len(utilise)):.0f} %)")
    print(f"     places vides restantes : {vides}")
    print(f"     total séances Pédo placées : {total_seances}")


def main():
    seed = None
    if "--seed" in sys.argv:
        i = sys.argv.index("--seed")
        if i + 1 < len(sys.argv):
            seed = int(sys.argv[i + 1])
    rng = random.Random(seed)

    data = charger()
    P = pg.periodes()

    exemples_individuels(data, P, rng)
    composition_salles(data, P)
    stats_globales(data, P)


if __name__ == "__main__":
    main()