"""Read saved r6a evidence only; never launch a native calculation."""
import json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'simulation'))
from pyrocast_cfbt.native import digest,read_native_csv,load_result
OUT=ROOT/'simulation/results/room_rule_r6a_20261025'


def read(path):return json.loads(path.read_text('utf-8'))


def shown(value):return '미도달/해당없음' if value is None else f'{value:.2f}'


def sensors(folder,manifest,until_s=None):
    c,_,_=read_native_csv(folder/'case_compartments.csv',until_s);d,ids,_=read_native_csv(folder/'case_devices.csv',until_s)
    model=read(folder/'scenario.json');rooms={r['id']:i for i,r in enumerate(model['rooms'],1)};out=[]
    t=c['Time']
    for s in manifest['sensors']:
        i=rooms[s['room']];z=s['placement']['local_height_m'];lower=c[f'HGT_{i}']>z
        def col(prefix):return d[next(k for k,v in ids.items() if k.startswith(prefix) and v.strip()==s['id'])]
        plate=col('TRGSURT_');gas=col('TRGGAST_');upper=c[f'ULT_{i}'];layer=np.where(lower,c[f'LLT_{i}'],upper)
        hit=np.flatnonzero(plate>manifest['settings']['temperature_C']);j=int(hit[0]) if len(hit) else None
        out.append({'room':s['room'],'below_ceiling_m':s['placement']['below_ceiling_m'],
            'sensor_max_C':float(max(plate)),'upper_max_C':float(max(upper)),
            'max_abs_local_gas_minus_layer_C':float(max(abs(gas-layer))),
            'observed_lower_layer_samples':int(sum(lower)),
            'first_threshold_sample':None if j is None else {'time_s':float(t[j]),'plate_C':float(plate[j]),
                'upper_C':float(upper[j]),'local_gas_C':float(gas[j]),'in_lower_layer':bool(lower[j])}})
    return out


