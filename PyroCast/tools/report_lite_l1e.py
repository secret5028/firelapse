"""Read saved L1e evidence and write the review report. No integration."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
import numpy as np
import run_lite_l1 as base

ROOT=base.ROOT
OUT=ROOT/'simulation/results/lite_l1e_20261025'
def read(p):return json.loads(p.read_text('utf-8'))
def main():
    a=read(OUT/'mc-aggregate.json');old=read(OUT/'reaggregate/aggregate.json')
    rows=[read(p) for p in sorted((OUT/'mc').glob('*/summary.json'))]
    assert len(rows)==20,'Wait for the authorized batch to finish'
    guard=read(ROOT/'simulation/results/lite_l1_20261025/source-guard.json')
    changed=[p for p,h in guard.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
    base.save(OUT/'source-verification.json',{'checked':len(guard),'changed':changed,
        'allowed_change':'shared display-only conditions.py explicitly authorized by user',
        'passed':all(Path(p).name=='conditions.py' for p in changed)})
    doors=read(OUT/'door-classification.json')['rows'];counts=Counter(d['door_class'] for d in doors)
    before=read(ROOT/'simulation/results/lite_l1c_20261025/trigger_only/standard/result.json')
    after=read(OUT/'validation/3F/result.json');b3=read(OUT/'validation/B3/result.json')
    b3old=read(ROOT/'simulation/results/lite_l1b_20261025/isolation/B3/comparison.json')
    sample_record=next(iter(after['shared_conditions']['rooms'].values()))
    bd_terms={v['key']:v['threshold'] for v in sample_record['backdraft']['terms']}
    def bd_count(r,path):
        y=np.load(path)['y'];n=len(r['room_summary'])
        # Same displayed BD criteria on both saved states. Old fuel inventory
        # remains unqualified; this is only a controlled diagnostic comparison.
        mask=(y[2*n:3*n]-273.15>=bd_terms['Tu'])&(y[6*n:7*n]>=bd_terms['Yf'])&(y[4*n:5*n]*29/32<bd_terms['O2']/100)
        return len({r['room_summary'][i]['original_room'] for i in range(n) if mask[i].any()})
    bd_before=bd_count(before,ROOT/'simulation/results/lite_l1c_20261025/trigger_only/standard/state.npz')
    bd_after=bd_count(after,OUT/'validation/3F/state.npz')
    reaction=[]
    for s in rows:
        r=read(OUT/'mc'/s['sample_id']/'result.json')
        reaction.append({'sample_id':s['sample_id'],'complete':s['complete'],
            'upper_heat_MJ':r['upper_combustion']['cumulative_heat_MJ']})
    base.save(OUT/'upper-reaction-summary.json',reaction)
    times=[r['times']['total_s'] for r in rows]
    lines=['간략 엔진 L1e — §1.5 구현·시험 결과 (2026-10-25)',
        '최신 로컬 명세 1.5.1~1.5.7 + 사용자 FO 연료·산소/FGI 온도 정의 적용.',
        '점수는 설정 조건의 충족 정도이며 발생 확률·발생 시각 예측이 아니다.', '',
        '1. 결론',
        f"20표본: 완료 {a['completed']}, 실패/미완료 {a['failed_or_incomplete']}, 수치 관문(실패≤1) {a['numerical_gate_passed']}.",
        f"전체 {a['wall_seconds']:.1f}s, 4병렬. 표본 벽시간 min/median/max = {min(times):.1f}/{np.median(times):.1f}/{max(times):.1f}s.",
        f"Radau 대체 {a['solver_fallback_count']}건. 시간초과에는 재시도하지 않았다. 실패는 안전/0위험으로 세지 않았다.",
        '미완료 표본/마지막 안전 출력(s): '+', '.join(f"{r['sample_id']}={r['safe_end_s']:g}" for r in rows if not r['complete']),
        f"완료 표본의 실제 연소 실 최대 {max(len(r['burning_original_rooms']) for r in rows if r['complete'])}실. 미완료 표본의 중간 실수를 완료 실적으로 합치지 않는다.",
        f"출력 에너지 진단 불합격: {a['output_diagnostic_failures']}. 질량 잔차는 보고만 하며 원인 분리·수락 스텝 보존 인증은 하지 않았다.",
        '기존 L1d는 20중14완료/6실패, 1385.260s. 새 집계는 분류·개폐조합도 달라져 순수 속도 개선비가 아니다.',
        f"기존 완료14건 에너지 기준 재집계: 진단 실패 {old['output_diagnostic_failures']}. 기존 FGI·백드래프트·롤오버는 미평가.", '',
        '2. 동일 3F 표준 입력 검증 (문 자동 분류 적용 전)',
        'L3: CFAST 표준 ⊆ 간략 ⊆ CFAST 공격 및 동시군 착화 순서 관문 통과.',
        'native 공격은 2850s까지의 부분 결과만 참조했다. 3600s native 완료로 보지 않는다.',
        '항목 | 변경 전 | 변경 후',
        f"적분(s) | {before['integration']['wall_seconds']:.3f} | {after['integration']['wall_seconds']:.3f}",
        f"실제 고체 연소 원래실 수 | {len({r['original_room'] for r in before['room_summary'] if r['actual_peak_kW']>0})} | {len({r['original_room'] for r in after['room_summary'] if r['actual_peak_kW']>0})}",
        f"추가 상층 누적 발열(MJ) | OFF | {after['upper_combustion']['cumulative_heat_MJ']:.8g}",
        f"동일 BD 기준({bd_terms})의 진단 실수 | {bd_before} | {bd_after}",
        '변경 전 BD는 상층 연료 재고 미검증 상태의 진단값이며, 유효 위험도 집계에는 쓰지 않는다.',
        '실제 발열 양수인 실만 연소로 센다. 조건 충족이나 공급 등록과 구분한다.',
        f"B3 단독: native R1 최고 {b3old['native_peak_upper_C']:.3f}℃, 이전 lite {b3old['lite_peak_upper_C']:.3f}℃, 새 lite {b3['room_summary'][0]['upper_max_C']:.3f}℃.",
        f"B3 적분 {b3['integration']['wall_seconds']:.3f}s, 상층 추가 발열 {b3['upper_combustion']['cumulative_heat_MJ']:.8g}MJ.",
        '단독·표준 사례에서 반응량이 0이면 반응 효과 검증으로 주장하지 않는다. 양의 반응은 별도 RHS/재고·화학량론 단위 검사로 확인했다.', '',
        f"MC에서 상층 발열 양수인 완료 표본: {sum(r['complete'] and r['upper_heat_MJ']>0 for r in reaction)}건. 전체 관측 최대 누적발열 {max(r['upper_heat_MJ'] for r in reaction):.8g}MJ.",
        '3. 수치 실패 격리',
        '5건을 기존 식으로 재현했다. 저장값은 마지막 RHS 시도 상태와 마지막 완료된 구간의 끝 상태다.',
        '실패 구간 내부의 마지막 수락 스텝이 아니다. 비유한 Newton/Jacobian 시도 값을 물리 상태로 해석하지 않는다.',
        '표본 | 완료 | 적분(s) | 마지막 RHS 시각 | 유한 여부 | 직전 완료구간 시각 | clip 실']
    for folder in sorted((OUT/'isolation').iterdir()):
        s=read(folder/'summary.json');trial=read(folder/'last_trial_state.json');prev=read(folder/'failed_segment_start.json')
        clipped=[r['cell'] for r in prev['rooms'] if r['at_lower_clip'] or r['at_upper_clip']]
        lines.append(f"{folder.name} | {s['complete']} | {s['integration']['wall_seconds']:.2f} | {trial['time_s']:.3f} | {trial['finite']} | {prev['time_s']:.3f} | {','.join(clipped)}")
    lines+=['clip 접촉과 유한차분 Jacobian overflow가 함께 관측됐다. clip만이 유일 원인이라는 증명은 아니다.',
        'softplus 폭=상태 atol의10배. 추가 반응은 시도 dt가 아닌 기존 재고/20s와 산소 제한으로 정한다.',
        '주 연소가 상층에서 쓸 산소를 같은20s 지평으로 예약한 나머지만 추가 연소에 사용한다.',
        '같은 반응량으로 연료−ξ, 산소−sξ, 열+Hcξ. 전체 질량·고체 HRR·복사 공급에 다시 더하지 않는다.',
        'τ20s 및 예약 지평은 프로젝트 근사. 순정 CFAST 상층/문 분출 상세반응과 동등하지 않다.', '',
        '4. 문 자동 분류',f"총 {len(doors)}개: {dict(counts)}. 문별 근거 전체는 door-classification.csv.",
        'ELEV.홀을 승강장 별칭으로 인식한다. R2 이름에 ELEV.홀/Assembly Line 등이 섞여 있어 과분류 가능성이 있다.',
        '규칙상 확정은 법정 방화 성능 확인이 아니다. 분류 버튼/3D 기호로 정정하면 저장 후 다음 탐색에 우선 적용된다.',
        'r8 공유 전이 그래프는 방화문 간선을 열림 여부와 무관하게 제거한다. 실제 유동은 개폐 상태를 따르므로 두 역할이 다르다.',
        '이는 열린 방화문을 통한 화염 전이를 과소 평가할 수 있는 기존 규칙 한계다. 동결 r8을 이번에 바꾸지 않았다.', '',
        '문 ID | 연결 실 | 분류 | 규칙 | 근거']
    lines += [f"{d['id']} | {d['a']} ↔ {d['b']} | {d['door_class']} | {d['rule']} | {d['reason']}" for d in doors]
    lines+=['','5. 공통 조건표와 MC 집계',
        'FO: 상층온도/기준, (실제 고체+상층 발열)/Thomas 필요발열, 하층 O2/LOC.',
        'FGI: 상층온도/gas.hot_C, Yf/기존 fire_zone LFL(T), 상층산소/기존 기준. 백드래프트 산소는 LOC/현재농도로 역수.',
        'LFL(T)는 기존 LFL0_hrr/Hc*clip(1-(T_K-293)/1300,.2,1) 근사이며 실제 혼합 연기의 실측 가연한계가 아니다. 혼합 Hc 입력은 미평가.',
        '입력의 기존 공통 조건표는 FGI/BD 산소 기준10vol%, FO/상층반응은 gas LOC12vol%다. 기존 조건 유지 요청에 따라 하나의12%로 몰래 통일하지 않았다.',
        '명세의 FGI/BD 설명 표에 적힌 LOC12%와 기존 입력10%의 차이를 검토 시 주의할 것. 실제 사용값은 각 결과 terms/scores에 저장했다.',
        'degree=min(T,F,O); 미정 요인이 있으면 unknown. 최대·중앙값은 전체 유한 셀-시점 점수의 요약(미충족 시점 포함).',
        '점수/기존 맥락 bool/실제 추가연소량을 따로 저장한다. 전이 트리거에는 되먹임하지 않는다.',
        '피난한계는 기존 온도·연기층 높이식. PPE/FED/시정 기준은 이번에 구현한 것이 아니다.',
        '현상 | 완료 무작위 표본 충족수/분모 | 점수 중앙값들의 중앙값 | 최대 | 최악 표본/실수/첫시각']
    for name,v in a['condition_sample_rates_random_only'].items():
        w=a['worst_including_mandatory'].get(name) or {}
        lines.append(f"{name} | {v.get('numerator')}/{v.get('denominator_completed_random')} | {v.get('median_of_sample_medians')} | {v.get('maximum_score')} | {w.get('sample_id')}/{w.get('ever_room_count')}/{w.get('first_s')}")
    lines += [f"경계 실-표본 쌍: {a['boundary_room_sample_pairs']}",
        '강제 표본2건과 실패는 확률 분모에서 제외하고 별도 표시. 불완전 표본이 있어 전체 최악을 확보했다는 뜻은 아니다.',
        'S01 개방 시 위험 시간 구간은 mc/S01/summary.json의 opening_risk. 실제 문 개방/폭압을 계산한 것이 아니다.', '',
        '6. 파일·화면·검증',
        '공통 조건표: simulation/pyrocast_cfbt/conditions.py. native 엔진/솔버/r8 전이 계산은 불변.',
        f"기존 source guard {len(guard)}파일 중 변경 {changed} (사용자 승인된 표시용 공통 조건표).",
        '29개 lite 검사 통과. 원본 fire_zone.py 및 CFAST 실행파일 수정/새 native 실행 없음.',
        '3D에는 문 분류 목록·근거·저장 정정 UI를 추가했다. 재생 시뮬레이션은 기존 저장 결과를 유지한다.',
        '새 MC20 결과를 기존 3D 화재 재생으로 바꿨다고 표시하지 않는다.',
        '결과 폴더: simulation/results/lite_l1e_20261025. 표본별 result/summary/state/manifest, 실패 시도와 개폐조합 보존.',
        '전처리 시간은 이번 MC에서 별도 측정하지 못했다. total·integration·postprocess만 기록하며 나머지는 전처리+입출력 등이 섞였다.',
        '추가 표본 확대·재시도·기준 완화는 하지 않았다.']
    report=ROOT/'specs/간략엔진-L1e-조건점수·문분류·MC20-시험결과-20261025.txt'
    report.write_text('\n'.join(lines)+'\n','utf-8')
    handoff=ROOT/'SESSION_HANDOFF.txt'
    header=(f"최신 2026-10-25 / 간략 L1e §1.5 완료 / MC20 완료{a['completed']}·미완료{a['failed_or_incomplete']}·수치관문{'통과' if a['numerical_gate_passed'] else '실패'}\n"
        "- 사용자 최신24899바이트 로컬명세 §1.5.1~1.5.7 및 FO/FGI 추가 정의 적용. 순정 엔진·r8 전이·원본 fire_zone 불변. 공통 conditions.py 표시 점수 변경은 사용자 명시 승인.\n"
        "- softplus 폭10atol, built-in BDF, singular만Radau1회. τ20s 상층 재고 반응/주연소 산소예약/같은ξ 열·O2·연료 처리. 가스반응 근사는 순정 문분출 구현과 동등하지 않음.\n"
        f"- 기존5singular 재현; 마지막RHS시도와직전완료구간 상태/개구부 저장. 수락스텝 최종상태라고 주장하지 말것. MC {a['wall_seconds']:.1f}s/4병렬, 실패{a['failed_or_incomplete']}, fallback{a['solver_fallback_count']}. 자동추가시행없음.\n"
        "- 3F 원래문분류 입력 L3 통과:151.394s/8실, 순서동일. native공격 공통2850s만 비교. B3단독1.515s/903.636C. 두 검증사례 상층추가발열0이므로 반응효과로 BD과다판정이 해결됐다고 주장하지 말것.\n"
        f"- MC 상층발열 양수 완료표본 {sum(r['complete'] and r['upper_heat_MJ']>0 for r in reaction)}건. 상세 upper-reaction-summary.json. 실패표본 제외로 전체최악 보증불가.\n"
        "- 조건표 점수=min(T,F,O),3요인AND/기존context bool별도. FO Thomas내부표면적에서개방면적제외+실제고체/상층HRR+하층O2. FGI gas.hot_C+legacy온도의존LFL(혼합Hc unknown). 물리전이에는피드백없음.\n"
        "- 같은seed20261025, 자동방화문19/일반4(이전18/5발언정정). 규칙2=18,규칙3=1. ELEV홀 OCR오염과과분류주의. AUDIT_PASS3alwaysopen. r8는열린방화문도전이간선제거(유동은따름)한계보존.\n"
        "-3D 문분류/근거/정정목록과기호 연결. /cfbt/lite/doors 저장은 simulation/config/lite-door-overrides.json. 시뮬재생은기존enriched_floor60_v7, 새MC로교체안함. 서버PID25304/8780 유지.\n"
        "- tools/refresh_lite_l1e_scores.py로 저장상태만최신점수재집계. 상태파일SHA불변. result.json/summary/aggregate가최종점수, BDF내result는실행당시초안점수(physics동일). 원시시도보존.\n"
        "- 검증29건 통과, JS2파일구문검사통과. 보고 specs/간략엔진-L1e-조건점수·문분류·MC20-시험결과-20261025.txt. 결과 simulation/results/lite_l1e_20261025.\n"
        "- 다음은검토후결정. 표본확대/실패재실행/임계값튜닝/정밀모드수정 하지말것.\n\n")
    oldtext=handoff.read_text('utf-8')
    if not oldtext.startswith('최신 2026-10-25 / 간략 L1e'):handoff.write_text(header+oldtext,'utf-8')
    readme=ROOT/'simulation/pyrocast_lite/README.txt'
    text=readme.read_text('utf-8').replace('현재 상태(1.4절 적용):','이전 상태(1.4절 기록, 아래 §1.5로 대체):')
    readme.write_text(text,'utf-8')
    with (OUT/'sample-summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['sample','complete','safe_end_s','solver_fallback','total_s','integration_s','mass_percent','energy_percent','burning_rooms','FO','FGI','backdraft','rollover','boundary_rooms'])
        for r in rows:
            w.writerow([r['sample_id'],r['complete'],r['safe_end_s'],r['solver_fallback'],r['times']['total_s'],r['times']['integration_s'],r['balance_diagnostic']['mass_percent'],r['balance_diagnostic']['energy_percent'],len(r['burning_original_rooms']),*[r['phenomena'][k].get('ever_room_count') for k in ('FO','FGI','backdraft','rollover')],r['boundary_room_count']])
    print(report)
if __name__=='__main__':main()
