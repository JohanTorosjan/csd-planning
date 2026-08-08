# ============================================================
#  scenarios.py — Choix des dispositions 4/6 vs 5/5 par semaine
#
#  Modèle : chaque JOUR reçoit une config parmi 4 :
#    A → 4/6 matin, 5/5 aprem   (défaut, réparti)      coût 0
#    B → 5/5 matin, 4/6 aprem   (réparti alternatif)   coût 1
#    C → tout 4/6 (M + AM)      (concentré)            coût 10
#    D → tout 5/5 (M + AM)      (concentré)            coût 10
#
#  Pour chaque semaine, on énumère les combinaisons de configs
#  (force brute légère) et on garde la combinaison VALIDE de coût
#  minimal — valide = chaque type a 2 créneaux 4/6 + 2 créneaux 5/5,
#  et chaque config respecte les indisponibilités des promos.
#  Si aucune combinaison valide → alerte + config par défaut.
#
#  Interface get_repartition(type, semaine) inchangée (wrapper).
# ============================================================

import itertools
from donnees import INDISPO_PROMO, INVERSER_MATIN_APREM

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi"]

JOURS_PAR_TYPE = {
    1: ("lundi",    "mardi"),
    2: ("mardi",    "mercredi"),
    3: ("mercredi", "jeudi"),
    4: ("jeudi",    "vendredi"),
    5: ("vendredi", "lundi"),
}

# Configs d'un jour : nature de (M, AM), et coût de préférence
CONFIGS = {
    "A": {"M": "46", "AM": "55", "cout": 0},   # réparti défaut
    "B": {"M": "55", "AM": "46", "cout": 1},   # réparti alternatif
    "C": {"M": "46", "AM": "46", "cout": 10},  # concentré 4/6
    "D": {"M": "55", "AM": "55", "cout": 10},  # concentré 5/5
}
ORDRE_CONFIGS = ["A", "B", "C", "D"]

ALERTES = []
_CACHE_SEMAINE = {}   # semaine -> dict {jour: {"M":nat, "AM":nat}}


def _promo_libre(annee, semaine, jour, moment):
    cle = f"{annee}A"
    for (j, m), motif in INDISPO_PROMO.get(cle, {}).get(semaine, []):
        if j == jour and m == moment:
            return False
    return True


def _config_valide_pour_jour(code_config, jour, semaine):
    """
    Une config de jour est valide si, pour chaque demi-journée,
    la promo qui l'occupe (4/6 → 4A+6A, 5/5 → 5A) est libre.
    """
    cfg = CONFIGS[code_config]
    for moment in ("M", "AM"):
        nature = cfg[moment]
        if nature == "46":
            if not _promo_libre(4, semaine, jour, moment):
                return False
            if not _promo_libre(6, semaine, jour, moment):
                return False
        else:  # "55"
            if not _promo_libre(5, semaine, jour, moment):
                return False
    return True


def _type_bien_servi(combo_par_jour):
    """
    Vérifie que CHAQUE type a exactement 2 créneaux 4/6 et 2 créneaux 5/5
    sur ses 2 jours. combo_par_jour : {jour: code_config}
    """
    for t, (j1, j2) in JOURS_PAR_TYPE.items():
        n46 = 0
        for jour in (j1, j2):
            cfg = CONFIGS[combo_par_jour[jour]]
            n46 += sum(1 for m in ("M", "AM") if cfg[m] == "46")
        if n46 != 2:
            return False
    return True


def _calculer_config_semaine(semaine):
    """
    Force brute légère : trouve la meilleure combinaison de configs
    (une par jour) pour cette semaine. Renvoie {jour: {"M":nat,"AM":nat}}.
    """
    options = {}
    jours_bloques = []
    for jour in JOURS:
        valides = [c for c in ORDRE_CONFIGS
                   if _config_valide_pour_jour(c, jour, semaine)]
        options[jour] = valides if valides else None
        if not valides:
            jours_bloques.append(jour)

    # Cas 1 : un ou plusieurs jours n'ont aucune config valide
    if jours_bloques:
        details = ", ".join(_detail_jour_bloque(j, semaine) for j in jours_bloques)
        ALERTES.append({
            "semaine": semaine,
            "jours":   jours_bloques,
            "message": (f"Semaine {semaine} : aucune disposition possible pour "
                        f"{details} — défaut appliqué"),
        })
        return _config_defaut()

    # Recherche de la meilleure combinaison
    meilleure = None
    meilleur_cout = None
    for combo in itertools.product(*[options[j] for j in JOURS]):
        combo_par_jour = dict(zip(JOURS, combo))
        if not _type_bien_servi(combo_par_jour):
            continue
        cout = sum(CONFIGS[c]["cout"] for c in combo)
        if meilleur_cout is None or cout < meilleur_cout:
            meilleur_cout = cout
            meilleure = combo_par_jour

    # Cas 2 : aucune combinaison ne satisfait tous les types
    if meilleure is None:
            # Couplage : chaque type peut être servable seul, mais pas tous ensemble.
            # On montre les configs possibles par jour pour localiser le conflit.
            detail_jours = []
            for jour in JOURS:
                codes = options[jour]
                detail_jours.append(f"{jour}={'/'.join(codes)}")
            ALERTES.append({
                "semaine": semaine,
                "jours":   JOURS,
                "message": (f"Semaine {semaine} : conflit de couplage, aucune "
                            f"combinaison ne sert tous les types 2+2 — "
                            f"configs possibles : {', '.join(detail_jours)} — défaut appliqué"),
            })
            return _config_defaut()

    resultat = {}
    for jour, code in meilleure.items():
        cfg = CONFIGS[code]
        resultat[jour] = {"M": cfg["M"], "AM": cfg["AM"]}
    return resultat


