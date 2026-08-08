# ============================================================
#  export.py — Génère un CSV par étudiant
#  Lignes = semaines, colonnes = 10 vacations
#  + un résumé en tête de fichier
# ============================================================

import csv
import os

from calendrier import liste_semaines, JOURS, MOMENTS, numero_periode
from poly import calculer_planning_salle, calculer_planning_etudiant

DOSSIER_SORTIE = "planning_csv"


def _colonnes_vacations():
    """Renvoie l'entête des 10 colonnes de vacation."""
    return [f"{jour} {moment}" for jour in JOURS for moment in MOMENTS]


def exporter_etudiant(code, data, dossier):
    """Génère le CSV d'un étudiant."""
    info  = data["info"]
    stats = data["stats"]
    vacs  = data["vacations"]

    chemin = os.path.join(dossier, f"{code}.csv")

    with open(chemin, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # ── Résumé en tête ──────────────────────────────────
        writer.writerow(["RÉSUMÉ ÉTUDIANT"])
        writer.writerow(["Code",   info["code"]])
        writer.writerow(["Année",  f"{info['annee']}A"])
        writer.writerow(["Type",   info["type"]])
        writer.writerow(["Groupe", info["groupe"]])
        writer.writerow(["Vacations Poly (total)", stats["nb_poly"]])
        writer.writerow([])  # ligne vide

        # ── Grille ──────────────────────────────────────────
        entete = ["Semaine", "Période"] + _colonnes_vacations()
        writer.writerow(entete)

        for semaine in liste_semaines():
            ligne = [semaine, numero_periode(semaine)]
            for jour in JOURS:
                for moment in MOMENTS:
                    cle = (semaine, jour, moment)
                    cellule = vacs.get(cle, {"detail": ""})
                    ligne.append(cellule["detail"])
            writer.writerow(ligne)


def exporter_tous(dossier=DOSSIER_SORTIE):
    """Génère les CSV de tous les étudiants."""
    print("Calcul du planning salle (avec roulement)...")
    salle = calculer_planning_salle(avec_roulement=True)   # ← roulement activé
    print("Calcul du planning étudiant...")
    planning = calculer_planning_etudiant(salle)

    os.makedirs(dossier, exist_ok=True)

    print(f"Génération des CSV dans '{dossier}/'...")
    for code, data in planning.items():
        exporter_etudiant(code, data, dossier)

    print(f"✅ {len(planning)} fichiers CSV générés dans '{dossier}/'")

# ── Point d'entrée ──────────────────────────────────────────

if __name__ == "__main__":
    exporter_tous()