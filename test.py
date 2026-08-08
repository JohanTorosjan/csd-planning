import pedo_periode_56 as p56
import pedo_groupes as pg
from collections import defaultdict

data = p56.charger_pedo()
seances = p56.seances_actuelles(data)
libres = p56.libres_par_etudiant()
groupes = p56.composer_groupes(seances, libres)
attributions, total = p56.placer(groupes, libres, seances)

doublons = 0
for code, places in attributions.items():
    par_sem = defaultdict(list)
    for cr, sem in places:
        par_sem[sem].append(cr)
    for sem, crs in par_sem.items():
        if len(crs) > 1:
            doublons += 1
            if doublons <= 5:
                print(f"  ⚠️ {code} sem {sem} : {crs}")
print(f"1) Doublons intra-P5-6 : {doublons}")

index = {}
for code, lignes in data.items():
    index[code] = {int(l[0]): l for l in lignes if len(l)>=12 and l[0].isdigit()}
conflits = 0
for code, places in attributions.items():
    for cr, sem in places:
        l = index[code].get(sem)
        if l and l[pg.IDX[cr]] != "—":
            conflits += 1
            if conflits <= 5:
                print(f"  ⚠️ {code} sem {sem} {cr[0]} : '{l[pg.IDX[cr]]}'")
print(f"2) Conflits : {conflits}")

print(f"\n3) Total séances P5-6 : {sum(len(v) for v in attributions.values())}")