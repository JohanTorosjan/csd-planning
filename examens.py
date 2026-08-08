# ============================================================
#  examens.py — Traitement des semaines d'examen (ÉTAPE 1)
#
#  Les semaines d'examen sont neutralisées par le planning normal.
#  Ce module les RÉCUPÈRE : pour chaque jour où une promo est en
#  examen, il remplit les créneaux libérés avec les autres promos.
#
#  Il lit les CSV produits par main.py, calcule l'équité déjà
#  atteinte, puis remplit les jours d'examen selon 3 cas :
#
#    5A en examen → créneaux 5/5 pris par les 4/6 (du type du jour)
#    4A en examen → 6A seuls (type du jour) puis binômes 5/5
#    6A en examen → 4A en binôme 4/4 (secours) + 5A dispo
#    2 promos en examen → la 3e promo seule (remplissage partiel)
#
#  Priorité partout : moins de vacations d'abord + dispo + capacité 19.
#
#  Sortie : nouveau dossier 'planning_csv_examens/' par défaut,
#           ou réécriture des CSV originaux avec --inplace.
# ============================================================

import os
import csv
import sys
from collections import defaultdict

from etudiants import ETUDIANTS, GROUPES
from disponibilites import est_disponible
from donnees import INDISPO_PROMO, CAPACITE
from scenarios import JOURS_PAR_TYPE
from calendrier import JOURS, MOMENTS

MAX_BOXES = CAPACITE["boxes"]
MOTIFS_EXAMEN = {"E", "ER"}

DOSSIER_ENTREE = "planning_csv"
DOSSIER_SORTIE = "planning_csv_examens"

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
#  Détection des examens
# ============================================================

def promos_en_examen(semaine, jour):
    """
    Renvoie l'ensemble des promos (4, 5, 6) en examen ce jour-là.
    Un examen occupe la journée entière (M+AM) dans les données.
    """
    en_exam = set()
    for annee in (4, 5, 6):
        cle = f"{annee}A"
        for (j, m), motif in INDISPO_PROMO.get(cle, {}).get(semaine, []):
            if j == jour and motif in MOTIFS_EXAMEN:
                en_exam.add(annee)
    return en_exam


def semaines_examen():
    """Renvoie l'ensemble des semaines contenant au moins un examen."""
    sems = set()
    for annee in (4, 5, 6):
        cle = f"{annee}A"
        for semaine, blocages in INDISPO_PROMO.get(cle, {}).items():
            for (j, m), motif in blocages:
                if motif in MOTIFS_EXAMEN:
                    sems.add(semaine)
    return sems


# ============================================================
#  Lecture des CSV
# ============================================================

def _lire_csv(chemin):
    """Lit un CSV étudiant → (lignes_resume, entete, data_par_semaine)."""
    with open(chemin, encoding="utf-8") as f:
        lignes = list(csv.reader(f))
    return lignes


def charger_plannings(dossier=DOSSIER_ENTREE):
    """
    Charge tous les CSV. Renvoie {code: lignes_brutes} pour réécriture,
    et vacations[code][(sem,jour,moment)] = texte cellule.
    """
    plannings = {}
    vacations = {}
    for nom in os.listdir(dossier):
        if not nom.endswith(".csv"):
            continue
        code = nom[:-4]
        lignes = _lire_csv(os.path.join(dossier, nom))
        plannings[code] = lignes
        # parser les vacations
        vac = {}
        entete_vue = False
        for ligne in lignes:
            if ligne and ligne[0] == "Semaine":
                entete_vue = True
                continue
            if entete_vue and len(ligne) >= 12:
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


# ============================================================
#  Calcul de l'équité déjà atteinte
# ============================================================

def compter_vacations(vacations):
    """vac_etudiant[code] = nb de vacations Poly déjà attribuées."""
    compte = defaultdict(int)
    for code, vac in vacations.items():
        for cle, cell in vac.items():
            if _est_poly(cell):
                compte[code] += 1
    return compte


# ============================================================
#  Remplissage des créneaux d'examen
# ============================================================

