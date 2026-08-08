# ============================================================
#  pedo_periode_56.py — Étape 7 (rattrapage) de Pédo-soin
#
#  Rattrapage des périodes 5 et 6 avec GROUPES STABLES et
#  roulement à SURNOMBRE MODULÉ pour resserrer l'équité intra-promo.
#
#  Principe :
#    - 5 groupes stables (un par créneau), actifs sur P5 puis P6,
#    - composition fixe : 6A (déficitaires) + 4A + 5A,
#    - les 4A et 5A sont placés en SURNOMBRE modulé : les plus
#      déficitaires dans les groupes à FAIBLE surnombre (ils viennent
#      souvent → rattrapent), les mieux servis dans les groupes à FORT
#      surnombre (ils roulent → gagnent peu). Réglage doux : on resserre
#      l'écart sans l'aggraver,
#    - les 6A déficitaires sont placés en priorité (2-4 places/groupe),
#    - roulement interne : chaque semaine, on remplit les places avec
#      les membres disponibles les moins servis.
#
#  Les démissions de 6A (à partir de juin) sont gérées en amont comme
#  des indisponibilités individuelles dans les données : un 6A qui a
#  démissionné a ses cellules bloquées, il n'est donc jamais placé.
#
#  Entrée : planning_csv_pedo (état P1-4 + remplissage) + planning_csv_ss
#           (disponibilités réelles).
#  Sortie : planning_csv_pedo (ajoute les séances P5-6).
#
#  Usage : python3 pedo_periode_56.py            (aperçu)
#          python3 pedo_periode_56.py --export   (écrit les CSV)
# ============================================================

import os
import csv
import sys
import statistics
from collections import defaultdict

from etudiants import ETUDIANTS

import pedo_groupes as pg

DOSSIER_PEDO = "planning_csv_pedo"
DOSSIER_SS = "planning_csv_ss"
VIDE = "—"
CAPACITE = 20

CRENEAUX = pg.CRENEAUX
IDX = pg.IDX
PERIODES_56 = (5, 6)

# composition cible par groupe (par créneau)
PLACES_6A = 3        # places 6A par groupe (déficitaires prioritaires)
PLACES_4A = 8        # places 4A par groupe (par semaine)
PLACES_5A = 9        # places 5A par groupe (par semaine)

# surnombre modulé : les groupes ont une taille croissante (pente douce).
# Un groupe "doux" (petit) : ses membres viennent souvent → gagnent plus.
# Un groupe "sévère" (grand) : ses membres roulent → gagnent moins.
# On range les plus déficitaires dans les groupes doux.
# PENTE = écart de taille entre groupes consécutifs. Douce (~1) pour
# resserrer légèrement l'écart sans l'inverser.
PENTE = 1.0

# nombre minimum de semaines dispo sur un créneau pour y être affecté.
# Relevé à 8 : on ne place un étudiant sur un créneau que s'il y est
# VRAIMENT disponible (pas juste 3 semaines), pour éviter les placements
# sur un mauvais créneau qui plombent le rattrapage.
MIN_DISPO = 8

# poids du remplissage dans le choix du créneau : plus il est élevé, plus
# on équilibre les tailles (au risque de dégrader un peu la dispo) ; plus
# il est bas, plus on privilégie la meilleure dispo de l'étudiant.
PENALITE_REMPLISSAGE = 0.5

# marge du plafond de gain par groupe : un membre peut dépasser la part
# équitable de ce nombre de séances avant d'être mis en fin de priorité.
# Petite marge = équité stricte ; grande marge = plus de souplesse.
PLAFOND_MARGE = 2


def _ordre(s):
    return s if s >= 36 else s + 100


def periode_de(sem, P):
    for per, sems in P.items():
        if sem in sems:
            return per
    return None


# ============================================================
#  Lecture de l'état actuel et des disponibilités
# ============================================================

def charger_pedo():
    data = {}
    for nom in os.listdir(DOSSIER_PEDO):
        if nom.endswith(".csv"):
            with open(os.path.join(DOSSIER_PEDO, nom), encoding="utf-8") as f:
                data[nom[:-4]] = [list(l) for l in csv.reader(f)]
    return data


def est_pedo(cell):
    return "édo" in cell


def seances_actuelles(data):
    """{code: nb de séances Pédo déjà placées (P1-4)}."""
    seances = defaultdict(int)
    for code, lignes in data.items():
        for l in lignes:
            if len(l) >= 12 and l[0].isdigit():
                for cr in CRENEAUX:
                    if est_pedo(l[IDX[cr]]):
                        seances[code] += 1
    return seances


