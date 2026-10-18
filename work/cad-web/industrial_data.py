"""Manual source reconciliation: architecture Dec 2015 + mechanical Oct 2015."""
import json
from pathlib import Path
F=[]
def floor(n,y,slabs):
    f=dict(n=n,y=y,slabs=slabs,walls=[],doors=[],windows=[],rooms=[],obstacles=[]);F.append(f);return f
def wall(f,x,z,X,Z):f['walls'].append([x,z,X,Z])
def room(f,name,x,z,w,d,entry=None,edges='nesw'):
    r=dict(name=name,x=x,z=z,w=w,d=d,entry=entry);f['rooms'].append(r)
    if 'n'in edges:wall(f,x,z,x+w,z)
    if 's'in edges:wall(f,x,z+d,x+w,z+d)
    if 'w'in edges:wall(f,x,z,x,z+d)
    if 'e'in edges:wall(f,x+w,z,x+w,z+d)
    return r
def door(f,x,z,axis='x',width=1,swing=1,hinge=1,name='문',kind='swing',height=2.1):
    f['doors'].append(dict(x=x,z=z,axis=axis,width=width,swing=swing,hinge=hinge,name=name,kind=kind,height=height))
def win(f,x,z,axis='x',width=2,kind='창'):
    f['windows'].append(dict(x=x,z=z,axis=axis,width=width,kind=kind))
def envelope(f):
    for w in [[0,0,98.6,0],[98.6,0,98.6,32],[98.6,32,0,32],[0,32,0,0]]:f['walls'].append(w)
f=floor(1,0,[[0,0,98.6,32]]);envelope(f)
room(f,'경비실',6,0,4.2,2.1,[6.6,2.1]);door(f,6.1,2.1,width=1,swing=-1,name='경비실')
room(f,'화장실(남)',6,2.1,4.2,2.7,[6,3.2]);door(f,6,2.7,'z',1,1,name='화장실(남)')
room(f,'화장실(여)',6,4.8,4.2,2.7,[6,6.7]);door(f,6,6.2,'z',1,1,name='화장실(여)')
room(f,'탈의실(남)',0,3.7,3.5,1.9,[3.5,4.8]);door(f,3.5,4.3,'z',1,-1,name='탈의실(남)')
room(f,'탈의실(여)',0,5.6,3.5,1.9,[3.5,6.7]);door(f,3.5,6.2,'z',1,-1,name='탈의실(여)')
wall(f,3.5,7.5,6,7.5);door(f,3.8,7.5,width=1.8,swing=-1,name='계단실 방화문',kind='double')
room(f,'창고 01',0,7.5,10.2,6.4,[10.2,12]);door(f,10.2,11.1,'z',1.8,1,name='창고 01 방화문',kind='double')
room(f,'창고 02',0,13.9,10.2,4.4,[10.2,16.5]);door(f,10.2,15.6,'z',1.8,1,name='창고 02 방화문',kind='double')
room(f,'폐수처리시설',0,18.3,10.2,13.7,[10.2,20.6]);door(f,10.2,19.7,'z',1.8,1,name='폐수처리시설 방화문',kind='double')
room(f,'화장실(동측)',88.9,0,3.7,3.7,[92.6,2.5]);door(f,92.6,2,'z',1,-1,name='동측 화장실')
wall(f,92.6,3.7,98.6,3.7);door(f,93,3.7,width=1.6,swing=-1,name='동측 계단실 방화문',kind='double')
r=room(f,'공장',10.2,0,88.4,32,[13.8,0],edges='');r['outline']=[[10.2,0],[88.9,0],[88.9,3.7],[98.6,3.7],[98.6,32],[10.2,32]]
entries=[]
for i,(x,width,h) in enumerate([(11.8,4,4),(35.45,5.5,5.5),(59.85,5.5,5.5),(85.2,4,4)],1):
    door(f,x,0,width=width,name=f'전면 행거도어 {i}',kind='sliding',height=h);entries.append(dict(id='F'+str(i),name=f'전면 출입구 {i}',x=x+width/2,z=0,inside=[x+width/2,.5]))
for i,x in enumerate([14.5,38.9,63.3,87.7],1):
    door(f,x-.7,32,width=1.4,name=f'후면 출입구 {i} · 폭 근사',kind='sliding');entries.append(dict(id='R'+str(i),name=f'후면 출입구 {i}',x=x,z=32,inside=[x,31.5]))
