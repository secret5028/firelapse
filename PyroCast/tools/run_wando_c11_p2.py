"""P2 only: preserve executed P1 deck; add one stock mechanical supply vent."""
import argparse
import difflib
import json
import re
from copy import deepcopy
import run_wando_c11_p1 as common

P1 = common.OUT
OUT = common.ROOT / 'simulation/results/wando_C11_P2_20261102'
FAN = dict(id='PPV', a='OUTSIDE', b='ROOM', flow_m3_h=10000., flow_m3_s=10000/3600,
           heights_m=[1.5,1.5], areas_m2=[1.,1.], orientations=['VERTICAL','VERTICAL'],
           cutoffs_Pa=[200.,300.], schedule=[[0,0],[1500,0],[1500,1],[1920,1],[1920,0]])
VENT = ("&VENT TYPE='MECHANICAL' ID='PPV' COMP_IDS='OUTSIDE','ROOM' "
        "FLOW=2.777777777777778 HEIGHTS=1.5,1.5 AREAS=1,1 "
        "ORIENTATIONS='VERTICAL','VERTICAL' OFFSETS=4.375,0 "
        "CRITERION='TIME' T=0,1500,1500,1920,1920 F=0,0,1,1,0 /\n")

def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'attempt.json').exists():
        raise RuntimeError('P2 already attempted: no overwrite or rerun')
    evidence=json.loads((P1/'input-evidence.json').read_text(encoding='utf-8'))
    assert common.sha(P1/'case.in')==evidence['deck_sha256']
    for p,h in evidence['hashes'].items():
        if not p.replace('\\','/').startswith('specs/'):
            assert common.sha(common.ROOT/p)==h, p
    old=(P1/'case.in').read_text(encoding='ascii')
    assert "TYPE='MECHANICAL'" not in old
    pos=old.index('&FIRE')
    new=old[:pos]+VENT+old[pos:]
    assert new.replace(VENT,'',1)==old
    (OUT/'case.in').write_text(new,encoding='ascii')
    model=json.loads((P1/'model.json').read_text(encoding='utf-8'))
    original=deepcopy(model)
    model['mechanical_vents']=[FAN]
    check=deepcopy(model);check.pop('mechanical_vents');assert check==original
    common.OUT=OUT
    common.save('model.json',model)
    evidence.update(scenario='P2',parent_scenario='P1',parent_deck_sha256=common.sha(P1/'case.in'),
                    deck_sha256=common.sha(OUT/'case.in'),only_change='one MECHANICAL supply VENT added',
                    model_other_fields_equal=True,deck_added_lines=1,mechanical_supply=FAN,
                    current_spec_sha256=common.sha(common.SPEC))
    evidence['hashes'][str(common.SPEC.relative_to(common.ROOT))]=common.sha(common.SPEC)
    evidence['assumptions']=[x.replace('fan OFF','fan ON 1500-1920 s') for x in evidence['assumptions']]
    evidence['assumptions'] += [
        'PPV equivalent supply port area 1 m2 at each end, vertical, centered at 1.5 m: assumed, not measured',
        '10000 m3/h is nominal outside-to-ROOM flow, native 200/300 Pa pressure cutoff defaults retained',
        'Mechanical supply is a two-zone mass/enthalpy source, not a resolved PPV jet or air-entrainment cone']
    evidence['native_source_basis']={'input_namelist.f90':'1669 VENT namelist; 1807-1873 mechanical parsing',
        'flowfan.f90':'58-66 opening and flow; 124-143 receiving mass/species/enthalpy; 199-210 pressure cutoff',
        'cfast_parameters.f90':'193 default pressure cutoffs 200/300 Pa'}
    common.save('input-evidence.json',evidence)
    (OUT/'P1-P2-input.diff').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='P1/case.in',tofile='P2/case.in')),encoding='utf-8')
    print('P2 prepared: one mechanical vent line added; P1 remainder identical')

def analyze():
    common.OUT=OUT
    common.analyze('P2',fan_on=True)
    report()

