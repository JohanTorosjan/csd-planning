# ============================================================
#  test_poly_pedo_urgences.py — VALIDATION GLOBALE de la pipeline
#
#  Lit planning_csv_urgences (dernier état : il contient TOUT —
#  Poly, examens, service sanitaire, Pédo, urgences — car chaque
#  étape recopie le dossier précédent).
#
#  Déroulé :
#     1. TESTS POLY        (via test_poly) + exploration cas par cas
#     2. TESTS PÉDO        (via test_pedo)
#     3. TESTS URGENCES    (via test_urgences)
#     4. STATS GLOBALES    (occupation totale, places restantes,
#                           répartition matière par matière)
#
#  Usage : python3 test_poly_pedo_urgences.py
#          python3 test_poly_pedo_urgences.py --seed 42
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
VIDE = "—"

try:
    from etudiants import NOMS
except Exception:
    NOMS = {}


def _ordre(s):
    return s if s >= 36 else s + 100


def _banniere(txt, car="█"):
    print("\n" + car * 70)
    print(f"  {txt}")
    print(car * 70)


# ============================================================
#  Classification des cellules
# ============================================================

def est_poly(cell):
    return "Poly" in cell


def est_ss(cell):
    return "sanitaire" in cell or "Service" in cell or "SS" in cell


def est_pedo(cell):
    return "édo" in cell


def est_urgence(cell):
    return "Urgences" in cell


def est_stage(cell):
    return cell.strip() in ("S", "X", "R")


def est_ferme(cell):
    return cell in ("fermé", "Fermé")


def est_cours(cell):
    return "cours" in cell or "indispo" in cell


def categorie(cell):
    if cell == VIDE:
        return "libre"
    if est_urgence(cell):
        return "urgences"
    if est_pedo(cell):
        return "pédo"
    if est_ss(cell):
        return "service sanitaire"
    if est_poly(cell):
        return "poly"
    if est_stage(cell):
        return "stage"
    if est_ferme(cell):
        return "fermé"
    if est_cours(cell):
        return "cours/indispo"
    return "autre"


# ============================================================
#  Chargement
# ============================================================

def charger():
    data = {}
    for nom in os.listdir(DOSSIER):
        if nom.endswith(".csv"):
            code = nom[:-4]
            with open(os.path.join(DOSSIER, nom), encoding="utf-8") as f:
                data[code] = {int(l[0]): l for l in csv.reader(f)
                              if len(l) >= 12 and l[0].isdigit()}
    return data


# ============================================================
#  1. exploration Poly cas par cas
# ============================================================

def exploration_poly(data, rng, n=3):
    _banniere("EXPLORATION POLY — cas par cas", "─")

    par_at = defaultdict(list)
    for code, info in ETUDIANTS.items():
        if info.get("erasmus"):
            continue
        a = info.get("annee")
        if a in (4, 5, 6):
            par_at[(a, info.get("type"))].append(code)

    for annee in (4, 5, 6):
        types = sorted(t for (a, t) in par_at if a == annee)
        print(f"\n  ── PROMO {annee}A ──")
        for t in types[:2]:            # 2 types par promo pour rester lisible
            codes = par_at[(annee, t)]
            for code in rng.sample(codes, min(1, len(codes))):
                _resume_etudiant(code, data)


def _resume_etudiant(code, data):
    lignes = data.get(code, {})
    nom = NOMS.get(code, "")
    compte = Counter()
    for sem, l in lignes.items():
        for col in COLONNES:
            compte[categorie(l[IDX[col]])] += 1
    interessant = {k: v for k, v in compte.items()
                   if k not in ("libre", "fermé")}
    resume = ", ".join(f"{k}:{v}" for k, v in
                       sorted(interessant.items(), key=lambda x: -x[1]))
    print(f"     {code} ({nom or '?'}, type {ETUDIANTS[code].get('type')}) : {resume}")


# ============================================================
#  Sous-modules (test_poly / test_pedo / test_urgences)
# ============================================================

def lancer_test_poly(seed):
    _banniere("1. VALIDATION POLY (+ service sanitaire)")
    try:
        import test_poly
        test_poly.rapport(dossier=DOSSIER, graine=seed)
    except SystemExit as e:
        print(f"  test_poly interrompu : {e}")
    except Exception as e:
        print(f"  ⚠️  test_poly a rencontré une erreur : {e}")


