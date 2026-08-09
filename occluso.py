# ============================================================
#  occluso.py — Placement des vacations d'OCCLUSO
#
#  Matière simple, réservée aux 4A. Placement INDIVIDUEL.
#
#  Règles :
#   - concerne UNIQUEMENT les 4A
#   - créneaux : lundi M, mardi M, jeudi M, vendredi M (matins)
#   - 4 places par vacation, TOUJOURS pleines
#   - période : de la rentrée (SEMAINE_DEBUT) jusqu'à une date de FIN
#     paramétrable (cette année : 28 mai = semaine 22)
#   - si les 4A sont tous en cours (0 dispo) → vacation sautée
#   - MINIMUM 3 vacations par 4A (garanti)
#   - on remplit le MAXIMUM de vacations possibles
#
#  Objectifs (par priorité) :
#     1. remplir un maximum de vacations (toutes pleines)
#     2. équité sur le nombre (tous ~même nb) + minimum 3
#     3. étalement temporel
#     4. bonus : au moins 1 vacation en période 1 si possible
#
#  Entrée : planning_csv_urgences (dernier état de la pipeline)
#  Sortie : planning_csv_occluso
#
#  Usage : python3 occluso.py            (aperçu)
#          python3 occluso.py --export   (écrit les CSV)
# ============================================================

import os
import csv
import sys
import statistics
from collections import defaultdict

from etudiants import ETUDIANTS

import pedo_groupes as pg

DOSSIER_ENTREE = "planning_csv_urgences"
DOSSIER_SORTIE = "planning_csv_occluso"
VIDE = "—"

IDX = pg.IDX

# ============================================================
#  CONFIGURATION
# ============================================================

# créneaux occluso (matins de lundi, mardi, jeudi, vendredi)
CRENEAUX_OCC = [("lundi", "M"), ("mardi", "M"),
                ("jeudi", "M"), ("vendredi", "M")]

PLACES_PAR_VACATION = 4

# date de fin : 28 mai = semaine 22 (paramétrable).
# L'occluso ne place rien après cette semaine.
SEMAINE_FIN_OCCLUSO = 22

# minimum garanti de vacations par 4A
MINIMUM_PAR_ETUDIANT = 3

# poids de l'étalement dans le score (comme pour les urgences)
POIDS_RECENCE = 3.0

# première période (pour le bonus « ≥1 en P1 ») : bornes de semaines
# on récupère P1 depuis pedo_groupes si dispo, sinon on approxime.


def _ordre(s):
    return s if s >= 36 else s + 100


JOUR_OFFSET = {"lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3,
               "vendredi": 4}

# séquence chronologique réelle des semaines (36→52 puis 1→35).
# On l'utilise pour mesurer les écarts en semaines SANS le saut artificiel
# du passage d'année (s52 et s2 sont en réalité quasi consécutives).
_SEQUENCE = list(range(36, 53)) + list(range(1, 36))
_POSITION = {s: i for i, s in enumerate(_SEQUENCE)}


def instant(sem, col):
    """Position temporelle absolue d'une vacation (en demi-journées),
    fondée sur la position réelle de la semaine dans l'année."""
    jour, moment = col
    base = _POSITION.get(sem, _ordre(sem)) * 14
    base += JOUR_OFFSET.get(jour, 0) * 2
    base += 1 if moment == "AM" else 0
    return base


def est_ferme(cell):
    return cell in ("fermé", "Fermé")


# ============================================================
#  Chargement
# ============================================================

def charger():
    data = {}
    for nom in os.listdir(DOSSIER_ENTREE):
        if nom.endswith(".csv"):
            code = nom[:-4]
            info = ETUDIANTS.get(code, {})
            # on charge tout (pour recopier), mais on ne place que les 4A
            with open(os.path.join(DOSSIER_ENTREE, nom), encoding="utf-8") as f:
                data[code] = [list(l) for l in csv.reader(f)]
    return data


def periode1():
    """Bornes (ensemble de semaines) de la période 1, via pedo_groupes."""
    try:
        P = pg.periodes()
        return set(P[1])
    except Exception:
        # approximation : P1 = rentrée -> ~semaine 44
        return set(range(36, 45))


