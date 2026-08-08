# ============================================================
#  etudiants.py — Chargement des étudiants et groupes depuis CSV
#
#  Les binômes/trinômes sont désormais FOURNIS par l'équipe
#  pédagogique dans deux fichiers (dossier docs/) :
#     composition_4_6.csv   binômes 4/6 et trinômes 4/4/6
#     composition_5_5.csv   binômes 5/5 et trinômes 5/5/5
#
#  Format commun (séparateur ';', UTF-8, en-tête) :
#     type ; nature ; code_1 ; nom_1 ; code_2 ; nom_2 ; code_3 ; nom_3
#
#  Le type vient de la colonne 'type' (= 2e chiffre du code).
#  Ce module reproduit exactement les structures attendues par le
#  reste du pipeline :
#     ETUDIANTS : {code: {code, annee, type, numero, [erasmus]}}
#     GROUPES   : {id: {id, type, nature, membres, secours}}
#     NOMS      : {code: nom}   (nouveau, pour l'affichage)
#
#  Il n'y a PLUS de secours 4/4 calculé : le champ 'secours' est
#  conservé (à None) pour compatibilité, mais quand un 6A est absent
#  on écrira simplement "Poly (6A absent)" et les 4A retrouvent leur
#  binôme secours eux-mêmes.
# ============================================================

import os
import csv

NB_TYPES = 5

# ── Chemins : relatifs à CE fichier, donc indépendants du cwd ──
_ICI = os.path.dirname(os.path.abspath(__file__))
_DOCS = os.path.join(_ICI, "..", "docs")

FICHIER_46 = os.path.join(_DOCS, "composition_4_6.csv")
FICHIER_55 = os.path.join(_DOCS, "composition_5_5.csv")


# ── Lecture d'un fichier de composition ─────────────────────

def _lire_composition(chemin):
    """
    Renvoie une liste de groupes bruts :
      {type, nature, membres:[(code, nom), ...]}
    Ignore l'en-tête et les colonnes de 3e membre vides.
    """
    if not os.path.exists(chemin):
        raise SystemExit(f"Fichier de composition introuvable : {chemin}")

    # Tolérance d'encodage : l'équipe édite ces fichiers dans divers
    # tableurs. On tente UTF-8 (avec/sans BOM) puis les encodages
    # Windows/Latin courants, pour ne jamais planter au chargement.
    texte = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            with open(chemin, encoding=enc) as f:
                texte = f.read()
            break
        except UnicodeDecodeError:
            continue
    if texte is None:
        raise SystemExit(f"Encodage illisible : {chemin}")

    groupes = []
    lecteur = csv.reader(texte.splitlines(), delimiter=";")
    next(lecteur, None)   # ignorer l'en-tête
    for ligne in lecteur:
        if not ligne or not ligne[0].strip():
            continue
        if not ligne[0].strip().isdigit():
            continue
        type_g = int(ligne[0].strip())
        nature = ligne[1].strip()
        membres = []
        # colonnes code/nom par paires : 2&3, 4&5, 6&7
        for i in (2, 4, 6):
            if i < len(ligne) and ligne[i].strip():
                code = ligne[i].strip()
                nom = ligne[i + 1].strip() if i + 1 < len(ligne) else ""
                membres.append((code, nom))
        groupes.append({"type": type_g, "nature": nature,
                        "membres": membres})
    return groupes


# ── Construction des structures ─────────────────────────────

def _construire():
    etudiants = {}
    groupes = {}
    noms = {}

    def enregistrer(code, nom, annee, type_g, numero):
        etudiants[code] = {
            "code": code,
            "annee": annee,
            "type": type_g,
            "numero": numero,
        }
        if nom:
            noms[code] = nom

    compteur_type = {t: 0 for t in range(1, NB_TYPES + 1)}

    # ---- 4/6 (binômes 4/6 et trinômes 4/4/6) ----
    for g in _lire_composition(FICHIER_46):
        t = g["type"]
        compteur_type[t] += 1
        id_g = f"G{t}_{compteur_type[t]:02d}"
        membres_codes = []
        for (code, nom) in g["membres"]:
            annee = int(code[0])
            enregistrer(code, nom, annee, t, len(etudiants) + 1)
            membres_codes.append(code)
        # ordre attendu par composition.py :
        #   4/6      -> [4A, 6A]
        #   trinome  -> [4A, 6A, 4A]
        groupes[id_g] = {
            "id": id_g,
            "type": t,
            "nature": g["nature"],   # "4/6" ou "trinome"
            "membres": membres_codes,
            "secours": None,
        }

    # ---- 5/5 (binômes 5/5 et trinômes 5/5/5) ----
    compteur_55 = {t: 0 for t in range(1, NB_TYPES + 1)}
    for g in _lire_composition(FICHIER_55):
        t = g["type"]
        compteur_55[t] += 1
        id_g = f"G{t}_55_{compteur_55[t]:02d}"
        membres_codes = []
        for (code, nom) in g["membres"]:
            annee = int(code[0])
            enregistrer(code, nom, annee, t, len(etudiants) + 1)
            membres_codes.append(code)
        groupes[id_g] = {
            "id": id_g,
            "type": t,
            "nature": g["nature"],   # "5/5" ou "trinome_5"
            "membres": membres_codes,
            "secours": None,
        }

    return etudiants, groupes, noms


