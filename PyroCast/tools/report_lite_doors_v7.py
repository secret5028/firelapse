"""v7 stage 2 only: classify openings and report, no scoring or integration."""
import json,hashlib,sys
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'simulation'))
from pyrocast_lite.door_classification import classify_doors
OUT=ROOT/'simulation/results/lite_v7_door_reclassification_20261025'
def read(p):return json.loads(p.read_text('utf-8'))
raw=read(ROOT/'simulation/results/room_rule_r8_20261025/source-scenario.json')
saved=ROOT/'simulation/config/lite-door-overrides.json'
overrides=read(saved) if saved.exists() else {}
classified,report=classify_doors(raw,overrides)
before={r['id']:r for r in read(OUT/'before.json')['rows']}
def label(r):return '방화(확정)' if r['door_class']=='fire' and r['confidence']=='confirmed' else '방화(추정)' if r['door_class']=='fire' and r['confidence']=='inferred' else {'ordinary':'일반문','external':'외기문'}.get(r['door_class'],r['door_class']+' 사용자정정')
def short(s):return s.replace('CAD_3F_','')
report['scope']='v7 8.1 stage2: section5 area/core classification only'
report['counts_before']=dict(Counter(label(r) for r in before.values()))
report['counts_after']=dict(Counter(label(r) for r in report['rows']))
report['room2_doors']=[r['id'] for r in report['rows'] if 'CAD_3F_R2' in (r['a'],r['b'])]
report['not_executed']=['stage3 candidate scores','stage3 two-state simulations','door jet','MC','opened-fire-door graph change']
paths=read(OUT/'preserved-sha256.json')
report['preserved_files_verified']=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha for p,sha in paths.items())
assert report['preserved_files_verified']
lines=['v7 8.1절 2단계 — 방화문 재분류 보고 / 2026-10-25',
'명세: specs/Claude명세-확정상태-v7-20261025.md (18611 bytes). 5절 면적·코어 조건만 적용.',
'①·② 후보 점수/순위 재산출, 시뮬레이션, MC 실행 없음. 엔진/정밀 r8/기존 v6 결과 불변.',
'이전: '+str(report['counts_before']), '재분류: '+str(report['counts_after']), '',
'문 | 연결 실 | 이전 → 이후 | 근거', '--- | --- | --- | ---']
for row in report['rows']:
 old=before[row['id']];row['previous']={k:old[k] for k in ('door_class','rule','confidence','reason')}
 row['changed']=label(row)!=label(old)
 reason=row['reason']
 if row['rule']==6:
  rejected=[f"{short(v['room'])} {v['area_m2']:.2f}㎡ >80㎡" for v in row['core_checks'] if v['area_m2'] is not None and not v['area_ok'] and (v['core_kind_match'] or v['leading_core_token'])]
  if rejected:reason+='; 코어 규칙 제외: '+', '.join(rejected)
 lines.append(f"{short(row['id'])} | {short(row['a'])} ↔ {short(row['b'])} | {label(old)} → {label(row)} | 규칙{row['rule']}: {reason.replace('CAD_3F_','')}")
lines += ['', '명세 예상과 실제 입력의 차이',
'- R2=325.0738㎡: 이름 첫 부분 ELEV.홀이 맞아도 면적 조건에서 제외. R2의 코어 토큰만으로 방화문을 확정하지 않는다.',
'- R4=82.90207㎡: 80㎡를 초과하므로 역시 규칙2 제외. 명세의 예상 결과에 R4 코어가 언급돼 있지만 수치 조건을 우선했으며 예외/반올림으로 끼워 맞추지 않았다.',
'- R15=27.26216㎡: ELEV.홀 선두 토큰으로 규칙2 충족. R12·R21은 stair, R18은 elev 코어로 면적 조건 충족.',
'- R2 연결 9문: D3은 반대쪽 R12 계단으로 확정 유지. W26/TPS·W27/EPS는 규칙3 추정. D7,D8,D10,D12,D13,D14는 일반문.',
'', '구현 해석/한계',
'- 규칙2는 (실 면적<=80㎡) AND (설정의 core_kind OR 이름 선두 코어 키워드). 80㎡ 경계 포함, 큰 코어도 면적 조건을 우회하지 못한다.',
'- 이름 뒤쪽에 섞인 코어 단어는 불인정. ELEV.홀/비상용 승강기처럼 띄어쓰기가 가능한 코어 명칭은 한 선두 키워드로 읽는다. 코드 목록과 정규식은 설정 파일에 기록했다.',
'- core_kind: stair, stair_lobby, elevator_lobby, elev, elevator, emergency_elevator. 일반 shaft는 규칙2에 포함하지 않고 EPS/TPS/PS는 기존 규칙3.',
'- 문 자체의 명시 도면 기호(규칙1)는 면적 조건보다 우선. 실 OCR의 단독 화/갑을 문별 방화 증거로 새로 승격하지 않는다.',
'- 사용자 저장 정정이 있으면 최우선(이번 입력은 없음). 반복 분류 시 이전 자동 fire_door 플래그가 도면 명시로 오인되지 않게 출처를 구분한다.',
'- 확정은 프로젝트 규칙상 분류이며 실제 내화성능·법규 적합성 확인이 아니다. 방화문 표지는 누락될 수 있다.',
'- 열린 방화문 전이 간선 변경은 이번 면적/토큰 재분류와 별개라 미적용. 기존 정밀 r8 그래프 불변. 후속 계산 전에 적용 범위를 확인할 것.',
'- 기존 ① 점수와 v6 결과는 이력으로 보존한다. v7 점수 구현/극단2상태 비교로 진행하지 않았다.',
'', '검증',
'- 관련 검사 11건 통과: 80㎡ 경계, 큰 코어 차단, 선두 토큰, 반대측 코어, 명시기호/사용자 우선, 반복 분류 안정성.',
f"- 원본 입력·명세·정밀 Python 소스·기존 v6 JSON {len(paths)}파일 SHA256 동일: {report['preserved_files_verified']}",
'- 분류 후 모델은 별도 classified-source.json에 저장. 원래 입력/완료 결과 덮어쓰기 없음.',
'- 2단계 완료 후 정지.']
for name,value in [('after.json',report),('classified-source.json',classified)]:
 (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf-8')
text='\n'.join(lines)+'\n';(ROOT/'specs/간략엔진-v7-방화문재분류-문별보고-20261025.txt').write_text(text,'utf-8')
print(text)
