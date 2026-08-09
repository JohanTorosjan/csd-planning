# ============================================================
#  urgences.py — Placement des vacations d'URGENCES
#
#  Matière distincte, placée en DERNIER (après toute la Pédo).
#  Placement INDIVIDUEL (pas de groupes) : chaque jour, chaque
#  demi-journée (vacation), on affecte 10 étudiants.
#
#  Composition selon la ou les promo(s) "EN COURS" (= 0 étudiant
#  disponible dans la promo, un cours bloque toute la promo) :
#
#     personne en cours → ALTERNANCE entre plusieurs configs
#     5A en cours       → 5 4A + 5 6A
#     4A en cours       → 6 5A + 4 6A
#     6A en cours       → 5 4A + 5 5A
#     5A+6A en cours    → 10 4A
#     4A+6A en cours    → 10 5A
#     4A+5A en cours    → 10 6A
#
#  Objectifs :
#   - ÉQUITÉ inter-promo sur l'année (chacun ~même nombre de vacations)
#   - ÉTALEMENT temporel : éviter les blocs, répartir dans l'année
#     (on préfère un étudiant vu il y a longtemps).
#
#  Toutes les règles (compositions, proportions d'alternance, poids
#  équité/étalement, mode d'étalement) sont configurables ci-dessous.
#
#  Entrée : planning_csv_pedo   Sortie : planning_csv_urgences
#
#  Usage : python3 urgences.py            (aperçu)
#          python3 urgences.py --export   (écrit les CSV)
# ============================================================

import os
import csv
import sys
import statistics
from collections import defaultdict

from etudiants import ETUDIANTS

import pedo_groupes as pg

DOSSIER_ENTREE = "planning_csv_pedo"
DOSSIER_SORTIE = "planning_csv_urgences"
VIDE = "—"

COLONNES = pg.COLONNES        # 10 demi-journées
IDX = pg.IDX

PLACES_PAR_VACATION = 10

# ============================================================
#  CONFIGURATION (facilement modifiable)
# ============================================================

# Composition par ensemble de promos EN COURS.
# Clé = frozenset des promos en cours ; valeur = dict {promo: nb}.
COMPOSITION = {
    frozenset({5}):    {4: 5, 5: 0, 6: 5},
    frozenset({4}):    {4: 0, 5: 6, 6: 4},
    frozenset({6}):    {4: 5, 5: 5, 6: 0},
    frozenset({5, 6}): {4: 10, 5: 0, 6: 0},
    frozenset({4, 6}): {4: 0, 5: 10, 6: 0},
    frozenset({4, 5}): {4: 0, 5: 0, 6: 10},
}

# Cas "personne en cours" : ALTERNANCE entre plusieurs configs.
# Chaque config = (dict compo, poids). Les poids donnent la proportion.
ALTERNANCE = [
    ({4: 5, 5: 0, 6: 5}, 1),   # 6/4
    ({4: 0, 5: 10, 6: 0}, 1),  # 5 seuls
    ({4: 3, 5: 4, 6: 3}, 1),   # mixte 4/5/6
]

# Détection "en cours" : une promo est en cours si son nombre de
# disponibles est <= ce seuil (0 = strict : un cours bloque toute la promo).
SEUIL_EN_COURS = 0

# Étalement temporel :
#   "souple"  : pénalité de score (jamais bloquant) — recommandé
#   "strict"  : délai minimum en jours entre 2 vacations (peut bloquer)
MODE_ETALEMENT = "souple"
DELAI_MIN_JOURS = 5           # utilisé seulement en mode strict

# Poids du score (mode souple) : score = deja_servi + POIDS_RECENCE * recence
# recence = 1/(jours depuis dernière vacation) ; plus c'est récent, plus ça pénalise.
POIDS_RECENCE = 3.0


def _ordre(s):
    return s if s >= 36 else s + 100


# index temporel d'une (semaine, demi-journée) pour mesurer l'étalement.
# Jour de la semaine → offset (lundi=0 … vendredi=4), matin=0/aprem=0.5
JOUR_OFFSET = {"lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3,
               "vendredi": 4, "samedi": 5, "dimanche": 6}

