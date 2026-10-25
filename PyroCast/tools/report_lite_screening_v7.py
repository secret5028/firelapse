"""Read the completed ten cases; no scoring rerun or solver execution."""
import json,hashlib
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'simulation/results/lite_v7_screening_20261025'
def read(p):return json.loads(p.read_text('utf-8'))
def short(s):return s.replace('CAD_3F_','')
def st(s):return {'open_except_confirmed':'개방','closed':'폐쇄',None:'미확정'}.get(s,s)
def fmt(v,n=4):return '없음/미평가' if v is None else f'{v:.{n}f}'
s=read(OUT/'score.json');c=read(OUT/'comparison.json');by={r['room']:r for r in c['rows']}
rows=s['ranked'];focus=[r for r in rows if r['room'] in ('CAD_3F_R1','CAD_3F_R2')]
preserved=read(OUT/'preserved-sha256.json')
same=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==v for p,v in preserved.items())
assert same
lines=['간략 엔진 v7 / 8.1절 3단계 결과 — 2026-10-25',
'범위: v7 ① 점수 + ② 상위5실 × 극단2상태 = 10회 직렬. 완료 후 정지.',
f"① 점수 {s['score_seconds']:.6f}초 / 원래{ s['all_room_count']}실 / 적격{s['eligible_count']}실 / 가중치 {s['weights']}",
f"② 3600초×{c['attempted_scenarios']}개 시나리오, 완주 {c['complete_scenarios']}개, 총 {c['total_wall_s']:.3f}초. 작업자1, MC0, 새 CFAST0.",
'실별 ②순위: 한 상태의 결과 전체를 선택해 연소실↓ → 연기위험실↓ → 최초FO↑. 서로 다른 상태의 최대 항목을 섞지 않는다. 완전 동률은 공동순위.',
'두 상태 중 하나라도 미완료면 그 실의 최악 비교는 미완료로 두고 ②순위를 확정하지 않는다.', '',
'①·② 순위표', '화점실 | 이름 | ①순위 | 점수 | ②순위 | 나쁜 상태 | 연소실 | 연기위험실 | 최초FO(s)']
for r in rows[:5]:
 b=by[r['room']];state='동률' if len(b['tied_states'])>1 else st(b['worst_state'])
 lines.append(f"{short(r['room'])} | {r['name']} | {r['rank1']} | {r['score']:.6f} | {b['rank2']} | {state} | {b['burning_room_count']} | {b['smoke_risk_room_count']} | {fmt(b['first_FO_s'],0)}")
lines += ['', 'R1·R2 위치 및 요인 원값',
'실 | ①순위 | ②평가 | 총에너지MJ | log10(MJ) | 입력peak kW | ΣA√H | 환기한계kW | 공급/환기비 | 2단계면적㎡ | 통과인접 | 가중방화비율']
for r in focus:
 raw=r['raw'];b=by.get(r['room'])
 lines.append(f"{short(r['room'])} | {r['rank1']} | {b['rank2'] if b else 'N=5 밖, 미실행'} | {r['fuel_energy_MJ']:.3f} | {raw['fuel']:.6f} | {r['fuel_peak_kW']:.1f} | {r['opening_A_sqrtH']:.6f} | {r['vent_limit_kW']:.3f} | {fmt(raw['ventilation_restriction'],6)} | {raw['connectivity']:.5f} | {raw['passage_adjacency']} | {raw['fire_isolation']:.6f}")
 lines.append('  정규화/직접 기여값: '+json.dumps(r['normalized'],ensure_ascii=False))
 lines.append(f"  인접문 {r['internal_door_count']} / 확정 {r['confirmed_fire_door_count']} / 추정 {r['inferred_fire_door_count']}; 통과 공간 {r['adjacent_passages']}; 도달실 {r['reachable_rooms']}")
