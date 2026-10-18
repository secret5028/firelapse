import pathlib,sys,json,html
W=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(W/'cad-deps'))
import cv2,numpy as np
O=W.parent/'outputs/CAD-v5-8개-원본대조';O.mkdir(exist_ok=True)
p=json.loads((W.parent/'outputs/CAD-벽공리-v5/office-1F/plan.json').read_text(encoding='utf8'))
rows=[
 ('D6','01 · D6 — 방풍실 외부 문',(14040,-1796,14051,-1789),['D6'],
 '원본의 왼쪽·오른쪽 양개문과 방풍실 형태가 확인됩니다. D6을 외기↔외기로 읽은 현재 결과는 잘못된 연결입니다. 오른쪽 정상 문과 같은 경계에 있는 실제 문으로 유지하고, R32 방풍실 경계와 개구부 형상을 함께 보정해야 합니다.',
 '원본 대조로 확인. 최종 R32 연결은 경계 재추출 후 검증 필요.'),
 ('D13','02 · D13 — R21 / R25 사이 문',(14005,-1787,14012,-1780),['D13'],
 '원본에서 세로 벽의 끊긴 구간과 문 호가 확인됩니다. 현재 코드는 반원의 가운데 방향을 닫힌 문짝 방향으로 선택해 가로 개구부로 만들었습니다. 실제 문이 놓이는 세로 방향으로 보정하고 R21↔R25를 검사해야 합니다.',
 '문과 벽 방향 오인식 확인. 반원 호만으로 양방향 문을 결정하는 규칙의 한계.'),
 ('hall','03·04·07 — 다목적실 전체',(14048,-1778,14069,-1757),['D16','D18','W76'],
 '원본 명칭은 다목적실입니다. 반복 좌석과 동심 단차선이 있으며, 이를 실을 나누는 벽으로 쓰면 안 됩니다. D18에는 좌우에 대응하는 DOOR 레이어의 문 기호가 있습니다. 오른쪽 D18의 방향과 주변 경계가 현재 모델에서 잘못 연결됩니다. W76·D16 쪽에는 평행선과 90도 호가 원본 WID 레이어에 실제로 있고 같은 위치에 중복 작도돼 있습니다. 문·창인지 단차·마감 상세인지는 평면만으로 확정하기 어렵습니다. 좌우 대칭은 벽 누락 검사의 보조 근거이며 높이·용도를 확정하는 근거는 아닙니다.',
 '다목적실·좌석·단차와 D18의 대응 문 기호 확인. W76·D16 비개구부 확정은 보류.'),
 ('W62','05 · W62 — 외부 부속 선',(14005,-1795,14010,-1789),['W62'],
 '외부의 사각 부속 형상 가장자리를 창으로 잡았습니다. 현재 후보 양쪽이 모두 외기이고 실내 경계를 나누지 않습니다. 건물의 연기 유동 개구부 후보에서 제외하는 방향이 타당합니다. 다만 D6도 현재 계산 결과는 외기↔외기이므로, 결과의 sides 값만으로 일괄 삭제하면 실제 문까지 잃습니다.',
 '외부 위치 및 실내 구획 경계 부재 확인. 부속물의 정확한 종류는 미확정.'),
 ('W65','06 · W65 — 연속 벽면의 선',(14003,-1779,14008,-1772),['W65'],
 '연속된 벽과 기둥 옆에 놓인 길고 얇은 선을 창 후보로 잡았습니다. 문짝 호나 벽을 관통하는 끊김은 이 위치에서 확인되지 않습니다. 개구부에서 제외하고 벽은 유지하는 쪽이 타당합니다.',
 '벽면 부착 선의 창 오인식 가능성이 높음. 벽을 삭제하거나 새 구멍을 내지 않음.'),
 ('W89','08 · W89 — 기둥 하부 반복 빗살선',(13989,-1784,13997,-1778),['W89'],
 '후보 위치에는 기둥 외곽을 따라 반복되는 빗살형 선이 있습니다. 해당 선이 4WID 레이어에 있어 창 후보로 포함됐습니다. 원본 주변에는 선홈통 및 하역장 데크끝선 표기도 있습니다. 틈 메우기만의 문제로 보기보다 배수·그레이팅 또는 데크 상세 계열의 선을 창으로 해석한 문제를 먼저 처리해야 합니다. 구체적인 부재 명칭은 평면만으로 확정하지 않았습니다.',
 '4WID 반복 빗살선과 후보 겹침 확인. 창 후보 제외 후 실제 벽 끝의 틈 여부를 별도 검사.')]
