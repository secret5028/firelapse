"""Report saved stage2 runs only. Does not integrate or launch engines."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'simulation/results/lite_v6_screening_20261025'
def read(p):return json.loads(p.read_text('utf-8'))
s=read(OUT/'score.json');c=read(OUT/'comparison.json');rows={r['room']:r for r in c['rows']}
lines=['간략 엔진 v6 / 8.1절 2단계 결과 — 2026-10-25',
'범위: ① 초간략 점수 + 상위 N 설정 + 3F N=5의 ② 순차 계산. 여기서 정지.',
'정렬: 연소 실 수↓ → 연기 위험 도달 실 수↓ → 최초 FO 시각↑. 동률은 공동 순위.',
f"① 점수 {s['score_seconds']:.6f}초 / 원래 구획 {s['all_room_count']}실 / 후보 {s['eligible_count']}실.",
f"② 3600초 × 5회, 직렬 1작업자, 모두 완주. 총 {c['total_wall_s']:.3f}초. MC·새 CFAST 실행 없음.",
'산소 재고 OFF. v6가 채택한 누적 E 상태 제거·희소 패턴 ON. 실행 중 물리 코드 SHA 불변: '+str(c['physics_code_unchanged_during_batch']),
'', '①순위 | 화점실 | 점수 | ②순위 | 연소실 | 연기위험실 | 최초FO | 적분(s) | 전처리(s) | 후처리(s) | 최고상층(C)']
details=[]
for candidate in s['ranked'][:5]:
 rid=candidate['room'];r=rows[rid];result=read(OUT/rid/'result.json');manifest=read(OUT/rid/'rule_manifest.json')
 t=r['times'];maxT=max(x['upper_max_C'] for x in result['room_summary'])
 lines.append(f"{candidate['rank1']} | {rid} {candidate['name']} | {candidate['score']:.6f} | 공동 {r['rank2']} | {r['burning_room_count']} | {r['smoke_risk_room_count']} | 없음 | {t['integration_s']:.3f} | {t['preprocess_s']:.3f} | {t['postprocess_s']:.3f} | {maxT:.2f}")
 details.append({'room':rid,'max_upper_C':maxT,'cell_events':result['events'],
   'burning_cells':[x for x in result['room_summary'] if x['actual_peak_kW']>0],
   'unreachable_rooms':manifest['graph']['unreachable_combustible_rooms'],
   'excluded_edges':manifest['graph']['excluded_edges'],'balance':r['balance']})
lines += ['', '해석',
'- 모두 최초 화점의 원래 실만 연소했다. R1은 내부 8셀 중 4셀에서 발열, 내부 추가 전이 3건이다. 원래 실로 합산하므로 1실이다.',
'- 다섯 사례 모두 상층 최고가 실간 전이 기준 600℃에 미달했다. R1 내부 전이는 셀 기준 300℃에 의해 발생했다.',
'- 이번 대표 상태: 방화문 19개 모두 닫힘, 일반문 4개 모두 열림, 개폐창 43개 모두 닫힘, 영구 개구부 3개 열림. 닫힘은 모델의 누설 처리 적용.',
'- 방화문 분류에 따른 전이 간선 제거도 전파 범위를 제한한다. OCR의 ELEV.홀 문자열로 생산실 주변 문까지 방화문으로 분류되는 기존 한계를 보존했다. 이번 단계는 재분류하지 않는다.',
'- 연기 위험 0은 연기 없음/안전이라는 뜻이 아니다. 상층 온도·미연 연료·층 두께/경계 높이의 지정 복합 조건 미충족이다. FO도 공통 조건표의 복합 충족이다.',
'- ②는 변별하지 못했다. R1은 공동 1위 중 안정적 ID 순 기본 선택일 뿐, 유일한 최악실이 아니다. 이를 맞추기 위해 가중치나 임계값을 바꾸지 않았다.',
'', '① 계산 정의와 한계',
'- 원래 실 기준, 셀 분할 전에 5요인을 층 전체에서 min-max. 가중치 각 1, 합 0~5. 상수 요인은 정보가 없어 0점. 동점 N 경계는 ID로 정확히 N개 선택.',
'- 연료는 현재 입력의 energy_MJ를 사용한다(기존 고연료 시나리오 배율 포함). 각 화점은 자기 실의 입력 곡선을 사용하며 다른 생산실의 50MW를 옮기지 않는다.',
'- 환기 지표는 도면 개구부의 기하학적 총 A√H/체적이다. 문·창 상태나 공기 유입망을 풀지 않는다. 연결도는 대표 상태에서 열린 실내 문/통로 2단계의 고유 실 면적 합이다.',
'- 통과 공간 인접은 기존 용도/core_kind만 사용. 새 OCR 추론을 추가하지 않았다. 후보는 기존 연료와 50MJ/m² 이상 하중을 가진 실(계단·승강로 등 코어 제외).',
'- 모든 창을 닫는 p>=0.5 대표화는 확률의 수학적 기대값도 MC 최악 조합도 아니다. 단 한 조합이므로 전체 조건의 최악을 보증하지 않는다.',
'- 화장실이 상위에 드는 것은 현재 입력 연료, 이진 인접 지표, 방화문 비율과 균등 가중의 결과다. 화재 빈도를 추정한 순위가 아니다.',
'- ① 점수는 입력 지표의 상대 순위이며 위험도 예측값이 아니다. 후보 선별용.',
'', '검증/화면',
'- 단위 검사 40건 통과: 순위 우선순위·공동순위·미완료 제외·N 범위·입력 보존·문창 대표 상태 포함.',
'- 10초 출력 장부 진단: 에너지 잔차 전 사례 0.1% 이내. 질량 잔차는 아래 수치만 보고하며 수락 스텝 보존 인증이 아니다.',
'- 기존 3D에 상위 N 입력(기본3), 순위표, 후보 색상 윤곽, MC 화점 선택 저장을 연결. 기존 화재 재생은 교체하지 않음.',
'- 재계산은 UI 명시 실행 때만 N개 직렬. 이번 검증 중 추가 시뮬레이션은 수행하지 않음.',
'- 후속 MC, 문 분출 연소, 문 재분류, 속도 추가 최적화는 하지 않음.', '', '장부 진단']
for r in c['rows']:
 b=r['balance'];lines.append(f"{r['room']}: 질량 {b['mass_percent']:.6f}%, 에너지 {b['energy_percent']:.6f}%")
lines+=['','요인별 원값(연료MJ, 환기A√H/V, 2-hop면적m², 인접0/1, 방화비율)']
for r in s['ranked'][:5]:lines.append(r['room']+' '+json.dumps(r['raw'],ensure_ascii=False))
(OUT/'diagnostic.json').write_text(json.dumps(details,ensure_ascii=False,indent=2),'utf-8')
report=ROOT/'specs/간략엔진-v6-후보점수·상위5비교-20261025.txt'
report.write_text('\n'.join(lines)+'\n','utf-8');print(report)
