"""P5: three fixed plate thresholds, one stock CFAST process each; no engine changes."""
import argparse
import copy
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'simulation'), str(ROOT/'simulation/deps')]
import numpy as np
from pyrocast_cfbt.deck import fire_curve, make_deck
from pyrocast_cfbt.native import execute, read_native_csv
from pyrocast_cfbt.rule_sensor import gas_proxy_plate
from pyrocast_cfbt.conditions import evaluate
from pyrocast_cfbt.spread import classify

BASE = ROOT/'simulation/results/wando_C11_P1_20261102'
OUT = ROOT/'simulation/results/wando_C11_P5_20261103'
TABLE = ROOT/'simulation/pyrocast_lite/fire_load_table.json'
EXE = ROOT/'simulation/build/baseline/cfast-baseline.exe'
THRESHOLDS = (400, 450, 500)
LABELS = {'FO':'fo', 'FGI':'fgi', 'BD':'backdraft'}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    baseline = (BASE/'case.in').read_bytes()
    cls = json.loads(TABLE.read_text(encoding='utf-8'))['classes']['coldstore_pu_lining']
    original = json.loads((BASE/'model.json').read_text(encoding='utf-8'))
    fuel = copy.deepcopy(original['fuel_groups'][0])
    fuel.pop('initial_time_s'); fuel.pop('room_rule_curve')
    fuel.update(id='ROOM_LINING', room='ROOM', position_m=[4.375,9.,0.],
                energy_MJ=43765., peak_kW=200000., growth_kW_s2=1000/cls['t_alpha']**2,
                hrrpua_kW_m2=cls['rhrf'], fuel_area_m2=500.2,
                lining_ignition_C=cls['lining_ignition_C'])
    # The emitting lining area is not the horizontal flame footprint. Preserve
    # its energy/power envelope, then cap only the native horizontal fire area.
    t, q, _ = fire_curve(fuel, 500.2)
    area = [min(157.5, max(.1, v/cls['rhrf'])) for v in q]
    fuel['room_rule_curve'] = dict(t=t, q=q, area=area)
    assert abs(np.trapezoid(q,t)/1000-43765) < 1e-6
    sensor = gas_proxy_plate(original, original['rooms'][0], fuel, 'GP_ROOM_LINING')
    sensor['xyz'][2] = sensor['solver_xyz'][2] = 6.405-.5
    sensor.update(used_for_ignition=True, basis='P5 fixed 0.5 m below ceiling; T4b material/corner/normal reused; upper-gas proxy unvalidated')
    for threshold in THRESHOLDS:
        dest = OUT/str(threshold); dest.mkdir(exist_ok=True)
        if (dest/'attempt.json').exists():
            raise RuntimeError('Already attempted; immutable inputs: '+str(dest))
        f = copy.deepcopy(fuel)
        f['room_rule_trigger'] = dict(criterion='TEMPERATURE', target_id=sensor['id'], setpoint=threshold)
        f['lining_ignition_C'] = threshold
        model = copy.deepcopy(original)
        model['fuel_groups'].append(f)
        model['room_fire_rule'] = {'prepared':True}
        # Generate only the new MATL/DEVC/FIRE/CHEM/TABL. The original P1 bytes
        # remain the prefix, preserving the first fire's identity and every vent.
        added_model = copy.deepcopy(model); added_model['fuel_groups'] = [f]
        generated = make_deck(added_model, [], [sensor]).replace('SOOT_YIELD=0.02', 'SOOT_YIELD=0.1')
        additions = [line for line in generated.splitlines()
                     if line.startswith("&MATL ID='M1'") or line.startswith('&DEVC')
                     or line.startswith(('&FIRE','&CHEM','&TABL'))]
        newline = '\r\n' if b'\r\n' in baseline else '\n'
        deck = baseline + (newline+newline.join(additions)+newline).encode('ascii')
        assert deck.startswith(baseline) and deck.count(b'&FIRE ')==2
        assert b'&CFBT' not in deck and b"TYPE='MECHANICAL'" not in deck
        oldchem = next(line for line in baseline.decode('ascii').splitlines() if line.startswith('&CHEM'))
        newchem = next(line for line in additions if line.startswith('&CHEM'))
        assert oldchem.replace("ID='F_PU'", "ID='F_ROOM_LINING'")==newchem
        (dest/'case.in').write_bytes(deck)
        save(dest/'model.json', model)
        save(dest/'input-evidence.json', dict(
            scenario=f'P5-{threshold}', threshold_C=threshold, default_lining_ignition_C=cls['lining_ignition_C'],
            baseline_deck_sha256=sha(BASE/'case.in'), baseline_prefix_unchanged=True,
            deck_sha256=sha(dest/'case.in'), engine_sha256=sha(EXE), fire_load_table_sha256=sha(TABLE),
            energy_MJ=43765., lining_area_m2=500.2, power_cap_kW=200000.,
            alpha_kW_s2=fuel['growth_kW_s2'], prescribed_peak_kW=max(q),
            prescribed_peak_after_ignition_s=t[int(np.argmax(q))], supply_end_after_ignition_s=t[-1],
            integrated_supply_MJ=float(np.trapezoid(q,t)/1000), fire_location_m=fuel['position_m'],
            sensor=sensor, wall_budget_s=1800, fan='OFF', output_step_s=5,
            assumptions=[
                '450 C and sensitivities 400/500 are user assumptions; equivalence to 10-15 kW/m2 is unvalidated',
                'Native ignition uses plate surface temperature > setpoint, not upper-layer temperature directly',
                'T4b 0.1 mm steel, emissivity 0.05; fixed corner 0.3 m from walls, exactly 0.5 m below ceiling',
                'Sensor may receive local plume/ceiling-jet heating; report plate and bulk upper gas separately',
                'Aggregate lining represented by one floor-centre fire; native footprint capped at 157.5 m2',
                '43765 MJ follows requested rounded budget; 500.2*0.1*35*25 would be 43767.5 MJ',
                '200 MW is a cap, not imposed instantaneous burning; existing 70/30 growth/decay energy allocation',
                'Fast uses class t_alpha=150 s: alpha=1000/150^2; no extra room-area power cap',
                'Cavity budget preserved and ROOM budget added as explicitly requested; no inventory deduction',
                'Stock oxygen limitation and combustion chemistry unchanged; no forced ignition or project reactions']))
    print(json.dumps({'prepared':list(THRESHOLDS),'peak_kW':max(q),'sensor_xyz':sensor['xyz'],
                      'energy_MJ':float(np.trapezoid(q,t)/1000)}, ensure_ascii=False))


