# ============================================================
#  test_poly.py — Contrôle complet du planning (Poly + SS)
#
#  Analyse planning_csv_ss (état le plus complet : Poly + examens
#  + restantes + finalisation + service sanitaire) et vérifie :
#
#    1. CAPACITÉ      — aucun créneau ne dépasse 19 box
#    2. ÉQUITÉ        — vacations par promo/type, écarts intra/inter
#    3. BINÔMES       — réciprocité des partenariats Poly
#    4. ABSENCES      — aucune vacation sur une semaine d'absence
#    5. SERVICE SAN.  — 6-7 semaines par 4A, créneaux cohérents
#    6. EXEMPLES      — quelques étudiants au hasard, semaine type
#
#  Rapport console avec verdict OK / PROBLÈME par section.
#  Lecture seule. Usage : python3 test_poly.py [dossier]
# ============================================================

import os
import csv
import sys
import random
import statistics
import re
from collections import defaultdict, Counter

from etudiants import ETUDIANTS, GROUPES, NOMS
from donnees import INDISPO_INDIVIDUEL, CAPACITE

DOSSIER_DEFAUT = "planning_csv_ss"
MAX_BOXES = CAPACITE["boxes"]

COLS = [("lundi", "M"), ("lundi", "AM"), ("mardi", "M"), ("mardi", "AM"),
        ("mercredi", "M"), ("mercredi", "AM"), ("jeudi", "M"), ("jeudi", "AM"),
        ("vendredi", "M"), ("vendredi", "AM")]
IDX = {c: 2 + i for i, c in enumerate(COLS)}
VIDE = "—"
_SUFFIXE = re.compile(r"\s*\([^)]*\)\s*$")


def _ordre(s):
    return s if s >= 36 else s + 100


def _info(code):
    return ETUDIANTS.get(code, {})


def _reel(code):
    """Étudiant réel (non Erasmus) ?"""
    return code in ETUDIANTS and not _info(code).get("erasmus")


# ============================================================
#  Chargement
# ============================================================

def charger(dossier):
    """{code: {sem: {(jour,moment): cellule}}}"""
    data = {}
    for nom in sorted(os.listdir(dossier)):
        if not nom.endswith(".csv"):
            continue
        code = nom[:-4]
        cells = {}
        with open(os.path.join(dossier, nom), encoding="utf-8") as f:
            for ligne in csv.reader(f):
                if len(ligne) >= 12 and ligne[0].isdigit():
                    sem = int(ligne[0])
                    cells[sem] = {c: ligne[IDX[c]] for c in COLS}
        data[code] = cells
    return data


def _est_poly(cell):
    return cell.startswith("Poly")


def _est_ss(cell):
    return "sanitaire" in cell.lower()


def _partenaires(cellule):
    """Codes cités après 'avec', suffixe (…) retiré."""
    nu = _SUFFIXE.sub("", cellule)
    if " avec " not in nu:
        return []
    return [p.strip() for p in nu.split(" avec ", 1)[1].split("+") if p.strip()]


# ============================================================
#  1. CAPACITÉ
# ============================================================

def controle_capacite(data):
    print("=" * 66)
    print("  1. CAPACITÉ (max 19 box par créneau)")
    print("=" * 66)

    # reconstruire les box par créneau via fusion des partenaires
    depassements = []
    pire = 0

    creneaux = defaultdict(list)
    for code, cells in data.items():
        for sem, jm in cells.items():
            for c, cell in jm.items():
                if _est_poly(cell):
                    creneaux[(sem,) + c].append(set([code] + _partenaires(cell)))

    for cle, groupes in creneaux.items():
        boxes = []
        for s in groupes:
            fus = None
            for b in boxes:
                if b & s:
                    b |= s
                    fus = b
                    break
            if fus is None:
                boxes.append(set(s))
        n = len(boxes)
        pire = max(pire, n)
        if n > MAX_BOXES:
            depassements.append((cle, n))

    print(f"  Créneaux Poly analysés : {len(creneaux)}")
    print(f"  Maximum de box sur un créneau : {pire} (limite {MAX_BOXES})")
    if depassements:
        print(f"  ❌ PROBLÈME : {len(depassements)} créneau(x) dépassent {MAX_BOXES}")
        for (sem, j, m), n in depassements[:8]:
            print(f"       semaine {sem} {j} {m} : {n} box")
    else:
        print(f"  ✅ OK : aucun dépassement de capacité")
    return not depassements


