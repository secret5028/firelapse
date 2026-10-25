"""Write a review report from completed r3 measurements; does not run CFAST."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'simulation/results/room_rule_r3_20261025'

def main():
    diagnostics=json.loads((OUT/'comparison.json').read_text('utf-8'))
    corrected=json.loads((OUT/'corrected-comparison.json').read_text('utf-8'))
    lines=[
        '실 단위 규칙 r3 — 입력 덱 보정과 정체 진단 결과 (2026-10-25)',
        '',
        '범위: 사용자 대화에 붙인 r3 지시문. Fortran/엔진/솔버/출력 격자 변경 없음.',
        '기존 전파 모드를 보존하고 별도 room-rule 실험 모드만 수정. 운영 3D 결과는 교체하지 않음.',
        '',
        '1. D1~D4: 3실, 600초 시나리오, 각 실행 예산 600초',
        '동일한 순정 상세 진단 출력을 켰으므로 실행 시간에는 진단 파일 쓰기 비용이 포함된다.',
        '실행 | 완주 | 벽시계 초 | native 진행초 | 단계 수 | 보고 dt 최소/중앙(초)',
    ]
    for d in diagnostics:
        stat=d['dt_statistics']
        lines.append(f"{d['id']} | {d['complete']} | {d['measured_wall_seconds']:.3f} | {d.get('native_progress_s')} | {d.get('total_steps')} | {stat['min_s']:.8g} / {stat['median_s']:.8g}")
    lines += [
        '',
        'dt는 원본 DASSL_DEBUG_PRINT가 출력한 이전 단계 변수다. 출력 위치에 따른 사건 재시도 문맥을 포함하며, 승인된 적분 단계만 별도로 계측한 통계가 아니다.',
        'D1: 기존 바닥센서 규칙 그대로. D2: TIME 278/333초. D3: D2+단일 개구부 공급 상한. D4: D2+상승180초.',
        'D1 정수초 로그는 R2=278, R3=331초였다. D2는 지시문 278/333초를 유지했으므로 센서만 바꾼 완전 동일 사건 시각 시험은 아니다.',
        '',
        '2. 공급량/실제 연소량/산소',
        '공급은 고체 열분해량×연소열이다. 실제 화원 HRR과 구별한다. 순정 DJET는 별도이며 아래 화원별 적분만으로 건물 전체 에너지 수지를 증명하지 않는다.',
    ]
    for d in diagnostics:
        lines.append(f"[{d['id']}] 순정 개구부 연소 적분 {d['native_vent_combustion_MJ']:.3f} MJ")
        for r in d['rooms']:
            lines.append(f"  {r['room']}: 공급/실제 최대={r['supply_peak_kW']:.2f}/{r['actual_peak_kW']:.2f} kW, 공급/화원 실제 누적={r['supplied_MJ']:.2f}/{r['actual_HRR_MJ']:.2f} MJ, 상/하층 O2 최소={r['upper_O2_min_vol_percent']:.3f}/{r['lower_O2_min_vol_percent']:.3f} vol%, IGN 구간={r['ignition_bracket_s']}")
        lines.append('  단계별 dt: '+json.dumps(d['dt_by_phase'],ensure_ascii=False))
    lines += [
        '',
        '3. 원인 판정의 범위',
        'D1은 600초를 완주했다. 앞선180초 예산 중단은 무한 정지의 증거가 아니며, 다화원 구간의 매우 작은 시간간격 때문에 느려진 사례다.',
        'D2도 작은 dt로 느려진다. 따라서 센서 착화 기능만이 지배적 원인이라는 설명은 지지되지 않는다.',
        'D3 상한 = 1.5×1500×2.1×sqrt(2.1) ≈ 6847 kW > 기존 5000 kW. 상한은 작동하지 않았다.',
        'D2와 D3 입력 SHA256은 같다. 동일 입력 반복 측정이지, 공급 감소의 효과를 검증한 시험이 아니다. k를 임의로 낮추지 않았고 상한은 기본 OFF로 남겼다.',
        'D4는 같은 에너지 예산을 더 천천히 공급한다. 고정600초 동안 방출된 양도 달라지므로 속도 차이를 순수 수치기법 효과라고 해석하면 안 된다.',
        'D1의 첫 추가 착화 전 보고 단계 수는 16,617, 이후 131,995(전체의 약89%)다. dt 중앙값만 비교하면 짧은 특정 구간의 작은 단계가 과대표집될 수 있다.',
        '최대 오차 성분 출력은 대부분 실 압력이었다. 이는 내부 항의 CPU 프로파일이나 산소식의 인과적 결함 증명이 아니다.',
        '순정 다화원/산소부족 결합에서 강성이 커진다는 설명은 유력한 추론이다. 어느 내부 항이 원인인지를 이 네 시험만으로 확정하지 않는다.',
        '',
        '4. r3 구현',
        '- 최초 화원 입력 곡선 유지. 이후 실당 대표 FIRE 하나, CFAST native target 조건으로 착화. 외부 사건 재실행 없음.',
        '- 기존 후보의 위치·방향·물성·착화 기준을 재사용. 표준은 기준1배, 상승60초. 보수1.2배/180초, 공격0.8배/30초는 프로젝트 가정.',
        '- 이번 비교는 역사적 착화 후보 R2=C_2, R3=C_11을 명시적으로 고정했다. 임의 건물에서 이를 자동으로 알아내는 알고리즘이 아니다.',
        '- 미지정 실은 기존 후보 입력 순서의 첫 후보를 사용한다. 여러 후보의 OR를 한 센서로 축소하는 한계가 있다.',
        '- 바닥15kW/㎡는 별도 센서와 조건표 표시 전용. 착화 결정에 피드백하지 않는다.',
        '- k×1500×max(A√H) 선택 옵션 구현. 개구부 합산 안 함. 창 파괴 후 면적/예정 최대개방 면적 사용. 실제 환기 한계가 아닌 수치 안정용 공급 상한.',
        '- 열·산소 반응은 기존 native에만 맡긴다. 프로젝트 bulk/혼합/강제점화/FO재확대 OFF. 공급 에너지 예산 적분과 음수/0상한 입력을 검사한다.',
        '- saved scenario 재입력 시 후보 ID와 덱이 유지되는 회귀 검사 추가.',
        '',
        '5. 보정 방식과 기존 방식의 비교',
        '두 방식 모두 동일 기하/연료 기본값, gas OFF. 과거63.277/121.592초 시험은 gas ON 및 CO에너지 예약이 있어 직접 동일조건 비교가 아니었다.',
        '대표 연료의 위치/물성을 같게 해도 native 판 열응답은 기존 Python 판+문 너머 보충열과 다르다. 기준 수치의 재사용이 착화 모델 전체의 동등성은 아니다.',
        'D1~D4의 r2 대표화원은 바닥 중앙(z=0m)이었고, 보정 비교는 기존 착화 후보 위치(z=1.5m)를 화원에도 재사용했다. 따라서 D1 대비 실행시간 차이는 순수한 착화 트리거 변경 효과가 아니다.',
        '보정 및 gas-OFF 기존 방식 모두 R2/R3 화원 HRR 최대는 0이다. 연료 공급과 DJET 개구부 연소는 발생한다. IGN 플래그를 실내 지속 화염의 증거로 사용하면 안 된다.',
        '보정 첫 착화 직후 표본: R2(260초) 연기층 경계0.811m/상층O2 2.273%, R3(520초) 경계1.153m/O2 1.799%. 대표 화원 높이1.5m는 둘 다 상층 내에 있다.',
        '순정 fire.f90의 lower_plume_height=실높이-상층두께-화원높이이므로 이 배치는 하층 공기 흡입/연소 기회를 바꾼다. 위치·높이와 판정시각의 결합을 추가 검토할 필요가 있다. 성공을 만들려고 높이나 임계값을 임의 변경하지 않았다.',
        '기존 방식도 schedule_stable=True지만 R2 재확인 불충족으로 condition_consistent=False, spread_search_complete=False다. 63.6/122.9초를 검증된 실제 화재 정답으로 간주하지 않는다.',
    ]
    for name,c in corrected['cases'].items():
        lines.append(name+': '+json.dumps(c,ensure_ascii=False))
    lines += [
        '시간 판정: '+json.dumps(corrected.get('timing'),ensure_ascii=False),
        '합격: '+str(corrected['passed']),
        '신규 방식 시간은 별도 stock baseline 1회와 시나리오1회를 분리해서 읽어야 한다. 기존 방식은 여러 재실행 합계도 함께 비교한다.',
        '모든 시각은 출력 구간/반올림 로그로 관측한 값 또는 기존 후처리 보간값이다.',
        '',
        '6. 적용 상태와 산출물',
        '3F 16실/3600초 확대 실행은 하지 않았다. 지시문의 선행 합격 기준을 만족하기 전 운영 기본값으로 전환하지 않는다.',
        'UI 새 규칙 모드는 검증중 비활성 상태, 현재 3D는 기존 결과 유지.',
        '코드: simulation/pyrocast_cfbt/room_rule.py, __main__.py, tools/serve_cfbt_building.py, simulation/viewer/overlay.js',
        '검사: simulation/tests/test_room_rule.py, tools/diagnose_room_rule_r3.py, tools/check_room_rule_r3.py',
        '근거: simulation/results/room_rule_r3_20261025/{input-audit.json,comparison.json,corrected-comparison.json}',
        '각 D폴더 diagnosis.json, R*-series.json에 HRR/O2 시계열과 dt 통계. case.in/case.cfbt/execution.log/completed.json에 재현 자료.',
        '새 진단 재실행 없이 재분석: tools/diagnose_room_rule_r3.py --analyze-only',
        '',
        '엔진: 기존 adaptive_radiation_20261025 진단 빌드 사용, 프로젝트 물리확장 및 최적화 OFF. 문자 그대로의 stock 바이너리와는 구분한다.',
        '별도 baseline_native만 stock cfast-baseline.exe 사용. 빌드/원본 Fortran은 이번 작업에서 수정하지 않았다.',
    ]
    path=ROOT/'specs/실단위규칙-r3-진단과착화보정-20261025.txt'
    path.write_text('\n'.join(lines)+'\n','utf-8')
    print(path)

if __name__=='__main__':main()
