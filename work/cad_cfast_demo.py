"""Reproducible, explicitly assumed 3F demonstration; does not alter CAD geometry."""
from pathlib import Path
import csv, hashlib, json, math, subprocess, time

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'outputs/CAD-온도연기-v16'
SOURCE = Path('C:/Users/<user>/Desktop/소방 크로키 업-로컬웹앱/data/d018b4bb75da4475b1fd75447603c1a0/cad-output/building.json')
OUT.mkdir(exist_ok=True)
raw = SOURCE.read_bytes()
b = json.loads(raw)
f = next(x for x in b['floors'] if x['name'] == '3F')
rooms = [r for r in f['rooms'] if 'outdoor' not in r.get('tags', [])]
ids = {r['id'] for r in rooms}
height = f['h']
fire_id = 'R9'
connections = []
for c in f['simulation_graph']['connections']:
    a, z = c['sides']
    if a not in ids or z not in ids | {'out'} or a == z:
        continue
    # Closed windows/elevator doors are solid boundaries in this demonstration.
    if c['kind'] != 'door':
        continue
    connections.append(c)
lines = ["&HEAD VERSION=7500, TITLE='CAD 3F assumed demonstration' /",
         '&TIME SIMULATION=601 PRINT=60 SMOKEVIEW=5 SPREADSHEET=5 /',
         '&INIT PRESSURE=101325 RELATIVE_HUMIDITY=50 INTERIOR_TEMPERATURE=20 EXTERIOR_TEMPERATURE=20 /',
         "&MATL ID='CONCRETE' MATERIAL='Assumed normal weight concrete' CONDUCTIVITY=1.75 DENSITY=2200 SPECIFIC_HEAT=1 THICKNESS=0.15 EMISSIVITY=0.94 /"]
dims = {}
for i, r in enumerate(rooms):
    w = max(math.sqrt(r['area']), max([c['dimensions']['width_m'] + .2 for c in connections if r['id'] in c['sides']] or [0]))
    d = r['area'] / w
    dims[r['id']] = (w, d)
    lines.append(f"&COMP ID='{r['id']}' WIDTH={w:.8f} DEPTH={d:.8f} HEIGHT={height} ORIGIN={i*50},0,{f['z']} CEILING_MATL_ID='CONCRETE' WALL_MATL_ID='CONCRETE' FLOOR_MATL_ID='CONCRETE' LEAK_AREA_RATIO=0.00017,0.000052 /")
for c in connections:
    a, z = c['sides']; d = c['dimensions']; frac = .5 if z == 'out' else 1
    lines.append(f"&VENT TYPE='WALL' ID='{c['id']}' COMP_IDS='{a}','{('OUTSIDE' if z == 'out' else z)}' TOP={d['top_m']} BOTTOM={d['bottom_m']} WIDTH={d['width_m']} FACE='FRONT' OFFSET=0 CRITERION='TIME' T=0 F={frac} /")
w, d = dims[fire_id]
lines += [f"&FIRE ID='ExampleFire' COMP_ID='{fire_id}' FIRE_ID='WoodSurrogate' LOCATION={w/2:.5f},{d/2:.5f} /",
          "&CHEM ID='WoodSurrogate' CARBON=6 HYDROGEN=10 OXYGEN=5 HEAT_OF_COMBUSTION=18100 RADIATIVE_FRACTION=0.33 /",
          "&TABL ID='WoodSurrogate' LABELS='TIME','HRR','HEIGHT','AREA','CO_YIELD','SOOT_YIELD' /"]
for t in range(0, 601, 15):
    q = 1000 * min(t/300, 1)**2
    lines.append(f"&TABL ID='WoodSurrogate' DATA={t},{q:.6f},0,1,0.006171682,0.015 /")
lines.append('&TAIL /')
(OUT/'demo.in').write_text('\n'.join(lines), encoding='ascii')
start = time.monotonic()
exe = ROOT/'work/smokeview-demo/firemodels/cfast7/cfast.exe'
run = subprocess.run([str(exe), 'demo'], cwd=OUT, capture_output=True, timeout=180)
elapsed = time.monotonic()-start
log = (run.stdout + run.stderr).decode('utf8', errors='replace')
(OUT/'execution.log').write_text(log, encoding='utf8')
if run.returncode or 'NORMAL EXIT' not in log.upper():
    raise RuntimeError(log[-5000:])
with (OUT/'demo_zone.csv').open() as stream:
    reader = csv.reader(stream); units = next(reader); headers = next(reader)
    values = [dict(zip(headers, map(float, row))) for row in reader if row]
assert len(values) == 121 and values[-1]['Time'] == 600
result = dict(schema='cad-cfast-overlay-v1', engine='CFAST 7.7.7', floor='3F', fire_room=fire_id,
              fire_name='공작실/설비보관실', building_sha256=hashlib.sha256(raw).hexdigest(),
              duration=600, step=5, height=height, elapsed_seconds=round(elapsed, 3),
              assumptions=['예시 화재: 3층 R9 공작실/설비보관실, 5분에 1 MW 도달 후 유지',
                           '일반 실내문 100% 개방, 창·승강기문 닫힘; 소화설비 작동 없음',
                           '초기 20°C, 목재 대리연료·콘크리트 경계 물성은 공식 예제값; 실제 자재 확인값 아님',
                           '3층 실내만 계산; 층간 흐름 제외·수직 경계 닫힘. 테라스는 실외로 제외',
                           '구획 면적·높이·개구부 연결을 사용한 2층 모델. 계산은 등면적 사각형, 표시는 원래 CAD 형상',
                           '색은 구획 평균 온도, 회색 부피는 연기층. 내부 난류·불꽃·특이현상 발생 판정 아님',
                           '미리 계산한 예시 재생: 기존 문·창/화점 편집은 이 결과를 재계산하지 않음'],
              material_source='CFAST 7.7.7 bundled Examples / Users Guide Example Case (Wood_Wall_Fire and CONCRETE)',
              excluded_rooms=[r['id'] for r in f['rooms'] if r['id'] not in ids],
              vents=[dict(id=c['id'], sides=c['sides'], fraction=1) for c in connections], rooms=[])
for i, r in enumerate(rooms, 1):
    series = [[v['Time'], v[f'ULT_{i}'], v[f'LLT_{i}'], v[f'HGT_{i}'], v[f'ULOD_{i}'], v[f'LLOD_{i}']] for v in values]
    assert all(math.isfinite(x) for row in series for x in row)
    assert all(-.001 <= row[3] <= height+.001 for row in series)
    result['rooms'].append(dict(id=r['id'], name=' / '.join(r.get('names',[])[:2]) or r['id'], area=r['area'], series=series))
result['hrr'] = [v['HRR_1'] for v in values]
assert max(r['series'][-1][1] for r in result['rooms']) > 30
(OUT/'cfast-demo.json').write_text(json.dumps(result, ensure_ascii=False, separators=(',',':')), encoding='utf8')
print(json.dumps(dict(seconds=elapsed, rooms=len(rooms), vents=len(connections), frames=len(values), final_fire=next(r['series'][-1] for r in result['rooms'] if r['id']==fire_id)), ensure_ascii=False))
