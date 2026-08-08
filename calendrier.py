# ============================================================
#  calendrier.py — Gestion du temps : semaines, périodes, vacations
# ============================================================

from donnees import SEMAINE_DEBUT, SEMAINE_FIN, PERIODES_DEBUT, SEMAINES_PAR_AN

# --- Jours et moments ---
JOURS   = ["lundi", "mardi", "mercredi", "jeudi", "vendredi"]
MOMENTS = ["M", "AM"]  # matin, après-midi

# Les 10 vacations d'une semaine
VACATIONS_SEMAINE = [(j, m) for j in JOURS for m in MOMENTS]


def liste_semaines():
    """
    Renvoie la liste ordonnée des numéros de semaines de l'année,
    en gérant le bouclage (ex: 36, 37... 52, 1, 2... 35).
    """
    semaines = []
    s = SEMAINE_DEBUT
    while True:
        semaines.append(s)
        if s == SEMAINE_FIN:
            break
        s += 1
        if s > SEMAINES_PAR_AN:  # bouclage en fin d'année calendaire
            s = 1
    return semaines


def position_absolue(semaine):
    """
    Convertit un numéro de semaine ISO en position absolue dans l'année
    universitaire (0 = première semaine, 1 = deuxième, etc.).
    Permet de comparer chronologiquement deux semaines malgré le bouclage.
    """
    return liste_semaines().index(semaine)


def numero_periode(semaine):
    """
    Renvoie le numéro de période (1 à 6) auquel appartient une semaine.
    """
    pos_sem = position_absolue(semaine)
    # On convertit les débuts de période en positions absolues
    debuts_pos = [position_absolue(d) for d in PERIODES_DEBUT]

    # La période est la dernière dont le début est <= à notre semaine
    periode = 1
    for i, debut_pos in enumerate(debuts_pos):
        if pos_sem >= debut_pos:
            periode = i + 1
    return periode


def semaines_de_periode(periode):
    """
    Renvoie la liste des semaines appartenant à une période donnée.
    """
    return [s for s in liste_semaines() if numero_periode(s) == periode]

def est_apres_separation(semaine):
    """
    Renvoie True si la semaine est à partir de la date de fin de
    séparation (fusion 4/6 + 5/5 active).
    """
    from donnees import SEMAINE_FIN_SEPARATION
    return position_absolue(semaine) >= position_absolue(SEMAINE_FIN_SEPARATION)
# ── Diagnostic ──────────────────────────────────────────────
if __name__ == "__main__":
    sems = liste_semaines()
    print(f"Année universitaire : {len(sems)} semaines")
    print(f"  De la semaine {SEMAINE_DEBUT} à la semaine {SEMAINE_FIN}")
    print(f"  Ordre : {sems}")
    print()
    print(est_apres_separation(36))  # False (semaine 36 = début d'année, avant sem 16)
    print(est_apres_separation(10))  # False (sem 10 avant sem 16 en position absolue)
    print(est_apres_separation(16))  # True
    print(est_apres_separation(20))  # True
    print("Découpage en périodes :")
    for p in range(1, len(PERIODES_DEBUT) + 1):
        sems_p = semaines_de_periode(p)
        if sems_p:
            print(f"  Période {p} : semaines {sems_p[0]} → {sems_p[-1]} "
                  f"({len(sems_p)} semaines)")
    print()

    # Test bouclage
    print("Test position absolue (vérifie le bouclage) :")
    for s in [SEMAINE_DEBUT, 52, 1, SEMAINE_FIN]:
        print(f"  Semaine {s:2d} → position {position_absolue(s):2d} "
              f"→ période {numero_periode(s)}")