for tag,x in [('L',4.75),('E',93.6)]:
    door(f,x-.8,0,width=1.6,swing=-1,name=tag+' 계단실 외부 출입문',kind='double');entries.append(dict(id=tag,name=('좌측'if tag=='L'else'우측')+' 계단실 입구',x=x,z=0,inside=[x,.5]))
# Simplified process-line footprints from 017. They are obstacles, not fire equipment.
f['obstacles']=[[19,2,38,11],[19,19,38,11],[67,4,18,9],[67,19,18,10],[1.5,20.5,6.8,10]]
for x in [18,21,24,27,30,33,42,45,48,51,54,57,66,69,72,75,78,81]:win(f,x,0,width=1.8)
for x in [1,4,7,11,17,20,23,26,29,32,35,42,45,48,51,54,57,60,67,70,73,76,79,82,90,93,96]:win(f,x,32,width=1.3)
for z in [5,9,13,17,21,25,29]:win(f,98.6,z,'z',2)
for z in [9,13,20,24,28]:win(f,0,z,'z',2)
f=floor(2,6,[[0,0,10.2,32],[88.9,0,9.7,32]])
for x,w in [(0,10.2),(88.9,9.7)]:
    for a in [[x,0,x+w,0],[x+w,0,x+w,32],[x+w,32,x,32],[x,32,x,0]]:f['walls'].append(a)
room(f,'화장실(남)',6,0,4.2,2.6,[6,1.3]);door(f,6,.8,'z',1,1,name='화장실(남)')
room(f,'화장실(여)',6,2.6,4.2,2.6,[6,4]);door(f,6,3.5,'z',1,1,name='화장실(여)')
room(f,'탕비실',6,5.2,4.2,2.3,[6,6.3]);door(f,6,5.8,'z',1,1,name='탕비실')
room(f,'접견실',6,7.5,4.2,7,[6,13.3]);door(f,6,12.8,'z',1,1,name='접견실')
room(f,'실험실',0,4.3,3.5,6.4,[3.5,9.8]);door(f,3.5,9.3,'z',1,-1,name='실험실');door(f,3.5,4.6,'z',1,-1,name='실험실 상부문')
room(f,'회의실',0,10.7,3.5,3.8,[3.5,13.4]);door(f,3.5,12.9,'z',1,-1,name='회의실')
room(f,'사무실',0,14.5,10.2,10.8,[4.75,14.5],edges='');wall(f,0,25.3,10.2,25.3)
room(f,'대표이사실',0,25.3,7.5,6.7,[6.8,25.3],edges='e');door(f,6.3,25.3,width=1,swing=1,name='대표이사실')
room(f,'화장실(임원)',7.5,25.3,2.7,3.3,[7.5,26.5]);door(f,7.5,26,'z',1,1,name='임원 화장실')
room(f,'휴게실(서측)',7.5,28.6,2.7,3.4,[7.5,29.8],edges='n');wall(f,7.5,28.6,7.5,32);door(f,7.5,29.3,'z',1,1,name='서측 휴게실')
room(f,'창고(동측)',88.9,0,3.7,3.7,[90.3,3.7]);door(f,89.8,3.7,width=1,swing=-1,name='동측 창고')
wall(f,92.6,3.7,98.6,3.7);door(f,93,3.7,width=1.6,swing=1,name='동측 계단 연결문',kind='double')
room(f,'휴게실(동측)',88.9,3.7,5.9,7.3,[94.8,7],edges='w');wall(f,94.8,3.7,94.8,11);door(f,94.8,6.5,'z',1,-1,name='동측 휴게실')
room(f,'세탁 및 다용도실',94.8,3.7,3.8,3.8,[94.8,6],edges='nes');door(f,94.8,5.5,'z',1,1,name='세탁 및 다용도실')
for i,z in enumerate([7.5,11,14.5,18,21.5,25],1):
    d=7 if i==6 else 3.5;room(f,f'숙소 {i:02}',94.8,z,3.8,d,[94.8,z+1.7]);door(f,94.8,z+1.2,'z',1,1,name=f'숙소 {i:02}')
