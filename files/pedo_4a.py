# ============================================================
#  pedo_4a.py — Étape 5 de Pédo-soin : placement des 4A
#
#  Modèle (débutants, quota faible, avec ROULEMENT) :
#    - placement PÉRIODE PAR PÉRIODE (comme les 6A) : à chaque
#      période un 4A prend un créneau où il est disponible,
#    - cible ~SEANCES_PAR_PERIODE séances par période (roulement :
#      il ne prend qu'une PART des semaines du créneau, pas toutes),
#    - plusieurs 4A partagent un créneau en se répartissant les
#      semaines disponibles (alternance souple),
#    - PRIORITÉ FORTE à la continuité : rester sur le même créneau
#      d'une période à la suivante (idéal = une moitié d'affilée),
#      mais on autorise à changer si l'emploi du temps bloque,
#    - équité : resserrer l'écart ; déficit rattrapé en P5-6.
#
#  Entrée : planning_csv_ss (dispo 4A) + placement 5A/6A (sièges,
#           capacité résiduelle réelle par créneau/période).
#  Sortie : planning_csv_pedo (ajoute les séances 4A).
#
#  Usage : python3 pedo_4a.py            (aperçu)
#          python3 pedo_4a.py --export   (écrit planning_csv_pedo)
# ============================================================

import os
import csv
import sys
import statistics
from collections import defaultdict

from etudiants import ETUDIANTS

import pedo_groupes as pg
import pedo_6a as p6

DOSSIER_ENTREE = "planning_csv_ss"
DOSSIER_PEDO = "planning_csv_pedo"
VIDE = "—"

SEANCES_PAR_PERIODE = 4     # cible de séances par période
QUOTA_CIBLE = 8             # cible sur 2 périodes
QUOTA_MIN = 4               # minimum souhaité sur la moitié
CAPACITE = p6.CAPACITE
PERIODES_4A = (1, 2, 3, 4)  # les 4A se placent sur ces périodes

CRENEAUX = pg.CRENEAUX
IDX = pg.IDX


def _ordre(s):
    return s if s >= 36 else s + 100


# ============================================================
#  Disponibilité des 4A
# ============================================================

def libres_4a(dossier=DOSSIER_ENTREE):
    """{code: {creneau: set(semaines libres)}}"""
    res = {}
    for nom in os.listdir(dossier):
        if not nom.endswith(".csv"):
            continue
        code = nom[:-4]
        info = ETUDIANTS.get(code, {})
        if info.get("annee") != 4 or info.get("erasmus"):
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


def semaines_dispo(code, creneau, per, P, libres):
    """Semaines de la période où le 4A est libre sur ce créneau.

    On se fonde UNIQUEMENT sur la disponibilité réelle du 4A (cellule
    « — » dans son CSV). On n'utilise PAS pg.creneau_ouvert : cette
    fonction est calibrée pour les 5A/6A et fermerait à tort des créneaux
    qui sont libres pour les 4A mais où d'autres promos ont cours
    (ex : jeudi M où les 5A ont cours mais les 4A sont libres)."""
    return {s for s in P[per]
            if s in libres.get(code, {}).get(creneau, set())}


# ============================================================
#  Capacité résiduelle réelle par créneau et période
# ============================================================

def capacite_sieges(sieges, groupes5, placement6):
    """
    {periode: {creneau: (places_libres_par_semaine, nom_groupe)}}
    places = CAPACITE - 5A - 6A placés dans le groupe occupant ce créneau.
    """
    taille5 = {g["nom"]: len(g["membres"]) for g in groupes5}
    occ6 = defaultdict(int)
    for per in PERIODES_4A:
        for code, (nom, cr, sems) in placement6[per].items():
            occ6[(per, nom)] += 1

    cap = defaultdict(dict)
    for per in PERIODES_4A:
        for cr in CRENEAUX:
            libre = 0
            nom_groupe = None
            for s in sieges[per]:
                if s["creneau"] != cr:
                    continue
                nom = s["nom"]
                nom_groupe = nom
                libre += max(0, CAPACITE - taille5.get(nom, 0) - occ6.get((per, nom), 0))
            if nom_groupe is not None and libre > 0:
                cap[per][cr] = (libre, nom_groupe)
    return cap


# ============================================================
#  Placement d'une période avec roulement
# ============================================================

