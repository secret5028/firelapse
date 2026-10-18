"""Manual transcription of the supplied A-202/203/204 scans, metres on shared axes."""
import json
from pathlib import Path
floors=[]
def floor(n,rects):
    f=dict(n=n,slabs=rects,walls=[],doors=[],windows=[],rooms=[],stairs=[]);floors.append(f);return f
def wall(f,a,b):f['walls'].append([*a,*b])
def door(f,x,z,axis='x',width=.9,swing=1,hinge=1,name='문',certain=True):
    d=dict(x=x,z=z,axis=axis,width=width,swing=swing,hinge=hinge,name=name,certain=certain);f['doors'].append(d);return d
def room(f,name,x,z,w,d,entry=None,edges='nesw'):
    f['rooms'].append(dict(name=name,x=x,z=z,w=w,d=d,entry=entry))
    if 'n' in edges:wall(f,(x,z),(x+w,z))
    if 's' in edges:wall(f,(x,z+d),(x+w,z+d))
    if 'w' in edges:wall(f,(x,z),(x,z+d))
    if 'e' in edges:wall(f,(x+w,z),(x+w,z+d))
def envelope(f):
    wall(f,(0,0),(45.9,0));wall(f,(45.9,0),(45.9,18));wall(f,(45.9,18),(0,18));wall(f,(0,18),(0,0))
def win(f,x,z,axis,width):f['windows'].append(dict(x=x,z=z,axis=axis,width=width))
f=floor(1,[[0,0,45.9,18]])
f['floorBasis']='사용자 지시: 1층 전체 바닥 적용'
envelope(f);room(f,'사무실',0,9,5.1,9,edges='ne')
door(f,.25,9,'x',.9,-1,1,'계단 연결문')
win(f,.8,18,'x',2);win(f,10.2,18,'x',1.1);win(f,20.4,18,'x',1.1);win(f,30.6,18,'x',1.1)
f['stairs']=[dict(x=0,z=7.4,w=5.1,d=1.6,name='DN · 하부 연결 미확인',kind='unknown')]
f=floor(2,[[0,0,45.9,18],[-3.5,6.8,3.5,2.2],[3.3,-1.5,12,1.5]])
envelope(f)
room(f,'식당',0,0,15.3,9,[3.45,9],edges='e')
f['rooms'][-1]['outline']=[[0,0],[15.3,0],[15.3,4.5],[10.2,4.5],[10.2,9],[3.9,9],[3.9,6.8],[0,6.8]]
room(f,'주방',10.2,4.5,5.1,4.5,[14.6,4.5],edges='nw')
wall(f,(0,9),(15.3,9));wall(f,(0,6.8),(3.9,6.8));wall(f,(3.9,6.8),(3.9,9))
door(f,14.1,4.5,'x',1,-1,-1,'주방');door(f,14.2,0,'x',1,-1,1,'상부 외부계단 연결문')
door(f,3.9,7.8,'z',1,1,1,'방풍실 → 식당');door(f,0,7.1,'z',1.5,-1,1,'외부 방풍실 문',False)
f['rooms'].append(dict(name='방풍실',x=0,z=6.8,w=3.9,d=2.2,entry=[3.9,8.3]))
room(f,'화장실(여)',0,9,2.4,2,[2.4,9.55]);door(f,2.4,9.15,'z',.8,-1,1,'화장실(여)')
room(f,'화장실(남)',0,11,2.4,2.5,[2.4,12.7]);door(f,2.4,12.25,'z',.9,-1,-1,'화장실(남)')
room(f,'샤워실',3.9,9,1.7,2,[5.6,10.5]);door(f,5.6,10.1,'z',.8,-1,-1,'샤워실')
room(f,'제습실',3.9,11,1.7,1,edges='new')
room(f,'세면실',5.6,9,2.05,3,[7.1,12],edges='nes');door(f,6.65,12,'x',.9,-1,1,'세면실')
room(f,'조리실',7.65,9,2.55,3,edges='ne')
room(f,'기숙사 #05',10.2,9,5.1,3,[10.9,12]);door(f,10.45,12,'x',.9,-1,1,'기숙사 #05')
room(f,'현관',3.9,12,1.8,1.5,edges='ew');door(f,3.9,12.2,'z',1,-1,-1,'현관');door(f,5.7,12.2,'z',1,1,1,'현관 → 복도')
room(f,'창고(소)',13.8,12,1.5,1.5,[13.8,12.9],edges='ws');door(f,13.8,12.45,'z',.8,-1,-1,'창고(소)')
for i,(x,w,dx) in enumerate([(3.9,3.75,6.55),(7.65,2.55,7.8),(10.2,2.55,10.35),(12.75,2.55,12.9)],1):
    room(f,f'기숙사 #{i:02}',x,13.5,w,4.5,[dx+.45,13.5]);door(f,dx,13.5,'x',.9,1,-1 if i==1 else 1,f'기숙사 #{i:02}')
