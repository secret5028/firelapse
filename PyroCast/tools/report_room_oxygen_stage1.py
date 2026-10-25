"""Read saved stage1 results only; no integration or native execution."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'simulation/results/lite_room_oxygen_stage1_20261025'
REPORT=ROOT/'specs/간략산소-3.0-1단계-시험결과-20261025.txt'
def read(p):return json.loads(p.read_text('utf-8'))
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    data=read(OUT/'completed.json');rows=data['rows'];floor=rows[-1]
    olddir=ROOT/'simulation/results/lite_l1e_20261025/validation/3F'
    old=read(olddir/'result.json');new=read(OUT/'3F/result.json')
    manifest_equal=read(olddir/'rule_manifest.json')==read(OUT/'3F/rule_manifest.json')
    started=read(OUT/'started.json')
    frozen_ok=all(sha(Path(p))==v for p,v in started['frozen_sha256_before'].items())
    oldtime=old['integration']['wall_seconds'];newtime=floor['times']['integration_s']
    comparison={'previous_result':str(olddir/'result.json'),'manifest_equal':manifest_equal,
        'previous_integration_s':oldtime,'current_integration_s':newtime,
        'time_reduction_percent':100*(oldtime-newtime)/oldtime,
        'historical_single_run_comparison_only':True,'L3_gate':floor['L3_gate'],
        'frozen_files_unchanged':frozen_ok,'frozen_file_count':len(started['frozen_sha256_before']),
        'stopped_after_stage1':True,'adopted':False}
    save(OUT/'comparison.json',comparison)
    # Correct only labels on the four saved results. Physics and state files stay intact.
    state_hashes={case:sha(OUT/case/'state.npz') for case in ('B1','B2','B3','3F')}
    for row in rows:
        p=OUT/row['case']/'result.json';r=read(p)
        r['revision']='L1_room_oxygen_experimental'
        r['engine_use']='stage1 validation only; not adopted for MC or operational 3D'
        if not r['known_bias'].startswith('[Previous'):
            r['known_bias']='[Previous two-layer oxygen model reference only] '+r['known_bias']
        r['bias_scope']='The previous bias has not been established for the room oxygen inventory model; read the stage1 comparison.'
        r['limits']=[v for v in r['limits'] if 'legacy plume/oxygen/heat-loss' not in v]
        r['stage1_validation']={'L3_passed':False,'adopted':False,'report':str(REPORT),
            'reason':'3F R17 burns outside stored native aggressive comparison set'}
        save(p,r)
    assert all(sha(OUT/case/'state.npz')==v for case,v in state_hashes.items())
    save(OUT/'report-audit.json',{'state_npz_sha256':state_hashes,'physics_reruns':0,
        'metadata_only_correction':True,'current_code_sha256':{p.name:sha(p) for p in (ROOT/'simulation/pyrocast_lite').glob('*.py')}})
    lines=[
        '간략 산소 §3.0 / §8.1 1단계 결과 — 2026-10-25',
        '결론: 네 계산 완주. 3F L3 불합격. 실험 모드로 보관하고 1단계에서 정지.',
        '근거 명세: specs/Claude명세-확정상태-20261025.md (실행 시작 시 14,376바이트)',
        '명세 SHA256: '+started['spec_sha256'],
        '',
        '1. 이번에 바꾼 것',
        '- 간략 엔진에 oxygen_inventory_mode=True를 추가. 실/셀당 mO2 질량 상태 하나만 적분한다.',
        '- ξ=min(공급 연료율+유입 연료율, mO2/(s·10초)). LOL/tanh 산소 연소 게이트를 사용하지 않는다.',
        '- 외기 유입만 산소 질량비 0.23을 사용한다. 실간 유입은 보내는 실의 산소 농도를 운반한다. 모든 실간 유입을 0.23으로 재설정하면 산소가 생성되므로 그렇게 하지 않았다.',
        '- 이미 공급이 시작된 화원에서 유입 연료를 함께 태운다. 공급 연료와 유입 연료를 따로 차감하며, 유입 연료를 새 열분해 질량으로 더하지 않는다. 대기 화원 자동 점화/문 분출 연소는 추가하지 않았다.',
        '- 기존 상층 반응은 온도 조건·연료 혼합시간 20초를 유지하며 주연소가 쓰고 남은 동일 실 산소 예산만 쓴다. 주연소+상층 소비율 ≤ mO2/10초. 같은 반응량으로 연료·산소·열을 계산한다.',
        '- 산소 상태 수: 3실 6→3, 3F 40셀 80→40. 전체 상태 수: 3실 34→31, 3F 441→401.',
        '- 기존 두 층 산소 모드는 보존. 새 모드는 이번 비교에만 명시적으로 켰다. 정밀 모드·전이 기준·부모·지연·공급 곡선·BDF·10초 출력은 유지했다.',
        '- 새 산소 상태 단위는 kg이므로 기존 질량분율 atol에 초기 실 질량을 곱해 단위를 맞췄다. rtol 완화는 하지 않았다.',
        '',
        '2. 네 사례를 직렬로 각 1회 실행 (BDF, 표본당 예산 1200초)',
        '사례 | 시나리오(s) | 전처리(s) | 적분(s) | 후처리(s) | 실제 연소 실/최초 양의 HRR 출력 시각(s)',
    ]
    for row in rows:
        times=row['times'];burn=', '.join(f'{k.replace("CAD_3F_", "")}:{v:g}' for k,v in row['burning_rooms'].items())
        lines.append(f'{row["case"]} | {row["safe_end_s"]:g} | {times["preprocess_s"]:.3f} | {times["integration_s"]:.3f} | {times["postprocess_s"]:.3f} | {burn}')
    lines += [
        '시각은 10초 출력 표본 기준이다. 조건 통과 시각과 공급 시작 시각은 각 result.json/events에 별도 저장했다.',
        'B1: 추가 전이 없음. B2: 추가 전이 없음(기존 경계 사례 과소 기록 유지). B3: R2 930초, R3 830초 실제 HRR>0 지속.',
        'B1/B2 화점실 최고 상층 온도: 437.485 / 550.649 ℃. B3 R1/R2/R3: 678.585 / 830.858 / 931.348 ℃.',
        '',
        '3. 3F 이전 간략 결과와 비교',
        f'저장된 L1e 결과와 rule_manifest 전체 동일: {manifest_equal}. 같은 물리 입력/표준 설정이며 이전 계산을 다시 돌리지는 않았다.',
        '항목 | 이전 L1e(층별 산소) | 이번(실 산소 재고)',
        f'적분 시간 | {oldtime:.3f} s | {newtime:.3f} s',
        f'수락 스텝 | {old["integration"]["accepted_steps"]} | {floor["solver"]["accepted_steps"]}',
        '실제 연소 실 | R2,R1,R6,R7,R8,R9,R11,R23 (8실) | 기존 8실 + R17 (9실)',
        '화점실 밖 첫 양의 HRR 출력 | 2110 s (35분10초) | 2600 s (43분20초)',
        'R2_C1 상층 600℃ 통과 | 2044.623 s | 2534.269 s',
        'R17 최대 실제 HRR / 지속 | 0 kW / 0 s | 928.859 kW / 1000 s',
        f'이번 적분 시간은 이전 단일 기록보다 {comparison["time_reduction_percent"]:.2f}% 짧다. 반복 측정이 아니므로 일반적인 속도 개선율로 보증하지 않는다.',
        '수락 스텝은 오히려 증가했다. 산소 근사만으로 전체 강성이 사라졌다거나 수십 초에 계산된다는 예상은 이번 시험에서 입증되지 않았다.',
        'R17은 이전에도 전이 조건과 공급 시작 이벤트가 있었으나 실제 HRR은 0이었다. 이번에는 연소가 지속된다. 관측된 차이는 전이 그래프 변경이 아니라 산소 제한/연소 응답 변경과 연결된다. 다른 실들도 열응답이 바뀌었으며 세부 원인 분리 시험은 하지 않았다.',
        '',
        '4. L3 관문: 불합격',
        '- 공통 비교 구간 0~2850초. CFAST 공격 결과가 미완료이므로 3600초 완주 결과처럼 외삽하지 않는다.',
        '- 요구: CFAST 표준 연소 집합 ⊆ 간략 표준 집합 ⊆ CFAST 공격 집합, 공통 실 착화 순서 일치.',
        '- 표준 하한(R2)은 포함한다. 하지만 R17이 CFAST 공격 8실 집합 밖에 있어 상한 집합 조건을 위반한다.',
        '- 공통 실의 순서는 일치한다. 동시에 나타나는 실은 같은 시간군으로 비교한다.',
        '- 16실을 만들기 위한 입력/기준 튜닝 없음. L3 실패를 숨기지 않고 현재 시험 상태로 정지한다.',
        '',
        '5. 장부와 검사',
        '사례 | 질량 출력잔차(%) | 에너지 출력잔차(%) | 산소 출력잔차/초기재고(%) | 최저 산소재고(kg)',
    ]
    for row in rows:
        b=row['balance'];lines.append(f'{row["case"]} | {b["mass_percent"]:.6f} | {b["energy_percent"]:.6f} | {b["oxygen_output_residual_percent_initial_stock"]:.6f} | {b["oxygen_stock_min_kg"]:.6f}')
    lines += [
        '에너지 출력진단은 네 건 모두 기존 0.1% 기준 이내다. 질량은 기존 방침대로 보고만 한다.',
        '산소 잔차는 저장된 10초 표본의 유출입·반응률을 사다리꼴 적분한 진단이다. B3 1.157%이며, 출력 적분 오차와 실제 수치 보존 오차를 분리하지 못했으므로 산소 보존 0.1% 인증이라고 주장하지 않는다. 위 최저 재고도 저장 표본 기준이다.',
        '단위 검사: 전체 간략 관련 34건 통과(이번 5건: 상태 축소, 선형 산소 상한/LOL 미호출, 실간 산소 수송 상쇄, 주연소·상층 공유 예산/반응량 일치, 고정 가정 보호).',
        f'정밀/공통 조건표 감시 파일 {len(started["frozen_sha256_before"])}개 작업 전후 SHA 동일: {frozen_ok}.',
        '상층 추가 발열: B1/B2 0, B3 0.464478 MJ, 3F 약 1e-13 MJ(사실상 0). 이번 변경으로 3F 롤오버 발열이 활성화됐다고 해석하지 않는다.',
        '',
        '6. 표시 해석과 남은 한계',
        '- X=mO2/m_room은 질량비다. 실제 산소 부피분율(vol%)과 같지 않다. 이번에는 명세 식대로 공통 조건표에 같은 대용 지표를 넣고 질량비%로 표시했다. 기존 12/10 등의 설정값은 변경하지 않았다. 실제 산소 농도 예측과 혼동하면 안 된다.',
        '- 조건표 호환용 o2_upper_vol/o2_lower_vol 키는 같은 실 대용 지표의 별칭이다. 독립된 상·하층 산소 계산값을 뜻하지 않으며 oxygen_basis/단위에 명시했다.',
        '- 한 실을 셀로 나눈 경우 산소 재고는 계산 셀당 하나다. 온도·유동의 상하층 구분은 계속 유지한다.',
        '- 이전 엔진 편차 문구는 이번 모델의 검증 결과가 아니므로 저장 결과에서 과거 참조로 표시하고 이번 모드는 validation only로 구분했다.',
        '- MC 집계의 폐쇄 위험 구간 코드는 아직 기존 층별 상태 배치를 사용한다. 새 모드의 MC 연결은 이후 단계에서 점검해야 하며 이번에는 실행하지 않았다.',
        '',
        '7. 정지 상태 / 산출물',
        '요청대로 1단계에서 정지. 문 분출 연소, 방화문 재분류, 연기 색/3D, MC는 시작하지 않았다. 새 CFAST 실행 0, MC 0, 병렬 계산 0.',
        '실행: tools/run_lite_room_oxygen_stage1.py (네 번 직렬, 자동 재실행 방지)',
        '보고: tools/report_room_oxygen_stage1.py (저장 결과만 읽음)',
        '결과: simulation/results/lite_room_oxygen_stage1_20261025/',
        '각 사례 input/manifest/result/summary/balance/state.npz와 시작 코드·명세 해시, 비교 및 보고 후 해시를 저장했다.',
        '실행 후 수정은 실험 상태/과거 편차 표시용 메타데이터뿐이다. 물리 재계산은 하지 않았고 state.npz 해시는 유지했다.',
    ]
    REPORT.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    prefix='''최신 2026-10-25 / 확정명세 §3.0 간략 산소 / §8.1 1단계 완료·L3 불합격·정지
- 사용자 요청: 1단계만, 병렬 금지. B1/B2/B3/3F 각1회 직렬 완료. 다음 단계 시작하지 말 것.
- oxygen_inventory_mode=True 실험 옵션: 셀당 mO2 1개, τ10s 선형 상한, LOL OFF. 내부 유입은 donor 산소, 외기만 .23. 기존 상층 반응은 공유 산소 잔여 예산. 기존 모드 보존/새 모드 운영 미채택.
- B1 1.555s 추가전이0; B2 1.650s 추가전이0; B3 3.659s R2 270/R3 370초, 실제연소930/830초. 3F3600초 완주139.074s/9실.
- 이전 L1e 151.394s/8실 대비 R17추가(928.859kW/1000s), 다른실2110→2600초. 전체manifest동일. native공격 공통2850초 집합상한위반으로L3불합격,순서통과. 임계값튜닝/재계산없음.
- 34검사통과. 에너지출력잔차4건<=.1%, 산소10초진단잔차 B3 1.157%/3F .1165%; 수락스텝보존인증아님. 원본/정밀/공통조건표63파일 작업전후불변.
- 실 산소 표시 mO2/mroom은질량비대용값,vol%아님. 조건표의상하층키는같은지표별칭. 기존threshold유지한근사한계명시.
- 결과 simulation/results/lite_room_oxygen_stage1_20261025. 보고 specs/간략산소-3.0-1단계-시험결과-20261025.txt.
- 새모드 MC의 condition_summary 폐쇄위험 상태offset은아직미연결; MC/3D/문분출/방화문후속단계없음. 정지.

'''
    handoff=ROOT/'SESSION_HANDOFF.txt';content=handoff.read_text('utf-8')
    if not content.startswith(prefix.splitlines()[0]):handoff.write_text(prefix+content,encoding='utf-8')
    readme=ROOT/'simulation/pyrocast_lite/README.txt';content=readme.read_text('utf-8')
    note='''2026-10-25 §3.0 stage1: oxygen_inventory_mode=True adds one oxygen mass per solver cell.
Experimental only: 3F 139.074s / 9 burning rooms, L3 failed due to additional R17.
Not adopted for operational 3D or MC. Default previous two-layer oxygen mode remains available.
Report: specs/간략산소-3.0-1단계-시험결과-20261025.txt. Stop after stage1 as requested.

'''
    if not content.startswith(note.splitlines()[0]):readme.write_text(note+content,encoding='utf-8')
    print(json.dumps({'report':str(REPORT),'L3_passed':False,'frozen_unchanged':frozen_ok,'manifest_equal':manifest_equal,'stopped':True},ensure_ascii=False))

if __name__=='__main__':main()
