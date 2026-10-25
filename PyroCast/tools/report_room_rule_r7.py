"""Read-only r7 report and audits; never launch CFAST."""
import json,sys,math
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'simulation'))
from pyrocast_cfbt.native import read_native_csv,digest
OUT=ROOT/'simulation/results/room_rule_r7_20261025'
def read(p):return json.loads(p.read_text('utf-8'))
def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2),'utf-8')
def audit(folder,report):
 model=read(folder/'scenario.json');manifest=read(folder/'rule_manifest.json');until=report.get('horizon_s')
 c,_,_=read_native_csv(folder/'case_compartments.csv',until);d,ids,_=read_native_csv(folder/'case_devices.csv',until)
 rooms={r['id']:r for r in model['rooms']};indices={r['id']:i for i,r in enumerate(model['rooms'],1)}
 out=[];t=c['Time']
 for sensor in manifest['sensors']:
  index=indices[sensor['room']];z=sensor['solver_xyz'][2]-rooms[sensor['room']]['origin_m'][2]
  plate=d[next(k for k,v in ids.items() if k.startswith('TRGSURT_') and v.strip()==sensor['id'])]
  gas=d[next(k for k,v in ids.items() if k.startswith('TRGGAST_') and v.strip()==sensor['id'])]
  settings=manifest.get('settings',{})
  threshold=settings.get('cell_temperature_C',300) if sensor.get('sensor_role')=='cell_flame_300' else settings.get('temperature_C',600)
  hits=np.flatnonzero(plate>threshold);j=int(hits[0]) if len(hits) else None
  upper=c[f'ULT_{index}'];single_zone=rooms[sensor['room']].get('shaft',False)
  lower=np.zeros(len(t),dtype=bool) if single_zone else c[f'HGT_{index}']>z
  layer=upper if single_zone else np.where(lower,c[f'LLT_{index}'],upper)
  out.append({'id':sensor['id'],'room':sensor['room'],'quality':sensor.get('sensor_quality'),'threshold_C':threshold,
   'sensor_max_C':float(max(plate)),'upper_max_C':float(max(upper)),
   'single_zone_shaft':single_zone,'max_abs_gas_minus_layer_C':float(max(abs(gas-layer))),
   'first_exceedance_sample':None if j is None else {'time_s':float(t[j]),'plate_C':float(plate[j]),'upper_C':float(upper[j]),'lower_layer':None if single_zone else bool(lower[j])}})
 save(folder/'sensor-audit.json',out)
 mapping={r['cell']:r for r in report['rows']};generations=[]
 for row in report['rows']:
  parent=row['parent'];rid=row['cell'];cursor=rid;seen=[]
  while True:
   if cursor in mapping:
    original=rooms[cursor]['parent_room']
    if not seen or seen[-1]!=original:seen.append(original)
   p=manifest['parents'].get(cursor)
   if not p:break
   cursor=p['room']
  generations.append({**row,'assumed_original_room_generation':max(0,len(seen)-1),
    'ancestry_original_rooms':list(reversed(seen)),
    'note':'static graph ancestry, not proof that a parent fire physically caused downstream ignition'})
 save(folder/'generation-table.json',generations)
 # Numerical input energy accounting; native oxygen limitation is not re-applied here.
 budgets=[]
 for group in model['fuel_groups']:
  curve=group['room_rule_curve'];integral=float(np.trapezoid(curve['q'],curve['t']))/1000
  budgets.append({'group':group['id'],'allocated_MJ':group['energy_MJ'],'potential_curve_MJ':integral,
   'zero_cap_unreleased_budget':max(curve['q'])==0,'difference_MJ':integral-group['energy_MJ']})
 save(folder/'energy-audit.json',budgets)
 return out,generations,budgets