def placer_periode(per, codes4, P, libres, cap_periode, deja_servi,
                   creneau_precedent, sems_deja):
    """
    Affecte les 4A à des créneaux pour CETTE période, avec roulement,
    en visant le REMPLISSAGE MAXIMAL de la salle.

    Modèle :
      1. chaque 4A reçoit UN créneau attitré pour la période (le meilleur
         pour lui : continuité si possible, sinon le plus de dispo), en
         équilibrant la charge entre créneaux,
      2. on remplit chaque semaine de chaque créneau jusqu'à `places`,
         en puisant dans les 4A attitrés les MOINS servis d'abord.

    Pas de plafond : un 4A peut dépasser la cible si des places restent.
    L'équité émerge de l'ordre "moins servi d'abord".

    Renvoie {code: (creneau, nom_groupe, set(semaines))}.
    """
    creneaux_per = cap_periode.get(per, {})
    if not creneaux_per:
        return {}

    # semaines dispo de chaque 4A par créneau (hors semaines déjà prises)
    dispo = {}
    for c in codes4:
        d = {}
        for cr in creneaux_per:
            sd = semaines_dispo(c, cr, per, P, libres) - sems_deja.get(c, set())
            if sd:
                d[cr] = sd
        if d:
            dispo[c] = d

    # ---- Étape 1 : affecter chaque 4A à UN créneau attitré ----
    # Objectif : REMPLIR les créneaux. On calcule pour chaque créneau le
    # nombre de 4A à lui attitrer pour saturer ses places (roulement) :
    #   besoin ≈ places × nb_semaines / part_moyenne  — mais on vise le
    # remplissage, donc on attribue tant qu'il reste des places à couvrir.
    # semaines réellement exploitables par créneau = celles où AU MOINS
    # un 4A est disponible (on n'utilise pas creneau_ouvert, cf supra)
    sems_exploitables = {}
    for cr in creneaux_per:
        ens = set()
        for c in dispo:
            ens |= dispo[c].get(cr, set())
        sems_exploitables[cr] = sorted(ens, key=_ordre)

    cap_totale = {}          # séances-place à remplir sur le créneau
    for cr, (places, nom) in creneaux_per.items():
        n_sem = len(sems_exploitables.get(cr, []))
        cap_totale[cr] = places * n_sem

    # capacité de couverture d'un 4A sur un créneau = nb de semaines qu'il
    # peut y assurer
    charge_couverte = defaultdict(int)   # cr -> séances-place déjà couvertes
    attitre = {}

    # servir d'abord les moins servis, puis les plus contraints
    ordre = sorted(dispo, key=lambda c: (deja_servi.get(c, 0), len(dispo[c])))
    for c in ordre:
        best = None
        for cr, sems in dispo[c].items():
            besoin = cap_totale.get(cr, 0)
            reste = besoin - charge_couverte[cr]   # places encore à couvrir
            cont = 1 if creneau_precedent.get(c) == cr else 0
            # PRIORITÉ AU REMPLISSAGE : d'abord les créneaux qui ont le plus
            # de places non couvertes ; la continuité départage à égalité
            score = (reste, cont, len(sems))
            if best is None or score > best[0]:
                best = (score, cr, len(sems))
        if best:
            _, cr, n_sems = best
            attitre[c] = cr
            charge_couverte[cr] += n_sems   # ce 4A couvre ~n_sems semaines

    # ---- Étape 2 : remplir chaque semaine, moins servis d'abord ----
    par_creneau = defaultdict(list)
    for c, cr in attitre.items():
        par_creneau[cr].append(c)

    resultat = {}
    obtenu = defaultdict(set)   # code -> semaines prises cette période

    for cr, membres in par_creneau.items():
        places, nom = creneaux_per[cr]
        sems_ouvertes = sems_exploitables.get(cr, [])

        for s in sems_ouvertes:
            # 4A attitrés dispo cette semaine sur ce créneau
            dispo_sem = [c for c in membres
                         if s in dispo[c].get(cr, set()) and s not in obtenu[c]]
            # les moins servis d'abord (deja_servi + ce qu'ils ont déjà pris)
            dispo_sem.sort(key=lambda c: deja_servi.get(c, 0) + len(obtenu[c]))
            # remplir jusqu'à `places`
            for c in dispo_sem[:places]:
                obtenu[c].add(s)

    for c, cr in attitre.items():
        if obtenu[c]:
            nom = creneaux_per[cr][1]
            resultat[c] = (cr, nom, obtenu[c])

    return resultat


# ============================================================
#  Construction complète
# ============================================================

