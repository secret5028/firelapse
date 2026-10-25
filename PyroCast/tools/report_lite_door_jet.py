"""Postprocess saved stage3 outputs only; never integrates a scenario."""
import json,hashlib
from pathlib import Path
import numpy as np
import run_lite_door_jet as task
ROOT=task.ROOT;OUT=task.OUT
read=task.read;save=task.base.save

def condensed(r):
    mapping={v['cell']:v['original_room'] for v in r['room_summary']}
    conditions={}
    for kind in ('FO','FGI','backdraft','rollover'):
        hit=set();first=None;degree=0.
        for cell,items in r['shared_conditions']['rooms'].items():
            scores=items[kind]['scores']
            mask=np.array([v is True for v in scores['all_met']])
            if mask.any():
                hit.add(mapping[cell]);at=float(np.asarray(r['t'])[mask][0]);first=at if first is None else min(first,at)
            degree=max(degree,max((x for x in scores['degree'] if x is not None),default=0.))
        conditions[kind]=dict(rooms=sorted(hit),count=len(hit),first_s=first,max_degree=degree)
    byroom={}
    for row in r['room_summary']:
        rid=row['original_room'];v=byroom.setdefault(rid,dict(upper_max_C=-1e9,first_HRR_s=None))
        v['upper_max_C']=max(v['upper_max_C'],row['upper_max_C'])
        t=row['first_actual_positive_HRR_s']
        if t is not None:v['first_HRR_s']=t if v['first_HRR_s'] is None else min(t,v['first_HRR_s'])
    return dict(rooms=byroom,conditions=conditions,burning_rooms=task.grouped(r['room_summary'],3600),
        integration_s=r['integration']['wall_seconds'],postprocess_s=r['postprocess_wall_seconds'],manifest_sha256=r['r8_manifest_sha256'])

old=read(ROOT/'simulation/results/lite_v5_sparse_20261025/result.json')
new=read(OUT/'3F/result.json');s=read(OUT/'3F/summary.json')
before,after=condensed(old),condensed(new)
if before['manifest_sha256']!=after['manifest_sha256']:raise ValueError('Different r8 input manifest')
old_by={r['cell']:r for r in old['room_summary']}
temperature=[dict(cell=r['cell'],before_C=old_by[r['cell']]['upper_max_C'],after_C=r['upper_max_C'],
    difference_C=r['upper_max_C']-old_by[r['cell']]['upper_max_C']) for r in new['room_summary']]
oldz=np.load(ROOT/'simulation/results/lite_v5_sparse_20261025/state.npz')
newz=np.load(OUT/'3F/state.npz');n=len(new['rooms'])
raw_max_error=float(np.max(np.abs(newz['y'][2*n:3*n]-oldz['y'][2*n:3*n])))
audit=dict(before=before,after=after,gate=s['gate'],temperature=temperature,
    max_upper_timeseries_difference_C=raw_max_error,
    before_min_fuel_mass_fraction=float(oldz['y'][6*n:8*n].min()),
    after_min_fuel_mass_fraction=s['reaction_checks']['min_fuel_mass_fraction'],
    timing_caveat='v5 saved baseline included profiler overhead; current run unprofiled, separate sessions; no speedup claim',
    old_and_new_manifest_identical=True,energy_gate_pass=s['balance']['passed'],
    implementation_gate_pass=bool(s['gate']['passed'] and s['balance']['passed']),
    production_default_enabled=False,MC_executed=False,operational_playback_replaced=False)
save(OUT/'comparison.json',audit)

