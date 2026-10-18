import pathlib,sys,json,math
W=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(W/'cad-deps'))
from shapely.geometry import Point,LineString
raw=json.loads((W/'raw8-hall.json').read_text(encoding='utf8'))
h=Point(14064.87451,-1761.20921)
for p in raw:
 if p['layer'] in ('CEN','TEXT1','K-FURNITURE','FUR'):continue
 ls=LineString([(x*.001,y*.001) for x,y in p['points']])
 if ls.distance(h)<.3:
  print(p['index'],p['layer'],p['kind'],p['source'],ls.bounds)
import cv2,numpy as np
O=W.parent/'outputs/CAD-v6-무대부-재검토';O.mkdir(exist_ok=True)
groups=[('north',(14054.5,-1763,14066.5,-1759),[('W76',(14059.4,-1761.45,14061.5,-1761.2)),('D16',(14064.0,-1761.5,14065.1,-1760.3))]),
 ('south',(14056.5,-1778.5,14065,-1774.5),[('W79',(14063.25,-1777.55,14064.45,-1776.5)),('LEFT DOOR',(14057.3,-1776.95,14058.45,-1776.0))])]
for name,(x0,y0,x1,y1),labels in groups:
 s=min(1600/(x1-x0),950/(y1-y0));im=np.full((round((y1-y0)*s)+40,round((x1-x0)*s)+40,3),255,np.uint8)
 def px(p):return (round((p[0]-x0)*s)+20,round((y1-p[1])*s)+20)
 for p in raw:
  if p['layer'] in ('CEN','TEXT1','TEX1','TEX2','SYM','지시선'):continue
  pts=[(x*.001,y*.001) for x,y in p['points']]
  color=(100,70,0) if p['layer']=='TEX' else (40,40,40)
  if p['index'] in (4466,4485,4487,4438):color=(0,120,0)
  cv2.polylines(im,[np.int32([px(q) for q in pts])],False,color,2 if p['layer']=='TEX' else 1,cv2.LINE_AA)
 for label,(a,b,c,d) in labels:
  pt=px((a,d));cv2.rectangle(im,pt,px((c,b)),(0,0,220),2);cv2.putText(im,label,(pt[0],pt[1]-5),cv2.FONT_HERSHEY_SIMPLEX,.7,(0,0,200),2)
 cv2.imencode('.png',im)[1].tofile(str(O/f'{name}.png'))
report=dict(north=dict(evidence='WALLBR 이중 경계와 WID 중앙 창틀, 폭 약 1.8m',interpretation='별도 실 및 영사창 가능성; 용도·높이 미확정',D16='문짝 선 부재만으로 폐기 불가; 주변 경계 누락과 함께 재검토'),
 south=dict(W79=dict(arc_layer='FURNITURE',arc_radius_m=.7,leaf_layer='WID',jamb_wall_layer='TEX',interpretation='문짝·호·벽 끝이 함께 존재하는 여닫이문 근거'),left=dict(arc_layer='FURNITURE',arc_radius_m=.75,interpretation='대응 위치에 문이 있으나 폭과 위치는 완전 대칭이 아님')),
 status='원본 재검토 결과. v6 코드 및 추출 데이터는 이번 재검토에서 변경하지 않음')
(O/'판정근거.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
(O/'index.html').write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><title>다목적실 북측·남측 재검토</title><style>body{max-width:1250px;margin:30px auto;background:#f3f5f7;color:#233244;font:17px/1.8 system-ui,'Malgun Gothic';padding:20px}section{background:white;padding:22px;margin:20px 0}img{width:100%}a{color:#1463a3}</style><h1>다목적실 북측·남측 원본 재검토</h1><p>검정은 원본 선, 파랑은 TEX 레이어의 경계선, 초록은 남측 문짝·호를 강조한 검토용 색상입니다. 실제 CAD 색상과 다릅니다.</p><section><h2>북측: 별도 기자재실 / 영사실 가능성</h2><p>WALLBR 이중 경계의 가운데 약 1.8m 창틀 W76이 있습니다. 남측을 무대로 보면 영사창을 둔 별도 실이라는 해석이 가능합니다. 도면에서 영사실 명칭이나 벽 높이는 확인되지 않아 용도와 구획을 확정한 것은 아닙니다. D16 역시 이 경계의 문 후보로 다시 검토해야 합니다.</p><img src="north.png"></section><section><h2>남측: W79의 문짝·호·벽이 서로 다른 레이어에 존재</h2><p>W79에는 WID 레이어의 약 0.7m 문짝, FURNITURE 레이어의 반지름 약 0.7m 여닫이 호, TEX 레이어의 벽 끝이 함께 있습니다. 문 기호가 없었던 것이 아니라 레이어별 분류에서 분리·누락됐습니다. 왼쪽에도 대응 문이 있지만 폭은 약 0.75m이고 위치도 조금 달라, 단순 대칭 복사 대신 실제 선을 사용해야 합니다.</p><img src="south.png"></section><p>이번 결과는 원본 재검토입니다. v6 코드와 추출 데이터는 변경하지 않았습니다. <a href="../CAD-문판정-v6/office-1F/index.html">v6 결과</a> · <a href="판정근거.json">판정 근거</a></p></html>''',encoding='utf8')
