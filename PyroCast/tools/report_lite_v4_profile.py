"""Saved profile + static sparsity inspection only. Does not run a solver."""
import json
from pathlib import Path
import run_lite_l1 as base
from pyrocast_lite.adapter import prepare
from scipy.optimize._numdiff import group_columns

OUT=base.ROOT/'simulation/results/lite_v4_profile_20261025'
REPORT=base.ROOT/'specs/간략엔진-v4-3.0a-프로파일1회-20261025.txt'
def read(p):return json.loads(p.read_text('utf-8'))

def main():
    s=read(OUT/'summary.json');c=s['counters'];wall=c['profiled_integration_s']
    model,_=prepare(read(OUT/'input.json'),read(OUT/'started.json')['parameters'])
    matrix=model.sparsity();groups=group_columns(matrix);energy=8*model.N
    static={'state_count':matrix.shape[0],'nnz':matrix.nnz,'column_groups':int(groups.max()+1),
        'energy_row_index_zero_based':energy,'energy_row_nonzero':matrix[energy,:].nnz,
        'energy_column_nonzero':matrix[:,energy].nnz,'solver_runs_in_this_report':0}
    base.save(OUT/'static-sparsity.json',static)
    lines=[
        'v4 §3.0a 프로파일 1회 — 2026-10-25',
        '결론: 수치 야코비안 구성을 위한 대량 RHS 평가가 지배한다. 측정만 하고 정지했다.',
        '현행 명세: specs/Claude명세-확정상태-v4-20261025.md. 사용자 요청: 프로파일 1회만, 산소 재고 OFF.',
        '',
        '1. 범위와 동일성',
        '- 3F 표준 3600초, 10초 출력, BDF/rtol1e-4/기존 atol/희소 패턴 유지. 상태 441개, 40셀.',
        '- oxygen_inventory_mode=False. 층별 산소/LOL 유지, smooth_state_bounds=True, upper_combustion_enabled=True. 재고 모드는 옵션 보관.',
        '- 단일 프로세스/직렬 1회. 계산 예산 1200초. native/MC/3D/문 분출 연소/최적화 실행 없음.',
        '- 프로파일 도구 안에서 RHS, num_jac, BDF 초기화에 계측 wrapper를 붙였다. 함수 인수와 반환값은 그대로이며 종료 시 원복했다. 생산 엔진 파일은 수정하지 않았다.',
        f'- 감시 파일 {s["guarded_file_count"]}개 SHA 작업 전후 동일: {s["guarded_files_unchanged"]}.',
        '- 비교 기준: simulation/results/lite_l1e_20261025/validation/3F 저장 결과. 산소 재고 ON의 139초 결과와 비교하지 않는다.',
        f'- 전체 manifest 동일: {s["comparison"]["manifest_identical"]}. 저장 출력격자 및 상태 배열 완전 동일: {s["comparison"]["state_arrays_identical"]}. 최대 상태 차이 0.',
        '- 실제 연소 8실: R2,R1,R6,R7,R8,R9,R11,R23. R2 첫 HRR 10초, 나머지 2110초. 기존 대비 차이 0초. 모든 전이 조건/공급 시작 이벤트 시각 차이도 0초.',
        '- R17은 전이 조건 이벤트만 있고 실제 HRR 0인 기존 결과 그대로다.',
        '',
        '2. 시간과 호출 수 (적분 구간만 계측, 후처리 제외)',
        f'- 전처리 {s["times"]["preprocess_s"]:.3f}초 / 프로파일 포함 적분 {wall:.3f}초 / 후처리 {s["times"]["postprocess_s"]:.3f}초.',
        f'- 기존 비계측 적분 {s["comparison"]["reference_wall_s"]:.3f}초. 이번 프로파일 시간 증가는 계측 오버헤드와 실행 환경 영향을 포함하므로 성능 악화로 해석하지 않는다.',
        f'- 수락 스텝 {c["accepted_steps"]:,}회. RHS 실제 호출 {c["rhs_calls"]:,}회. RHS 합계 {c["rhs_seconds"]:.3f}초, 1회 평균 {c["rhs_mean_ms"]:.4f}ms(계측 상태).',
        f'- 솔버 nfev {c["reported_nfev"]:,}회는 유한차분용 RHS 호출을 포함하지 않는다. 실제 RHS 횟수와 다름에 주의.',
        f'- 수치 야코비안 계산 {c["jac_calls"]}회 = BDF 초기 {c["jac_initial_calls"]}회 + 구간 내부 재계산 {c["jac_noninitial_calls"]}회. njev 합계와 일치.',
        f'- 야코비안 총 {c["jac_seconds"]:.3f}초 = 전체 적분의 {100*c["jac_seconds"]/wall:.2f}%. 이 시간에는 아래 RHS 평가가 포함된다.',
        f'- 야코비안 내부 RHS {c["rhs_jac_calls"]:,}회({100*c["rhs_jac_calls"]/c["rhs_calls"]:.2f}% 호출), {c["rhs_jac_seconds"]:.3f}초.',
        f'- 야코비안 한 번당 평균 RHS {c["rhs_jac_calls"]/c["jac_calls"]:.2f}회. 차분 보폭 조정에 따른 추가 평가를 포함한다.',
        f'- num_jac 밖 RHS {c["rhs_calls"]-c["rhs_jac_calls"]:,}회 = nfev {c["reported_nfev"]:,} + 각 야코비안 기준점 평가 {c["jac_calls"]}회.',
        f'- LU 분해 {c["reported_nlu"]}회. cProfile splu 누적 0.678초로 야코비안 구성 시간에 비해 작다.',
        '',
        '3. 재시작 구분',
        f'- 전이 이벤트 재시작 {c["event_restarts"]}회. 입력 HRR 절점 재시작 {c["input_knot_restarts"]}회. 최초 포함 BDF 초기화 {c["bdf_initializations"]}회.',
        f'- BDF 초기화 총 {c["bdf_initialization_seconds"]:.3f}초({100*c["bdf_initialization_seconds"]/wall:.2f}%), 이 안의 초기 야코비안 {c["jac_initial_seconds"]:.3f}초.',
        f'- 구간 내부 야코비안 재계산 {c["jac_noninitial_seconds"]:.3f}초. 이벤트 7건이나 초기화만으로 전체 병목을 설명할 수 없다.',
        '- 초기화/야코비안/RHS 누적 시간은 서로 중첩된다. 세 값을 더하면 안 된다.',
        '',
        '4. 함수별 시간 상위 5개 (self time: 호출한 하위 함수 시간을 뺀 값)',
        '함수 | 호출 수 | 자체 시간(s) | 하위 호출 포함(s)',
    ]
    for f in s['top5_self']:
        name=f['function']
        if f['file']!='~':name=Path(f['file']).name+':'+str(f['line'])+' '+name
        lines.append(f'{name} | {f["calls"]:,} | {f["self_seconds"]:.3f} | {f["cumulative_seconds"]:.3f}')
    lines += [
        '전체 순위와 cumulative 순위는 functions.json 및 profile-top.txt, 원시 자료는 integration.prof에 저장했다.',
        '산소 oxygen_factor의 자체 시간은 약 5.703초, 하위 연산 포함 9.959초다. 산소 식만 단순화해 전체 비용 대부분을 없앨 수 있다는 근거는 없다.',
        '',
        '5. 정적 소스 확인으로 드러난 원인 (추가 적분 없음)',
        f'- jac_sparsity를 주고 있지만 실제 열 묶음 수는 {static["column_groups"]}개 / 상태 {static["state_count"]}개다. 즉 열을 함께 교란하는 이점이 없다.',
        f'- core.py sparsity의 E 행/열 전체 True와 adapter.py 벽 연결로, 누적 에너지 E의 {energy}번 행(0부터)에 {static["energy_row_nonzero"]}개 열이 모두 표시된다. E 열도 {static["energy_column_nonzero"]}개 행을 연결한다.',
        '- 모든 열이 공통 E 행에 걸리므로 SciPy group_columns는 같은 그룹으로 묶을 수 없다. 희소 행렬 저장·LU 사용과 유한차분 평가 횟수 감소는 별개다.',
        '- 관측 결론: RHS 1회가 약 104ms인 것이 아니다. 여러 RHS 평가와 야코비안 비용을 나눈 스텝당 평균을 단일 RHS 비용으로 해석하면 안 된다.',
        '- 다음 검토 후보: 현재 고정 공급 모드에서 실제 E 의존성을 확인해 보수적인 희소 패턴을 정확히 하거나 해석적 야코비안을 제공하는 방법. 해당 작업은 이번 요청에 포함되지 않아 적용하지 않았다. 야코비안 재사용 주기·솔버·이벤트 로직도 변경하지 않았다.',
        '- 속도 향상 배수는 아직 측정하지 않았다. 후속 변경은 한 종류만 적용하고 동일성/시간을 별도 비교해야 한다.',
        '',
        '6. 정지 및 결과 위치',
        '- 사용자 지시대로 프로파일 1회 후 정지. 다음 최적화, 재실행, MC, 문 분출 연소를 시작하지 않았다.',
        '- v4가 L3 상한을 CFAST 공격의 조건 이벤트 집합으로 바꾼 점은 확인했다. 이번은 기존 결과 동일성 계측이며, 과거 산소 재고 시험을 새 기준으로 재집계하는 작업은 하지 않았다.',
        '결과: simulation/results/lite_v4_profile_20261025/',
        '실행 도구: tools/profile_lite_v4_stage1.py. 보고 도구: tools/report_lite_v4_profile.py(저장 자료/정적 검사만).',
        'started.json/summary.json/counters.json/functions.json/profile-top.txt/integration.prof 및 input/manifest/result/state.npz 보존.',
    ]
    REPORT.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    note='''최신 2026-10-25 / v4 §3.0a 프로파일 1회 완료 / 보고 후 정지
- 현행 specs/Claude명세-확정상태-v4-20261025.md. 산소 재고 OFF, 기존 층별 산소 유지. 이번 범위 프로파일만, 후속 최적화 금지.
- 3F3600초 1회 직렬/BDF/상태441. 계측 포함169.976s. 저장L1e151.394s와 manifest/출력상태배열/이벤트시각 완전 동일. 실제8실, R17미연소. 감시75파일SHA불변.
- RHS151209회/평균1.0914ms, 실제nfev3943과구분. 수치Jac325회(초기62+내부263), Jac시간163.639s=96.27%, 내부RHS146941회/160.278s. LU956회/.678s.
- 이벤트재시작7/입력절점54/BDF초기화62(28.956s). 초기화를제외한Jac135.057s. 정적jac_sparsity441열그룹=441상태, E행/열전체True 때문에열묶음효과없음. 희소패턴/해석Jac는검토후보만,미수정.
- 결과 simulation/results/lite_v4_profile_20261025. 보고 specs/간략엔진-v4-3.0a-프로파일1회-20261025.txt. 재실행/최적화/MC/3D/문분출 없음. 정지유지.
- v4 L3상한이actualHRR집합에서조건통과이벤트집합으로변경됨; 이전산소재고시험은당시기준불합격이력. 이번에재집계안함.

'''
    p=base.ROOT/'SESSION_HANDOFF.txt';old=p.read_text('utf-8')
    if not old.startswith(note.splitlines()[0]):p.write_text(note+old,encoding='utf-8')
    print(json.dumps({'report':str(REPORT),'static':static,'stopped':True},ensure_ascii=False))

if __name__=='__main__':main()
