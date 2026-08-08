# ============================================================
#  service_sanitaire.py — Service sanitaire des 4A
#
#  Contraintes :
#    - 4A uniquement, hors Erasmus et redoublants dispensés
#    - 2 vacations/semaine, mêmes créneaux, pendant 7 semaines
#    - jamais le mercredi
#    - un créneau n'accueille qu'un seul groupe
#    - groupe de 6 à 8 étudiants
#
#  DISPONIBILITÉ : lue directement dans planning_csv_final.
#  Une cellule vaut "—" si et seulement si l'étudiant est libre.
#  On n'utilise PAS les "jours de Poly" comme approximation :
#  examens.py place des 4A hors des jours de leur type pendant
#  les semaines d'examen (ex : type 1 le jeudi, semaine 50).
#
#  Les 7 semaines d'un groupe sont les 7 premières où ses DEUX
#  créneaux sont libres pour TOUS les types qu'il accueille.
#  Les semaines d'examen des 4A sont écartées en bloc.
#
#  Structure choisie par recherche exhaustive sur les appariements
#  de créneaux, en maximisant la marge du type le plus contraint.
#  L'affectation des étudiants est exacte (flot à bornes basses).
#
#  Entrée : planning_csv_final/   Sortie : planning_csv_ss/
# ============================================================

import os
import csv
import sys
from itertools import combinations, product
from collections import defaultdict

from etudiants import ETUDIANTS
from donnees import INDISPO_PROMO, SEMAINES_FERMEES

try:
    from donnees import PERIODES_SERVICE_SANITAIRE
except ImportError:
    PERIODES_SERVICE_SANITAIRE = None

try:
    from donnees import REDOUBLANTS_4A
except ImportError:
    REDOUBLANTS_4A = set()
try:
    from donnees import NB_REDOUBLANT_4A
except ImportError:
    NB_REDOUBLANT_4A = None

DOSSIER_ENTREE = "planning_csv_final"
DOSSIER_SORTIE = "planning_csv_ss"

CAP_MAX = 8
CAP_MIN = 6
# Le service vise SEMAINES_MAX semaines quand c'est possible, et descend
# à SEMAINES_MIN quand une semaine de la fenêtre est bloquée (férié...).
# Un appariement est valable dès qu'il offre au moins SEMAINES_MIN semaines
# libres ; on en prend ensuite jusqu'à SEMAINES_MAX si elles existent.
# Les groupes qui n'atteignent que SEMAINES_MIN sont signalés (rattrapage
# manuel éventuel par l'équipe).
SEMAINES_MIN = 6
SEMAINES_MAX = 7
SEMAINES_REQUISES = SEMAINES_MIN  # seuil d'appariement valable
PERIODES_SS = (1, 2, 3, 4)

JOURS = ["lundi", "mardi", "jeudi", "vendredi"]        # mercredi exclu
CRENEAUX = [(j, m) for j in JOURS for m in ("M", "AM")]

COLONNES_VAC = [
    ("lundi", "M"), ("lundi", "AM"),
    ("mardi", "M"), ("mardi", "AM"),
    ("mercredi", "M"), ("mercredi", "AM"),
    ("jeudi", "M"), ("jeudi", "AM"),
    ("vendredi", "M"), ("vendredi", "AM"),
]
IDX_COLONNE = {c: 2 + i for i, c in enumerate(COLONNES_VAC)}

VIDE = "—"
MOTIFS_EXAMEN = {"E", "ER"}


def _ordre(sem):
    return sem if sem >= 36 else sem + 100


def _semaines_examen_4a():
    sems = set()
    for sem, blocages in INDISPO_PROMO.get("4A", {}).items():
        if any(motif in MOTIFS_EXAMEN for _, motif in blocages):
            sems.add(sem)
    return sems


SEMAINES_EXAMEN_4A = _semaines_examen_4a()


# ============================================================
#  Données
# ============================================================