def _groupe_de(code):
    for gid, g in GROUPES.items():
        if code in g["membres"]:
            return gid, g
    return None, None


def _binomes_46_du_type(type_b):
    """Renvoie les groupes 4/6 (binômes/trinômes) d'un type."""
    res = []
    for gid, g in GROUPES.items():
        if g.get("type") == type_b and g["nature"] in NATURES_46:
            res.append((gid, g))
    return res


def _binomes_55_du_type(type_b):
    res = []
    for gid, g in GROUPES.items():
        if g.get("type") == type_b and g["nature"] in NATURES_55:
            res.append((gid, g))
    return res


def _6a_du_type(type_b):
    """Renvoie les codes 6A d'un type (individuels)."""
    res = []
    for code, info in ETUDIANTS.items():
        if info.get("annee") == 6 and info.get("type") == type_b:
            res.append(code)
    return res


def _membres_dispo(membres, sem, jour, moment):
    return all(est_disponible(m, sem, jour, moment) for m in membres)


def _4a_du_type(type_b):
    """Renvoie les codes 4A d'un type (titulaires des binômes 4/6)."""
    res = []
    for gid, g in GROUPES.items():
        if g.get("type") == type_b and g["nature"] in ("4/6", "trinome"):
            for m in g["membres"]:
                if ETUDIANTS.get(m, {}).get("annee") == 4:
                    res.append(m)
    return sorted(set(res))


def _4a_absents_du_type(type_b):
    """
    Quand les 6A sont en examen : chaque groupe 4/6 tourne en "6A absent",
    les 4A présents gardent leur box (comme dans composition.py).
    Renvoie une liste de (membres_4A, libelle) — un groupe par binôme/trinôme.
    Plus de 4/4 : on ne recompose pas de paires secours.
    """
    res = []
    for gid, g in GROUPES.items():
        if g.get("type") != type_b or g["nature"] not in ("4/6", "trinome"):
            continue
        quatres = [m for m in g["membres"]
                   if ETUDIANTS.get(m, {}).get("annee") == 4]
        if quatres:
            res.append((quatres, "Poly 6A absent (examen)"))
    return res


def _candidats_pour_types(en_exam, types_cibles, semaine, jour, moment):
    """
    Construit la liste des candidats (membres, libelle) pour un ensemble
    de types donné, selon la promo en examen.
    """
    candidats = []
    for t in types_cibles:
        if en_exam == {5}:
            # 5A en examen → 4/6 prennent les créneaux 5/5
            for gid, g in _binomes_46_du_type(t):
                candidats.append((g["membres"], f"Poly {g['nature']} (examen)"))
        elif en_exam == {4}:
            # 4A en examen → 6A seuls puis binômes 5/5
            for code6 in _6a_du_type(t):
                candidats.append(([code6], "Poly 6A seul (examen)"))
            for gid, g in _binomes_55_du_type(t):
                candidats.append((g["membres"], f"Poly {g['nature']} (examen)"))
        elif en_exam == {6}:
            # 6A en examen → les 4A gardent leur box ("6A absent"), + 5A
            for membres, libelle in _4a_absents_du_type(t):
                candidats.append((membres, libelle))
            for gid, g in _binomes_55_du_type(t):
                candidats.append((g["membres"], f"Poly {g['nature']} (examen)"))
        else:
            # 2 promos en examen → la 3e promo seule
            presente = {4, 5, 6} - en_exam
            if presente == {6}:
                for code6 in _6a_du_type(t):
                    candidats.append(([code6], "Poly 6A seul (examen)"))
            elif presente == {5}:
                for gid, g in _binomes_55_du_type(t):
                    candidats.append((g["membres"], f"Poly {g['nature']} (examen)"))
            elif presente == {4}:
                # 4A seuls, sans recomposer de 4/4
                for membres, libelle in _4a_absents_du_type(t):
                    candidats.append((membres, libelle))
    return candidats