def main():
 b=read(OUT/'B/verification.json');comparison=read(OUT/'C/comparison.json');manifest=read(OUT/'C/rule_manifest.json')
 lines=['r7 실 단위 전이 규칙 — 구현 및 고정 입력 시험 (2026-10-25)','',
  '순정 CFAST 7.7.7, 엔진·솔버·출력격자 무수정. 엔진 SHA256 '+digest(ROOT/'simulation/build/baseline/cfast-baseline.exe'),
  '0. 50MW 출처: SOURCE scenario.json의 최초 peak_kW와 demonstration.primary_peak_kW가 모두50000. 생성기 tools/run_floor_spread_scenario.py:21 기본값, :47 직접 대입. 합산 오류 아님.',
  '분할 전 최초입력50MW는 시작셀 수치상한31.274MW를 초과. 분할후16.667MW는 이 상한보다 낮음. 초기곡선 추가클램프 없이 면적분할만 적용.',
  'r6에서 이 전체 곡선과 연료를 최초 셀 한 곳에 남긴 처리 수정. r7은 원래 R2의3셀에 각각1/3 예산. 최초 셀 peak16666.67kW, 에너지195044.28MJ. 다른2셀은 독립 대기 화원.',
  'room_involvement에서는 R2 형제2셀 공급이 각28.173MW로 정해져 시작셀16.667MW와 합계73.013MW의 잠재공급상한. 최초실 총 에너지 보존과 총 peak50MW 보존은 다름. item_peak는각16.667MW로합계50MW. 이는 실제동시발열과도구분한다.',
  '기존 fuel_area_m2가 있으면 바닥 대비 피복률로 재사용, coverage_fraction 명시 우선, 둘다 없으면0.5. 결과에 맞춘 재조정 없음.',
  '일반 전이: T4b600C. 같은실 셀: 화원 위 강판300C와 중심거리/0.05m/s. 기본 상승60초. 이 값은 전이가정이며 FO예측값 아님.',
  '통과공간도 T4b를 갖지만 화원은 없음. 바로 인접 통과공간의600C 조건을 참조하며 복도를 건너뛰지 않음. 무연료 셀 경계에는 화원위300C판을 만들지 않고600C센서를 참조.',
  '셀 거리는 기존 직사각형 계산 구획의 중심간 거리. 불규칙 CAD 실을 그대로 복원한 수평 화염해석이 아님.',
  '불확실 센서: '+', '.join(manifest['fallback_sensors'])+'; r6a 높이의 가장 먼 모서리 유지, 국부 가열이 판정에 영향을 줄 수 있음.',
  '엔진의 조건은 엄격한 초과(>)이며 출력은5초. 사건은 구간/추정으로 표시. 기준과 같은 값에서 발생한다고 재해석하지 않음.',
  '139 Python 검사와 예산/무재시도 회귀검사1건, JS 문법 확인 통과. 기존 방식 보존. r7은 별도 입력 생성기와 실행 도구로 사용.','',
  '1. B 새 실행(기존 CSV 재사용 없음):']
 for name,r in b['cases'].items():
  lines.append(f"{name}: 합격={r['passed']},1200초 완주={r['complete']},계산{r['native_wall_seconds']:.3f}초")
  for row in r['rows'][1:]:lines.append(f"  {row['cell']}: 조건구간{row['trigger_interval_s']},실제발열첫표본{row['first_actual_positive_HRR_s']},최대{row['actual_peak_kW']:.2f}kW,양수연속{row['longest_positive_HRR_s']:.1f}초")
 lines+=['','2. 실제3F: 원30실,40계산셀. 같은 기존 C입력,시간3600초,각실행 예산1800초. baseline은 최초셀만 활성,형제셀도 비활성. 16실은 합격기준 아님.']
 summary={'B_passed':b['passed'],'C_acceptance_passed':comparison.get('room_involvement',{}).get('complete',False),'cases':{},'no_engine_changes':True,'target_16_rooms_required':False}
 for name,r in comparison.items():
  folder=OUT/'C'/name;view=r
  if not r['complete'] and (folder/'partial-analysis.json').exists():view=read(folder/'partial-analysis.json')
  lines.append(f"{name}: 완료={r['complete']},계산시간={r.get('native_wall_seconds')}초,해석시각={view.get('horizon_s',r.get('native_time_s'))},단계수={view.get('total_steps') or (r.get('status_sample_statistics',{}).get('last') or {}).get('steps')} (미완료는 마지막관측값)")
  if not r['complete']:lines.append('  미완료: '+r.get('error',''));lines.append('  부분출력만 분석하며3600초로 보간/완주처리하지 않음.')
  if view.get('rows'):
   sensor,rows,energy=audit(folder,view)
   actual=view['actual_burning_original_rooms'];sustained=view['sustained_60s_original_rooms']
   lines.append(f"  실제발열 원래실 {len(actual)}개(최초포함): "+', '.join(actual))
   lines.append(f"  연속60초 이상 {len(sustained)}개: "+', '.join(sustained))
   lines.append('  세대는 가정 그래프의 연소가능 원래실 경로로 계산하며 같은실 셀은 새 세대로 세지 않음. 통과공간은 연소세대로 세지 않음.')
   for row in rows:
    if not row['parent']:continue
    p=row['parent'];lines.append(f"  G{row['assumed_original_room_generation']} {p['room']} -> {row['cell']}: 조건{row['trigger_interval_s']},지연{row['delay_s']:.2f}s,실제첫발열{row['first_actual_positive_HRR_s']},최대{row['actual_peak_kW']:.2f}kW,연속{row['longest_positive_HRR_s']:.0f}s, {row['status']}")
   lines.append('  복도에서 멈춘 목적실: '+(', '.join(x['cell'] for x in view['passage_stops']) or '없음(이 고정 경로에서 직접 부모가 통과공간인 미충족 목적실 없음)'))
   lines.append('  공급 근거·피복률·HRRPUA·수치상한: rule_manifest.json / analysis.json; 전체 센서: sensor-audit.json; 에너지분배: energy-audit.json')
   summary['cases'][name]={'complete':r['complete'],'wall_seconds':r.get('native_wall_seconds'),'horizon_s':view.get('horizon_s'),
    'actual_original_rooms':actual,'sustained60_original_rooms':sustained,'passage_stop_rooms':[x['cell'] for x in view['passage_stops']],
    'fallback_sensors':view['fallback_sensors'],'max_assumed_room_generation_burning':max((x['assumed_original_room_generation'] for x in rows if x['actual_peak_kW']>0),default=0)}
  lines.append('  dt 통계: '+json.dumps(r.get('status_sample_statistics'),ensure_ascii=False)+'; 상태표본 통계이며 전체 단계 통계 아님.')
 discarded=OUT/'C/room_involvement_watchdog90_aborted/discarded-attempt.json'
 if discarded.exists():
  discarded_data=read(discarded)
  summary['discarded_runner_attempt']=discarded_data
  lines+=['','실행기 정정 이력: 첫 room_involvement 실행은 legacy90초 출력진전 감시가 남아있어676.469초/1020초에서조기중단. 요청한30분 시험이 아니므로 별도보존.',
   'stall_timeout_s=0으로 정정. 엔진·덱은 동일(바이트확인). 기준계산 재사용, 정정한1800초 실행과 item_peak 비교는 각1회. 위 비교시간과 별도로 조기중단시도676.469초의 작업비용을 포함해야 함.']
 summary['native_wall_total_including_discarded_s']=sum(v.get('native_wall_seconds') or 0 for v in comparison.values())+sum(v['native_wall_seconds'] for v in b['cases'].values())+(read(discarded)['wall_seconds'] if discarded.exists() else 0)
 lines+=['','해석 한계:',
  '- 기존 r6a baseline943.828초(50MW)와 r7 baseline은 공급곡선 크기가 달라 동등정확도 가속률 비교가 아님. 원본50MW 비용 비중은 별도 프로파일링하지 않음.',
  '- 이전 C는3240초에 예산중단, 안전출력3230초에서9실. 최종1시간 결과가 아니므로 r7 완료결과와 같은 시각 비교는 별도 읽기분석이 필요.',
  '- 수치공급상한은 실별 실제 산소 공급한계가 아님. 잔여 미연가스와 FGI/개구부연소 조건에 영향. 추가연소는OFF; 순정 산소제한은 그대로.',
  '- item_peak에서 실간 경로의 출발센서 PC_R2_C1 최고589.773C<600C라 다른실 착화없음. 그셀 상층최고600.042C로 대용판과약10.269C차이. C0/C2판은600C초과했어도 단일선정경로의 C1조건을 대체하지 않음. T4b는 상층온도를 직접 판정하는 기능이 아님.',
  '- 정적 Dijkstra 단일부모의 한계: room_involvement의 R1_C2는 같은실C4 대신외부R4를부모로선택. R4센서약188C로미달하여R1내부활성셀C4가있어도다른경로는평가하지않음. 셀간300C가모든인접경로의OR가아님. 이를 바꾸려면 다음 설계결정 필요.',
  '- 300C 화원위 판도 이웃에서 들어온 열로 가열될 수 있다. 실제 부모화원연소를 확인하는 논리 AND는 순정타깃에 추가하지 않음.',
  '- 이 C 입력에 수직개구부는 없음. 전층/외벽 수직전파의 검증으로 해석하지 않음.',
  '- 3D 재생 패키지와 뷰어에 fallback 판정불확실 전달/표시 지원 추가. 운영 화면의 기존 계산결과는 자동 교체하지 않음. r7은 시험결과 JSON/보고서로 분리.',
  '- 자동재시도/임계값 튜닝/기존 방식 삭제 없음.']
 save(OUT/'final_summary.json',summary)
 (ROOT/'specs/실단위규칙-r7-구현시험결과-20261025.txt').write_text('\n'.join(lines)+'\n','utf-8')
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