def controler_redoublants():
    if NB_REDOUBLANT_4A is not None and len(REDOUBLANTS_4A) != NB_REDOUBLANT_4A:
        raise SystemExit(
            f"Incohérence : NB_REDOUBLANT_4A={NB_REDOUBLANT_4A} mais "
            f"REDOUBLANTS_4A contient {len(REDOUBLANTS_4A)} code(s).")


def etudiants_concernes():
    par_type = defaultdict(list)
    for code, info in ETUDIANTS.items():
        if info.get("annee") != 4 or info.get("erasmus"):
            continue
        if code in REDOUBLANTS_4A:
            continue
        par_type[info["type"]].append(code)
    for t in par_type:
        par_type[t].sort()
    return dict(par_type)


def _lire_csv(code, dossier):
    chemin = os.path.join(dossier, f"{code}.csv")
    with open(chemin, encoding="utf-8") as f:
        return [list(l) for l in csv.reader(f)]


def _developper_bornes(debut, fin):
    """Développe (debut, fin) en liste de semaines consécutives dans
    l'ordre scolaire, en gérant le bouclage de l'année (ex: (52, 6))."""
    o_debut, o_fin = _ordre(debut), _ordre(fin)
    if o_fin < o_debut:
        raise SystemExit(
            f"Période SS invalide : ({debut}, {fin}) — fin avant début "
            f"dans l'ordre scolaire.")
    sems = []
    o = o_debut
    while o <= o_fin:
        sems.append(o if o < 100 else o - 100)
        o += 1
    return sems


def periodes_depuis_csv(par_type=None, dossier=DOSSIER_ENTREE):
    """{période: [semaines dans l'ordre scolaire]}.

    Les périodes du service sanitaire sont désormais FOURNIES par
    l'équipe dans donnees.PERIODES_SERVICE_SANITAIRE (bornes début/fin),
    et non plus déduites de la colonne 'Période' du calendrier Poly.
    Le paramètre par_type est conservé pour compatibilité d'appel.
    """
    if PERIODES_SERVICE_SANITAIRE is None:
        raise SystemExit(
            "PERIODES_SERVICE_SANITAIRE absent de donnees.py — "
            "définissez les périodes du service sanitaire (bornes "
            "début/fin) avant de lancer ce module.")
    res = {}
    for i, (debut, fin) in enumerate(PERIODES_SERVICE_SANITAIRE, start=1):
        res[i] = _developper_bornes(debut, fin)
    return res


def _est_rattrap(cellule):
    """Une vacation Poly de RATTRAPAGE serait écrasable par le service
    sanitaire (c'est du bonus). Utilisé par le rapport de récupération."""
    return cellule.startswith("Poly") and "(rattrap)" in cellule


def charger_disponibilites(par_type, dossier=DOSSIER_ENTREE):
    """dispo[type] = {(semaine, jour, moment)} libres pour TOUS les
    étudiants de ce type. Conservateur : seul '—' compte comme libre."""
    dispo = {}
    for t, codes in par_type.items():
        commun = None
        for code in codes:
            libres = set()
            for ligne in _lire_csv(code, dossier):
                if len(ligne) >= 12 and ligne[0].isdigit():
                    sem = int(ligne[0])
                    for c in CRENEAUX:
                        if ligne[IDX_COLONNE[c]] == VIDE:
                            libres.add((sem,) + c)
            commun = libres if commun is None else commun & libres
        dispo[t] = commun or set()
    return dispo


# ============================================================
#  Créneaux, paires, appariements
# ============================================================

def semaines_communes(a, b, types, semaines, dispo):
    """Semaines où a ET b sont libres pour tous les types donnés."""
    ok = set()
    for sem in semaines:
        if sem in SEMAINES_FERMEES or sem in SEMAINES_EXAMEN_4A:
            continue
        if all((sem,) + a in dispo[t] and (sem,) + b in dispo[t]
               for t in types):
            ok.add(sem)
    return ok


