# ============================================================
#  como.py — Placement de la COMO
#
#  Concerne 4A, 5A, 6A. Mix inter-promo, 3 places par vacation.
#
#  Règles :
#   - 3 étudiants par vacation ; salles PLEINES à 3 (prioritaire)
#   - créneaux : tous les jours SAUF le jeudi (8 demi-journées)
#   - MIX SOUPLE : on vise 1 étudiant de chaque promo (4A, 5A, 6A) par
#     vacation, mais on accepte des variantes (2+1, etc.) quand une promo
#     n'a personne de disponible — remplir la salle prime sur le mix.
#   - ÉQUITÉ INTRA-PROMO : au sein de chaque promo, on répartit également
#     (on prend toujours le moins servi de la promo visée).
#   - quota indicatif souple (~6-8/an) ; date de fin paramétrable.
#
#  Entrée : planning_csv_occluso  (--pipeline → planning_csv_odf)
#  Sortie : planning_csv_como
#
#  Usage : python3 como.py            (aperçu)
#          python3 como.py --export   (écrit les CSV)
#          python3 como.py --pipeline (lit planning_csv_odf)
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
DOSSIER_SORTIE = "planning_csv_como"
VIDE = "—"

IDX = pg.IDX

# ============================================================
#  CONFIGURATION
# ============================================================

# créneaux COMO : tous les jours SAUF le jeudi
CRENEAUX_COMO = [("lundi", "M"), ("lundi", "AM"),
                 ("mardi", "M"), ("mardi", "AM"),
                 ("mercredi", "M"), ("mercredi", "AM"),
                 ("vendredi", "M"), ("vendredi", "AM")]

PLACES_PAR_VACATION = 3

# ordre de visée du mix (1 de chaque promo)
PROMOS_MIX = [4, 5, 6]

