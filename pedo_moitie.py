# ============================================================
#  pedo_moities.py — Étape 1 de Pédo-soin
#
#  Découpe les 5A en deux moitiés équilibrées par type :
#     moitié A -> périodes 1+2      moitié B -> périodes 3+4
#
#  Puis REMESURE la disponibilité sur les membres réels de chaque
#  moitié, et non sur la promotion entière : un groupe ne contient
#  qu'une fraction de chaque type, donc l'intersection des semaines
#  libres est bien plus large que ce qu'un calcul sur les 15 laisse
#  croire.
#
#  Usage : python3 pedo_moities.py
# ============================================================

import os
import csv
from collections import defaultdict

from etudiants import ETUDIANTS
from donnees import INDISPO_PROMO, SEMAINES_FERMEES

DOSSIER = "planning_csv_ss"

PEDO_DEBUT = None  # obsolète : les périodes viennent de pedo_groupes
MOITIES = {"A": (1, 2), "B": (3, 4)}

CRENEAUX = [("lundi", "M"), ("mercredi", "M"), ("mercredi", "AM"),
            ("jeudi", "M"), ("vendredi", "M")]

COLONNES = [("lundi", "M"), ("lundi", "AM"), ("mardi", "M"), ("mardi", "AM"),
            ("mercredi", "M"), ("mercredi", "AM"), ("jeudi", "M"),
            ("jeudi", "AM"), ("vendredi", "M"), ("vendredi", "AM")]
IDX = {c: 2 + i for i, c in enumerate(COLONNES)}

VIDE = "—"
TYPES = range(1, 6)


def _ordre(s):
    return s if s >= 36 else s + 100


TOUTES = sorted(list(range(36, 53)) + list(range(1, 36)), key=_ordre)


# ============================================================
#  Calendrier
# ============================================================

def periodes():
    """Délègue à pedo_groupes (source unique des périodes Pédo)."""
    import pedo_groupes as pg
    return pg.periodes()


def creneau_ouvert(sem, creneau):
    """Ouvert = pas de fermeture, pas de cours/férié/examen pour les 5A."""
    if sem in SEMAINES_FERMEES:
        return False
    return not any((j, m) == creneau
                   for (j, m), _ in INDISPO_PROMO.get("5A", {}).get(sem, []))


# ============================================================
#  Découpage en deux moitiés
# ============================================================

def cinquiemes_par_type():
    par_type = defaultdict(list)
    for code, info in ETUDIANTS.items():
        if info.get("annee") == 5 and not info.get("erasmus"):
            par_type[info["type"]].append(code)
    for t in par_type:
        par_type[t].sort()
    return dict(par_type)


def decouper():
    """Alterne les étudiants de chaque type entre A et B."""
    par_type = cinquiemes_par_type()
    moities = {"A": [], "B": []}
    for t in sorted(par_type):
        for i, code in enumerate(par_type[t]):
            moities["A" if i % 2 == 0 else "B"].append(code)
    return moities, par_type


# ============================================================
#  Disponibilité
# ============================================================

def semaines_libres_par_etudiant():
    """{code: {creneau: set(semaines libres)}}"""
    res = {}
    for nom in os.listdir(DOSSIER):
        if not nom.endswith(".csv"):
            continue
        code = nom[:-4]
        info = ETUDIANTS.get(code, {})
        if info.get("annee") != 5 or info.get("erasmus"):
            continue
        libres = defaultdict(set)
        with open(os.path.join(DOSSIER, nom), encoding="utf-8") as f:
            for ligne in csv.reader(f):
                if len(ligne) >= 12 and ligne[0].isdigit():
                    sem = int(ligne[0])
                    for c in CRENEAUX:
                        if ligne[IDX[c]] == VIDE:
                            libres[c].add(sem)
        res[code] = libres
    return res


def seances(codes, creneau, sems_periode, libres):
    """Semaines où le créneau est ouvert ET tous ces codes sont libres."""
    ok = set(s for s in sems_periode if creneau_ouvert(s, creneau))
    for code in codes:
        ok &= libres[code][creneau]
    return ok


# ============================================================
#  Affichage
# ============================================================

