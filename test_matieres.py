# ============================================================
#  test_matieres.py — Validation globale des MATIÈRES ANNEXES
#
#  Analyse le planning final (planning_csv_paro) qui contient tout
#  l'empilement : occluso, ODF, stérilisation, pano, radio, COMO, paro
#  (en plus de Poly/Pédo/urgences hérités).
#
#  Volets :
#   1) NON-ÉCRASEMENT : vérifie qu'aucune matière n'a écrasé une autre
#      (chaque cellule a au plus une matière ; les matières héritées
#      Poly/Pédo/urgences/SS sont toujours là).
#   2) CONTRAINTES PAR MATIÈRE : créneaux autorisés, places par vacation,
#      promos concernées, date de fin, quotas.
#   3) PARCOURS D'ÉTUDIANTS : pour quelques étudiants de chaque année,
#      liste de toutes leurs vacations dans les matières annexes.
#   4) ÉTALEMENT : pour chaque matière et chaque promo, l'écart moyen
#      entre deux vacations d'un même étudiant.
#
#  Lecture seule.
#
#  Usage : python3 test_matieres.py
#          python3 test_matieres.py --dossier planning_csv_paro
#          python3 test_matieres.py --seed 42
# ============================================================

import os
import csv
import sys
import random
import statistics
from collections import defaultdict, Counter

from etudiants import ETUDIANTS

import pedo_groupes as pg

COLONNES = pg.COLONNES
IDX = pg.IDX

DOSSIER = "planning_csv_paro"   # planning final (tout empilé)

try:
    from etudiants import NOMS
except Exception:
    NOMS = {}

_SEQUENCE = list(range(36, 53)) + list(range(1, 36))
_POSITION = {s: i for i, s in enumerate(_SEQUENCE)}


def _ordre(s):
    return s if s >= 36 else s + 100


def pos(sem):
    return _POSITION.get(sem, _ordre(sem))


# ------------------------------------------------------------
#  Définition des matières (pour vérifier les contraintes)
# ------------------------------------------------------------

L = {j: (j, "M") for j in ["lundi", "mardi", "mercredi", "jeudi", "vendredi"]}
A = {j: (j, "AM") for j in ["lundi", "mardi", "mercredi", "jeudi", "vendredi"]}

TOUS = COLONNES

MATIERES = {
    "Occluso": {
        "motif": "Occluso",
        "creneaux": [("lundi", "M"), ("mardi", "M"),
                     ("jeudi", "M"), ("vendredi", "M")],
        "places": {("lundi", "M"): 4, ("mardi", "M"): 4,
                   ("jeudi", "M"): 4, ("vendredi", "M"): 4},
        "promos": {4},
        "fin": 22,
    },
    "ODF": {
        "motif": "ODF",
        "creneaux": [("lundi", "AM"), ("mardi", "AM"), ("mercredi", "M"),
                     ("mercredi", "AM"), ("vendredi", "AM")],
        "places_defaut": 3,
        "promos": {5},
        "fin": 22,
    },
    "Stérilisation": {
        "motif": "Stérilisation",
        "creneaux": list(TOUS),
        "places_defaut": 1,
        "promos": {4, 5, 6},
        "fin": 22,
    },
    "Pano/CBCT": {
        "motif": "Pano",
        "creneaux": [("lundi", "AM"), ("mardi", "AM"), ("mercredi", "M"),
                     ("mercredi", "AM"), ("jeudi", "AM"), ("vendredi", "AM")],
        "places_defaut": 1,
        "promos": {5, 6},
        "fin": 22,
    },
    "Radio": {
        "motif": "Radio",
        "creneaux": list(TOUS),
        "places_special": {("mardi", "M"): 3, ("vendredi", "AM"): 3},
        "places_defaut": 4,
        "promos": {4, 5, 6},
        "fin": 22,
    },
    "COMO": {
        "motif": "COMO",
        "creneaux": [c for c in TOUS if c not in (("jeudi", "M"),
                                                  ("jeudi", "AM"))],
        "places_defaut": 3,
        "promos": {4, 5, 6},
        "fin": 22,
    },
    "Paro": {
        "motif": "Paro",
        "creneaux": [c for c in TOUS if c != ("lundi", "M")],
        "places_defaut": 4,
        "promos": {4, 5, 6},
        "fin": 22,
    },
}

# matières héritées (ne doivent pas avoir été écrasées)
MOTIFS_HERITES = ["Poly", "Pédo", "PEDO", "Urgences", "service sanitaire",
                  "SS", "stage"]


