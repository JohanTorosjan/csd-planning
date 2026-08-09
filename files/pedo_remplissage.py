# ============================================================
#  pedo_remplissage.py — Étape 6 (dernière) de Pédo-soin
#
#  Comble les places vides de la salle avec les 5A et 6A qui ont
#  le MOINS de séances (équité intra-promo), sans créer de doublon.
#
#  Principe :
#    - on parcourt chaque (créneau, semaine) ayant des places libres
#      (capacité CAPACITE non atteinte après 5A+6A+4A),
#    - candidats = 5A et 6A qui sont :
#        • disponibles cette semaine sur ce créneau (cellule « — »),
#        • PAS actifs en Pédo cette PÉRIODE (jamais 2 Pédo dans une
#          période où l'étudiant a déjà son créneau stable),
#        • les MOINS servis de leur promo d'abord,
#    - la salle prime : on comble même si le candidat dépasse 16.
#    - l'étudiant rejoint le GROUPE qui occupe le créneau, avec un
#      flag [remplissage] pour la traçabilité.
#
#  Entrée/sortie : planning_csv_pedo (in place).
#
#  Usage : python3 pedo_remplissage.py            (aperçu)
#          python3 pedo_remplissage.py --export   (écrit les CSV)
# ============================================================

import os
import csv
import sys
import statistics
from collections import defaultdict

from etudiants import ETUDIANTS

import pedo_groupes as pg

DOSSIER_PEDO = "planning_csv_pedo"
VIDE = "—"
CAPACITE = 20

CRENEAUX = pg.CRENEAUX
IDX = pg.IDX


def _ordre(s):
    return s if s >= 36 else s + 100


def periode_de(sem, P):
    """Numéro de période contenant cette semaine."""
    for per, sems in P.items():
        if sem in sems:
            return per
    return None


# ============================================================
#  Lecture de l'état actuel
# ============================================================

def charger():
    """Charge planning_csv_pedo. Renvoie {code: {sem: [cellules]}}."""
    data = {}
    for nom in os.listdir(DOSSIER_PEDO):
        if nom.endswith(".csv"):
            with open(os.path.join(DOSSIER_PEDO, nom), encoding="utf-8") as f:
                cells = {}
                lignes = []
                for l in csv.reader(f):
                    lignes.append(list(l))
                data[nom[:-4]] = lignes
    return data


def est_pedo(cell):
    return "édo" in cell


def analyser(data):
    """
    Analyse l'état actuel. Renvoie :
      occupation : {(sem, creneau): nb d'étudiants en Pédo}
      groupe_creneau : {(sem, creneau): nom_groupe dominant}
      seances_promo : {code: nb de séances Pédo}
      pedo_periodes : {code: set(périodes où l'étudiant est actif en Pédo)}
      index : {code: {sem: ligne_index}}
    """
    P = pg.periodes()
    occupation = defaultdict(int)
    groupe_compte = defaultdict(lambda: defaultdict(int))
    seances = defaultdict(int)
    pedo_periodes = defaultdict(set)
    index = {}

    for code, lignes in data.items():
        idx = {}
        for i, l in enumerate(lignes):
            if len(l) >= 12 and l[0].isdigit():
                sem = int(l[0])
                idx[sem] = i
                for cr in CRENEAUX:
                    cell = l[IDX[cr]]
                    if est_pedo(cell):
                        occupation[(sem, cr)] += 1
                        seances[code] += 1
                        per = periode_de(sem, P)
                        if per:
                            pedo_periodes[code].add(per)
                        # extraire le nom du groupe entre parenthèses
                        nom = cell
                        if "(" in cell and ")" in cell:
                            nom = cell[cell.index("(") + 1:cell.index(")")]
                        groupe_compte[(sem, cr)][nom] += 1
        index[code] = idx

    groupe_creneau = {}
    for key, comptes in groupe_compte.items():
        groupe_creneau[key] = max(comptes, key=comptes.get)

    return occupation, groupe_creneau, seances, pedo_periodes, index


# ============================================================
#  Disponibilité (cellule libre dans le CSV pédo lui-même)
# ============================================================

def libre_sur(data, index, code, sem, creneau):
    """L'étudiant a-t-il sa cellule libre (—) cette semaine/créneau ?"""
    i = index.get(code, {}).get(sem)
    if i is None:
        return False
    return data[code][i][IDX[creneau]] == VIDE


# ============================================================
#  Remplissage
# ============================================================

