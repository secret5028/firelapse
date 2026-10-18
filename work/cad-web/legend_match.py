"""Match source legend crops, retain candidates separately from accepted geometry."""
import io, math
from PIL import Image
def enrich(result, raw, request):
 specs=raw.get('symbolTemplates',[])
 if not specs:return result
 if not isinstance(specs,list) or len(specs)>20:raise ValueError('범례 템플릿은 최대 20개')
 from head_symbol_detection import match_symbols,audit_count
 import numpy as np
 images={i:np.asarray(Image.open(io.BytesIO(data)).convert('L')) for i,data in request['images']}
 target=images[request['page']];h,w=target.shape
 reports=[]
 for spec in specs:
  if not isinstance(spec,dict) or spec.get('kind') not in ['head','hydrant','extinguisher']:raise ValueError('범례 종류 오류')
  page=spec.get('page');box=spec.get('box');region=spec.get('region');expected=spec.get('expected')
  if type(page)!=int or page not in images:raise ValueError('범례 원본 페이지 오류')
  def point(q):return isinstance(q,list) and len(q)==2 and all(type(x) in [int,float] and math.isfinite(x) and 0<=x<=1 for x in q)
  if not isinstance(box,list) or len(box)!=2 or not all(point(q) for q in box):raise ValueError('범례 영역 오류')
  if not isinstance(region,list) or not 3<=len(region)<=100 or not all(point(q) for q in region):raise ValueError('기호 탐색 영역 필요')
  if expected is not None and (type(expected)!=int or not 0<=expected<=10000):raise ValueError('범례 수량 오류')
  source=images[page];sh,sw=source.shape
  x0,y0=round(box[0][0]*sw),round(box[0][1]*sh);x1,y1=round(box[1][0]*sw),round(box[1][1]*sh)
  if not 5<=x1-x0<=256 or not 5<=y1-y0<=256:raise ValueError('범례 기호 크기는 5~256픽셀')
  hits=match_symbols(target,[source[y0:y1,x0:x1]],[[q[0]*w,q[1]*h] for q in region],threshold=.9)
  reports.append({'kind':spec['kind'],'sourcePage':page,'box':box,'expected':expected,'candidates':[dict(hit,point=[hit['point'][0]/w,hit['point'][1]/h]) for hit in hits[:2000]],'audit':audit_count(hits,expected) if expected is not None else {'located':len(hits),'status':'quantity-unknown'},'status':'candidates-only'})
 result['symbolMatches']=reports
 result['unresolved']=result.get('unresolved',[])+['범례 '+x['kind']+': 기호 매칭 후보 '+str(x['audit']['located'])+'개 · 위치 확정 전' for x in reports]
 return result