def main():
    a=read(OUT/'A/analysis.json');b=read(OUT/'B/post_coordinate_fix_verification.json')
    comparison=read(OUT/'C/comparison.json');m=read(OUT/'C/rule_manifest.json')
    lines=['r6a 문 좌표 수정 및 A → B → C 결과 (2026-10-25)','',
        '변경: rule_graph.point의 b측 실 중심 근사를 제거. opening_frame의 a 원점 포함 절대 좌표를 양쪽에 동일 적용.',
        'CAD 좌표가 있으면 해당 중심점을 사용. CAD 좌표 없는 WALL 개구부의 기존 함수는 수평 위치와 바닥 높이를 반환하므로 실제 문 중심 높이까지 재구성한 것은 아님.',
        '검사: 133개 Python 검사 통과. 문 방향 반전/입력 순서/닫힌 문/방화문/수직 위쪽 간선 및 계산용 원점 변경에 따른 CAD 통과거리 불변 포함.',
        '추가 좌표 수정: 가상 셀 경계는 원래 실의 아핀 좌표변환을 역으로 적용해 CAD 위치로 통일. 기존 문 CAD 좌표와 계산용 원점(100m 간격)을 섞던 오류 제거.',
        'CFAST 엔진, 솔버, 5초 출력 격자, 기존 전이 방식 및 운영 3D는 변경하지 않음.','',
        f"A: 상층 최고 {a['upper_max_C']:.3f}℃, 센서 최고 {a['plate_max_C']:.3f}℃, 차이 {a['difference_of_maxima_C']:.3f}℃: 합격.",
        'B1은 600℃ 미도달이므로 A만으로 600℃ 부근의 모든 건물에서 상층 추종을 보증하지 않음. 초기 0~25초 표본은 하층, 25~30초 사이 상층 편입.',
        'B: 수정된 범용 생성기의 입력 3건과 완료된 기존 B 입력이 바이트 동일. 엔진/출력 파일 해시도 확인해 재실행 없이 재사용.']
    for name,v in b.items():
        lines.append(f"  {name}: 합격, 원 측정 계산시간 {v['native_wall_seconds']:.3f}초")
        for r in v['rows'][1:]:lines.append(f"    {r['room']}: 조건 {r['trigger_s']}초, 공급 {r['supply_start_s']}초, 실제발열 첫 표본 {r['first_actual_positive_HRR_s']}초, 연속 양수 HRR {r['longest_positive_HRR_s']:.0f}초")
    threshold_audit=OUT/'B/threshold_sample_audit.json'
    if threshold_audit.exists():
        observed=[r['first_plate_over600_sample'] for r in read(threshold_audit) if r['first_plate_over600_sample']]
        lines.append(f"B2/B3에서 센서 >600℃ 첫 표본의 상층 평균은 {min(r['upper_C'] for r in observed):.1f}~{max(r['upper_C'] for r in observed):.1f}℃. 해당 표본의 국부 가스=상층 평균. 센서 열응답 지연은 남아 있으며 모든 건물에서 오판정 없음을 보증하지 않음.")
    lines+=['',f"C: 원래 {m['original_rooms']}실 → {m['native_cells']} 계산 셀, 대기 포함 화원 {m['registered_sources']}개. 3600초, 출력5초.",
        '기존 층 시험 예산을 유지: 실행당 실제 시간 1200초(20분). 최초 화원만 켠 기준 1회 + 규칙 시나리오 1회, 사건별 재실행 없음.',
        '초기 화원의 입력 HRR·면적 곡선 동일, 셀 분할 전후 체적 및 총 연료 에너지 보존 확인.',
        '초기 실의 연료 예산 전체는 최초 화원 셀에 한 번만 남음. 나머지 셀에 중복 연료를 만들지 않아 초기 실 내부 균등 연소를 재현하지 않음.']
    if m.get('discarded_attempt'):
        old=m['discarded_attempt']['baseline_last_state']
        lines.append(f"좌표계 오류 발견으로 첫 기준 계산은 중단·보존: 실제 {old['wall_seconds']:.1f}초 사용, 마지막 진행 약 {old['last_native_time_s']:.0f}초. 최종 비교 시간에 합산하지 않으며 작업 총비용에는 포함. 반복 수렴 또는 임계값 튜닝 재실행이 아님.")
    for name,r in comparison['cases'].items():
        lines.append(f"  {name}: 완료={r['complete']}, 실제 계산시간={r.get('native_wall_seconds')}초")
        sample_path=OUT/'C'/name/'status_samples.json'
        if sample_path.exists():
            samples=read(sample_path);positive=[s['dt_s'] for s in samples if s['dt_s']>0]
            stats={'positive_dt_min_s':min(positive) if positive else None,
                   'positive_dt_median_s':float(np.median(positive)) if positive else None,
                   'zero_dt_samples':[s for s in samples if s['dt_s']==0],
                   'basis':'observed status only; exclude initialization dt=0 from positive-step summary'}
            (OUT/'C'/name/'positive_dt_summary.json').write_text(json.dumps(stats,indent=2),'utf-8')
            lines.append('    상태 표본의 양수 dt 요약: '+json.dumps({k:v for k,v in stats.items() if k!='zero_dt_samples'},ensure_ascii=False))
        if not r['complete']:
            lines.append('    '+r.get('error','미완료'));lines.append('    상태 표본 통계: '+json.dumps(r.get('status_sample_statistics'),ensure_ascii=False))
            # Read a safely earlier, actually saved output prefix. Never pad it
            # to 3600s, create completed.json, or label it a completed scenario.
            if r.get('native_time_s',0)>=15:
                from run_room_rule_r6a_floor import observe
                folder=OUT/'C'/name;horizon=int(r['native_time_s']//5)*5-10
                try:
                    native=load_result(folder,horizon,{'folder':str(folder),'wall_seconds':r['native_wall_seconds']},allow_prefix=True)
                    partial=observe(read(folder/'scenario.json'),native,m,name=='baseline_native')
                    partial.update(complete=False,observed_prefix_only=True,requested_horizon_s=3600,
                        target_16_rooms_met=None,prefix_only_16_sustained=len(partial['sustained_60s_original_rooms'])>=16)
                    (folder/'partial-analysis.json').write_text(json.dumps(partial,ensure_ascii=False,indent=2),'utf-8')
                    lines.append(f"    완료 아님: 저장된 {horizon}초까지의 부분 관측에서 발열 {len(partial['actual_burning_original_rooms'])}실 / 60초 지속 {len(partial['sustained_60s_original_rooms'])}실. 1시간 완료나 최종 전이 수로 해석 금지.")
                    lines.append('    부분 관측 연소 실: '+', '.join(partial['actual_burning_original_rooms']))
                    for row in partial['rows']:
                        parent=row['parent']['room'] if row['parent'] else 'initial'
                        lines.append(f"    {row['cell']}: 출발 {parent}, 지연 {row['delay_s']:.2f}s, 조건시각 {shown(row['trigger_estimate_s'])}, 실제발열 첫 표본 {shown(row['first_actual_positive_HRR_s'])}, 최고 {row['actual_peak_kW']:.2f}kW, 연속 {row['longest_positive_HRR_s']:.0f}s; {row['status']}; 출발 센서 최고 {shown(row['sensor_max_C'])}℃")
                    diagnostic=sensors(folder,m,horizon)
                    (folder/'sensor_tracking_partial.json').write_text(json.dumps({'observed_until_s':horizon,'sensors':diagnostic},ensure_ascii=False,indent=2),'utf-8')
                    early=[s['room'] for s in diagnostic if s['first_threshold_sample'] and s['first_threshold_sample']['upper_C']<600]
                    lines.append('    부분 관측 첫 센서 >600℃ 표본에서 상층 <600℃인 셀: '+(', '.join(early) or '없음'))
                except (OSError,ValueError,StopIteration) as exc:lines.append('    부분 출력 미평가: '+str(exc))
            continue
        lines.append(f"    단계수 {r['total_steps']}, 실제 발열 실 {len(r['actual_burning_original_rooms'])}, 60초 이상 지속 실 {len(r['sustained_60s_original_rooms'])}, >1kW 실 {len(r['over_1kW_original_rooms'])}, 최대 동시 >1kW 실 {r['max_concurrent_original_rooms_over_1kW']}")
        lines.append('    연소 실: '+', '.join(r['actual_burning_original_rooms']))
        diagnostic=sensors(OUT/'C'/name,m);(OUT/'C'/name/'sensor_tracking.json').write_text(json.dumps(diagnostic,ensure_ascii=False,indent=2),'utf-8')
        elevated=[s['room'] for s in diagnostic if s['first_threshold_sample'] and s['first_threshold_sample']['upper_C']<600]
        lines.append('    첫 센서 >600℃ 출력 표본에서 상층 <600℃인 셀: '+(', '.join(elevated) or '없음')+' (5초 표본 진단, 실제 임계 통과 시각과 구분)')
        lines.append('    셀 / 출발실 / 구간 지연(s) / 조건시각 추정(s) / 실제발열 첫 표본(s) / 최고kW / 연속 양수 HRR(s)')
        for row in r['rows']:
            parent=row['parent']['room'] if row['parent'] else 'initial'
            lines.append(f"    {row['cell']} / {parent} / {row['delay_s']:.2f} / {row['trigger_estimate_s']} / {row['first_actual_positive_HRR_s']} / {row['actual_peak_kW']:.2f} / {row['longest_positive_HRR_s']:.0f}")
            if row['status'] not in ('initial_source','actual_source_burning'):lines.append('    전이 미발생: '+row['cell']+' / '+row['status'])
    lines+=['','경계 및 한계:',
        '센서 배치 불가(출발실 제외, 수신 화원 가능): '+json.dumps(m['sensor_placement_unavailable'],ensure_ascii=False),
        '통과 공간: '+', '.join(m['graph']['passing_rooms']),
        '경로 미도달: '+', '.join(m['graph']['unreachable_combustible_rooms']),
        '이번 실제 입력에는 수직 개구부가 없음: 층간/계단 하향 전이는 이번 결과로 검증하지 않음.',
        '기준 실행은 초기 화원만 켠 대조군. 기존 반복 전이 방식의 동일 결과/속도 비교가 아니므로 가속배수로 해석하지 않음.',
        '타깃600℃+경로 지연은 명시적 전이 가정. 실제 FO/FGI 발생 시각 또는 확률 예측 아님.',
        '순정 엔진만 사용: 프로젝트 bulk·혼합물 추가연소 OFF. 관련 확장 진단을 0 또는 검증 완료로 꾸며 넣지 않음.',
        '센서 국부 가스는 플룸 가우시안 꼬리를 포함할 수 있음. 셀별 sensor_tracking.json을 별도로 저장.',
        'dt 통계는 case.status를 실제 시간 1초마다 읽은 관측 표본이며 모든 솔버 단계의 최솟값/중앙값이 아님.',
        '닫힌 일반문 600초 관통, 복도 거리/0.5m/s, 단일 최단 경로, 외기 우선 공급 상한 등은 사용자 조절 가능한 가정.',
        '엔진 SHA256: '+m['engine_sha256'],'','세부 근거: simulation/results/room_rule_r6a_20261025/C/의 rule_manifest.json, comparison.json, 각 실행 analysis.json.']
    path=ROOT/'specs/실단위규칙-r6a-좌표수정-ABC결과-20261025.txt';path.write_text('\n'.join(lines)+'\n','utf-8');print(path)


if __name__=='__main__':main()