def places_attendues(mat, col):
    d = MATIERES[mat]
    if "places" in d:
        return d["places"].get(col)
    if "places_special" in d and col in d["places_special"]:
        return d["places_special"][col]
    return d.get("places_defaut")


def matiere_de_cellule(v):
    """Renvoie le nom de la matière annexe d'une cellule, ou None."""
    for mat, d in MATIERES.items():
        if d["motif"] in v:
            return mat
    return None


# ------------------------------------------------------------
#  Chargement
# ------------------------------------------------------------

def charger():
    data = {}
    for nom in os.listdir(DOSSIER):
        if not nom.endswith(".csv"):
            continue
        code = nom[:-4]
        if ETUDIANTS.get(code, {}).get("erasmus"):
            continue
        lignes = {}
        with open(os.path.join(DOSSIER, nom), encoding="utf-8") as f:
            for l in csv.reader(f):
                if len(l) >= 12 and l[0].isdigit():
                    lignes[int(l[0])] = l
        data[code] = lignes
    return data


def vacations_matiere(data, mat):
    """{code: [(sem,col)]} pour une matière donnée."""
    motif = MATIERES[mat]["motif"]
    res = defaultdict(list)
    for code, lignes in data.items():
        for sem, l in lignes.items():
            for col in COLONNES:
                if motif in l[IDX[col]]:
                    res[code].append((sem, col))
    return res


# ------------------------------------------------------------
#  Volet 1 : non-écrasement
# ------------------------------------------------------------

def volet_ecrasement(data):
    print("=" * 70)
    print("  VOLET 1 — NON-ÉCRASEMENT")
    print("=" * 70)

    # compter chaque motif de matière annexe
    compte = Counter()
    herites = Counter()
    for code, lignes in data.items():
        for sem, l in lignes.items():
            for col in COLONNES:
                v = l[IDX[col]]
                m = matiere_de_cellule(v)
                if m:
                    compte[m] += 1
                for h in MOTIFS_HERITES:
                    if h in v:
                        herites[h] += 1
                        break

    print("\n  Matières annexes présentes dans le planning final :")
    for mat in MATIERES:
        n = compte.get(mat, 0)
        flag = "" if n > 0 else "  ⚠️ ABSENTE"
        print(f"     {mat:16s}: {n}{flag}")

    print("\n  Matières héritées (doivent être intactes) :")
    for h, n in herites.most_common():
        print(f"     {h:20s}: {n}")

    # (a) une cellule ne peut pas contenir 2 matières annexes
    double = 0
    for code, lignes in data.items():
        for sem, l in lignes.items():
            for col in COLONNES:
                v = l[IDX[col]]
                nb = sum(1 for d in MATIERES.values() if d["motif"] in v)
                if nb > 1:
                    double += 1
    print(f"\n  (a) Cellules avec 2 matières superposées : {double}")

    # (b) VÉRIFICATION RIGOUREUSE : chaque matière placée à son étape
    #     (dossier intermédiaire) est-elle intacte dans le dossier final ?
    #     Détecte un écrasement même si le motif écraseur a « remplacé » le
    #     texte (cas invisible pour le simple comptage de superposition).
    print("\n  (b) Intégrité de chaque matière vs son dossier d'étape :")
    chaine = [
        ("planning_csv_occluso", "Occluso"),
        ("planning_csv_odf", "ODF"),
        ("planning_csv_sterilisation", "Stérilisation"),
        ("planning_csv_pano", "Pano"),
        ("planning_csv_radio", "Radio"),
        ("planning_csv_como", "COMO"),
        ("planning_csv_paro", "Paro"),
    ]
    total_ecrase = 0
    for dossier, motif in chaine:
        if not os.path.isdir(dossier):
            print(f"     {motif:16s}: (dossier d'étape absent, ignoré)")
            continue
        src = {}
        for nom in os.listdir(dossier):
            if nom.endswith(".csv"):
                cc = nom[:-4]
                if ETUDIANTS.get(cc, {}).get("erasmus"):
                    continue
                with open(os.path.join(dossier, nom), encoding="utf-8") as f:
                    src[cc] = {int(l[0]): l for l in csv.reader(f)
                               if len(l) >= 12 and l[0].isdigit()}
        placees = 0
        ecrasees = 0
        for cc, lignes in src.items():
            for sem, l in lignes.items():
                for col in COLONNES:
                    if motif in l[IDX[col]]:
                        placees += 1
                        lf = data.get(cc, {}).get(sem)
                        if not (lf and motif in lf[IDX[col]]):
                            ecrasees += 1
        total_ecrase += ecrasees
        flag = "" if ecrasees == 0 else "  ⚠️"
        print(f"     {motif:16s}: {placees} placées, "
              f"{ecrasees} écrasées{flag}")

    ok = (double == 0 and total_ecrase == 0)
    print(f"\n  → {'✅ aucun écrasement (ni superposition ni destruction)' if ok else '⚠️ ÉCRASEMENT DÉTECTÉ'}")


