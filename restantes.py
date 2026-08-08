# ============================================================
#  restantes.py — Traitement des semaines "à intervenir"
#                 de type PATCHWORK (indispos promo partielles)
#
#  Ces semaines ne permettent pas le 2+2 parfait (force brute
#  échoue), mais une config imparfaite récupère ~90% des vacations.
#
#  Approche (toutes ces semaines sont AVANT la date de séparation,
#  donc créneaux SÉPARÉS : un créneau est soit 4/6 soit 5/5) :
#
#    1. Choisir la nature de chaque créneau (4/6 / 5/5 / rien) en
#       maximisant le total de créneaux utilement remplis, avec
#       l'objectif 2 créneaux 4/6 + 2 créneaux 5/5 par type.
#    2. Remplir chaque créneau avec les binômes de sa nature,
#       priorité aux moins servis (semaine puis année), 2 vac/sem,
#       capacité 19.
#
#  Entrée : planning_csv_examens/ (cumule avec examens déjà traités)
#  Sortie : planning_csv_restantes/ (ou --inplace)
# ============================================================

import os
import csv
import sys
from itertools import product
from collections import defaultdict

from etudiants import ETUDIANTS, GROUPES
from disponibilites import est_disponible
from donnees import CAPACITE
from scenarios import JOURS_PAR_TYPE
from calendrier import JOURS, MOMENTS
from neutralisation import detecter_semaines_neutralisees

MAX_BOXES = CAPACITE["boxes"]

DOSSIER_ENTREE = "planning_csv_examens"
DOSSIER_SORTIE = "planning_csv_restantes"

NATURES_46 = ("4/6", "trinome", "6A absent")
NATURES_55 = ("5/5", "trinome_5")

COLONNES_VAC = [
    ("lundi", "M"), ("lundi", "AM"),
    ("mardi", "M"), ("mardi", "AM"),
    ("mercredi", "M"), ("mercredi", "AM"),
    ("jeudi", "M"), ("jeudi", "AM"),
    ("vendredi", "M"), ("vendredi", "AM"),
]


# ============================================================
#  Semaines à traiter (patchwork : ni fermée, ni examen)
# ============================================================

def semaines_patchwork():
    """Semaines neutralisées de type COUPLAGE / JOUR_BLOQUE (hors examen)."""
    neutres = detecter_semaines_neutralisees()
    res = []
    for sem, motifs in neutres.items():
        if "FERMEE" in motifs or "EXAMEN" in motifs:
            continue
        res.append(sem)
    return sorted(res, key=lambda s: (s if s >= 36 else s + 100))


# ============================================================
#  Lecture / écriture CSV
# ============================================================

def charger_plannings(dossier=DOSSIER_ENTREE):
    plannings = {}
    vacations = {}
    for nom in os.listdir(dossier):
        if not nom.endswith(".csv"):
            continue
        code = nom[:-4]
        with open(os.path.join(dossier, nom), encoding="utf-8") as f:
            lignes = list(csv.reader(f))
        plannings[code] = lignes
        vac = {}
        entete = False
        for ligne in lignes:
            if ligne and ligne[0] == "Semaine":
                entete = True
                continue
            if entete and len(ligne) >= 12:
                try:
                    sem = int(ligne[0])
                except ValueError:
                    continue
                for idx, (j, m) in enumerate(COLONNES_VAC):
                    vac[(sem, j, m)] = ligne[2 + idx]
        vacations[code] = vac
    return plannings, vacations


def _est_poly(cell):
    return cell.startswith("Poly")


def compter_vacations(vacations):
    compte = defaultdict(int)
    for code, vac in vacations.items():
        for cell in vac.values():
            if _est_poly(cell):
                compte[code] += 1
    return compte


def _vacations_semaine(code, semaine, vacations, ajouts):
    n = 0
    for (jour, moment) in COLONNES_VAC:
        cle = (semaine, jour, moment)
        if _est_poly(vacations.get(code, {}).get(cle, "")):
            n += 1
        elif _est_poly(ajouts.get(code, {}).get(cle, "")):
            n += 1
    return n


