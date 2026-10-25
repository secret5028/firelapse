"""Saved-result report only; no simulation or re-ranking calculations."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'simulation/results/lite_v8_mc_R2_10_20261026'
def read(p):return json.loads(p.read_text('utf-8'))
def fmt(x):return '—' if x is None else f'{x:.3f}'
def main():
    a=read(OUT/'aggregate.json');rows=read(OUT/'summaries.json')
    lines=['5단계 — R2 MC10 직렬 결과 (2026-10-26)',
        '',f"완주 {a['completed']}/10, 실패·미완료 {a['failed_or_incomplete']}/10. 무작위 {a['random_completed']}/8, 필수 {a['mandatory_completed']}/2.",
        f"직렬 전체 소요 {a['wall_s']:.3f}초. 표본별 적분 예산 1,200초, 시뮬레이션 길이 3,600초, 출력 10초.",
        f"seed=20261025. workers=1. 실행 중 간략 엔진 소스 SHA 동일: {a['code_unchanged_during_batch']}.",
        '입력: 승인 N8의 R2 연료/용도/기하. 문·창 상태만 표본별 재추출. 문 분출 기본 ON, 층별 산소 유지, 받는 실 하층 산소 소비.',
        'R2 연료 하중 1,800 MJ/m², 피복률 0.5, HRRPUA 250 kW/m². 최초 총 peak 40,634.225 kW를 셀에 배분. 임계·지연·확률 튜닝 없음.',
        'S00 모든 방화문 열림(그 밖의 문·창은 추출 상태), S01 모든 개폐 가능 개구부 닫힘, S02~S09 무작위. 영구 통로는 항상 열림.',
        '추정 방화문 열림확률 0.35, 확정 0.2, 일반문 0.5, 개폐창 0.3, 고정창 0. 열린 창 유효면적 0.5.',
        '집계 코드가 피난한계 all_met 위치를 잘못 읽은 오류는 저장 상태로 후처리만 복원했다. 계산 재실행 0회. 원래 오류 요약과 수정 전 집계를 별도 보존했다.',
        '표본별 합산 시간은 기록된 적분+결과 후처리+복원 시간이며, 최초 전처리/오류 기록 부대 시간은 누락된다. 직렬 전체 소요는 최초 배치의 실제 벽시계 시간이다.',
        '', '표본 | 완주 | 연소 실 | 연기 위험 실 | 연기 주의 실 | FO/FGI/BD/롤오버 충족 실 | 적분초 | 합산초 | 안전 출력 끝초 | 에너지% | 질량%',
        '---|---|---|---|---|---|---|---|---|---|---']
    for s in rows:
        if not s.get('complete'):
            lines.append(f"{s['sample_id']} | 실패·미완료 | — | — | — | — | {fmt(s.get('times',{}).get('integration_s'))} | {fmt(s.get('times',{}).get('total_s'))} | {s.get('safe_end_s','—')} | — | —")
            lines.append('실패 이유: '+str(s.get('failure')))
            continue
        p=s['phenomena'];b=s['balance_diagnostic']
        lines.append(f"{s['sample_id']} | 완료 | {len(s['burning_original_rooms'])} | {len(s['smoke_risk_rooms'])} | {len(s['smoke_caution_rooms'])} | "+'/'.join(str(p[k]['ever_room_count']) for k in ('FO','FGI','backdraft','rollover'))+f" | {s['times']['integration_s']:.3f} | {s['times']['total_s']:.3f} | {s['safe_end_s']:.0f} | {b['energy_percent']:.6f} | {b['mass_percent']:.6f}")
    lines+=['','주의/위험 실은 기간 중 한 번이라도 해당한 원래 실의 합집합으로, 두 열은 서로 배타적이지 않다. 셀 수를 실 수로 세지 않는다.',
        '현상별 표본비율은 공통 조건표를 사용한다. 색 표시는 v8 4.2절 2단계 규칙이며 조건표 지수와 판정 구성이 다르므로 혼동하지 않는다.',
        '', '현상 | 충족 무작위 표본/완주 무작위 표본 | 최고 지수 | 표본별 최고 지수의 중앙값 | 최악 표본(필수 포함)',
        '---|---|---|---|---']
    for k,v in a['condition_sample_rates_random_only'].items():
        score=lambda x:'미평가' if x is None else f'{x*100:.2f}'
        lines.append(f"{k} | {v.get('numerator','—')}/{v.get('denominator_completed_random','—')} | {score(v.get('maximum_score'))} | {score(v.get('median_of_sample_maxima'))} | {a['worst_including_mandatory'].get(k,{}).get('sample_id') or '없음'}")
    lines+=['','지수 100은 설정 조건 기준이며 발생확률이 아니다. 최고 지수와 충족 지속시간 비율을 저장했다. 무의미한 전체 시간 중앙값을 사용하지 않는다.',
        '최악 표본 기준: 해당 현상 충족 실 수 많음 → 최초 충족 시각 빠름 → 표본 ID. 표본별 실제 열린 문·창은 sample.json 및 aggregate.json에 저장.',
        '',f"10초 출력 장부 에너지 진단 미통과 표본: {a['output_diagnostic_failures']}",
        '에너지 허용 0.1%, 질량 잔차는 보고용. 출력 구적 진단이며 적분 내부 모든 단계의 엄밀 보존 인증은 아니다.',
        '저장 출력 수치 범위(표시용 양수 처리 전): '+json.dumps({s['sample_id']:s.get('numerical_output_health') for s in rows},ensure_ascii=False),
        f"Radau 대체 실행 표본: {[s['sample_id'] for s in rows if s.get('solver_fallback')]}",
        '기존 20표본 중 실패≤1 관문을 10표본에 임의 환산하지 않았다. 이번은 요청한 10표본 탐색이며 20표본 관문 완료로 주장하지 않는다.',
        '', '모든 개구부 닫힘 표본의 개방 시 위험 구간']
    closed=next((s for s in rows if s['kind']=='all_openings_closed'),{})
    if closed.get('complete') and closed.get('opening_risk',{}).get('status')=='evaluated':
        risk=closed['opening_risk'];lines.append('설정 기준: '+json.dumps(risk['thresholds'],ensure_ascii=False))
        hit={k:v for k,v in risk['rooms'].items() if v}
        lines.append(json.dumps(hit,ensure_ascii=False,indent=2) if hit else '조건 교집합을 만족한 저장 구간 없음.')
    else:lines.append('미완료 또는 미평가. 안전으로 간주하지 않는다.')
    lines+=['이 구간은 닫힌 상태의 조건 교집합이다. 실제 문 개방이나 점화 사건을 계산한 결과가 아니다.',
        '', '3D 및 한계',
        '- 완주 표본은 기존 3D의 간략 계산 사례 선택에 추가했다. 미완료 표본은 재생 선택에 넣지 않고 본 표에 남겼다.',
        '- 회색 연기는 계산 상층 범위의 표시 효과이며 실제 광학밀도는 계산하지 않는다. 위험 색과 별개로 표시한다.',
        '- 문 분출·상층 발열은 별도 값. 문 분출을 롤오버로 부르거나 고체 착화 실 수에 더하지 않는다.',
        '- 실내 열·산소·유동은 프로젝트 간략식. 정밀 CFAST r8 동결, 새 정밀 실행 없음.',
        '- 창 파괴·수직 전파·정확한 천장 제트 속도·폭압은 생략. 연료 및 문 분류의 추론·가정 유지.',
        '- '+a['known_bias'], '- '+a['bias_scope'],
        '계산은 순정 CFAST 7.7.7(정밀) 또는 CFAST 구역 모델 개념을 참고한 프로젝트 간략 엔진(탐색)이다. 전이는 프로젝트 규칙(상층 온도 기준 + 경로 지연)에 따른 가정이며 FO 발생 예측이 아니다. 조건 충족 비율은 설정한 입력 분포 안의 비율이며 실제 발생 확률이 아니다.',
        '', '결과: simulation/results/lite_v8_mc_R2_10_20261026',
        '요청된 5단계 종료. 추가 표본·재실행·튜닝 없이 정지.']
    report=ROOT/'specs/간략엔진-v8-R2-MC10-20261026.txt';report.write_text('\n'.join(lines)+'\n',encoding='utf-8');print(report)

if __name__=='__main__':main()
