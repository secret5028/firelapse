"""Local-only candidate triage and persistent API spending guards."""
import hashlib,io,json,math,time
from PIL import Image,ImageFilter,ImageStat

def triage(folder,m):
 seen={};rows=[]
 for p in m['pages']:
  with Image.open(folder/p['image']) as src:
   im=src.convert('L');digest=hashlib.sha256(im.tobytes()+str(im.size).encode()).hexdigest()
   duplicate=seen.get(digest);seen.setdefault(digest,p['page'])
   text=p.get('text','');role=next((v for k,v in [('범례','legend'),('일람표','schedule'),('계통도','diagram'),('평면도','floor_plan')] if k in text),'unknown')
   candidates=[]
   # Edge density ranks local inspection candidates, not semantic certainty.
   for y in range(4):
    for x in range(4):
     q=[x/4,y/4,(x+1)/4,(y+1)/4];tile=im.crop(tuple(round(q[i]*(im.width if i%2==0 else im.height)) for i in range(4)))
     pixels=list(tile.getdata());ink=sum(v<180 for v in pixels)/max(1,len(pixels))
     if .005<ink<.65:
      edge=ImageStat.Stat(tile.filter(ImageFilter.FIND_EDGES)).mean[0]
      candidates.append({'rect':q,'score':round(ink/(edge+1),5),'reason':'선·문자가 있는 영역 · 흐림 여부와 필요성 확인'})
   candidates.sort(key=lambda c:c['score'],reverse=True)
   rows.append({'page':p['page'],'role':role,'duplicateOf':duplicate,'candidates':candidates[:4],'note':'문자층 키워드 분류' if role!='unknown' else '문자/도면 종류 자동 판정 불가'})
 return {'version':1,'sourceHash':m['sha256'],'pages':rows,'duplicateCount':sum(r['duplicateOf'] is not None for r in rows),'note':'완전히 같은 미리보기만 중복 표시. 반복층·같은 기호로 임의 확정하지 않음.'}

def crop_request(p,rects):
 if not isinstance(rects,dict):raise ValueError('판독 영역 형식 오류')
 used={};images=[]
 for i,data in p['images']:
  q=rects.get(str(i+1))
  if not isinstance(q,list) or len(q)!=4 or any(type(x) not in [int,float] or not math.isfinite(x) or not 0<=x<=1 for x in q) or q[2]<=q[0] or q[3]<=q[1]:raise ValueError('전송할 각 페이지의 영역을 지정하세요.')
  with Image.open(io.BytesIO(data)) as im:
   box=tuple(round(q[n]*(im.width if n%2==0 else im.height)) for n in range(4))
   tile=im.crop(box)
   if min(tile.size)<16:raise ValueError('판독 영역이 너무 작습니다.')
   tile.thumbnail((1280,1280));b=io.BytesIO();tile.save(b,'PNG');images.append((i,b.getvalue()))
  used[str(i+1)]=q
 old=p['requestId'];p['requestId']=hashlib.sha256((old+json.dumps(used,sort_keys=True)+'crop-v1').encode()).hexdigest()
 p['prompt']=p['prompt'].replace(old,p['requestId'])+'\n부분 판독이다. 각 이미지 좌표는 잘라낸 이미지 자체 기준 0~1이다. 해당 영역에서 보이는 항목만 반환하고 전체 바닥/층 정보를 추정하지 마라. metadata.role=unknown, scaleAnchor=null, floorOutline=[]로 반환. 누락 구간을 연결하지 마라.'
 p.update(images=images,crops=used,partial=True,maxOutputTokens=2500)
 return p

def preview(p,folder):
 sizes=[]
 for i,b in p['images']:
  with Image.open(io.BytesIO(b)) as im:sizes.append({'page':i+1,'width':im.width,'height':im.height})
 ledger=json.loads((folder/'api-ledger.json').read_text('utf8')) if (folder/'api-ledger.json').exists() else {'attempts':[]}
 return {'requestId':p['requestId'],'images':sizes,'pixels':sum(s['width']*s['height'] for s in sizes),'outputTokenLimit':p.get('maxOutputTokens',2500),'callsUsed':len(ledger['attempts']),'pixelsUsed':sum(a['pixels'] for a in ledger['attempts']),'cached':(folder/('cache-'+p['requestId']+'.json')).exists(),'note':'입력 토큰·금액은 제공자와 모델에 따라 달라 확정 계산하지 않음. 호출 수·전송 화소·최대 출력으로 제한.'}

def reserve(folder,p,req,atomic):
 info=preview(p,folder)
 if req.get('previewId')!=p['requestId']:raise ValueError('전송량 확인을 먼저 눌러 현재 영역을 확인하세요.')
 limit=req.get('callLimit',5);pixels=req.get('pixelLimit',10000000)
 if type(limit)!=int or not 0<=limit<=50 or type(pixels)!=int or not 0<=pixels<=100000000:raise ValueError('호출 한도는 0~50, 화소 한도는 0~100MP')
 if info['callsUsed']>=limit or info['pixelsUsed']+info['pixels']>pixels:raise ValueError('작업 API 사용 한도에 도달했습니다. 추가 호출을 중단했습니다.')
 path=folder/'api-ledger.json';ledger=json.loads(path.read_text('utf8')) if path.exists() else {'attempts':[]}
 ledger['attempts'].append({'requestId':p['requestId'],'pixels':info['pixels'],'time':time.time(),'provider':req.get('provider'),'model':req.get('model'),'status':'reserved'})
 atomic(path,ledger) # Failed/uncertain calls also consume budget; no automatic retry.