def _vacations_semaine(code, semaine, vacations, ajouts):
    """Compte les vacations Poly d'un étudiant sur une semaine donnée
    (en tenant compte des ajouts déjà faits)."""
    n = 0
    for (jour, moment) in COLONNES_VAC:
        cle = (semaine, jour, moment)
        cell = vacations.get(code, {}).get(cle, "")
        if _est_poly(cell):
            n += 1
            continue
        cell_aj = ajouts.get(code, {}).get(cle, "")
        if cell_aj and _est_poly(cell_aj):
            n += 1
    return n


def traiter_jour(semaine, jour, vacations, vac_count, ajouts):
    """
    Traite un jour d'examen : remplit les créneaux libérés.
    Règle : chaque groupe vise 2 vacations/semaine AU TOTAL (normal + examen).
    Vagues : types du jour d'abord, puis autres types (équité).
    Priorité combinée : moins de vacations cette semaine, puis sur l'année.
    """
    en_exam = promos_en_examen(semaine, jour)
    if not en_exam:
        return

    types_du_jour = [t for t, (j1, j2) in JOURS_PAR_TYPE.items()
                     if jour in (j1, j2)]
    autres_types = [t for t in range(1, 6) if t not in types_du_jour]

    for moment in ("M", "AM"):
        occ = _compter_box(vacations, ajouts, semaine, jour, moment)
        deja_places = _membres_deja_places(vacations, ajouts, semaine, jour, moment)

        for vague in (types_du_jour, autres_types):
            if occ >= MAX_BOXES:
                break
            candidats = _candidats_pour_types(en_exam, vague, semaine, jour, moment)

            candidats_ok = []
            for membres, libelle in candidats:
                if any(m in deja_places for m in membres):
                    continue
                if not _membres_dispo(membres, semaine, jour, moment):
                    continue
                # Règle des 2 vacations/semaine : le groupe est écarté si
                # l'un de ses membres a déjà 2 vacations cette semaine.
                deja_2 = any(
                    _vacations_semaine(m, semaine, vacations, ajouts) >= 2
                    for m in membres
                )
                if deja_2:
                    continue
                candidats_ok.append((membres, libelle))

            # Tri combiné : d'abord vacations de la semaine (croissant),
            # puis vacations sur l'année (croissant).
            def cle_tri(c):
                membres = c[0]
                vac_sem = max(_vacations_semaine(m, semaine, vacations, ajouts)
                              for m in membres)
                vac_an = sum(vac_count.get(m, 0) for m in membres)
                return (vac_sem, vac_an)
            candidats_ok.sort(key=cle_tri)

            for membres, libelle in candidats_ok:
                if occ >= MAX_BOXES:
                    break
                # re-vérifier la limite (elle a pu changer pendant la boucle)
                if any(_vacations_semaine(m, semaine, vacations, ajouts) >= 2
                       for m in membres):
                    continue
                for m in membres:
                    autres = [x for x in membres if x != m]
                    base = libelle.split(' (examen)')[0]
                    if autres:
                        texte = f"{base} avec {'+'.join(autres)} (examen)"
                    else:
                        texte = libelle
                    ajouts.setdefault(m, {})[(semaine, jour, moment)] = texte
                    vac_count[m] += 1
                    deja_places.add(m)
                occ += 1


def _membres_deja_places(vacations, ajouts, semaine, jour, moment):
    """Ensemble des codes déjà placés sur ce créneau (original + ajouts)."""
    places = set()
    for code, vac in vacations.items():
        if _est_poly(vac.get((semaine, jour, moment), "")):
            places.add(code)
    for code, aj in ajouts.items():
        if (semaine, jour, moment) in aj:
            places.add(code)
    return places


def _occupation_creneau(vacations, ajouts, semaine, jour, moment):
    """Compte les box déjà occupés sur ce créneau (original + ajouts)."""
    membres_places = set()
    for code, vac in vacations.items():
        cell = vac.get((semaine, jour, moment), "")
        if _est_poly(cell):
            membres_places.add(code)
    for code, aj in ajouts.items():
        if (semaine, jour, moment) in aj:
            membres_places.add(code)
    # approximation : nb de box ≈ regrouper par binôme.
    # Ici on compte simplement les groupes distincts via les partenaires.
    # Pour rester simple à l'étape 1 : on compte les box comme
    # ceil(membres / 2) n'est pas fiable ; on recompte par ensembles.
    return _compter_box(vacations, ajouts, semaine, jour, moment)


