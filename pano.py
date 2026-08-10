# ============================================================
#  pano.py — Placement des vacations de PANO / CBCT (radio)
#
#  Concerne les 6A en priorité, les 5A en renfort. 1 étudiant/vacation.
#
#  Règles :
#   - créneaux : lunAM, marAM, merM, merAM, jeuAM, venAM
#     (jours 2, 4, 5, 6, 8, 10 : tous les après-midis + mercredi matin)
#   - 1 seul étudiant par vacation
#   - il faut TOUJOURS quelqu'un (toutes les vacations couvertes)
#   - 6A d'abord (quota indicatif 3/an) ; 5A seulement en renfort quand
#     il n'y a pas assez de 6A disponibles.
#   - date de fin paramétrable (SEMAINE_FIN_PANO)
#
#  Entrée : planning_csv_occluso  (--pipeline → planning_csv_odf)
#  Sortie : planning_csv_pano
#
#  Usage : python3 pano.py            (aperçu)
#          python3 pano.py --export   (écrit les CSV)
#          python3 pano.py --pipeline (lit planning_csv_odf)
# ============================================================

import os
import csv
import sys
import statistics
from collections import defaultdict

from etudiants import ETUDIANTS

import pedo_groupes as pg

DOSSIER_OCCLUSO = "planning_csv_occluso"
DOSSIER_ODF = "planning_csv_odf"
DOSSIER_SORTIE = "planning_csv_pano"
VIDE = "—"

IDX = pg.IDX

# ============================================================
#  CONFIGURATION
# ============================================================

# créneaux Pano : lunAM, marAM, merM, merAM, jeuAM, venAM
CRENEAUX_PANO = [("lundi", "AM"), ("mardi", "AM"), ("mercredi", "M"),
                 ("mercredi", "AM"), ("jeudi", "AM"), ("vendredi", "AM")]

# quota indicatif (6A prioritaires)
QUOTA_6A = 3

# date de fin (comme les autres cette année : s22)
SEMAINE_FIN_PANO = 22

# poids de l'étalement dans le score
POIDS_RECENCE = 3.0


_SEQUENCE = list(range(36, 53)) + list(range(1, 36))
_POSITION = {s: i for i, s in enumerate(_SEQUENCE)}


def _ordre(s):
    return s if s >= 36 else s + 100


JOUR_OFFSET = {"lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3,
               "vendredi": 4}


def instant(sem, col):
    jour, moment = col
    base = _POSITION.get(sem, _ordre(sem)) * 14
    base += JOUR_OFFSET.get(jour, 0) * 2
    base += 1 if moment == "AM" else 0
    return base


def est_ferme(cell):
    return cell in ("fermé", "Fermé")


def annee(code):
    return ETUDIANTS.get(code, {}).get("annee")


# ============================================================
#  Chargement
# ============================================================

def dossier_entree():
    return DOSSIER_ODF if "--pipeline" in sys.argv else DOSSIER_OCCLUSO


def charger(dossier):
    data = {}
    for nom in os.listdir(dossier):
        if nom.endswith(".csv"):
            code = nom[:-4]
            with open(os.path.join(dossier, nom), encoding="utf-8") as f:
                data[code] = [list(l) for l in csv.reader(f)]
    return data


# ============================================================
#  Placement
# ============================================================