for i,z in enumerate([11,14.5,18,21.5,25],7):
    d=7 if i==11 else 3.5;room(f,f'숙소 {i:02}',88.9,z,3.8,d,[92.7,z+1.7]);door(f,92.7,z+1.2,'z',1,-1,name=f'숙소 {i:02}')
for z in [6,9.5,13,16.5,20,23.5,27,30.5]:win(f,88.9,z,'z',1.7,'방화유리')
for z in [6,9.5,13,16.5,20,23.5,27,30.5]:win(f,98.6,z,'z',1.7)
for z in [5.5,11.5,17.5,22,28]:win(f,0,z,'z',1.8)
f=floor(3,9.6,[[0,0,10.2,32],[88.9,0,9.7,32]])
room(f,'옥상 좌측',0,4.3,10.2,27.7,[5,4.3],edges='');wall(f,0,4.3,10.2,4.3);door(f,4.5,4.3,width=1,name='좌측 옥상 출입문')
room(f,'펌프실',88.9,0,4.25,18.3,[93.15,17.2]);door(f,93.15,16.7,'z',1,-1,name='펌프실 출입문')
room(f,'옥상 우측',93.15,4.3,5.45,27.7,[94,4.3],edges='');wall(f,93.15,4.3,98.6,4.3);door(f,93.5,4.3,width=1,name='우측 옥상 출입문')
for a in [[0,0,10.2,0],[0,0,0,4.3],[10.2,0,10.2,4.3],[93.15,0,98.6,0],[98.6,0,98.6,4.3]]:f['walls'].append(a)
MECH=[]
for i,(x,z) in enumerate([(10.65,14),(33.7,.5),(67.2,.5),(98.1,14),(33.7,31.5),(67.2,31.5)],1):MECH.append(dict(id=f'H1-{i}',type='hydrant',name=f'1층 옥내소화전 {i}',f=1,x=x,z=z,source='002 · MF-02',system='H'))
for i,(x,z) in enumerate([(9.2,14.8),(93.7,16.9)],1):MECH.append(dict(id=f'H2-{i}',type='hydrant',name=f'2층 옥내소화전 {i}',f=2,x=x,z=z,source='003 · MF-03',system='H'))
MECH.extend([dict(id='inlet',type='inlet',name='연결송수구',f=1,x=92,z=-1.2,source='001·002 · 공통 소화배관 연결',system='H'),dict(id='PA-A',type='valve',name='준비작동식 밸브 A',f=1,x=5,z=1.5,source='004 · A 상세',system='SP-A'),dict(id='PA-B',type='valve',name='준비작동식 밸브 B',f=1,x=92,z=4.7,source='004 · B 상세',system='SP-B'),dict(id='tank',type='tank',name='소화수조 · 소화용수 45톤 이상',f=3,x=90.8,z=6.2,source='001·006',system='H')])
for i in range(3):MECH.append(dict(id='pump'+str(i),type='pump',name=['주펌프','예비펌프','보조펌프'][i],f=3,x=89.6+i*1.1,z=16.4,source='001·006',system='H'))
DATA=dict(title='강화산업단지 7B-5L 외 3필지 공장',width=98.6,depth=32,floors=F,entries=entries,mechanical=MECH,north=[1,0],stairAnchors={'L':[[4.8,1.2],[4.8,3.2],[4.8,3.2]],'E':[[93.7,1.2],[93.7,3.2],[94,3.2]]},sources={str(n):title for n,title in [(1,'범례·장비일람·소화배관 계통도'),(2,'1층 소화배관'),(3,'2층 소화배관'),(4,'1층 스프링클러'),(6,'지붕층 소화배관'),(9,'1층 경보설비'),(10,'2층 경보설비'),(11,'지붕층 경보설비'),(12,'1층 방송·유도등·비상조명'),(13,'2층 방송·유도등·비상조명'),(14,'지붕층 방송·유도등·비상조명'),(16,'건물 배치도'),(17,'1층 건축 평면'),(18,'2층 건축 평면'),(19,'옥탑층 건축 평면'),(20,'1층 방화구획'),(21,'2층 방화구획'),(22,'1층 창호'),(23,'2층 창호'),(24,'옥탑층 창호')]})
if __name__=='__main__':Path('work/industrial-data.json').write_text(json.dumps(DATA,ensure_ascii=False),encoding='utf-8')
