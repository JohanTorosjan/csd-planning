# ============================================================
#  erasmus.py — Étudiants Erasmus (greffés sur des binômes)
#
#  Les Erasmus sont des étudiants EN PLUS, définis dans
#  docs/erasmus.csv. Chacun se greffe sur un binôme existant du
#  bon type — le plus DISPONIBLE pendant sa plage de présence —
#  qui devient un trinôme. Hors de sa plage, l'Erasmus est
#  indisponible (comme un stage) : il n'apparaît dans le planning
#  que sur sa période, et quand il est absent le binôme d'accueil
#  retombe simplement à 2 membres (aucun box fantôme).
#
#  Format CSV (séparateur ';', UTF-8, en-tête) :
#     nom ; annee ; type ; debut ; fin
#  Le code est GÉNÉRÉ : E{annee}{type}{numéro}, ex E5301.
#
#  Fonction principale : greffer_erasmus(etudiants, groupes, noms)
#  appelée par etudiants.py APRÈS la construction des groupes.
#  Renvoie (ERASMUS_PRESENCE, INDISPO_ERASMUS).
# ============================================================

import os
import csv

from absences import INDISPO_INDIVIDUEL  # pour mesurer la disponibilité

_ICI = os.path.dirname(os.path.abspath(__file__))
_DOCS = os.path.join(_ICI, "..", "docs")
FICHIER_ERASMUS = os.path.join(_DOCS, "erasmus.csv")


def _ordre(s):
    return s if s >= 36 else s + 100


ANNEE_COMPLETE = sorted(list(range(36, 53)) + list(range(1, 36)), key=_ordre)


def _lire_texte(chemin):
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with open(chemin, encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"Encodage illisible : {chemin}")


def _semaines_plage(debut, fin):
    o_d, o_f = _ordre(debut), _ordre(fin)
    return [s for s in ANNEE_COMPLETE if o_d <= _ordre(s) <= o_f]


def _semaines_indispo(code, plage_semaines):
    """Nb de semaines de la plage où l'étudiant est indisponible."""
    bloques = set()
    for semaines, _motif in INDISPO_INDIVIDUEL.get(code, []):
        bloques.update(semaines)
    return sum(1 for s in plage_semaines if s in bloques)


def _disponibilite_binome(groupe, plage_semaines):
    """Score : total de semaines-membre LIBRES sur la plage.
    Plus c'est haut, plus le binôme est disponible pour accueillir."""
    total = 0
    for code in groupe["membres"]:
        indispo = _semaines_indispo(code, plage_semaines)
        total += (len(plage_semaines) - indispo)
    return total


def _lire_erasmus(chemin):
    if not os.path.exists(chemin):
        return []
    lignes = list(csv.reader(_lire_texte(chemin).splitlines(), delimiter=";"))
    res = []
    for ligne in lignes[1:]:
        if len(ligne) < 5 or not ligne[1].strip().isdigit():
            continue
        res.append({
            "nom": ligne[0].strip(),
            "annee": int(ligne[1].strip()),
            "type": int(ligne[2].strip()),
            "debut": int(ligne[3].strip()),
            "fin": int(ligne[4].strip()),
        })
    return res


def greffer_erasmus(etudiants, groupes, noms, chemin=FICHIER_ERASMUS):
    """Greffe les Erasmus sur les binômes les plus disponibles.
    Modifie etudiants, groupes, noms EN PLACE.
    Renvoie (presence, indispo_hors_plage)."""
    erasmus = _lire_erasmus(chemin)
    presence = {}
    indispo = {}

    def nature_cible(annee):
        return "5/5" if annee == 5 else "4/6"

    accueils_utilises = set()
    numero = {}

    for e in erasmus:
        annee, type_e = e["annee"], e["type"]
        plage = _semaines_plage(e["debut"], e["fin"])
        cible = nature_cible(annee)

        candidats = [
            (gid, g) for gid, g in groupes.items()
            if g["type"] == type_e
            and g["nature"] == cible
            and len(g["membres"]) == 2
            and gid not in accueils_utilises
        ]
        if not candidats:
            print(f"  ⚠️  ERASMUS {e['nom']} ({annee}A type {type_e}) : "
                  f"aucun binôme {cible} libre — ignoré")
            continue

        gid, g = max(candidats,
                     key=lambda gc: _disponibilite_binome(gc[1], plage))
        accueils_utilises.add(gid)

        cle = (annee, type_e)
        numero[cle] = numero.get(cle, 0) + 1
        code = f"E{annee}{type_e}{numero[cle]:02d}"

        etudiants[code] = {
            "code": code,
            "annee": annee,
            "type": type_e,
            "numero": 0,
            "erasmus": True,
        }
        noms[code] = e["nom"]

        g["membres"].append(code)
        g["nature"] = "trinome" if cible == "4/6" else "trinome_5"

        presence[code] = {"debut": e["debut"], "fin": e["fin"]}
        hors = [s for s in ANNEE_COMPLETE if s not in set(plage)]
        if hors:
            indispo[code] = [(hors, "Erasmus")]

    return presence, indispo


if __name__ == "__main__":
    for e in _lire_erasmus(FICHIER_ERASMUS):
        plage = _semaines_plage(e["debut"], e["fin"])
        print(f"  {e['nom']} : {e['annee']}A type {e['type']}, "
              f"présent {e['debut']}→{e['fin']} ({len(plage)} semaines)")