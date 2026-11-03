"""P4 only. Copy executed P1 input; change only CUT's schedule to closed."""
import argparse
import difflib
import json
import re
from copy import deepcopy
import run_wando_c11_p1 as common

P1=common.OUT
OUT=common.ROOT/'simulation/results/wando_C11_P4_20261102'


def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'attempt.json').exists():
        raise RuntimeError('P4 already attempted; no overwrite or rerun')
    evidence=json.loads((P1/'input-evidence.json').read_text(encoding='utf-8'))
    assert common.sha(P1/'case.in')==evidence['deck_sha256']
    assert all(common.sha(common.ROOT/p)==h for p,h in evidence['hashes'].items())
    model=json.loads((P1/'model.json').read_text(encoding='utf-8'))
    original=deepcopy(model)
    cut=next(v for v in model['openings'] if v['id']=='CUT')
    cut['schedule']=[[0,0]]
    check=deepcopy(model)
    next(v for v in check['openings'] if v['id']=='CUT')['schedule']=next(v for v in original['openings'] if v['id']=='CUT')['schedule']
    assert check==original
    old=(P1/'case.in').read_text(encoding='ascii')
    old_control='T=0,1320,1320,1800,1800 F=0,0,0.5,0.5,1'
    assert old.count(old_control)==1
    new=old.replace(old_control,'T=0 F=0')
    changed=[(a,b) for a,b in zip(old.splitlines(),new.splitlines()) if a!=b]
    assert len(changed)==1 and "ID='CUT'" in changed[0][0]
    (OUT/'case.in').write_text(new,encoding='ascii')
    common.OUT=OUT
    common.save('model.json',model)
    evidence.update(scenario='P4',parent_scenario='P1',parent_deck_sha256=common.sha(P1/'case.in'),
                    deck_sha256=common.sha(OUT/'case.in'),only_change='CUT schedule -> [[0,0]]',
                    model_other_fields_equal=True,deck_changed_lines=1)
    evidence['assumptions']=[x for x in evidence['assumptions'] if not x.startswith('CUT center')]
    evidence['assumptions'].append('CUT is held at zero opening for the full run; bottom/top gaps unchanged')
    common.save('input-evidence.json',evidence)
    (OUT/'P1-P4-input.diff').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='P1/case.in',tofile='P4/case.in')),encoding='utf-8')
    print('P4 prepared: exactly one deck line changed; all other model inputs equal to P1')


