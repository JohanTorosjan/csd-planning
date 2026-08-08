# ============================================================
#  absences.py — Chargement des absences des 6A depuis CSV
#
#  Lit docs/absences_6A.csv et construit INDISPO_INDIVIDUEL au
#  format attendu par le reste du pipeline :
#
#     INDISPO_INDIVIDUEL = {
#         "6101": [([45,46,...], "S"), ([2,3,...], "R")],
#         ...
#     }
#
#  Chaque cellule non vide = absence de la semaine entière. Les
#  semaines consécutives portant le MÊME symbole sont regroupées
#  en un bloc. Un changement de symbole ouvre un nouveau bloc.
#
#  Le symbole (S, X, R, ou autre) est conservé tel quel comme motif :
#  le planning affichera ce symbole, on ne cherche pas à l'interpréter.
# ============================================================

import os
import csv

_ICI = os.path.dirname(os.path.abspath(__file__))
_DOCS = os.path.join(_ICI, "..", "docs")
FICHIER_ABSENCES = os.path.join(_DOCS, "absences_6A.csv")


def _lire_texte(chemin):
    """Lecture tolérante à l'encodage."""
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with open(chemin, encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"Encodage illisible : {chemin}")


def _ordre(s):
    return s if s >= 36 else s + 100


def charger_absences(chemin=FICHIER_ABSENCES):
    """
    Renvoie INDISPO_INDIVIDUEL : {code: [(semaines, motif), ...]}.
    Regroupe les semaines consécutives de même symbole.
    """
    if not os.path.exists(chemin):
        raise SystemExit(f"Fichier d'absences introuvable : {chemin}")

    lignes = list(csv.reader(_lire_texte(chemin).splitlines(), delimiter=";"))
    if not lignes:
        return {}

    entete = lignes[0]
    # colonnes de semaines : à partir de l'index 2 (code, nom, puis semaines)
    semaines_col = []
    for i in range(2, len(entete)):
        val = entete[i].strip()
        if val.isdigit():
            semaines_col.append((i, int(val)))

    indispo = {}
    for ligne in lignes[1:]:
        if len(ligne) < 3 or not ligne[0].strip().isdigit():
            continue
        code = ligne[0].strip()

        # séquence (semaine, symbole) dans l'ordre des colonnes
        sequence = []
        for (i, sem) in semaines_col:
            symbole = ligne[i].strip() if i < len(ligne) else ""
            if symbole:
                sequence.append((sem, symbole))

        if not sequence:
            continue

        # regrouper en blocs de symbole identique et de semaines contiguës
        # dans l'ordre scolaire
        sequence.sort(key=lambda x: _ordre(x[0]))
        blocs = []
        sems_courant = [sequence[0][0]]
        motif_courant = sequence[0][1]
        for k in range(1, len(sequence)):
            sem, motif = sequence[k]
            contigu = _ordre(sem) == _ordre(sems_courant[-1]) + 1
            if motif == motif_courant and contigu:
                sems_courant.append(sem)
            else:
                blocs.append((sems_courant, motif_courant))
                sems_courant = [sem]
                motif_courant = motif
        blocs.append((sems_courant, motif_courant))

        indispo[code] = blocs

    return indispo


INDISPO_INDIVIDUEL = charger_absences()


# ── Diagnostic ──────────────────────────────────────────────

if __name__ == "__main__":
    from collections import Counter

    print(f"6A avec absences : {len(INDISPO_INDIVIDUEL)}")

    total_blocs = sum(len(b) for b in INDISPO_INDIVIDUEL.values())
    total_sem = sum(len(sems) for b in INDISPO_INDIVIDUEL.values()
                    for sems, _ in b)
    print(f"Blocs d'absence : {total_blocs}")
    print(f"Semaines-absence totales : {total_sem}")

    motifs = Counter()
    for blocs in INDISPO_INDIVIDUEL.values():
        for sems, motif in blocs:
            motifs[motif] += len(sems)
    print(f"Par motif : {dict(motifs)}")

    print(f"\nExemples :")
    for code in list(INDISPO_INDIVIDUEL)[:5]:
        print(f"  {code} : {INDISPO_INDIVIDUEL[code]}")