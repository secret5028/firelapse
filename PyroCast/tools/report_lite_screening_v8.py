"""Read the completed ten serial cases; never starts a simulation."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'simulation/results/lite_v8_screening_20261025'
def read(p):return json.loads(p.read_text('utf-8'))
def short(s):return s.replace('CAD_3F_','')
def table(lines,headers,rows):
    lines.append(' | '.join(headers));lines.append(' | '.join(['---']*len(headers)))
    lines.extend(' | '.join(str(v).replace('|','/') for v in row) for row in rows);lines.append('')
def main():
    s=read(OUT/'score.json');c=read(OUT/'comparison.json')
    old=read(ROOT/'simulation/results/lite_v7_screening_20261025/score.json')
    rank2={r['room']:r for r in c['rows']};rankold={r['room']:r['rank1'] for r in old['ranked']}
    lines=['FireLapse v8 — 8.1절 2단계 결과 (2026-10-25)','',
      '범위: 화점 연료 기준 적용 → ① 재산정 → 상위5실×극단2상태 3600초, 총10회 직렬 → 보고 후 정지.',
      '정밀 엔진·열/산소 방정식·전이 임계값·문 분류·가중치는 변경하지 않았다. MC/문 분출 연소/다음 단계 실행 없음.',
      f"완주 {c['complete_scenarios']}/{c['attempted_scenarios']}, 총 {c['total_wall_s']:.3f}초. 실행 중 소스·입력 SHA 불변: {c['code_and_input_unchanged_during_batch']}.",
      f"BDF {sum(len(x.get('attempts',[]))==1 for x in c['cases'])}건, Radau 대체 {sum(x.get('solver_fallback',False) for x in c['cases'])}건.",'',
      '입력과 해석',
      '- Q_origin,peak=min(coverage×A×HRRPUA, k×1500×외기 ΣA√H), coverage=공유 설정 기본0.5, k=1.0, fast t² α=0.047.',
      '- 현 시험의 현재 연료 그룹 HRRPUA=400 kW/m²와 현재 에너지 예산을 사용. 오래된 fuel_default 메타데이터로 되돌리지 않았다.',
      '- 외기 상한은 도면 총면적 합으로 개폐상태와 무관하게 고정했다. 두 극단의 화원 곡선은 동일하고 실제 연소는 산소 제한에 따른다. 이는 수치 공급 상한이며 환기망의 정확한 공급량이 아니다.',
      '- ① 분모는 v7과 같이 내·외부 개구부 총합. 분자만 새 Q_origin으로 교체했다. 가중치 모두1, 정규화 규칙 불변.',
      '- 이번 수정은 §1.1 화점 정의다. 다른 실의 대기 화원은 §2 item_peak 유지. 화점 실의 형제 셀은 새 연료 기준 공급량·에너지의 면적 몫을 받는다.',
      '- 입력 peak를 크게 바꿔도 ① 점수와 최초 화원 곡선이 불변임을 검사했다. 기존 감쇠 적분과 셀 분할 연료 예산 보존도 검사했다.',
      '- 개방: 확정 방화문만 닫힘, 일반문·추정 방화문 열림, 개폐창50%. 폐쇄: 문·창 닫힘. 영구통로 항상 열림. 창 파괴 없음.',
      '- 각 실의 두 상태를 다섯 정렬키로 비교해 하나의 나쁜 상태를 택한다. 서로 다른 상태의 최대 지표를 섞지 않았다.',
      '- 순위키: 연소실수↓ → 연기위험3요인실수↓ → 연기주의1~2요인실수↓ → 최초FO↑ → 화점최고상층온도↓. 반올림 전 수치로 정렬, 완전 동률만 공동.',
      '- 완료 후 최고온도 집계가 화면용 소수1자리 값을 사용한 것을 발견해 저장된 원시 진단값으로 후처리만 정정했다. 순위 변화와 추가 적분은 없다(unrounded-ranking-audit.json).',
      '- 연소/연기 실 수는 셀을 원래 실로 합산하고 10초 출력 시간축 전체의 도달 여부를 센다. 주의와 위험은 서로 다른 시간에 같은 실에서 나타날 수 있어 배타적 합계가 아니다.',
      '- 최고 상층 온도는 화점 실에 속한 모든 셀·시간의 최댓값. FO는 공통 조건표 복합 all_met이며 단일600℃ 도달과 다르다.','',
      '①·② 순위표 (② 상위5만 실행)']
    rows=[]
    for r in s['ranked']:
        b=rank2.get(r['room']);rows.append([short(r['room']),r['name'],rankold.get(r['room']),r['rank1'],f"{r['score']:.6f}",
            f"{r['origin_budget']['Q_origin_peak_kW']:.3f}",b['rank2'] if b else '미실행',b['worst_state'] if b else '—'])
    table(lines,['실','이름','v7①','v8①','점수','Q_origin kW','②','나쁜 상태'],rows)
    lines.append('② 10회 결과')
    table(lines,['화점','상태','완주','연소실','위험실','주의실','최초FO s','화점 최고℃','총 s','적분 s'],[
        [short(r['room']),r['state'],r['complete'],r['burning_room_count'],r['smoke_risk_room_count'],r.get('smoke_caution_room_count'),
         r['first_FO_s'] if r['first_FO_s'] is not None else '없음',round(r.get('origin_max_upper_C',0),3),round(r['times']['total_s'],3),round(r['times'].get('integration_s',0),3)] for r in c['cases']])
    lines.append('R1·R2 요인 원값 및 정규화')
    for rid in ('CAD_3F_R1','CAD_3F_R2'):
        r=next(r for r in s['ranked'] if r['room']==rid)
        lines.extend([f"{short(rid)}: ① {r['rank1']}위, ② {rank2[rid]['rank2'] if rid in rank2 else '상위5 밖, 미실행(안전 판정 아님)'}",
          f"에너지 {r['fuel_energy_MJ']:.3f} MJ, 면적 {r['area_m2']:.5f} m², Q_origin {r['fuel_peak_kW']:.6f} kW, 전체 개구부 ΣA√H {r['opening_A_sqrtH']:.6f}",
          '원값 '+json.dumps(r['raw'],ensure_ascii=False),'정규화 '+json.dumps(r['normalized'],ensure_ascii=False),''])
    lines.append('전체 실 Q_origin,peak — 입력 peak 미사용; 실제 달성 HRR과 다름')
    table(lines,['실','면적 m²','연료 MJ','피복','HRRPUA','연료면적 공급 kW','외기 상한 kW','Q_origin kW','제한'],[
        [short(rid),round(b['area_m2'],3),round(b['energy_MJ'],3),b['coverage'],b['hrrpua_kW_m2'],round(b['fuel_surface_peak_kW'],3),
         round(b['external_cap_kW'],3),round(b['Q_origin_peak_kW'],3),b['limiting_factor']] for rid,b in s['origin_budgets'].items()])
    zero=[short(k) for k,b in s['origin_budgets'].items() if b['energy_MJ']>0 and b['Q_origin_peak_kW']==0]
    lines.extend(['한계 및 정지 상태',f"- 외기 개구부 없는 유연료실: {', '.join(zero)}. v8 식상 Q_origin=0. 내부문 대체 규칙을 임의 도입하지 않았다. 이런 실을 화점으로 직접 계산 요청하면 명시적 오류로 알린다. 이번 상위5에는 없다.",
      '- ①은 상대 후보 선별 점수이며 위험도 예측값/발생확률이 아니다. 두 극단만으로 최악 개폐조합을 보증하지 않는다.',
      '- R2는 여전히①6위다. 순위를 맞추려고 가중치·임계값을 조정하거나 추가 시뮬레이션하지 않았다.',
      '- 이 결과의 연소 수는 공급 상한 자체가 아니라 산소 제한 후 실제 HRR>0 집계다.',
      '- 장부 잔차는10초 출력 적분 진단이며 수락 스텝 보존의 인증이 아니다.',
      f"- 출력 장부 최대 에너지 상대잔차 {max(x.get('balance',{}).get('energy_percent',0) for x in c['cases']):.6f}%, 질량 {max(x.get('balance',{}).get('mass_percent',0) for x in c['cases']):.6f}%.",
      '- 요청한 v8 8.1절2단계 완료 후 정지. 후속 MC·문 분출 연소·색 개편·추가 최적화 없음.','',
      '자료: simulation/results/lite_v8_screening_20261025/score.json, comparison.json, 각 실/상태 input.json·summary.json·BDF/result.json·state.npz·rule_manifest.json',
      '코드: simulation/pyrocast_lite/screening_v8.py, tools/run_lite_screening_v8.py; v7 코드/결과 보존.'])
    dest=ROOT/'specs/간략엔진-v8-연료기준화점·상위5비교-20261025.txt'
    dest.write_text('\n'.join(lines)+'\n','utf-8');print(dest)
    print(json.dumps([{k:r[k] for k in ('room','rank1','rank2','worst_state','burning_room_count','smoke_risk_room_count','smoke_caution_room_count','origin_max_upper_C')} for r in c['rows']],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