def lancer_test_pedo(seed):
    _banniere("2. VALIDATION PÉDO")
    try:
        import test_pedo
        test_pedo.DOSSIER_PEDO = DOSSIER          # rediriger vers le dossier final
        data = test_pedo.charger()
        P = pg.periodes()
        rng = random.Random(seed)
        test_pedo.exemples_individuels(data, P, rng)
        test_pedo.composition_salles(data, P)
        test_pedo.stats_globales(data, P)
    except Exception as e:
        print(f"  ⚠️  test_pedo a rencontré une erreur : {e}")


def lancer_test_urgences(seed):
    _banniere("3. VALIDATION URGENCES")
    try:
        import test_urgences
        test_urgences.DOSSIER = DOSSIER
        data, urgences = test_urgences.charger()
        rng = random.Random(seed)
        test_urgences.exemples_individuels(urgences, rng)
        test_urgences.equite_par_promo(urgences)
        test_urgences.remplissage(data, urgences)
        test_urgences.compositions(data)
    except Exception as e:
        print(f"  ⚠️  test_urgences a rencontré une erreur : {e}")


# ============================================================
#  4. Stats globales d'occupation
# ============================================================

def stats_globales(data):
    _banniere("4. STATISTIQUES GLOBALES D'OCCUPATION")

    # répartition de toutes les demi-journées par catégorie
    cat = Counter()
    par_promo_cat = {4: Counter(), 5: Counter(), 6: Counter()}
    total_dj = 0
    for code, lignes in data.items():
        info = ETUDIANTS.get(code, {})
        if info.get("erasmus"):
            continue
        a = info.get("annee")
        if a not in (4, 5, 6):
            continue
        for sem, l in lignes.items():
            for col in COLONNES:
                c = categorie(l[IDX[col]])
                cat[c] += 1
                par_promo_cat[a][c] += 1
                total_dj += 1

    print(f"\n  Demi-journées totales (hors Erasmus) : {total_dj}")
    print(f"\n  Répartition par catégorie :")
    for c, n in cat.most_common():
        print(f"     {c:20s} : {n:6d} ({100 * n / total_dj:4.1f} %)")

    # occupation "utile" (matières) vs libre/fermé/cours
    matieres = ("poly", "service sanitaire", "pédo", "urgences")
    n_mat = sum(cat[m] for m in matieres)
    print(f"\n  Total vacations 'matières' (Poly+SS+Pédo+Urgences) : {n_mat}")

    # par promo : combien de chaque matière
    print(f"\n  Par promo (moyenne par étudiant) :")
    for a in (4, 5, 6):
        codes = [c for c, i in ETUDIANTS.items()
                 if i.get("annee") == a and not i.get("erasmus")]
        n = len(codes)
        ligne = "  ".join(
            f"{m}={par_promo_cat[a][m] / n:.1f}"
            for m in matieres)
        print(f"     {a}A ({n}) : {ligne}")

    # taux de remplissage des créneaux ouvrables
    # (demi-journées non fermées où au moins une matière est posée quelque part)
    libres = cat["libre"]
    ouvrables = total_dj - cat["fermé"]
    occupees = ouvrables - libres
    print(f"\n  Sur {ouvrables} demi-journées ouvrables (hors fermé) :")
    print(f"     occupées : {occupees} ({100 * occupees / ouvrables:.1f} %)")
    print(f"     libres   : {libres} ({100 * libres / ouvrables:.1f} %)")


def main():
    seed = None
    if "--seed" in sys.argv:
        i = sys.argv.index("--seed")
        if i + 1 < len(sys.argv):
            seed = int(sys.argv[i + 1])

    if not os.path.isdir(DOSSIER):
        print(f"⚠️  Dossier '{DOSSIER}' introuvable. "
              f"Lance d'abord la pipeline complète (jusqu'à urgences.py --export).")
        return

    _banniere("VALIDATION GLOBALE — POLY + PÉDO + URGENCES")
    print(f"  Dossier analysé : {DOSSIER}/ "
          f"({len([f for f in os.listdir(DOSSIER) if f.endswith('.csv')])} fichiers)")
    print("  (ce dossier contient tout l'empilement de la pipeline)")

    data = charger()
    rng = random.Random(seed)

    # 1. Poly + exploration
    lancer_test_poly(seed)
    exploration_poly(data, rng)

    # 2. Pédo
    lancer_test_pedo(seed)

    # 3. Urgences
    lancer_test_urgences(seed)

    # 4. Stats globales
    stats_globales(data)

    _banniere("FIN DE LA VALIDATION GLOBALE")


if __name__ == "__main__":
    main()