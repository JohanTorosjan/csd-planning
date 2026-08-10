# ============================================================
#  odf.py — Placement des vacations d'ODF
#
#  Matière réservée aux 5A. Placement INDIVIDUEL.
#
#  Règles :
#   - concerne UNIQUEMENT les 5A
#   - créneaux : lundi AM, mardi AM, mercredi M, mercredi AM, vendredi AM
#     (jours 2, 4, 5, 6, 10)
#   - 3 étudiants par vacation, salles TOUJOURS pleines à 3
#     (si < 3 disponibles → vacation non ouverte, signalé dans les logs)
#   - quota : 2 vacations par semestre (soit 4/an) par 5A
#     • les salles pleines priment : comme 77×2 = 154 n'est pas divisible
#       par 3, quelques 5A feront 3 vacations dans un semestre (donc 5/an)
#       pour absorber le reste. C'est assumé.
#   - semestres :
#       S1 = période 1 + période 2
#       S2 = période 3 → date de fin (SEMAINE_FIN_ODF, paramétrable)
#   - équité (ne pas toujours favoriser les mêmes) + étalement intra-semestre
#
#  Entrée : planning_csv_occluso (dernier état de la pipeline)
#  Sortie : planning_csv_odf
#
#  Usage : python3 odf.py            (aperçu)
#          python3 odf.py --export   (écrit les CSV)
# ============================================================

import os
import csv
import sys
import statistics
from collections import defaultdict

from etudiants import ETUDIANTS

import pedo_groupes as pg

DOSSIER_ENTREE = "planning_csv_occluso"
DOSSIER_SORTIE = "planning_csv_odf"
VIDE = "—"

IDX = pg.IDX

# ============================================================
#  CONFIGURATION
# ============================================================

# créneaux ODF : lunAM, marAM, merM, merAM, venAM (jours 2,4,5,6,10)
CRENEAUX_ODF = [("lundi", "AM"), ("mardi", "AM"), ("mercredi", "M"),
                ("mercredi", "AM"), ("vendredi", "AM")]

PLACES_PAR_VACATION = 3

# date de fin (comme l'occluso cette année) : semaine 22 (28 mai)
SEMAINE_FIN_ODF = 22

# quota par semestre (on vise ce nombre ; le reste non divisible par 3
# fait que quelques 5A en auront 3 dans un semestre)
QUOTA_PAR_SEMESTRE = 2

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


# ============================================================
#  Semestres
# ============================================================

def semestres():
    """Renvoie (S1_sems, S2_sems) : ensembles de semaines par semestre."""
    P = pg.periodes()
    s1 = set(P[1]) | set(P[2])
    s2 = set()
    for per in (3, 4, 5, 6):
        s2 |= set(P[per])
    s2 = {s for s in s2 if _ordre(s) <= _ordre(SEMAINE_FIN_ODF)}
    return s1, s2


# ============================================================
#  Chargement
# ============================================================

def charger():
    data = {}
    for nom in os.listdir(DOSSIER_ENTREE):
        if nom.endswith(".csv"):
            code = nom[:-4]
            with open(os.path.join(DOSSIER_ENTREE, nom), encoding="utf-8") as f:
                data[code] = [list(l) for l in csv.reader(f)]
    return data


# ============================================================
#  Placement
# ============================================================

def placer(data):
    """
    Place les 5A en ODF, semestre par semestre.
    Renvoie (affectations {code:[(sem,col)]}, alertes [str]).
    """
    codes5 = [c for c, i in ETUDIANTS.items()
              if i.get("annee") == 5 and not i.get("erasmus")]
    codes5 = [c for c in codes5 if c in data]

    index = {}
    for code in codes5:
        index[code] = {int(l[0]): i for i, l in enumerate(data[code])
                       if len(l) >= 12 and l[0].isdigit()}

    S1, S2 = semestres()
    affectations = defaultdict(list)
    alertes = []

    for nom_sem, sems_sem in (("S1", S1), ("S2", S2)):
        _placer_semestre(nom_sem, sems_sem, codes5, index, data,
                         affectations, alertes)

    return affectations, alertes


