import urgences as u
import pedo_groupes as pg
from etudiants import ETUDIANTS
from collections import defaultdict

u.POIDS_RECENCE = 3.0

data = u.charger()
affectations, libelles = u.placer(data)
COLONNES = pg.COLONNES; IDX = pg.IDX

compte = defaultdict(int)
for code, places in affectations.items():
    for sem,col in places:
        compte[(sem,col)] += 1
pas_10 = {k:v for k,v in compte.items() if v != 10}
print(f"1) Vacations avec != 10 étudiants : {len(pas_10)}")
for (sem,col),v in list(pas_10.items())[:10]:
    print(f"     s{sem} {col[0]}{col[1]} : {v}")

print(f"\n2) Vacations couvertes : {len(libelles)}")
print(f"   Affectations : {sum(compte.values())} (attendu {len(libelles)*10})")

index = {}
for code,lignes in data.items():
    index[code] = {int(l[0]):l for l in lignes if len(l)>=12 and l[0].isdigit()}
conflits=0
for code,places in affectations.items():
    for sem,col in places:
        l = index[code].get(sem)
        if l and l[IDX[col]] != "—": conflits+=1
print(f"\n3) Conflits : {conflits}")

doublons=0
for code,places in affectations.items():
    if len(places) != len(set(places)): doublons+=1
print(f"4) Doublons sur une vacation : {doublons}")

mauvaise_compo=0
for (sem,col),lib in libelles.items():
    promos_attendues = set(int(x) for x in lib.split("/"))
    promos_reelles=set()
    for code,places in affectations.items():
        if (sem,col) in places:
            promos_reelles.add(ETUDIANTS[code]["annee"])
    if promos_reelles - promos_attendues: mauvaise_compo+=1
print(f"5) Vacations avec promo hors compo : {mauvaise_compo}")
print(f"\n-> {'TOUT OK' if not pas_10 and not conflits and not doublons and not mauvaise_compo else 'VOIR CI-DESSUS'}")