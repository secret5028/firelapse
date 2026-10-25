"""Read-only native output review; never launches or retries a simulation."""
import json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'simulation'))
from pyrocast_cfbt.native import digest,read_native_csv
from report_room_rule_r7 import audit
from run_room_rule_r8 import ranges,save,ENGINE
OUT=ROOT/'simulation/results/room_rule_r8_20261025'
def read(path):return json.loads(path.read_text('utf-8'))

def main():
 result=read(OUT/'comparison.json')
 result['partial_cases']={k:read(OUT/k/'partial-analysis.json') for k,r in result['cases'].items() if not r['complete'] and (OUT/k/'partial-analysis.json').exists()}
 # Display provenance only: the alternate shares these two selected values.
 if 'aggressive' in result['settings']:
  for key in ('coverage_default','vent_cap_k'):
   item=result['settings']['aggressive']['parameters'][key]
   item['source']='comparison_shared'
   item['inherited_source']=result['settings']['selected']['parameters'][key]['source']
  manifest=read(OUT/'aggressive/rule_manifest.json')
  manifest['rule_settings']=result['settings']['aggressive']
  save(OUT/'aggressive/rule_manifest.json',manifest)
 # Refresh display-only range metadata with the explicit incomplete distinction.
 result['ranges']=ranges(result['cases']);save(OUT/'comparison.json',result)
 lines=['실 단위 규칙 r8 동결 구현·시험 결과 (2026-10-25)',
  '결론: '+('두 프리셋 모두 3600초 완주, r8 실행 합격.' if result['complete'] else '미완료 사례가 있어 r8의 두 실행 완주 기준은 불합격.'),
  '엔진/솔버/센서 배치/전이 구조 추가 변경 없음. 기존 방식 보존.',
  '운영 3D 재생은 기존 결과 유지. r8 설정과 비교 요약만 별도 표시.',
  '최초 연소실 포함, 원래 실 ID로 집계. 셀 수/IGN 플래그를 연소 실 수로 세지 않음.',
  '전이 기준은 상층 가스 직접값이 아닌 T4b 판 온도. 모든 범위·프리셋은 프로젝트 가정, NIST 검증 기준이나 확률 아님.',
  '',f"순정 엔진 SHA256: {digest(ENGINE)}",f"전체 묶음 벽시계 시간: {result['wall_seconds']:.3f}초",
  '표준과 공격은 병렬 실행. 개별 계산시간을 합친 값은 전체 대기시간과 다름. 다른 전파 결과를 동등정확도 가속률로 해석하지 않음.']
 summary={'complete':result['complete'],'engine_sha256':digest(ENGINE),'runs':{},'operating_playback_replaced':False,'ranges':result['ranges']}
 base=result['baseline_native'];lines += [f"기준 실행: {base['report']['native_wall_seconds']:.3f}초 / 3600초 완료 / 재사용 여부 {base['cache_hit']}",
  '기준 덱은 최초 화원만 등록. 표준/공격이 동일 기준 실행을 공유. 기존 r7 기준 덱과 달라 새로 1회 실행함.',
  '이후 재사용은 덱·기간·엔진 및 저장 출력 해시가 모두 맞을 때만 가능.']
 verified={}
 for name,report in result['cases'].items():
  folder=OUT/name;settings=result['settings'][name];observed=report
  manifest=read(folder/'rule_manifest.json')
  lines += [f"입력: 원래 {manifest['original_rooms']}실 → {manifest['native_cells']} 계산구획 / 등록 화원 {manifest['registered_sources']}개"]
  if not report['complete'] and (folder/'partial-analysis.json').exists():observed=read(folder/'partial-analysis.json')
  lines += ['',f"[{name} / {settings['preset_label']} / {settings['room_supply']}]",
   f"완료: {report['complete']}; 계산시간: {report.get('native_wall_seconds')}초; 분석 범위: {observed.get('horizon_s')}초",
   f"실제 발열 >0 관측: {observed.get('actual_burning_original_rooms',[])}",
   f"60초 이상 지속: {observed.get('sustained_60s_original_rooms',[])}",
   f"계산 단계: {report.get('total_steps')}; 상태 표본 dt 통계: {report.get('status_sample_statistics')}"]
  if not report['complete']:lines += [str(report.get('error')),'부분 출력은 1시간 완료 결과가 아니며 완전한 비교 범위에 넣지 않음.']
  if 'rows' in observed:
   sensors,generations,budgets=audit(folder,observed)
   active=[r for r in generations if r['first_actual_positive_HRR_s'] is not None]
   lines+=['세대 / 출발셀 → 수신셀(원래실) / 조건 시각 구간 / 지연 / 첫 실제 발열 / 지속시간']
   for row in sorted(active,key=lambda r:r['first_actual_positive_HRR_s']):
    parent=row['parent'];lines += [f"{row['assumed_original_room_generation']} / {parent['room'] if parent else '최초'} → {row['cell']}({row['original_room']}) / {row['trigger_interval_s']} / {row['delay_s']:.3f}s / {row['first_actual_positive_HRR_s']}s / {row['longest_positive_HRR_s']}s"]
   lines+=['세대는 정적 경로를 원래 실 기준으로 압축한 값. 물리적 원인 확정 아님.',f"fallback: {observed.get('fallback_sensors',[])}",f"복도 미가열 정지: {[r['cell'] for r in observed.get('passage_stops',[])]}"]
   summary['runs'][name]={'complete':report['complete'],'wall_seconds':report.get('native_wall_seconds'),
     'horizon_s':observed.get('horizon_s'),'actual_rooms':observed['actual_burning_original_rooms'],
     'sustained_60s_rooms':observed['sustained_60s_original_rooms'],'active_generations':active,
     'max_abs_potential_energy_difference_MJ':max(abs(x['difference_MJ']) for x in budgets)}
  lines+=['실제 적용 설정 (기본값 여부 / 출처):']
  for key,item in settings['parameters'].items():
   lines += [f"- {key}: {item['value']} {item['unit']}; default={item['is_default']}; source={item['source']}; applicable={item['applicable']}"]
  if report['complete']:
   cached=read(folder/'completed.json');checks={f:digest(folder/f)==h for f,h in cached['files'].items()}
   verified[name]={'engine':cached['signature']['engine']==digest(ENGINE),'outputs':checks}
   assert all(checks.values()) and verified[name]['engine']
 old=ROOT/'simulation/results/room_rule_r7_20261025/C/item_peak'
 current=OUT/'selected';same={}
 if result['cases']['selected']['complete']:
  for suffix in ('compartments','devices','vents'):
   a,_,_=read_native_csv(old/f'case_{suffix}.csv');b,_,_=read_native_csv(current/f'case_{suffix}.csv')
   same[suffix]=a.keys()==b.keys() and all(np.array_equal(a[k],b[k],equal_nan=True) for k in a)
  lines += ['',f'기존 r7 item_peak와 표준 r8의 출력 숫자 배열 동일 여부: {same}']
 summary.update(output_hash_verification=verified,standard_vs_r7_numeric_equal=same)
 lines+=['','범위: '+str(result['ranges']['burning_room_count_range']),
  '실별 첫 발열 시각 범위는 comparison.json의 ranges에 저장. 한 사례에서만 탄 실은 해당 사례의 관측값과 다른 사례의 미관측을 병기. 미관측을 0초로 대입하지 않음.',
  '한계: 정적 Dijkstra 부모 경로 하나, 대체 센서의 국부 가열 가능성, 통과 공간 센서 미달 시 전이 정지, 닫힌 일반문 관통 가정 후에도 VENT 닫힘 유지, 수치 공급 상한은 실제 환기 한계가 아님.',
  '이번 입력에는 수직 개구부가 없어 층간 확산 검증이 아님. 임계값 변경·추가 정밀화·자동 재시도 없음.',
  '정밀 모드는 동결. 간략 엔진은 별도 지시 전 구현하지 않음.']
 save(OUT/'final-summary.json',summary)
 (ROOT/'specs/실단위규칙-r8-동결-구현시험결과-20261025.txt').write_text('\n'.join(lines)+'\n','utf-8')
 print(json.dumps({'complete':summary['complete'],'runs':{k:{x:v[x] for x in ('complete','wall_seconds','horizon_s','actual_rooms')} for k,v in summary['runs'].items()},'r7_equal':same},ensure_ascii=False))
if __name__=='__main__':main()