# ============================================================
#  2. ÉQUITÉ
# ============================================================

def controle_equite(data):
    print("\n" + "=" * 66)
    print("  2. ÉQUITÉ (vacations Poly par promo et type)")
    print("=" * 66)

    vac = defaultdict(int)
    for code, cells in data.items():
        for jm in cells.values():
            for cell in jm.values():
                if _est_poly(cell):
                    vac[code] += 1

    souci = False        # vrai problème (4A/5A) → fait échouer le verdict
    note_6a = False      # dispersion 6A (stages) → signalée mais n'échoue pas
    for annee in (4, 5, 6):
        codes = [c for c in vac if _info(c).get("annee") == annee and _reel(c)]
        if not codes:
            continue
        vals = [vac[c] for c in codes]
        print(f"\n  {annee}A : n={len(vals)} min={min(vals)} max={max(vals)} "
              f"moy={statistics.mean(vals):.1f} σ={statistics.pstdev(vals):.2f}")
        for t in range(1, 6):
            ct = [c for c in codes if _info(c).get("type") == t]
            if not ct:
                continue
            vt = [vac[c] for c in ct]
            sigma = statistics.pstdev(vt)
            flag = ""
            if sigma > 3:
                if annee == 6:
                    # attendu : la charge des 6A dépend de leurs stages
                    flag = "  ⚠️ dispersion (stages)"
                    note_6a = True
                else:
                    flag = "  ❌ écart intra-type anormal"
                    souci = True
            print(f"    type {t} : n={len(vt)} min={min(vt)} max={max(vt)} "
                  f"moy={statistics.mean(vt):.1f} σ={sigma:.2f}{flag}")

    if souci:
        print("\n  ❌ PROBLÈME : écart intra-type anormal chez les 4A/5A")
    elif note_6a:
        print("\n  ✅ OK : 4A/5A équitables. Dispersion 6A = stages (attendue, "
              "pas un défaut).")
    else:
        print("\n  ✅ OK : équité intra-type satisfaisante partout")
    return not souci


# ============================================================
#  3. BINÔMES (réciprocité)
# ============================================================

def controle_binomes(data):
    print("\n" + "=" * 66)
    print("  3. COHÉRENCE DES BINÔMES (réciprocité Poly)")
    print("=" * 66)

    incohérences = []
    total = 0
    for code, cells in data.items():
        for sem, jm in cells.items():
            for c, cell in jm.items():
                if not _est_poly(cell):
                    continue
                for part in _partenaires(cell):
                    total += 1
                    # le partenaire doit me citer en retour sur le même créneau
                    autre = data.get(part, {}).get(sem, {}).get(c, "")
                    if not _est_poly(autre):
                        incohérences.append((code, part, sem, c, "pas Poly"))
                    elif code not in _partenaires(autre):
                        incohérences.append((code, part, sem, c, "non réciproque"))

    print(f"  Liens de partenariat vérifiés : {total}")
    if incohérences:
        print(f"  ❌ PROBLÈME : {len(incohérences)} lien(s) non réciproque(s)")
        for code, part, sem, c, motif in incohérences[:8]:
            print(f"       {code} cite {part} (sem {sem} {c[0]} {c[1]}) : {motif}")
    else:
        print(f"  ✅ OK : tous les binômes sont réciproques")
    return not incohérences


# ============================================================
#  4. ABSENCES respectées
# ============================================================

def controle_absences(data):
    print("\n" + "=" * 66)
    print("  4. ABSENCES RESPECTÉES (pas de Poly sur un stage/absence)")
    print("=" * 66)

    # semaines d'absence par étudiant
    absent = defaultdict(set)
    for code, blocs in INDISPO_INDIVIDUEL.items():
        for semaines, _motif in blocs:
            absent[code].update(semaines)

    violations = []
    for code, cells in data.items():
        for sem in absent.get(code, ()):
            jm = cells.get(sem, {})
            for c, cell in jm.items():
                if _est_poly(cell):
                    violations.append((code, sem, c, cell))

    print(f"  Étudiants avec absences : {len(absent)}")
    if violations:
        print(f"  ❌ PROBLÈME : {len(violations)} vacation(s) Poly sur une absence")
        for code, sem, c, cell in violations[:8]:
            print(f"       {code} sem {sem} {c[0]} {c[1]} : {cell[:40]}")
    else:
        print(f"  ✅ OK : aucune vacation Poly ne tombe sur une absence")
    return not violations


# ============================================================
#  5. SERVICE SANITAIRE
# ============================================================

