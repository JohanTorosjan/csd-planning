# ============================================================
#  pedo_groupes.py — Étape 2 de Pédo-soin
#
#  Forme les groupes de 5A et leur assigne un créneau par période.
#
#  Constat de l'étape 1 : la disponibilité est COLLECTIVE. Les 5A
#  d'un même type sont libres exactement aux mêmes semaines. Un type
#  se comporte donc comme un bloc pour le choix des créneaux, mais
#  ses étudiants peuvent être RÉPARTIS entre plusieurs groupes.
#
#  Un groupe siège sur un créneau qui convient à TOUS ses types.
#  Le créneau peut changer entre les deux périodes (les membres, non).
#
#  Recherche exhaustive :
#    - pour chaque période, affectation injective groupe -> créneau
#    - répartition des étudiants (flot exact, 8-12 par groupe)
#    - critère : maximiser les séances du groupe le plus mal loti
#
#  Usage : python3 pedo_groupes.py
# ============================================================

import os
import csv
from itertools import permutations, combinations
from collections import defaultdict

from etudiants import ETUDIANTS
from donnees import INDISPO_PROMO, SEMAINES_FERMEES

try:
    from donnees import PERIODES_PEDO
except ImportError:
    PERIODES_PEDO = None

DOSSIER = "planning_csv_ss"

# Bornes de secours si donnees.PERIODES_PEDO est absent (format début/fin).
_PERIODES_SECOURS = [(36, 44), (45, 1), (2, 8), (9, 17), (18, 27), (28, 35)]
MOITIES = {"A": (1, 2), "B": (3, 4)}
# Le nombre de groupes n'est PLUS codé en dur : il se calcule à partir
# de l'effectif de la moitié et de la fourchette de taille (voir
# nb_groupes ci-dessous). MOITIES reste la correspondance période.
MOITIES = {"A": (1, 2), "B": (3, 4)}

# Fourchette de taille des groupes. On vise TAILLE_CIBLE ; en dégradation
# (si aucune solution), on autorise TAILLE_DEGRADEE.
TAILLE_CIBLE = (8, 12)
TAILLE_DEGRADEE = (7, 13)

CRENEAUX = [("lundi", "M"), ("mercredi", "M"), ("mercredi", "AM"),
            ("jeudi", "M"), ("vendredi", "M")]

COLONNES = [("lundi", "M"), ("lundi", "AM"), ("mardi", "M"), ("mardi", "AM"),
            ("mercredi", "M"), ("mercredi", "AM"), ("jeudi", "M"),
            ("jeudi", "AM"), ("vendredi", "M"), ("vendredi", "AM")]
IDX = {c: 2 + i for i, c in enumerate(COLONNES)}

VIDE = "—"
TYPES = list(range(1, 6))
QUOTA = 16
SEUIL_TYPE = 4       # un type doit avoir >= 4 séances sur un créneau
                     # pour être considéré compatible avec lui


def nb_groupes(effectif_total, taille):
    """Nombre de groupes possibles pour placer `effectif_total` étudiants
    avec des groupes de taille dans [tmin, tmax]. Renvoie la liste des
    valeurs valides (souvent une seule), de la plus équilibrée à la moins."""
    import math
    tmin, tmax = taille
    g_min = math.ceil(effectif_total / tmax)
    g_max = effectif_total // tmin
    if g_max < g_min:
        return []
    # trier par proximité à la taille idéale (~milieu de la fourchette)
    ideal = (tmin + tmax) / 2
    plage = list(range(g_min, g_max + 1))
    plage.sort(key=lambda g: abs(effectif_total / g - ideal))
    return plage


def _ordre(s):
    return s if s >= 36 else s + 100


TOUTES = sorted(list(range(36, 53)) + list(range(1, 36)), key=_ordre)


# ============================================================
#  Calendrier et disponibilité
# ============================================================

