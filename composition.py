# ============================================================
#  composition.py — Composition réelle des groupes par vacation
#  Calcule, pour un type + une demi-journée précise + une semaine,
#  la liste des groupes actifs avec leur composition réelle.
#  Évaluation INDÉPENDANTE par demi-journée.
#
#  Règle des 6A absents (nouvelle) :
#    Les binômes/trinômes sont fournis par l'équipe. Il n'y a plus
#    de secours 4/4 calculé. Quand le 6A d'un groupe 4/6 ou d'un
#    trinôme est absent, les 4A présents GARDENT leur box (ils
#    comptent dans la capacité) et la vacation est libellée
#    "Poly (6A absent)". Les 4A retrouvent leur binôme eux-mêmes.
# ============================================================

from etudiants import GROUPES, ETUDIANTS
from disponibilites import est_disponible
from scenarios import get_repartition, JOURS_PAR_TYPE


def _dispo(code, semaine, jour, moment):
    """Raccourci : un membre est-il dispo sur cette vacation ?"""
    return est_disponible(code, semaine, jour, moment)


def composition_creneau(type_binome, semaine, jour, moment):
    """
    Renvoie la liste des groupes actifs sur UNE demi-journée précise
    (jour, moment) d'un type donné, en semaine donnée.
    """
    repartition = get_repartition(type_binome, semaine)
    nature_creneau = repartition.get((jour, moment))
    if nature_creneau is None:
        return []  # demi-journée hors des jours de ce type

    groupes_type = {
        id_g: g for id_g, g in GROUPES.items()
        if g["type"] == type_binome
    }

    if nature_creneau == "55":
        return _composition_55(groupes_type, semaine, jour, moment)
    elif nature_creneau == "46":
        return _composition_46(groupes_type, semaine, jour, moment)
    return []


# ── Créneaux 5/5 ────────────────────────────────────────────

def _composition_55(groupes_type, semaine, jour, moment):
    actifs = []
    for id_g, g in groupes_type.items():
        if g["nature"] not in ("5/5", "trinome_5"):
            continue
        presents = [m for m in g["membres"]
                    if _dispo(m, semaine, jour, moment)]
        if len(presents) == 0:
            continue
        elif len(presents) == 1:
            actifs.append(_entree(id_g, "5A seul", presents, jour, moment))
        else:
            nature = "5/5" if len(presents) == 2 else "trinome_5"
            actifs.append(_entree(id_g, nature, presents, jour, moment))
    return actifs


# ── Créneaux 4/6 (binômes 4/6 et trinômes 4/4/6) ───────────

def _composition_46(groupes_type, semaine, jour, moment):
    """
    Un seul passage, pas de secours :
      - 6A présent  -> le groupe fonctionne (4/6, trinome, ou 6A seul)
      - 6A absent   -> les 4A présents gardent le box, libellé
                       "Poly (6A absent)" (ils comptent en capacité)
    """
    actifs = []

    groupes_46 = {
        id_g: g for id_g, g in groupes_type.items()
        if g["nature"] in ("4/6", "trinome")
    }

    def present(code):
        return _dispo(code, semaine, jour, moment)

    for id_g, g in groupes_46.items():
        if g["nature"] == "4/6":
            e4, e6 = g["membres"][0], g["membres"][1]
            p4, p6 = present(e4), present(e6)

            if p4 and p6:
                actifs.append(_entree(id_g, "4/6", [e4, e6], jour, moment))
            elif p6 and not p4:
                actifs.append(_entree(id_g, "6A seul", [e6], jour, moment))
            elif p4 and not p6:
                # 6A absent : le 4A garde son box
                actifs.append(_entree(id_g, "6A absent", [e4], jour, moment))
            # ni l'un ni l'autre : rien

        elif g["nature"] == "trinome":
            e4a, e6, e4b = g["membres"][0], g["membres"][1], g["membres"][2]
            p6 = present(e6)
            presents_4 = [e for e in (e4a, e4b) if present(e)]

            if p6 and len(presents_4) == 2:
                membres = [presents_4[0], e6, presents_4[1]]
                actifs.append(_entree(id_g, "trinome", membres, jour, moment))
            elif p6 and len(presents_4) == 1:
                membres = [presents_4[0], e6]
                actifs.append(_entree(id_g, "4/6", membres, jour, moment))
            elif p6 and len(presents_4) == 0:
                actifs.append(_entree(id_g, "6A seul", [e6], jour, moment))
            elif not p6 and presents_4:
                # 6A absent : les 4A présents gardent le box
                actifs.append(
                    _entree(id_g, "6A absent", presents_4, jour, moment))
            # 6A absent et aucun 4A : rien

    return actifs


def _entree(id_g, nature, membres, jour, moment):
    return {
        "id":      id_g,
        "nature":  nature,
        "membres": list(membres),
        "jour":    jour,
        "moment":  moment,
    }


# ── Diagnostic ──────────────────────────────────────────────

if __name__ == "__main__":
    type_test = 1
    sem_test  = 40

    rep = get_repartition(type_test, sem_test)
    print(f"Type {type_test}, semaine {sem_test} — répartition :")
    for (j, m), nat in rep.items():
        print(f"  {j} {m} → {nat}")
    print()

    for (jour, moment), nature in rep.items():
        actifs = composition_creneau(type_test, sem_test, jour, moment)
        print(f"── {jour} {moment} ({nature}) : {len(actifs)} groupes actifs")
        for a in actifs[:5]:
            print(f"     [{a['id']:10s}] {a['nature']:10s}  "
                  f"{' + '.join(a['membres'])}")
        if len(actifs) > 5:
            print(f"     ... et {len(actifs) - 5} autres")
        print()