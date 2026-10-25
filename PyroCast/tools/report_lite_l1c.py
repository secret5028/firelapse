"""Assemble section 1.3 comparison from saved evidence only."""
from pathlib import Path
import hashlib
import json
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'simulation/results/lite_l1c_20261025'
def read(p):return json.loads(p.read_text('utf-8-sig'))
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
cases={}
for label,stage,preset in [('복사 전 표준','trigger_only','standard'),('복사 후 표준','radiation_on','standard'),('복사 후 공격','radiation_on','aggressive')]:
    folder=OUT/stage/preset;r=read(folder/'result.json');s=read(folder/'summary.json');g=s['gate']
    sustained=sorted({x['original_room'] for x in r['room_summary'] if x['longest_positive_HRR_s']>=60})
    cases[label]={'stage':stage,'preset':preset,'complete':r['ok'],'times':s['times'],
        'burning_original_rooms':g['lite_full_3600'],'burning_cells':sum(x['actual_peak_kW']>0 for x in r['room_summary']),
        'sustained_60s_original_rooms':sustained,'gate':g,
        'first_spread_HRR_sample_s':min((t for room,t in g['lite_full_3600'].items() if room!='CAD_3F_R2'),default=None),
        'settings':r['rule_settings']['values']}
decision=read(OUT/'radiation-decision.json')
audits={stage:read(OUT/stage/'standard/balance-diagnostic.json') for stage in ('trigger_only','radiation_on')}
guard=read(ROOT/'simulation/results/lite_l1_20261025/source-guard.json')
changed=[p for p,h in guard.items() if sha(Path(p))!=h]
assert not changed,changed
manifest_checks={}
for stage,preset in [('trigger_only','standard'),('radiation_on','standard'),('radiation_on','aggressive')]:
    native=ROOT/'simulation/results/room_rule_r8_20261025'/('selected' if preset=='standard' else 'aggressive')/'rule_manifest.json'
    a=read(OUT/stage/preset/'rule_manifest.json');b=read(native)
    manifest_checks[stage+'/'+preset]={k:a[k]==b[k] for k in ('settings','cells','parents','initial_source')}
    assert all(manifest_checks[stage+'/'+preset].values())
source=ROOT/'simulation/vendor/cfast-7.7.7/Source'
verification={'tests_passed':10,'frozen_sources_checked':len(guard),'frozen_sources_changed':changed,
    'manifest_fields_equal':manifest_checks,'native_runs':0,'L3_runs':3,'isolation_runs':2,
    'source_hashes':{f:sha(source/f) for f in ('radiation.f90','prec.f90','input_namelist.f90')},
    'lite_hashes':{p.name:sha(p) for p in (ROOT/'simulation/pyrocast_lite').glob('*.py')}}
save(OUT/'verification.json',verification)
status={'stage':'section_1.3_comparison_complete','L3_standard_before':cases['복사 전 표준']['gate']['passed'],
        'L3_standard_after':cases['복사 후 표준']['gate']['passed'],
        'radiation_candidate_retained':decision['retain_candidate'],'default_gas_radiation_enabled':False,
        'cell_trigger':'upper_layer_temperature/shared cell_temperature_C','L4':'not_certified; sampled diagnostic only',
        'MC':'not_run','operating_3D_changed':False,'native_runs':0,
        'reason':'radiation rollback criteria met; whole-model 0.1% conservation gate not established'}