# ============================================================
#  Placement
# ============================================================

def placer(data):
    """
    Remplit les vacations occluso pour les 4A.
    Renvoie affectations {code: [(sem, col)]}.
    """
    codes4 = [c for c, i in ETUDIANTS.items()
              if i.get("annee") == 4 and not i.get("erasmus")]
    codes4 = [c for c in codes4 if c in data]

    index = {}
    for code in codes4:
        index[code] = {int(l[0]): i for i, l in enumerate(data[code])
                       if len(l) >= 12 and l[0].isdigit()}

    # semaines occluso : de la rentrée à la date de fin
    sems = sorted({s for c in codes4 for s in index[c]}, key=_ordre)
    sems = [s for s in sems if _ordre(s) <= _ordre(SEMAINE_FIN_OCCLUSO)]

    # liste des vacations exploitables (>= 4 dispo)
    vacations = []
    dispo_vac = {}
    for sem in sems:
        for cr in CRENEAUX_OCC:
            i = IDX[cr]
            libres = []
            nferme = 0
            ntot = 0
            for code in codes4:
                li = index[code].get(sem)
                if li is None:
                    continue
                ntot += 1
                v = data[code][li][i]
                if est_ferme(v):
                    nferme += 1
                elif v == VIDE:
                    libres.append(code)
            if nferme > ntot * 0.5:
                continue
            if len(libres) >= PLACES_PAR_VACATION:
                vacations.append((sem, cr))
                dispo_vac[(sem, cr)] = libres

    # ordre chronologique des vacations
    vacations.sort(key=lambda x: instant(x[0], x[1]))

    deja = defaultdict(int)
    dernier = {}
    affectations = defaultdict(list)

    P1 = periode1()

    def score(code, inst, phase_min=False):
        base = deja[code]
        # bonus P1 : si on est en P1 et que l'étudiant n'a encore rien,
        # on le favorise fortement (score très bas)
        d = dernier.get(code)
        recence = 0.0
        if d is not None:
            recence = 1.0 / max(1, inst - d)
        return base + POIDS_RECENCE * recence

    for sem, cr in vacations:
        inst = instant(sem, cr)
        cands = list(dispo_vac[(sem, cr)])
        # bonus P1 : en période 1, prioriser ceux qui n'ont aucune vacation
        if sem in P1:
            cands.sort(key=lambda c: (deja[c] > 0, score(c, inst)))
        else:
            cands.sort(key=lambda c: score(c, inst))
        for code in cands[:PLACES_PAR_VACATION]:
            affectations[code].append((sem, cr))
            deja[code] += 1
            dernier[code] = inst

    # ── garantie du minimum : compléter ceux sous le minimum ──
    _garantir_minimum(affectations, deja, index, data, codes4, sems)

    return affectations


def _garantir_minimum(affectations, deja, index, data, codes4, sems):
    """
    S'assure que chaque 4A atteint MINIMUM_PAR_ETUDIANT vacations.
    Pour chaque étudiant sous le minimum, on cherche une vacation où il
    est dispo et où on peut le placer en remplaçant un étudiant qui, lui,
    est au-dessus du minimum (échange équitable) — ou sur une place libre
    si la vacation n'était pas pleine (ne devrait pas arriver ici).
    """
    # ensemble des places déjà prises par vacation
    par_vac = defaultdict(list)
    for code, places in affectations.items():
        for v in places:
            par_vac[v].append(code)

    for code in codes4:
        while deja[code] < MINIMUM_PAR_ETUDIANT:
            # trouver une vacation où `code` est dispo et pas déjà placé
            place_trouvee = False
            for sem in sems:
                li = index[code].get(sem)
                if li is None:
                    continue
                for cr in CRENEAUX_OCC:
                    v = (sem, cr)
                    if v not in par_vac:
                        continue
                    if data[code][li][IDX[cr]] != VIDE:
                        continue
                    if code in par_vac[v]:
                        continue
                    # remplacer le membre le plus servi (au-dessus du min)
                    membres = par_vac[v]
                    remplacable = max(
                        membres,
                        key=lambda m: deja[m])
                    if deja[remplacable] > MINIMUM_PAR_ETUDIANT and \
                       deja[remplacable] > deja[code] + 1:
                        # échange
                        par_vac[v].remove(remplacable)
                        affectations[remplacable].remove(v)
                        deja[remplacable] -= 1
                        par_vac[v].append(code)
                        affectations[code].append(v)
                        deja[code] += 1
                        place_trouvee = True
                        break
                if place_trouvee:
                    break
            if not place_trouvee:
                # aucun échange possible (rare) : on abandonne pour cet étudiant
                break