def placer_4a():
    groupes5, P, _ = p6.pe.construire()
    _, _, _, sieges, placement6, _ = p6.placer_6a()
    libres = libres_4a()
    codes4 = sorted(c for c, i in ETUDIANTS.items()
                    if i.get("annee") == 4 and not i.get("erasmus"))

    cap = capacite_sieges(sieges, groupes5, placement6)

    deja_servi = defaultdict(int)
    creneau_precedent = {}
    sems_deja = defaultdict(set)
    placement = defaultdict(dict)   # periode -> {code: (cr, nom, sems)}

    for per in PERIODES_4A:
        res = placer_periode(per, codes4, P, libres, cap, deja_servi,
                             creneau_precedent, sems_deja)
        for code, (cr, nom, sems) in res.items():
            placement[per][code] = (cr, nom, sems)
            deja_servi[code] += len(sems)
            creneau_precedent[code] = cr
            sems_deja[code] |= sems

    # cache semaines/période pour l'export
    global _PERIODE_SEMAINES
    _PERIODE_SEMAINES = {p: set(P[p]) for p in P}

    return groupes5, P, cap, placement, deja_servi


_PERIODE_SEMAINES = {}


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
        for code, (cr, nom, sems) in aff.items():
            for s in sems:
                i = index[code][s]
                col = IDX[cr]
                actuel = data[code][i][col]
                if actuel != VIDE:
                    conflits.append(
                        f"{code} sem {s} {cr[0]} {cr[1]} : trouvé '{actuel}'")
                    continue
                if ecrire:
                    data[code][i][col] = f"Pédo-soin ({nom})"
                ecrits += 1

    if conflits:
        print(f"\n⚠️  {len(conflits)} conflit(s) — rien n'est écrit :")
        for c in conflits[:12]:
            print(f"     {c}")
        raise SystemExit("Disponibilité 4A mal calculée.")

    print(f"\n  {ecrits} séances 4A placées, sans conflit.")
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

def rapport(cap, placement, deja_servi):
    print("=" * 66)
    print("  PÉDO-SOIN — PLACEMENT DES 4A")
    print("=" * 66)

    for per in PERIODES_4A:
        aff = placement[per]
        par_creneau = defaultdict(int)
        for code, (cr, nom, sems) in aff.items():
            par_creneau[cr] += 1
        print(f"\n  Période {per} : {len(aff)} 4A placés")
        for cr in CRENEAUX:
            if cr in par_creneau:
                pl = cap.get(per, {}).get(cr, (0, "?"))[0]
                print(f"      {cr[0]:9s} {cr[1]:3s} : {par_creneau[cr]} 4A "
                      f"({pl} places/sem)")

    # équité (total sur les 4 périodes)
    tous = [deja_servi.get(c, 0) for c in ETUDIANTS
            if ETUDIANTS[c].get("annee") == 4 and not ETUDIANTS[c].get("erasmus")]
    print("\n  " + "=" * 60)
    print("  ÉQUITÉ (séances 4A, périodes 1-4)")
    if tous:
        print(f"    n={len(tous)}, min={min(tous)}, max={max(tous)}, "
              f"moy={statistics.mean(tous):.1f}, méd={statistics.median(tous):.0f}, "
              f"σ={statistics.pstdev(tous):.2f}")
        atteint = sum(1 for v in tous if v >= QUOTA_MIN)
        print(f"    {atteint}/{len(tous)} atteignent le minimum ({QUOTA_MIN})")
        cible = sum(1 for v in tous if v >= QUOTA_CIBLE)
        print(f"    {cible}/{len(tous)} atteignent la cible ({QUOTA_CIBLE})")
        manque = sum(max(0, QUOTA_CIBLE - v) for v in tous)
        print(f"    déficit vs cible : {manque} séances "
              f"(~{manque / len(tous):.1f} par 4A, rattrapage P5-6)")

    # continuité : combien gardent le même créneau P1->P2 et P3->P4
    def meme(c, pa, pb):
        return (c in placement[pa] and c in placement[pb]
                and placement[pa][c][0] == placement[pb][c][0])
    codes4 = [c for c in ETUDIANTS
              if ETUDIANTS[c].get("annee") == 4 and not ETUDIANTS[c].get("erasmus")]
    cont12 = sum(1 for c in codes4 if meme(c, 1, 2))
    cont34 = sum(1 for c in codes4 if meme(c, 3, 4))
    print(f"\n  Continuité : {cont12} 4A gardent leur créneau P1->P2, "
          f"{cont34} en P3->P4")

    # remplissage : total de séances 4A placées (places de salle comblées)
    total_seances = sum(len(sems) for per in PERIODES_4A
                        for (_, _, sems) in placement[per].values())
    print(f"\n  Remplissage : {total_seances} places-semaine comblées par les 4A")


def main(export=None):
    ecrire = export if export is not None else ("--export" in sys.argv)
    groupes5, P, cap, placement, deja_servi = placer_4a()
    rapport(cap, placement, deja_servi)
    exporter(placement, ecrire)


if __name__ == "__main__":
    main()