lines=['v8 8.1절 3단계 — 문 분출 연소 구현·검증 (2026-10-26)',
'사용자 확정: 실 단위 산소 재고 OFF. 층별 산소 유지, 받는 실 하층 산소 소비.',
'결론: B3 2회 + 기존 3F 표준 1회 직렬 완료. 3F 집합·순서 및 에너지 관문 합격. MC·색 표시 단계는 미실행.',
'문 분출 옵션은 검증 실행에서만 ON. 기존 선별/운영 기본값은 OFF로 보존하며 N=8 결과를 새 물리로 재표시하지 않았다.',
'', '1. 계산과 중복 방지',
'- 기존 양방향 문 유량으로 이미 운반된 상층 미연 연료만 분출 반응에 사용. 받는 쪽 유입 연료에서 연소분을 한 번 차감한다.',
'- 한 실에 들어오는 모든 분출이 받는 실 하층 O2/10s 예산을 공유한다. 기존 플룸의 하층 산소 인출을 먼저 예약한다.',
'- 같은 반응률 xi에서 연료 감소 xi, 산소 소비 (Hc/H_O2)*xi, 발열 Hc*xi를 산출. 열은 받는 상층에 한 번 더한다.',
'- 출발실 상층 재고 중 유출되는 연료를 상층 추가연소 예산에서 예약해 중복 사용을 막는다.',
'- 출발 상층 > 실내 초기온도+200K; 기존 반응 경계 폭0.5K의 연속 처리를 사용. 이번 입력 실내·외기 모두20℃.',
'- BDF·출력10s·전이 임계값·정밀 CFAST 소스·기존 모델은 유지. 문 분출 열은 고체 화원 HRR/상층 반응과 별도 기록.',
'', '2. CFAST 근거와 근사의 한계',
'로컬 vendor/cfast-7.7.7/Source/fire.f90 vent_jets/vent_jet_fire: 수평 개구부로 나가는 상층 연료와 받는 실 하층 공기를 사용.',
'input_namelist.f90의 tgignt=interior_ambient_temperature+200. 공식 기술문서: https://doi.org/10.6028/NIST.TN.1889v1',
'이 구현은 해당 흐름을 참고한 프로젝트 근사식이다. CFAST의 분출 플룸 공기 혼합량/연료 조성별 화학/복사 모델과 동일하지 않다.',
'추가 혼합 질량 이동, 외부 분출 연소, 가상 셀 경계의 분출 연소는 계산하지 않는다. 생성물은 기존 혼합가스 잔여분으로 처리한다.',
'따라서 NIST 검증 엔진·실제 롤오버 예측이라고 표시하지 않는다. 통행/FGI 조건은 기존 공유 조건표를 사용한다.',
'', '3. B3 저장 CFAST 비교 (DJET는 받는 실별 합계, 단위 kW)',
'명세의 1907/443 kW는 이번에 확인한 r5 B3 파일 값과 불일치하므로 참조값으로 사용하지 않았다.',
'사례 | R1 수신 | R2 수신 | R3 수신 | 비고']
for row in read(OUT/'native-reference.json'):
    values={j['id']:j['peak']/1000 for j in row['jets']}
    lines.append(f"CFAST {row['mode']} | {values.get('R1',0):.3f} | {values.get('R2',0):.3f} | {values.get('R3',0):.3f} | 저장 출력, 입력 전이 규칙 차이 포함")
for name in ('B3_primary_only','B3_transition'):
    r=read(OUT/name/'result.json');sm=read(OUT/name/'summary.json')
    peaks={row['id']:max(row['door_jet_HRR_kW']) for row in r['rooms']}
    lines.append(f"간략 {name} | {peaks.get('R1',0):.3f} | {peaks.get('R2',0):.3f} | {peaks.get('R3',0):.3f} | 전체 {sm['times']['total_s']:.3f}s, 에너지 잔차 {sm['balance']['energy_percent']:.6f}%")
    lines.append('  실제 화원: '+', '.join(f"{x['cell']} 최초{x['first_actual_positive_HRR_s']}s / 최고{x['actual_peak_kW']:.2f}kW / 지속{x['longest_positive_HRR_s']}s" for x in r['room_summary']))
lines+=['B3 단독은 양쪽 모두 DJET=0. 전이 사례는 서로 다른 규칙의 저장 참조값이며 일대일 정답 검증이 아니다. 수치 맞추기/재튜닝 없음.',
    '', '4. 3F 문 분출 전·후 (같은 r8 manifest SHA)',
    f"SHA256 {before['manifest_sha256']}",
    '이 비교는 저장 CFAST와 입력을 맞춘 역사적 표준 시험이다. 새 용도표·방화문 재분류를 적용한 N=8 선별 입력과 구분한다.',
    f"문 분출 전 적분 {before['integration_s']:.3f}s(프로파일 포함), 후 적분 {after['integration_s']:.3f}s, 후 전체 {s['times']['total_s']:.3f}s.",
    '별도 시점 측정과 프로파일 차이가 있으므로 속도 개선율로 해석하지 않는다.',
    '실 | 전 최초 실제HRR(s) | 후 최초 실제HRR(s) | 전 상층 최고℃ | 후 상층 최고℃']
