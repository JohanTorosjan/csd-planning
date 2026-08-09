# ============================================================
#  test_occluso.py — Vérification et exploration de l'occluso
#
#  Quatre volets :
#   1) EXEMPLES INDIVIDUELS : quelques 4A (2 par type), leur parcours
#      occluso dans l'année (semaines, créneaux, écart moyen).
#   2) ÉQUITÉ ET ÉTALEMENT : distribution du nombre de vacations,
#      min/max/σ, minimum garanti, bonus P1, étalement.
#   3) REMPLISSAGE DES SALLES : pour chaque semaine et chaque créneau,
#      combien de vacations, leur complétude (4 places), les creux.
#   4) INTÉGRITÉ : vacations pleines, 4A only, créneaux/dates respectés.
#
#  Lecture seule : lit planning_csv_occluso.
#
#  Usage : python3 test_occluso.py
#          python3 test_occluso.py --seed 42
# ============================================================

import os
import csv
import sys
import random
import statistics
from collections import defaultdict, Counter

from etudiants import ETUDIANTS

import pedo_groupes as pg

DOSSIER = "planning_csv_occluso"
IDX = pg.IDX

CRENEAUX_OCC = [("lundi", "M"), ("mardi", "M"),
                ("jeudi", "M"), ("vendredi", "M")]
PLACES = 4
SEMAINE_FIN = 22
MINIMUM = 3

try:
    from etudiants import NOMS
except Exception:
    NOMS = {}

_SEQUENCE = list(range(36, 53)) + list(range(1, 36))
_POSITION = {s: i for i, s in enumerate(_SEQUENCE)}


def _ordre(s):
    return s if s >= 36 else s + 100


def instant_sem(sem):
    return _POSITION.get(sem, _ordre(sem))


def est_occluso(cell):
    return "Occluso" in cell


# ============================================================
#  Chargement
# ============================================================

def charger():
    """{code: {sem: ligne}} + occluso par étudiant {code: [(sem, cr)]}."""
    data = {}
    occ = defaultdict(list)
    for nom in os.listdir(DOSSIER):
        if not nom.endswith(".csv"):
            continue
        code = nom[:-4]
        lignes = {}
        with open(os.path.join(DOSSIER, nom), encoding="utf-8") as f:
            for l in csv.reader(f):
                if len(l) >= 12 and l[0].isdigit():
                    sem = int(l[0])
                    lignes[sem] = l
                    for cr in CRENEAUX_OCC:
                        if est_occluso(l[IDX[cr]]):
                            occ[code].append((sem, cr))
        data[code] = lignes
    return data, occ


# ============================================================
#  Volet 1 : exemples individuels
# ============================================================

def ecart_moyen(places):
    if len(places) < 2:
        return None
    pos = sorted(instant_sem(s) for s, _ in places)
    return statistics.mean(pos[k] - pos[k - 1] for k in range(1, len(pos)))


def exemples(occ, rng):
    print("=" * 70)
    print("  VOLET 1 — EXEMPLES INDIVIDUELS (parcours occluso)")
    print("=" * 70)

    par_type = defaultdict(list)
    for code, info in ETUDIANTS.items():
        if info.get("annee") == 4 and not info.get("erasmus"):
            par_type[info.get("type")].append(code)

    for t in sorted(par_type):
        print(f"\n  ── Type {t} ──")
        for code in rng.sample(par_type[t], min(2, len(par_type[t]))):
            places = sorted(occ.get(code, []), key=lambda x: instant_sem(x[0]))
            nom = NOMS.get(code, "")
            em = ecart_moyen(places)
            em_str = f", écart moyen {em:.1f} sem" if em else ""
            ligne = "  ".join(f"s{sem}{cr[0][:3]}" for sem, cr in places)
            print(f"     {code} ({nom or '?'}) — {len(places)} vac.{em_str}")
            print(f"        {ligne}")


# ============================================================
#  Volet 2 : équité et étalement
# ============================================================

def equite(occ):
    print("\n" + "=" * 70)
    print("  VOLET 2 — ÉQUITÉ ET ÉTALEMENT")
    print("=" * 70)

    codes4 = [c for c, i in ETUDIANTS.items()
              if i.get("annee") == 4 and not i.get("erasmus")]
    vals = [len(occ.get(c, [])) for c in codes4]

    print(f"\n  4A ({len(vals)} étudiants) :")
    print(f"     vacations/étudiant : min={min(vals)}, max={max(vals)}, "
          f"moy={statistics.mean(vals):.1f}, σ={statistics.pstdev(vals):.2f}")
    dist = Counter(vals)
    print(f"     distribution : "
          + "  ".join(f"{n}:{dist[n]}" for n in sorted(dist)))
    sous = sum(1 for v in vals if v < MINIMUM)
    print(f"     sous le minimum ({MINIMUM}) : {sous}")

    # bonus P1
    try:
        P1 = set(pg.periodes()[1])
    except Exception:
        P1 = set(range(36, 45))
    en_p1 = sum(1 for c in codes4
                if any(s in P1 for s, _ in occ.get(c, [])))
    print(f"\n  Bonus : 4A avec ≥1 vacation en P1 : {en_p1}/{len(codes4)}")

    # étalement
    ecarts = []
    for c in codes4:
        e = ecart_moyen(occ.get(c, []))
        if e is not None:
            ecarts.append(e)
    if ecarts:
        print(f"\n  Étalement (écart moyen entre 2 vacations d'un étudiant) : "
              f"{statistics.mean(ecarts):.1f} sem")