def run(threshold):
    dest = OUT/str(threshold)
    evidence = json.loads((dest/'input-evidence.json').read_text(encoding='utf-8'))
    assert sha(EXE)==evidence['engine_sha256'] and sha(dest/'case.in')==evidence['deck_sha256']
    with (dest/'attempt.json').open('x',encoding='utf-8') as f:
        json.dump({'authorized_runs':1,'threshold_C':threshold,'budget_s':1800},f)
    try:
        result = execute(EXE,dest,(dest/'case.in').read_text(encoding='ascii'),'',3600,1800,stall_timeout_s=0)
        save(dest/'run-summary.json',result['run'])
        print(json.dumps(result['run'],ensure_ascii=False))
    except (ValueError,OSError,StopIteration) as exc:
        # Stock 7.7.7 can exit normally at 3600 but output only through 3595.
        # Retain that limitation explicitly; never launch a replacement run.
        log=(dest/'case.log').read_text(errors='replace')
        c,_,_=read_native_csv(dest/'case_compartments.csv')
        if 'NORMAL EXIT' not in log.upper() or c['Time'][-1]<3595:raise
        save(dest/'run-summary.json',dict(normal_exit=True,last_csv_s=float(c['Time'][-1]),
            validator_error=str(exc),endpoint_sample_missing=True,rerun=False))
        print('Native NORMAL EXIT; final 5 s sample missing; no rerun')