save(OUT/'status.json',status);save(OUT/'comparison.json',cases)
lines=['간략 엔진 L1c — 최신1.3절 시행·복사 전후 비교 (2026-10-25)',
'결론: 지정 순서의 3F 3회와 단독 2회를 완료했다. 표준 전·후 모두 재정의 L3 관문은 통과했다.',
'그러나 복사 후보는 단독 비교의 악화 조건에 해당하여 기본 OFF로 되돌린다. 셀 상층 트리거 변경은 유지한다.',
'L4 전체 보존 0.1% 합격은 확인하지 못했다. 몬테카를로/운영3D 교체는 수행하지 않았다.',
'', '1. 적용·보존',
'- 1.3.1이 구3절보다 우선: 셀 트리거는 부모 상층>cell_temperature_C(표준300℃). 실간은 상층>temperature_C(표준600℃).',
'- 두 값 모두 r8 rule_settings.resolve에서 가져온다. 공격은 공유 프리셋대로 셀250℃/실간500℃다.',
'- 지연/곡선/부모/공급 상한/셀 분할은 같은 r8 manifest. 판 센서 상태를 만들지 않는다.',
'- 사건은 1회 확정, 현재 상태에서 적분 이어감. 임계값·연료·창 튜닝, native/정밀모드 수정 없음.',
'- BDF/솔버/출력10s 변경 없음. 이번 추가 진단은 물리 RHS를 바꾸지 않는 유출입 장부 출력이다.',
'', '2. 복사 계수 소스 확인 및 구현',
'- radiation.f90:53,87-92: defabsup=0.50 m^-1은 fgasabsorb OFF인 CONSTANT 모드 값.',
'- input_namelist.f90:2609-2610은 CONSTANT일 때 OFF. 기본값은2652의 CALCULATED.',
'- 정상 absorb()는 radiation.f90:921-947에서 CO2/H2O/soot로 계산한다. 따라서0.50을 항상쓰는 범용정답이라고 표현하지 않는다.',
'- radiation.f90:59-63의 Lm=1.8Vu/(A+depth*(width+depth_plan))는 3.6Vu/(2A+perimeter*upper_depth)와 같다.',
'  여기 Au는 상층 체적의 전체 경계면적(층 경계 포함). 벽 교환 접촉면적은 천장+상층 접촉벽만 사용한다.',
'- prec.f90:19 sigma=5.67e-8. eps_g=1-exp(-0.50Lm). 화원복사 중 eps_g 몫→상층, 나머지→벽.',
'- 벽→상층 q=eps_g eps_w sigma (Tw^4-Tu^4) A_contact, 벽 장부는 반대 부호. 하층 가스 복사흡수는 생략.',
'- 중요한 정정: 이전 FiniteWalls.flux에도 gas-wall 복사(hr)가 이미 있었다. 단순히 새 항을 더하면 중복이다.',
'  후보ON에서는 이전 실내 복사항을 제거하고, 대류+새 회색가스 교환으로 대체했다. OFF에서는 이전 식을 그대로 쓴다.',
'- Tw는 기존 1노드 벽체 온도를 표면온도로 대용한다. 형상계수/radiosity/성분별흡수를 구현한 순정 RAD4 복제가 아니다.',
'- 형상/온도/표면물성 외 새 보정계수나 결과 맞춤 튜닝 없음. 기본 gas_radiation_enabled=False.',
'', '3. 단독 비교(최초 화원만1200초, 새CFAST실행0)',
'사례 | CFAST최고℃ | 복사전최고℃/차이% | 복사후최고℃/차이% | 복사후적분초']
for name in ('B2','B3'):
    old=read(ROOT/f'simulation/results/lite_l1b_20261025/isolation/{name}/comparison.json')
    new=read(OUT/f'radiation_on/isolation/{name}/comparison.json')
    lines.append(f"{name} | {new['native_peak_upper_C']:.2f} | {old['lite_peak_upper_C']:.2f}/{old['peak_difference_percent_C']:+.2f}% | {new['lite_peak_upper_C']:.2f}/{new['peak_difference_percent_C']:+.2f}% | {new['wall_seconds']:.3f}")