# ── Validation : refuser les incohérences de saisie ─────────

_TAILLE_ATTENDUE = {"4/6": 2, "trinome": 3, "5/5": 2, "trinome_5": 3}


def _valider(etudiants, groupes):
    """Arrête le chargement si les CSV contiennent une incohérence.
    Ces fichiers sont remplis à la main : mieux vaut un échec clair
    ici qu'un planning faux trois étapes plus loin."""
    erreurs = []

    # 1. nature connue et cohérente avec le nombre de membres
    for id_g, g in groupes.items():
        nat = g["nature"]
        if nat not in _TAILLE_ATTENDUE:
            erreurs.append(f"{id_g} : nature inconnue '{nat}'")
            continue
        attendu = _TAILLE_ATTENDUE[nat]
        if len(g["membres"]) != attendu:
            erreurs.append(
                f"{id_g} : nature '{nat}' attend {attendu} membres, "
                f"en a {len(g['membres'])} ({'+'.join(g['membres'])})")

    # 2. aucun étudiant dans deux groupes
    appartenance = {}
    for id_g, g in groupes.items():
        for code in g["membres"]:
            if code in appartenance:
                erreurs.append(
                    f"{code} apparaît dans {appartenance[code]} ET {id_g}")
            else:
                appartenance[code] = id_g

    # 3. cohérence code / année / type (2e chiffre = type du groupe)
    for id_g, g in groupes.items():
        for code in g["membres"]:
            if len(code) < 4 or not code.lstrip("E")[:1].isdigit():
                erreurs.append(f"{id_g} : code mal formé '{code}'")
                continue
            noyau = code[1:] if code.startswith("E") else code
            if len(noyau) >= 2 and noyau[1].isdigit():
                type_code = int(noyau[1])
                if type_code != g["type"]:
                    erreurs.append(
                        f"{id_g} (type {g['type']}) : le code {code} "
                        f"indique le type {type_code}")

    if erreurs:
        print("⚠️  INCOHÉRENCES DANS LES FICHIERS DE COMPOSITION :")
        for e in erreurs[:20]:
            print(f"     - {e}")
        if len(erreurs) > 20:
            print(f"     ... et {len(erreurs) - 20} autres")
        raise SystemExit("Corrigez les CSV de composition avant de continuer.")


ETUDIANTS, GROUPES, NOMS = _construire()

_valider(ETUDIANTS, GROUPES)


# ── Erasmus : greffe sur les binômes les plus disponibles ───
# Les Erasmus sont des étudiants EN PLUS (docs/erasmus.csv), greffés
# sur un binôme du bon type qui devient trinôme. Hors de leur plage,
# ils sont indisponibles (INDISPO_ERASMUS, fusionné dans donnees.py).

try:
    from erasmus import greffer_erasmus
    ERASMUS_PRESENCE, INDISPO_ERASMUS = greffer_erasmus(
        ETUDIANTS, GROUPES, NOMS)
except ImportError:
    ERASMUS_PRESENCE, INDISPO_ERASMUS = {}, {}


# ── Diagnostic ──────────────────────────────────────────────

if __name__ == "__main__":
    from collections import Counter

    print(f"Étudiants chargés : {len(ETUDIANTS)}")
    for annee in (4, 5, 6):
        codes = [c for c, i in ETUDIANTS.items() if i["annee"] == annee]
        par_type = Counter(ETUDIANTS[c]["type"] for c in codes)
        detail = "  ".join(f"t{t}:{par_type[t]}" for t in range(1, 6))
        print(f"  {annee}A : {len(codes):3d}   {detail}")

    print(f"\nGroupes chargés : {len(GROUPES)}")
    natures = Counter(g["nature"] for g in GROUPES.values())
    for nat, nb in sorted(natures.items()):
        print(f"  {nat:12s} : {nb}")

    print(f"\nNoms disponibles : {len(NOMS)}")

    print(f"\n── Détail du type 1 ──")
    for id_g, g in sorted(GROUPES.items()):
        if g["type"] == 1:
            membres = " + ".join(
                f"{c}({NOMS.get(c, '?').split()[0] if NOMS.get(c) else '?'})"
                for c in g["membres"])
            print(f"  [{id_g:12s}] {g['nature']:10s}  {membres}")