# ------------------------------------------------------------
#  Volet 2 : contraintes par matière
# ------------------------------------------------------------

def volet_contraintes(data):
    print("\n" + "=" * 70)
    print("  VOLET 2 — CONTRAINTES PAR MATIÈRE")
    print("=" * 70)

    for mat, d in MATIERES.items():
        vac = vacations_matiere(data, mat)
        # composition par vacation
        par_vac = defaultdict(list)
        for code, places in vac.items():
            for v in places:
                par_vac[v].append(code)

        # contraintes
        hors_creneau = 0
        mauvais_places = 0
        hors_promo = 0
        apres_fin = 0
        for (sem, col), membres in par_vac.items():
            if col not in d["creneaux"]:
                hors_creneau += 1
            att = places_attendues(mat, col)
            if att is not None and len(membres) != att:
                mauvais_places += 1
            if _ordre(sem) > _ordre(d["fin"]):
                apres_fin += 1
            for code in membres:
                if ETUDIANTS.get(code, {}).get("annee") not in d["promos"]:
                    hors_promo += 1

        total_vac = len(par_vac)
        total_places = sum(len(m) for m in par_vac.values())
        print(f"\n  ── {mat} ──")
        print(f"     vacations : {total_vac}, places : {total_places}")
        print(f"     hors créneau : {hors_creneau}  |  "
              f"mauvais nb places : {mauvais_places}  |  "
              f"hors promo : {hors_promo}  |  après s{d['fin']} : {apres_fin}")
        pb = hors_creneau + mauvais_places + hors_promo + apres_fin
        print(f"     → {'✅ OK' if pb == 0 else '⚠️ ' + str(pb) + ' problème(s)'}")


# ------------------------------------------------------------
#  Volet 3 : parcours d'étudiants
# ------------------------------------------------------------

def volet_parcours(data, rng):
    print("\n" + "=" * 70)
    print("  VOLET 3 — PARCOURS D'ÉTUDIANTS (matières annexes)")
    print("=" * 70)

    # pré-calcul : toutes les vacations annexes par étudiant
    vac_etud = defaultdict(list)   # code -> [(pos, sem, col, mat)]
    for code, lignes in data.items():
        for sem, l in lignes.items():
            for col in COLONNES:
                m = matiere_de_cellule(l[IDX[col]])
                if m:
                    vac_etud[code].append((pos(sem), sem, col, m))
    for code in vac_etud:
        vac_etud[code].sort()

    for a in (4, 5, 6):
        codes = [c for c, i in ETUDIANTS.items()
                 if i.get("annee") == a and not i.get("erasmus") and c in data]
        print(f"\n  ── PROMO {a}A ──")
        for code in rng.sample(codes, min(2, len(codes))):
            nom = NOMS.get(code, "")
            events = vac_etud.get(code, [])
            par_mat = Counter(m for _, _, _, m in events)
            resume = "  ".join(f"{m}:{n}" for m, n in par_mat.most_common())
            print(f"\n     {code} ({nom or '?'}) — {len(events)} vacations annexes")
            print(f"        {resume}")
            # timeline compacte
            ligne = "  ".join(
                f"s{sem}{col[0][:3]}{'M' if col[1]=='M' else 'A'}·{m[:4]}"
                for _, sem, col, m in events[:16])
            print(f"        {ligne}")
            if len(events) > 16:
                print(f"        … (+{len(events)-16} autres)")


# ------------------------------------------------------------
#  Volet 4 : étalement
# ------------------------------------------------------------

def volet_etalement(data):
    print("\n" + "=" * 70)
    print("  VOLET 4 — ÉTALEMENT (écart moyen entre 2 vacations)")
    print("=" * 70)

    for mat in MATIERES:
        vac = vacations_matiere(data, mat)
        print(f"\n  ── {mat} ──")
        for a in (4, 5, 6):
            if a not in MATIERES[mat]["promos"]:
                continue
            ecarts = []
            nb = []
            for code, places in vac.items():
                if ETUDIANTS.get(code, {}).get("annee") != a:
                    continue
                nb.append(len(places))
                if len(places) < 2:
                    continue
                ps = sorted(pos(s) for s, _ in places)
                for k in range(1, len(ps)):
                    ecarts.append(ps[k] - ps[k - 1])
            if nb:
                moy_nb = statistics.mean(nb)
                if ecarts:
                    print(f"     {a}A : {len(nb)} étud, "
                          f"moy {moy_nb:.1f} vac/étud, "
                          f"écart moyen {statistics.mean(ecarts):.1f} sem")
                else:
                    print(f"     {a}A : {len(nb)} étud, "
                          f"moy {moy_nb:.1f} vac/étud (trop peu pour écart)")


