# ============================================================
#  poly.py — Assemblage du planning complet
#  1. Calcule le planning "salle" (type × semaine × demi-journée)
#  2. Le réorganise côté étudiant (pour l'export CSV)
#  3. Signale les dépassements de capacité (sans les résoudre)
# ============================================================

from etudiants import ETUDIANTS, GROUPES
from calendrier import liste_semaines, JOURS, MOMENTS, numero_periode
from scenarios import get_repartition, JOURS_PAR_TYPE
from composition import composition_creneau
from disponibilites import est_disponible, raison_indisponibilite
from donnees import SEMAINES_FERMEES, INDISPO_INDIVIDUEL, INDISPO_PROMO, CAPACITE, SEMAINES_EXAMEN

from neutralisation import detecter_semaines_neutralisees, libelle_csv
SEMAINES_NEUTRALISEES = detecter_semaines_neutralisees()

NB_TYPES = 5


# ── 1. PLANNING CÔTÉ SALLE ──────────────────────────────────

def calculer_planning_salle(avec_roulement=False):
    """
    Calcule le planning salle (type × semaine × demi-journée).
    Si avec_roulement=True, applique le roulement pour respecter
    la capacité des 19 boxes.
    """
    from scenarios import reset_alertes
    reset_alertes()

    planning_salle = {}

    for semaine in liste_semaines():
        if semaine in SEMAINES_NEUTRALISEES:
                    continue  
        creneaux = {}
        for type_b in range(1, NB_TYPES + 1):
            repartition = get_repartition(type_b, semaine)
            for (jour, moment) in repartition.keys():
                actifs = composition_creneau(type_b, semaine, jour, moment)
                for groupe in actifs:
                    groupe["type"] = type_b
                    creneaux.setdefault((jour, moment), []).append(groupe)

        planning_salle[semaine] = creneaux

    # Application du roulement si demandé
    if avec_roulement:
        from roulement import calculer_reductions, appliquer_reductions
        reductions = calculer_reductions(planning_salle)
        planning_salle = appliquer_reductions(planning_salle, reductions)

    return planning_salle

# ── 2. VÉRIFICATION DE CAPACITÉ ─────────────────────────────

def verifier_capacite(planning_salle):
    """
    Parcourt le planning salle et renvoie la liste des dépassements.
    Chaque dépassement : (semaine, jour, moment, nb_groupes)
    """
    depassements = []
    max_boxes = CAPACITE["boxes"]

    for semaine, creneaux in planning_salle.items():
        for (jour, moment), groupes in creneaux.items():
            nb = len(groupes)
            if nb > max_boxes:
                depassements.append((semaine, jour, moment, nb))

    return depassements


# ── 3. PLANNING CÔTÉ ÉTUDIANT ───────────────────────────────

def _groupe_de_etudiant(code):
    """Trouve le groupe d'origine d'un étudiant (pour le résumé)."""
    for id_g, g in GROUPES.items():
        if code in g["membres"]:
            return id_g
    return None


def _detail_poly(code, groupe_actif):
    """Construit le détail d'une cellule Poly pour un étudiant."""
    nature = groupe_actif["nature"]
    autres = [m for m in groupe_actif["membres"] if m != code]
    if autres:
        return f"Poly {nature} avec {'+'.join(autres)}"
    else:
        return f"Poly {nature}"


