"""Local overlap evidence and grouped model readiness; never invent missing geometry."""
import json,math
from pathlib import Path
import numpy as np
from PIL import Image

def read_json(p):return json.loads(p.read_text('utf8'))
def missing(v):
 a=v.get('metadata',{});r=[]
 if a.get('role')!='floor_plan':r.append('층 평면도 미확정')
 if not a.get('building') or a.get('floor') is None:r.append('동·층 미확정')
 if not a.get('heightM') or a.get('elevationM') is None:r.append('층고·기준높이 미확정')
 if not (a.get('scaleAnchor') or {}).get('lengthM'):r.append('축척 미확정')
 if not a.get('floorOutline'):r.append('바닥 외곽 미확정')
 if len([e for e in v.get('entities',[]) if e.get('kind')=='wall' and e.get('certainty')=='observed'])<3:r.append('벽 판독 부족')
 return r

def summary(folder,m):
 groups={};ready=[];optional=[];seen=set()
 for row in m['pages']:
  n=row['page'];path=folder/f'interpretation-{n}.json'
  if not path.exists():groups.setdefault('판독 데이터 없음',[]).append(n);continue
  v=read_json(path);a=v.get('metadata',{})
  if a.get('role') in ['legend','schedule','diagram']:continue
  errors=missing(v);key=(a.get('building'),a.get('floor'))
  if key in seen:errors.append('같은 동·층의 중복 도면 · 교차 대조 필요')
  if not errors:ready.append(n);seen.add(key)
  for error in errors:groups.setdefault(error,[]).append(n)
  for note in v.get('unresolved',[]):
   if any(k in note for k in ['문','계단','경로','송수','배관','구역','방화','층','축척']):groups.setdefault(note,[]).append(n)
   else:optional.append({'page':n,'note':note})
 return {'readyPages':ready,'critical':[{'reason':k,'pages':v} for k,v in groups.items()],'optionalCount':len(optional),'note':'미판독은 묶어서 알림. 중요 누락 분류는 키워드 기반이며 운영 안전성 검증을 의미하지 않음.'}

def raster(path):
 with Image.open(path) as im:
  gray=im.convert('L').resize((128,128));a=np.asarray(gray,dtype=np.float32)/255
  # Trim common border/title margin before comparison.
  a=1-a[10:118,10:118];a[a<.12]=0
  return a,im.width/im.height

def alignment(a,b):
 fa=np.fft.fft2(a-a.mean());fb=np.fft.fft2(b-b.mean());cross=fa*np.conj(fb);cross/=np.maximum(np.abs(cross),1e-8)
 y,x=np.unravel_index(np.argmax(np.fft.ifft2(cross).real),a.shape)
 dy=int(y if y<=a.shape[0]//2 else y-a.shape[0]);dx=int(x if x<=a.shape[1]//2 else x-a.shape[1])
 if abs(dx)>8 or abs(dy)>8:return 0,None
 moved=np.roll(b,(dy,dx),(0,1));mask=np.ones(a.shape,bool)
 if dy>0:mask[:dy]=False
 if dy<0:mask[dy:]=False
 if dx>0:mask[:,:dx]=False
 if dx<0:mask[:,dx:]=False
 av=a[mask];bv=moved[mask];den=float(np.linalg.norm(av)*np.linalg.norm(bv));score=float(np.dot(av,bv)/den) if den else 0
 return score,{'dxNormalized':dx/128,'dyNormalized':dy/128,'rotation':0,'scale':1}

def overlaps(folder,m):
 rasters=[raster(folder/r['image']) for r in m['pages']];pairs=[]
 # cheap low-resolution feature shortlist, then translation alignment.
 features=[]
 for a,_ in rasters:
  f=a.reshape(12,9,12,9).mean((1,3)).ravel();f=f/(np.linalg.norm(f)+1e-8);features.append(f)
 mat=np.stack(features);similar=mat@mat.T
 for i,(a,ratio) in enumerate(rasters):
  for j in np.argsort(-similar[i])[:5]:
   j=int(j)
   if j<=i or abs(ratio/rasters[j][1]-1)>.02 or similar[i,j]<.8:continue
   score,transform=alignment(a,rasters[j][0])
   if score<.70:continue
   p=m['pages'][i]['page'];q=m['pages'][j]['page'];one=folder/f'interpretation-{p}.json';two=folder/f'interpretation-{q}.json';same=False
   if one.exists() and two.exists():
    x=read_json(one).get('metadata',{});y=read_json(two).get('metadata',{})
    if x.get('building') and y.get('building') and x['building']!=y['building']:continue
    if x.get('floor') is not None and y.get('floor') is not None and x['floor']!=y['floor']:continue
    same=bool(x.get('building') and x.get('floor') is not None and (x.get('building'),x.get('floor'))==(y.get('building'),y.get('floor')))
   pairs.append({'page':p,'reference':q,'similarity':round(score,3),'transform':transform,'sameFloorMetadata':same,'status':'cross-check-candidate','reason':'유사 구조 · 동일 위치/도면 시점/설비 종류 확인 필요. 자동 선 병합 안 함.'})
 return {'pairs':sorted(pairs,key=lambda p:-p['similarity'])[:80],'pagesCompared':len(rasters),'note':'축척·회전이 같은 도면의 작은 위치 이동만 비교. 표제·층·개정 및 설비 연결 확인 전에는 보완 근거 후보로만 사용.'}