lines+=['- 차이%는 섭씨 수치 비율이며 에너지비율이 아니다. 양쪽 실제HRR/누적발열은 여전히 반올림오차 수준으로 같다.',
'- 층경계 높이는 비슷하지만 완전히 같지는 않다. 그래프/CSV에 실제 차이를 보존했다.',
'- 악화 평가는 초기0~240초 양의오차 최대, 후기600~1200초 RMS 및1200초 차이를 함께 기록한다.',
'  초기최대 과대가 커지거나 후기 RMS가 줄지 않으면 비채택. 온도 임계값 튜닝과 무관한 비교지표다.',
'사례 | 초기최대 과대℃ 전→후 | 후기 RMS℃ 전→후 | 1200초 오차℃ 전→후 | 판정']
for d in decision['checks']:
    a,b=d['before'],d['after']
    lines.append(f"{d['case']} | {a['initial_max_positive_error_C']:.2f}→{b['initial_max_positive_error_C']:.2f} | {a['late_rms_error_C']:.2f}→{b['late_rms_error_C']:.2f} | {a['at_1200_error_C']:.2f}→{b['at_1200_error_C']:.2f} | 되돌림")
lines+=['- B2 초기과대 악화, B3 후기과소 악화. 원인 후보를 시험한 결과이지 복사항 추가가 항상 개선한다는 근거가 아니다.',
'- 이후 ON 3F 두 건은 사용자 요청의 전후 비교를 완성하기 위한 시험으로만 실행. 기본/운영 모델에 ON을 채택하지 않았다.',
'', '4. 3F 복사 전·후 나란히 비교(시뮬레이션3600초)',
'항목 | 복사 전 표준 | 복사 후 표준 | 복사 후 공격(참고)']
cs=list(cases.values())
for label,vals in [
    ('완료',[str(c['complete']) for c in cs]),
    ('전처리초',[f"{c['times']['preprocess_s']:.3f}" for c in cs]),
    ('적분초',[f"{c['times']['integration_s']:.3f}" for c in cs]),
    ('후처리초',[f"{c['times']['postprocess_s']:.3f}" for c in cs]),
    ('연소 원래실수(HRR>0)',[str(len(c['burning_original_rooms'])) for c in cs]),
    ('60초이상 연속연소 원래실수',[str(len(c['sustained_60s_original_rooms'])) for c in cs]),
    ('연소 셀수',[str(c['burning_cells']) for c in cs]),
    ('최초 다른실 실제발열 표본초',[str(c['first_spread_HRR_sample_s']) for c in cs]),
    ('표준 관문',['통과','통과','합격조건 아님'])]:
    lines.append(label+' | '+' | '.join(vals))
lines+=['- 관문 비교는 native공격의 안전 공통 구간2850초까지로 제한한다. 3600초 결과는 별도로 보고하며 미완료 native를1시간으로 외삽하지 않는다.',
'- 표준합격: native표준 {R2} ⊆ 간략표준 ⊆ native공격 {R2,R1,R6,R7,R8,R9,R11,R23}. 포함실 착화순서도 동일.',
'  동일시각 표본은 동시군으로 처리하며 알파벳순서를 물리적 착화순서로 만들지 않는다(native5s/lite10s).',
'- 원래실은 셀을 합쳐센다. 실제HRR>0과60초지속은 별도 표기. 공급/트리거만 있고 실제HRR0인 실은 연소실에서 제외.',
'- 복사전표준: R2_C1 첫발열510초/C2 570초, C1상층600℃ 통과2042.769초, 다른실공급2102.769초/첫양수표본2110초.',
'- 상층온도만을 쓰므로 부모셀 자체의 연소 전에도 유입열로 다음셀 조건이 충족될 수 있다. 복사전 C2의 부모 C1 상층300℃는394.321초에 통과했으며 C1의 실제첫발열은510초다. C2 공급은지연후568.988초. 지정규칙대로 별도부모연소필수조건은 추가하지 않았다.',
'- 복사후표준: C1 첫발열460초/C2 540초이나 C1상층최고580.00℃로600℃ 미달, 다른실 전이없음.',
'- 복사후공격: 공통실은 native공격보다 이른440초에 전이. R17·R10이 추가로양수HRR을보여10실이며 native8실집합과다름.',
'  R17 최장연속30초, R10_C0 10초로60초지속실은8실이다. 공격시험은 합격조건이아닌 비교용이다.',
'- 이 관문은 사용자 지정 참조 범위 비교이며 NIST 검증·현실예측 정확도 합격을 뜻하지 않는다.',
'', '원래실별 첫 실제HRR 표본(s) | 복사 전 표준 | 복사 후 표준 | 복사 후 공격']
for room in sorted(set().union(*(set(c['burning_original_rooms']) for c in cs))):
    lines.append(room+' | '+' | '.join(str(c['burning_original_rooms'].get(room,'없음')) for c in cs))