def libres_par_etudiant():
    """{code: set((creneau, semaine)) libres en P5-6}.

    On lit planning_csv_PEDO (état à jour avec toutes les vacations déjà
    posées : Poly, service sanitaire, Pédo P1-4…), et PAS planning_csv_ss :
    une cellule n'est réellement libre que si elle l'est dans le fichier
    qu'on va modifier. Sinon on réutiliserait des créneaux déjà occupés
    par d'autres vacations (conflits)."""
    P = pg.periodes()
    sems56 = set(P[5]) | set(P[6])
    res = {}
    for nom in os.listdir(DOSSIER_PEDO):
        if not nom.endswith(".csv"):
            continue
        code = nom[:-4]
        info = ETUDIANTS.get(code, {})
        if info.get("erasmus"):
            continue
        if info.get("annee") not in (4, 5, 6):
            continue
        libres = set()
        with open(os.path.join(DOSSIER_PEDO, nom), encoding="utf-8") as f:
            for l in csv.reader(f):
                if len(l) >= 12 and l[0].isdigit():
                    sem = int(l[0])
                    if sem not in sems56:
                        continue
                    for cr in CRENEAUX:
                        if l[IDX[cr]] == VIDE:
                            libres.add((cr, sem))
        res[code] = libres
    return res


# ============================================================
#  Composition des groupes (surnombre modulé)
# ============================================================

def _tailles_groupes(n_etudiants, n_groupes, pente):
    """
    Répartit n_etudiants sur n_groupes avec une PENTE douce : les premiers
    groupes (doux) sont plus petits (leurs membres viennent souvent), les
    derniers (sévères) plus grands (leurs membres roulent).

    `pente` = écart de taille entre groupes consécutifs (0 = tailles égales,
    1 = +1 membre par groupe). Une pente douce (~1) donne un léger effet
    d'équité sans exploser l'écart.

    Renvoie une liste de tailles, du plus doux (petit) au plus sévère (grand),
    dont la somme vaut exactement n_etudiants.
    """
    base = n_etudiants // n_groupes
    # tailles centrées sur `base` avec la pente : base + pente*(g - milieu)
    milieu = (n_groupes - 1) / 2
    tailles = [base + round(pente * (g - milieu)) for g in range(n_groupes)]
    # ajuster la somme pour retomber exactement sur n_etudiants
    diff = n_etudiants - sum(tailles)
    # répartir le reste sur les groupes du milieu
    g = n_groupes // 2
    step = 0
    while diff != 0:
        i = (g + step) % n_groupes
        tailles[i] += 1 if diff > 0 else -1
        diff += -1 if diff > 0 else 1
        step += 1
    return tailles