for rid in sorted(after['rooms']):
    a=before['rooms'][rid];b=after['rooms'][rid]
    lines.append(f"{rid} | {a['first_HRR_s']} | {b['first_HRR_s']} | {a['upper_max_C']:.3f} | {b['upper_max_C']:.3f}")
lines += [f"시간별 상층 온도 최대 절대차 {raw_max_error:.6f}℃ (실별 최고값 차이와 다름).",
    '조건 | 전 충족 원래실 수 | 후 충족 원래실 수 | 전/후 최고 정도지수']
for kind in before['conditions']:
    a=before['conditions'][kind];b=after['conditions'][kind]
    lines.append(f"{kind} | {a['count']} | {b['count']} | {a['max_degree']:.6f} / {b['max_degree']:.6f}")
lines += [
    f"문 분출 누적발열 {s['cumulative_door_jet_MJ']:.3f}MJ, 상층 추가연소 누적 {s['cumulative_upper_MJ']:.6f}MJ. 서로 다른 장부이며 롤오버 확정이 아니다.",
    '3F 실제 연소8실: '+', '.join(after['burning_rooms']),
    '관문: CFAST 표준 실제연소1실 ⊆ 간략8실 ⊆ CFAST 공격 조건통과9실. 공통 관측구간2850s, 간략 전체3600s도8실.',
    '순서: 최초R2 → 나머지7실 동시 표본군. CFAST 실제960s, 간략2110s. 동일 시각 예측이 아니라 순서 관문이다.',
    'CFAST 공격은2850s 부분 결과이므로 이후의 native 전이 여부는 미평가. R17은 native 조건통과/실제HRR0, 이번 간략도 고체 연소 없음.',
    '', '5. 장부·수치 한계',
    f"3F 에너지 잔차 {s['balance']['energy_percent']:.8f}% ≤ 0.1%; 질량 잔차 {s['balance']['mass_percent']:.8f}% (보고만).",
    f"3F 열/반응량 일치 오차 {s['reaction_checks']['max_heat_stoichiometry_error_W']:.3g}W, 공유 O2 예산 초과 {s['reaction_checks']['max_lower_oxygen_budget_excess_kg_s']:.3g}kg/s(부동소수점).",
    f"하층/상층 O2 질량분율 최솟값 {s['reaction_checks']['min_lower_oxygen_mass_fraction']:.6f}/{s['reaction_checks']['min_upper_oxygen_mass_fraction']:.6f}.",
    f"연료 질량분율 최소: 전 {audit['before_min_fuel_mass_fraction']:.8g}, 후 {audit['after_min_fuel_mass_fraction']:.8g}. 기존 부드러운 경계/적분에 따른 작은 음수 잔차는 남아 있다.",
    '반응은 양수 재고만 사용한다. 10s 저장 표본의 장부 검사는 모든 내부 솔버 단계의 엄격 보존/양수성을 증명하지 않는다. 이 단계에서 솔버나 경계를 재조정하지 않았다.',
    '', '6. 실행 범위와 산출물',
    'B3 단독1회 → B3 전이1회 → 3F 표준1회 직렬, 재시도0. 새 CFAST/MC/화재 화면 교체 없음.',
    '입력·manifest·계수·코드SHA·state.npz·result.json·summary.json·balance.json·native-reference.json·comparison.json 저장.',
    'N=8 추가6회 결과는 specs/간략엔진-v8-N8추가6회-20261025.txt. R2 ①6위 → ②2위, R1 ①1위 → ②3위.',
    '이번 단계 보고 후 정지. 기존 선별 결과를 문 분출 ON 결과로 혼용하지 않는다.']
report=ROOT/'specs/간략엔진-v8-문분출연소-검증보고-20261026.txt'
report.write_text('\n'.join(lines)+'\n','utf-8')
print(json.dumps(dict(report=str(report),gate=audit['implementation_gate_pass'],before=before['conditions'],after=after['conditions'],max_upper_difference_C=raw_max_error),ensure_ascii=False))