def combler(data):
    P = pg.periodes()
    occupation, groupe_creneau, seances, pedo_periodes, index = analyser(data)

    # codes 5A et 6A (hors Erasmus)
    codes = {5: [], 6: []}
    for code, info in ETUDIANTS.items():
        if info.get("erasmus"):
            continue
        a = info.get("annee")
        if a in (5, 6):
            codes[a].append(code)

    # liste des trous : (sem, creneau, places_vides), triés
    trous = []
    for sem in range(1, 53):
        for cr in CRENEAUX:
            key = (sem, cr)
            if key not in groupe_creneau:
                continue   # créneau non utilisé en Pédo cette semaine
            vide = CAPACITE - occupation[key]
            if vide > 0:
                trous.append((sem, cr, vide))

    ajouts = []   # (code, sem, creneau, nom_groupe)
    ajouts_set = set()   # (code, sem, cr) déjà ajoutés — lookup rapide
    # on comble trou par trou ; à chaque place, le candidat le moins servi
    for sem, cr, vide in trous:
        per = periode_de(sem, P)
        nom_groupe = groupe_creneau[(sem, cr)]
        for _ in range(vide):
            # candidats : 5A puis 6A, disponibles, pas actifs cette période
            meilleur = None
            for promo in (5, 6):
                for code in codes[promo]:
                    if per in pedo_periodes.get(code, set()):
                        continue   # déjà actif en Pédo cette période
                    if (code, sem, cr) in ajouts_set:
                        continue
                    if not libre_sur(data, index, code, sem, cr):
                        continue
                    sc = seances.get(code, 0)
                    if meilleur is None or sc < meilleur[1]:
                        meilleur = (code, sc)
            if meilleur is None:
                break   # plus de candidat pour ce trou
            code = meilleur[0]
            ajouts.append((code, sem, cr, nom_groupe))
            ajouts_set.add((code, sem, cr))
            seances[code] += 1
            occupation[(sem, cr)] += 1
            # marquer l'étudiant actif cette période (évite 2e Pédo/période)
            pedo_periodes[code].add(per)

    return ajouts, seances


# ============================================================
#  Export
# ============================================================

def exporter(data, ajouts, ecrire):
    index = {}
    for code, lignes in data.items():
        idx = {int(l[0]): i for i, l in enumerate(lignes)
               if len(l) >= 12 and l[0].isdigit()}
        index[code] = idx

    conflits = 0
    for code, sem, cr, nom in ajouts:
        i = index[code][sem]
        col = IDX[cr]
        if data[code][i][col] != VIDE:
            conflits += 1
            continue
        if ecrire:
            data[code][i][col] = f"Pédo-soin ({nom}) [remplissage]"

    if conflits:
        print(f"\n⚠️  {conflits} conflit(s) détecté(s) — non écrits")

    print(f"\n  {len(ajouts) - conflits} places comblées par remplissage.")
    if ecrire:
        for code, lignes in data.items():
            with open(os.path.join(DOSSIER_PEDO, f"{code}.csv"), "w",
                      newline="", encoding="utf-8") as f:
                csv.writer(f).writerows(lignes)
        print(f"  CSV mis à jour dans {DOSSIER_PEDO}/")
    else:
        print("  (aperçu — ajouter --export pour écrire)")


# ============================================================
#  Rapport
# ============================================================

def rapport(ajouts, seances):
    print("=" * 66)
    print("  PÉDO-SOIN — REMPLISSAGE DES TROUS")
    print("=" * 66)

    par_promo = defaultdict(int)
    for code, sem, cr, nom in ajouts:
        par_promo[ETUDIANTS[code].get("annee")] += 1
    print(f"\n  {len(ajouts)} places comblées :")
    for a in sorted(par_promo):
        print(f"      {par_promo[a]} par des {a}A")

    # équité après remplissage, par promo
    for promo in (5, 6):
        vals = [seances.get(c, 0) for c, i in ETUDIANTS.items()
                if i.get("annee") == promo and not i.get("erasmus")]
        if vals:
            print(f"\n  Équité {promo}A après remplissage :")
            print(f"    min={min(vals)}, max={max(vals)}, "
                  f"moy={statistics.mean(vals):.1f}, "
                  f"méd={statistics.median(vals):.0f}, "
                  f"σ={statistics.pstdev(vals):.2f}")


def main(export=None):
    ecrire = export if export is not None else ("--export" in sys.argv)
    data = charger()
    ajouts, seances = combler(data)
    rapport(ajouts, seances)
    exporter(data, ajouts, ecrire)


if __name__ == "__main__":
    main()
