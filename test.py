import os, csv
import pedo_groupes as pg
from etudiants import ETUDIANTS
from collections import defaultdict

DOSSIER = "planning_csv_occluso"
IDX = pg.IDX
CRENEAUX_OCC = [("lundi","M"),("mardi","M"),("jeudi","M"),("vendredi","M")]
def ordre(s): return s if s>=36 else s+100
COLS = [("lundi","M"),("lundi","AM"),("mardi","M"),("mardi","AM"),("mercredi","M"),("mercredi","AM"),("jeudi","M"),("jeudi","AM"),("vendredi","M"),("vendredi","AM")]

data = {}
for nom in os.listdir(DOSSIER):
    if nom.endswith(".csv"):
        code = nom[:-4]
        with open(os.path.join(DOSSIER,nom),encoding="utf-8") as f:
            data[code] = {int(l[0]):l for l in csv.reader(f) if len(l)>=12 and l[0].isdigit()}

par_vac = defaultdict(list); par_etud = defaultdict(int)
non_4a=0; hors_creneau=0; apres_fin=0
for code,lignes in data.items():
    a = ETUDIANTS.get(code,{}).get("annee")
    for sem,l in lignes.items():
        for col in COLS:
            if "Occluso" in l[IDX[col]]:
                par_vac[(sem,col)].append(code); par_etud[code]+=1
                if a != 4: non_4a += 1
                if col not in CRENEAUX_OCC: hors_creneau += 1
                if ordre(sem) > ordre(22): apres_fin += 1

pas_4 = {k:len(v) for k,v in par_vac.items() if len(v)!=4}
print(f"1) Vacations : {len(par_vac)}, avec !=4 : {len(pas_4)}")
for k,v in list(pas_4.items())[:5]: print(f"      {k} : {v}")
print(f"2) Occluso sur non-4A : {non_4a}")
print(f"3) Hors créneaux : {hors_creneau}")
print(f"4) Après date fin (s22) : {apres_fin}")
codes4 = [c for c,i in ETUDIANTS.items() if i.get("annee")==4 and not i.get("erasmus")]
sous3 = [c for c in codes4 if par_etud.get(c,0) < 3]
print(f"5) 4A sous minimum 3 : {len(sous3)}")
print(f"\n-> {'TOUT OK' if not pas_4 and not non_4a and not hors_creneau and not apres_fin and not sous3 else 'VOIR'}")