# ============================================================
#  Groupes
# ============================================================

def _binomes_46_du_type(type_b):
    return [(gid, g) for gid, g in GROUPES.items()
            if g.get("type") == type_b and g["nature"] in NATURES_46]


def _binomes_55_du_type(type_b):
    return [(gid, g) for gid, g in GROUPES.items()
            if g.get("type") == type_b and g["nature"] in NATURES_55]


def _membres_dispo(membres, sem, jour, moment):
    return all(est_disponible(m, sem, jour, moment) for m in membres)


# ============================================================
#  Étape 1 : choisir la nature des créneaux
# ============================================================

def _peut_accueillir(nature, sem, jour, moment):
    """Un créneau peut être de cette nature si au moins un binôme dispo."""
    if nature == "46":
        binomes = []
        for t in _types_du_jour(jour):
            binomes += _binomes_46_du_type(t)
        return any(_membres_dispo(g["membres"], sem, jour, moment)
                   for _, g in binomes)
    if nature == "55":
        binomes = []
        for t in _types_du_jour(jour):
            binomes += _binomes_55_du_type(t)
        return any(_membres_dispo(g["membres"], sem, jour, moment)
                   for _, g in binomes)
    return False


def _types_du_jour(jour):
    return [t for t, (j1, j2) in JOURS_PAR_TYPE.items() if jour in (j1, j2)]


def choisir_natures(sem, sacrifice_cumule=None):
    """
    Choisit la nature (46 / 55 / rien) de chaque demi-journée pour
    maximiser le total de créneaux utilement remplis, avec objectif
    2 créneaux 46 + 2 créneaux 55 par type.

    SACRIFICE TOURNANT : quand plusieurs configs atteignent le score
    maximal, on choisit celle qui épargne les types déjà les plus
    sacrifiés (équité annuelle entre types). Si sacrifice_cumule est
    fourni (dict {type: nb}), il est lu ET mis à jour.

    Renvoie {(jour,moment): '46'|'55'|'rien'}.
    """
    demijours = [(j, m) for j in JOURS for m in MOMENTS]

    # Pré-calcul de faisabilité
    faisable = {}
    for (j, m) in demijours:
        faisable[(j, m, "46")] = _peut_accueillir("46", sem, j, m)
        faisable[(j, m, "55")] = _peut_accueillir("55", sem, j, m)

    def satisfaction(assign):
        """Renvoie {type: (n46, n55)} plafonnés à 2."""
        res = {}
        for t in range(1, 6):
            j1, j2 = JOURS_PAR_TYPE[t]
            n46 = n55 = 0
            for j in (j1, j2):
                for m in MOMENTS:
                    a = assign[(j, m)]
                    if a == "46" and faisable[(j, m, "46")]:
                        n46 += 1
                    elif a == "55" and faisable[(j, m, "55")]:
                        n55 += 1
            res[t] = (min(n46, 2), min(n55, 2))
        return res

    def score(assign):
        """Nombre de créneaux-types servis (max 20 = 5 types × 4)."""
        return sum(a + b for a, b in satisfaction(assign).values())

    def types_sacrifies(assign):
        """Types qui n'atteignent pas leur 2+2 dans cette config."""
        return [t for t, (n46, n55) in satisfaction(assign).items()
                if n46 < 2 or n55 < 2]

    # Force brute sur les options réalisables par demi-journée.
    options_par_creneau = []
    for (j, m) in demijours:
        opts = ["rien"]
        if faisable[(j, m, "46")]:
            opts.append("46")
        if faisable[(j, m, "55")]:
            opts.append("55")
        options_par_creneau.append(opts)

    # 1re passe : trouver le score maximal
    best_score = -1
    configs_max = []
    for combo in product(*options_par_creneau):
        assign = dict(zip(demijours, combo))
        s = score(assign)
        if s > best_score:
            best_score = s
            configs_max = [dict(assign)]
        elif s == best_score:
            configs_max.append(dict(assign))

    # 2e passe : SACRIFICE TOURNANT.
    # À score égal, choisir la config qui épargne les types déjà les plus
    # sacrifiés. Coût = vecteur trié décroissant des sacrifices cumulés
    # des types qu'on s'apprête à sacrifier ; on prend le min lexicographique.
    if sacrifice_cumule is None:
        return configs_max[0]

    def cout(assign):
        touches = [sacrifice_cumule.get(t, 0) for t in types_sacrifies(assign)]
        return sorted(touches, reverse=True)

    best = min(configs_max, key=cout)

    # Mettre à jour le compteur de sacrifices (effet de bord assumé)
    for t in types_sacrifies(best):
        sacrifice_cumule[t] = sacrifice_cumule.get(t, 0) + 1

    return best


