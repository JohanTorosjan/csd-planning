# ============================================================
#  sterilisation.py — Placement des vacations de STÉRILISATION
#
#  Concerne 4A, 5A, 6A. Placement INDIVIDUEL : 1 étudiant par vacation.
#
#  Règles :
#   - 1 seul étudiant par vacation (les 10 demi-journées)
#   - il faut TOUJOURS quelqu'un (toutes les vacations couvertes)
#   - priorité aux 4A, puis 5A, puis 6A (« éviter les 6A »)
#   - quota indicatif souple : ~3 (4A), ~2 (5A), ~1 (6A) en moyenne
#   - logique temporelle : les 6A font leur stérilisation EN DÉBUT
#     d'année. Mécanisme : PHASE 1, tant qu'il reste des 6A non placés,
#     on met un 6A par vacation (ils remplissent les premières semaines) ;
#     PHASE 2, le reste de l'année est couvert par les 4A et 5A.
#
#  Entrée : planning_csv_occluso  (--pipeline → planning_csv_odf)
#  Sortie : planning_csv_sterilisation
#
#  Usage : python3 sterilisation.py            (aperçu)
#          python3 sterilisation.py --export   (écrit les CSV)
#          python3 sterilisation.py --pipeline (lit planning_csv_odf)
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
DOSSIER_SORTIE = "planning_csv_sterilisation"
VIDE = "—"

COLONNES = pg.COLONNES
IDX = pg.IDX

# ============================================================
#  CONFIGURATION
# ============================================================

# quota indicatif par promo (moyenne visée, souple)
QUOTA = {4: 3, 5: 2, 6: 1}

