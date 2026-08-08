# ============================================================
#  roulement.py — Gestion de la capacité (roulement + débordement)
#
#  AVANT la date de séparation :
#    Roulement classique : un 4/6 en surplus saute sa 2e vacation.
#
#  À PARTIR de la date de séparation (fusion 4/6 + 5/5) :
#    Les 4/6 peuvent déborder sur les créneaux 5/5 (du même jour OU
#    de l'autre jour de leur type), si leurs membres sont disponibles.
#    Priorité : créneaux 4/6 d'abord, puis débordement 5/5, puis réduction.
#    Les 5/5 sont prioritaires sur leurs créneaux (capacité résiduelle).
# ============================================================

from etudiants import GROUPES
from calendrier import est_apres_separation, semaines_de_periode
from scenarios import JOURS_PAR_TYPE, get_config_semaine
from disponibilites import est_disponible
from donnees import CAPACITE

NB_TYPES = 5
MAX_BOXES = CAPACITE["boxes"]

# Comptage en BOX : la contrainte physique est le nombre de fauteuils.
# Un box occupé compte pour 1, quelle que soit sa composition (binôme,
# trinôme, ou 4A seul quand le 6A est absent). Les places à moitié
# vides d'un "6A absent" ne sont pas récupérées : ce serait un gain
# marginal pour une complexité importante (cf. analyse capacité).
NATURES_46 = ("4/6", "trinome", "6A absent")
NATURES_55 = ("5/5", "trinome_5")


# ============================================================
#  Helpers
# ============================================================

def _jour2_de_type(type_binome):
    return JOURS_PAR_TYPE[type_binome][1]


def _membres_dispo(groupe, semaine, jour, moment):
    """
    True si TOUS les membres 'titulaires' du groupe permettant de tenir
    le créneau sont disponibles. Pour un 4/6, il faut au moins que le
    binôme puisse fonctionner : on exige la disponibilité d'au moins un
    membre de chaque rôle présent. Approche simple : on demande qu'au
    moins un membre soit disponible (le groupe est actif).
    """
    membres = groupe.get("membres", [])
    return any(est_disponible(m, semaine, jour, moment) for m in membres)


# ============================================================
#  AVANT LA DATE — roulement classique
# ============================================================

def _reductions_avant_date(planning_salle, sems):
    reductions = {sem: set() for sem in sems}
    compteur = {}

    for sem in sorted(sems, key=lambda s: (s if s >= 36 else s + 100)):
        config = get_config_semaine(sem)
        for type_b in range(1, NB_TYPES + 1):
            jour2 = _jour2_de_type(type_b)
            moments_46 = [m for m in ("M", "AM") if config[jour2][m] == "46"]

            for moment2 in moments_46:
                creneau = (jour2, moment2)
                groupes_creneau = planning_salle[sem].get(creneau, [])
                groupes_type = [
                    g for g in groupes_creneau
                    if g.get("type") == type_b and g["nature"] in NATURES_46
                ]
                surplus = len(groupes_creneau) - MAX_BOXES
                if surplus <= 0:
                    continue
                n_a_reduire = min(surplus, len(groupes_type))
                if n_a_reduire <= 0:
                    continue
                candidats = sorted(
                    groupes_type,
                    key=lambda g: (compteur.get(g["id"], 0), g["id"])
                )
                for g in candidats[:n_a_reduire]:
                    reductions[sem].add(g["id"])
                    compteur[g["id"]] = compteur.get(g["id"], 0) + 1

    return reductions


def _appliquer_reductions(planning_salle, reductions):
    """Retire la 2e vacation des groupes réduits (avant la date)."""
    for sem, groupes_reduits in reductions.items():
        if not groupes_reduits:
            continue
        creneaux = planning_salle[sem]
        for (jour, moment), groupes in list(creneaux.items()):
            gardes = []
            for g in groupes:
                type_b = g.get("type")
                if type_b is not None:
                    jour2 = _jour2_de_type(type_b)
                    if g["id"] in groupes_reduits and jour == jour2:
                        continue
                gardes.append(g)
            creneaux[(jour, moment)] = gardes


# ============================================================
#  APRÈS LA DATE — débordement + réduction
# ============================================================