def composer_groupes(seances, libres):
    """
    Compose les 5 groupes (un par créneau) pour chaque promo.

    Les étudiants sont très flexibles en P5-6 (chacun a plusieurs créneaux
    où il est largement disponible). On exploite cette flexibilité pour
    ÉQUILIBRER les groupes : chaque étudiant (traité par déficit décroissant)
    va dans le créneau le MOINS rempli parmi ses bons créneaux, sans
    dépasser la taille cible du groupe. Les tailles cibles suivent une
    PENTE douce (petits groupes = doux, grands = sévères) et, comme les
    plus déficitaires sont traités d'abord, ils tombent dans les groupes
    qui se remplissent en premier (les doux) → ils viennent souvent.

    - 6A : déficitaires prioritaires, PLACES_6A par groupe, meilleur créneau.
    - 4A et 5A : équilibrage sur bons créneaux, avec pente douce.

    Renvoie {creneau: {"6A":[codes], "4A":[codes], "5A":[codes]}}
    """
    quota = {4: 8, 5: 16, 6: 16}

    def bons_creneaux(code):
        """Créneaux où le code a >= MIN_DISPO semaines, triés dispo décroissante."""
        par_cr = defaultdict(int)
        for (cr, sem) in libres.get(code, set()):
            par_cr[cr] += 1
        return sorted((cr for cr, n in par_cr.items() if n >= MIN_DISPO),
                      key=lambda cr: -par_cr[cr])

    par_promo = {4: [], 5: [], 6: []}
    for code, info in ETUDIANTS.items():
        if info.get("erasmus"):
            continue
        a = info.get("annee")
        if a in (4, 5, 6):
            deficit = quota[a] - seances.get(code, 0)
            par_promo[a].append((code, deficit))
    for a in (4, 5, 6):
        par_promo[a].sort(key=lambda x: -x[1])   # plus déficitaire d'abord

    groupes = {cr: {"6A": [], "4A": [], "5A": []} for cr in CRENEAUX}

    # --- 6A : candidats = ceux SOUS LA MOYENNE, répartis sur les créneaux ---
    # (convergence vers la moyenne : voir placer(). On met tous les
    #  sous-moyenne comme membres, en surnombre par rapport aux PLACES_6A,
    #  pour que le roulement puisse les faire tourner.)
    import statistics as _stats
    vals6 = [seances.get(c, 0) for c, i in ETUDIANTS.items()
             if i.get("annee") == 6 and not i.get("erasmus")]
    moyenne6 = _stats.mean(vals6) if vals6 else 16
    sous_moyenne = [c for c, d in par_promo[6]
                    if seances.get(c, 0) < moyenne6]
    # répartir sur les créneaux : chacun sur son meilleur créneau dispo,
    # en équilibrant (le moins rempli d'abord)
    for code in sorted(sous_moyenne, key=lambda c: seances.get(c, 0)):
        crs = bons_creneaux(code)
        if not crs:
            # repli : meilleur créneau même sous MIN_DISPO
            par_cr = defaultdict(int)
            for (cr, sem) in libres.get(code, set()):
                par_cr[cr] += 1
            crs = [max(par_cr, key=par_cr.get)] if par_cr else []
        if crs:
            # créneau (parmi ses bons) avec le moins de 6A déjà placés
            cr = min(crs, key=lambda c: len(groupes[c]["6A"]))
            groupes[cr]["6A"].append(code)

    # --- 4A et 5A : équilibrage sur bons créneaux, avec pente douce ---
    for promo in (4, 5):
        codes_tries = [c for c, d in par_promo[promo]]
        n = len(codes_tries)
        tailles = _tailles_groupes(n, len(CRENEAUX), PENTE)
        cible = {cr: tailles[g] for g, cr in enumerate(CRENEAUX)}

        # dispo (nb de semaines) de chaque étudiant par créneau
        dispo_sem = {}
        for code in codes_tries:
            d = defaultdict(int)
            for (cr, sem) in libres.get(code, set()):
                d[cr] += 1
            dispo_sem[code] = d

        for code in codes_tries:
            d = dispo_sem[code]
            # créneaux où l'étudiant est SUFFISAMMENT disponible
            bons = [cr for cr in CRENEAUX if d.get(cr, 0) >= MIN_DISPO]
            if not bons:
                # aucun bon créneau : prendre le meilleur disponible quand même
                if d:
                    bons = [max(d, key=d.get)]
                else:
                    continue
            # choisir le créneau qui maximise un compromis entre :
            #   - la disponibilité de l'étudiant (venir souvent),
            #   - le fait que le groupe n'est pas déjà plein (équilibrage).
            # score = dispo_normalisée - pénalité_de_remplissage
            def score(cr):
                remplissage = len(groupes[cr][f"{promo}A"]) / max(1, cible[cr])
                dispo_norm = d.get(cr, 0) / 18.0     # ~part des semaines P5-6
                # la dispo prime ; le remplissage départage / évite l'entassement
                penalite = remplissage if remplissage < 1 else 1 + remplissage
                return dispo_norm - PENALITE_REMPLISSAGE * penalite
            cr = max(bons, key=score)
            groupes[cr][f"{promo}A"].append(code)

    return groupes


# ============================================================
#  Roulement : remplir les semaines
# ============================================================

def placer(groupes, libres, seances):
    """
    Pour chaque groupe (créneau) et chaque semaine de P5-6, remplit les
    places avec les membres disponibles les moins servis.

    Un PLAFOND de gain par groupe (part équitable + marge) empêche qu'un
    membre très disponible ne rafle les places laissées par les absents :
    un membre qui a atteint son plafond passe en dernier (il ne prend une
    place que si aucun autre membre n'est disponible cette semaine).

    Renvoie {code: [(creneau, semaine)]} — les séances P5-6 attribuées.
    """
    P = pg.periodes()
    sems56 = sorted(set(P[5]) | set(P[6]), key=_ordre)

    total = dict(seances)
    attributions = defaultdict(list)   # code -> [(cr, sem)]
    deja = defaultdict(set)            # code -> {(cr, sem)} déjà attribués
    gain = defaultdict(int)            # code -> nb de séances P5-6 gagnées

    places_promo = {"6A": PLACES_6A, "4A": PLACES_4A, "5A": PLACES_5A}

    # plafond de gain par (créneau, tag) = part équitable + marge
    # part = places × nb_semaines_exploitables / nb_membres
    plafond = {}
    for cr in CRENEAUX:
        # semaines où au moins un membre du créneau est dispo
        sems_util = set()
        for tag in ("6A", "4A", "5A"):
            for c in groupes[cr][tag]:
                sems_util |= {s for (crr, s) in libres.get(c, set()) if crr == cr}
        n_sem = len(sems_util)
        for tag in ("6A", "4A", "5A"):
            membres = groupes[cr][tag]
            if not membres:
                continue
            places = places_promo[tag]
            part = places * n_sem / len(membres)
            plafond[(cr, tag)] = part + PLAFOND_MARGE

    for cr in CRENEAUX:
        for sem in sems56:
            # on ne filtre PAS par creneau_ouvert : cette fonction est
            # calibrée sur le calendrier 5A/6A des P1-4 et ne correspond
            # pas aux disponibilités réelles en P5-6. On se fonde
            # uniquement sur la dispo réelle (cellule « — »), via `libres`.
            for tag in ("6A", "4A", "5A"):
                membres = groupes[cr][tag]
                places = places_promo[tag]
                pla = plafond.get((cr, tag), 10**9)
                # membres disponibles cette semaine sur ce créneau
                dispo = [c for c in membres
                         if (cr, sem) in libres.get(c, set())
                         and (cr, sem) not in deja[c]]
                # tri : (a atteint son plafond ?, total servi croissant)
                # ceux sous le plafond passent d'abord ; à égalité, les moins servis
                dispo.sort(key=lambda c: (gain[c] >= pla, total.get(c, 0)))
                for c in dispo[:places]:
                    attributions[c].append((cr, sem))
                    deja[c].add((cr, sem))
                    total[c] = total.get(c, 0) + 1
                    gain[c] += 1

    return attributions, total


