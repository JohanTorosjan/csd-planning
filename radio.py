# ============================================================
#  radio.py — Placement des PETITES SALLES RADIO
#
#  Concerne 4A, 5A, 6A. Mix inter-promo, plusieurs places par vacation.
#
#  Règles :
#   - les 10 demi-journées ; salles PLEINES (prioritaire)
#   - 4 places par vacation, SAUF mardi matin (3) et vendredi AM (3)
#   - mix souple « plus de 4A que de 5A que de 6A », obtenu via les quotas :
#       4A → 9/an, 5A → 8/an, 6A → 1/an (attestation radioprotection)
#     Les quotas sont SOUPLES : les salles pleines priment, donc quelques
#     dépassements sont acceptés (fourchettes 6-9 / 6-8).
#   - date de fin paramétrable (SEMAINE_FIN_RADIO)
#
#  Le mix émerge du score : à chaque place, on prend l'étudiant au plus
#  fort déficit par rapport à SON quota. Comme les 4A ont le plus gros
#  quota (9) et les 6A le plus petit (1), on obtient naturellement
#  « plus de 4A que de 5A que de 6A ».
#
#  Entrée : planning_csv_occluso  (--pipeline → planning_csv_odf)
#  Sortie : planning_csv_radio
#
#  Usage : python3 radio.py            (aperçu)
#          python3 radio.py --export   (écrit les CSV)
#          python3 radio.py --pipeline (lit planning_csv_odf)
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
DOSSIER_SORTIE = "planning_csv_radio"
VIDE = "—"

COLONNES = pg.COLONNES
IDX = pg.IDX

# ============================================================
#  CONFIGURATION
# ============================================================

# quotas indicatifs par promo (souples ; donnent le mix « 4 > 5 > 6 »)
QUOTA = {4: 9, 5: 8, 6: 1}

# places par vacation : 4 partout sauf mardi matin et vendredi AM = 3
PLACES_REDUITES = {("mardi", "M"), ("vendredi", "AM")}
PLACES_NORMAL = 4
PLACES_REDUIT = 3

# date de fin (comme les autres cette année : s22)
SEMAINE_FIN_RADIO = 22

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


def places_vacation(col):
    return PLACES_REDUIT if col in PLACES_REDUITES else PLACES_NORMAL


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
    Remplit chaque vacation à sa capacité (3 ou 4) avec un mix de promos.
    Le mix émerge du déficit au quota (4A quota 9 > 5A 8 > 6A 1).
    Renvoie (affectations, alertes).
    """
    codes = [c for c, i in ETUDIANTS.items()
             if i.get("annee") in (4, 5, 6) and not i.get("erasmus")
             and c in data]
    index = {}
    for code in codes:
        index[code] = {int(l[0]): i for i, l in enumerate(data[code])
                       if len(l) >= 12 and l[0].isdigit()}

    sems = sorted({s for c in codes for s in index[c]}, key=_ordre)
    sems = [s for s in sems if _ordre(s) <= _ordre(SEMAINE_FIN_RADIO)]

    deja = defaultdict(int)
    dernier = {}
    affectations = defaultdict(list)
    alertes = []

    def score(code, inst):
        a = annee(code)
        # priorité ABSOLUE aux 6A qui n'ont pas encore leur attestation :
        # tant qu'un 6A est à 0, il doit être pris dès qu'il est dispo.
        if a == 6 and deja[code] == 0:
            deficit = 1000            # priorité maximale
        else:
            deficit = QUOTA[a] - deja[code]
        d = dernier.get(code)
        recence = 1.0 / max(1, inst - d) if d is not None else 0.0
        return (-deficit, POIDS_RECENCE * recence)

    for sem in sems:
        for col in COLONNES:
            i = IDX[col]
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

            besoin = places_vacation(col)
            if not dispo:
                alertes.append(f"vacation s{sem} {col[0]} {col[1]} : "
                               f"aucun étudiant (salle vide)")
                continue
            if len(dispo) < besoin:
                alertes.append(f"vacation s{sem} {col[0]} {col[1]} : "
                               f"{len(dispo)} dispo pour {besoin} places "
                               f"(salle non pleine)")

            inst = instant(sem, col)
            dispo.sort(key=lambda c: score(c, inst))
            for code in dispo[:besoin]:
                affectations[code].append((sem, col))
                deja[code] += 1
                dernier[code] = inst

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
                data[code][i][j] = "Radio"

    if conflits:
        print(f"\n⚠️  {conflits} conflit(s) — cellules déjà occupées")

    total = sum(len(v) for v in affectations.values())
    print(f"\n  {total} affectations de radio.")
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
    print("  PETITES SALLES RADIO — RAPPORT")
    print("=" * 66)

    vac = defaultdict(list)
    for code, places in affectations.items():
        for v in places:
            vac[v].append(code)
    print(f"\n  Vacations couvertes : {len(vac)}")
    print(f"  Places pourvues : {sum(len(m) for m in vac.values())}")

    # composition moyenne du mix
    tot = {4: 0, 5: 0, 6: 0}
    for code, places in affectations.items():
        tot[annee(code)] += len(places)
    somme = sum(tot.values()) or 1
    print(f"\n  Mix global : 4A={tot[4]} ({100*tot[4]/somme:.0f}%)  "
          f"5A={tot[5]} ({100*tot[5]/somme:.0f}%)  "
          f"6A={tot[6]} ({100*tot[6]/somme:.0f}%)")

    for a in (4, 5, 6):
        codes = [c for c, i in ETUDIANTS.items()
                 if i.get("annee") == a and not i.get("erasmus")]
        vals = [len(affectations.get(c, [])) for c in codes]
        actifs = [v for v in vals if v > 0]
        print(f"\n  {a}A (quota {QUOTA[a]}) : {len(actifs)}/{len(vals)} ont ≥1")
        if vals:
            print(f"     min={min(vals)}, max={max(vals)}, "
                  f"moy={statistics.mean(vals):.1f}, σ={statistics.pstdev(vals):.2f}")

    # salles pleines ?
    non_pleines = 0
    for v, membres in vac.items():
        if len(membres) != places_vacation(v[1]):
            non_pleines += 1
    print(f"\n  Salles non pleines : {non_pleines}/{len(vac)}")

    if alertes:
        print(f"\n  ⚠️  {len(alertes)} alerte(s) (dont fériés) :")
        for a in alertes[:8]:
            print(f"     - {a}")


def main(export=None):
    ecrire = export if export is not None else ("--export" in sys.argv)
    data = charger(dossier_entree())
    affectations, alertes = placer(data)
    rapport(affectations, alertes)
    exporter(data, affectations, ecrire)


if __name__ == "__main__":
    main()