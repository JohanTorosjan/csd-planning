# ============================================================
#  pedo_6a.py — Étape 4 de Pédo-soin : placement des 6A
#
#  Les 6A sont placés PÉRIODE PAR PÉRIODE (ils partent et reviennent
#  de stage). À chaque période :
#    - sièges disponibles = places libres des groupes mixtes 5A
#                         + groupes 6A "purs" sur les créneaux que
#                           les 5A n'utilisent pas cette période
#    - dans chaque groupe on réserve RESERVE_4A places pour les 4A
#    - on affecte les 6A PRÉSENTS (>= 3 semaines libres sur un créneau)
#    - priorité aux 6A les moins servis (équité atteignable)
#    - continuité : garder un 6A dans le même groupe qu'à la période
#      précédente quand c'est possible
#
#  Un 6A n'occupe que les semaines où il est réellement libre.
#  Ce qui manque au quota sera rattrapé en période 5.
#
#  Usage : python3 pedo_6a.py            (aperçu)
#          python3 pedo_6a.py --export   (écrit planning_csv_pedo)
# ============================================================

import os
import csv
import sys
import statistics
from collections import defaultdict

from etudiants import ETUDIANTS
from donnees import INDISPO_PROMO, SEMAINES_FERMEES

import pedo_groupes as pg
import pedo_export as pe

DOSSIER_ENTREE = "planning_csv_ss"      # source des disponibilités 6A
DOSSIER_PEDO = "planning_csv_pedo"      # déjà rempli des 5A (in/out)
VIDE = "—"

RESERVE_4A = 4          # places gardées pour les 4A dans chaque groupe
CAPACITE = 20
QUOTA_6A = 16
PRESENT_MIN = 3         # séances libres mini pour être "présent" une période
PLAFOND_SOUPLE = 18     # au-delà, un 6A devient très coûteux à servir

CRENEAUX = pg.CRENEAUX
IDX = pg.IDX
MOITIES = pg.MOITIES


def _ordre(s):
    return s if s >= 36 else s + 100


def creneau_ouvert_6a(sem, creneau):
    if sem in SEMAINES_FERMEES:
        return False
    return not any((j, m) == creneau
                   for (j, m), _ in INDISPO_PROMO.get("6A", {}).get(sem, []))


# ============================================================
#  Disponibilité des 6A
# ============================================================

def libres_6a(dossier=DOSSIER_ENTREE):
    """{code: {creneau: set(semaines libres)}}"""
    res = {}
    for nom in os.listdir(dossier):
        if not nom.endswith(".csv"):
            continue
        code = nom[:-4]
        info = ETUDIANTS.get(code, {})
        if info.get("annee") != 6 or info.get("erasmus"):
            continue
        libres = defaultdict(set)
        with open(os.path.join(dossier, nom), encoding="utf-8") as f:
            for ligne in csv.reader(f):
                if len(ligne) >= 12 and ligne[0].isdigit():
                    sem = int(ligne[0])
                    for c in CRENEAUX:
                        if ligne[IDX[c]] == VIDE:
                            libres[c].add(sem)
        res[code] = dict(libres)
    return res


def seances_sur(code, creneau, sems_periode, libres):
    """Semaines de la période où le 6A est libre sur ce créneau."""
    return {s for s in sems_periode
            if creneau_ouvert_6a(s, creneau) and s in libres[code].get(creneau, set())}


# ============================================================
#  Sièges disponibles par période
# ============================================================

def _creneaux_avec_4a(P):
    """
    {periode: set(creneaux)} où au moins un 4A est disponible.
    Sert à ne réserver des places 4A que là où des 4A peuvent venir :
    ailleurs, la réserve est libérée au profit des 6A.
    Autonome (lit les CSV directement) pour éviter d'importer pedo_4a.
    """
    from etudiants import ETUDIANTS
    libres = defaultdict(lambda: defaultdict(set))  # code -> creneau -> sems
    for nom in os.listdir(DOSSIER_ENTREE):
        if not nom.endswith(".csv"):
            continue
        code = nom[:-4]
        info = ETUDIANTS.get(code, {})
        if info.get("annee") != 4 or info.get("erasmus"):
            continue
        with open(os.path.join(DOSSIER_ENTREE, nom), encoding="utf-8") as f:
            for ligne in csv.reader(f):
                if len(ligne) >= 12 and ligne[0].isdigit():
                    sem = int(ligne[0])
                    for c in CRENEAUX:
                        if ligne[IDX[c]] == VIDE:
                            libres[code][c].add(sem)

    res = defaultdict(set)
    for per in (1, 2, 3, 4):
        for c in CRENEAUX:
            for code in libres:
                if any(s in libres[code].get(c, set())
                       and creneau_ouvert_6a(s, c) for s in P[per]):
                    res[per].add(c)
                    break
    return res


