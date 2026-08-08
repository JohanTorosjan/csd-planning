# ============================================================
#  diag_premiere_etape.py — Bilan du planning Poly (étape 1)
#
#  Explore les CSV de planning_csv/ et dresse un état des lieux :
#    - couverture : semaines actives / neutralisées / fermées
#    - occupation des cellules (Poly, absences, à intervenir, vide)
#    - vacations par promo et par type
#    - équité intra-promo et intra-type
#    - remplissage des box par créneau
#    - disponibilité résiduelle (cellules vides réutilisables)
#
#  Lecture SEULE : ne modifie rien. À lancer après main.py.
#
#  Usage : python3 diag_premiere_etape.py [dossier]
# ============================================================

import os
import csv
import sys
import statistics
from collections import defaultdict, Counter

from etudiants import ETUDIANTS

DOSSIER_DEFAUT = "planning_csv"

COLONNES = [("lundi", "M"), ("lundi", "AM"), ("mardi", "M"), ("mardi", "AM"),
            ("mercredi", "M"), ("mercredi", "AM"), ("jeudi", "M"),
            ("jeudi", "AM"), ("vendredi", "M"), ("vendredi", "AM")]
IDX = {c: 2 + i for i, c in enumerate(COLONNES)}

VIDE = "—"


def _ordre(s):
    return s if s >= 36 else s + 100


def _info(code):
    return ETUDIANTS.get(code, {})


def _reels(codes, annee, type_=None):
    return [c for c in codes
            if _info(c).get("annee") == annee
            and not _info(c).get("erasmus")
            and (type_ is None or _info(c).get("type") == type_)]


def _fmt(vals):
    if not vals:
        return "aucune donnée"
    return (f"n={len(vals)}, min={min(vals)}, max={max(vals)}, "
            f"écart={max(vals) - min(vals)}, moy={statistics.mean(vals):.1f}, "
            f"σ={statistics.pstdev(vals):.2f}")


# ============================================================
#  Chargement
# ============================================================

def charger(dossier):
    """{code: {sem: {(jour,moment): cellule}}} + set des semaines."""
    data = {}
    semaines = set()
    for nom in sorted(os.listdir(dossier)):
        if not nom.endswith(".csv"):
            continue
        code = nom[:-4]
        cells = {}
        with open(os.path.join(dossier, nom), encoding="utf-8") as f:
            for ligne in csv.reader(f):
                if len(ligne) >= 12 and ligne[0].isdigit():
                    sem = int(ligne[0])
                    semaines.add(sem)
                    cells[sem] = {c: ligne[IDX[c]] for c in COLONNES}
        data[code] = cells
    return data, semaines


def classer(cellule):
    """Catégorie d'une cellule."""
    if cellule.startswith("Poly"):
        return "poly"
    if cellule == VIDE:
        return "vide"
    if cellule.startswith("A INTERVENIR"):
        return "a_intervenir"
    if cellule == "fermé":
        return "ferme"
    # sinon : absence individuelle (S/X/R) ou cours promo
    return "autre"


# ============================================================
#  Sections du bilan
# ============================================================

def panorama(data, semaines):
    print("=" * 66)
    print("  PANORAMA")
    print("=" * 66)
    par_annee = Counter()
    for code in data:
        i = _info(code)
        if not i.get("erasmus"):
            par_annee[i.get("annee")] += 1
    for a in (4, 5, 6):
        print(f"  {a}A : {par_annee[a]} étudiants")
    print(f"  Total : {len(data)} fichiers")
    print(f"  Semaines couvertes : {len(semaines)}")
    sems = sorted(semaines, key=_ordre)
    print(f"  De la semaine {sems[0]} à {sems[-1]}")


def occupation(data):
    print("\n" + "=" * 66)
    print("  OCCUPATION DES CELLULES (toutes promos)")
    print("=" * 66)
    compte = Counter()
    for cells in data.values():
        for sem, creneaux in cells.items():
            for cellule in creneaux.values():
                compte[classer(cellule)] += 1
    total = sum(compte.values())
    libelles = {"poly": "Poly (vacations)", "vide": "libre (—)",
                "a_intervenir": "À INTERVENIR (neutralisé)",
                "ferme": "fermé", "autre": "absence / cours"}
    for cat in ("poly", "vide", "a_intervenir", "ferme", "autre"):
        n = compte.get(cat, 0)
        print(f"  {libelles[cat]:28s} {n:7d}  ({100 * n / total:5.1f} %)")
    print(f"  {'TOTAL':28s} {total:7d}")

    ai = compte.get("a_intervenir", 0)
    if ai:
        print(f"\n  ⚠️  {ai} cellules 'À INTERVENIR' : semaines neutralisées")
        print(f"     non encore traitées (examens, restantes, etc.)")