# séquence chronologique réelle des semaines (36→52 puis 1→35), pour
# mesurer les écarts sans le saut artificiel du passage d'année.
_SEQUENCE = list(range(36, 53)) + list(range(1, 36))
_POSITION = {s: i for i, s in enumerate(_SEQUENCE)}


def instant(sem, col):
    """Position temporelle absolue d'une vacation (en demi-journées)."""
    jour, moment = col
    base = _POSITION.get(sem, _ordre(sem)) * 14             # 14 demi-journées/semaine
    base += JOUR_OFFSET.get(jour, 0) * 2
    base += 1 if moment == "AM" else 0
    return base


# ============================================================
#  Chargement
# ============================================================

def charger():
    data = {}
    for nom in os.listdir(DOSSIER_ENTREE):
        if nom.endswith(".csv"):
            with open(os.path.join(DOSSIER_ENTREE, nom), encoding="utf-8") as f:
                data[nom[:-4]] = [list(l) for l in csv.reader(f)]
    return data


def est_ferme(cell):
    return cell in ("fermé", "Fermé")


def annee(code):
    return ETUDIANTS.get(code, {}).get("annee")


# ============================================================
#  Placement
# ============================================================

def placer(data):
    """
    Parcourt chaque vacation et affecte 10 étudiants selon la composition.
    Renvoie :
      affectations : {(code): [(sem, col)]}
      libelles     : {(sem, col): "x/y"}  (compo appliquée)
    """
    # index des lignes par code/semaine
    index = {}
    codes = []
    for code, lignes in data.items():
        info = ETUDIANTS.get(code, {})
        if info.get("erasmus") or info.get("annee") not in (4, 5, 6):
            continue
        codes.append(code)
        index[code] = {int(l[0]): i for i, l in enumerate(lignes)
                       if len(l) >= 12 and l[0].isdigit()}

    # semaines présentes
    sems = sorted({s for c in codes for s in index[c]}, key=_ordre)

    deja = defaultdict(int)              # code -> nb vacations urgences
    dernier = {}                         # code -> instant de la dernière
    affectations = defaultdict(list)
    libelles = {}
    alt_i = 0                            # curseur d'alternance pondérée
    alt_sequence = _sequence_alternance()

    for sem in sems:
        for col in COLONNES:
            i_col = IDX[col]
            # disponibilité par promo cette vacation
            dispo = {4: [], 5: [], 6: []}
            nferme = 0
            ntot = 0
            for code in codes:
                li = index[code].get(sem)
                if li is None:
                    continue
                ntot += 1
                val = data[code][li][i_col]
                if est_ferme(val):
                    nferme += 1
                elif val == VIDE:
                    dispo[annee(code)].append(code)
            # sauter fermé / férié (moins de 10 dispo au total)
            if nferme > ntot * 0.5:
                continue
            if sum(len(v) for v in dispo.values()) < PLACES_PAR_VACATION:
                continue

            # promos en cours = disponibles <= seuil
            en_cours = frozenset(a for a in (4, 5, 6)
                                 if len(dispo[a]) <= SEUIL_EN_COURS)

            # composition à appliquer
            if en_cours in COMPOSITION:
                compo = COMPOSITION[en_cours]
                lib = _libelle(compo)
            else:
                # personne en cours (ou combinaison non prévue) : alternance
                compo = alt_sequence[alt_i % len(alt_sequence)]
                alt_i += 1
                lib = _libelle(compo)

            # remplir place par place, par promo
            inst = instant(sem, col)
            choisis = []
            for a in (4, 5, 6):
                besoin = compo.get(a, 0)
                if besoin <= 0:
                    continue
                cand = _candidats(dispo[a], deja, dernier, inst)
                choisis += cand[:besoin]

            # enregistrer
            for code in choisis:
                affectations[code].append((sem, col))
                deja[code] += 1
                dernier[code] = inst
            libelles[(sem, col)] = lib

    return affectations, libelles