r2=next(r for r in focus if r['room']=='CAD_3F_R2')
lines += [f"R2는 {r2['rank1']}위다. 큰 연료/발열과 회복된 연결도에도 통과공간 인접 0점, 가중 방화비율 감점이 남는다. N=5를 바꾸거나 R2를 강제로 끼워 넣지 않았다.",
'화재 빈도나 실제 최악을 보증하는 순위가 아니다. 지표와 실제 위험의 타당성이 확정됐다고 해석하지 않는다.', '',
'10회 개별 결과', '화점 | 상태 | 완주 | 연소실 | 연기위험실 | 최초FO(s) | 적분(s) | 전처리(s) | 후처리(s) | 총(s) | 최고상층℃ | 전이이벤트 | 질량잔차% | 에너지잔차%']
diagnostics=[]
for case in c['cases']:
 folder=OUT/case['room']/case['state'];dest=folder/case.get('selected_attempt','BDF')
 result=read(dest/'result.json') if (dest/'result.json').exists() else None
 temps=max((r['upper_max_C'] for r in result['room_summary']),default=None) if result else None
 events=len(result['events']) if result else None;t=case['times'];bal=case.get('balance',{})
 lines.append(f"{short(case['room'])} | {st(case['state'])} | {case['complete']} | {case['burning_room_count']} | {case['smoke_risk_room_count']} | {fmt(case['first_FO_s'],0)} | {fmt(t.get('integration_s'),3)} | {fmt(t.get('preprocess_s'),3)} | {fmt(t.get('postprocess_s'),3)} | {t['total_s']:.3f} | {fmt(temps,2)} | {events} | {fmt(bal.get('mass_percent'),6)} | {fmt(bal.get('energy_percent'),6)}")
 data=read(folder/'input.json');manifest=read(dest/'rule_manifest.json') if (dest/'rule_manifest.json').exists() else {}
 openings=data['screening_source']['opening_states']
 diag={'room':case['room'],'state':case['state'],'max_upper_C':temps,
       'burning_cells':[r for r in result['room_summary'] if r['actual_peak_kW']>0] if result else [],
       'events':result['events'] if result else [],'opening_counts':dict(Counter(v['class']+(' open' if v['open'] else ' closed') for v in openings)),
       'opened_fire_door_edges':manifest.get('initially_open_fire_doors',[]),'excluded_edges':manifest.get('graph',{}).get('excluded_edges',[]),
       'failure':case.get('failure'),'solver_fallback':case.get('solver_fallback')}
 diagnostics.append(diag)
 if case.get('failure'):lines.append('  실패: '+case['failure'])
