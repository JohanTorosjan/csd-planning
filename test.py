import os, csv
import pedo_groupes as pg
from etudiants import ETUDIANTS

DOSSIER = "planning_csv_paro"
IDX = pg.IDX; COLONNES = pg.COLONNES
MOTIFS = ["Occluso","ODF","Stérilisation","Pano","Radio","COMO","Paro"]

erasmus = [c for c,i in ETUDIANTS.items() if i.get("erasmus")]
print(f"Étudiants Erasmus : {len(erasmus)}")
for c in erasmus:
    print(f"   {c} : {ETUDIANTS[c]}")

print(f"\nMatières annexes :")
for c in erasmus:
    path = os.path.join(DOSSIER, f"{c}.csv")
    if not os.path.exists(path):
        print(f"   {c} : PAS de fichier"); continue
    with open(path,encoding="utf-8") as f:
        lignes={int(l[0]):l for l in csv.reader(f) if len(l)>=12 and l[0].isdigit()}
    compte={m:0 for m in MOTIFS}
    for sem,l in lignes.items():
        for col in COLONNES:
            v=l[IDX[col]]
            for m in MOTIFS:
                if m in v: compte[m]+=1
    total=sum(compte.values())
    detail=" ".join(f"{m}:{compte[m]}" for m in MOTIFS if compte[m]>0) or "AUCUNE"
    print(f"   {c} ({ETUDIANTS[c].get('annee')}A) : {total} vacations | {detail}")

print(f"\nDans Poly/Pédo/urgences ?")
for c in erasmus:
    path = os.path.join(DOSSIER, f"{c}.csv")
    if not os.path.exists(path): continue
    with open(path,encoding="utf-8") as f:
        lignes={int(l[0]):l for l in csv.reader(f) if len(l)>=12 and l[0].isdigit()}
    autres={"Poly":0,"Pédo":0,"Urgences":0}
    for sem,l in lignes.items():
        for col in COLONNES:
            v=l[IDX[col]]
            for m in autres:
                if m in v: autres[m]+=1
    print(f"   {c} : Poly:{autres['Poly']} Pédo:{autres['Pédo']} Urgences:{autres['Urgences']}")