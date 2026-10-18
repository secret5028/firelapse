import sys,json,math,ezdxf,numpy as np,cv2
from ezdxf.math import Vec3
f=sys.argv[1]; out=sys.argv[2]
WALL=('IN-BWALL','IN-CON','C-300X300','COL','WAL','CON')
CLOSE=('IN-WIN','IN-DOFRAME','IN-SILL','WID')
d=ezdxf.readfile(f); msp=d.modelspace()
def lay(e): return e.dxf.layer.upper()
def segs(e,depth=0):
    t=e.dxftype()
    if t=='INSERT' and depth<4:
        try:
            for v in e.virtual_entities():
                if v.dxf.layer=='0': v.dxf.layer=e.dxf.layer
                yield from segs(v,depth+1)
        except Exception: pass
    elif t=='LINE': yield lay(e),[(e.dxf.start.x,e.dxf.start.y),(e.dxf.end.x,e.dxf.end.y)],False
    elif t in('LWPOLYLINE','POLYLINE'):
        try:
            from ezdxf import path as zp
            pts=[(v.x,v.y) for v in zp.make_path(e).flattening(20)]
        except Exception: return
        closed=e.closed if t=='LWPOLYLINE' else e.is_closed
        yield lay(e),pts,closed
    elif t in('ARC','CIRCLE'):
        yield lay(e),[(v.x,v.y) for v in e.flattening(50)],t=='CIRCLE'
    elif t=='HATCH':
        for p in e.paths:
            try: yield lay(e),[(v.x,v.y) for v in p.vertices] if hasattr(p,'vertices') else [],True
            except Exception: pass
W,C=[],[]
for e in msp:
    for l,p,cl in segs(e):
        if len(p)<2: continue
        if any(l.startswith(k) for k in WALL): W.append((p,cl))
        elif any(l.startswith(k) for k in CLOSE): C.append((p,cl))
allp=np.array([q for p,_ in W for q in p]); x0,y0=allp.min(0); x1,y1=allp.max(0)
span=max(x1-x0,y1-y0); unit=1.0 if span<500 else 0.001   # m or mm → m
R=0.02   # 2cm/px
pad=40; Wd=int((x1-x0)*unit/R)+2*pad; Hd=int((y1-y0)*unit/R)+2*pad
tr=lambda p: np.int32([[ (x-x0)*unit/R+pad, Hd-((y-y0)*unit/R+pad)] for x,y in p])
wall=np.zeros((Hd,Wd),np.uint8)
for p,cl in W:
    q=tr(p)
    cv2.polylines(wall,[q],False,255,2)
    if cl and len(q)>2 and cv2.contourArea(q)<(0.8/R)**2*4: cv2.fillPoly(wall,[q],255)   # 기둥 등 작은 닫힌 도형은 채움
closer=wall.copy()
for p,cl in C: cv2.polylines(closer,[tr(p)],False,255,2)
closer=cv2.morphologyEx(closer,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
# 바깥 = 가장자리에서 채움
ff=closer.copy(); m=np.zeros((Hd+2,Wd+2),np.uint8); cv2.floodFill(ff,m,(0,0),128)
outside=ff==128
free=(closer==0)&~outside
n,lab,st,_=cv2.connectedComponentsWithStats(free.astype(np.uint8),4)
rooms=[]; minA=(1.0/R)**2   # 1㎡ 이상
wallbody=np.zeros_like(wall)
for i in range(1,n):
    a=st[i,cv2.CC_STAT_AREA]
    mk=(lab==i).astype(np.uint8)
    thick=cv2.distanceTransform(mk,cv2.DIST_L2,3).max()*2*R
    if a<minA or thick<0.45: wallbody[mk>0]=255; continue   # 벽 두 줄 사이 띠(두께<45cm) = 벽체
    cs,_=cv2.findContours((lab==i).astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    c=max(cs,key=cv2.contourArea); c=cv2.approxPolyDP(c,1.5,True)
    rooms.append(dict(area=round(a*R*R,1),poly=[[round((x-pad)*R,2),round((Hd-y-pad)*R,2)] for x,y in c[:,0]]))
wallbody|=wall
# 벽 다각형(구멍 포함)
cs,hier=cv2.findContours(wallbody,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
shapes=[]
for i,c in enumerate(cs):
    if hier[0][i][3]!=-1 or cv2.contourArea(c)<20: continue
    c=cv2.approxPolyDP(c,1.0,True)
    holes=[]; j=hier[0][i][2]
    while j!=-1:
        h=cv2.approxPolyDP(cs[j],1.0,True)
        if cv2.contourArea(h)>4: holes.append([[ (x-pad)*R,(Hd-y-pad)*R] for x,y in h[:,0]])
        j=hier[0][j][0]
    shapes.append(dict(o=[[ (x-pad)*R,(Hd-y-pad)*R] for x,y in c[:,0]],h=holes))
# 개구부(창·문틀) 위치: CLOSE 요소의 외접 사각형 → 3D에서 높이 구간 표시
ops=[]
for p,cl in C:
    a=np.array(p)*unit; a=(a-[x0*unit,y0*unit])
    ops.append([round(a[:,0].min(),2),round(a[:,1].min(),2),round(a[:,0].max(),2),round(a[:,1].max(),2)])
json.dump(dict(size=[round((Wd-2*pad)*R,1),round((Hd-2*pad)*R,1)],walls=shapes,rooms=rooms,openings=ops),open(out+'.json','w'))
vis=np.full((Hd,Wd,3),255,np.uint8)
rng=np.random.default_rng(3)
for i in range(1,n):
    if st[i,cv2.CC_STAT_AREA]>=minA: vis[lab==i]=rng.integers(150,240,3)
vis[wallbody>0]=(40,40,40)
for p,cl in C: cv2.polylines(vis,[tr(p)],False,(220,120,0),2)
cv2.imwrite(out+'_plan.png',vis)
print('unit',unit,'px',Wd,Hd,'walls',len(shapes),'rooms',len(rooms),'areas',sorted([r['area'] for r in rooms],reverse=True)[:12],'openings',len(ops))
