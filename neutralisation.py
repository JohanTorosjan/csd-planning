# ============================================================
#  neutralisation.py — Détection des semaines "à intervenir"
#
#  Une semaine est neutralisée (aucune Poly planifiée, traitement
#  manuel / futur programme) pour l'une de ces raisons :
#    FERMEE      : vacances / fermeture (SEMAINES_FERMEES)
#    EXAMEN      : examens E / ER       (SEMAINES_EXAMEN)
#    COUPLAGE    : dispositions 2+2 impossibles (conflit de couplage)
#    JOUR_BLOQUE : au moins un jour entièrement bloqué
#
#  Les motifs se cumulent (ex : "EXAMEN+COUPLAGE").
#
#  Passe préliminaire : on calcule d'abord les scénarios pour repérer
#  les alertes, puis on en déduit la liste des semaines neutralisées
#  AVANT de construire le planning.
# ============================================================

from donnees import SEMAINES_FERMEES, SEMAINES_EXAMEN
from calendrier import liste_semaines
import scenarios


def detecter_semaines_neutralisees():
    """
    Renvoie un dict {semaine: set de motifs}.
    Ex : {1: {"FERMEE"}, 2: {"EXAMEN", "COUPLAGE"}, 18: {"EXAMEN"}, ...}
    """
    neutralisees = {}

    # 1. Semaines fermées
    for sem in SEMAINES_FERMEES:
        neutralisees.setdefault(sem, set()).add("FERMEE")

    # 2. Semaines d'examen
    for sem in SEMAINES_EXAMEN:
        neutralisees.setdefault(sem, set()).add("EXAMEN")

    # 3. Passe préliminaire : calculer les scénarios pour récupérer les alertes
    scenarios.reset_alertes()
    for sem in liste_semaines():
        if sem in SEMAINES_FERMEES or sem in SEMAINES_EXAMEN:
            continue
        scenarios.get_config_semaine(sem)  # génère l'alerte si problème

    # 4. Classer les alertes par motif
    for alerte in scenarios.ALERTES:
        sem = alerte["semaine"]
        message = alerte["message"]
        if "couplage" in message:
            neutralisees.setdefault(sem, set()).add("COUPLAGE")
        elif "aucune disposition possible" in message:
            neutralisees.setdefault(sem, set()).add("JOUR_BLOQUE")
        else:
            # filet de sécurité : tout autre problème de scénario
            neutralisees.setdefault(sem, set()).add("SCENARIO")

    return neutralisees


def motif_lisible(motifs):
    """Transforme un set de motifs en chaîne lisible triée."""
    ordre = ["FERMEE", "EXAMEN", "COUPLAGE", "JOUR_BLOQUE", "SCENARIO"]
    presents = [m for m in ordre if m in motifs]
    return "+".join(presents)


def libelle_csv(motifs):
    """Libellé affiché dans le CSV pour une semaine neutralisée."""
    traduction = {
        "FERMEE":      "VACANCES/FERMETURE",
        "EXAMEN":      "EXAMEN",
        "COUPLAGE":    "CONFLIT (couplage)",
        "JOUR_BLOQUE": "JOUR BLOQUE",
        "SCENARIO":    "SCENARIO",
    }
    ordre = ["FERMEE", "EXAMEN", "COUPLAGE", "JOUR_BLOQUE", "SCENARIO"]
    parts = [traduction[m] for m in ordre if m in motifs]
    return "A INTERVENIR (" + " + ".join(parts) + ")"


# ── Diagnostic ──────────────────────────────────────────────

if __name__ == "__main__":
    neutralisees = detecter_semaines_neutralisees()

    def ordre(s):
        return s if s >= 36 else s + 100

    print(f"=== Semaines neutralisées : {len(neutralisees)} ===\n")
    for sem in sorted(neutralisees, key=ordre):
        motifs = neutralisees[sem]
        print(f"  Semaine {sem:2d} : {motif_lisible(motifs):25s} → {libelle_csv(motifs)}")

    # Répartition par motif
    from collections import Counter
    compte = Counter()
    for motifs in neutralisees.values():
        for m in motifs:
            compte[m] += 1
    print(f"\nRépartition par motif :")
    for motif, n in compte.most_common():
        print(f"  {motif:12s} : {n}")

    total_actives = len(liste_semaines()) - len(neutralisees)
    print(f"\nSemaines actives (Poly planifiée) : {total_actives}")
    print(f"Semaines neutralisées             : {len(neutralisees)}")