def _bornes_pedo():
    """Bornes (début, fin) des périodes Pédo, depuis donnees ou secours."""
    return PERIODES_PEDO if PERIODES_PEDO is not None else _PERIODES_SECOURS


def periodes():
    """{numéro période: [semaines dans l'ordre scolaire]}.
    Les périodes sont fournies par l'équipe (donnees.PERIODES_PEDO),
    en bornes (début, fin) avec bouclage d'année géré."""
    res = {}
    for i, (debut, fin) in enumerate(_bornes_pedo(), start=1):
        o_d, o_f = _ordre(debut), _ordre(fin)
        res[i] = [s for s in TOUTES if o_d <= _ordre(s) <= o_f]
    return res


def creneau_ouvert(sem, creneau):
    if sem in SEMAINES_FERMEES:
        return False
    return not any((j, m) == creneau
                   for (j, m), _ in INDISPO_PROMO.get("5A", {}).get(sem, []))


def decouper():
    par_type = defaultdict(list)
    for code, info in ETUDIANTS.items():
        if info.get("annee") == 5 and not info.get("erasmus"):
            par_type[info["type"]].append(code)
    for t in par_type:
        par_type[t].sort()
    moities = {"A": defaultdict(list), "B": defaultdict(list)}
    for t in sorted(par_type):
        for i, code in enumerate(par_type[t]):
            moities["A" if i % 2 == 0 else "B"][t].append(code)
    return {k: dict(v) for k, v in moities.items()}


def libres_par_etudiant():
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


def table_seances(moitie_codes, P, libres, pair):
    """{(type, creneau, periode): set(semaines où ce type est libre)}"""
    table = {}
    for t, codes in moitie_codes.items():
        for c in CRENEAUX:
            for p in pair:
                ok = {s for s in P[p] if creneau_ouvert(s, c)}
                for code in codes:
                    ok &= libres[code][c]
                table[(t, c, p)] = ok
    return table


# ============================================================
#  Flot à bornes : répartir les étudiants dans les groupes
# ============================================================

INF = 10 ** 9


class _Flot:
    def __init__(self, n):
        self.n = n
        self.adj = [[] for _ in range(n)]

    def ajouter(self, u, v, cap):
        self.adj[u].append([v, cap, len(self.adj[v])])
        self.adj[v].append([u, 0, len(self.adj[u]) - 1])
        return (u, len(self.adj[u]) - 1)

    def _bfs(self, s, t):
        self.niveau = [-1] * self.n
        self.niveau[s] = 0
        file = [s]
        for u in file:
            for v, cap, _ in self.adj[u]:
                if cap > 0 and self.niveau[v] < 0:
                    self.niveau[v] = self.niveau[u] + 1
                    file.append(v)
        return self.niveau[t] >= 0

    def _dfs(self, u, t, flot):
        if u == t:
            return flot
        while self.iter[u] < len(self.adj[u]):
            arete = self.adj[u][self.iter[u]]
            v, cap, rev = arete
            if cap > 0 and self.niveau[v] == self.niveau[u] + 1:
                d = self._dfs(v, t, min(flot, cap))
                if d > 0:
                    arete[1] -= d
                    self.adj[v][rev][1] += d
                    return d
            self.iter[u] += 1
        return 0

    def maxflow(self, s, t):
        total = 0
        while self._bfs(s, t):
            self.iter = [0] * self.n
            while True:
                f = self._dfs(s, t, INF)
                if f == 0:
                    break
                total += f
        return total


