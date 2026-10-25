"""Report the one v5 run; read saved trajectories, no solve_ivp calls."""
import json
import numpy as np
import run_lite_l1 as base
from pyrocast_lite.adapter import prepare

OUT=base.ROOT/'simulation/results/lite_v5_sparse_20261025'
REF=base.ROOT/'simulation/results/lite_l1e_20261025/validation/3F'
REPORT=base.ROOT/'specs/간략엔진-v5-누적상태제거·희소패턴-시험결과-20261025.txt'
def read(p):return json.loads(p.read_text('utf-8'))

def main():
    s=read(OUT/'summary.json');p=read(base.ROOT/'simulation/results/lite_v4_profile_20261025/summary.json')
    c=s['counters'];oldc=p['counters'];comparison=s['comparison'];sp=read(OUT/'static-sparsity.json')
    result=read(OUT/'result.json');oldresult=read(REF/'result.json')
    a=np.load(OUT/'state.npz');b=np.load(REF/'state.npz');n=40;oldphys=np.delete(b['y'],8*n,axis=0)
    raw=read(OUT/'input.json');params=read(OUT/'started.json')['parameters']
    old,_=prepare(raw,{**params,'remove_cumulative_state':False});new,_=prepare(raw,params)
    # Same stored state and activation history, testing the RHS mapping only.
    initial=old.activation.copy();max_rhs=0.;all_rhs_equal=True
    for j,t in enumerate(b['t']):
        activation={**initial,**{e['room']:e['condition_time_s'] for e in oldresult['events'] if e['condition_time_s']<=t}}
        old.activation=activation.copy();new.activation=activation.copy()
        lhs=np.delete(old.rhs(float(t),b['y'][:,j]),8*n);rhs=new.rhs(float(t),oldphys[:,j])
        max_rhs=max(max_rhs,float(np.max(abs(lhs-rhs))))
        all_rhs_equal=all_rhs_equal and np.array_equal(lhs,rhs)
    extrema={}
    for label,start,end in [('upper_K',2*n,3*n),('lower_K',3*n,4*n)]:
        diff=abs(a['y'][start:end]-oldphys[start:end]);i,j=np.unravel_index(diff.argmax(),diff.shape)
        extrema[label]={'cell':result['room_summary'][i]['cell'],'time_s':float(a['t'][j]),
            'old_C':float(oldphys[start+i,j]-273.15),'new_C':float(a['y'][start+i,j]-273.15),'delta_C':float(diff[i,j])}
    evidence={'static_checks':36,'stored_state_rhs_samples':len(b['t']),
        'same_physical_rhs_at_identical_state_and_activation':bool(all_rhs_equal),'max_rhs_abs_difference':max_rhs,
        'temperature_difference_extrema':extrema,'additional_simulations':0,'adopted':False,'stopped':True}
    base.save(OUT/'report-evidence.json',evidence)
    result['validation_status']={'scope':'v5 section3.0a-3 trial only','gate_passed':comparison['gate_passed'],
        'adopted':False,'report':str(REPORT)}
    base.save(OUT/'result.json',result)
    ratio=oldc['profiled_integration_s']/c['profiled_integration_s']
    lines=[
        'v5 §3.0a-3 — 累積状態 제거·희소 패턴 정정 / 2026-10-25',
        '결론: 속도는 개선됐으나 엄격한 동일성 기준 불합격. 실험 옵션으로 보관하고 보고 후 정지.',
        '현행 명세: specs/Claude명세-확정상태-v5-20261025.md (16,101바이트). 적용 범위는 3.0a의 3번 하나뿐.',
        '',
        '1. 적용 범위',
        '- remove_cumulative_state=True일 때 누적 공급 에너지 E 한 개를 적분 상태에서 제거했다. 현재 어댑터의 다른 상태는 실별 물리량·벽 온도이며 별도의 합계 상태는 없다.',
        '- 공급 곡선은 시간·확정된 전이 이벤트로 정해지고 누적 E를 참조하지 않는다. 원본 fire_zone의 E 기반 감쇠 기능은 기존 경로에 보존했다.',
        '- 에너지는 10초 출력 시각의 RHS Qp(공급)와 Q(실제 연소)를 사다리꼴 적분해 cumulative_energy에 저장한다. 물리 계산으로 되먹임하지 않는다.',
        '- 희소 패턴은 각 실의 8개 상태와 직접 연결된 이웃 실, 같은 실의 벽 노드만 연결한다. 전역 E 행·열을 제거했다. 벽 상태 인덱스와 후처리 장부 인덱스도 같이 정정했다.',
        '- 산소 재고 OFF, 기존 층별 산소·LOL 유지. BDF/rtol1e-4/남은 상태의 atol/10초 출력/수식/전이값/재시작 방식 유지.',
        '- 해석적 야코비안·재사용 주기·numba·이벤트 연속화는 적용하지 않았다.',
        '',
        '2. 검사 및 단일 실행',
        '- 관련 단위 검사 36건 통과. 신규 검사: 같은 상태의 RHS와 E 독립성, 삭제 후 atol 일치, 관측한 유한차분 의존성이 희소 패턴 밖에 없는지 검사.',
        f'- 저장된 기존 3F 출력 상태 {len(b["t"])}개에서 같은 이벤트 이력을 넣어 물리 RHS를 대조: 완전 일치={all_rhs_equal}, 최대 절대차={max_rhs:g}. 이 대조는 저장값의 RHS 평가이며 추가 적분이 아니다.',
        '- 3F 표준 3600초를 직렬 1회 완료. 계측 방식은 v4와 동일(cProfile+RHS/Jac wrapper), 계산 예산 1200초.',
        f'- 전체 manifest 동일={comparison["manifest_identical"]}. 실행 중 감시 코드 파일 {s["guarded_file_count"]}개 추가 변경 없음={s["guarded_files_unchanged"]}.',
        '',
        '3. 성능 비교 (양쪽 모두 계측 포함)',
        '항목 | v4 기존 | v5 이번',
        f'적분 시간(s) | {oldc["profiled_integration_s"]:.3f} | {c["profiled_integration_s"]:.3f}',
        f'상태 수 | 441 | {sp["state_count"]}',
        f'열 묶음 수 | 441 | {sp["column_groups"]}',
        f'전체 RHS 횟수 | {oldc["rhs_calls"]} | {c["rhs_calls"]}',
        f'RHS 평균(ms) | {oldc["rhs_mean_ms"]:.4f} | {c["rhs_mean_ms"]:.4f}',
        f'야코비안 계산 횟수 | {oldc["jac_calls"]} | {c["jac_calls"]}',
        f'야코비안 1회당 RHS | {oldc["rhs_jac_calls"]/oldc["jac_calls"]:.2f} | {c["rhs_jac_calls"]/c["jac_calls"]:.2f}',
        f'야코비안 시간(s) | {oldc["jac_seconds"]:.3f} | {c["jac_seconds"]:.3f}',
        f'수락 스텝 | {oldc["accepted_steps"]} | {c["accepted_steps"]}',
        f'이벤트 재시작/입력절점 | {oldc["event_restarts"]}/{oldc["input_knot_restarts"]} | {c["event_restarts"]}/{c["input_knot_restarts"]}',
        f'이번은 약 {ratio:.2f}배 속도, 적분 시간 {100*(1-1/ratio):.2f}% 감소. 각 1회 비교이므로 일반적인 속도 보증은 아니다.',
        '열 묶음은 107개로 줄었으나 수십 개라는 기대에는 미달한다. Jacobian 비용 1/10 이하 및 적분 15~30초 예상도 이번 측정에서는 달성하지 못했다.',
        f'이번 전처리 {s["times"]["preprocess_s"]:.3f}초, 후처리 {s["times"]["postprocess_s"]:.3f}초. 비계측 기존151.394초는 참고이며 공정한 주 비교는 계측170초 대51초다.',
        '',
        '4. 동일성 판정: 불합격',
        '- 상태 비교에서는 삭제한 E만 제외하고 남은 물리 상태를 같은 출력 시각끼리 비교했다. 후처리 에너지와 기존 적분 E는 동일성 관문의 상태 비교 대상이 아니다.',
        '- 실제 연소 집합은 같은 8실(R2,R1,R6,R7,R8,R9,R11,R23). 첫 실제 HRR 출력 시각은 R2 10초/나머지2110초로 모두 같다. R17은 실제 연소 0 유지.',
        f'- 내부 이벤트 시각 최대 차이 {max(abs(e["condition_time_difference_s"]) for e in comparison["event_time_differences"]):.9f}초. 출력 격자상 첫 연소가 같아도 정확한 이벤트 시각은 동일하지 않다.',
        '- 최대 상대차 정의: abs(new-old)/max(abs(old),1e-12), 각 상태·출력 시각별. 거의 0인 연료 상태에서는 상대차가 커질 수 있어 절대차도 함께 보고한다.',
        f'- 최대 상대차 {comparison["max_relative_state_difference"]:.9g}; 요구 1e-6 초과. 온도만 보아도 불합격이므로 0 근처의 분모 문제만은 아니다.',
        '상태 블록 | 최대 절대차(각 상태 단위) | 최대 상대차',
    ]
    for label,d in comparison['state_difference_by_block'].items():
        lines.append(f'{label} | {d["max_abs"]:.9g} | {d["max_relative"]:.9g}')
    for label,d in extrema.items():
        lines.append(f'{label} 최대차 위치: {d["cell"]}, {d["time_s"]:g}초, 기존 {d["old_C"]:.6f}℃ → 이번 {d["new_C"]:.6f}℃, 차이 {d["delta_C"]:.6f}℃.')
    lines += [
        '- 수식의 RHS가 같아도 상태 제거·유한차분 그룹 변경으로 적응 적분 경로가 달라질 수 있다. 수락 스텝과 이벤트 시각 변화가 실제 관측됐다. 이번 큰 국부 차이의 원인을 이것만으로 확정하지는 않는다.',
        '- 허용 오차를 줄이거나 기준을 완화해 다시 돌리지 않았다. 요구한 1회 결과 그대로 불합격을 기록한다.',
        '',
        '5. 누적 에너지 후처리',
        f'- 새 누적 공급 에너지 최종값: {result["cumulative_energy"]["supply_J"][-1]:.6f} J. 기존 적분 E: {b["y"][8*n,-1]:.6f} J.',
        '- 두 값 차이는 출력 사다리꼴 적분과 실제 전이 시간 차이를 모두 포함한다. 보존 잔차나 물리 에너지 손실로 단정하지 않는다.',
        '',
        '6. 정지 상태',
        '- 후보 옵션 기본 OFF. 기존 경로를 보존했고 새 결과를 운영 3D/MC에 채택하지 않았다.',
        '- 다음 최적화·재실행·문 분출 연소·방화문 재분류·MC·UI 변경 없음. 사용자 요청대로 3.0a-3 보고 후 정지.',
        '결과: simulation/results/lite_v5_sparse_20261025/',
        'summary.json: 엄격한 동일성/시간/이벤트 비교. functions.json/integration.prof: 프로파일. report-evidence.json: 저장 상태 RHS 대조.',
        '실행 tools/profile_lite_v5_stage3.py. 보고 tools/report_lite_v5_sparse.py (새 적분 없음).',
    ]
    lines[0]='v5 §3.0a-3 — 누적 상태 제거·희소 패턴 정정 / 2026-10-25'
    REPORT.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    note='''최신 2026-10-25 / v5 §3.0a-3 1회 완료 / 속도개선·엄격동일성불합격·정지
- 현행 specs/Claude명세-확정상태-v5-20261025.md(16101B). 누적E제거+국소희소패턴만, remove_cumulative_state=True 실험옵션. 산소재고OFF, 기본경로보존(옵션기본OFF).
- 3F3600s 직렬1회51.043s(계측포함), v4동일계측169.976s 대비3.33배. 상태441→440, 열묶음441→107, RHS151209→43244, Jac당RHS452.13→113.06, Jac325→344/시간163.639→44.614s. 스텝1225→1219.
- 8연소실/첫HRR출력시각동일, 내부이벤트최대3.20953s차. 상태최대상대차20.1746>1e-6; 상층최대차51.4666C(R11,2240s),하층54.3399C(R1_C7,2440s). 엄격동일성실패. 기준완화/재실행없음.
- 36검사통과. 저장기존3F361상태의동일활성이력/RHS에서E제외물리미분완전동일. 시간적분결과동일은아님. 새물리식을추가하지않음.
- E는출력RHS Qp/Q 사다리꼴누적후처리; 적분제어에는안씀. 벽offset정정. 기존legacy에너지감쇠/산소재고옵션보존. 운영3D/MC미채택.
- 결과 simulation/results/lite_v5_sparse_20261025. 보고 specs/간략엔진-v5-누적상태제거·희소패턴-시험결과-20261025.txt. 추가최적화/계산금지,보고후정지.

'''
    target=base.ROOT/'SESSION_HANDOFF.txt';text=target.read_text('utf-8')
    if not text.startswith(note.splitlines()[0]):target.write_text(note+text,encoding='utf-8')
    print(json.dumps({'report':str(REPORT),'same_rhs':bool(all_rhs_equal),'gate':comparison['gate_passed'],'stopped':True},ensure_ascii=False))

if __name__=='__main__':main()