# ============================================================
#  Export
# ============================================================

def exporter(data, attributions, groupes, ecrire):
    # index des lignes par code/semaine
    index = {}
    for code, lignes in data.items():
        index[code] = {int(l[0]): i for i, l in enumerate(lignes)
                       if len(l) >= 12 and l[0].isdigit()}

    # nom de groupe par créneau (pour l'étiquette)
    nom_groupe = {cr: f"PEDO-56-{cr[0][:3]}{cr[1]}" for cr in CRENEAUX}

    conflits, ecrits = [], 0
    for code, places in attributions.items():
        for cr, sem in places:
            i = index[code].get(sem)
            if i is None:
                continue
            col = IDX[cr]
            actuel = data[code][i][col]
            if actuel != VIDE:
                conflits.append(f"{code} sem {sem} {cr[0]} {cr[1]} : '{actuel}'")
                continue
            if ecrire:
                data[code][i][col] = f"Pédo-soin ({nom_groupe[cr]})"
            ecrits += 1

    if conflits:
        print(f"\n⚠️  {len(conflits)} conflit(s) — rien n'est écrit :")
        for c in conflits[:12]:
            print(f"     {c}")
        raise SystemExit("Disponibilité P5-6 mal calculée.")

    print(f"\n  {ecrits} séances P5-6 placées, sans conflit.")
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

def rapport(groupes, attributions, total, seances):
    print("=" * 66)
    print("  PÉDO-SOIN — RATTRAPAGE PÉRIODES 5-6")
    print("=" * 66)

    # composition des groupes
    print("\n  Composition des groupes (membres) :")
    for g, cr in enumerate(CRENEAUX):
        n6 = len(groupes[cr]["6A"])
        n4 = len(groupes[cr]["4A"])
        n5 = len(groupes[cr]["5A"])
        print(f"    {cr[0]:9s} {cr[1]:3s} : 6A={n6:2d} 4A={n4:2d} 5A={n5:2d}  "
              f"(4A+5A: {n4+n5} membres)")

    # gains par promo
    for promo in (4, 5, 6):
        codes = [c for c, i in ETUDIANTS.items()
                 if i.get("annee") == promo and not i.get("erasmus")]
        avant = [seances.get(c, 0) for c in codes]
        apres = [total.get(c, 0) for c in codes]
        gains = [total.get(c, 0) - seances.get(c, 0) for c in codes]
        actifs = [g for g in gains if g > 0]
        print(f"\n  {promo}A :")
        print(f"    avant P5-6 : min={min(avant)}, max={max(avant)}, "
              f"moy={statistics.mean(avant):.1f}, σ={statistics.pstdev(avant):.2f}")
        print(f"    après P5-6 : min={min(apres)}, max={max(apres)}, "
              f"moy={statistics.mean(apres):.1f}, σ={statistics.pstdev(apres):.2f}")
        if actifs:
            print(f"    {len(actifs)}/{len(codes)} ont gagné des séances "
                  f"(moy +{statistics.mean(actifs):.1f})")


def main():
    ecrire = "--export" in sys.argv
    data = charger_pedo()
    seances = seances_actuelles(data)
    libres = libres_par_etudiant()
    groupes = composer_groupes(seances, libres)
    attributions, total = placer(groupes, libres, seances)
    rapport(groupes, attributions, total, seances)
    exporter(data, attributions, groupes, ecrire)


if __name__ == "__main__":
    main()