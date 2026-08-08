# ============================================================
#  disponibilites.py — Disponibilité brute d'un étudiant
#  Combine les 3 niveaux de blocage :
#    1. GLOBAL     (semaines fermées)
#    2. PAR PROMO  (vacations occupées par cours/exam)
#    3. INDIVIDUEL (semaines entières d'absence)
# ============================================================
from etudiants import ETUDIANTS, ERASMUS_PRESENCE
from calendrier import position_absolue

from donnees import (
    SEMAINES_FERMEES,
    INDISPO_PROMO,
    INDISPO_INDIVIDUEL,
)
from etudiants import ETUDIANTS

def _dans_plage_erasmus(code, semaine):
    """
    Pour un Erasmus, renvoie True si la semaine est dans sa plage de présence.
    Gère le bouclage sur l'année via position_absolue.
    """
    presence = ERASMUS_PRESENCE.get(code)
    if presence is None:
        return True  # pas un Erasmus → toujours "dans sa plage"

    pos_sem   = position_absolue(semaine)
    pos_debut = position_absolue(presence["debut"])
    pos_fin   = position_absolue(presence["fin"])
    return pos_debut <= pos_sem <= pos_fin


def _semaine_fermee(semaine):
    """Niveau 1 : la semaine est-elle globalement fermée ?"""
    return semaine in SEMAINES_FERMEES


def _promo_bloquee(annee, semaine, jour, moment):
    """
    Niveau 2 : la promo (4, 5 ou 6) est-elle bloquée sur cette
    vacation précise cette semaine ?
    """
    cle = f"{annee}A"
    blocages_promo = INDISPO_PROMO.get(cle, {})
    blocages_semaine = blocages_promo.get(semaine, [])
    # Chaque blocage est ((jour, moment), motif)
    for (j, m), motif in blocages_semaine:
        if j == jour and m == moment:
            return True
    return False


def _individuel_bloque(code_etudiant, semaine):
    """
    Niveau 3 : l'étudiant est-il individuellement absent cette
    semaine (stage, erasmus...) ? Les absences sont par semaine entière.
    """
    blocages = INDISPO_INDIVIDUEL.get(code_etudiant, [])
    # Chaque blocage est (liste_semaines, motif)
    for semaines, motif in blocages:
        if semaine in semaines:
            return True
    return False


def est_disponible(code_etudiant, semaine, jour, moment):
    """
    Fonction principale : l'étudiant est-il disponible sur cette
    vacation (semaine + jour + moment) ?
    Dispo SEULEMENT si aucun des 3 niveaux ne le bloque.
    """
    # Niveau 1 — global
    if _semaine_fermee(semaine):
        return False

    if code_etudiant in ERASMUS_PRESENCE and not _dans_plage_erasmus(code_etudiant, semaine):
        return False
    
    # Niveau 3 — individuel
    if _individuel_bloque(code_etudiant, semaine):
        return False

    # Niveau 2 — promo
    annee = ETUDIANTS[code_etudiant]["annee"]
    if _promo_bloquee(annee, semaine, jour, moment):
        return False

    return True


def raison_indisponibilite(code_etudiant, semaine, jour, moment):
    """
    Renvoie la raison du blocage (pour le debug / l'export),
    ou None si l'étudiant est disponible.
    """
    if _semaine_fermee(semaine):
        return f"fermé ({SEMAINES_FERMEES[semaine]})"

    blocages = INDISPO_INDIVIDUEL.get(code_etudiant, [])
    for semaines, motif in blocages:
        if semaine in semaines:
            return f"individuel ({motif})"

    annee = ETUDIANTS[code_etudiant]["annee"]
    cle = f"{annee}A"
    for (j, m), motif in INDISPO_PROMO.get(cle, {}).get(semaine, []):
        if j == jour and m == moment:
            return f"promo ({motif})"

    return None


# ── Diagnostic ──────────────────────────────────────────────

if __name__ == "__main__":
    # Quelques tests avec les données fictives
    tests = [
        ("4101", 36, "lundi", "M"),
        ("4101", 1,  "lundi", "M"),   # si semaine 1 fermée
        ("5101", 10, "lundi", "M"),   # si promo 5A bloquée
        ("6101", 12, "lundi", "M"),   # si individuel
    ]

    print("Tests de disponibilité :")
    for code, sem, jour, moment in tests:
        if code not in ETUDIANTS:
            print(f"  {code} n'existe pas, test ignoré")
            continue
        dispo = est_disponible(code, sem, jour, moment)
        raison = raison_indisponibilite(code, sem, jour, moment)
        statut = "✅ dispo" if dispo else f"❌ bloqué — {raison}"
        print(f"  {code}  sem {sem:2d}  {jour} {moment:2s}  → {statut}")