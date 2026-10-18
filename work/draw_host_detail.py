import pathlib,sys,json
W=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(W/'cad-deps'))
import cv2,numpy as np
groups=[('office-1F',['W68','W69','W72']),('office-1F',['W78','W79','D18']),('hotel-1F',['W2','W13','W14','W17']),('exhibition-1F',['W2','W3','W7','W8'])]
for idx,(name,ids) in enumerate(groups):
 p=json.loads((W.parent/'outputs/CAD-연결보강-v4'/name/'plan.json').read_text(encoding='utf8'))
 os=[o for o in p['openings'] if o['id'] in ids];points=[pt for o in os for poly in o['polys'] for pt in poly]
 xs,ys=zip(*points);xmin,xmax,ymin,ymax=min(xs)-1,max(xs)+1,min(ys)-1,max(ys)+1
 scale=min(1250/(xmax-xmin),800/(ymax-ymin));im=np.full((round((ymax-ymin)*scale)+50,round((xmax-xmin)*scale)+30,3),255,np.uint8)
 def pix(pt):return (round((pt[0]-xmin)*scale)+10,round((ymax-pt[1])*scale)+30)
 for v in p['source_vectors']:
  if v['excluded_from_boundary']:continue
  pts=v['points'];xx,yy=zip(*pts)
  if max(xx)<xmin or min(xx)>xmax or max(yy)<ymin or min(yy)>ymax:continue
  color={'wall':(40,40,40),'column':(50,50,130),'door':(0,130,0),'window':(230,130,40)}[v['category']]
  cv2.polylines(im,[np.int32([pix(pt) for pt in pts])],v['closed'],color,2 if v['category']=='wall' else 1)
 for o in os:
  pts=[pt for poly in o['polys'] for pt in poly];xx,yy=zip(*pts);a=pix((min(xx)-.1,max(yy)+.1));b=pix((max(xx)+.1,min(yy)-.1))
  cv2.rectangle(im,a,b,(0,0,230),2);cv2.putText(im,o['id'],(a[0],a[1]-5),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,0,200),2)
 cv2.imencode('.png',im)[1].tofile(str(W/f'host-detail-{idx}.png'))
