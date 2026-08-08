# ── CALENDRIER ──────────────────────────────────────────────
SEMAINE_DEBUT   = 36
SEMAINE_FIN     = 35
SEMAINES_PAR_AN = 52   # 52 ou 53 selon l'année ISO
PERIODES_DEBUT  = [36, 45, 2, 9, 18, 28]  # semaines de départ des 6 périodes

# ── EFFECTIFS ───────────────────────────────────────────────
NB_4A = 75
NB_5A = 75
NB_6A = 66



# Paramètre global : inverser matin ↔ après-midi pour tout le planning
# (passe scénario 1↔2 et 3↔4). Pratique pour relancer en miroir.
INVERSER_MATIN_APREM = False

# ── NIVEAU 1 : SEMAINES FERMÉES (vacances, fermeture) ───────
SEMAINES_FERMEES = {
    1: "fermeture",
    32: "fermeture",
    33: "fermeture",
}


INDISPO_PROMO = {
    "4A": {
        36: [(("lundi", "M"), "A"), (("lundi", "AM"), "A"), (("mardi", "M"), "A"), (("mardi", "AM"), "A"), (("mercredi", "M"), "A"), (("mercredi", "AM"), "A"), (("jeudi", "M"), "A"), (("jeudi", "AM"), "A"), (("vendredi", "M"), "A"), (("vendredi", "AM"), "A")],
        37: [(("lundi", "M"), "C"), (("mardi", "AM"), "C"), (("jeudi", "AM"), "C"), (("vendredi", "M"), "C")],
        38: [(("lundi", "M"), "C"), (("mardi", "AM"), "C"), (("jeudi", "AM"), "C"), (("vendredi", "M"), "C")],
        39: [(("lundi", "M"), "C"), (("mardi", "AM"), "C"), (("jeudi", "AM"), "C"), (("vendredi", "M"), "C")],
        40: [(("lundi", "M"), "C"), (("mardi", "AM"), "C"), (("jeudi", "AM"), "C"), (("vendredi", "M"), "C")],
        41: [(("lundi", "M"), "C"), (("mardi", "AM"), "C"), (("jeudi", "AM"), "C"), (("vendredi", "M"), "C")],
        42: [(("lundi", "M"), "C"), (("mardi", "AM"), "C"), (("jeudi", "AM"), "C"), (("vendredi", "M"), "C")],
        43: [(("lundi", "M"), "C"), (("mardi", "AM"), "C"), (("jeudi", "AM"), "C"), (("vendredi", "M"), "C")],
        44: [(("lundi", "M"), "C"), (("mardi", "AM"), "C"), (("jeudi", "AM"), "C"), (("vendredi", "M"), "C")],
        45: [(("mardi", "M"), "C"), (("mercredi", "AM"), "C"), (("vendredi", "M"), "C"), (("vendredi", "AM"), "C")],
        46: [(("mardi", "M"), "C"), (("mercredi", "M"), "F"), (("mercredi", "AM"), "F"), (("vendredi", "AM"), "C")],
        47: [(("mardi", "M"), "C"), (("mercredi", "AM"), "C"), (("vendredi", "AM"), "C")],
        48: [(("mardi", "M"), "C"), (("mercredi", "AM"), "C"), (("vendredi", "AM"), "C")],
        49: [(("mardi", "M"), "C"), (("mercredi", "AM"), "C"), (("vendredi", "AM"), "C")],
        50: [(("mardi", "M"), "C"), (("vendredi", "AM"), "C")],
        51: [(("mardi", "M"), "C"), (("vendredi", "AM"), "C")],
        52: [(("jeudi", "AM"), "F"), (("vendredi", "M"), "F"), (("vendredi", "AM"), "F")],
        2: [(("mercredi", "M"), "E"), (("mercredi", "AM"), "E"), (("jeudi", "M"), "E"), (("jeudi", "AM"), "E"), (("vendredi", "M"), "ER"), (("vendredi", "AM"), "ER")],
        3: [(("mardi", "M"), "C"), (("mercredi", "M"), "C"), (("vendredi", "M"), "C")],
        4: [(("mardi", "M"), "C"), (("mercredi", "M"), "C"), (("vendredi", "M"), "C")],
        5: [(("mardi", "M"), "C"), (("mercredi", "M"), "C"), (("vendredi", "M"), "C")],
        6: [(("mardi", "M"), "C"), (("mercredi", "M"), "C"), (("vendredi", "M"), "C")],
        7: [(("mardi", "M"), "C"), (("mercredi", "M"), "C"), (("vendredi", "M"), "C")],
        8: [(("mardi", "M"), "C"), (("mercredi", "M"), "C"), (("vendredi", "M"), "C")],
        9: [(("mardi", "M"), "C"), (("mercredi", "AM"), "C"), (("vendredi", "M"), "C")],
        10: [(("mardi", "M"), "C"), (("mercredi", "AM"), "C"), (("vendredi", "M"), "C")],
        11: [(("mardi", "M"), "C"), (("mercredi", "AM"), "C"), (("vendredi", "M"), "C")],
        12: [(("mardi", "M"), "C"), (("mercredi", "AM"), "C"), (("vendredi", "M"), "C")],
        13: [(("mardi", "M"), "C"), (("mercredi", "AM"), "C"), (("vendredi", "M"), "C")],
        14: [(("lundi", "M"), "F"), (("lundi", "AM"), "F"), (("mardi", "M"), "C"), (("mercredi", "AM"), "C"), (("vendredi", "M"), "C")],
        15: [(("mardi", "M"), "C"), (("mardi", "AM"), "C"), (("vendredi", "M"), "C")],
        19: [(("lundi", "M"), "E"), (("lundi", "AM"), "E"), (("mardi", "M"), "E"), (("mardi", "AM"), "E"), (("mercredi", "M"), "E"), (("mercredi", "AM"), "E"), (("jeudi", "M"), "F"), (("jeudi", "AM"), "F")],
        21: [(("lundi", "M"), "F"), (("lundi", "AM"), "F")],
        29: [(("mercredi", "M"), "F"), (("mercredi", "AM"), "F")],
    },
    "5A": {
        37: [(("lundi", "AM"), "C"), (("mardi", "M"), "C"), (("jeudi", "M"), "C")],
        38: [(("lundi", "AM"), "C"), (("mardi", "M"), "C"), (("jeudi", "M"), "C")],
        39: [(("lundi", "AM"), "C"), (("mardi", "M"), "C"), (("jeudi", "M"), "C")],
        40: [(("lundi", "AM"), "C"), (("mardi", "M"), "C"), (("jeudi", "M"), "C")],
        41: [(("lundi", "AM"), "C"), (("mardi", "M"), "C"), (("jeudi", "M"), "C")],
        42: [(("lundi", "AM"), "C"), (("mardi", "M"), "C"), (("jeudi", "M"), "C")],
        43: [(("lundi", "AM"), "C"), (("mardi", "M"), "C"), (("jeudi", "M"), "C")],
        44: [(("lundi", "AM"), "C"), (("mardi", "M"), "C"), (("jeudi", "M"), "C")],
        45: [(("lundi", "AM"), "C"), (("mercredi", "M"), "C")],
        46: [(("lundi", "AM"), "C"), (("mercredi", "M"), "F"), (("mercredi", "AM"), "F")],
        47: [(("lundi", "AM"), "C"), (("mercredi", "M"), "C")],
        48: [(("lundi", "AM"), "C"), (("mercredi", "M"), "C")],
        49: [(("lundi", "AM"), "C"), (("mercredi", "M"), "C")],
        50: [(("lundi", "AM"), "C"), (("mercredi", "M"), "C")],
        51: [(("lundi", "AM"), "C"), (("mercredi", "M"), "C")],
        52: [(("jeudi", "AM"), "F"), (("vendredi", "M"), "F"), (("vendredi", "AM"), "F")],
        2: [(("lundi", "M"), "E"), (("lundi", "AM"), "E"), (("mardi", "M"), "E"), (("mardi", "AM"), "E"), (("vendredi", "M"), "ER"), (("vendredi", "AM"), "ER")],
        3: [(("lundi", "AM"), "C"), (("jeudi", "M"), "C"), (("vendredi", "AM"), "C")],
        4: [(("lundi", "AM"), "C"), (("jeudi", "M"), "C"), (("vendredi", "AM"), "C")],
        5: [(("lundi", "AM"), "C"), (("jeudi", "M"), "C"), (("vendredi", "AM"), "C")],
        6: [(("lundi", "M"), "Af"), (("lundi", "AM"), "Af"), (("mardi", "M"), "Af"), (("mardi", "AM"), "Af"), (("mercredi", "M"), "Af"), (("mercredi", "AM"), "Af"), (("jeudi", "M"), "C"), (("jeudi", "AM"), "C"), (("vendredi", "M"), "Af"), (("vendredi", "AM"), "Af")],
        7: [(("lundi", "AM"), "C"), (("jeudi", "M"), "C"), (("vendredi", "AM"), "C")],
        8: [(("lundi", "AM"), "C"), (("jeudi", "M"), "C"), (("vendredi", "AM"), "C")],
        9: [(("lundi", "M"), "C"), (("lundi", "AM"), "C"), (("mercredi", "M"), "C")],
        10: [(("lundi", "M"), "C"), (("lundi", "AM"), "C"), (("mercredi", "M"), "C")],
        11: [(("lundi", "M"), "C"), (("lundi", "AM"), "C"), (("mercredi", "M"), "C")],
        12: [(("lundi", "M"), "C"), (("lundi", "AM"), "C"), (("mercredi", "M"), "C")],
        13: [(("lundi", "M"), "C"), (("lundi", "AM"), "C"), (("mercredi", "M"), "C")],
        14: [(("lundi", "M"), "F"), (("lundi", "AM"), "F"), (("mardi", "M"), "E"), (("mardi", "AM"), "E"), (("mercredi", "M"), "C")],
        15: [(("lundi", "M"), "C"), (("lundi", "AM"), "C"), (("mercredi", "M"), "C")],
        18: [(("lundi", "M"), "E"), (("lundi", "AM"), "E"), (("mardi", "M"), "E"), (("mardi", "AM"), "E"), (("mercredi", "M"), "E"), (("mercredi", "AM"), "E")],
        19: [(("jeudi", "M"), "F"), (("jeudi", "AM"), "F")],
        21: [(("lundi", "M"), "F"), (("lundi", "AM"), "F"), (("mardi", "M"), "E"), (("mardi", "AM"), "E")],
        22: [(("lundi", "M"), "E"), (("lundi", "AM"), "E")],
        27: [(("lundi", "M"), "E"), (("lundi", "AM"), "E")],
        29: [(("mercredi", "M"), "F"), (("mercredi", "AM"), "F")],
    },
    "6A": {
        36: [(("lundi", "M"), "C"), (("lundi", "AM"), "C"), (("mardi", "M"), "C"), (("mardi", "AM"), "C"), (("mercredi", "M"), "C"), (("mercredi", "AM"), "C"), (("jeudi", "M"), "C"), (("jeudi", "AM"), "C"), (("vendredi", "M"), "C"), (("vendredi", "AM"), "C")],
        37: [(("lundi", "M"), "C"), (("mardi", "AM"), "C"), (("jeudi", "AM"), "C"), (("vendredi", "M"), "C")],
        38: [(("lundi", "M"), "C"), (("mardi", "AM"), "C"), (("jeudi", "AM"), "C"), (("vendredi", "M"), "C")],
        39: [(("mardi", "AM"), "C"), (("jeudi", "AM"), "C")],
        46: [(("mercredi", "M"), "F"), (("mercredi", "AM"), "F")],
        50: [(("mercredi", "M"), "E"), (("mercredi", "AM"), "E"), (("jeudi", "M"), "ER"), (("jeudi", "AM"), "ER")],
        52: [(("jeudi", "AM"), "F"), (("vendredi", "M"), "F"), (("vendredi", "AM"), "F")],
        14: [(("lundi", "M"), "F"), (("lundi", "AM"), "F")],
        19: [(("jeudi", "M"), "F"), (("jeudi", "AM"), "F")],
        21: [(("lundi", "M"), "F"), (("lundi", "AM"), "F")],
        29: [(("mercredi", "M"), "F"), (("mercredi", "AM"), "F")],
    },
}