def paires_viables(semaines, dispo):
    """
    Pour chaque paire de créneaux, les ensembles de types MAXIMAUX
    qui disposent d'au moins 7 semaines communes.
    """
    res = []
    for a, b in combinations(CRENEAUX, 2):
        seuls = [t for t in sorted(dispo)
                 if len(semaines_communes(a, b, [t], semaines, dispo))
                 >= SEMAINES_REQUISES]
        if not seuls:
            continue
        valides = []
        for taille in range(1, len(seuls) + 1):
            for sous in combinations(seuls, taille):
                T = frozenset(sous)
                if len(semaines_communes(a, b, T, semaines, dispo)) \
                        >= SEMAINES_REQUISES:
                    valides.append(T)
        maximaux = [T for T in valides if not any(T < U for U in valides)]
        for T in maximaux:
            res.append((a, b, T))
    return res


def appariements(semaines, dispo):
    """Ensembles de paires disjointes (en créneaux) de taille maximale."""
    paires = paires_viables(semaines, dispo)
    meilleurs, taille = [], 0

    def rec(depart, occupes, acc):
        nonlocal meilleurs, taille
        if len(acc) > taille:
            taille, meilleurs = len(acc), [list(acc)]
        elif len(acc) == taille and acc:
            meilleurs.append(list(acc))
        for k in range(depart, len(paires)):
            a, b, T = paires[k]
            if a in occupes or b in occupes:
                continue
            rec(k + 1, occupes | {a, b}, acc + [(a, b, T)])

    rec(0, set(), [])
    vus, res = set(), []
    for e in meilleurs:
        cle = frozenset((a, b, T) for a, b, T in e)
        if cle not in vus:
            vus.add(cle)
            res.append(e)
    return res


# ============================================================
#  Affectation exacte : flot à bornes inférieures
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


def affectation(groupes, eff):
    """groupes : liste de frozenset(types). -> {(type,i): nb} ou None."""
    ng = len(groupes)
    S, T = 0, 6 + ng
    SS, TT = T + 1, T + 2
    exces = [0] * (T + 3)
    F = _Flot(T + 3)

    for t in range(1, 6):
        l = eff.get(t, 0)
        exces[t] += l
        exces[S] -= l

    aretes = {}
    for i, types in enumerate(groupes):
        for t in types:
            if eff.get(t, 0):
                aretes[(t, i)] = F.ajouter(t, 6 + i, CAP_MAX)

    for i in range(ng):
        exces[T] += CAP_MIN
        exces[6 + i] -= CAP_MIN
        F.ajouter(6 + i, T, CAP_MAX - CAP_MIN)

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
    for (t, i), (u, idx) in aretes.items():
        passe = CAP_MAX - F.adj[u][idx][1]
        if passe:
            res[(t, i)] = passe
    return res


_cache_marges = {}


def marges(groupes, eff):
    cle = tuple(sorted(tuple(sorted(g)) for g in groupes))
    if cle in _cache_marges:
        return _cache_marges[cle]

    if affectation(groupes, eff) is None:
        _cache_marges[cle] = None
        return None

    plafond = CAP_MAX * len(groupes) - sum(eff.values())
    res = {}
    for t in range(1, 6):
        k = 0
        while k < plafond:
            essai = dict(eff)
            essai[t] += k + 1
            if affectation(groupes, essai) is None:
                break
            k += 1
        res[t] = k
    _cache_marges[cle] = res
    return res


# ============================================================
#  Choix de la structure
# ============================================================

