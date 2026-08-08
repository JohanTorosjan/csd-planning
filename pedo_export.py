# ============================================================
#  pedo_export.py — Étape 3 de Pédo-soin (5A seulement)
#
#  Reconstruit les groupes de 5A via pedo_groupes.chercher, choisit
#  nominativement leurs membres, puis écrit une séance de Pédo dans
#  chaque cellule "—" correspondante.
#
#  Comme pour le service sanitaire, l'export REFUSE d'écrire si une
#  cellule visée n'est pas libre : c'est le garde-fou qui valide le
#  raisonnement sur la disponibilité.
#
#  Entrée : planning_csv_ss/   Sortie : planning_csv_pedo/
#
#  Usage : python3 pedo_export.py            (aperçu)
#          python3 pedo_export.py --export   (écrit les CSV)
# ============================================================

import os
import csv
import sys
from collections import defaultdict

from etudiants import ETUDIANTS

import pedo_groupes as pg

DOSSIER_ENTREE = "planning_csv_ss"
DOSSIER_SORTIE = "planning_csv_pedo"
VIDE = "—"


# ============================================================
#  Construction nominative des groupes
# ============================================================

def construire():
    P = pg.periodes()
    moities = pg.decouper()
    libres = pg.libres_par_etudiant()

    groupes = []          # dict par groupe
    for nom in ("A", "B"):
        pair = pg.MOITIES[nom]
        p1, p2 = pair
        res = pg.chercher(nom, moities[nom], P, libres)
        meilleur, _, _, n_util, taille_util, degrade = res
        if meilleur is None:
            raise SystemExit(f"Moitié {nom} : aucune configuration faisable.")
        score, c1, c2, rep, totaux = meilleur
        if degrade:
            print(f"  ⚠️  Moitié {nom} : taille dégradée "
                  f"{taille_util[0]}-{taille_util[1]} utilisée.")

        # piocher les vrais codes selon la répartition rep[(type, groupe)]
        restants = {t: list(v) for t, v in moities[nom].items()}
        for g in range(n_util):
            membres = []
            for t in sorted(pg.TYPES):
                n = rep.get((t, g), 0)
                for _ in range(n):
                    membres.append(restants[t].pop(0))
            groupes.append({
                "nom": f"PEDO-{nom}{g + 1}",
                "moitie": nom,
                "membres": sorted(membres),
                "creneau": {p1: c1[g], p2: c2[g]},
                "periodes": pair,
                "seances_prevues": totaux[g],
            })

        reste = {t: v for t, v in restants.items() if v}
        if reste:
            raise SystemExit(f"Moitié {nom} : 5A non affectés {reste}")

    return groupes, P, libres


# ============================================================
#  Séances effectives d'un groupe
# ============================================================

def seances_groupe(groupe, P, libres):
    """[(semaine, jour, moment)] où le groupe siège réellement."""
    membres = groupe["membres"]
    cellules = []
    for p in groupe["periodes"]:
        c = groupe["creneau"][p]
        sems = {s for s in P[p] if pg.creneau_ouvert(s, c)}
        for code in membres:
            sems &= libres[code][c]
        for s in sorted(sems, key=pg._ordre):
            cellules.append((s, c[0], c[1]))
    return cellules


# ============================================================
#  Export
# ============================================================

def _charger(dossier):
    data = {}
    for nom in os.listdir(dossier):
        if nom.endswith(".csv"):
            with open(os.path.join(dossier, nom), encoding="utf-8") as f:
                data[nom[:-4]] = [list(l) for l in csv.reader(f)]
    return data


def exporter(groupes, P, libres, ecrire):
    data = _charger(DOSSIER_ENTREE)
    index = {code: {int(l[0]): i for i, l in enumerate(lignes)
                    if len(l) >= 12 and l[0].isdigit()}
             for code, lignes in data.items()}

    conflits, prevus = [], 0
    ecrits_par_etudiant = defaultdict(int)

    for g in groupes:
        cellules = seances_groupe(g, P, libres)
        for code in g["membres"]:
            for (sem, j, m) in cellules:
                prevus += 1
                i = index[code][sem]
                col = pg.IDX[(j, m)]
                actuel = data[code][i][col]
                if actuel != VIDE:
                    conflits.append(
                        f"{code} sem {sem} {j} {m} : attendu '{VIDE}', "
                        f"trouvé '{actuel}'")
                    continue
                if ecrire:
                    data[code][i][col] = f"Pédo-soin ({g['nom']})"
                ecrits_par_etudiant[code] += 1

    if conflits:
        print(f"\n⚠️  {len(conflits)} conflit(s) — rien n'est écrit :")
        for c in conflits[:12]:
            print(f"     {c}")
        raise SystemExit("Disponibilité mal calculée.")

    print(f"\n  {prevus} séances de Pédo placées, sans conflit.")
    vals = list(ecrits_par_etudiant.values())
    if vals:
        import statistics
        print(f"  Par étudiant : min={min(vals)}, max={max(vals)}, "
              f"moy={statistics.mean(vals):.1f}")

    if not ecrire:
        print("\n  (aperçu — ajouter --export pour écrire les CSV)")
        return

    os.makedirs(DOSSIER_SORTIE, exist_ok=True)
    for code, lignes in data.items():
        with open(os.path.join(DOSSIER_SORTIE, f"{code}.csv"), "w",
                  newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(lignes)
    print(f"  CSV écrits dans {DOSSIER_SORTIE}/")


def afficher(groupes, P, libres):
    print("=" * 66)
    print("  GROUPES DE PÉDO-SOIN (5A)")
    print("=" * 66)
    for g in groupes:
        cellules = seances_groupe(g, P, libres)
        par_type = defaultdict(int)
        for code in g["membres"]:
            par_type[ETUDIANTS[code]["type"]] += 1
        compo = " ".join(f"t{t}:{n}" for t, n in sorted(par_type.items()))
        p1, p2 = g["periodes"]
        print(f"\n  {g['nom']}  ({len(g['membres'])} 5A : {compo})")
        print(f"    P{p1} : {g['creneau'][p1][0]} {g['creneau'][p1][1]}   "
              f"P{p2} : {g['creneau'][p2][0]} {g['creneau'][p2][1]}")
        print(f"    {len(cellules)} séances")
        print(f"    membres : {', '.join(g['membres'])}")


def main():
    ecrire = "--export" in sys.argv
    groupes, P, libres = construire()
    afficher(groupes, P, libres)
    exporter(groupes, P, libres, ecrire)


if __name__ == "__main__":
    main()