# ============================================================
#  Étape 2 : remplir les créneaux
# ============================================================

def _moyennes_par_promo(vac_count):
    """Moyenne de vacations par promo (4, 5, 6), pour mesurer le retard."""
    par_promo = defaultdict(list)
    for code, n in vac_count.items():
        info = ETUDIANTS.get(code, {})
        if info.get("erasmus"):
            continue
        annee = info.get("annee")
        if annee in (4, 5, 6):
            par_promo[annee].append(n)
    moy = {}
    for annee, vals in par_promo.items():
        moy[annee] = sum(vals) / len(vals) if vals else 0
    return moy


def _retard(membre, vac_count, moyennes):
    """Retard d'un membre par rapport à la moyenne de sa promo.
    Plus c'est négatif, plus il est en retard (prioritaire)."""
    info = ETUDIANTS.get(membre, {})
    annee = info.get("annee")
    moy = moyennes.get(annee, 0)
    return vac_count.get(membre, 0) - moy


def _config_depuis_natures(natures):
    """Transforme {(jour,moment): '46'/'55'/'rien'} en config
    {jour: {'M':nature, 'AM':nature}} pour get_config_semaine.
    'rien' devient '55' par défaut (créneau qui sera de toute façon
    vide si personne n'est dispo — composition_creneau renverra [])."""
    config = {}
    for j in JOURS:
        config[j] = {}
        for m in MOMENTS:
            nat = natures.get((j, m), "rien")
            config[j][m] = "46" if nat == "46" else "55"
    return config


def traiter_semaine(sem, vacations, vac_count, ajouts, sacrifice_cumule=None):
    """Place les binômes sur une semaine patchwork.
    Réutilise composition_creneau (secours/trinômes gérés) en lui
    injectant NOS natures via get_config_semaine, puis place par
    équité annuelle (membres les plus en retard vs leur promo).
    sacrifice_cumule permet le sacrifice tournant entre types."""
    import composition
    import scenarios

    natures = choisir_natures(sem, sacrifice_cumule)
    moyennes = _moyennes_par_promo(vac_count)
    config_patchwork = _config_depuis_natures(natures)

    # Injection : get_config_semaine renvoie NOTRE config pour cette semaine
    orig = scenarios.get_config_semaine
    def config_injectee(semaine):
        if semaine == sem:
            return config_patchwork
        return orig(semaine)
    scenarios.get_config_semaine = config_injectee

    try:
        for (jour, moment) in [(j, m) for j in JOURS for m in MOMENTS]:
            nature = natures[(jour, moment)]
            if nature == "rien":
                continue

            # Récupérer les VRAIS groupes via composition (secours gérés)
            groupes = []
            for t in _types_du_jour(jour):
                actifs = composition.composition_creneau(t, sem, jour, moment)
                # ne garder que ceux de la nature choisie
                for g in actifs:
                    if nature == "46" and g["nature"] in NATURES_46:
                        groupes.append(g)
                    elif nature == "55" and g["nature"] in NATURES_55:
                        groupes.append(g)

            _placer_groupes(groupes, sem, jour, moment,
                            vacations, vac_count, moyennes, ajouts)
    finally:
        scenarios.get_config_semaine = orig