def afficher_moities(moities, par_type):
    print("=" * 68)
    print("  DÉCOUPAGE DES 5A EN DEUX MOITIÉS")
    print("=" * 68)
    print(f"\n  {len(par_type)} types, "
          f"{sum(len(v) for v in par_type.values())} étudiants\n")
    print(f"  {'':10s}" + "".join(f"  type {t}" for t in TYPES) + "   total")
    for nom in ("A", "B"):
        codes = moities[nom]
        ligne = f"  moitié {nom}  "
        for t in TYPES:
            n = sum(1 for c in codes if ETUDIANTS[c]["type"] == t)
            ligne += f"{n:7d}"
        ligne += f"{len(codes):8d}"
        print(ligne)
    print(f"\n  moitié A -> périodes 1+2      moitié B -> périodes 3+4")


def afficher_disponibilite(moities, libres, P):
    for nom in ("A", "B"):
        p1, p2 = MOITIES[nom]
        codes = moities[nom]
        print("\n" + "=" * 68)
        print(f"  MOITIÉ {nom} — périodes {p1}+{p2} — {len(codes)} étudiants")
        print("=" * 68)

        # par type, sur les membres RÉELS de la moitié
        print("\n  Séances possibles pour un groupe MONO-TYPE de cette moitié")
        print("  (mesuré sur les membres réels, pas sur les 15 du type)\n")
        entete = f"    {'':8s}" + "".join(f"{c[0][:3] + c[1]:>10s}"
                                          for c in CRENEAUX)
        print(entete)
        for t in TYPES:
            membres = [c for c in codes if ETUDIANTS[c]["type"] == t]
            if not membres:
                continue
            ligne = f"    type {t} "
            for c in CRENEAUX:
                n = sum(len(seances(membres, c, P[p], libres))
                        for p in (p1, p2))
                ligne += f"{n:>10d}"
            ligne += f"   ({len(membres)} étudiants)"
            print(ligne)

        # détail par période
        for p in (p1, p2):
            ouverts = [c for c in CRENEAUX
                       if any(creneau_ouvert(s, c) for s in P[p])]
            print(f"\n  Période {p} : {len(ouverts)} créneau(x) exploitable(s)")
            for c in CRENEAUX:
                total = sum(1 for s in P[p] if creneau_ouvert(s, c))
                if total == 0:
                    print(f"    {c[0]:9s} {c[1]:<3s} : fermé (cours 5A)")
                    continue
                detail = []
                for t in TYPES:
                    membres = [x for x in codes if ETUDIANTS[x]["type"] == t]
                    if membres:
                        detail.append(
                            f"t{t}:{len(seances(membres, c, P[p], libres))}")
                print(f"    {c[0]:9s} {c[1]:<3s} : {total} sem ouvertes   "
                      + " ".join(detail))


def afficher_synthese(moities, libres, P):
    print("\n" + "=" * 68)
    print("  SYNTHÈSE")
    print("=" * 68)
    for nom in ("A", "B"):
        p1, p2 = MOITIES[nom]
        codes = moities[nom]
        best = {}
        for t in TYPES:
            membres = [c for c in codes if ETUDIANTS[c]["type"] == t]
            if not membres:
                continue
            best[t] = max(
                sum(len(seances(membres, c, P[p], libres)) for p in (p1, p2))
                for c in CRENEAUX)
        if not best:
            continue
        print(f"\n  Moitié {nom} — meilleur créneau unique, par type :")
        for t, n in sorted(best.items()):
            etat = "OK" if n >= 16 else f"sous le quota ({16 - n} manquante(s))"
            print(f"    type {t} : {n:2d} séances   {etat}")
        print(f"    -> le changement de créneau entre les 2 périodes peut "
              f"améliorer ces chiffres")


# ============================================================
#  Point d'entrée
# ============================================================

def main():
    if not os.path.isdir(DOSSIER):
        raise SystemExit(f"Dossier introuvable : {DOSSIER}")
    P = periodes()
    moities, par_type = decouper()
    libres = semaines_libres_par_etudiant()

    afficher_moities(moities, par_type)
    afficher_disponibilite(moities, libres, P)
    afficher_synthese(moities, libres, P)


if __name__ == "__main__":
    main()