# ── NIVEAU 3 : INDISPONIBILITÉ INDIVIDUELLE ─────────────────
# {code_étudiant: [(liste_semaines, motif), ...]}
# Remplace INDISPO_INDIVIDUEL par ceci pour tester les bascules
from absences import INDISPO_INDIVIDUEL

CAPACITE = {"boxes": 19}


# ── ERASMUS (présents sur une plage de semaines seulement) ──
# Chaque Erasmus : promo (4, 5 ou 6) + plage [debut, fin]
# La plage peut boucler sur l'année (ex: 35→4 passe par 52→1).
# Le type et le binôme d'accueil sont choisis automatiquement.
ERASMUS = [
    {"promo": 4, "debut": 36, "fin": 4},   # présent semaines 36→4
    {"promo": 4, "debut": 5,  "fin": 20},
    {"promo": 5, "debut": 36, "fin": 20},
    {"promo": 6, "debut": 10, "fin": 31},
    # ... à compléter avec les vrais Erasmus
]

SEMAINE_FIN_SEPARATION = 16

# ── SEMAINES D'EXAMEN (détection automatique) ───────────────
# Une semaine contenant au moins un motif "E" ou "ER" (examen /
# réserve d'examen) est neutralisée pour la Poly : aucune vacation
# n'y est placée. Ces semaines sont à traiter manuellement.
MOTIFS_EXAMEN = {"E", "ER"}

