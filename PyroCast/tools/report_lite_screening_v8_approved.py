"""Completed approved-input batch report. Reads files only; no simulation."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'simulation/results/lite_v8_approved_screening_20261025'
def read(p):return json.loads(p.read_text('utf-8'))
def short(r):return r.replace('CAD_3F_','')
def table(lines,headers,rows):
    lines.extend([' | '.join(headers),' | '.join(['---']*len(headers))])
    lines.extend(' | '.join(str(v).replace('|','/') for v in row) for row in rows);lines.append('')
def main():
    s=read(OUT/'score.json');c=read(OUT/'comparison.json');old=read(ROOT/'simulation/results/lite_v8_screening_20261025/comparison.json')
    second={r['room']:r for r in c['rows']};uses=s['approved_input']['room_uses'];budgets=s['origin_budgets']
    lines=['FireLapse v8 승인 용도표 적용 — 8.1절2단계 보고 (2026-10-25)','',
        '사용자 승인: 화장실40MJ/m²·250kW/m²(가정), 화장실4실 통과 공간으로 후보 제외, R14/R28 개구부 없는1m²미만으로 후보·그래프 제외. 나머지는 승인표 유지.',
        f"적격 후보 {s['eligible_count']}실, 계산 원래실 {s['all_room_count']}개(기존{s['original_room_count']}개). 셀 분할 후38존. 상위5×극단2상태=10회 직렬, 각3600초.",
        f"완주 {c['complete_scenarios']}/{c['attempted_scenarios']}, 총 {c['total_wall_s']:.3f}초. Radau 대체 {sum(r.get('solver_fallback',False) for r in c['cases'])}건.",
        f"실행 중 코드·입력SHA 불변: {c['code_and_input_unchanged_during_batch']}. 정밀모드·열/산소방정식·임계값·가중치 수정 없음. MC·다음단계 실행 없음.",'',
        '적용 방식과 근거',
        '- fire_load_table.json의 mean/rhrf를 사용한다. R2만 사용자 지정1800 유지: 이전 시연600×3의 승계이며 실측/문헌기본값이 아니다.',
        '- 용도별 대응은 사용자가 승인한 이 건물 전용표(approved_uses_v8.json)다. 건물SHA가 다르면 적용을 거부한다. 단순 키워드 자동 분류 결과로 가장하지 않는다.',
        '- 화장실 class=toilet 추가. q80=mean은 확률분포를 추정하지 않는 호환용 고정값, t_alpha는 기존default를 계승. 이번 화점 성장은v8 alpha=.047, MC 미실행.',
        '- 화장실 R11/R16/R17/R24: 하중40<50이므로 화점후보·대기화원 없음. 연기/유동/온도 노드와 연결은 유지한다.',
        '- R14/R28: 면적<1, 연결개구부0을 검증한 뒤 계산실·후보·전이그래프에서 제거한다. 향후 기하가 바뀌면 자동제외 대신 오류로 알린다.',
        '- 홀 R4/R15는 승인표transport 100MJ/m²로50이상이므로 후보 유지. 다른 실의사용자지시되지않은 제외는 추가하지 않았다.',
        '- Qorigin=min(.5×면적×HRRPUA,1500×외기합A√H). 외기개구부 없으면 상한750×내부최대A√H. 같은 화원곡선을 두 극단에 사용, 실제 연소는 기존산소제한 계산.',
        '- 내부상한은 여러문 합산이 아니며, 외기/내부 모두 도면 총기하 기준이다. 정밀한 환기망 한계가 아닌 사용자 지정공급상한이다.',
        '- 최초실 외 다른실 공급은§2 item_peak 유지. 연료하중·HRRPUA·피복률은 그 실에도 승인표를 적용. 최초실 형제셀은 새화원 면적몫 사용.',
        '- 순위: 연소실수↓→연기위험3요인실수↓→연기주의1~2요인실수↓→최초FO↑→화점최고상층온도↓. 두 상태중 실제 한 사례를 선택, 각 상태최댓값 혼합금지.',
        '- 원래실 기준 집계, 시간·셀 전체의 도달여부. 주의와위험은 시간별로달라 같은실이중복될수있다. FO는공통조건표 복합all_met. 최고온도는반올림전진단값.',
        '- 개방상태: 확정방화문만닫힘·다른문열림·개폐창50%. 폐쇄상태: 문·창닫힘(누설). 영구통로유지. 창파괴없음.','',
        '① 전체 후보 및 ② 순위']
    table(lines,['실','이름','①','점수','Qorigin kW','②','나쁜상태'],[
        [short(r['room']),r['name'],r['rank1'],f"{r['score']:.6f}",f"{r['fuel_peak_kW']:.3f}",
         second[r['room']]['rank2'] if r['room'] in second else '미실행',second[r['room']]['worst_state'] if r['room'] in second else '—'] for r in s['ranked']])
    lines.append('② 시나리오10회 및 계산시간')
    table(lines,['화점','상태','완주','연소','위험','주의','최초FO s','화점최고℃','적분s','전체s'],[
        [short(r['room']),r['state'],r['complete'],r['burning_room_count'],r['smoke_risk_room_count'],r.get('smoke_caution_room_count'),
         r['first_FO_s'] if r['first_FO_s'] is not None else '없음',round(r.get('origin_max_upper_C',0),3),
         round(r['times'].get('integration_s',0),3),round(r['times']['total_s'],3)] for r in c['cases']])
    lines.append('R1·R2 위치 및 요인 원값')
    for rid in ('CAD_3F_R1','CAD_3F_R2'):
        r=next(r for r in s['ranked'] if r['room']==rid)
        lines.extend([f"{short(rid)}: ①{r['rank1']}위, ②{second[rid]['rank2'] if rid in second else '미실행: 상위5밖, 안전판정 아님'}",
          f"면적{r['area_m2']:.5f}, 에너지{r['fuel_energy_MJ']:.3f}MJ, Qorigin{r['fuel_peak_kW']:.6f}kW, 전체개구부ΣA√H={r['opening_A_sqrtH']:.6f}",
          '원값: '+json.dumps(r['raw'],ensure_ascii=False),'정규화: '+json.dumps(r['normalized'],ensure_ascii=False),''])
    lines.append('승인된23실 입력과 제외 사유')
    table(lines,['실','용도','근거','면적','하중','피복률','HRRPUA','외기ΣA√H','내부maxA√H','Qorigin kW','상태'],[
        [short(rid),u['label'],u['classification_basis'],round(u['area_m2'],3),u['load_MJ_m2'],u['coverage'],u['hrrpua_kW_m2'],
         round(budgets[rid]['external_A_sqrtH'],3) if rid in budgets else 0,
         round(budgets[rid]['internal_max_A_sqrtH'],3) if rid in budgets else 0,
         round(budgets[rid]['Q_origin_peak_kW'],3) if rid in budgets else '미등록',
         '후보·그래프 제외' if u['graph_excluded'] else '통과공간·후보제외' if u['passage_without_fire'] else '후보']
        for rid,u in uses.items()])
    lines.append('실제 전이 기록 (새 실행 없이 저장 결과 조회)')
    for case in c['cases']:
        folder=OUT/case['room']/case['state']/case.get('selected_attempt','BDF')
        r=read(folder/'result.json')
        burned=[short(k) for k,v in case['rooms'].items() if v['burning']]
        lines.append(f"{short(case['room'])}/{case['state']}: 연소실={','.join(burned)}, 전이이벤트수={len(r.get('events',[]))}")
        for event in r.get('events',[]):lines.append('  '+json.dumps(event,ensure_ascii=False))
    lines.extend(['','이전 v8과 해석',
        f"- 이전 일괄 고연료 v8 실행시간 {old['total_wall_s']:.3f}s, 이번 {c['total_wall_s']:.3f}s. 연료와 노드구성이 달라 알고리즘 속도개선 배수로 해석하지 않는다.",
        '- 후보 정규화 범위는 R14/R28 제외후 원래28실. 화장실은물리노드유지하므로정규화에도포함하되후보만제외한다(기존층전체정규화방식유지).',
        '- 이 순위는17실 중①상위5개에 대한②비교다. 전체17실의시뮬최악을확정하거나발생확률을뜻하지 않는다.',
        '- R2가상위5밖이면추가실행하지않는다. 결과에맞춘가중치·임계값조정없음.',
        f"- 출력격자10초장부진단: 최대에너지잔차{max(r.get('balance',{}).get('energy_percent',0) for r in c['cases']):.6f}%, 최대질량잔차{max(r.get('balance',{}).get('mass_percent',0) for r in c['cases']):.6f}%. 질량은보고전용이며수락스텝보존인증아님.",
        '- 검사16건통과(값·원본보존·상한·화원peak독립·에너지·후보/그래프제외·화장실비연소).',
        '- 사용자지정8.1절2단계후정지. MC/문분출연소/추가최적화/추가시나리오실행없음.','',
        '결과: simulation/results/lite_v8_approved_screening_20261025 (score/comparison/개별input·summary·result·state·manifest)',
        '구현: screening_v8_approved.py, approved_uses_v8.json, fire_load_table.json, run_lite_screening_v8_approved.py. 이전v8결과보존.'])
    dest=ROOT/'specs/간략엔진-v8-승인용도표·상위5비교-20261025.txt';dest.write_text('\n'.join(lines)+'\n','utf-8')
    print(dest)
    print(json.dumps([{k:r[k] for k in ('room','rank1','rank2','worst_state','burning_room_count','smoke_risk_room_count','smoke_caution_room_count','first_FO_s','origin_max_upper_C')} for r in c['rows']],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
