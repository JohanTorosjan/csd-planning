# ============================================================
#  main_matieres.py — Enchaîne les matières annexes EN CASCADE
#
#  Objectif : vérifier que toutes les matières « tiennent » ensemble,
#  chacune lisant le planning produit par la précédente (et non plus
#  toujours le même dossier de départ). C'est le test de non-étranglement.
#
#  Chaîne :
#     planning_csv_occluso                     (point de départ)
#         → odf           → planning_csv_odf
#         → stérilisation → planning_csv_sterilisation
#         → pano          → planning_csv_pano
#         → radio         → planning_csv_radio   (planning final des matières)
#
#  Chaque étape lit le dossier de l'étape précédente, place sa matière,
#  et écrit son propre dossier. Comme chaque matière ne remplit que des
#  cellules « — », les matières ne s'écrasent jamais : elles se voient
#  mutuellement et se répartissent les créneaux restants.
#
#  Usage : python3 main_matieres.py
#          python3 main_matieres.py --depart planning_csv_odf   (autre départ)
# ============================================================

import os
import sys
import csv
import shutil

import odf
import sterilisation as ste
import pano
import radio
import como
import paro

import pedo_groupes as pg
from etudiants import ETUDIANTS

IDX = pg.IDX
COLONNES = pg.COLONNES


def depart():
    if "--depart" in sys.argv:
        i = sys.argv.index("--depart")
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return "planning_csv_occluso"


def compter_occupation(dossier):
    """Compte les cellules occupées par matière dans un dossier."""
    from collections import Counter
    c = Counter()
    for nom in os.listdir(dossier):
        if not nom.endswith(".csv"):
            continue
        code = nom[:-4]
        if ETUDIANTS.get(code, {}).get("erasmus"):
            continue
        with open(os.path.join(dossier, nom), encoding="utf-8") as f:
            for l in csv.reader(f):
                if len(l) < 12 or not l[0].isdigit():
                    continue
                for col in COLONNES:
                    v = l[IDX[col]]
                    if v == "—":
                        c["libre"] += 1
                    elif v in ("fermé", "Fermé"):
                        c["fermé"] += 1
                    elif "Occluso" in v:
                        c["occluso"] += 1
                    elif "ODF" in v:
                        c["odf"] += 1
                    elif "Stérilisation" in v:
                        c["stérilisation"] += 1
                    elif "Pano" in v:
                        c["pano"] += 1
                    elif "Radio" in v:
                        c["radio"] += 1
                    elif "COMO" in v:
                        c["como"] += 1
                    elif "Paro" in v:
                        c["paro"] += 1
                    else:
                        c["autre"] += 1
    return c


def etape(nom_matiere, module, dossier_in, export_dossier, avec_pipeline_flag):
    """Exécute une matière : charge dossier_in, place, écrit sa sortie."""
    print(f"\n{'='*66}")
    print(f"  ÉTAPE : {nom_matiere}")
    print(f"  lit : {dossier_in}  →  écrit : {export_dossier}")
    print('='*66)

    data = module.charger(dossier_in)

    # placer + alertes (signatures homogènes : (affectations, alertes) sauf
    # occluso qui n'a pas d'alertes — mais occluso n'est pas dans la chaîne)
    res = module.placer(data)
    if isinstance(res, tuple):
        affectations, alertes = res
    else:
        affectations, alertes = res, []

    # export
    module.exporter(data, affectations, True)

    if alertes:
        vrais = [a for a in alertes if "férié" not in a.lower()]
        print(f"  ⚠️  {len(alertes)} alerte(s) "
              f"({len(vrais)} hors fériés présumés)")

    return affectations, alertes


def main():
    d0 = depart()
    if not os.path.isdir(d0):
        print(f"⚠️  Dossier de départ '{d0}' introuvable.")
        return

    print("#" * 66)
    print("  PIPELINE DES MATIÈRES ANNEXES — EN CASCADE")
    print(f"  départ : {d0}")
    print("#" * 66)

    # occupation initiale
    print("\n  Occupation au départ :")
    for k, v in compter_occupation(d0).most_common():
        print(f"     {k:16s}: {v}")

    # ODF lit d0 → planning_csv_odf
    # (odf.charger() n'accepte pas de paramètre → on adapte via DOSSIER_ENTREE)
    odf.DOSSIER_ENTREE = d0
    data = odf.charger()
    aff = odf.placer(data)
    affectations_odf, alertes_odf = aff
    odf.exporter(data, affectations_odf, True)
    print(f"\n[ODF] {sum(len(v) for v in affectations_odf.values())} placements "
          f"→ {odf.DOSSIER_SORTIE}")

    # STÉRILISATION lit planning_csv_odf → planning_csv_sterilisation
    data = ste.charger(odf.DOSSIER_SORTIE)
    aff_ste, al_ste = ste.placer(data)
    ste.exporter(data, aff_ste, True)
    print(f"[STÉ] {sum(len(v) for v in aff_ste.values())} placements "
          f"→ {ste.DOSSIER_SORTIE}")

    # PANO lit planning_csv_sterilisation → planning_csv_pano
    data = pano.charger(ste.DOSSIER_SORTIE)
    aff_pano, al_pano = pano.placer(data)
    pano.exporter(data, aff_pano, True)
    print(f"[PANO] {sum(len(v) for v in aff_pano.values())} placements "
          f"→ {pano.DOSSIER_SORTIE}")

    # RADIO lit planning_csv_pano → planning_csv_radio
    data = radio.charger(pano.DOSSIER_SORTIE)
    aff_radio, al_radio = radio.placer(data)
    radio.exporter(data, aff_radio, True)
    print(f"[RADIO] {sum(len(v) for v in aff_radio.values())} placements "
          f"→ {radio.DOSSIER_SORTIE}")

    # COMO lit planning_csv_radio → planning_csv_como
    data = como.charger(radio.DOSSIER_SORTIE)
    aff_como, al_como = como.placer(data)
    como.exporter(data, aff_como, True)
    print(f"[COMO] {sum(len(v) for v in aff_como.values())} placements "
          f"→ {como.DOSSIER_SORTIE}")

    # PARO lit planning_csv_como → planning_csv_paro (planning FINAL)
    data = paro.charger(como.DOSSIER_SORTIE)
    aff_paro, al_paro = paro.placer(data)
    paro.exporter(data, aff_paro, True)
    print(f"[PARO] {sum(len(v) for v in aff_paro.values())} placements "
          f"→ {paro.DOSSIER_SORTIE}")

    # occupation finale (planning_csv_paro contient tout l'empilement)
    print("\n" + "#" * 66)
    print("  OCCUPATION FINALE (planning_csv_paro)")
    print("#" * 66)
    for k, v in compter_occupation(paro.DOSSIER_SORTIE).most_common():
        print(f"     {k:16s}: {v}")

    # bilan alertes
    total_alertes = (len(alertes_odf) + len(al_ste) + len(al_pano)
                     + len(al_radio) + len(al_como) + len(al_paro))
    vrais = 0
    for liste in (alertes_odf, al_ste, al_pano, al_radio, al_como, al_paro):
        vrais += sum(1 for a in liste
                     if "vide" not in a and "aucun" not in a.lower())
    print(f"\n  Total alertes (toutes matières) : {total_alertes}")
    print(f"  dont 'vraies' alertes (hors salles vides/fériés) : {vrais}")
    print("  (les alertes 'aucun étudiant' sur fériés sont normales)")


if __name__ == "__main__":
    main()