def analyze_case(path, threshold=None):
    model = json.loads((path/'model.json').read_text(encoding='utf-8'))
    c,_,cu = read_native_csv(path/'case_compartments.csv')
    m,_,mu = read_native_csv(path/'case_masses.csv')
    v,vid,_ = read_native_csv(path/'case_vents.csv')
    t=c['Time']; n=len(t)
    assert np.array_equal(t,m['Time']) and np.array_equal(t,v['Time'])
    assert cu['ULO2_1']=='mol_frac' and mu['ULMTUHC_1']=='kg'
    normal='NORMAL EXIT' in (path/'case.log').read_text(errors='replace').upper()
    assert normal and t[-1]>=3595, 'Incomplete run: report without extrapolation or rerun'
    final_native_s=float(re.search(r'T\s*=\s*([0-9.Ee+\-]+)',(path/'case.status').read_text()).group(1))
    assert final_native_s>=3600
    def peak(a):
        j=int(np.argmax(a)); return {'value':float(a[j]),'time_s':float(t[j])}
    def first(a, value):
        hits=np.flatnonzero(np.asarray(a)>=value)
        return float(t[hits[0]]) if len(hits) else None
    openings={op['id']:{'fraction':v[next(k for k in v if k.startswith('WF_') and vid[k]==op['id'])]}
              for op in model['openings']}
    states={}; inventory={}
    for j,f in enumerate(model['fuel_groups'],1):
        inventory[f['id']]={'actual_HRR_W':c[f'HRR_{j}']}
    for i,room in enumerate(model['rooms'],1):
        total=sum(m[f'ULM{s}_{i}'] for s in ('N2','O2','CO2','CO','HCN','HCL','TUHC','H2O','OD'))
        assert np.all(total>0)
        states[room['id']]={
            'T_upper_C':c[f'ULT_{i}'],'o2_upper_vol':c[f'ULO2_{i}'],'o2_lower_vol':c[f'LLO2_{i}'],
            'upper_mass_kg':total,'fuel_upper_kg':m[f'ULMTUHC_{i}'],
            'fuel_upper_J':m[f'ULMTUHC_{i}']*25e6,'bulk_HRR_W':np.zeros(n),
            'received_door_jet_HRR_W':c[f'DJET_{i}']}
    native={'zone':c,'slabs':[],'vents':[]}
    common=evaluate(model,dict(time_s=t,rooms=states,phenomena=classify(model,native,states,[],[]),
        solid_fuel_inventory=inventory,opening_states=openings,ignitions=[],candidates=[],directional_vent_reactions=[]))
    series={'time_s':t.tolist()}; summary={}
    for i,room in enumerate(model['rooms'],1):
        rid=room['id'];s=states[rid]
        own=sum((inventory[f['id']]['actual_HRR_W'] for f in model['fuel_groups'] if f['room']==rid), np.zeros(n))/1000
        vals=dict(T_upper_C=s['T_upper_C'],O2_upper_vol_percent=s['o2_upper_vol']*100,
            fuel_upper_mass_fraction=s['fuel_upper_kg']/s['upper_mass_kg'],source_HRR_kW=own,
            door_jet_kW=s['received_door_jet_HRR_W']/1000,
            **{label:100*np.asarray(common[rid][key]['scores']['degree']) for label,key in LABELS.items()})
        assert all(np.isfinite(a).all() for a in vals.values())
        series[rid]={key:a.tolist() for key,a in vals.items()}
        series[rid]['rollover_active']=common[rid]['fgi']['rollover']['active']
        summary[rid]=dict(temperature_peak_C=peak(vals['T_upper_C']),source_HRR_peak_kW=peak(own),
            door_jet_peak_kW=peak(vals['door_jet_kW']),
            indices={k:dict(peak=peak(vals[k]),first_70_s=first(vals[k],70),first_100_s=first(vals[k],100)) for k in LABELS})
    result=dict(rooms=summary,last_csv_s=float(t[-1]),normal_exit=normal,
                native_final_status_s=final_native_s,endpoint_sample_missing=bool(t[-1]<3600),
                execution=json.loads((path/'execution-state.json').read_text(encoding='utf-8')),
                time_basis='first 5 s native sample, no interpolation; no extrapolation of last 5 s')
    if threshold is not None:
        dev,_,_=read_native_csv(path/'case_devices.csv'); assert np.array_equal(t,dev['Time'])
        first_ign=first(c['IGN_2'],.5)
        active=np.flatnonzero(c['HRR_2']>0)
        result.update(threshold_C=threshold,status='미착화' if first_ign is None else '착화',
            ignition_first_sample_s=first_ign,
            ignition_bracket_s=None if first_ign is None else [max(0,first_ign-5),first_ign],
            actual_burning_first_sample_s=float(t[active[0]]) if len(active) else None,
            actual_burning_sample_span_s=float(len(active)*5),
            plate_peak_C=peak(dev['TRGSURT_1']),sensor_local_gas_peak_C=peak(dev['TRGGAST_1']),
            upper_peak_minus_threshold_C=summary['ROOM']['temperature_peak_C']['value']-threshold,
            plate_peak_minus_threshold_C=float(max(dev['TRGSURT_1'])-threshold))
        j=int(np.flatnonzero(c['IGN_2']>=.5)[0]) if first_ign is not None else None
        result['at_first_ignition_sample']=None if j is None else dict(
            upper_C=float(c['ULT_1'][j]),plate_C=float(dev['TRGSURT_1'][j]),
            sensor_local_gas_C=float(dev['TRGGAST_1'][j]),HRR_kW=float(c['HRR_2'][j]/1000))
        result['upper_gas_first_threshold_sample_s']=first(c['ULT_1'],threshold)
        series['sensor']={'plate_C':dev['TRGSURT_1'].tolist(),'local_gas_C':dev['TRGGAST_1'].tolist()}
        save(path/'summary.json',result); save(path/'timeseries.json',series)
        save(path/'condition-scores.json',common)
    return result,series


