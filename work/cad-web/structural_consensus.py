"""Same-building, same-floor consensus. All coordinates retain source evidence."""
import re,json,hashlib
from pathlib import Path
import cv2
import numpy as np

def classify(text):
 t=re.sub(r'\s+','',text).replace('충','층')
 b=re.search(r'(?<!\d)(\d{1,4})동',t)
 if not any(k in t for k in ['평면']):return None
 if not b and not ('주차장' in t or '주자장' in t):return None
 if re.search(r'지하1[.,·]2',t):return None
 floors=[]
 if '지하' in t:
  m=re.search(r'지하(\d+)층',t)
  if m:floors=[-int(m[1])]
 elif '지붕' in t:floors=['roof']
 elif '옥탑' in t:floors=['penthouse']
 else:
  m=re.search(r'(?:지상)?(\d+)[~～\-](\d+)층',t)
  if m and 0<int(m[1])<=int(m[2])<=100:floors=list(range(int(m[1]),int(m[2])+1))
  else:
   m=re.search(r'(?:지상)?(\d+)층',t)
   if m:floors=[int(m[1])]
 if not floors:return None
 if '다락' in t:floors=[str(f)+'-loft' for f in floors]
 discipline='suppression' if any(k in t for k in ['스프링클러','소화','살수']) else 'reference'
 return {'building':b[1]+'동' if b else '공용주차장','floors':floors,'discipline':discipline,'ocrText':text}

def groups(rows):
 result={}
 for row in rows:
  c=classify(row['text'])
  if c:
   for f in c['floors']:result.setdefault((c['building'],str(f)),[]).append({'page':row['page'],**c})
 return result

def gray(path):
 im=cv2.imdecode(np.fromfile(str(path),dtype=np.uint8),cv2.IMREAD_GRAYSCALE)
 if im is None:raise ValueError('image unavailable')
 return im

def ink(im):
 # Exclude title, legend margin and perimeter dimensions from matching/model evidence.
 mask=(im<225).astype(np.uint8)*255;h,w=im.shape
 roi=np.zeros_like(mask);roi[int(h*.12):int(h*.87),int(w*.04):int(w*.79)]=255
 return cv2.bitwise_and(mask,roi)

def register(ref,moving):
 orb=cv2.ORB_create(nfeatures=7000,fastThreshold=8)
 ka,da=orb.detectAndCompute(ref,ink(ref));kb,db=orb.detectAndCompute(moving,ink(moving))
 if da is None or db is None:return None
 pairs=cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(db,da,k=2)
 good=[p[0] for p in pairs if len(p)==2 and p[0].distance<.7*p[1].distance]
 if len(good)<18:return None
 src=np.float32([kb[m.queryIdx].pt for m in good]);dst=np.float32([ka[m.trainIdx].pt for m in good])
 mat,inliers=cv2.estimateAffinePartial2D(src,dst,method=cv2.RANSAC,ransacReprojThreshold=3,maxIters=5000)
 if mat is None:return None
 keep=inliers.ravel().astype(bool);ratio=float(keep.mean());scale=float(np.hypot(mat[0,0],mat[0,1]));err=float(np.median(np.linalg.norm(cv2.transform(src[None],mat)[0][keep]-dst[keep],axis=1)))
 area=cv2.contourArea(cv2.convexHull(dst[keep]))/(ref.shape[0]*ref.shape[1])
 if keep.sum()<18 or ratio<.3 or not .5<scale<2 or err>2.5 or area<.04:return None
 return {'matrix':mat.tolist(),'inliers':int(keep.sum()),'ratio':ratio,'medianErrorPx':err,'coverage':float(area)}

def consensus(paths):
 ref=gray(paths[0]);masks=[ink(ref)];accepted=[{'page':int(Path(paths[0]).stem.split('-')[-1]),'reference':True}];rejected=[];seen={hashlib.sha256(ref.tobytes()).hexdigest()}
 for p in paths[1:]:
  im=gray(p);digest=hashlib.sha256(im.tobytes()).hexdigest()
  if digest in seen:rejected.append({'file':str(p),'reason':'동일 이미지 중복은 별도 근거로 세지 않음'});continue
  seen.add(digest);a=register(ref,im)
  if a is None:rejected.append({'file':str(p),'reason':'정렬 근거 부족'});continue
  warped=cv2.warpAffine(ink(im),np.array(a['matrix']),ref.shape[::-1],flags=cv2.INTER_NEAREST)
  masks.append(warped);accepted.append({'page':int(Path(p).stem.split('-')[-1]),**a})
 if len(masks)<2:return {'status':'insufficient','accepted':accepted,'rejected':rejected,'walls':[]},ref,np.zeros_like(ref)
 votes=sum((cv2.dilate(m,np.ones((3,3),np.uint8))>0).astype(np.uint16) for m in masks)
 common=np.where((votes>=max(2,int(np.ceil(len(masks)*.65))))&(masks[0]>0),255,0).astype(np.uint8)
 lines=cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD).detect(common)[0]
 segments=[]
 if lines is not None:
  for line in lines.reshape(-1,4):
   a,b=line[:2],line[2:];v=b-a;length=np.linalg.norm(v)
   if length>=25:segments.append((a,b,v/length,length))
 walls=[]
 density=cv2.GaussianBlur((ink(ref)>0).astype(np.float32),(0,0),9)
 dense=(density>.16).astype(np.uint8)*255
 dense=cv2.morphologyEx(dense,cv2.MORPH_CLOSE,np.ones((31,31),np.uint8))
 contours,_=cv2.findContours(dense,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
 structure=np.zeros_like(ref)
 if contours:
  big=max(contours,key=cv2.contourArea);cv2.drawContours(structure,[big],-1,255,-1);structure=cv2.dilate(structure,np.ones((31,31),np.uint8))
 # Paired parallel edges are structural candidates, not every common line.
 for i,(a,b,u,length) in enumerate(segments):
  for c,d,v,l2 in segments[i+1:]:
   if abs(float(u@v))<.998:continue
   normal=np.array([-u[1],u[0]]);dist=abs(float((c-a)@normal))
   if not 3<=dist<=16:continue
   lo=max(0,min(float((c-a)@u),float((d-a)@u)));hi=min(length,max(float((c-a)@u),float((d-a)@u)))
   if hi-lo<25:continue
   offset=normal*float((c-a)@normal)*.5;p1=a+u*lo+offset;p2=a+u*hi+offset
   mid=(p1+p2)*.5
   mx,my=map(int,mid)
   if not (0<=my<ref.shape[0] and 0<=mx<ref.shape[1]) or not structure[my,mx]:continue
   if any(np.linalg.norm(p1-np.array(w['a']))+np.linalg.norm(p2-np.array(w['b']))<12 for w in walls):continue
   walls.append({'type':'wall','a':p1.tolist(),'b':p2.tolist(),'evidence':'aligned-common-parallel-edges','certainty':'candidate','sourcePages':[x['page'] for x in accepted],'thicknessPx':dist})
 return {'status':'candidate','accepted':accepted,'rejected':rejected,'walls':walls,'note':'공통 평행선 후보. 개구부·기둥·범례 대조 미완료 구간은 확정 구조가 아님.'},ref,common