def choisir_structure(periodes, dispo, eff, verbeux=True):
    options = {p: appariements(periodes[p], dispo) for p in PERIODES_SS}
    if verbeux:
        for p in PERIODES_SS:
            n = len(options[p][0]) if options[p] else 0
            print(f"  période {p} : {n} groupes, "
                  f"{len(options[p])} appariements possibles")

    meilleur, essais, faisables = None, 0, 0
    for combo in product(*[options[p] for p in PERIODES_SS]):
        essais += 1
        groupes = [T for per in combo for _, _, T in per]
        m = marges(groupes, eff)
        if m is None:
            continue
        faisables += 1
        score = (min(m.values()), sum(m.values()))
        if meilleur is None or score > meilleur[0]:
            meilleur = (score, combo, m)

    if verbeux:
        print(f"  {essais} combinaisons testées, {faisables} faisables")
    if meilleur is None:
        raise SystemExit(
            "Aucune structure ne place les 75 étudiants.\n"
            "Le service sanitaire ne tient plus dans les créneaux laissés "
            "libres par la Poly : il faudra réserver ses créneaux AVANT "
            "de calculer la Poly.")
    return meilleur


# ============================================================
#  Construction nominative
# ============================================================

def construire():
    controler_redoublants()
    par_type = etudiants_concernes()
    eff = {t: len(v) for t, v in par_type.items()}
    print(f"Effectifs 4A concernés : {eff}  (total {sum(eff.values())})")
    if REDOUBLANTS_4A:
        print(f"Dispensés (redoublants) : {sorted(REDOUBLANTS_4A)}")

    periodes = periodes_depuis_csv(par_type)
    dispo = charger_disponibilites(par_type)

    score, combo, m = choisir_structure(periodes, dispo, eff)
    print(f"  marges par type : {m}   (marge minimale {min(m.values())})\n")

    plats = [(p, a, b, T)
             for p, cfg in zip(PERIODES_SS, combo) for a, b, T in cfg]
    comptes = affectation([T for _, _, _, T in plats], eff)

    restants = {t: list(v) for t, v in par_type.items()}
    groupes = []
    for i, (p, a, b, T) in enumerate(plats):
        membres = []
        for t in sorted(T):
            n = comptes.get((t, i), 0)
            membres += [restants[t].pop(0) for _ in range(n)]
        rang = sum(1 for g in groupes if g["periode"] == p) + 1
        sems = sorted(semaines_communes(a, b, T, periodes[p], dispo),
                      key=_ordre)[:SEMAINES_MAX]
        groupes.append({
            "nom": f"SS-P{p}G{rang}",
            "periode": p,
            "creneaux": (a, b),
            "types": sorted(T),
            "membres": sorted(membres),
            "semaines": sems,
        })

    reste = {t: v for t, v in restants.items() if v}
    if reste:
        raise SystemExit(f"Étudiants non affectés : {reste}")
    return groupes


# ============================================================
#  Export
# ============================================================