def _compter_box(vacations, ajouts, semaine, jour, moment):
    """Compte les box réels (ensembles d'étudiants ensemble)."""
    ensembles = []
    def ajoute(membres):
        s = set(membres)
        for e in ensembles:
            if e & s:
                e |= s
                return
        ensembles.append(s)

    for code, vac in vacations.items():
        cell = vac.get((semaine, jour, moment), "")
        if _est_poly(cell):
            partenaires = _extraire_partenaires(cell)
            ajoute([code] + partenaires)
    for code, aj in ajouts.items():
        cell = aj.get((semaine, jour, moment), "")
        if cell:
            partenaires = _extraire_partenaires(cell)
            ajoute([code] + partenaires)
    return len(ensembles)


def _extraire_partenaires(cellule):
    import re
    if " avec " not in cellule:
        return []
    apres = cellule.split(" avec ", 1)[1]
    apres = re.sub(r"\s*\(.*?\)\s*$", "", apres).strip()
    return [p.strip() for p in apres.split("+") if p.strip()] if apres else []


# ============================================================
#  Écriture des CSV
# ============================================================

def ecrire_plannings(plannings, ajouts, dossier_sortie, inplace=False):
    dossier = DOSSIER_ENTREE if inplace else dossier_sortie
    os.makedirs(dossier, exist_ok=True)

    for code, lignes in plannings.items():
        aj = ajouts.get(code, {})
        nouvelles_lignes = []
        entete_vue = False
        for ligne in lignes:
            if ligne and ligne[0] == "Semaine":
                entete_vue = True
                nouvelles_lignes.append(ligne)
                continue
            if entete_vue and len(ligne) >= 12:
                try:
                    sem = int(ligne[0])
                except ValueError:
                    nouvelles_lignes.append(ligne)
                    continue
                ligne = list(ligne)
                for idx, (j, m) in enumerate(COLONNES_VAC):
                    if (sem, j, m) in aj:
                        ligne[2 + idx] = aj[(sem, j, m)]
                nouvelles_lignes.append(ligne)
            else:
                nouvelles_lignes.append(ligne)

        chemin = os.path.join(dossier, f"{code}.csv")
        with open(chemin, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(nouvelles_lignes)

    return dossier


# ============================================================
#  Point d'entrée
# ============================================================

def _passe_securite_capacite(salle, sems_exam):
    """
    Garantit qu'aucun créneau des semaines réactivées ne dépasse MAX_BOXES.
    Retire les groupes en surplus (ceux avec le PLUS de vacations d'abord),
    en s'assurant qu'ils gardent au moins 1 vacation dans la semaine.
    Modifie 'salle' en place.
    """
    NAT_46 = NATURES_46
    for sem in sems_exam:
        if sem not in salle:
            continue

        # Compter les vacations de chaque groupe dans cette semaine
        vac_sem = defaultdict(int)
        for (jour, moment), groupes in salle[sem].items():
            for g in groupes:
                vac_sem[g["id"]] += 1

        for (jour, moment), groupes in salle[sem].items():
            if len(groupes) <= MAX_BOXES:
                continue
            surplus = len(groupes) - MAX_BOXES

            # Candidats au retrait : ceux qui ont > 1 vacation cette semaine
            # (pour garder le minimum), triés par nb de vacations décroissant.
            retirables = [g for g in groupes if vac_sem[g["id"]] > 1]
            retirables.sort(key=lambda g: -vac_sem[g["id"]])

            a_retirer = retirables[:surplus]
            ids_retires = {id(g) for g in a_retirer}
            salle[sem][(jour, moment)] = [
                g for g in groupes if id(g) not in ids_retires
            ]
            for g in a_retirer:
                vac_sem[g["id"]] -= 1


def planning_jours_sans_examen():
    """
    3e VOIE : récupère le planning NORMAL des jours SANS examen, dans les
    semaines d'examen — en réutilisant le vrai poly.py, sans le modifier.

    Technique : on retire temporairement les semaines d'examen de la
    variable poly.SEMAINES_NEUTRALISEES, on appelle le vrai calcul
    (calculer_planning_salle + gerer_capacite), puis on restaure l'état.
    On ne garde que les créneaux des jours SANS examen.

    Renvoie : ajouts_normaux[code][(sem,jour,moment)] = texte de cellule.
    """
    import poly
    from roulement import gerer_capacite

    sems_exam = semaines_examen()

    # 1. Sauvegarder et retirer temporairement les semaines d'examen
    sauvegarde = dict(poly.SEMAINES_NEUTRALISEES)
    temp = {s: m for s, m in poly.SEMAINES_NEUTRALISEES.items()
            if s not in sems_exam}
    poly.SEMAINES_NEUTRALISEES = temp

    try:
        # 2. Calculer le planning normal (VRAI code) avec ces semaines actives
        salle = poly.calculer_planning_salle(avec_roulement=False)
        salle, _stats = gerer_capacite(salle)
    finally:
        # 3. Restaurer l'état initial quoi qu'il arrive
        poly.SEMAINES_NEUTRALISEES = sauvegarde

    # 3bis. PASSE DE SÉCURITÉ CAPACITÉ : sur les semaines d'examen réactivées,
    # certains créneaux du 1er jour peuvent dépasser 19 (le roulement classique
    # ne réduit que le 2e jour). On retire l'excédent en priorisant les groupes
    # qui ont le PLUS de vacations, tout en garantissant qu'ils gardent au moins
    # 1 vacation dans la semaine.
    _passe_securite_capacite(salle, sems_exam)

    # 4. Extraire uniquement les jours SANS examen des semaines d'examen
    ajouts = {}
    for sem in sems_exam:
        if sem not in salle:
            continue
        for (jour, moment), groupes in salle[sem].items():
            if promos_en_examen(sem, jour):
                continue  # jour À examen → géré par la logique examen
            for g in groupes:
                nature = g["nature"]
                membres = g.get("membres", [])
                debord = " (débord)" if g.get("debord") else ""
                for m in membres:
                    autres = [x for x in membres if x != m]
                    if autres:
                        texte = f"Poly {nature} avec {'+'.join(autres)}{debord}"
                    else:
                        texte = f"Poly {nature}{debord}"
                    ajouts.setdefault(m, {})[(sem, jour, moment)] = texte

    return ajouts


def traiter_examens(inplace=False):
    plannings, vacations = charger_plannings()

    sems_exam = sorted(semaines_examen(), key=lambda s: (s if s >= 36 else s + 100))
    print(f"Semaines d'examen à traiter : {sems_exam}")

    ajouts = {}

    # ── ÉTAPE 2 : jours SANS examen des semaines d'examen (planning normal) ──
    ajouts_normaux = planning_jours_sans_examen()
    for code, aj in ajouts_normaux.items():
        ajouts.setdefault(code, {}).update(aj)
    total_normaux = sum(len(a) for a in ajouts_normaux.values())
    print(f"Vacations normales ajoutées (jours sans examen) : {total_normaux}")

    # Injecter ces ajouts dans 'vacations' pour que le compteur d'équité
    # en tienne compte AVANT de distribuer les créneaux d'examen.
    for code, aj in ajouts_normaux.items():
        vacations.setdefault(code, {}).update(aj)

    # Recalculer le compteur d'équité APRÈS les jours normaux
    vac_count = compter_vacations(vacations)

    # ── ÉTAPE 1 : jours À examen (logique de remplacement) ──
    for sem in sems_exam:
        for jour in JOURS:
            if promos_en_examen(sem, jour):
                traiter_jour(sem, jour, vacations, vac_count, ajouts)

    total_examen = sum(len(a) for a in ajouts.values()) - total_normaux
    print(f"Vacations ajoutées sur les jours d'examen : {total_examen}")

    dossier = ecrire_plannings(plannings, ajouts, DOSSIER_SORTIE, inplace)
    print(f"CSV écrits dans : {dossier}/")


if __name__ == "__main__":
    inplace = "--inplace" in sys.argv
    traiter_examens(inplace=inplace)