def _placer_apres_date(planning_salle, sem, compteur):
    """
    Recompose le planning de la semaine 'sem' (après la date).
    Modifie planning_salle[sem] en place.
    'compteur' : dict id_groupe -> vacations cumulées (mis à jour ici).
    Renvoie (nb_debordements, nb_reductions).
    """
    creneaux = planning_salle[sem]
    config = get_config_semaine(sem)

    # Occupation courante par créneau = nb de 5/5 présents (prioritaires)
    occupation = {}
    for cle, groupes in creneaux.items():
        occupation[cle] = sum(1 for g in groupes if g["nature"] in NATURES_55)

    nb_debord = 0
    nb_reduc = 0

    # ── Préparation : pour chaque type, ses créneaux 4/6 / 5/5
    #    et la liste de ses groupes 4/6 uniques ─────────────────
    infos_type = {}  # type_b -> {"c46":[...], "c55":[...], "groupes":[...]}
    for type_b in range(1, NB_TYPES + 1):
        j1, j2 = JOURS_PAR_TYPE[type_b]
        c46, c55 = [], []
        for jour in (j1, j2):
            for moment in ("M", "AM"):
                cle = (jour, moment)
                if config[jour][moment] == "46":
                    c46.append(cle)
                else:
                    c55.append(cle)

        groupes_46 = []
        vus = set()
        for cle in c46:
            for g in creneaux.get(cle, []):
                if g.get("type") == type_b and g["nature"] in NATURES_46:
                    if g["id"] not in vus:
                        groupes_46.append(g)
                        vus.add(g["id"])

        # Retirer ces groupes des créneaux 4/6 (on va les replacer proprement)
        for cle in c46:
            creneaux[cle] = [
                g for g in creneaux.get(cle, [])
                if not (g.get("type") == type_b and g["nature"] in NATURES_46)
            ]
            occupation[cle] = len(creneaux[cle])

        infos_type[type_b] = {"c46": c46, "c55": c55, "groupes": groupes_46}

    # Compteur du nombre de vacations attribuées à chaque groupe CETTE semaine
    obtenu = {g["id"]: 0
              for t in infos_type
              for g in infos_type[t]["groupes"]}

    def _essayer_placer(g, type_b):
        """Tente de placer 1 vacation pour g. Renvoie True si placé."""
        c46 = infos_type[type_b]["c46"]
        c55 = infos_type[type_b]["c55"]
        for cle in c46 + c55:  # 4/6 d'abord, puis débordement 5/5
            jour, moment = cle
            if occupation.get(cle, 0) >= MAX_BOXES:
                continue
            if not _membres_dispo(g, sem, jour, moment):
                continue
            # éviter de placer 2 fois le même groupe sur le même créneau
            deja = any(x["id"] == g["id"] for x in creneaux.get(cle, []))
            if deja:
                continue
            est_debord = cle in c55
            g_place = dict(g)
            if est_debord:
                g_place["debord"] = True
            creneaux.setdefault(cle, []).append(g_place)
            occupation[cle] = occupation.get(cle, 0) + 1
            return est_debord
        return None  # aucune place trouvée

    # ── PHASE 1 — une vacation pour chaque groupe (équitable) ──
    tous_groupes = [(t, g) for t in infos_type for g in infos_type[t]["groupes"]]
    tous_groupes.sort(key=lambda tg: (compteur.get(tg[1]["id"], 0), tg[1]["id"]))
    for type_b, g in tous_groupes:
        res = _essayer_placer(g, type_b)
        if res is not None:
            obtenu[g["id"]] += 1
            if res:  # True = débordement
                nb_debord += 1

    # ── PHASE 2 — deuxième vacation (moins servis d'abord) ────
    tous_groupes.sort(
        key=lambda tg: (compteur.get(tg[1]["id"], 0) + obtenu[tg[1]["id"]],
                        tg[1]["id"])
    )
    for type_b, g in tous_groupes:
        if obtenu[g["id"]] >= 2:
            continue
        res = _essayer_placer(g, type_b)
        if res is not None:
            obtenu[g["id"]] += 1
            if res:
                nb_debord += 1

    # ── Bilan : compteur cumulé + réductions (groupes < 2) ────
    for gid, n in obtenu.items():
        compteur[gid] = compteur.get(gid, 0) + n
        if n < 2:
            nb_reduc += (2 - n)
        if n == 0:
            # ne devrait plus arriver sauf créneaux totalement saturés
            nb_reduc += 0  # déjà compté ci-dessus

    return nb_debord, nb_reduc