def semaines_actives(data):
    """Une semaine est 'active' si elle contient au moins une vacation."""
    print("\n" + "=" * 66)
    print("  COUVERTURE PAR SEMAINE")
    print("=" * 66)
    etat = {}
    poly_sem = defaultdict(int)
    ai_sem = defaultdict(int)
    for cells in data.values():
        for sem, creneaux in cells.items():
            for cellule in creneaux.values():
                cat = classer(cellule)
                if cat == "poly":
                    poly_sem[sem] += 1
                elif cat == "a_intervenir":
                    ai_sem[sem] += 1

    sems = sorted(set(poly_sem) | set(ai_sem), key=_ordre)
    actives = [s for s in sems if poly_sem[s] > 0]
    neutres = [s for s in sems if ai_sem[s] > 0 and poly_sem[s] == 0]
    print(f"  Semaines avec vacations Poly : {len(actives)}")
    print(f"     {[s for s in actives]}")
    print(f"  Semaines neutralisées (À INTERVENIR only) : {len(neutres)}")
    print(f"     {[s for s in neutres]}")


def vacations(data):
    print("\n" + "=" * 66)
    print("  VACATIONS DE POLY PAR PROMO ET TYPE")
    print("=" * 66)
    total = defaultdict(int)
    for code, cells in data.items():
        for creneaux in cells.values():
            for cellule in creneaux.values():
                if classer(cellule) == "poly":
                    total[code] += 1

    for annee in (4, 5, 6):
        codes = _reels(total, annee)
        vals = [total[c] for c in codes]
        print(f"\n  {annee}A : {_fmt(vals)}")
        for t in range(1, 6):
            ct = _reels(total, annee, t)
            if ct:
                vt = [total[c] for c in ct]
                print(f"    type {t} : {_fmt(vt)}")
    return total


def remplissage_box(data):
    """Reconstruit l'occupation des créneaux par fusion des partenaires."""
    import re
    SUFFIXE = re.compile(r"\s*\([^)]*\)\s*$")

    def partenaires(cellule):
        nu = SUFFIXE.sub("", cellule)
        if " avec " not in nu:
            return []
        return [p.strip()
                for p in nu.split(" avec ", 1)[1].split("+") if p.strip()]

    brut = defaultdict(list)
    for code, cells in data.items():
        for sem, creneaux in cells.items():
            for c, cellule in creneaux.items():
                if classer(cellule) == "poly":
                    brut[(sem,) + c].append(set([code] + partenaires(cellule)))

    tailles = []
    for cle, groupes in brut.items():
        boxes = []
        for s in groupes:
            fusion = None
            for b in boxes:
                if b & s:
                    b |= s
                    fusion = b
                    break
            if fusion is None:
                boxes.append(set(s))
        tailles.append(len(boxes))

    print("\n" + "=" * 66)
    print("  REMPLISSAGE DES BOX")
    print("=" * 66)
    if not tailles:
        print("  Aucun créneau avec vacation.")
        return
    print(f"  {len(tailles)} créneaux utilisés, "
          f"moyenne {statistics.mean(tailles):.1f} box/créneau")
    d = Counter(tailles)
    for n in sorted(d):
        barre = "█" * min(d[n] // 5, 40)
        print(f"    {n:2d} box : {d[n]:4d} créneaux {barre}")
    pleins = sum(v for k, v in d.items() if k >= 19)
    print(f"  Créneaux à 19 box (pleins) : {pleins} "
          f"({100 * pleins / len(tailles):.1f} %)")


def disponibilite(data):
    print("\n" + "=" * 66)
    print("  DISPONIBILITÉ RÉSIDUELLE (cellules vides réutilisables)")
    print("=" * 66)
    for annee in (4, 5, 6):
        vals = []
        for code, cells in data.items():
            i = _info(code)
            if i.get("annee") != annee or i.get("erasmus"):
                continue
            n = sum(1 for creneaux in cells.values()
                    for cellule in creneaux.values()
                    if classer(cellule) == "vide")
            vals.append(n)
        print(f"  {annee}A demi-journées libres : {_fmt(vals)}")


# ============================================================
#  Point d'entrée
# ============================================================

def rapport(dossier=DOSSIER_DEFAUT):
    if not os.path.isdir(dossier):
        raise SystemExit(f"Dossier introuvable : {dossier}")
    data, semaines = charger(dossier)

    panorama(data, semaines)
    occupation(data)
    semaines_actives(data)
    vacations(data)
    remplissage_box(data)
    disponibilite(data)

    print("\n" + "=" * 66)
    print("  Bilan de première étape terminé.")
    print("=" * 66)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    rapport(args[0] if args else DOSSIER_DEFAUT)