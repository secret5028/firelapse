"""Legend-guided raster symbol matching. Counts are audit targets, never placement rules.
A clear in-plan exemplar can supplement a large printed legend symbol at a different scale.
Only candidate coordinates are returned; apply source/pipe masks and review discrepancies.
"""
from __future__ import annotations
import cv2
import numpy as np

def match_symbols(gray, exemplars, polygon, *, threshold=.88, scales=(.9,1.,1.1), minimum_separation=8):
    if not .5<=threshold<=1 or minimum_separation<1:raise ValueError('invalid matcher settings')
    candidates=[]
    for exemplar in exemplars:
        for rotation in range(4):
            rotated=np.rot90(exemplar,rotation).copy()
            for scale in scales:
                template=cv2.resize(rotated,None,fx=scale,fy=scale)
                if min(template.shape)<5 or any(a>b for a,b in zip(template.shape,gray.shape)) or template.std()<1:continue
                scores=cv2.matchTemplate(gray,template,cv2.TM_CCOEFF_NORMED)
                ys,xs=np.where((scores>=threshold)&(scores==cv2.dilate(scores,np.ones((7,7),np.uint8))))
                for y,x in zip(ys,xs):
                    point=(float(x+template.shape[1]/2),float(y+template.shape[0]/2))
                    if cv2.pointPolygonTest(np.asarray(polygon,np.float32),point,False)<0:continue
                    candidates.append({'point':list(point),'score':float(scores[y,x]),'rotation':rotation*90,'scale':scale})
    accepted=[]
    for candidate in sorted(candidates,key=lambda c:-c['score']):
        p=candidate['point']
        if all(np.linalg.norm(np.subtract(p,c['point']))>=minimum_separation for c in accepted):accepted.append(candidate)
    return accepted

def audit_count(points, expected):
    located=len(points)
    return {'expected':expected,'located':located,'difference':located-expected,'status':'count-matched' if located==expected else 'review-required'}