# ------------------------------------------------------------
#  Volet 5 : couverture par promo (chaque promo a-t-elle ses matières ?)
# ------------------------------------------------------------

# ce que chaque promo doit avoir (motif → cible indicative), et si la
# couverture 100% est requise (True) ou partielle acceptée (False, ex renfort)
ATTENDU_PROMO = {
    4: [("Occluso", "~4", True), ("Stérilisation", "~3", True),
        ("Radio", "6-9", True), ("COMO", "6-8", True), ("Paro", "6-8", True)],
    5: [("ODF", "4/an", True), ("Stérilisation", "~2", True),
        ("Pano", "renfort", False), ("Radio", "6-8", True),
        ("COMO", "6-8", True), ("Paro", "6-8", True)],
    6: [("Stérilisation", "~1", True), ("Pano", "~3", True),
        ("Radio", "1 attest.", True), ("COMO", "6-8", True),
        ("Paro", "6-8", True)],
}
INTERDIT_PROMO = {4: ["ODF", "Pano"], 5: ["Occluso"], 6: ["Occluso", "ODF"]}


def volet_couverture(data):
    print("\n" + "=" * 70)
    print("  VOLET 5 — COUVERTURE PAR PROMO (bonnes matières, bonnes proportions)")
    print("=" * 70)

    motifs = ["Occluso", "ODF", "Stérilisation", "Pano", "Radio",
              "COMO", "Paro"]
    compte = {}
    for code, lignes in data.items():
        c = {m: 0 for m in motifs}
        for sem, l in lignes.items():
            for col in COLONNES:
                v = l[IDX[col]]
                for m in motifs:
                    if m in v:
                        c[m] += 1
        compte[code] = c

    for promo in (4, 5, 6):
        codes = [c for c, i in ETUDIANTS.items()
                 if i.get("annee") == promo and not i.get("erasmus")
                 and c in data]
        print(f"\n  ── PROMO {promo}A ({len(codes)} étudiants) ──")
        print("     Matières attendues :")
        for motif, cible, requis_100 in ATTENDU_PROMO[promo]:
            vals = [compte[c][motif] for c in codes]
            avec = sum(1 for v in vals if v > 0)
            pct = 100 * avec / len(codes)
            if requis_100:
                mark = "✅" if pct == 100 else "⚠️"
            else:
                mark = "○"     # couverture partielle attendue (renfort)
            print(f"        {mark} {motif:14s}: {avec}/{len(codes)} "
                  f"({pct:.0f}%)  moy={statistics.mean(vals):.1f} "
                  f"[{min(vals)}-{max(vals)}]  cible {cible}")
        print("     Matières interdites :")
        for motif in INTERDIT_PROMO[promo]:
            total = sum(compte[c][motif] for c in codes)
            mark = "✅" if total == 0 else "⚠️"
            print(f"        {mark} {motif:14s}: "
                  f"{'absente' if total == 0 else str(total) + ' PRÉSENTE !'}")


# ------------------------------------------------------------

def main():
    global DOSSIER
    if "--dossier" in sys.argv:
        i = sys.argv.index("--dossier")
        if i + 1 < len(sys.argv):
            DOSSIER = sys.argv[i + 1]
    seed = None
    if "--seed" in sys.argv:
        i = sys.argv.index("--seed")
        if i + 1 < len(sys.argv):
            seed = int(sys.argv[i + 1])
    rng = random.Random(seed)

    if not os.path.isdir(DOSSIER):
        print(f"⚠️  Dossier '{DOSSIER}' introuvable. "
              f"Lance d'abord : python3 main_matieres.py")
        return

    print("#" * 70)
    print(f"  VALIDATION DES MATIÈRES ANNEXES — dossier {DOSSIER}")
    print("#" * 70 + "\n")

    data = charger()
    volet_ecrasement(data)
    volet_contraintes(data)
    volet_parcours(data, rng)
    volet_etalement(data)
    volet_couverture(data)

    print("\n" + "#" * 70)
    print("  FIN DE LA VALIDATION")
    print("#" * 70)


if __name__ == "__main__":
    main()