def _placer_semestre(nom_sem, sems_sem, codes5, index, data,
                     affectations, alertes):
    """Place QUOTA_PAR_SEMESTRE vacations par 5A dans ce semestre,
    salles pleines à 3, équité + étalement."""
    sems = sorted(sems_sem, key=_ordre)

    # vacations exploitables (>=3 5A dispo)
    vacations = []
    dispo_vac = {}
    for sem in sems:
        for cr in CRENEAUX_ODF:
            i = IDX[cr]
            libres = []
            nferme = 0
            ntot = 0
            for code in codes5:
                li = index[code].get(sem)
                if li is None:
                    continue
                ntot += 1
                v = data[code][li][i]
                if est_ferme(v):
                    nferme += 1
                elif v == VIDE:
                    libres.append(code)
            if nferme > ntot * 0.5:
                continue
            if len(libres) >= PLACES_PAR_VACATION:
                vacations.append((sem, cr))
                dispo_vac[(sem, cr)] = libres

    vacations.sort(key=lambda x: instant(x[0], x[1]))

    # combien de vacations ouvrir : viser QUOTA × nb_5A / 3 places
    besoin_places = len(codes5) * QUOTA_PAR_SEMESTRE
    n_vac_a_ouvrir = -(-besoin_places // PLACES_PAR_VACATION)  # arrondi sup

    if len(vacations) < n_vac_a_ouvrir:
        alertes.append(
            f"[{nom_sem}] seulement {len(vacations)} vacations exploitables "
            f"pour {n_vac_a_ouvrir} nécessaires (salles risquent d'être non pleines)")

    # compteurs pour ce semestre
    deja = defaultdict(int)          # nb vacations ce semestre
    dernier = {}                     # instant dernière vacation

    def score(code, inst):
        base = deja[code]
        d = dernier.get(code)
        recence = 1.0 / max(1, inst - d) if d is not None else 0.0
        return base + POIDS_RECENCE * recence

    # on ouvre les vacations une à une (étalées) et on remplit chacune à 3
    # en priorisant les 5A qui ont le moins de vacations ce semestre.
    # on choisit les vacations pour couvrir l'année de façon étalée :
    # échantillonnage régulier dans la liste chronologique.
    choisies = _echantillon_etale(vacations, n_vac_a_ouvrir)

    for (sem, cr) in choisies:
        inst = instant(sem, cr)
        cands = [c for c in dispo_vac[(sem, cr)]
                 if (sem, cr) not in affectations[c]]
        cands.sort(key=lambda c: score(c, inst))
        pris = cands[:PLACES_PAR_VACATION]
        if len(pris) < PLACES_PAR_VACATION:
            alertes.append(
                f"[{nom_sem}] vacation s{sem} {cr[0]} {cr[1]} : "
                f"seulement {len(pris)} 5A dispo (salle non pleine)")
        for code in pris:
            affectations[code].append((sem, cr))
            deja[code] += 1
            dernier[code] = inst

    # garantir que chaque 5A atteigne QUOTA (compléter les sous-quota)
    _completer_quota(nom_sem, sems, codes5, index, data,
                     affectations, deja, dispo_vac, alertes)


def _echantillon_etale(vacations, n):
    """Sélectionne n vacations réparties régulièrement dans la liste
    chronologique (pour étaler sur le semestre)."""
    if n >= len(vacations):
        return list(vacations)
    pas = len(vacations) / n
    return [vacations[int(k * pas)] for k in range(n)]


def _completer_quota(nom_sem, sems, codes5, index, data,
                     affectations, deja, dispo_vac, alertes):
    """S'assure que chaque 5A a QUOTA_PAR_SEMESTRE vacations ce semestre.
    Pour un 5A sous le quota, on cherche une vacation ouverte où il est
    dispo, en remplaçant un 5A au-dessus du quota — sinon on ouvre une
    vacation supplémentaire si possible."""
    # placements par vacation
    par_vac = defaultdict(list)
    for code in codes5:
        for v in affectations[code]:
            if v[0] in sems:
                par_vac[v].append(code)

    for code in codes5:
        while deja[code] < QUOTA_PAR_SEMESTRE:
            place = False
            # 1) chercher une vacation ouverte où `code` est dispo et où on
            #    peut remplacer un membre au-dessus du quota
            for v, membres in par_vac.items():
                if code in membres:
                    continue
                if code not in dispo_vac.get(v, []):
                    continue
                remplacable = max(membres, key=lambda m: deja[m], default=None)
                if remplacable and deja[remplacable] > QUOTA_PAR_SEMESTRE:
                    membres.remove(remplacable)
                    affectations[remplacable].remove(v)
                    deja[remplacable] -= 1
                    membres.append(code)
                    affectations[code].append(v)
                    deja[code] += 1
                    place = True
                    break
            if place:
                continue

            # 2) dernier recours : OUVRIR une vacation supplémentaire sur un
            #    créneau dispo de `code`, avec 2 autres 5A dispo (qui
            #    passeront à 3 — le "reste" assumé). On garde la salle pleine.
            for v in dispo_vac:
                if v[0] not in sems:
                    continue
                if code not in dispo_vac[v]:
                    continue
                if v in par_vac:            # déjà ouverte
                    continue
                # deux autres 5A dispo sur cette vacation, pas déjà dessus
                autres = [c for c in dispo_vac[v]
                          if c != code]
                if len(autres) < PLACES_PAR_VACATION - 1:
                    continue
                # préférer des 5A au quota exactement (ils passeront à 3)
                autres.sort(key=lambda c: deja[c])
                choisis = [code] + autres[:PLACES_PAR_VACATION - 1]
                par_vac[v] = choisis
                for c in choisis:
                    affectations[c].append(v)
                    deja[c] += 1
                place = True
                break

            if not place:
                alertes.append(
                    f"[{nom_sem}] {code} : impossible d'atteindre le quota "
                    f"{QUOTA_PAR_SEMESTRE} (a {deja[code]})")
                break


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
        for sem, cr in places:
            i = index[code].get(sem)
            if i is None:
                continue
            j = IDX[cr]
            if data[code][i][j] != VIDE:
                conflits += 1
                continue
            if ecrire:
                data[code][i][j] = "ODF"

    if conflits:
        print(f"\n⚠️  {conflits} conflit(s) — cellules déjà occupées")

    total = sum(len(v) for v in affectations.values())
    print(f"\n  {total} affectations d'ODF.")
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
    print("  ODF — RAPPORT")
    print("=" * 66)

    codes5 = [c for c, i in ETUDIANTS.items()
              if i.get("annee") == 5 and not i.get("erasmus")]
    S1, S2 = semestres()

    # vacations
    vac = set()
    for places in affectations.values():
        vac |= set(places)
    print(f"\n  Vacations ODF : {len(vac)}")
    print(f"  Places pourvues : {sum(len(v) for v in affectations.values())}")

    # quota par semestre
    for nom_sem, sems_sem in (("S1", S1), ("S2", S2)):
        par_etud = [sum(1 for s, _ in affectations.get(c, []) if s in sems_sem)
                    for c in codes5]
        from collections import Counter
        dist = Counter(par_etud)
        print(f"\n  {nom_sem} — vacations/5A : "
              + "  ".join(f"{n}:{dist[n]}" for n in sorted(dist)))
        hors = sum(1 for v in par_etud if v != QUOTA_PAR_SEMESTRE)
        print(f"     hors quota ({QUOTA_PAR_SEMESTRE}) : {hors}")

    # total annuel
    tot = [len(affectations.get(c, [])) for c in codes5]
    print(f"\n  Total annuel/5A : min={min(tot)}, max={max(tot)}, "
          f"moy={statistics.mean(tot):.1f}")

    if alertes:
        print(f"\n  ⚠️  {len(alertes)} alerte(s) :")
        for a in alertes[:15]:
            print(f"     - {a}")


def main(export=None):
    ecrire = export if export is not None else ("--export" in sys.argv)
    data = charger()
    affectations, alertes = placer(data)
    rapport(affectations, alertes)
    exporter(data, affectations, ecrire)


if __name__ == "__main__":
    main()