def report():
    """Read saved outputs only; never start an engine process."""
    import numpy as np
    roots={s:common.ROOT/f'simulation/results/wando_C11_{s}_20261102' for s in ('P1','P2','P4')}
    summaries={s:json.loads((p/'summary.json').read_text(encoding='utf-8')) for s,p in roots.items()}
    series={s:json.loads((p/'timeseries.json').read_text(encoding='utf-8')) for s,p in roots.items()}
    vents,ids,units=common.read_native_csv(OUT/'case_vents.csv')
    t=vents['Time']; fraction=vents[next(k for k in vents if k.startswith('MF_') and ids[k]=='PPV')]
    flow=vents[next(k for k in vents if k.startswith('M_Outside') and ids[k]=='PPV')]
    on=(t>1500)&(t<1920);off=(t<1500)|(t>1920)
    assert np.all(fraction[on]==1) and np.all(fraction[off]==0)
    assert np.all(abs(flow[off])<1e-12) and np.all(abs(flow[on])>0)
    fan_check=dict(first_active_sample_s=float(t[np.flatnonzero(fraction>0)[0]]),
        last_active_sample_s=float(t[np.flatnonzero(fraction>0)[-1]]),
        absolute_mass_flow_on_min_kg_s=float(abs(flow[on]).min()),
        absolute_mass_flow_on_max_kg_s=float(abs(flow[on]).max()),off_mass_flow_zero=True,
        sample_note='5 s samples; exact switch at 1500/1920 s is defined in native input')
    common.save('fan-verification.json',fan_check)
    timing={}
    for s,p in roots.items():
        log=(p/'case.log').read_text(errors='replace')
        timing[s]=dict(wall_s=summaries[s]['run']['wall_seconds'],
            native_s=float(re.search(r'Total execution time\s*=\s*(\S+)',log)[1]),
            steps=int(re.search(r'Total time steps\s*=\s*(\d+)',log)[1]))
    prefix={}
    for key,values in series['P2']['ROOM'].items():
        a=np.asarray(values);b=np.asarray(series['P1']['ROOM'][key])
        mask=np.asarray(series['P2']['time_s'])<1500
        prefix[key]=float(np.max(abs(a[mask]-b[mask])))
    common.save('P1-P2-P4-comparison.json',dict(scenarios=summaries,timing=timing,
        fan_verification=fan_check,pre_fan_max_abs_difference=prefix,
        independence='Separate immutable decks, attempts, CSV and summaries. P1/P4 not rerun or overwritten.'))
    def at(v):
        if v is None:return '미도달'
        v=round(v);return f'{v:,} s ({v//60:02d}:{v%60:02d})'
    def pk(v,unit=''):return f"{v['value']:,.3f} {unit} @ {at(v['time_s'])}"
    labels={'FO':'FO','FGI':'FGI','BD':'백드래프트'}
    lines=['# C11 P2 — 배풍기 ON, 독립 CFAST 1회 및 P1·P4 비교','',
        'P2를 별도 폴더에 입력·실행·결과로 보존했다. P1(OFF), P4(OFF·절단 없음)는 저장 결과만 읽었으며 재계산·덮어쓰기하지 않았다. P3·간략 근사는 실행하지 않고 이 보고 후 정지한다.','',
        '## 실행 조건','', '| 항목 | P1 | P2 | P4 |','|---|---|---|---|',
        '| 절단 | 1320/1800 s | P1과 동일 | 없음 |',
        '| 급기 | OFF | 외기→ROOM, 10,000 m³/h, 1500~1920 s | OFF |',
        '| 화원·재료·솔버·출력 | slow, 기존 입력 | P1과 동일 | P1과 동일 |',
        '| 실행 수 | 기존 1회 | 이번 1회 | 기존 1회 |',
        '| 외부 실행 시간(s) | '+' | '.join(f"{timing[s]['wall_s']:.3f}" for s in roots)+' |',
        '| native 시간(s) | '+' | '.join(f"{timing[s]['native_s']:.0f}" for s in roots)+' |',
        '| 단계 수 | '+' | '.join(f"{timing[s]['steps']:,}" for s in roots)+' |',
        '| CSV 마지막(s) | '+' | '.join(str(summaries[s]['run']['last_csv_s']) for s in roots)+' |','',
        'P2 덱은 P1에 순정 `&VENT TYPE=MECHANICAL` 1줄만 추가했다. 명세의 MVENT 표현은 CFAST 7.7.7 실제 입력 문법으로 옮겼다. 엔진·조건표·연료·절단 일정·임계값 변경 없음.',
        '급기구 양끝 면적 1 m², 수직 면, 중심 높이 1.5 m를 적용했다. 면적은 명세에 없어 [가정]이며, 층별 유입 배분에 영향을 줄 수 있다. 팬 압력 차단은 순정 기본 200/300 Pa를 유지했다. PPV의 공간 제트·문 주변 공기 유인은 계산하지 않는다.','',
        f"실제 CSV 급기 확인: 최초 ON 표본 {at(fan_check['first_active_sample_s'])}, 마지막 ON 표본 {at(fan_check['last_active_sample_s'])}, ON 질량유량 절댓값 {fan_check['absolute_mass_flow_on_min_kg_s']:.4f}~{fan_check['absolute_mass_flow_on_max_kg_s']:.4f} kg/s, OFF 구간 0.",
        '', '## 그래프','',
        '기존과 같은 4패널: ROOM 상층 T·O₂·미연 연료 질량분율·3지수. 기준선 780/1320/1500/2100 s. 회색 끝 구간은 미출력이며 외삽하지 않았다.','',
        '![P2 전체](../simulation/results/wando_C11_P2_20261102/P2-timeseries.png)','',
        '![P2 확대](../simulation/results/wando_C11_P2_20261102/P2-zoom.png)','',
        '![P1 P2 P4 비교](../simulation/results/wando_C11_P2_20261102/P1-P2-P4-comparison.png)','',
        '## 지수 70·100 최초 도달','',
        '5초 출력에서 최초 기준 이상인 시각. 조건지수이며 현상 발생 확률·폭발/FGI 발생 확정이 아니다.','',
        '| 구획·지수 | P1 ≥70 / ≥100 | P2 ≥70 / ≥100 | P4 ≥70 / ≥100 |','|---|---|---|---|']
    for rid in ('ROOM','CAVITY'):
        for k,label in labels.items():
            lines.append(f'| {rid} {label} | '+' | '.join(at(summaries[s]['rooms'][rid]['indices'][k]['first_70_s'])+' / '+at(summaries[s]['rooms'][rid]['indices'][k]['first_100_s']) for s in roots)+' |')
    lines+=['','## 지수 최고값·시각','', '| 구획·지수 | P1 | P2 | P4 |','|---|---:|---:|---:|']
    for rid in ('ROOM','CAVITY'):
        for k,label in labels.items():
            lines.append(f'| {rid} {label} | '+' | '.join(pk(summaries[s]['rooms'][rid]['indices'][k]['peak']) for s in roots)+' |')
    lines+=['','## CFAST 대조','', '| 항목 | P1 | P2 | P4 |','|---|---:|---:|---:|']
    for rid,key,label,unit in [('CAVITY','source_HRR_peak_kW','CAVITY 실제 화원 HRR peak','kW'),
        ('ROOM','door_jet_peak_kW','ROOM 수신 door jet peak','kW'),
        ('ROOM','temperature_peak_C','ROOM 상층 T peak','℃'),('CAVITY','temperature_peak_C','CAVITY 상층 T peak','℃'),
        ('ROOM','fuel_mass_fraction_peak','ROOM 미연 연료 peak','kg/kg')]:
        lines.append('| '+label+' | '+' | '.join(pk(summaries[s]['rooms'][rid][key],unit) for s in roots)+' |')
    lines.append('| 외기 수신 door jet peak | '+' | '.join(pk(summaries[s]['door_jet_outside_peak_kW'],'kW') for s in roots)+' |')
    lines.append('| ROOM 최저 O₂ (vol%) | '+' | '.join(f"{summaries[s]['rooms']['ROOM']['minimum_O2_vol_percent']:.3f}" for s in roots)+' |')
    for key,label in [('interface_first_below_3m_s','ROOM 경계 ≤3 m'),('interface_first_below_1_8m_s','ROOM 경계 ≤1.8 m')]:
        lines.append('| '+label+' | '+' | '.join(at(summaries[s]['rooms']['ROOM'][key]) for s in roots)+' |')
    lines+=['','## 2100초 비교','', '| 값 | P1 | P2 | P4 |','|---|---:|---:|---:|']
    for key in ('T_upper_C','O2_upper_vol_percent','fuel_upper_mass_fraction','interface_m','FO','FGI','BD'):
        lines.append('| '+key+' | '+' | '.join(f"{summaries[s]['times']['2100'][key]:.4f}" for s in roots)+' |')
    a=summaries['P1']['rooms']['ROOM'];b=summaries['P2']['rooms']['ROOM'];d=summaries['P4']['rooms']['ROOM']
    lines+=['','## 차이·한계','',
        f"- P1 대비 ROOM 최고 T {a['temperature_peak_C']['value']:.1f}→{b['temperature_peak_C']['value']:.1f}℃, FGI 100 {at(a['indices']['FGI']['first_100_s'])}→{at(b['indices']['FGI']['first_100_s'])}.",
        '- ROOM door jet 최대는 두 경우 모두 1325초로 팬 ON(1500초) 이전이다. 최대값이 같다는 것만으로 팬 가동 중 영향이 없었다고 판단하지 않는다.',
        f"- P4 대비 ROOM 최고 T {d['temperature_peak_C']['value']:.1f}→{b['temperature_peak_C']['value']:.1f}℃. P4와 P2는 절단과 급기 두 조건이 달라 팬 단독 효과로 해석하지 않는다.",
        f"- 팬 이전 ROOM T 최대 차이 {prefix['T_upper_C']:.6g}℃, O₂ {prefix['O2_upper_vol_percent']:.6g}%p. 입력 추가에 따른 수치 편차를 그대로 기록했다.",
        '- 명목 ON/OFF는 고정 입력이다. 유입 산소 증가와 냉각·희석·미연 가스 연소가 함께 작용하므로, 결과는 이 입력의 비교이며 배풍 일반의 효과를 입증하지 않는다.',
        '- ROOM FO 지수는 기존 식의 고체+bulk 발열 0 때문에 0이다. native DJET를 고체 발열로 재배정하지 않았다. DJET는 받는 구획 합계로 틈·절단 개별 분리 불가.',
        '- 순정 정상 종료와 3600초 CSV 끝 표본 유무는 별개다. 마지막 3595초이면 기존 로더의 horizon 검사 실패를 보존하고 5초를 채우지 않았다.',
        '- 실행 시간은 이번 1회 관측이다. P2 단계 수는 P1보다 조금 많으므로 116초 대 136초를 일반적인 속도 개선으로 해석하지 않는다.',
        '- 0.1 m 공동 2존 근사, 내장재 바닥 등가 화원, 강제 공급 포트 면적은 사례 검증되지 않은 가정이다. 실제 2100초 사건에 맞춘 조정 없음.',
        '', '자료: [입력 diff](../simulation/results/wando_C11_P2_20261102/P1-P2-input.diff) · [비교 JSON](../simulation/results/wando_C11_P2_20261102/P1-P2-P4-comparison.json) · [급기 출력 확인](../simulation/results/wando_C11_P2_20261102/fan-verification.json) · [P1·P4 기존 파일 불변](../simulation/results/wando_C11_P2_20261102/baseline-independence.json).',
        '', '**P2 1회 보고 후 정지. P3 미실행.**','']
    (common.ROOT/'specs/웹앱-C11-P2-계산보고-20261102.md').write_text('\n'.join(lines),encoding='utf-8')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(7,1,figsize=(13,17),sharex=True,layout='constrained')
    fig.suptitle('Independent Wando scenarios | P1 fan OFF / P2 fan ON / P4 no cut',fontsize=14)
    keys=['T_upper_C','O2_upper_vol_percent','fuel_upper_mass_fraction','FO','FGI','BD']
    labs=['Upper T (C)','Upper O2 (vol %)','Unburned fuel (kg/kg)','FO index','FGI index','Backdraft index','Rollover index']
    for ax,key,label in zip(axs,keys,labs):
        for s,col in zip(roots,['#526987','#d95624','#329277']):
            ax.plot(series[s]['time_s'],series[s]['ROOM'][key],label=s,color=col,lw=1.5)
        ax.set_ylabel(label);ax.grid(alpha=.2);ax.set_xlim(0,3600)
        for at_s in (780,1320,1500,2100):ax.axvline(at_s,color='#777',ls='--',lw=.8,alpha=.6)
        ax.axvspan(1500,1920,color='#edc37b',alpha=.10)
        if key in labels:
            for level in (70,100):ax.axhline(level,color='#777',ls=':',lw=.8)
    axs[0].legend(ncol=3);axs[-1].set_xlabel('Time after ignition (s) | shaded: P2 fan ON | no end extrapolation')
    fig.savefig(OUT/'P1-P2-P4-comparison.png',dpi=150);plt.close(fig)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','analyze'])
    action=p.parse_args().action
    if action=='prepare':prepare()
    elif action=='analyze':analyze()
    else:
        common.OUT=OUT
        common.run('P2')