def reserve_4a(per, creneau, creneaux_4a):
    """RESERVE_4A si des 4A peuvent venir sur ce créneau/période, sinon 0
    (places libérées pour les 6A)."""
    return RESERVE_4A if creneau in creneaux_4a.get(per, set()) else 0


def sieges_par_periode(groupes5, P):
    """
    {periode: [ {nom, creneau, capacite_6a, pur} ]}
    Les groupes mixtes cèdent leurs places restantes ; sur les créneaux
    libres des 5A, on ouvre des groupes 6A purs.

    La réserve 4A est CONDITIONNELLE : on ne garde 4 places pour les 4A
    que sur les créneaux/périodes où des 4A sont réellement disponibles.
    Ailleurs, ces places reviennent aux 6A (pas de gaspillage).
    """
    creneaux_4a = _creneaux_avec_4a(P)
    sieges = defaultdict(list)
    occupe = defaultdict(dict)

    for g in groupes5:
        for per in g["periodes"]:
            c = g["creneau"][per]
            occupe[per][c] = g["nom"]
            cap = CAPACITE - len(g["membres"]) - reserve_4a(per, c, creneaux_4a)
            if cap > 0:
                sieges[per].append({
                    "nom": g["nom"], "creneau": c,
                    "capacite": cap, "pur": False})

    for per in (1, 2, 3, 4):
        moitie = "A" if per in (1, 2) else "B"
        for c in CRENEAUX:
            if c in occupe[per]:
                continue
            if not any(creneau_ouvert_6a(s, c) for s in P[per]):
                continue
            sieges[per].append({
                "nom": f"PEDO-6A-{moitie}-{c[0][:3]}{c[1]}",
                "creneau": c,
                "capacite": CAPACITE - reserve_4a(per, c, creneaux_4a),
                "pur": True})
    return sieges


# ============================================================
#  Affectation d'une période (flot pondéré par équité + continuité)
# ============================================================

INF = 10 ** 9


class _FlotCout:
    """Flot maximum à coût minimum (SPFA + envois successifs)."""
    def __init__(self, n):
        self.n = n
        self.g = [[] for _ in range(n)]

    def ajouter(self, u, v, cap, cout):
        self.g[u].append([v, cap, cout, len(self.g[v])])
        self.g[v].append([u, 0, -cout, len(self.g[u]) - 1])
        return (u, len(self.g[u]) - 1)

    def flot(self, s, t):
        total, cost = 0, 0
        while True:
            dist = [INF] * self.n
            dans = [False] * self.n
            prev = [(-1, -1)] * self.n
            dist[s] = 0
            file = [s]
            while file:
                u = file.pop(0)
                dans[u] = False
                for i, (v, cap, cout, _) in enumerate(self.g[u]):
                    if cap > 0 and dist[u] + cout < dist[v]:
                        dist[v] = dist[u] + cout
                        prev[v] = (u, i)
                        if not dans[v]:
                            dans[v] = True
                            file.append(v)
            if dist[t] == INF:
                break
            # pousser 1 unité (les capacités unitaires dominent ici)
            f = INF
            v = t
            while v != s:
                u, i = prev[v]
                f = min(f, self.g[u][i][1])
                v = u
            v = t
            while v != s:
                u, i = prev[v]
                self.g[u][i][1] -= f
                r = self.g[u][i][3]
                self.g[v][r][1] += f
                v = u
            total += f
            cost += f * dist[t]
        return total, cost