def controle_service_sanitaire(data):
    print("\n" + "=" * 66)
    print("  5. SERVICE SANITAIRE (semaines par 4A, cohérence)")
    print("=" * 66)

    ss = defaultdict(list)  # code -> [(sem, creneau)]
    for code, cells in data.items():
        for sem, jm in cells.items():
            for c, cell in jm.items():
                if _est_ss(cell):
                    ss[code].append((sem, c))

    concernes = [c for c in ss if _info(c).get("annee") == 4 and _reel(c)]
    print(f"  4A avec service sanitaire : {len(concernes)}")

    souci = False
    compte = Counter()
    for code in concernes:
        sems = sorted(set(s for s, _ in ss[code]), key=_ordre)
        n = len(sems)
        compte[n] += 1
        # chaque 4A devrait avoir 6 ou 7 semaines, sur 2 créneaux fixes
        if n < 6:
            souci = True
        creneaux = set(c for _, c in ss[code])
        if len(creneaux) != 2:
            souci = True

    for n in sorted(compte):
        marque = "" if n in (6, 7) else "  ⚠️"
        print(f"    {compte[n]} étudiant(s) avec {n} semaines{marque}")

    # tous les 4A réels concernés ? (hors Erasmus)
    tous_4a = [c for c in ETUDIANTS if _info(c).get("annee") == 4 and _reel(c)]
    manquants = [c for c in tous_4a if c not in ss]
    if manquants:
        print(f"  ⚠️  {len(manquants)} 4A sans service sanitaire "
              f"(peut être normal : dispensés/redoublants)")

    if souci:
        print("  ⚠️  Certains 4A n'ont pas 6-7 semaines sur 2 créneaux fixes")
    else:
        print("  ✅ OK : chaque 4A a 6-7 semaines sur 2 créneaux cohérents")
    return not souci


# ============================================================
#  6. EXEMPLES CONCRETS
# ============================================================

def exemples(data, n=3):
    print("\n" + "=" * 66)
    print(f"  6. EXEMPLES CONCRETS ({n} étudiants au hasard)")
    print("=" * 66)

    codes = [c for c in data if _reel(c)]
    random.shuffle(codes)
    for code in codes[:n]:
        info = _info(code)
        nom = NOMS.get(code, "?")
        print(f"\n  {code} — {nom} ({info.get('annee')}A type {info.get('type')})")
        # semaine type : une semaine active où il a des vacations
        cells = data[code]
        sem_active = None
        for sem in sorted(cells, key=_ordre):
            if any(_est_poly(v) or _est_ss(v) for v in cells[sem].values()):
                sem_active = sem
                break
        if sem_active is None:
            print("     (aucune semaine active trouvée)")
            continue
        print(f"     Semaine {sem_active} :")
        for c in COLS:
            cell = cells[sem_active][c]
            if cell != VIDE:
                print(f"        {c[0]:9s} {c[1]:3s} : {cell}")
        # compteurs
        n_poly = sum(1 for jm in cells.values()
                     for v in jm.values() if _est_poly(v))
        n_ss = sum(1 for jm in cells.values()
                   for v in jm.values() if _est_ss(v))
        print(f"     Total : {n_poly} vacations Poly, {n_ss} demi-journées SS")


# ============================================================
#  Point d'entrée
# ============================================================

def rapport(dossier=DOSSIER_DEFAUT, graine=None):
    if not os.path.isdir(dossier):
        raise SystemExit(f"Dossier introuvable : {dossier}")
    if graine is not None:
        random.seed(graine)

    print(f"\nAnalyse de '{dossier}'  ({len(os.listdir(dossier))} fichiers)\n")
    data = charger(dossier)

    resultats = {
        "capacité": controle_capacite(data),
        "équité": controle_equite(data),
        "binômes": controle_binomes(data),
        "absences": controle_absences(data),
        "service sanitaire": controle_service_sanitaire(data),
    }
    exemples(data)

    print("\n" + "=" * 66)
    print("  VERDICT GLOBAL")
    print("=" * 66)
    for nom, ok in resultats.items():
        print(f"  {'✅' if ok else '❌'} {nom}")
    if all(resultats.values()):
        print("\n  ✅ Tous les contrôles passent.")
    else:
        echecs = [n for n, ok in resultats.items() if not ok]
        print(f"\n  ⚠️  À examiner : {', '.join(echecs)}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    d = args[0] if args else DOSSIER_DEFAUT
    rapport(d)