def _placer_groupes(groupes, sem, jour, moment,
                    vacations, vac_count, moyennes, ajouts):
    """Place une liste de groupes sur un créneau, par équité annuelle,
    en respectant capacité 19 et 2 vacations/semaine."""
    occ = 0
    deja = set()

    # Filtrer : pas déjà 2 vacations cette semaine
    ok = []
    for g in groupes:
        membres = g["membres"]
        if any(_vacations_semaine(m, sem, vacations, ajouts) >= 2
               for m in membres):
            continue
        ok.append(g)

    # Tri : équité annuelle (membre le plus en retard vs sa promo)
    def cle_tri(g):
        membres = g["membres"]
        retard = min(_retard(m, vac_count, moyennes) for m in membres)
        vs = max(_vacations_semaine(m, sem, vacations, ajouts)
                 for m in membres)
        return (retard, vs)
    ok.sort(key=cle_tri)

    for g in ok:
        if occ >= MAX_BOXES:
            break
        membres = g["membres"]
        if any(m in deja for m in membres):
            continue
        if any(_vacations_semaine(m, sem, vacations, ajouts) >= 2
               for m in membres):
            continue
        nat = g["nature"]
        for m in membres:
            autres = [x for x in membres if x != m]
            if autres:
                texte = f"Poly {nat} avec {'+'.join(autres)} (rattrap)"
            else:
                texte = f"Poly {nat} (rattrap)"
            ajouts.setdefault(m, {})[(sem, jour, moment)] = texte
            vac_count[m] += 1
            deja.add(m)
        occ += 1


# ============================================================
#  Écriture
# ============================================================

def ecrire_plannings(plannings, ajouts, inplace=False):
    dossier = DOSSIER_ENTREE if inplace else DOSSIER_SORTIE
    os.makedirs(dossier, exist_ok=True)
    for code, lignes in plannings.items():
        aj = ajouts.get(code, {})
        nouvelles = []
        entete = False
        for ligne in lignes:
            if ligne and ligne[0] == "Semaine":
                entete = True
                nouvelles.append(ligne)
                continue
            if entete and len(ligne) >= 12:
                try:
                    sem = int(ligne[0])
                except ValueError:
                    nouvelles.append(ligne)
                    continue
                ligne = list(ligne)
                for idx, (j, m) in enumerate(COLONNES_VAC):
                    if (sem, j, m) in aj:
                        ligne[2 + idx] = aj[(sem, j, m)]
                nouvelles.append(ligne)
            else:
                nouvelles.append(ligne)
        with open(os.path.join(dossier, f"{code}.csv"), "w",
                  newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(nouvelles)
    return dossier


# ============================================================
#  Point d'entrée
# ============================================================

def traiter_restantes(inplace=False):
    plannings, vacations = charger_plannings()
    vac_count = compter_vacations(vacations)

    sems = semaines_patchwork()
    print(f"Semaines patchwork à traiter : {sems}")

    # Compteur de sacrifices par type (sacrifice tournant entre semaines)
    sacrifice_cumule = {t: 0 for t in range(1, 6)}

    ajouts = {}
    for sem in sems:
        traiter_semaine(sem, vacations, vac_count, ajouts, sacrifice_cumule)

    total = sum(len(a) for a in ajouts.values())
    print(f"Vacations ajoutées (rattrapage) : {total}")
    print(f"Sacrifices par type : {sacrifice_cumule}")

    dossier = ecrire_plannings(plannings, ajouts, inplace)
    print(f"CSV écrits dans : {dossier}/")


if __name__ == "__main__":
    traiter_restantes(inplace="--inplace" in sys.argv)