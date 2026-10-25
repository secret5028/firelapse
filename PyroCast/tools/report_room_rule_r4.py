"""Rebuild the review report from saved B1 outputs; never runs a simulation."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'simulation/results/room_rule_r4_20261025'

def main():
    r=json.loads((OUT/'comparison.json').read_text('utf-8'))
    lines=['실 단위 규칙 r4 — B1 고정 입력 비교 결과 (2026-10-25)','',
           '결론: T0~T3 모두 1200초 완주. R1만 연소하고 R2·R3는 어느 방식에서도 착화하지 않았다.',
           '표준으로 승인 요청할 합격 방식이 없다. 8실 재실행 비용 시험과 3F16실 시험을 시작하지 않았다.',
           '엔진/솔버/출력 격자를 변경하지 않았으며, 결과에 맞춰 임계값·연료량·높이·창 개방을 추가 변경하지 않았다.','',
           '1. 고정 입력 B1',
           'fixtures/room_rule_benchmark_3room.json SHA256='+r['fixture_sha256'],
           '5×5×2.7m 3실 직렬, 실내문0.9×2.1m 상시 개방, 각 실 외기 창1.8×1.2m/하단0.9m 완전개방. 파괴 없음.',
           'R1 바닥 중앙, fast t²(alpha=0.0469kW/s²), 최대1500kW. 모든 화원 높이0m. 1200초, 출력5초/기존 최대적분간격1초.',
           'R2/R3 연료10000MJ(400MJ/㎡), 공급peak 상한 적용 전5000kW, HRRPUA500kW/㎡, 상승60초. 초기 연료예산도10000MJ로 고정.',
           '미지정 재료/벽체는 기존 정규화 기본값을 사용하고 fixture에 명시적으로 저장. 실제 건물의 측정값이 아니다.',
           '새 공급 상한: 외기 우선 max(A√H), k=1.0. B1에서는3549.24kW. 외기 개구부가 없는 실만 내부최대×0.5. 수치 안정용 가정이며 환기 네트워크의 산소 공급 해가 아니다.',
           'T0도 같은 바닥 화원·공급 곡선·상한을 사용한다. 기존 Python 판/보충열과 외부 반복 구조만 유지한다.',
           'T1은 기존 생성 후보의 첫 항목을 사전 고정했다(R2 x5.5/y2.5/z0.75, R3 x10.5/y2.5/z0.75). 가장 빨리 붙은 미래 후보를 골라 쓰지 않는다.',
           'T2: 실 중앙 천장 아래0.2m, 아래 방향1mm 강판, native 판온도500℃. 상층 가스온도와 동일하지 않다.',
           'T3: 실 중앙 바닥 위0.1m, 위 방향1mm 강판, native 입사열유속15kW/㎡.','',
           '2. 측정 — 실제 시간(초), 단계 수는1200초 출력의native STEPS',
           '방식 | 시나리오 native합 | 기준 native별도 | 총벽시계(기준포함) | 시나리오 실행횟수 | 단계수',]
    for name,c in r['cases'].items():
        runs=c['runs'][1:] if c['baseline_seconds'] else c['runs']
        lines.append(f"{name} | {c['scenario_native_seconds']:.3f} | {c['baseline_seconds']:.3f} | {c['total_wall_seconds']:.3f} | {c['scenario_runs']} | {[x['steps_at_horizon'] for x in runs]}")
    lines+=['T0 기존 방식 / T1 연료 타깃 / T2 천장 강판 / T3 바닥 열유속.',
            '모두600초 실행 예산 내 완료. 새 방식은 시나리오1회+별도stock기준1회다. T0는 추가착화가 없어 native1회뿐이므로 재실행 제거 속도시험이 아니다.','',
            '3. 실별 착화/HRR/지속시간/센서',
            '지속시간은 HRR>0인 양끝 표본 사이 구간만 계산한 연속시간이다. 5초 출력으로 관측한 하한이며 >1kW 동반 지표도 JSON에 남겼다.']
    for name,c in r['cases'].items():
        lines.append('['+name+']')
        for v in c['rows']:
            lines.append(f"  {v['room']}: 착화={v['ignition_s']}, 화원최대={v['actual_source_peak_kW']:.3f}kW, 최장연속양수HRR={v['longest_positive_HRR_s']:.1f}s, 개구부연소최대={v['native_vent_peak_kW']:.3f}kW, 상층최고={v['upper_C_max']:.3f}℃")
            if v.get('sensor_max') is not None:lines.append(f"    센서={v['sensor_criterion']}, 최대{v['sensor_max']:.3f}/기준{v['sensor_setpoint']}, 위치{v['sensor_xyz']}, 화원{v['source_xyz']}")
            if v.get('candidate_surface_max_C') is not None:lines.append(f"    기존 전체 후보 표면최고={v['candidate_surface_max_C']:.3f}℃, 기준369℃")
            if v.get('at_ignition_interpolated'):lines.append('    착화시 상태='+json.dumps(v['at_ignition_interpolated'],ensure_ascii=False))
    lines+=['',
            '4. 판정과 제한',
            '두 전이실의 양수 HRR60초 지속 기준: 모든 방식 불충족. T0 착화시각 자체가 없으므로 같거나 빠른지 비교할 유한 참조값이 없다.',
            'R2/R3의 착화시 온도·경계·산소도 사건이 없으므로 미해당이다. 0초로 채워 넣지 않았다.',
            'R1만1500kW로1195초 연속양수HRR. R2/R3 화원과DJET는전부0. 이번B1에서미전이는산소부족으로꺼진화원과다르게, 착화기준미충족이다.',
            'T2가 가장 공격적이라는 사전 추측은 채택 근거가 되지 않는다. R2 상층최고281℃/강판최고205℃로500℃미만이다.',
            'T0 R2 최고364.6℃는369℃에가깝지만, 성공시키기위해기준을낮추거나입력을재조정하지않았다.',
            '따라서 B1은 미착화 음성 대조 사례로 보존할 수 있으나, 방식 선택/전파 성능/다화원 속도의 합격 사례로 사용할 수 없다.',
            '8실 시험은 선택된 방식과 실제3회이상 재실행 사례가 확보된 뒤 가능하다. 지금 임의의T2를 골라 대규모 시험으로 넘어가지 않았다.',
            '또한 r3 결과에서 단계89%가추가착화이후라는것은 사실이나, 산소연소항만이비용원인이라는인과적확정이나CPU프로파일은아니다.','',
            '5. 코드와 표시',
            'room_rule.py: fuel_r4/ceiling_r4/floor_r4 명시 모드. 외기우선공급상한 기본ON(k1), 초기화원예외+경고, 높이0~0.5m검증, 화원/센서위치별도기록.',
            '기존 floor_r2/fuel_r3 및 외부 반복 방식은 보존. CLI에서 room-rule 사용 시 trigger를 명시해야 하며 표준을 자동 선택하지 않는다.',
            'combustion_display.py/conditions.py/playback.py/overlay.js: 실제HRR>0만 연소중. 착화+양수공급+HRR0은 산소·혼합 제한에 의한 미연소, 공급0은 성장시작/소진 등으로 분리한다.',
            'IGN만으로 산소부족을 단정하지 않는다. native 공급량을 같이 확인한다. 기존 저장자료에 공급 정보가 없으면 현재발열없음까지만 표시한다.',
            '문 분출연소는 기존 방향별 개구부HRR로 별도표시. 작은 양수HRR까지 집계한다는 수치적 한계를 메타데이터에 기록.',
            '현재 3D의 계산결과는 대체하지 않았다. 화면 코드는 수정했으며 새실험모드는검증중비활성 유지. 저장결과표시후처리도 엔진재실행과구분한다.',
            '',
            '재현/자료',
            'tools/test_room_rule_r4.py --analyze-only (완료자료 읽기만; 새 실행 안 함)',
            'tools/report_room_rule_r4.py (이 보고서 재작성)',
            'simulation/results/room_rule_r4_20261025/comparison.json 및 T0~T3/analysis.json',
            '각 폴더의 requested-scenario.json, run_*/case.in, case.cfbt, completed.json, case_*csv.',
            '표준 선택: 없음 / 승인 요청: 합격 후보가 없으므로 아직 없음 / 8실 및3F시험: 미실행.']
    path=ROOT/'specs/실단위규칙-r4-B1비교-20261025.txt';path.write_text('\n'.join(lines)+'\n','utf-8');print(path)

if __name__=='__main__':main()