# ============================================================
#  Fonction principale
# ============================================================

def gerer_capacite(planning_salle):
    """
    Applique la gestion de capacité :
      - avant la date : roulement classique (réductions)
      - après la date : débordement + réduction
    Modifie planning_salle en place. Renvoie (planning, stats).
    """
    sems_avant = [s for s in planning_salle if not est_apres_separation(s)]
    sems_apres = [s for s in planning_salle if est_apres_separation(s)]

    reductions = _reductions_avant_date(planning_salle, sems_avant)
    _appliquer_reductions(planning_salle, reductions)

    # Compteur cumulé initialisé avec les vacations RÉELLES d'avant la date
    # (après roulement), pour que la rotation équitable en tienne compte.
    compteur = {}
    for sem in sems_avant:
        for cle, groupes in planning_salle[sem].items():
            for g in groupes:
                if g["nature"] in NATURES_46:
                    compteur[g["id"]] = compteur.get(g["id"], 0) + 1

    # Traiter les semaines après la date dans l'ORDRE CHRONOLOGIQUE
    # (bouclage année : 16..35 sont déjà dans l'ordre naturel ici)
    sems_apres_ordonnees = sorted(
        sems_apres, key=lambda s: (s if s >= 36 else s + 100)
    )

    total_debord = 0
    total_reduc = 0
    for sem in sems_apres_ordonnees:
        d, r = _placer_apres_date(planning_salle, sem, compteur)
        total_debord += d
        total_reduc += r

    stats = {
        "reductions_avant": sum(len(s) for s in reductions.values()),
        "debordements_apres": total_debord,
        "reductions_apres": total_reduc,
    }
    return planning_salle, stats


# ============================================================
#  Mesure et vérification
# ============================================================

def mesurer_equite(planning_salle):
    vacations_groupe = {}
    for sem, creneaux in planning_salle.items():
        for cle, groupes in creneaux.items():
            for g in groupes:
                if g["nature"] in NATURES_46:
                    vacations_groupe[g["id"]] = vacations_groupe.get(g["id"], 0) + 1
    if not vacations_groupe:
        return {}
    valeurs = list(vacations_groupe.values())
    return {
        "par_groupe": vacations_groupe,
        "min": min(valeurs), "max": max(valeurs),
        "ecart": max(valeurs) - min(valeurs),
        "moyenne": sum(valeurs) / len(valeurs),
    }


def verifier_capacite(planning_salle):
    depassements = []
    for sem, creneaux in planning_salle.items():
        for (jour, moment), groupes in creneaux.items():
            if len(groupes) > MAX_BOXES:
                depassements.append((sem, jour, moment, len(groupes)))
    return depassements


# ── Diagnostic ──────────────────────────────────────────────

if __name__ == "__main__":
    from poly import calculer_planning_salle

    print("Calcul du planning salle brut...")
    salle_brut = calculer_planning_salle()

    print("Gestion de la capacité (roulement + débordement)...")
    salle_final, stats = gerer_capacite(salle_brut)

    print(f"\nStats :")
    print(f"  Réductions avant la date   : {stats['reductions_avant']}")
    print(f"  Débordements après la date : {stats['debordements_apres']}")
    print(f"  Réductions après la date   : {stats['reductions_apres']}")

    print("\nVérification capacité :")
    depass = verifier_capacite(salle_final)
    if depass:
        print(f"  ⚠️  {len(depass)} dépassements restants. Exemples :")
        for (sem, jour, moment, nb) in depass[:12]:
            print(f"     Semaine {sem:2d}  {jour} {moment}  → {nb} groupes")
    else:
        print("  ✅ Aucun dépassement")

    print("\nÉquité (vacations 4/6 par groupe) :")
    eq = mesurer_equite(salle_final)
    print(f"  min={eq['min']}, max={eq['max']}, écart={eq['ecart']}, moy={eq['moyenne']:.1f}")