cards=[]
for name,title,bounds,ids,note,status in rows:
 x0,y0,x1,y1=bounds;scale=min(1900/(x1-x0),1400/(y1-y0))
 def pix(pt):return (round((pt[0]-x0)*scale)+20,round((y1-pt[1])*scale)+20)
 src=np.fromfile(str(W/f'raw8-{name}.png'),np.uint8);im=cv2.imdecode(src,cv2.IMREAD_COLOR)
 for opening in p['openings']:
  if opening['id'] not in ids:continue
  pts=np.array([q for poly in opening['polys'] for q in poly]);a=pix((pts[:,0].min()-.12,pts[:,1].max()+.12));b=pix((pts[:,0].max()+.12,pts[:,1].min()-.12))
  cv2.rectangle(im,a,b,(20,20,230),3)
  cv2.putText(im,opening['id'],(a[0],max(22,a[1]-9)),cv2.FONT_HERSHEY_SIMPLEX,.8,(0,0,220),2,cv2.LINE_AA)
 cv2.imencode('.png',im)[1].tofile(str(O/f'{name}.png'))
 cards.append(f'<article id="{name}"><h2>{title}</h2><p>{note}</p><p class="status">{status}</p><a href="{name}.png"><img src="{name}.png" alt="{title} 원본 CAD 선과 현재 후보 위치" loading="lazy"></a></article>')
page='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>업무시설 1층 · 남은 8개 원본 대조</title><style>
body{margin:0;background:#f1f4f7;color:#233143;font:17px/1.75 system-ui,'Malgun Gothic',sans-serif}header,main{max-width:1180px;margin:auto;padding:24px}article{background:white;padding:24px;margin:22px 0;border:1px solid #d6dde5;border-radius:10px}h1{font-size:28px}h2{font-size:23px}img{width:100%;max-height:1000px;object-fit:contain;border:1px solid #ddd}a{color:#1264aa}.status{padding:12px;background:#fff3d8}nav a{display:inline-block;padding:8px 14px;background:white;margin:4px;border-radius:5px}.note{border-left:4px solid #b54d12;padding:12px;background:#fff6ed}
</style><header><h1>업무시설 1층 · 남은 8개 원본 대조</h1><p>v5의 후보 위치를 원본 DXF의 전체 선과 대조했습니다. 빨간 사각형은 현재 추출된 개구부 위치입니다. 선 색상은 검토용이며 원본 CAD 색상과 다릅니다.</p><p class="note">이 페이지는 원본 대조와 수정 방향의 검토 결과입니다. 추출 코드, v5 평면·3D·시뮬레이션 데이터는 변경하지 않았습니다. 이 8개 검토가 나머지 모든 문·창의 정확성을 보증하지 않습니다.</p><nav>__NAV__</nav><p><a href="../CAD-벽공리-v5/office-1F/index.html">기존 v5 결과</a> · <a href="판정근거.json">판정 근거</a></p></header><main>__CARDS__</main></html>'''
page=page.replace('__NAV__',''.join(f'<a href="#{r[0]}">{r[0]}</a>' for r in rows)).replace('__CARDS__',''.join(cards))
(O/'index.html').write_text(page,encoding='utf8')
(O/'판정근거.json').write_text(json.dumps(dict(source_sha256=p['provenance'].get('source_sha256'),scope='원본 대조만 수행; 추출 코드/결과 미변경',items=[dict(group=r[0],ids=r[3],bounds_m=r[2],finding=r[4],status=r[5]) for r in rows]),ensure_ascii=False,indent=2),encoding='utf8')
print(O)