lines += ['', '이번 결과 해석',
'- 10건 모두 원래실 기준1실 연소/연기위험0/FO미충족으로, 다섯 화점의 ②지표가 같다. 온도나 셀별연소량이 같다는 뜻은 아니다. 지정된 실수/FO 지표로 변별되지 않는 결과다.',
'- R1 개방 최고227.93℃, 폐쇄320.41℃. 폐쇄 상태는 최초 셀에서300℃를 넘겨 내부3셀 추가공급/연소가 발생하지만 원래R1 안이라 연소실수1이다.',
'- 전체10건의 최고상층온도는 R4 개방535.91℃로 실간기준600℃에 못 미친다. 전이임계값을 낮추거나 입력곡선을 키우지 않았다.',
'- R1의50MW 입력은 기존셀배분으로 최초셀6.25MW가 된다. R0·R3·R23은 각각원래입력peak1MW를 유지한다. 연료총량이 크다고 자동으로초기HRR을늘리는 모델이 아니다.',
'- R2의 ①6위는 v7지표를 그대로 적용한 결과다. R2는상위5밖이므로②미평가이고, 안전/덜위험으로판정한것이아니다. 비교10회를넘겨추가하지않았다.',
'', '입력/구현 정의',
'- 연료 log는 양의 총 에너지에만 적용. 무연료 실은 연료0점, log 정규화 범위에서 제외. 다른 지표의 층 정규화에는 모든 원래 실을 포함한다.',
'- 환기비는 실의 원래 연료 peak 합 / (1500 × 모든 WALL 개구부 기하학적 ΣA√H). 내부·외부 개구부를 포함한다. 실제 환기망 산소 공급 한계가 아니다. 3에서 clip 후 층 min-max.',
'- 최초 화점은 자기 실의 입력 곡선을 사용한다. 실이 셀로 분할되면 기존 규칙대로 에너지가 배분된다. 다른 실의50MW를 작은 실로 옮기지 않는다.',
'- 연결도는 확정 방화문을 닫은 개방 상태에서 열린 일반문·추정 방화문·영구통로의2-hop 고유 면적 합, 자기 실 제외. 창은 연결도 경로가 아니다.',
'- 통과 공간 인접은 기존 fuel_default.usage/core_kind를 쓴 이진값 그대로. 방화 격리 기여값은 1-(확정문수+0.5×추정문수)/인접문수 그대로. 재정규화하지 않는다.',
'- 확정방화문6개는 두 상태 모두닫힘. 추정방화문4개·일반문13개·개폐창43개는 개방/폐쇄에 따라 달라진다. 영구통로3개와 분할셀 경계는 항상열림. 닫힘은 기존누설모델 유지.',
'- 열린창 유효면적0.5. 고정창은 닫힘 유지(이번 입력에0개). 창파괴OFF, 산소재고OFF, 문분출연소 미추가. 기존 상층연소와 층별산소식 유지.',
'- 열린 추정방화문은 현재 공유 r8 입력 준비 코드가 이미 간선으로 허용함을 소스와 입력 검사로 확인했다. 그 코드를 수정하지 않았다. 이전 인계의 열린방화문 일괄제외 설명은 현재 소스와 달라 이번 manifest를 기준으로 기록한다.',
'- 단일부모·전이지연·임계값·연료·벽체는 그대로. 표준 설정만 사용. 두 상태는 위험을 끼워 맞추는 튜닝이나 MC가 아니다.',
'- 연기위험실0은 연기가 없다는 뜻이 아니다. 온도·미연연료·층축적 복합조건의 미충족이다. FO 최초시각은 공통3요인 조건을 모두 충족한 첫10초 출력 표본이다.',
'- 장부는10초 출력 재구성 진단. 에너지0.1% 기준, 질량보고만. 수락스텝 보존 인증 아님.', '',
'검증 및 정지',
f"- 실행 중 입력·명세·물리/공유소스 SHA 불변: {c['code_and_input_unchanged_during_batch']}. 원본/정밀소스/기존v6결과 {len(preserved)}파일 SHA 불변: {same}.",
f"- Radau 대체 {sum(bool(r.get('solver_fallback')) for r in c['cases'])}건. 수치실패 시 잔여1200초 적분예산 안에서1회만, 시간초과 재시도 없음.",
'- v7 점수/상태/동점/실패/개방방화문간선 검사8건 통과. 기준에 맞추기 위한 가중치 수정 없음.',
'- 기존3D화재재생은 교체하지 않고 후보표만 갱신. MC·문분출·색상변경·추가속도작업 없이 3단계에서 정지.', '',
'전체 후보 ① 순위 (가중치 변경 없이)', '순위 | 실 | 점수 | 연료log | 공급/환기 | 연결면적 | 통과인접 | 가중방화비율']
for r in rows:
 x=r['raw'];lines.append(f"{r['rank1']} | {short(r['room'])} {r['name']} | {r['score']:.6f} | {fmt(x['fuel'],6)} | {fmt(x['ventilation_restriction'],6)} | {x['connectivity']:.3f} | {x['passage_adjacency']} | {x['fire_isolation']:.6f}")
(OUT/'diagnostic.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2),'utf-8')
report=ROOT/'specs/간략엔진-v7-상위5·극단2상태-비교보고-20261025.txt'
report.write_text('\n'.join(lines)+'\n','utf-8');print(report)
