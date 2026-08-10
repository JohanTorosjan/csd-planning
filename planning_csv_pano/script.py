#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyse_planning.py
====================

Analyse statistique de tous les fichiers CSV de planning (un fichier par
étudiant, ex: 4101.csv, E5201.csv...) situés dans le dossier courant.

Usage :
    python3 analyse_planning.py

À lancer depuis la racine du dossier contenant les CSV (planning_csv_pano).

Ce script :
  - lit chaque fichier CSV du dossier (motif *.csv)
  - extrait les métadonnées de chaque étudiant (Code, Année, Type, Groupe,
    Vacations Poly, Détail)
  - extrait la grille hebdomadaire (Semaine, Période, 10 créneaux
    lundi M -> vendredi AM)
  - nettoie/normalise les intitulés de "matière" (regroupe les variantes
    du type "Urgences (6/4)" -> "Urgences", "Poly trinome avec 6101+4102
    (rattrap)" -> "Poly trinome avec 6101+4102", etc.)
  - calcule un maximum de statistiques :
      * répartition globale des matières (nb de créneaux, %)
      * répartition par année (4A, 5A, 6A...)
      * répartition par jour de la semaine
      * répartition par créneau Matin/Après-midi
      * répartition par étudiant (code)
      * taux de créneaux vides ("—"), fermés ("fermé"), occupés
      * top matières par étudiant
  - exporte tout dans un classeur Excel multi-feuilles (statistiques.xlsx)
    et affiche un résumé dans le terminal.

Dépendances : pandas, openpyxl (installés automatiquement si absents).
"""

import csv
import glob
import os
import re
import subprocess
import sys


# ----------------------------------------------------------------------
# 0. Dépendances
# ----------------------------------------------------------------------
def ensure_packages():
    needed = {"pandas": "pandas", "openpyxl": "openpyxl"}
    for module, pip_name in needed.items():
        try:
            __import__(module)
        except ImportError:
            print(f"Installation du paquet manquant : {pip_name} ...")
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", pip_name, "--quiet"]
            )


ensure_packages()

import pandas as pd  # noqa: E402


# ----------------------------------------------------------------------
# 1. Paramètres
# ----------------------------------------------------------------------
DOSSIER = "."                       # dossier contenant les CSV (racine)
SORTIE_XLSX = "statistiques.xlsx"   # fichier Excel de sortie
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi"]
MOMENTS = ["M", "AM"]  # Matin / Après-midi
CRENEAUX_VIDES = {"—", "-", "", None}  # valeurs considérées "libres"
STATUTS_SPECIAUX = {"fermé", "ferme"}  # semaines fermées (vacances)


def normaliser_matiere(valeur: str) -> str:
    """
    Nettoie l'intitulé d'une matière pour regrouper les variantes :
    - retire les suffixes entre parenthèses type (rattrap), (examen),
      (6/4), (A), (C), etc. -> on les garde à part comme "statut"
    - retire les espaces superflus
    """
    if valeur is None:
        return valeur
    v = valeur.strip()
    return v


def extraire_statut(valeur: str):
    """
    Sépare le nom "de base" de la matière et le tag entre parenthèses
    (ex: 'Urgences (6/4)' -> ('Urgences', '6/4')
         'cours/indispo promo (C)' -> ('cours/indispo promo', 'C')
         'Poly trinome avec 6101+4102 (rattrap)' -> ('Poly trinome avec 6101+4102', 'rattrap'))
    """
    m = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", valeur)
    if m:
        base, tag = m.group(1).strip(), m.group(2).strip()
        return base, tag
    return valeur, ""


def lire_fichier(chemin: str):
    """
    Lit un fichier CSV de planning et retourne :
      - meta : dict des métadonnées de l'étudiant
      - lignes : liste de dicts (une ligne = un créneau occupé)
    """
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))

    meta = {"Fichier": os.path.basename(chemin)}
    idx_entete = None
    for i, row in enumerate(rows):
        if not row:
            continue
        if row[0] == "Semaine":
            idx_entete = i
            break
        if len(row) >= 2:
            cle, valeur = row[0], row[1]
            meta[cle] = valeur
        elif len(row) == 1 and row[0] not in ("", "RÉSUMÉ ÉTUDIANT"):
            # ligne de type "RÉSUMÉ ÉTUDIANT" ou vide -> ignorée
            pass

    lignes = []
    if idx_entete is not None:
        entetes = rows[idx_entete]
        colonnes_creneaux = entetes[2:]  # lundi M, lundi AM, ...
        for row in rows[idx_entete + 1:]:
            if not row or len(row) < 2:
                continue
            semaine, periode = row[0], row[1]
            valeurs = row[2:]
            for col_nom, val in zip(colonnes_creneaux, valeurs):
                val = normaliser_matiere(val)
                jour, moment = col_nom.rsplit(" ", 1)  # "lundi", "M"/"AM"
                lignes.append(
                    {
                        "Fichier": meta["Fichier"],
                        "Code": meta.get("Code", ""),
                        "Semaine": semaine,
                        "PériodeBloc": periode,
                        "Jour": jour,
                        "Moment": moment,
                        "ValeurBrute": val,
                    }
                )
    return meta, lignes


# ----------------------------------------------------------------------
# 2. Lecture de tous les fichiers
# ----------------------------------------------------------------------
def main():
    fichiers = sorted(glob.glob(os.path.join(DOSSIER, "*.csv")))
    fichiers = [f for f in fichiers if os.path.basename(f) != SORTIE_XLSX]

    if not fichiers:
        print("Aucun fichier .csv trouvé dans le dossier courant.")
        sys.exit(1)

    print(f"{len(fichiers)} fichiers CSV trouvés. Lecture en cours...")

    metas = []
    toutes_lignes = []
    erreurs = []

    for chemin in fichiers:
        try:
            meta, lignes = lire_fichier(chemin)
            metas.append(meta)
            toutes_lignes.extend(lignes)
        except Exception as e:
            erreurs.append((chemin, str(e)))

    if erreurs:
        print(f"\n⚠ {len(erreurs)} fichier(s) n'ont pas pu être lus :")
        for chemin, err in erreurs:
            print(f"  - {chemin} : {err}")

    df_meta = pd.DataFrame(metas)
    df = pd.DataFrame(toutes_lignes)

    if df.empty:
        print("Aucune donnée de planning n'a pu être extraite.")
        sys.exit(1)

    # Nettoyage des types
    df["Semaine"] = pd.to_numeric(df["Semaine"], errors="coerce")
    df["PériodeBloc"] = pd.to_numeric(df["PériodeBloc"], errors="coerce")

    # Catégorisation du créneau
    def categoriser(v):
        if v in CRENEAUX_VIDES:
            return "libre"
        if v.lower() in STATUTS_SPECIAUX:
            return "fermé"
        return "occupé"

    df["Statut"] = df["ValeurBrute"].apply(categoriser)

    # Matière de base + tag, uniquement pour les créneaux occupés
    base_tag = df["ValeurBrute"].apply(
        lambda v: extraire_statut(v) if v not in CRENEAUX_VIDES else ("", "")
    )
    df["Matiere"] = base_tag.apply(lambda t: t[0])
    df["Tag"] = base_tag.apply(lambda t: t[1])

    # Jointure avec les métadonnées (Année, Type, Groupe) par fichier
    if "Code" in df_meta.columns:
        meta_cols = [c for c in ["Fichier", "Code", "Année", "Type", "Groupe",
                                  "Vacations Poly (total)", "Détail"] if c in df_meta.columns]
        df = df.merge(df_meta[meta_cols], on="Fichier", how="left", suffixes=("", "_meta"))

    # ------------------------------------------------------------------
    # 3. Statistiques
    # ------------------------------------------------------------------
    df_occupe = df[df["Statut"] == "occupé"].copy()

    # 3.1 Répartition globale des matières (nb de créneaux + %)
    stat_matieres = (
        df_occupe.groupby("Matiere")
        .size()
        .reset_index(name="Nb_créneaux")
        .sort_values("Nb_créneaux", ascending=False)
    )
    stat_matieres["Pourcentage_%"] = (
        100 * stat_matieres["Nb_créneaux"] / stat_matieres["Nb_créneaux"].sum()
    ).round(2)

    # 3.2 Répartition par statut global (occupé / libre / fermé)
    stat_statuts = (
        df.groupby("Statut").size().reset_index(name="Nb_créneaux")
        .sort_values("Nb_créneaux", ascending=False)
    )
    stat_statuts["Pourcentage_%"] = (
        100 * stat_statuts["Nb_créneaux"] / stat_statuts["Nb_créneaux"].sum()
    ).round(2)

    # 3.3 Répartition matière x année
    if "Année" in df_occupe.columns:
        stat_matiere_annee = (
            df_occupe.groupby(["Année", "Matiere"])
            .size()
            .reset_index(name="Nb_créneaux")
            .sort_values(["Année", "Nb_créneaux"], ascending=[True, False])
        )
    else:
        stat_matiere_annee = pd.DataFrame()

    # 3.4 Répartition par jour de la semaine
    stat_jour = (
        df_occupe.groupby("Jour").size().reindex(JOURS).reset_index(name="Nb_créneaux")
    )
    stat_jour["Pourcentage_%"] = (
        100 * stat_jour["Nb_créneaux"] / stat_jour["Nb_créneaux"].sum()
    ).round(2)

    # 3.5 Répartition par moment (matin / après-midi)
    stat_moment = (
        df_occupe.groupby("Moment").size().reset_index(name="Nb_créneaux")
    )
    stat_moment["Pourcentage_%"] = (
        100 * stat_moment["Nb_créneaux"] / stat_moment["Nb_créneaux"].sum()
    ).round(2)

    # 3.6 Matière x jour (heatmap-friendly)
    stat_matiere_jour = (
        df_occupe.pivot_table(
            index="Matiere", columns="Jour", values="Statut",
            aggfunc="count", fill_value=0
        )
        .reindex(columns=JOURS, fill_value=0)
    )
    stat_matiere_jour["Total"] = stat_matiere_jour.sum(axis=1)
    stat_matiere_jour = stat_matiere_jour.sort_values("Total", ascending=False)

    # 3.7 Statistiques par étudiant (code)
    stat_etudiant = (
        df.groupby(["Fichier", "Code"])
        .agg(
            Nb_creneaux_total=("Statut", "size"),
            Nb_occupes=("Statut", lambda s: (s == "occupé").sum()),
            Nb_libres=("Statut", lambda s: (s == "libre").sum()),
            Nb_fermes=("Statut", lambda s: (s == "fermé").sum()),
            Nb_matieres_distinctes=(
                "Matiere", lambda s: s[s != ""].nunique()
            ),
        )
        .reset_index()
        .sort_values("Nb_occupes", ascending=False)
    )

    # 3.8 Top matière par étudiant (matière la plus fréquente pour chacun)
    def top_matiere(sous_df):
        occ = sous_df[sous_df["Statut"] == "occupé"]
        if occ.empty:
            return pd.Series({"Matiere_top": "", "Nb_occurrences": 0})
        vc = occ["Matiere"].value_counts()
        return pd.Series({"Matiere_top": vc.index[0], "Nb_occurrences": vc.iloc[0]})

    stat_top_matiere_etudiant = (
        df.groupby(["Fichier", "Code"]).apply(top_matiere).reset_index()
    )

    # 3.9 Répartition par tag (rattrap / examen / débord / lettre A-F, etc.)
    stat_tags = (
        df_occupe[df_occupe["Tag"] != ""]
        .groupby("Tag")
        .size()
        .reset_index(name="Nb_créneaux")
        .sort_values("Nb_créneaux", ascending=False)
    )

    # 3.10 Nombre de matières distinctes globalement
    nb_matieres_distinctes = stat_matieres.shape[0]

    # ------------------------------------------------------------------
    # 4. Export Excel multi-feuilles
    # ------------------------------------------------------------------
    with pd.ExcelWriter(SORTIE_XLSX, engine="openpyxl") as writer:
        stat_matieres.to_excel(writer, sheet_name="Matieres_global", index=False)
        stat_statuts.to_excel(writer, sheet_name="Statuts", index=False)
        if not stat_matiere_annee.empty:
            stat_matiere_annee.to_excel(writer, sheet_name="Matieres_par_annee", index=False)
        stat_jour.to_excel(writer, sheet_name="Repartition_jours", index=False)
        stat_moment.to_excel(writer, sheet_name="Repartition_matin_am", index=False)
        stat_matiere_jour.to_excel(writer, sheet_name="Matiere_x_jour")
        stat_etudiant.to_excel(writer, sheet_name="Par_etudiant", index=False)
        stat_top_matiere_etudiant.to_excel(writer, sheet_name="Top_matiere_par_etudiant", index=False)
        stat_tags.to_excel(writer, sheet_name="Tags", index=False)
        df.to_excel(writer, sheet_name="Donnees_brutes", index=False)

    # ------------------------------------------------------------------
    # 5. Résumé dans le terminal
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("RÉSUMÉ DE L'ANALYSE")
    print("=" * 70)
    print(f"Fichiers analysés      : {len(fichiers)}")
    print(f"Créneaux totaux        : {len(df)}")
    print(f"Créneaux occupés       : {len(df_occupe)}")
    print(f"Matières distinctes    : {nb_matieres_distinctes}")

    print("\n--- Répartition des statuts ---")
    print(stat_statuts.to_string(index=False))

    print("\n--- Top 15 matières (toutes années confondues) ---")
    print(stat_matieres.head(15).to_string(index=False))

    print("\n--- Répartition par jour ---")
    print(stat_jour.to_string(index=False))

    print("\n--- Répartition matin / après-midi ---")
    print(stat_moment.to_string(index=False))

    if not stat_tags.empty:
        print("\n--- Répartition des tags (rattrap/examen/etc.) ---")
        print(stat_tags.head(15).to_string(index=False))

    print(f"\n✅ Détails complets exportés dans : {os.path.abspath(SORTIE_XLSX)}")
    print("   (feuilles : Matieres_global, Statuts, Matieres_par_annee, "
          "Repartition_jours, Repartition_matin_am, Matiere_x_jour, "
          "Par_etudiant, Top_matiere_par_etudiant, Tags, Donnees_brutes)")


if __name__ == "__main__":
    main()