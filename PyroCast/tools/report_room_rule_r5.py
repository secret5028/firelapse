"""Write the r5 review from saved results only; never launches a simulation."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'simulation'))
from pyrocast_cfbt.native import read_native_csv,digest
OUT=ROOT/'simulation/results/room_rule_r5_20261025'

def fmt(x):return '없음' if x is None else f'{x:.1f}' if isinstance(x,(int,float)) else str(x)
def main():
    sweep=json.loads((OUT/'sweep-comparison.json').read_text('utf-8'))
    comparison=json.loads((OUT/'comparison.json').read_text('utf-8'))
    baseline=OUT/'compare/B1/T4/baseline_native'
    zone=read_native_csv(baseline/'case_compartments.csv',1200)[0]
    devices,ids,_=read_native_csv(baseline/'case_devices.csv',1200)
    key=next(k for k,v in ids.items() if v.strip()=='PC_R1' and k.startswith('TRGSURT_'))
    plate=devices[key];hits=[float(t) for t,v in zip(devices['Time'],plate) if v>600]
    evidence={'B1_baseline_upper_max_C':float(max(zone['ULT_1'])),'B1_baseline_parent_plate_max_C':float(max(plate)),
              'first_plate_above_600_sample_s':hits[0] if hits else None,
              'device_id':'PC_R1','baseline_input_sha256':digest(baseline/'case.in'),
              'interpretation':'Confirmed plate exceeds gas temperature; direct flame radiation explanation inferred from geometry and target source terms, not a radiation-disabled isolation test'}
    (OUT/'B1-T4-negative-control.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),'utf-8')
    lines=['실 단위 규칙 r5 — 9개 입력 스윕 및 T0/T1/T2/T4 비교 (2026-10-25)',
      '범위: 엔진·솔버·출력 5초 격자 유지. 기존 방식 보존. 운영 3D 결과 교체 없음.',
      '이 보고서는 조건과 입력 규칙 비교이며, 실제 착화/FO 시각의 실험 검증이 아니다.', '',
      '1. B2 선정 기준',
      '사용자 답변: 9개 조합 중 상대적으로 늦은 사례. R2만 착화한 사례가 없으면 R2 착화가 가장 늦은 사례를 선택한다. 600초 절대 기준은 사용하지 않는다.',
      'B3는 B2와 구분되는 조합 중 R2/R3 실제 화원 HRR이 각각 60초 이상 양수인 첫 사례(peak, 창 순서)다.',
      'B1 고정 파일 변경 없음: '+str(sweep['B1_sha256_unchanged']), '',
      '2. 기존 T0 방식 9개 스윕',
      'R1 peak/창 | 완주 | R1 최고℃/600℃ 첫 구간 | R2/R3 착화초 | R2/R3 양수HRR 최장초 | 전체 소요초 | 조건 자기일관성']
    for c in sweep['cases']:
        p=c['parameters'];rows=c['rows'];r1,r2,r3=rows
        lines.append(f"{p['R1_peak_kW']}kW/{p['R1_window']} | {c['complete']} | {fmt(r1['upper_C_max'])}/{c.get('R1_600C_bracket_s')} | {fmt(r2['ignition_s'])}/{fmt(r3['ignition_s'])} | {fmt(r2['longest_positive_HRR_s'])}/{fmt(r3['longest_positive_HRR_s'])} | {fmt(c['total_wall_seconds'])} | {c['condition_consistent']}")
    lines+=['선정: '+json.dumps(sweep['selected'],ensure_ascii=False),
      'R1 온도는 최종 전이 계산의 결과이므로 추가 화원의 피드백을 포함한다. 이 최고온도를 초기 화원만 있는 기준 실행의 값으로 읽으면 안 된다.',
      'T0 자기일관성이 False인 경우 착화 일정은 참조값이며 수렴한 물리적 정답이 아니다. B2/B3는 전이가 발생하는 입력 확보 목적이다.', '',
      '3. 12개 비교',
      'T0 기존 Python 판+보충복사/반복. T1 해당 실 대표 연료 타깃. T2 해당 실 천장 강판500℃. T4 출발실 천장 강판600℃+공급 지연60초/성장60초.',
      'B/방식 | 완주 | R2/R3 트리거초 | R2/R3 첫 양수HRR초 | R2/R3 양수HRR 최장초 | 시나리오 native초 | 별도 baseline초 | native 시나리오 실행수 | 재사용수']
    for key,c in comparison['cases'].items():
        rows=c.get('rows',[])
        if len(rows)!=3:
            lines.append(f"{key} | {c.get('complete')} | {c.get('error')}");continue
        r2,r3=rows[1:]
        lines.append(f"{key} | {c['complete']} | {fmt(r2['ignition_s'])}/{fmt(r3['ignition_s'])} | {fmt(r2['first_actual_positive_HRR_s'])}/{fmt(r3['first_actual_positive_HRR_s'])} | {fmt(r2['longest_positive_HRR_s'])}/{fmt(r3['longest_positive_HRR_s'])} | {fmt(c['recorded_native_seconds_excluding_baseline'])} | {fmt(c['baseline_seconds'])} | {c['scenario_runs']} | {c.get('cached_native_jobs',0)}")
        if key.endswith('T4'):
            lines.append('  T4 가정 공급 시작 R2/R3: '+fmt(r2.get('prescribed_supply_start_s'))+'/'+fmt(r3.get('prescribed_supply_start_s'))+'초. 트리거를 실제 연소 시작으로 표시하지 않는다.')
    lines+=['각 analysis.json에 센서 위치/값, 실제 화원 HRR 최대, DJET 최대, 착화 시점 온도·층경계·산소, 단계 수, 입력/엔진 SHA를 저장했다.',
      '시나리오 native 시간은 실제 엔진 실행 측정의 합이다. 재사용된 사례는 원래 측정 시간이며 캐시 읽기 시간을 속도 향상으로 계산하지 않았다. baseline은 별도다.',
      '9개 스윕 도중 정상 종료한 native CSV의 E 생략 지수 표기(예: 8.49-100)를 기존 로더가 읽지 못한 문제를 고쳤다. 원본 CSV를 해시 검증한 뒤 재사용하고, 필요한 후속 회차만 실행했다. 복구 전 결과와 시간을 보존했다.', '',
      '4. 표준 선정 결과',
      '음성 B1에서 미전이, B2/B3에서 두 전이실 각각 실제 HRR>0가 60초 이상인 신규 방식: '+str(comparison['eligible_new_modes']),
      '방식별 합격 항목: '+json.dumps(comparison.get('criteria',{}),ensure_ascii=False),
      f"B1 T4 기준 실행: R1 상층 최고 {evidence['B1_baseline_upper_max_C']:.2f}℃, PC_R1 강판 최고 {evidence['B1_baseline_parent_plate_max_C']:.2f}℃, 판600℃ 초과 첫 표본 {evidence['first_plate_above_600_sample_s']}초.",
      'B1에서 T4가 전이한 것은 음성 대조 조건 위반이다. 강판600℃를 가스600℃ 대용으로 쓴 전제가 성립하지 않았다. 화원 바로 위 아래향 센서가 받는 화염 복사가 원인이라는 해석은 배치·소스 항에 근거한 추론이며 별도 원인 격리 시험은 하지 않았다.',
      '표준은 아직 선택하지 않았다. 합격 후보가 있어도 사용자 승인 전 자동 채택하거나 8실/3F16실 시험으로 확대하지 않는다.', '',
      '5. 소스 확인과 한계',
      'CFAST 7.7.7 radiation.f90:57-99, target.f90:182-196/260-284: 실 내부 화원·벽·가스 복사를 계산하며 확인한 경로에는 실 간 개구부 복사 교환이 없다. 고온 가스 이송과 순정 개구부 연소까지 없다는 뜻은 아니다.',
      'input_namelist.f90:1283-1298 및 fire.f90:1293-1346: 다른 실의 타깃 ID를 FIRE가 참조할 수 있다. 상세 해시와 실행 확인은 stage0-source-audit.json 참조.',
      'T4의 600℃는 1mm 강판의 온도다. 상층 가스600℃, 실제 FO, 이웃 실 첫 연료 착화를 동일시하지 않는다.',
      'T4는 처음 열린 실내 문으로 BFS 부모 하나를 고른다. 다른 경로와 부모 화원의 실제 연소 여부를 추가 조건으로 검사하지 않는다. 연기 유입으로 달궈진 부모 센서도 트리거가 될 수 있다.',
      'r4 공급 상한(외기 우선, 외기 없으면 내부 최대×0.5)은 수치 안정용 가정이다. 연료/산소/열 계산은 순정 CFAST가 맡지만 이 입력 가정의 정확성이 NIST에 의해 검증된 것은 아니다.',
      '입력의 연료·벽체 물성은 프로젝트 기본값이다. 고온 결과의 실제 건물 적합성을 검증한 시험은 아니다.',
      '실제 source HRR>0, 양수 공급이나 HRR0, 개구부 연소를 구분한다. 추가 반응 항은 OFF. T4 전이 사건은 FO 사건 목록에 넣지 않는다.',
      '단일 실행은 외부 재실행을 제거하지만 다화원 산소 제한 구간의 native 계산 비용 자체를 없애지 않는다. 전이 결과가 다르면 소요 시간 차이를 동등 정확도의 가속률로 표현할 수 없다.', '',
      '근거 폴더: '+str(OUT)]
    path=ROOT/'specs/실단위규칙-r5-스윕과T4비교-20261025.txt'
    path.write_text('\n'.join(lines)+'\n','utf-8');print(path)
if __name__=='__main__':main()