# ============================================================
#  Volet 3 : remplissage des salles (focus)
# ============================================================

def remplissage(data, occ):
    print("\n" + "=" * 70)
    print("  VOLET 3 — REMPLISSAGE DES SALLES")
    print("=" * 70)

    # compter les étudiants par vacation
    par_vac = defaultdict(int)
    for code, places in occ.items():
        for v in places:
            par_vac[v] += 1

    vals = list(par_vac.values())
    pleines = sum(1 for v in vals if v == PLACES)
    print(f"\n  Vacations occluso : {len(par_vac)}")
    print(f"     pleines ({PLACES} places) : {pleines} "
          f"({100 * pleines / max(1, len(par_vac)):.0f} %)")
    incompletes = [v for v in vals if v != PLACES]
    if incompletes:
        print(f"     incomplètes : {len(incompletes)} "
              f"(tailles {sorted(Counter(incompletes).items())})")
    print(f"     total places pourvues : {sum(vals)}")

    # détail par semaine × créneau (grille de remplissage)
    sems = sorted({s for (s, cr) in par_vac}, key=_ordre)
    print(f"\n  Grille de remplissage (nb d'étudiants par vacation) :")
    print(f"     {'sem':>4}  " + "  ".join(cr[0][:3] for cr in CRENEAUX_OCC))
    for sem in sems:
        cells = []
        for cr in CRENEAUX_OCC:
            n = par_vac.get((sem, cr), None)
            if n is None:
                cells.append("  ·")       # pas de vacation (4A en cours/fermé)
            else:
                marque = "" if n == PLACES else "!"
                cells.append(f"{n:3d}{marque}")
        print(f"     s{sem:>3}  " + "  ".join(cells))

    # combien de créneaux possibles non utilisés (4A tous en cours)
    total_creneaux = len(sems) * len(CRENEAUX_OCC)
    utilises = len(par_vac)
    print(f"\n  Créneaux occluso : {utilises} utilisés sur "
          f"{total_creneaux} possibles (le reste = 4A en cours/fermé)")


# ============================================================
#  Volet 4 : intégrité
# ============================================================

def integrite(data, occ):
    print("\n" + "=" * 70)
    print("  VOLET 4 — INTÉGRITÉ")
    print("=" * 70)

    par_vac = defaultdict(list)
    non_4a = 0
    hors_creneau = 0
    apres_fin = 0
    for code, places in occ.items():
        a = ETUDIANTS.get(code, {}).get("annee")
        for sem, cr in places:
            par_vac[(sem, cr)].append(code)
            if a != 4:
                non_4a += 1
            if cr not in CRENEAUX_OCC:
                hors_creneau += 1
            if _ordre(sem) > _ordre(SEMAINE_FIN):
                apres_fin += 1

    pas_4 = {k: len(v) for k, v in par_vac.items() if len(v) != PLACES}
    codes4 = [c for c, i in ETUDIANTS.items()
              if i.get("annee") == 4 and not i.get("erasmus")]
    sous = [c for c in codes4 if len(occ.get(c, [])) < MINIMUM]

    print(f"\n  Vacations non pleines : {len(pas_4)}")
    print(f"  Occluso sur non-4A : {non_4a}")
    print(f"  Occluso hors créneaux : {hors_creneau}")
    print(f"  Occluso après la date de fin (s{SEMAINE_FIN}) : {apres_fin}")
    print(f"  4A sous le minimum ({MINIMUM}) : {len(sous)}")

    ok = (not pas_4 and not non_4a and not hors_creneau
          and not apres_fin and not sous)
    print(f"\n  → {'✅ TOUT OK' if ok else '⚠️  VOIR CI-DESSUS'}")


def main():
    seed = None
    if "--seed" in sys.argv:
        i = sys.argv.index("--seed")
        if i + 1 < len(sys.argv):
            seed = int(sys.argv[i + 1])
    rng = random.Random(seed)

    if not os.path.isdir(DOSSIER):
        print(f"⚠️  Dossier '{DOSSIER}' introuvable. "
              f"Lance d'abord : python3 occluso.py --export")
        return

    data, occ = charger()
    exemples(occ, rng)
    equite(occ)
    remplissage(data, occ)
    integrite(data, occ)


if __name__ == "__main__":
    main()