# date de fin (comme occluso/ODF cette année) : semaine 22 (28 mai).
# La stérilisation ne place rien après cette semaine.
SEMAINE_FIN_STE = 22

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
    Couvre chaque vacation avec 1 étudiant.
    PHASE 1 : 6A d'abord (jusqu'à ce que tous aient leur stérilisation).
    PHASE 2 : 4A/5A pour le reste.
    Renvoie (affectations {code:[(sem,col)]}, alertes [str]).
    """
    codes = [c for c, i in ETUDIANTS.items()
             if i.get("annee") in (4, 5, 6) and not i.get("erasmus")
             and c in data]
    index = {}
    for code in codes:
        index[code] = {int(l[0]): i for i, l in enumerate(data[code])
                       if len(l) >= 12 and l[0].isdigit()}

    sems = sorted({s for c in codes for s in index[c]}, key=_ordre)
    # ne pas placer après la date de fin (paramétrable)
    sems = [s for s in sems if _ordre(s) <= _ordre(SEMAINE_FIN_STE)]

    deja = defaultdict(int)          # nb de stérilisations par étudiant
    dernier = {}                     # instant dernière vacation
    affectations = defaultdict(list)
    alertes = []

    # 6A non encore placés (chacun doit faire son quota de 1)
    codes6 = [c for c in codes if annee(c) == 6]
    restants_6a = set(codes6)

    def score(code, inst):
        # déficit par rapport au quota (négatif = déjà au-dessus)
        q = QUOTA[annee(code)]
        deficit = q - deja[code]
        d = dernier.get(code)
        recence = 1.0 / max(1, inst - d) if d is not None else 0.0
        # plus le déficit est grand, plus on veut le placer (score bas)
        return (-deficit, POIDS_RECENCE * recence)

    for sem in sems:
        for col in COLONNES:
            i = IDX[col]
            # étudiants disponibles cette vacation
            dispo = []
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
                    dispo.append(code)
            if nferme > ntot * 0.5:
                continue
            if not dispo:
                alertes.append(f"vacation s{sem} {col[0]} {col[1]} : "
                               f"aucun étudiant disponible")
                continue

            inst = instant(sem, col)

            # PHASE 1 : s'il reste des 6A à placer et qu'un 6A est dispo ici
            choisi = None
            dispo6 = [c for c in dispo if c in restants_6a]
            if dispo6:
                # le 6A le moins servi (tous à 0 au début), départage récence
                choisi = min(dispo6, key=lambda c: score(c, inst))
                restants_6a.discard(choisi)
            else:
                # PHASE 2 : priorité 4A > 5A ; on évite les 6A déjà servis.
                # candidats = 4A et 5A (les 6A ne repassent que s'il n'y a
                # personne d'autre).
                cand45 = [c for c in dispo if annee(c) in (4, 5)]
                pool = cand45 if cand45 else dispo
                # priorité promo (4 avant 5) intégrée via un petit bonus,
                # puis score (déficit + étalement)
                def cle(c):
                    prio = {4: 0, 5: 1, 6: 2}[annee(c)]
                    return (prio,) + score(c, inst)
                choisi = min(pool, key=cle)

            affectations[choisi].append((sem, col))
            deja[choisi] += 1
            dernier[choisi] = inst

    if restants_6a:
        alertes.append(f"{len(restants_6a)} 6A n'ont pas pu être placés "
                       f"en phase 1 (dispo insuffisante en début d'année)")

    # ── garantir un minimum de 1 stérilisation par étudiant ──
    _garantir_minimum_1(codes, index, data, affectations, deja, sems, alertes)

    return affectations, alertes


def _garantir_minimum_1(codes, index, data, affectations, deja, sems, alertes):
    """Pour chaque étudiant à 0, cherche une vacation où il est dispo et
    remplace un étudiant qui a plus que le minimum (>1), sans le faire
    passer sous 1."""
    par_vac = defaultdict(list)
    for code in codes:
        for v in affectations[code]:
            par_vac[v].append(code)

    a_zero = [c for c in codes if deja[c] == 0]
    for code in a_zero:
        place = False
        for sem in sems:
            li = index[code].get(sem)
            if li is None:
                continue
            for col in COLONNES:
                if data[code][li][IDX[col]] != VIDE:
                    continue
                v = (sem, col)
                membres = par_vac.get(v, [])
                if not membres:
                    continue
                # remplacer le membre le plus servi (qui restera >= 1)
                remplacable = max(membres, key=lambda m: deja[m])
                if deja[remplacable] > 1:
                    par_vac[v].remove(remplacable)
                    affectations[remplacable].remove(v)
                    deja[remplacable] -= 1
                    par_vac[v].append(code)
                    affectations[code].append(v)
                    deja[code] += 1
                    place = True
                    break
            if place:
                break
        if not place:
            alertes.append(f"{code} : impossible de garantir 1 stérilisation")


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
                data[code][i][j] = "Stérilisation"

    if conflits:
        print(f"\n⚠️  {conflits} conflit(s) — cellules déjà occupées")

    total = sum(len(v) for v in affectations.values())
    print(f"\n  {total} affectations de stérilisation.")
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
    print("  STÉRILISATION — RAPPORT")
    print("=" * 66)

    vac = set()
    for places in affectations.values():
        vac |= set(places)
    print(f"\n  Vacations couvertes : {len(vac)}")
    print(f"  Total affectations : {sum(len(v) for v in affectations.values())}")

    for a in (4, 5, 6):
        codes = [c for c, i in ETUDIANTS.items()
                 if i.get("annee") == a and not i.get("erasmus")]
        vals = [len(affectations.get(c, [])) for c in codes]
        actifs = [v for v in vals if v > 0]
        print(f"\n  {a}A : {len(actifs)}/{len(vals)} ont ≥1 stérilisation "
              f"(quota indicatif {QUOTA[a]})")
        if vals:
            print(f"     min={min(vals)}, max={max(vals)}, "
                  f"moy={statistics.mean(vals):.1f}")

    # répartition temporelle des 6A (doivent être en début d'année)
    sems6 = []
    for c, i in ETUDIANTS.items():
        if i.get("annee") == 6 and not i.get("erasmus"):
            for sem, _ in affectations.get(c, []):
                sems6.append(_POSITION.get(sem, 99))
    if sems6:
        print(f"\n  6A — position temporelle de leurs stérilisations :")
        print(f"     semaine moyenne (0=rentrée) : {statistics.mean(sems6):.0f}, "
              f"max : {max(sems6)}")

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