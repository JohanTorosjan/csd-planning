# ============================================================
#  main.py — Orchestrateur complet du planning Poly
# ============================================================

import logs
from poly import calculer_planning_salle, calculer_planning_etudiant
from roulement import gerer_capacite, mesurer_equite, verifier_capacite

from export import exporter_etudiant, DOSSIER_SORTIE
from etudiants import ETUDIANTS, GROUPES
import os

from neutralisation import motif_lisible
from poly import SEMAINES_NEUTRALISEES

from calendrier import liste_semaines


def _effectifs_reels():
    """Compte les effectifs réels par promo depuis ETUDIANTS
    (hors Erasmus), plutôt que de se fier à des constantes figées."""
    from collections import Counter
    c = Counter(i["annee"] for i in ETUDIANTS.values()
                if not i.get("erasmus"))
    return c.get(4, 0), c.get(5, 0), c.get(6, 0)


def main():
    logs.reset()
    logs.section("GÉNÉRATION DU PLANNING POLY")
    n4, n5, n6 = _effectifs_reels()
    logs.info(f"Effectifs : {n4} 4A, {n5} 5A, {n6} 6A "
              f"({len(ETUDIANTS)} étudiants)")
    logs.info(f"Groupes générés : {len(GROUPES)}")

    # ── 1. Planning salle brut ──────────────────────────────
    logs.section("ÉTAPE 1 — Planning salle (brut)")
    salle_brut = calculer_planning_salle(avec_roulement=False)
    logs.succes(f"{len(salle_brut)} semaines actives calculées")

    # Alertes de scénario
    from scenarios import ALERTES
    if ALERTES:
        logs.attention(f"{len(ALERTES)} alerte(s) de scénario détectée(s)")
        for a in ALERTES:
            logs.attention(f"  {a['message']}")
    else:
        logs.succes("Aucune alerte de scénario")

    # Capacité avant roulement
    depass_avant = verifier_capacite(salle_brut)

    from donnees import SEMAINES_EXAMEN

    logs.section("Semaines neutralisées (traitement manuel)")
    def _ordre(s): return s if s >= 36 else s + 100
    for sem in sorted(SEMAINES_NEUTRALISEES, key=_ordre):
        motifs = motif_lisible(SEMAINES_NEUTRALISEES[sem])
        logs.attention(f"  Semaine {sem} : {motifs}")
    actives = [s for s in liste_semaines() if s not in SEMAINES_NEUTRALISEES]
    logs.info(f"Total : {len(SEMAINES_NEUTRALISEES)} semaines neutralisées, "
              f"{len(actives)} actives")

    # ── 2. Capacité (roulement + débordement) ───────────────
    logs.section("ÉTAPE 2 — Capacité (roulement + débordement)")
    salle_final, stats = gerer_capacite(salle_brut)
    logs.info(f"Réductions avant la date   : {stats['reductions_avant']}")
    logs.info(f"Débordements après la date : {stats['debordements_apres']}")
    logs.info(f"Réductions après la date   : {stats['reductions_apres']}")

    depass_apres = verifier_capacite(salle_final)
    if depass_apres:
        logs.attention(f"{len(depass_apres)} dépassement(s) restant(s) après capacité")
        for (sem, jour, moment, nb) in depass_apres:
            logs.attention(f"  Semaine {sem} {jour} {moment} → {nb} groupes")
    else:
        logs.succes("Capacité respectée partout")

    # ── 3. Équité ───────────────────────────────────────────
    logs.section("ÉTAPE 3 — Équité")
    equite = mesurer_equite(salle_final)
    logs.info(f"Vacations 4/6 par groupe : min={equite['min']}, "
              f"max={equite['max']}, écart={equite['ecart']}, "
              f"moy={equite['moyenne']:.1f}")

    # ── 4. Planning étudiant + export ───────────────────────
    logs.section("ÉTAPE 4 — Export CSV")
    planning = calculer_planning_etudiant(salle_final)
    os.makedirs(DOSSIER_SORTIE, exist_ok=True)
    for code, data in planning.items():
        exporter_etudiant(code, data, DOSSIER_SORTIE)
    logs.succes(f"{len(planning)} fichiers CSV générés dans '{DOSSIER_SORTIE}/'")

    # ── 5. Écriture des fichiers de logs ────────────────────
    logs.section("ÉTAPE 5 — Rapports")
    chemin_alertes = logs.ecrire_alertes(ALERTES, depass_apres, equite)
    chemin_log = logs.ecrire_log_execution()
    logs.succes(f"Alertes écrites dans '{chemin_alertes}'")
    logs.succes(f"Journal écrit dans '{chemin_log}'")


if __name__ == "__main__":
    main()