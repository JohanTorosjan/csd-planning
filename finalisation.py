# ============================================================
#  finalisation.py — CSV finaux COMPLETS
#
#  Prend les CSV traités (planning_csv_restantes) et produit des
#  CSV définitifs (planning_csv_final) contenant TOUTE l'information :
#
#   Ordre de priorité par cellule :
#     1. Poly (vacation placée)        → conservée telle quelle
#     2. Indispo INDIVIDUELLE (stage,  → motif précis
#        erasmus) — prime même sur une semaine fermée
#     3. Semaine fermée                → "fermé"
#     4. Indispo PROMO (cours)         → "cours/indispo promo (motif)"
#     5. Rien                          → "—"
#
#   Plus AUCUN "A INTERVENIR" : les CSV finaux retranscrivent
#   fidèlement toutes les données d'entrée, prêts pour le
#   placement des autres disciplines.
# ============================================================

import os
import csv
import sys
from collections import defaultdict

from donnees import SEMAINES_FERMEES, INDISPO_INDIVIDUEL, INDISPO_PROMO
from etudiants import ETUDIANTS

DOSSIER_ENTREE = "planning_csv_restantes"
DOSSIER_SORTIE = "planning_csv_final"

COLONNES_VAC = [
    ("lundi", "M"), ("lundi", "AM"),
    ("mardi", "M"), ("mardi", "AM"),
    ("mercredi", "M"), ("mercredi", "AM"),
    ("jeudi", "M"), ("jeudi", "AM"),
    ("vendredi", "M"), ("vendredi", "AM"),
]

VIDE = "—"


def _est_poly(cell):
    return cell.startswith("Poly")


def _categorie(cell):
    if "(examen)" in cell:
        return "examen"
    if "(rattrap)" in cell:
        return "rattrap"
    if "(débord)" in cell:
        return "debord"
    return "normal"


# ============================================================
#  Détermination du contenu réel d'une cellule
# ============================================================

def _indispo_individuelle(code, semaine):
    """Renvoie le motif d'indispo individuelle, ou None."""
    for semaines, motif in INDISPO_INDIVIDUEL.get(code, []):
        if semaine in semaines:
            return motif
    return None


def _indispo_promo(code, semaine, jour, moment):
    """Renvoie le motif d'indispo promo sur ce créneau, ou None."""
    info = ETUDIANTS.get(code)
    if not info:
        return None
    cle = f"{info['annee']}A"
    for (j, m), motif in INDISPO_PROMO.get(cle, {}).get(semaine, []):
        if j == jour and m == moment:
            return motif
    return None


def contenu_cellule(code, semaine, jour, moment, cell_actuelle):
    """
    Détermine le contenu final d'une cellule, en appliquant l'ordre
    de priorité. cell_actuelle = ce qui est déjà dans le CSV.
    """
    # 1. Une vacation Poly est prioritaire et conservée
    if _est_poly(cell_actuelle):
        return cell_actuelle

    # 2. Indispo individuelle (stage, erasmus) — prime sur "fermé"
    motif_indiv = _indispo_individuelle(code, semaine)
    if motif_indiv:
        return motif_indiv

    # 3. Semaine fermée
    if semaine in SEMAINES_FERMEES:
        return "fermé"

    # 4. Indispo promo (cours, examen...)
    motif_promo = _indispo_promo(code, semaine, jour, moment)
    if motif_promo:
        return f"cours/indispo promo ({motif_promo})"

    # 5. Rien
    return VIDE


# ============================================================
#  Traitement d'un CSV
# ============================================================

def finaliser_csv(code, lignes):
    """Nettoie et enrichit un CSV. Renvoie (nouvelles_lignes, stats)."""
    idx_entete = None
    for i, ligne in enumerate(lignes):
        if ligne and ligne[0] == "Semaine":
            idx_entete = i
            break

    stats = {"total": 0, "normal": 0, "examen": 0, "rattrap": 0, "debord": 0}
    nouvelles = [list(l) for l in lignes]

    if idx_entete is not None:
        for i in range(idx_entete + 1, len(nouvelles)):
            ligne = nouvelles[i]
            if len(ligne) < 12:
                continue
            try:
                sem = int(ligne[0])
            except ValueError:
                continue
            for idx, (j, m) in enumerate(COLONNES_VAC):
                cell = ligne[2 + idx]
                nouveau = contenu_cellule(code, sem, j, m, cell)
                ligne[2 + idx] = nouveau
                if _est_poly(nouveau):
                    stats["total"] += 1
                    stats[_categorie(nouveau)] += 1

    # Mettre à jour l'entête
    for i, ligne in enumerate(nouvelles):
        if ligne and ligne[0] == "Vacations Poly (total)":
            nouvelles[i] = ["Vacations Poly (total)", str(stats["total"])]
            detail = (f"normal:{stats['normal']} examen:{stats['examen']} "
                      f"rattrap:{stats['rattrap']} débord:{stats['debord']}")
            if i + 1 < len(nouvelles) and nouvelles[i+1] and \
               nouvelles[i+1][0] == "Détail":
                nouvelles[i+1] = ["Détail", detail]
            else:
                nouvelles.insert(i + 1, ["Détail", detail])
            break

    return nouvelles, stats


def finaliser_tout(entree=DOSSIER_ENTREE, sortie=DOSSIER_SORTIE):
    os.makedirs(sortie, exist_ok=True)
    stats_globales = defaultdict(int)
    nb = 0
    restes_intervenir = 0

    for nom in os.listdir(entree):
        if not nom.endswith(".csv"):
            continue
        code = nom[:-4]
        with open(os.path.join(entree, nom), encoding="utf-8") as f:
            lignes = list(csv.reader(f))
        nouvelles, stats = finaliser_csv(code, lignes)

        # contrôle : plus aucun "A INTERVENIR"
        for ligne in nouvelles:
            for c in ligne:
                if isinstance(c, str) and c.startswith("A INTERVENIR"):
                    restes_intervenir += 1

        with open(os.path.join(sortie, nom), "w", newline="",
                  encoding="utf-8") as f:
            csv.writer(f).writerows(nouvelles)
        for k, v in stats.items():
            stats_globales[k] += v
        nb += 1

    print(f"Fichiers finalisés : {nb} dans {sortie}/")
    print(f"Vacations totales   : {stats_globales['total']}")
    print(f"  normal    : {stats_globales['normal']}")
    print(f"  examen    : {stats_globales['examen']}")
    print(f"  rattrapage: {stats_globales['rattrap']}")
    print(f"  débord    : {stats_globales['debord']}")
    if restes_intervenir:
        print(f"  ⚠️  {restes_intervenir} cellules 'A INTERVENIR' résiduelles !")
    else:
        print("  ✅ Aucun 'A INTERVENIR' résiduel")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    entree = args[0] if args else DOSSIER_ENTREE
    finaliser_tout(entree)