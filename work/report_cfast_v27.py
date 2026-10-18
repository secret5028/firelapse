from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'outputs/CAD-속도검증-v27';BASE=ROOT/'outputs/CAD-조건부전이-v26'
r=json.loads((OUT/'full-verification.json').read_text('utf8'))
old=json.loads((BASE/'cfast-demo.json').read_text('utf8'))
new=json.loads((OUT/'final/cfast-demo.json').read_text('utf8'))
before={v['key']:v for v in old['rooms']};after={v['key']:v for v in new['rooms']}
r['room_peak_upper_C']={k:dict(baseline=max(x[1] for x in before[k]['series']),candidate=max(x[1] for x in after[k]['series'])) for k in before}
r['target_peaks']=[dict(id=b['id'],baseline_max_surface_C=max(s[1] for s in a['target_series']),candidate_max_surface_C=max(s[1] for s in b['target_series'])) for a,b in zip(old['fires'][1:],new['fires'][1:])]
r['speed_reduction_percent']=100*(1-r['native_timing']['wall_seconds']/r['baseline_wall_seconds'])
r['total_peak_delta_percent']=100*(r['candidate_peak_total_kW']/r['baseline_peak_total_kW']-1)
r['energy_delta_percent']=100*(r['candidate_energy_MJ']/r['baseline_energy_MJ']-1)
(OUT/'full-verification.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),'utf8')
m=r['comparison']['metrics']
peaks='\n'.join(f"- {k}: {r['room_peak_upper_C'][k]['baseline']:.3f} → {r['room_peak_upper_C'][k]['candidate']:.3f} °C" for k in ['3F_R9','3F_R2','3F_R8'])
text=f'''CFAST 성능 비교 v27 — 2026-10-15

요청: CFAST 계산 방식 유지, 느린 항목 점검, 실행시간 단축, 기존 결과와 비교.

실행과 범위
- 원본 CFAST 7.7.7 바이너리 유지. SHA256 {r['native_timing']['signature']['engine_sha256']}
- 100개 계산 구획, 156개 표시 공간, 벽 개구부133개, 수직연결36개 유지.
- v26의 물리 입력 행은 동일: 건물/치수/물성/화재곡선/화원위치/착화조건/개구부/열전달/가스 계산 유지.
- CFAST 자동 오차 허용치는 그대로. &MISC MAX_TIME_STEP=0.25로 최대 시간 간격만 제한.
- 일반문100%, 외부문50%, 창닫힘, 승강기문1%누설, 소화설비 미작동 등 기존 가정 유지.
- 30분 결과를 5초 간격으로 저장(361시점). UI와 CAD 추출/3D 모델은 수정하지 않음.

항목별 확인
1. 엔진 계산: 이전 실행 wall2079.672초 중 native CPU시간2055초. 브라우저 렌더링을 기다리는 시간이 주원인이 아님.
2. 연성 규모: 100구획 압력/상하층/열전달/개구부 유동을 동시에 풀며 추가착화 및 가열구간에서 단계가 세분됨. 소스의 DASSL은 수치 Jacobian 및 dense 선형계를 사용. 구획/계산항목을 삭제하지 않았음.
3. 시간 간격 선택: 동일10분 입력, 출력최적화만293.004초/3109단계 → 상한0.25초194.117초/4213단계(33.75% 단축). 단계 수는 늘었지만 실행시간이 감소. 반복 시도/Jacobian 재계산 각각의 횟수는 계측하지 않았으므로 개별 시간 비중은 확정하지 않음.
4. 상한0.1초: 190.089초/7526단계. 0.25초보다 약2% 빠르지만 원본과 온도/착화시각 차이는 약간 더 큼. 이번에는0.25초 선택. 보편적인 최적 간격이라는 의미가 아님.
5. 출력: PRINT=0, -k, -o:CD 사용. _zone.csv와 compartments/devices를 유지하여 UI와 층간유량/착화검사에 필요한 값 보존. 중복 masses/vents/walls CSV와 주기별 텍스트 출력 생략. 최초10분 시계열은 출력만 변경 시 숫자 차이0.
6. 키보드/IO 단독 개선율: 120초 동일기준 실행도39.064초와31.014초로 변동. 단일쌍의 시간차를 코드 효과로 과대해석하지 않음. DIAG KEYBOARD_INPUT=OFF는 실제 폴링중단과 다르므로 최종에는 native -k 사용.
7. 재실행: 입력+엔진+실행옵션 해시와 결과 파일 해시 일치시에만 캐시 사용. 변경입력/손상출력/강제실행/실패실행 거부 시험 통과. 캐시를 새 물리계산으로 표시하지 않음.

30분 전체 실측
- 기존 v26 native wall: {r['baseline_wall_seconds']:.3f}초 ({r['baseline_wall_seconds']/60:.2f}분)
- 개선 native wall: {r['native_timing']['wall_seconds']:.3f}초 ({r['native_timing']['wall_seconds']/60:.2f}분)
- 기존 저장 실행 대비 단축: {r['speed_reduction_percent']:.2f}%. 전체는 각1회 비교이므로 머신 상태 변동 포함. 별도의 동시점10분 통제시험은 위 수치.
- native CPU: {r['native_timing']['cpu_seconds']:.3f}초, 단계 {r['native_timing']['steps']}
- 같은 조건의 전체 파이프라인 캐시 재실행: {r['cached_invocation_seconds']:.3f}초. 수치 데이터 동일 확인.

기존 v26 대비 전체 시간/공간 차이 (동일한5초 출력 시각)
- 상부층 온도: 최대 {m['upper_C']['max']:.6f}°C, 평균절대차 {m['upper_C']['mae']:.6f}°C
- 하부층 온도: 최대 {m['lower_C']['max']:.6f}°C
- 연기층 경계 높이: 최대 {m['layer_m']['max']:.6f}m
- 상부층 광학밀도: 최대 {m['upper_OD']['max']:.6f}/m
- 하부층 광학밀도: 최대 {m['lower_OD']['max']:.6f}/m
- 착화 대상 표면온도: 최대 {r['comparison']['target_C']['max']:.6f}°C
- 총 HRR 피크: {r['baseline_peak_total_kW']:.3f} → {r['candidate_peak_total_kW']:.3f} kW ({r['total_peak_delta_percent']:+.4f}%)
- 총 HRR 적분: {r['baseline_energy_MJ']:.3f} → {r['candidate_energy_MJ']:.3f} MJ ({r['energy_delta_percent']:+.4f}%)
- 착화 출력시각: {r['ignition_candidate']} (기존과 같음)
- 연기 도달 비교용 OD>=0.01/m 문턱 시각차: {r['comparison']['smoke_arrival_differences']}. 이 문턱은 성능비교용이며 인명안전/진입 판단 기준이 아님.

주요 실의 최고 상부층 온도
{peaks}

재현
- 현재 시나리오: powershell -File work/run_cfast_current.ps1
- 새 실행을 강제하려면 뒤에 --force 추가. 기존 결과는 v26 폴더에 보존.
- cad_cfast_multifloor.py의 기본 가연물 구성은 기존v23이므로 현재v26조건은 위 wrapper처럼 --ignition-config를 명시한다.
- 상세 수치: full-verification.json, final/comparison.json, 각 short-case benchmark.json 및 progress.json.

근거
https://github.com/firemodels/cfast/blob/CFAST-7.7.7/Manuals/CFAST_Users_Guide/Input_File_Chapter.tex
https://github.com/firemodels/cfast/blob/CFAST-7.7.7/Source/CFAST/solve.f90
https://github.com/firemodels/cfast/blob/CFAST-7.7.7/Source/CFAST/utilities.f90

이번 검사는 수치 일관성·실행 성능 비교다. 건물 실제 화재에 대한 물리 검증이나 정확도 보증이 아니다.
'''
(OUT/'속도개선-비교결과.txt').write_text(text,'utf8')
print(json.dumps({k:r[k] for k in ['speed_reduction_percent','cached_invocation_seconds','total_peak_delta_percent','energy_delta_percent']},ensure_ascii=False))