def _detecter_semaines_examen():
    semaines = {}
    for promo, par_semaine in INDISPO_PROMO.items():
        for semaine, blocages in par_semaine.items():
            for (jour, moment), motif in blocages:
                if motif in MOTIFS_EXAMEN:
                    semaines.setdefault(semaine, set()).add(motif)
    return semaines

# {semaine: set de motifs} — ex {2: {"E","ER"}, 18: {"E"}, ...}
SEMAINES_EXAMEN = _detecter_semaines_examen()



# 4A ayant déjà validé le service sanitaire (dispensés)
REDOUBLANTS_4A = set()      # ex : {"4102", "4315"}
NB_REDOUBLANT_4A = 0        # garde-fou : doit valoir len(REDOUBLANTS_4A)


PERIODES_SERVICE_SANITAIRE = [
    (38, 44),
    (45, 51),
    (3, 9),
    (10, 16),
]


from etudiants import INDISPO_ERASMUS
for _code, _blocs in INDISPO_ERASMUS.items():
    INDISPO_INDIVIDUEL.setdefault(_code, []).extend(_blocs)

# Périodes de la Pédo-soin (fournies par l'équipe pédagogique).
# Bornes (début, fin) en numéros de semaine, bouclage d'année géré.
# Les 4 premières structurent les groupes 5A (moitié A = P1+P2,
# moitié B = P3+P4). Les périodes 5 et 6 servent au rattrapage général.
PERIODES_PEDO = [
    (36, 44),
    (45, 1),
    (2, 8),
    (9, 17),
    (18, 27),
    (28, 35),
]