def report():
    base,base_series=analyze_case(BASE)
    cases={str(k):analyze_case(OUT/str(k),k) for k in THRESHOLDS}
    save(OUT/'comparison.json',{'P1':base,**{k:v[0] for k,v in cases.items()}})
    save(OUT/'P1-current-timeseries.json',base_series)
    sys.path.insert(0,str(ROOT/'simulation/results/ui_C9_20261102/plot-deps'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for k,(result,series) in cases.items():
        t=np.asarray(series['time_s']); b=base_series['ROOM']; s=series['ROOM']
        fig,axs=plt.subplots(4,1,figsize=(13,10),sharex=True,layout='constrained')
        fig.suptitle(f'P5 {k} C plate threshold vs P1 | stock CFAST | fan OFF | condition indices')
        for ax,key,label in zip(axs[:3],('T_upper_C','O2_upper_vol_percent','fuel_upper_mass_fraction'),
                              ('Upper T (C)','Upper O2 (vol %)','Unburned fuel (kg/kg)')):
            ax.plot(base_series['time_s'],b[key],color='#888888',ls='--',label='P1')
            ax.plot(t,s[key],color='#b53729',label=f'P5 {k}');ax.set_ylabel(label);ax.legend(loc='upper right')
        for key,col in zip(LABELS,('#df2d28','#863bad','#b72666','#d7830b')):
            axs[3].plot(base_series['time_s'],b[key],color=col,ls='--',alpha=.45)
            axs[3].plot(t,s[key],color=col,label=key)
        for limit in (70,100):axs[3].axhline(limit,color='#777777',ls=':',lw=1)
        axs[3].set_ylabel('Index (not probability)');axs[3].legend(ncol=4)
        for ax in axs:
            for at in (780,1320,1500,2100):ax.axvline(at,color='#405767',ls='--',alpha=.6,lw=1)
            ax.grid(alpha=.2);ax.set_xlim(0,3600)
        for at in (780,1320,1500,2100):axs[0].text(at+6,.98,str(at),rotation=90,va='top',transform=axs[0].get_xaxis_transform())
        axs[3].set_xlabel('Time (s) | dashed curves: P1 | CSV last sample 3595 s')
        fig.savefig(OUT/f'P5-{k}-comparison.png',dpi=155);plt.close(fig)
    with (OUT/'index-crossings.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['scenario','room','index','peak','first_70_s','first_100_s'])
        for name,obj in [('P1',base)]+[(f'P5-{k}',v[0]) for k,v in cases.items()]:
            for rid,r in obj['rooms'].items():
                for key,item in r['indices'].items():w.writerow([name,rid,key,item['peak']['value'],item['first_70_s'],item['first_100_s']])
    print(json.dumps({'P1':base,**{k:v[0] for k,v in cases.items()}},ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','report'])
    p.add_argument('--threshold',type=int,choices=THRESHOLDS)
    args=p.parse_args()
    if args.action=='run':
        if args.threshold is None:p.error('--threshold required')
        run(args.threshold)
    else:globals()[args.action]()