def _candidats(codes_dispo, deja, dernier, inst):
    """Trie les candidats par score croissant (meilleur d'abord)."""
    def score(code):
        base = deja[code]                       # équité : moins servi = mieux
        if MODE_ETALEMENT == "strict":
            d = dernier.get(code)
            if d is not None and (inst - d) < DELAI_MIN_JOURS * 2:
                return (1, base)                # repoussé (récent), mais pas exclu
            return (0, base)
        else:
            d = dernier.get(code)
            recence = 0.0
            if d is not None:
                ecart = max(1, inst - d)
                recence = 1.0 / ecart           # récent -> grand -> pénalisé
            return (base + POIDS_RECENCE * recence,)
    return sorted(codes_dispo, key=score)


def _sequence_alternance():
    """Développe ALTERNANCE en une séquence selon les poids."""
    seq = []
    for compo, poids in ALTERNANCE:
        seq += [compo] * poids
    return seq if seq else [ALTERNANCE[0][0]]


def _libelle(compo):
    """'5 4A + 5 6A' -> '4/6', '10 5A' -> '5', etc."""
    parts = []
    for a in (6, 5, 4):
        if compo.get(a, 0) > 0:
            parts.append(str(a))
    return "/".join(parts)


# ============================================================
#  Export
# ============================================================

def exporter(data, affectations, libelles, ecrire):
    index = {}
    for code, lignes in data.items():
        index[code] = {int(l[0]): i for i, l in enumerate(lignes)
                       if len(l) >= 12 and l[0].isdigit()}

    conflits = 0
    for code, places in affectations.items():
        for sem, col in places:
            i = index[code].get(sem)
            if i is None:
                continue
            j = IDX[col]
            if data[code][i][j] != VIDE:
                conflits += 1
                continue
            if ecrire:
                lib = libelles.get((sem, col), "")
                data[code][i][j] = f"Urgences ({lib})" if lib else "Urgences"

    if conflits:
        print(f"\n⚠️  {conflits} conflit(s) — cellules déjà occupées")

    total = sum(len(v) for v in affectations.values())
    print(f"\n  {total} affectations d'urgences.")
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

def rapport(affectations, libelles):
    print("=" * 66)
    print("  URGENCES — RAPPORT")
    print("=" * 66)

    # nombre de vacations couvertes + répartition des compositions
    from collections import Counter
    compo_count = Counter(libelles.values())
    print(f"\n  {len(libelles)} vacations couvertes")
    print("  Compositions appliquées :")
    for lib, n in compo_count.most_common():
        print(f"      {n:4d} × Urgences ({lib})")

    # équité inter-promo
    for a in (4, 5, 6):
        codes = [c for c, i in ETUDIANTS.items()
                 if i.get("annee") == a and not i.get("erasmus")]
        vals = [len(affectations.get(c, [])) for c in codes]
        if vals:
            print(f"\n  {a}A ({len(vals)}) : min={min(vals)}, max={max(vals)}, "
                  f"moy={statistics.mean(vals):.1f}, "
                  f"σ={statistics.pstdev(vals):.2f}")

    # étalement : écart moyen entre 2 vacations consécutives d'un étudiant
    ecarts = []
    for code, places in affectations.items():
        if len(places) < 2:
            continue
        insts = sorted(instant(s, c) for s, c in places)
        for k in range(1, len(insts)):
            ecarts.append((insts[k] - insts[k - 1]) / 14.0)  # en semaines
    if ecarts:
        print(f"\n  Étalement : écart moyen entre 2 vacations "
              f"= {statistics.mean(ecarts):.1f} semaines "
              f"(min {min(ecarts):.1f}, méd {statistics.median(ecarts):.1f})")
        colles = sum(1 for e in ecarts if e < 0.5)
        print(f"     vacations à moins d'une demi-semaine d'écart : {colles}")


def main(export=None):
    ecrire = export if export is not None else ("--export" in sys.argv)
    data = charger()
    affectations, libelles = placer(data)
    rapport(affectations, libelles)
    exporter(data, affectations, libelles, ecrire)


if __name__ == "__main__":
    main()