def repartir(compat, effectifs, n_groupes, taille=TAILLE_CIBLE):
    """
    compat : {groupe: set(types acceptés)}
    effectifs : {type: nb d'étudiants à placer}
    taille : (tmin, tmax) — bornes de taille par groupe.
    Renvoie {(type, groupe): nb} ou None si impossible.
    Chaque groupe reçoit entre tmin et tmax étudiants, tous placés.
    """
    tmin, tmax = taille
    types = sorted(effectifs)
    nt = len(types)
    S = 0
    base_t = 1
    base_g = base_t + nt
    T = base_g + n_groupes
    SS, TT = T + 1, T + 2
    exces = [0] * (T + 3)
    F = _Flot(T + 3)

    for i, t in enumerate(types):
        l = effectifs[t]
        exces[base_t + i] += l
        exces[S] -= l

    aretes = {}
    for g in range(n_groupes):
        for i, t in enumerate(types):
            if t in compat[g]:
                aretes[(t, g)] = F.ajouter(base_t + i, base_g + g, tmax)

    for g in range(n_groupes):
        exces[T] += tmin
        exces[base_g + g] -= tmin
        F.ajouter(base_g + g, T, tmax - tmin)

    F.ajouter(T, S, INF)

    besoin = 0
    for v in range(T + 1):
        if exces[v] > 0:
            F.ajouter(SS, v, exces[v])
            besoin += exces[v]
        elif exces[v] < 0:
            F.ajouter(v, TT, -exces[v])

    if F.maxflow(SS, TT) != besoin:
        return None

    res = {}
    for (t, g), (u, idx) in aretes.items():
        passe = tmax - F.adj[u][idx][1]
        if passe:
            res[(t, g)] = passe
    return res


# ============================================================
#  Recherche
# ============================================================

def types_compatibles(creneau, periode, table, pair):
    """Types ayant assez de séances sur ce créneau, sur les 2 périodes."""
    return {t for t in TYPES
            if len(table.get((t, creneau, periode), set())) >= SEUIL_TYPE}


def _chercher_avec(nom_moitie, moitie_codes, P, libres, n, taille):
    """Recherche pour un nombre de groupes n et une taille donnés.
    Renvoie (meilleur, testees, faisables)."""
    pair = MOITIES[nom_moitie]
    table = table_seances(moitie_codes, P, libres, pair)
    effectifs = {t: len(v) for t, v in moitie_codes.items()}
    p1, p2 = pair

    if n > len(CRENEAUX):
        return None, 0, 0   # pas assez de créneaux pour n groupes distincts

    meilleur = None
    testees = faisables = 0

    for c1 in permutations(CRENEAUX, n):
        for c2 in permutations(CRENEAUX, n):
            testees += 1
            compat = []
            for g in range(n):
                ok = (types_compatibles(c1[g], p1, table, pair) &
                      types_compatibles(c2[g], p2, table, pair))
                compat.append(ok)
            if any(not c for c in compat):
                continue

            rep = repartir(compat, effectifs, n, taille)
            if rep is None:
                continue
            faisables += 1

            totaux = []
            for g in range(n):
                presents = {t for (t, gg) in rep if gg == g}
                total = 0
                for p, cs in ((p1, c1), (p2, c2)):
                    commun = None
                    for t in presents:
                        s = table[(t, cs[g], p)]
                        commun = set(s) if commun is None else commun & s
                    total += len(commun or set())
                totaux.append(total)

            score = (min(totaux), sum(totaux))
            if meilleur is None or score > meilleur[0]:
                meilleur = (score, c1, c2, rep, totaux)
    return meilleur, testees, faisables


def chercher(nom_moitie, moitie_codes, P, libres):
    """Cherche la meilleure structure de groupes pour une moitié.

    Le nombre de groupes est CALCULÉ (pas codé en dur) à partir de
    l'effectif et de la taille visée. On essaie d'abord la taille cible
    (8-12) ; si aucune configuration n'est faisable, on DÉGRADE vers la
    taille élargie (7-13) en le signalant. On teste les nombres de
    groupes valides du plus équilibré au moins.

    Renvoie (meilleur, testees, faisables, n_utilise, taille_utilisee,
             degrade).
    """
    effectif = sum(len(v) for v in moitie_codes.values())
    total_testees = total_faisables = 0

    for taille, degrade in ((TAILLE_CIBLE, False), (TAILLE_DEGRADEE, True)):
        for n in nb_groupes(effectif, taille):
            meilleur, t, f = _chercher_avec(
                nom_moitie, moitie_codes, P, libres, n, taille)
            total_testees += t
            total_faisables += f
            if meilleur is not None:
                return (meilleur, total_testees, total_faisables,
                        n, taille, degrade)

    return None, total_testees, total_faisables, None, None, False