room(f,'계단실',0,13.5,3.9,4.5,edges='ne');door(f,2.8,13.5,'x',.95,1,-1,'하부 계단 연결문')
door(f,3.05,9,'x',.8,1,-1,'식당 → 복도')
f['rooms'].append(dict(name='창고',x=15.3,z=0,w=30.6,d=18,entry=None))
# Warehouse's hanger door is explicitly labelled; do not interpret it as a pedestrian route.
door(f,20.4,0,'x',4,1,1,'행거도어 4,000 × 5,000',False)
for x,w in [(1,2.7),(5.4,4.4),(11,1.8)]:win(f,x,0,'x',w)
for x,w in [(.8,2),(4.5,2.3),(8.1,1.4),(10.7,1.4),(13.2,1.4),(20.4,1.1),(30.6,1.1)]:win(f,x,18,'x',w)
for z in [1,4.5]:win(f,0,z,'z',2.1)
for z in [2,7,12]:win(f,45.9,z,'z',1.6)
f['stairs']=[dict(x=0,z=13.5,w=3.9,d=4.5,name='계단 A · 2↔3층',kind='u'),dict(x=3.3,z=-1.5,w=12,d=1.5,name='계단 B · 2↔3층',kind='straight'),dict(x=-3.5,z=6.8,w=3.5,d=2.2,name='DN · 외부 연결 미확인',kind='unknown')]
f=floor(3,[[0,0,15.3,18],[3.35,-1.5,9,1.5]])
envelope(f);wall(f,(15.3,0),(15.3,18))
for i,(x,w,dx) in enumerate([(3.9,3.75,6.55),(7.65,2.55,7.8),(10.2,2.55,10.35),(12.75,2.55,12.9)],1):
    room(f,f'기숙사 #{i:02}',x,13.5,w,4.5,[dx+.45,13.5]);door(f,dx,13.5,'x',.9,1,-1 if i==1 else 1,f'기숙사 #{i:02}')
for i,z,d, dz,s in [(9,0,2.7,1.75,-1),(8,2.7,1.8,3.55,-1),(7,5.4,2.7,5.55,1),(6,8.1,1.8,8.25,1),(5,10.8,2.7,10.95,1)]:
    room(f,f'기숙사 #{i:02}',0,z,3.35,d,[3.35,dz+.45]);door(f,3.35,dz,'z',.9,-1,s,f'기숙사 #{i:02}')
for i,x,dx in [(10,5.1,6.55),(11,7.65,7.8),(12,10.2,10.35),(13,12.75,12.9)]:
    room(f,f'기숙사 #{i:02}',x,0,2.55,4.5,[dx+.45,4.5]);door(f,dx,4.5,'x',.9,-1,-1 if i==10 else 1,f'기숙사 #{i:02}')
room(f,'휴게실 / 조리실',5.1,6,5.1,6,edges='n')
wall(f,(10.2,6),(10.2,12))
room(f,'세탁실',10.2,6,1.65,3,[10.7,6]);door(f,10.25,6,'x',.9,1,1,'세탁실')
room(f,'샤워실·화장실(여)',11.85,6,3.45,3,[12.4,6]);door(f,11.95,6,'x',.9,1,1,'샤워실(여)');door(f,14.15,6,'x',.9,1,1,'화장실(여)')
room(f,'샤워실(남)',10.8,9,2.1,3,[11.3,12]);door(f,10.85,12,'x',.9,-1,1,'샤워실(남)')
room(f,'화장실(남)',12.9,9,2.4,3,[13.4,12]);door(f,12.95,12,'x',.9,-1,1,'화장실(남)')
room(f,'계단실',0,13.5,3.9,4.5,edges='ne');door(f,2.8,13.5,'x',.95,1,-1,'하부 계단 연결문')
door(f,3.5,0,'x',.95,-1,1,'상부 외부계단 연결문')
for x,w in [(.8,2),(4.5,2.3),(8.1,1.4),(10.7,1.4),(13.2,1.4),(20.4,1.1),(30.6,1.1)]:win(f,x,18,'x',w)
for z in [.8,3.1,5.8,8.5,11.4]:win(f,0,z,'z',1.2)
for z in [2,7,12]:win(f,45.9,z,'z',1.6)
f['stairs']=[dict(x=0,z=13.5,w=3.9,d=4.5,name='계단 A · 3층 도착',kind='arrival'),dict(x=3.35,z=-1.5,w=9,d=1.5,name='계단 B · 3층 도착',kind='arrival')]
DATA=dict(title='당산리 공장',width=45.9,depth=18,height=3.6,floors=floors,method='제공 이미지 수작업 판독 · 좌표 근사',north=None)
if __name__=='__main__':Path(__file__).with_name('factory-data.json').write_text(json.dumps(DATA,ensure_ascii=False),encoding='utf-8')