# date de fin (comme les autres cette année : s22)
SEMAINE_FIN_COMO = 22

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
    Remplit chaque vacation à 3 places en visant 1 de chaque promo
    (mix souple), avec équité intra-promo. Renvoie (affectations, alertes).
    """
    codes = [c for c, i in ETUDIANTS.items()
             if i.get("annee") in (4, 5, 6) and not i.get("erasmus")
             and c in data]
    index = {}
    for code in codes:
        index[code] = {int(l[0]): i for i, l in enumerate(data[code])
                       if len(l) >= 12 and l[0].isdigit()}

    sems = sorted({s for c in codes for s in index[c]}, key=_ordre)
    sems = [s for s in sems if _ordre(s) <= _ordre(SEMAINE_FIN_COMO)]

    deja = defaultdict(int)
    dernier = {}
    affectations = defaultdict(list)
    alertes = []

    def score(code, inst):
        # équité intra-promo : le moins servi d'abord ; étalement départage
        d = dernier.get(code)
        recence = 1.0 / max(1, inst - d) if d is not None else 0.0
        return (deja[code], POIDS_RECENCE * recence)

    for sem in sems:
        for col in CRENEAUX_COMO:
            i = IDX[col]
            dispo = {4: [], 5: [], 6: []}
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
                    dispo[annee(code)].append(code)
            if nferme > ntot * 0.5:
                continue

            total_dispo = sum(len(v) for v in dispo.values())
            if total_dispo == 0:
                alertes.append(f"vacation s{sem} {col[0]} {col[1]} : "
                               f"aucun étudiant (salle vide)")
                continue
            if total_dispo < PLACES_PAR_VACATION:
                alertes.append(f"vacation s{sem} {col[0]} {col[1]} : "
                               f"{total_dispo} dispo pour "
                               f"{PLACES_PAR_VACATION} (salle non pleine)")

            inst = instant(sem, col)
            choisis = _composer(dispo, inst, score)
            for code in choisis:
                affectations[code].append((sem, col))
                deja[code] += 1
                dernier[code] = inst

    return affectations, alertes


def _composer(dispo, inst, score):
    """
    Choisit jusqu'à 3 étudiants en visant 1 de chaque promo (mix souple),
    puis complète avec le moins servi toutes promos si une promo manque.
    """
    choisis = []
    pris = set()

    # 1) une place par promo (dans l'ordre 4,5,6), le moins servi de chacune
    for a in PROMOS_MIX:
        cands = [c for c in dispo[a] if c not in pris]
        if cands:
            best = min(cands, key=lambda c: score(c, inst))
            choisis.append(best)
            pris.add(best)
        if len(choisis) == PLACES_PAR_VACATION:
            return choisis

    # 2) compléter les places restantes avec le moins servi, toutes promos
    reste = [c for a in PROMOS_MIX for c in dispo[a] if c not in pris]
    reste.sort(key=lambda c: score(c, inst))
    for c in reste:
        if len(choisis) == PLACES_PAR_VACATION:
            break
        choisis.append(c)
        pris.add(c)

    return choisis


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
                data[code][i][j] = "COMO"

    if conflits:
        print(f"\n⚠️  {conflits} conflit(s) — cellules déjà occupées")

    total = sum(len(v) for v in affectations.values())
    print(f"\n  {total} affectations de COMO.")
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
    print("  COMO — RAPPORT")
    print("=" * 66)

    vac = defaultdict(list)
    for code, places in affectations.items():
        for v in places:
            vac[v].append(code)
    print(f"\n  Vacations couvertes : {len(vac)}")
    print(f"  Places pourvues : {sum(len(m) for m in vac.values())}")

    # mix global
    tot = {4: 0, 5: 0, 6: 0}
    for code, places in affectations.items():
        tot[annee(code)] += len(places)
    somme = sum(tot.values()) or 1
    print(f"\n  Mix global : 4A={tot[4]} ({100*tot[4]/somme:.0f}%)  "
          f"5A={tot[5]} ({100*tot[5]/somme:.0f}%)  "
          f"6A={tot[6]} ({100*tot[6]/somme:.0f}%)")

    # composition des vacations (combien ont 1/1/1, 2/1, etc.)
    from collections import Counter
    compos = Counter()
    for membres in vac.values():
        c = {4: 0, 5: 0, 6: 0}
        for m in membres:
            c[annee(m)] += 1
        signature = "/".join(str(c[a]) for a in (4, 5, 6))
        compos[signature] += 1
    print(f"\n  Compositions (4A/5A/6A par vacation) :")
    for sig, n in compos.most_common():
        print(f"     {sig} : {n}")

    # équité intra-promo
    for a in (4, 5, 6):
        codes = [c for c, i in ETUDIANTS.items()
                 if i.get("annee") == a and not i.get("erasmus")]
        vals = [len(affectations.get(c, [])) for c in codes]
        actifs = [v for v in vals if v > 0]
        print(f"\n  {a}A : {len(actifs)}/{len(vals)} ont ≥1")
        if vals:
            print(f"     min={min(vals)}, max={max(vals)}, "
                  f"moy={statistics.mean(vals):.1f}, σ={statistics.pstdev(vals):.2f}")

    non_pleines = sum(1 for m in vac.values() if len(m) != PLACES_PAR_VACATION)
    print(f"\n  Salles non pleines : {non_pleines}/{len(vac)}")

    if alertes:
        vrais = [a for a in alertes if "vide" not in a]
        print(f"\n  ⚠️  {len(alertes)} alerte(s) "
              f"({len(vrais)} 'salle non pleine' hors fériés) :")
        for a in alertes[:6]:
            print(f"     - {a}")


def main(export=None):
    ecrire = export if export is not None else ("--export" in sys.argv)
    data = charger(dossier_entree())
    affectations, alertes = placer(data)
    rapport(affectations, alertes)
    exporter(data, affectations, ecrire)


if __name__ == "__main__":
    main()