def affecter_periode(per, sieges, presents, libres, P, deja_servi,
                     groupe_precedent, rarete):
    """
    Renvoie {code: (nom_groupe, creneau, set(semaines))} pour cette période.

    Deux règles d'équité (cible = QUOTA_6A séances) :

    1. PLAFOND SOUPLE : un 6A ayant déjà atteint le quota passe en fin de
       priorité. Il n'occupe un siège que si la capacité n'a pas été
       épuisée par les retardataires (sinon le siège resterait vide).

    2. PRIORITÉ AUX CONTRAINTS : parmi les retardataires, on sert d'abord
       ceux qui ont le moins de PÉRIODES disponibles sur l'année (rareté
       faible), car ils ont peu d'occasions de rattraper. À rareté égale,
       le moins servi d'abord ; puis le plus contraint dans la période.

    Le flot optimise ensuite, parmi les retenus, QUEL siège (créneau)
    donne le plus de séances à chacun.
    """
    sems = P[per]
    capacite_totale = sum(s["capacite"] for s in sieges)

    # sièges éligibles pour chaque 6A présent
    elig = {}
    for code in presents:
        opts = []
        for idx, s in enumerate(sieges):
            sur = seances_sur(code, s["creneau"], sems, libres)
            if len(sur) >= PRESENT_MIN:
                opts.append(idx)
        if opts:
            elig[code] = opts

    candidats = [c for c in presents if c in elig]

    # clé de tri :
    #  - d'abord les retardataires (0), les 6A au quota ensuite (1)  [plafond]
    #  - puis rareté croissante (moins de périodes dispo = prioritaire)
    #  - puis déjà servi croissant (les moins servis d'abord)
    #  - puis peu d'options dans la période (les plus contraints)
    def cle(c):
        au_quota = 1 if deja_servi.get(c, 0) >= QUOTA_6A else 0
        return (au_quota, rarete.get(c, 99), deja_servi.get(c, 0), len(elig[c]))

    candidats.sort(key=cle)

    # on ne retient que ce que la capacité permet de placer
    retenus = candidats[:capacite_totale]

    # flot à coût min : parmi les retenus, choisir le siège qui rapporte
    # le plus de séances (coût = -séances) avec bonus de continuité
    S, T = 0, 1
    base_c = 2
    base_s = base_c + len(retenus)
    n = base_s + len(sieges)
    F = _FlotCout(n)
    idx_code = {c: i for i, c in enumerate(retenus)}

    for c in retenus:
        F.ajouter(S, base_c + idx_code[c], 1, 0)

    for c in retenus:
        for idx in elig[c]:
            s = sieges[idx]
            gagne = len(seances_sur(c, s["creneau"], sems, libres))
            cont = 0 if groupe_precedent.get(c) == s["nom"] else 1
            # coût principal : moins de séances = plus cher (on maximise)
            cout = (20 - gagne) * 10 + cont
            F.ajouter(base_c + idx_code[c], base_s + idx, 1, cout)

    for idx, s in enumerate(sieges):
        F.ajouter(base_s + idx, T, s["capacite"], 0)

    F.flot(S, T)

    resultat = {}
    for c in retenus:
        u = base_c + idx_code[c]
        for (v, cap, cout, rev) in F.g[u]:
            if base_s <= v < base_s + len(sieges) and cap == 0:
                idx = v - base_s
                s = sieges[idx]
                sur = seances_sur(c, s["creneau"], sems, libres)
                resultat[c] = (s["nom"], s["creneau"], sur)
                break
    return resultat


# ============================================================
#  Construction complète
# ============================================================

def placer_6a():
    groupes5, P, _ = pe.construire()
    libres = libres_6a()
    sieges = sieges_par_periode(groupes5, P)
    codes6 = sorted(libres)

    # RARETÉ : nombre de périodes (P1 à P5) où le 6A pourrait faire ses
    # séances. On inclut la PÉRIODE 5 (rattrapage) car un 6A absent en P5
    # ne pourra pas y rattraper : il est donc PLUS contraint et doit être
    # servi en priorité pendant P1-4. Un 6A encore présent en P5 a une
    # marge. (Il n'y a pas de 6A en période 6.)
    #
    # Pour P1-4 on regarde les sièges réels ; pour P5, les sièges du
    # rattrapage ne sont pas encore modélisés, donc on se fonde sur la
    # simple DISPONIBILITÉ du 6A (a-t-il des créneaux libres en P5 ?).
    rarete = {}
    for c in codes6:
        n = 0
        for per in (1, 2, 3, 4):
            if any(len(seances_sur(c, s["creneau"], P[per], libres)) >= PRESENT_MIN
                   for s in sieges[per]):
                n += 1
        # période 5 : disponibilité brute sur les créneaux Pédo
        if 5 in P and any(len(seances_sur(c, cr, P[5], libres)) >= PRESENT_MIN
                          for cr in CRENEAUX):
            n += 1
        rarete[c] = n

    deja_servi = defaultdict(int)
    groupe_precedent = {}
    placement = defaultdict(dict)   # periode -> {code: (nom, creneau, sems)}

    for per in (1, 2, 3, 4):
        presents = [c for c in codes6
                    if any(len(seances_sur(c, s["creneau"], P[per], libres))
                           >= PRESENT_MIN for s in sieges[per])]
        res = affecter_periode(per, sieges[per], presents, libres, P,
                               deja_servi, groupe_precedent, rarete)
        for code, (nom, creneau, sems) in res.items():
            placement[per][code] = (nom, creneau, sems)
            deja_servi[code] += len(sems)
            groupe_precedent[code] = nom

    return groupes5, P, libres, sieges, placement, deja_servi