def calculer_planning_etudiant(planning_salle):
    """
    Réorganise le planning salle côté étudiant.

    Retourne :
      planning[code] = {
        "info":      {...},
        "vacations": {(semaine, jour, moment): {"type":..., "detail":...}},
        "stats":     {"nb_poly": ...}
      }
    """
    planning = {}

    # Initialisation
    for code, info in ETUDIANTS.items():
        planning[code] = {
            "info": {
                "code":   code,
                "annee":  info["annee"],
                "type":   info["type"],
                "groupe": _groupe_de_etudiant(code),
            },
            "vacations": {},
            "stats": {"nb_poly": 0},
        }

    # Pré-indexer : pour chaque (semaine, jour, moment), quel étudiant est dans quel groupe
    poly_index = {}  # (semaine, jour, moment, code) -> groupe_actif
    for semaine, creneaux in planning_salle.items():
        for (jour, moment), groupes in creneaux.items():
            for groupe in groupes:
                for membre in groupe["membres"]:
                    poly_index[(semaine, jour, moment, membre)] = groupe

    # Remplir chaque vacation de chaque étudiant
    for code, info in ETUDIANTS.items():
        annee = info["annee"]
        for semaine in liste_semaines():
            for jour in JOURS:
                for moment in MOMENTS:
                    cle = (semaine, jour, moment)
                    cellule = _evaluer_cellule(code, annee, semaine, jour, moment,
                                               poly_index)
                    planning[code]["vacations"][cle] = cellule
                    if cellule["type"] == "poly":
                        planning[code]["stats"]["nb_poly"] += 1

    return planning


def _evaluer_cellule(code, annee, semaine, jour, moment, poly_index):
    """
    Détermine l'événement d'une vacation pour un étudiant.
    Ordre de priorité : vacances > individuel > promo > poly > libre
    """

# 0. Semaine neutralisée (fermeture, examen, couplage, jour bloqué)
    if semaine in SEMAINES_NEUTRALISEES:
        motifs = SEMAINES_NEUTRALISEES[semaine]
        return {"type": "a_intervenir", "detail": libelle_csv(motifs)}
    
    # 2. Indisponibilité individuelle (stage, erasmus)
    blocages = INDISPO_INDIVIDUEL.get(code, [])
    for semaines, motif in blocages:
        if semaine in semaines:
            # Catégorie selon le motif
            cat = "erasmus" if "erasmus" in motif.lower() else "stage"
            return {"type": cat, "detail": motif}

    # 3. Indisponibilité promo (cours/exam regroupés)
    cle_promo = f"{annee}A"
    for (j, m), motif in INDISPO_PROMO.get(cle_promo, {}).get(semaine, []):
        if j == jour and m == moment:
            return {"type": "indispo", "detail": "cours/indispo promo"}

    # 4. Poly ?
    groupe_actif = poly_index.get((semaine, jour, moment, code))
    if groupe_actif:
        detail = _detail_poly(code, groupe_actif)
        if groupe_actif.get("debord"):
            detail += " (débord)"
        return {"type": "poly", "detail": detail}

    # 5. Libre
    return {"type": "libre", "detail": "—"}


# ── Diagnostic ──────────────────────────────────────────────

if __name__ == "__main__":
    print("Calcul du planning salle...")
    salle = calculer_planning_salle()
        # Alertes de scénario (placements problématiques)
    from scenarios import ALERTES
    print(f"\nAlertes de scénario : {len(ALERTES)}")
    if ALERTES:
        for a in ALERTES:
            print(f"  ⚠️  {a['message']}")

    print(f"  {len(salle)} semaines actives calculées")

    print("\nVérification capacité...")
    depass = verifier_capacite(salle)
    if depass:
        print(f"  ⚠️  {len(depass)} dépassements détectés. Exemples :")
        for (sem, jour, moment, nb) in depass[:10]:
            print(f"     Semaine {sem:2d}  {jour} {moment}  → {nb} groupes (max {CAPACITE['boxes']})")
    else:
        print("  ✅ Aucun dépassement")

    print("\nCalcul du planning étudiant...")
    etu = calculer_planning_etudiant(salle)
    print(f"  {len(etu)} étudiants traités")

    # Aperçu d'un étudiant
    code_test = "4101"
    print(f"\n── Aperçu étudiant {code_test} ──")
    info = etu[code_test]["info"]
    stats = etu[code_test]["stats"]
    print(f"  Année {info['annee']}, type {info['type']}, groupe {info['groupe']}")
    print(f"  Total vacations Poly : {stats['nb_poly']}")
    print(f"\n  Quelques vacations (semaine 36) :")
    for jour in JOURS:
        for moment in MOMENTS:
            cle = (36, jour, moment)
            c = etu[code_test]["vacations"][cle]
            print(f"     {jour:9s} {moment:2s} : [{c['type']:8s}] {c['detail']}")