def placer(data):
    """
    Couvre chaque vacation Pano avec 1 étudiant : un 6A en priorité
    (visant le quota), un 5A seulement s'il n'y a pas de 6A disponible.
    Renvoie (affectations, alertes).
    """
    codes = [c for c, i in ETUDIANTS.items()
             if i.get("annee") in (5, 6) and not i.get("erasmus")
             and c in data]
    index = {}
    for code in codes:
        index[code] = {int(l[0]): i for i, l in enumerate(data[code])
                       if len(l) >= 12 and l[0].isdigit()}

    sems = sorted({s for c in codes for s in index[c]}, key=_ordre)
    sems = [s for s in sems if _ordre(s) <= _ordre(SEMAINE_FIN_PANO)]

    deja = defaultdict(int)
    dernier = {}
    affectations = defaultdict(list)
    alertes = []

    def score(code, inst):
        # 6A : déficit au quota ; 5A : renfort (score plus élevé = moins
        # prioritaire, mais départagé par moins servi + étalement)
        if annee(code) == 6:
            deficit = QUOTA_6A - deja[code]
        else:
            deficit = -deja[code]        # 5A : juste équilibrer entre eux
        d = dernier.get(code)
        recence = 1.0 / max(1, inst - d) if d is not None else 0.0
        return (-deficit, POIDS_RECENCE * recence)

    for sem in sems:
        for col in CRENEAUX_PANO:
            i = IDX[col]
            dispo6 = []
            dispo5 = []
            nferme = 0
            ntot = 0
            for code in codes:
                li = index[code].get(sem)
                if li is None:
                    continue
                ntot += 1
                v = data[code][li][i]
                if est_ferme(v):
                    nferme += 1
                elif v == VIDE:
                    if annee(code) == 6:
                        dispo6.append(code)
                    else:
                        dispo5.append(code)
            if nferme > ntot * 0.5:
                continue
            if not dispo6 and not dispo5:
                alertes.append(f"vacation s{sem} {col[0]} {col[1]} : "
                               f"aucun 6A/5A disponible")
                continue

            inst = instant(sem, col)
            # 6A d'abord ; 5A en renfort seulement si aucun 6A dispo
            pool = dispo6 if dispo6 else dispo5
            choisi = min(pool, key=lambda c: score(c, inst))

            affectations[choisi].append((sem, col))
            deja[choisi] += 1
            dernier[choisi] = inst

    return affectations, alertes


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
        for sem, col in places:
            i = index[code].get(sem)
            if i is None:
                continue
            j = IDX[col]
            if data[code][i][j] != VIDE:
                conflits += 1
                continue
            if ecrire:
                data[code][i][j] = "Pano/CBCT"

    if conflits:
        print(f"\n⚠️  {conflits} conflit(s) — cellules déjà occupées")

    total = sum(len(v) for v in affectations.values())
    print(f"\n  {total} affectations de Pano/CBCT.")
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

def rapport(affectations, alertes):
    print("=" * 66)
    print("  PANO / CBCT — RAPPORT")
    print("=" * 66)

    vac = set()
    for places in affectations.values():
        vac |= set(places)
    print(f"\n  Vacations couvertes : {len(vac)}")
    total = sum(len(v) for v in affectations.values())
    print(f"  Total affectations : {total}")

    # part 6A vs 5A
    n6 = sum(len(p) for c, p in affectations.items() if annee(c) == 6)
    n5 = sum(len(p) for c, p in affectations.items() if annee(c) == 5)
    print(f"     dont 6A : {n6}  |  5A (renfort) : {n5}")

    for a in (6, 5):
        codes = [c for c, i in ETUDIANTS.items()
                 if i.get("annee") == a and not i.get("erasmus")]
        vals = [len(affectations.get(c, [])) for c in codes]
        actifs = [v for v in vals if v > 0]
        cible = f" (quota {QUOTA_6A})" if a == 6 else " (renfort)"
        print(f"\n  {a}A{cible} : {len(actifs)}/{len(vals)} ont ≥1")
        if vals:
            print(f"     min={min(vals)}, max={max(vals)}, "
                  f"moy={statistics.mean(vals):.1f}")

    if alertes:
        print(f"\n  ⚠️  {len(alertes)} alerte(s) :")
        for a in alertes[:10]:
            print(f"     - {a}")


def main(export=None):
    ecrire = export if export is not None else ("--export" in sys.argv)
    data = charger(dossier_entree())
    affectations, alertes = placer(data)
    rapport(affectations, alertes)
    exporter(data, affectations, ecrire)


if __name__ == "__main__":
    main()