# ============================================================
#  Export
# ============================================================

def exporter(placement, ecrire):
    data = {}
    for nom in os.listdir(DOSSIER_PEDO):
        if nom.endswith(".csv"):
            with open(os.path.join(DOSSIER_PEDO, nom), encoding="utf-8") as f:
                data[nom[:-4]] = [list(l) for l in csv.reader(f)]
    index = {code: {int(l[0]): i for i, l in enumerate(lignes)
                    if len(l) >= 12 and l[0].isdigit()}
             for code, lignes in data.items()}

    conflits, ecrits = [], 0
    for per, aff in placement.items():
        for code, (nom, creneau, sems) in aff.items():
            for s in sems:
                i = index[code][s]
                col = IDX[creneau]
                actuel = data[code][i][col]
                if actuel != VIDE:
                    conflits.append(
                        f"{code} sem {s} {creneau[0]} {creneau[1]} : "
                        f"trouvé '{actuel}'")
                    continue
                if ecrire:
                    data[code][i][col] = f"Pédo-soin ({nom})"
                ecrits += 1

    if conflits:
        print(f"\n⚠️  {len(conflits)} conflit(s) — rien n'est écrit :")
        for c in conflits[:12]:
            print(f"     {c}")
        raise SystemExit("Disponibilité 6A mal calculée.")

    print(f"\n  {ecrits} séances 6A placées, sans conflit.")
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

def rapport(groupes5, sieges, placement, deja_servi):
    print("=" * 66)
    print("  PÉDO-SOIN — PLACEMENT DES 6A")
    print("=" * 66)

    for per in (1, 2, 3, 4):
        aff = placement[per]
        purs = sum(1 for s in sieges[per] if s["pur"])
        print(f"\n  Période {per} : {len(aff)} 6A placés, "
              f"{len(sieges[per])} sièges ({purs} groupe(s) pur(s))")
        par_groupe = defaultdict(int)
        for code, (nom, _, _) in aff.items():
            par_groupe[nom] += 1
        for nom in sorted(par_groupe):
            print(f"      {nom:22s} : {par_groupe[nom]} 6A")

    print("\n  " + "=" * 60)
    print("  ÉQUITÉ (séances 6A sur périodes 1-4)")
    vals = [deja_servi[c] for c in deja_servi]
    tous = [deja_servi.get(c, 0)
            for c in ETUDIANTS
            if ETUDIANTS[c].get("annee") == 6
            and not ETUDIANTS[c].get("erasmus")]
    if tous:
        print(f"    n={len(tous)}, min={min(tous)}, max={max(tous)}, "
              f"moy={statistics.mean(tous):.1f}, "
              f"méd={statistics.median(tous):.0f}, "
              f"σ={statistics.pstdev(tous):.2f}")
        atteint = sum(1 for v in tous if v >= QUOTA_6A)
        print(f"    {atteint}/{len(tous)} atteignent {QUOTA_6A} séances "
              f"dès la période 4")
        manque = sum(max(0, QUOTA_6A - v) for v in tous)
        print(f"    séances à rattraper en P5 : {manque} "
              f"(~{manque / len(tous):.1f} par 6A)")

    # stabilité : changements de groupe
    change = 0
    for per in (2, 3, 4):
        for code in placement[per]:
            if code in placement[per - 1]:
                if placement[per][code][0] != placement[per - 1][code][0]:
                    change += 1
    print(f"\n  Stabilité : {change} changements de groupe entre périodes "
          f"consécutives")


def main(export=None):
    ecrire = export if export is not None else ("--export" in sys.argv)
    groupes5, P, libres, sieges, placement, deja_servi = placer_6a()
    rapport(groupes5, sieges, placement, deja_servi)
    exporter(placement, ecrire)


if __name__ == "__main__":
    main()