# ============================================================
#  Affichage
# ============================================================

def afficher(nom_moitie, res, moitie_codes, P, libres):
    pair = MOITIES[nom_moitie]
    p1, p2 = pair
    meilleur, testees, faisables, n_util, taille_util, degrade = res
    print("\n" + "=" * 70)
    entete_n = f"{n_util} groupes" if n_util else "?"
    print(f"  MOITIÉ {nom_moitie} — périodes {p1}+{p2} — {entete_n}")
    print("=" * 70)

    if meilleur is None:
        print(f"  {testees} configurations testées, aucune faisable.")
        print(f"  Aucune répartition (même dégradée {TAILLE_DEGRADEE[0]}-"
              f"{TAILLE_DEGRADEE[1]}) ne convient.")
        return

    score, c1, c2, rep, totaux = meilleur
    table = table_seances(moitie_codes, P, libres, pair)
    print(f"  {testees} configurations testées, {faisables} faisables")
    if degrade:
        print(f"  ⚠️  taille dégradée {taille_util[0]}-{taille_util[1]} "
              f"utilisée (la cible {TAILLE_CIBLE[0]}-{TAILLE_CIBLE[1]} "
              f"ne donnait rien)")
    print(f"  Séances du groupe le plus mal loti : {score[0]}  "
          f"(quota {QUOTA})\n")

    for g in range(n_util):
        presents = sorted({t for (t, gg) in rep if gg == g})
        detail = "  ".join(f"t{t}:{rep[(t, g)]}" for t in presents)
        effectif = sum(rep[(t, g)] for t in presents)
        etat = "OK" if totaux[g] >= QUOTA else f"-{QUOTA - totaux[g]}"
        print(f"  Groupe {g + 1} : {effectif:2d} étudiants   "
              f"{totaux[g]:2d} séances  [{etat}]")
        print(f"      composition : {detail}")
        for p, cs in ((p1, c1), (p2, c2)):
            commun = None
            for t in presents:
                s = table[(t, cs[g], p)]
                commun = set(s) if commun is None else commun & s
            sems = sorted(commun or set(), key=_ordre)
            apercu = ", ".join(str(s) for s in sems[:8])
            if len(sems) > 8:
                apercu += ", ..."
            print(f"      P{p} : {cs[g][0]:9s} {cs[g][1]:<3s} -> "
                  f"{len(sems):2d} séances ({apercu})")
        print()


def main():
    if not os.path.isdir(DOSSIER):
        raise SystemExit(f"Dossier introuvable : {DOSSIER}")
    P = periodes()
    moities = decouper()
    libres = libres_par_etudiant()

    print("=" * 70)
    print("  PÉDO-SOIN — COMPOSITION DES GROUPES DE 5A")
    print("=" * 70)
    for nom in ("A", "B"):
        eff = {t: len(v) for t, v in moities[nom].items()}
        total = sum(eff.values())
        options = nb_groupes(total, TAILLE_CIBLE)
        n_prevu = options[0] if options else "?"
        print(f"  moitié {nom} : {total} étudiants  {eff}   "
              f"-> {n_prevu} groupes (calculé)")
    print(f"\n  Contrainte : {TAILLE_CIBLE[0]} à {TAILLE_CIBLE[1]} 5A par "
          f"groupe (dégradation {TAILLE_DEGRADEE[0]}-{TAILLE_DEGRADEE[1]} "
          f"si besoin)")

    for nom in ("A", "B"):
        res = chercher(nom, moities[nom], P, libres)
        afficher(nom, res, moities[nom], P, libres)


if __name__ == "__main__":
    main()