def analyze():
    common.OUT=OUT
    common.analyze('P4')
    before=json.loads((P1/'summary.json').read_text(encoding='utf-8'))
    after=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
    log=(OUT/'case.log').read_text(errors='replace')
    steps=int(re.search(r'Total time steps\s*=\s*(\d+)',log).group(1))
    native_s=float(re.search(r'Total execution time\s*=\s*(\S+)',log).group(1))
    def at(value):
        if value is None:return '미도달'
        sec=round(value);return f'{sec:,}초 ({sec//60:02d}:{sec%60:02d})'
    def pk(record,unit):return f"{record['value']:,.3f} {unit} @ {at(record['time_s'])}"
    def hits(s):
        return ''.join(f"| {label} | {at(s['indices'][key]['first_70_s'])} | {at(s['indices'][key]['first_100_s'])} | {s['indices'][key]['peak']['value']:.2f} @ {at(s['indices'][key]['peak']['time_s'])} |\n"
            for key,label in [('FO','FO'),('FGI','FGI'),('BD','백드래프트')])
    a=before['rooms'];b=after['rooms']
    delta=dict(runtime_seconds=after['run']['wall_seconds']-before['run']['wall_seconds'],
        room_temperature_peak_C=b['ROOM']['temperature_peak_C']['value']-a['ROOM']['temperature_peak_C']['value'],
        cavity_HRR_peak_kW=b['CAVITY']['source_HRR_peak_kW']['value']-a['CAVITY']['source_HRR_peak_kW']['value'],
        room_door_jet_peak_kW=b['ROOM']['door_jet_peak_kW']['value']-a['ROOM']['door_jet_peak_kW']['value'])
    one_line=(f"P1 대비: ROOM 최고 온도 {a['ROOM']['temperature_peak_C']['value']:.1f}→{b['ROOM']['temperature_peak_C']['value']:.1f}℃, "
        f"ROOM door jet peak {a['ROOM']['door_jet_peak_kW']['value']:.1f}→{b['ROOM']['door_jet_peak_kW']['value']:.1f} kW, "
        f"FGI 100 도달 {at(a['ROOM']['indices']['FGI']['first_100_s'])}→{at(b['ROOM']['indices']['FGI']['first_100_s'])}.")
    common.save('P1-comparison.json',dict(P1=before,P4=after,differences=delta,one_line=one_line,
                                       native_steps=steps,native_wall_s=native_s))
    lines=[
        '# C11 r2 P4 — 절단 없음, CFAST 1회 결과',
        '', 'P4만 시간 적분 1회 실행했다. P2·P3·간략 근사는 실행하지 않고 여기서 정지한다.',
        '', 'P4는 운영 연결 우선 요청 전에 이미 시작한 실행이다. 연결 완료 후 저장 출력만 분석했으며 재실행하지 않았다. 실행 이후 명세 파일은 r3으로 갱신됐으나, 실행 당시 입력 덱·엔진·조건표·물리 코드의 해시는 그대로다. 명세 해시 차이는 summary.json의 unchanged에 false로 보존했다.',
        '', '**'+one_line+'**',
        '', '## 실행 조건', '', '| 항목 | P4 |', '|---|---|',
        '| P1과 다른 입력 | CUT 개방 일정만 `T=0 F=0`. 기존 1,320/1,800초 절단·확대 없음 |',
        '| 동일성 | 덱 1줄만 변경. 모델의 CUT schedule 이외 전체 필드 동일 검증 |',
        '| 유지 입력 | slow α=0.00293, 총 9,807.656 MJ, 공급 peak 10,749.504 kW, 70% 성장·30% 감쇠 가정, 하부·상부 틈 개방, 외기 문 개방, 배풍기 OFF |',
        '| 엔진 | 순정 CFAST baseline, SHA256 `317cd8d1ae914152effe8733fe9fd49e0dc7284acdb041c7d9a57c77eb3467f9` |',
        f"| 시간 | 외부 {after['run']['wall_seconds']:.3f}초 / native {native_s:.0f}초 / {steps:,} 단계 |",
        f"| 종료·출력 | native 정상 종료, 요청 3,600초. CSV 마지막 {after['run']['last_csv_s']:g}초. 마지막 5초를 외삽하지 않음 |",
        '| 로더 | P1과 동일하게 마지막 3,600초 표본이 없어 엄격한 horizon 검사는 실패. 재계산하지 않음 |',
        '| 검증 | CUT WF 전 구간 0, 조건표 전체 evaluate와 3지수 동일, 엔진·조건표·물리 입력 생성 코드 SHA 불변 |',
        '', '## 그래프', '',
        '세로선 780/1,320/1,500/2,100초를 유지했다. P4의 1,320초는 **절단을 실행하지 않은 비교선**, 1,500초 역시 배풍기를 켜지 않은 비교선이다.',
        '', '![P4 전체](../simulation/results/wando_C11_P4_20261102/P4-timeseries.png)',
        '', '![P4 확대](../simulation/results/wando_C11_P4_20261102/P4-zoom.png)',
        '', '## ROOM 지수 최초 도달', '',
        '5초 native 출력 표본의 최초 기준 이상 시각. 미도달은 저장 구간에 한하며 발생확률이나 실제 현상 발생 판정이 아니다.',
        '', '| 지수 | ≥70 | ≥100 | 최고 지수·시각 |', '|---|---:|---:|---:|',hits(b['ROOM']),
        '## CFAST 대조', '', '| 항목 | P1 절단 있음 | P4 절단 없음 |', '|---|---:|---:|',
        f"| CAVITY 실제 화원 HRR peak | {pk(a['CAVITY']['source_HRR_peak_kW'],'kW')} | {pk(b['CAVITY']['source_HRR_peak_kW'],'kW')} |",
        f"| ROOM 수신 door jet peak | {pk(a['ROOM']['door_jet_peak_kW'],'kW')} | {pk(b['ROOM']['door_jet_peak_kW'],'kW')} |",
        f"| 외기 수신 door jet peak | {pk(before['door_jet_outside_peak_kW'],'kW')} | {pk(after['door_jet_outside_peak_kW'],'kW')} |",
        f"| ROOM 상층 T peak | {pk(a['ROOM']['temperature_peak_C'],'℃')} | {pk(b['ROOM']['temperature_peak_C'],'℃')} |",
        f"| CAVITY 상층 T peak | {pk(a['CAVITY']['temperature_peak_C'],'℃')} | {pk(b['CAVITY']['temperature_peak_C'],'℃')} |",
        f"| ROOM 상층 최저 O₂ | {a['ROOM']['minimum_O2_vol_percent']:.3f}% | {b['ROOM']['minimum_O2_vol_percent']:.3f}% |",
        f"| ROOM 상층 미연 연료 최대 질량분율 | {a['ROOM']['fuel_mass_fraction_peak']['value']:.6f} | {b['ROOM']['fuel_mass_fraction_peak']['value']:.6f} |",
        f"| ROOM 경계 3 m 이하 | {at(a['ROOM']['interface_first_below_3m_s'])} | {at(b['ROOM']['interface_first_below_3m_s'])} |",
        f"| ROOM 경계 1.8 m 이하 | {at(a['ROOM']['interface_first_below_1_8m_s'])} | {at(b['ROOM']['interface_first_below_1_8m_s'])} |",
        '', '## 2,100초 비교', '', '| 값 | P1 | P4 |', '|---|---:|---:|']
    for key,label in [('T_upper_C','상층 T(℃)'),('O2_upper_vol_percent','상층 O₂(vol%)'),
                      ('fuel_upper_mass_fraction','미연 연료(kg/kg)'),('interface_m','연기 경계(m)'),
                      ('FO','FO'),('FGI','FGI'),('BD','백드래프트')]:
        lines.append(f"| {label} | {before['times']['2100'][key]:.4f} | {after['times']['2100'][key]:.4f} |")
    lines += ['', '## CAVITY 지수 참고', '', '| 지수 | ≥70 | ≥100 | 최고 지수·시각 |', '|---|---:|---:|---:|',hits(b['CAVITY']),
        '## 해석 범위', '',
        '- P4는 절단만 없앤 입력 대조다. 결과를 맞추기 위한 성장률·에너지·임계값·솔버 변경은 없다.',
        '- 저산소·미연 연료 축적이 있어도 온도 등 다른 요인이 기준보다 낮으면 AND 지수는 낮다. 낮은 지수가 추후 개방 안전을 보증하지 않는다. 이번 P4는 나중에 문이나 강판을 여는 개입을 계산하지 않았다.',
        '- ROOM FO 지수는 기존 식에서 해당 실 고체+프로젝트 bulk 발열을 쓰므로 0이다. native DJET를 임의 재배정하지 않았다. 이 항의 한계는 P1과 동일하다.',
        '- DJET는 받는 구획 합계다. P4는 절단이 닫혀 있으므로 ROOM 수신 발열이 있으면 상·하부 틈 경로 합계다. 두 틈의 개별 peak는 순정 출력에 없어 분리 미평가다.',
        '- 공동 두께 0.1 m의 2존 근사, 등가 바닥 화원 면적, 입력 성장·감쇠 곡선은 검증된 실제 내장재 화재 재현이 아니다. 지수는 FGI·폭압·화염 전파 발생을 계산하는 모델이 아니다.',
        '- 도달 시각·peak는 5초 표본 기준이다. 마지막 5초 출력 누락을 숨기거나 새 표본으로 채우지 않았다.',
        '', '자료: [입력 차이](../simulation/results/wando_C11_P4_20261102/P1-P4-input.diff), [P1 비교 JSON](../simulation/results/wando_C11_P4_20261102/P1-comparison.json), [ROOM CSV](../simulation/results/wando_C11_P4_20261102/room-timeseries.csv).',
        '', '**P4 보고 후 정지. 다음 순서는 P2 → P3이며 아직 실행하지 않았다.**','']
    (common.ROOT/'specs/웹앱-C11-P4-계산보고-20261102.md').write_text('\n'.join(lines),encoding='utf-8')
    print(one_line)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','analyze'])
    action=p.parse_args().action
    if action=='prepare':prepare()
    elif action=='analyze':analyze()
    else:
        common.OUT=OUT
        getattr(common,action)('P4')