def exporter(groupes, entree=DOSSIER_ENTREE, sortie=DOSSIER_SORTIE):
    data = {}
    for nom in os.listdir(entree):
        if nom.endswith(".csv"):
            data[nom[:-4]] = _lire_csv(nom[:-4], entree)
    index = {code: {int(l[0]): i for i, l in enumerate(lignes)
                    if len(l) >= 12 and l[0].isdigit()}
             for code, lignes in data.items()}

    conflits, ecrits = [], 0
    for g in groupes:
        for code in g["membres"]:
            for sem in g["semaines"]:
                i = index[code][sem]
                for c in g["creneaux"]:
                    col = IDX_COLONNE[c]
                    actuel = data[code][i][col]
                    if actuel != VIDE:
                        conflits.append(
                            f"{code} sem {sem} {c[0]} {c[1]} : "
                            f"attendu '{VIDE}', trouvé '{actuel}'")
                        continue
                    data[code][i][col] = f"Service sanitaire ({g['nom']})"
                    ecrits += 1

    if conflits:
        print(f"\n⚠️  {len(conflits)} conflit(s) — rien n'a été écrit :")
        for c in conflits[:10]:
            print(f"     {c}")
        raise SystemExit("Disponibilité mal calculée.")

    os.makedirs(sortie, exist_ok=True)
    for code, lignes in data.items():
        with open(os.path.join(sortie, f"{code}.csv"), "w",
                  newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(lignes)

    attendu = sum(len(g["membres"]) * len(g["semaines"]) * 2 for g in groupes)
    print(f"\n{ecrits} vacations écrites dans {sortie}/  (attendu {attendu})")


def rapport_recuperation(groupes, periodes, dossier=DOSSIER_ENTREE):
    """Pour chaque groupe à moins de SEMAINES_MAX semaines, examine la
    (ou les) semaine(s) manquante(s) de sa fenêtre et dit si elle serait
    RÉCUPÉRABLE en écrasant au plus 2 vacations Poly de rattrapage (aucun
    blocage dur sur les deux créneaux). Ne modifie rien : l'équipe tranche.
    """
    # plannings des membres concernés
    besoin = set()
    for g in groupes:
        if len(g["semaines"]) < SEMAINES_MAX:
            besoin.update(g["membres"])
    plan = {}
    for code in besoin:
        p = {}
        for ligne in _lire_csv(code, dossier):
            if len(ligne) >= 12 and ligne[0].isdigit():
                sem = int(ligne[0])
                p[sem] = {c: ligne[IDX_COLONNE[c]] for c in CRENEAUX}
        plan[code] = p

    recuperables = []
    for g in groupes:
        if len(g["semaines"]) >= SEMAINES_MAX:
            continue
        fenetre = periodes[g["periode"]]
        prises = set(g["semaines"])
        manquantes = [s for s in fenetre if s not in prises]
        a, b = g["creneaux"]
        for sem in manquantes:
            durs = 0
            membres_rattrap = set()
            for code in g["membres"]:
                for c in (a, b):
                    cell = plan.get(code, {}).get(sem, {}).get(c, "—")
                    if cell == VIDE:
                        continue
                    if _est_rattrap(cell):
                        membres_rattrap.add(code)
                    else:
                        durs += 1
            if durs == 0 and 1 <= len(membres_rattrap) <= 2:
                recuperables.append((g["nom"], sem, sorted(membres_rattrap),
                                     (a, b)))

    if recuperables:
        print(f"\n  ── Semaines récupérables en écrasant du rattrapage Poly "
              f"(à faire à la main si souhaité) ──")
        for nom, sem, membres, (a, b) in recuperables:
            print(f"    {nom} : gagner la semaine {sem} en retirant la Poly "
                  f"rattrap de {'+'.join(membres)}")
            print(f"       créneaux {a[0]} {a[1]} / {b[0]} {b[1]}")
    return recuperables


def afficher(groupes):
    a_rattraper = []
    for g in groupes:
        a, b = g["creneaux"]
        sems = g["semaines"]
        etendue = _ordre(sems[-1]) - _ordre(sems[0]) + 1
        trou = "" if etendue == len(sems) else \
            f"  [{etendue - len(sems)} semaine(s) sautée(s)]"
        manque = ""
        if len(sems) < SEMAINES_MAX:
            manque = f"  ⚠️ {len(sems)} semaines (rattrapage manuel)"
            a_rattraper.append(g["nom"])
        print(f"{g['nom']}  période {g['periode']}  "
              f"{a[0]} {a[1]} + {b[0]} {b[1]}")
        print(f"   types {g['types']}, {len(g['membres'])} étudiants{manque}")
        print(f"   semaines : {', '.join(str(s) for s in sems)}{trou}")
        print(f"   {', '.join(g['membres'])}")

    if a_rattraper:
        print(f"\n  ⚠️  {len(a_rattraper)} groupe(s) à {SEMAINES_MIN} semaines "
              f"(1 semaine à rattraper) : {', '.join(a_rattraper)}")
    else:
        print(f"\n  ✅ Tous les groupes ont leurs {SEMAINES_MAX} semaines.")


if __name__ == "__main__":
    gr = construire()
    afficher(gr)
    _par_type = etudiants_concernes()
    _periodes = periodes_depuis_csv(_par_type)
    rapport_recuperation(gr, _periodes)
    if "--export" in sys.argv:
        exporter(gr)
    else:
        print("\n(ajouter --export pour écrire les CSV)")