# ============================================================
#  Export
# ============================================================

def exporter(data, affectations, ecrire):
    index = {}
    for code in affectations:
        index[code] = {int(l[0]): i for i, l in enumerate(data[code])
                       if len(l) >= 12 and l[0].isdigit()}

    conflits = 0
    for code, places in affectations.items():
        for sem, cr in places:
            i = index[code].get(sem)
            if i is None:
                continue
            j = IDX[cr]
            if data[code][i][j] != VIDE:
                conflits += 1
                continue
            if ecrire:
                data[code][i][j] = "Occluso"

    if conflits:
        print(f"\n⚠️  {conflits} conflit(s) — cellules déjà occupées")

    total = sum(len(v) for v in affectations.values())
    print(f"\n  {total} affectations d'occluso.")
    if ecrire:
        os.makedirs(DOSSIER_SORTIE, exist_ok=True)
        for code, lignes in data.items():
            with open(os.path.join(DOSSIER_SORTIE, f"{code}.csv"), "w",
                      newline="", encoding="utf-8") as f:
                csv.writer(f).writerows(lignes)
        print(f"  CSV écrits dans {DOSSIER_SORTIE}/")
    else:
        print("  (aperçu — ajouter --export pour écrire)")


# ============================================================
#  Rapport
# ============================================================

def rapport(affectations):
    print("=" * 66)
    print("  OCCLUSO — RAPPORT")
    print("=" * 66)

    codes4 = [c for c, i in ETUDIANTS.items()
              if i.get("annee") == 4 and not i.get("erasmus")]
    vals = [len(affectations.get(c, [])) for c in codes4]

    # vacations couvertes
    vac = set()
    for places in affectations.values():
        vac |= set(places)
    print(f"\n  Vacations occluso : {len(vac)}")
    print(f"  Places pourvues : {sum(vals)}")

    if vals:
        print(f"\n  Équité 4A ({len(vals)} étudiants) :")
        print(f"     min={min(vals)}, max={max(vals)}, "
              f"moy={statistics.mean(vals):.1f}, σ={statistics.pstdev(vals):.2f}")
        sous_min = sum(1 for v in vals if v < MINIMUM_PAR_ETUDIANT)
        print(f"     sous le minimum ({MINIMUM_PAR_ETUDIANT}) : {sous_min}")

    # bonus P1
    P1 = periode1()
    en_p1 = 0
    for c in codes4:
        if any(sem in P1 for sem, _ in affectations.get(c, [])):
            en_p1 += 1
    print(f"\n  4A avec au moins 1 vacation en P1 : {en_p1}/{len(codes4)}")

    # étalement
    ecarts = []
    for c in codes4:
        places = affectations.get(c, [])
        if len(places) < 2:
            continue
        insts = sorted(instant(s, cc) for s, cc in places)
        for k in range(1, len(insts)):
            ecarts.append((insts[k] - insts[k - 1]) / 14)
    if ecarts:
        print(f"\n  Étalement : écart moyen entre 2 vacations "
              f"= {statistics.mean(ecarts):.1f} semaines "
              f"(min {min(ecarts):.1f})")


def main(export=None):
    ecrire = export if export is not None else ("--export" in sys.argv)
    data = charger()
    affectations = placer(data)
    rapport(affectations)
    exporter(data, affectations, ecrire)


if __name__ == "__main__":
    main()