# ============================================================
#  logs.py — Centralisation des logs et alertes
#  Affiche dans la console + écrit dans des fichiers.
# ============================================================

import os
from datetime import datetime

DOSSIER_LOGS = "logs"
FICHIER_ALERTES = "alertes.txt"
FICHIER_LOG = "execution.log"

_LIGNES_LOG = []


def _horodatage():
    return datetime.now().strftime("%H:%M:%S")


def log(message, niveau="INFO"):
    """Écrit une ligne de log (console + tampon)."""
    ligne = f"[{_horodatage()}] {niveau:7s} {message}"
    print(ligne)
    _LIGNES_LOG.append(ligne)


def info(message):
    log(message, "INFO")


def succes(message):
    log(message, "OK")


def attention(message):
    log(message, "WARN")


def section(titre):
    """Affiche un séparateur de section."""
    barre = "=" * 60
    print(f"\n{barre}")
    print(f"  {titre}")
    print(barre)
    _LIGNES_LOG.append(f"\n{barre}")
    _LIGNES_LOG.append(f"  {titre}")
    _LIGNES_LOG.append(barre)


def ecrire_alertes(alertes, depassements, equite=None, dossier=DOSSIER_LOGS):
    """
    Écrit un fichier alertes.txt regroupant tous les problèmes détectés.
    """
    os.makedirs(dossier, exist_ok=True)
    chemin = os.path.join(dossier, FICHIER_ALERTES)

    with open(chemin, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("  RAPPORT D'ALERTES — Génération du planning Poly\n")
        f.write(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 60 + "\n\n")

        f.write(f"ALERTES DE SCÉNARIO ({len(alertes)})\n")
        f.write("-" * 60 + "\n")
        if alertes:
            for a in alertes:
                f.write(f"  ⚠️  {a['message']}\n")
        else:
            f.write("  Aucune\n")
        f.write("\n")

        f.write(f"DÉPASSEMENTS DE CAPACITÉ APRÈS ROULEMENT ({len(depassements)})\n")
        f.write("-" * 60 + "\n")
        if depassements:
            for (sem, jour, moment, nb) in depassements:
                f.write(f"  ⚠️  Semaine {sem:2d}  {jour} {moment}  "
                        f"→ {nb} groupes (max 19)\n")
        else:
            f.write("  Aucun\n")
        f.write("\n")

        if equite:
            f.write("ÉQUITÉ DES VACATIONS (groupes 4/6)\n")
            f.write("-" * 60 + "\n")
            f.write(f"  Min     : {equite['min']} vacations\n")
            f.write(f"  Max     : {equite['max']} vacations\n")
            f.write(f"  Écart   : {equite['ecart']} vacations\n")
            f.write(f"  Moyenne : {equite['moyenne']:.1f} vacations\n")
            f.write("\n")

    return chemin


def ecrire_log_execution(dossier=DOSSIER_LOGS):
    """Écrit le journal complet de l'exécution."""
    os.makedirs(dossier, exist_ok=True)
    chemin = os.path.join(dossier, FICHIER_LOG)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write("\n".join(_LIGNES_LOG))
    return chemin


def reset():
    """Vide le tampon de log (avant une nouvelle exécution)."""
    _LIGNES_LOG.clear()