def _detail_jour_bloque(jour, semaine):
    """Explique pourquoi un jour n'a aucune config valide (quelle promo bloque)."""
    blocages = []
    for moment in ("M", "AM"):
        promos_bloquees = []
        if not _promo_libre(4, semaine, jour, moment):
            promos_bloquees.append("4A")
        if not _promo_libre(5, semaine, jour, moment):
            promos_bloquees.append("5A")
        if not _promo_libre(6, semaine, jour, moment):
            promos_bloquees.append("6A")
        if promos_bloquees:
            blocages.append(f"{moment}:{'/'.join(promos_bloquees)}")
    if blocages:
        return f"{jour} ({', '.join(blocages)})"
    return jour


def _types_impossibles(options):
    """
    Identifie les types qui ne peuvent pas obtenir 2+2, en testant
    chaque type isolément avec les configs valides de ses 2 jours.
    """
    problematiques = []
    for t, (j1, j2) in JOURS_PAR_TYPE.items():
        possible = False
        for c1 in options[j1]:
            for c2 in options[j2]:
                n46 = sum(1 for m in ("M", "AM") if CONFIGS[c1][m] == "46")
                n46 += sum(1 for m in ("M", "AM") if CONFIGS[c2][m] == "46")
                if n46 == 2:
                    possible = True
                    break
            if possible:
                break
        if not possible:
            problematiques.append(t)
    return problematiques

def _config_defaut():
    """Config par défaut : tous les jours en A (4/6 matin)."""
    return {j: {"M": "46", "AM": "55"} for j in JOURS}


def _appliquer_inversion(config):
    """Inversion globale matin↔aprem si activée."""
    if not INVERSER_MATIN_APREM:
        return config
    inv = {}
    for jour, nats in config.items():
        inv[jour] = {"M": nats["AM"], "AM": nats["M"]}
    return inv


def get_config_semaine(semaine):
    """Renvoie la config de la semaine (avec cache)."""
    if semaine not in _CACHE_SEMAINE:
        _CACHE_SEMAINE[semaine] = _calculer_config_semaine(semaine)
    return _appliquer_inversion(_CACHE_SEMAINE[semaine])


def get_repartition(type_binome, semaine):
    """
    Interface inchangée : nature (46/55) de chaque demi-journée du type.
    """
    config = get_config_semaine(semaine)
    j1, j2 = JOURS_PAR_TYPE[type_binome]
    rep = {}
    for jour in (j1, j2):
        rep[(jour, "M")]  = config[jour]["M"]
        rep[(jour, "AM")] = config[jour]["AM"]
    return rep


def get_vacations_46(type_binome, semaine):
    rep = get_repartition(type_binome, semaine)
    return [vac for vac, nat in rep.items() if nat == "46"]


def get_vacations_55(type_binome, semaine):
    rep = get_repartition(type_binome, semaine)
    return [vac for vac, nat in rep.items() if nat == "55"]


def reset_alertes():
    ALERTES.clear()
    _CACHE_SEMAINE.clear()


# ── Diagnostic ──────────────────────────────────────────────

if __name__ == "__main__":
    from calendrier import liste_semaines

    print("=== Test : dispositions par semaine (force brute) ===\n")

    for sem in [36, 37, 10, 15, 45]:
        config = get_config_semaine(sem)
        print(f"── Semaine {sem} ──")
        for jour in JOURS:
            nats = config[jour]
            print(f"  {jour:9s} : M→{nats['M']}  AM→{nats['AM']}")
        print()

    reset_alertes()
    for sem in liste_semaines():
        get_config_semaine(sem)
    print(f"Total alertes sur l'année : {len(ALERTES)}")
    for a in ALERTES:
        print(f"  ⚠️  {a['message']}")