lines+=['', '5. 장부검사: 국부 교환 검증과 전체L4 구분',
'- 단위검사10건 통과. 새복사 분배합=원래화원복사, 벽↔상층 양방향열은 반대부호, 평형/영층흡수0 확인.',
'- 전체L4는 저장10초 출력 기반 진단만 수행했다. 솔버 수락스텝 누적유출입 장부가 없어 합격인증하지 않는다.',
'- 재고는 현코드대로 P0/(RT)밀도와 벽노드열용량으로 재구성. 상대잔차 분모=max(초기재고, 누적총유입).',
'- 내부유출입은 상쇄하고 외부유입/유출+열분해질량, 실제발열+열분해현열-벽뒷면열을 독립 비교했다.',
'표준 사례 | 최대누적질량잔차% | 최대누적에너지잔차% | L4']
for stage,label in [('trigger_only','복사전'),('radiation_on','복사후')]:
    a=audits[stage]
    lines.append(f"{label} | {a['mass_max_cumulative_relative_percent']:.6f} | {a['energy_max_cumulative_relative_percent']:.6f} | 합격미확인")
lines+=['- 질량 진단값은0.1%보다크지만10초 출력 적분오차와모델폐쇄식 영향을분리하지않았다. 이를정확한물리오차로단정하지않는다.',
'- 국부 에너지 분배장부 오차는4.5e-8W 이하. 이것만으로 전체질량·에너지보존을통과했다고말하지않는다.',
'- 추가3F 재실행은하지않았다. accepted-step 누적장부가없는현재자료로0.1%를보장하지않고MC를중단한다.',
'', '6. 최종 상태·한계',
'- 유지: 상층온도 셀트리거, 기존 Cd/LOL공유입력. 복사후보는실험옵션으로보관·기본OFF.',
'- 표준 전후L3통과, 복사검증악화로비채택, L4합격미확인. MC20표본미실행, 운영3D교체없음.',
f"- native새실행0. 원본/r8/native {len(guard)}개 SHA불변. 세실행의settings/cells/parents/initial_source는해당r8프리셋과동일.",
'- 비교 보고/그래프는 저장결과를 읽기만 한다. 모든 실행은이미시도한폴더 재실행거부. 자동튜닝·재시도없음.',
'', '7. 파일',
'simulation/results/lite_l1c_20261025/{comparison.json,status.json,verification.json,radiation-decision.json}',
'simulation/results/lite_l1c_20261025/isolation-before-after.png 및.pdf',
'simulation/results/lite_l1c_20261025/trigger_only/standard/{result.json,state.npz,gate.json,balance-diagnostic.json}',
'simulation/results/lite_l1c_20261025/radiation_on/{standard,aggressive,isolation}',
'tools/run_lite_l1c.py: 단계별실행; tools/audit_lite_l1c.py: 저장상태진단; plot_lite_l1c.py/report_lite_l1c.py: 읽기전용.']
path=ROOT/'specs/간략엔진-L1c-셀트리거·복사전후-시험결과-20261025.txt'
path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps(status,ensure_ascii=False,indent=2));print(path)

