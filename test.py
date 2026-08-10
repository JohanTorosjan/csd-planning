import paro
import pedo_groupes as pg
from etudiants import ETUDIANTS
from collections import defaultdict
import statistics, os

data = paro.charger(paro.DOSSIER_OCCLUSO)
aff, alertes = paro.placer(data)
def ordre(s): return s if s>=36 else s+100

par_vac=defaultdict(list)
for c,pl in aff.items():
    for v in pl: par_vac[v].append(c)
pas4=sum(1 for m in par_vac.values() if len(m)!=4)
apres=sum(1 for c,pl in aff.items() for s,co in pl if ordre(s)>ordre(22))
non456=sum(1 for c,pl in aff.items() for _ in pl if ETUDIANTS.get(c,{}).get("annee") not in (4,5,6))
lunM=sum(1 for c,pl in aff.items() for s,co in pl if co==("lundi","M"))
index={c:{int(l[0]):l for l in data[c] if len(l)>=12 and l[0].isdigit()} for c in aff}
conflits=sum(1 for c,pl in aff.items() for s,co in pl if index[c].get(s) and index[c][s][pg.IDX[co]]!="—")
doublons=sum(1 for c,pl in aff.items() if len(pl)!=len(set(pl)))
print("=== INTÉGRITÉ ===")
print(f"1) != 4 places : {pas4}")
print(f"2) Après s22 : {apres}")
print(f"3) Non 4/5/6 : {non456}")
print(f"4) Lundi matin : {lunM}")
print(f"5) Conflits : {conflits}")
print(f"6) Doublons : {doublons}")
ok = not pas4 and not apres and not non456 and not lunM and not conflits and not doublons
print(f"-> {'✅ TOUT OK' if ok else '⚠️ VOIR'}")

print("\n=== INTÉGRATION (sur como) ===")
if os.path.isdir("planning_csv_como"):
    data2 = paro.charger("planning_csv_como")
    aff2, al2 = paro.placer(data2)
    nvac2=len(set(v for pl in aff2.values() for v in pl))
    print(f"Paro sur como : {nvac2} vac (isolé : {len(par_vac)})")
    for a in (4,5,6):
        codes=[c for c,i in ETUDIANTS.items() if i.get("annee")==a and not i.get("erasmus")]
        vals=[len(aff2.get(c,[])) for c in codes]
        print(f"   {a}A : moy={statistics.mean(vals):.1f}, min={min(vals)}")
    vac2=defaultdict(list)
    for c,pl in aff2.items():
        for v in pl: vac2[v].append(c)
    print(f"   Salles non pleines : {sum(1 for m in vac2.values() if len(m)!=4)}/{len(vac2)}")
else:
    print("(dossier como absent — lance como.py --export d'abord)")