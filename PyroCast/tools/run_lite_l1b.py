"""Section 1.2: two isolated comparisons and one 3F run, no native execution."""
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import run_lite_l1 as base
from pyrocast_lite.adapter import prepare
from pyrocast_lite.runner import run,results
from pyrocast_cfbt.deck import make_deck
from pyrocast_cfbt.native import native_float

ROOT=base.ROOT
OUT=ROOT/'simulation/results/lite_l1b_20261025'
base.OUT=OUT


def physical_lines(deck):
    prefixes=('&TIME ','&INIT ','&MISC ',"&MATL ID='WALL'",'&COMP ','&VENT ',
              "&FIRE ID='F_primary'","&CHEM ID='F_primary'","&TABL ID='F_primary'")
    return [s for s in deck.splitlines() if s.startswith(prefixes)]


def read_native(folder):
    meta=json.loads((folder/'completed.json').read_text('utf-8'))
    csvpath=folder/'case_compartments.csv'
    expected=meta['files']['case_compartments.csv']
    if hashlib.sha256(csvpath.read_bytes()).hexdigest()!=expected:
        raise ValueError('Native CSV hash mismatch')
    with csvpath.open(encoding='utf-8-sig',newline='') as f:lines=list(csv.reader(f))
    array=np.array([[native_float(x) for x in r] for r in lines[4:] if r and r[0].strip()])
    values={name:array[:,i] for i,name in enumerate(lines[0])}
    units=dict(zip(lines[0],lines[3]))
    for key in ('HRR_1','HRR_E1'):
        if units[key]!='W':raise ValueError('Unexpected native HRR units')
        values[key]=values[key]/1000.
    if units['ULO2_1']!='mol_frac':raise ValueError('Unexpected native oxygen units')
    values['ULO2_1']=values['ULO2_1']*100.
    return values,meta


def first_limited(t,actual,expected):
    # Diagnostic tolerance only. Never used by the physical model or transitions.
    mask=(expected>1)&((expected-actual)>np.maximum(1.,expected*.001))
    return float(t[np.flatnonzero(mask)[0]]) if mask.any() else None


def isolated(name, parameters=None):
    folder=OUT/'isolation'/name
    if (folder/'started.json').exists():raise RuntimeError('No automatic repeat: '+str(folder))
    raw=json.loads(base.inputs()[name].read_text('utf-8'))
    raw['room_rule_r8']={'preset':'standard','room_supply':'item_peak'}
    start=time.perf_counter();m,manifest=prepare(raw,parameters);prep=time.perf_counter()-start
    native_folder=ROOT/f'simulation/results/room_rule_r5_20261025/compare/{name}/T1/baseline_native'
    bmodel=deepcopy(m.input_model)
    bmodel['fuel_groups']=[g for g in bmodel['fuel_groups'] if 'initial_time_s' in g]
    expected=make_deck(bmodel,[],[])
    actual=(native_folder/'case.in').read_text('utf-8')
    if physical_lines(expected)!=physical_lines(actual):
        raise ValueError('Baseline physical inputs differ; do not run a new native case')
    n,meta=read_native(native_folder)
    base.save(folder/'started.json',{'time':time.time(),'native_reference':str(native_folder),
                                   'primary_only':True,'physical_input_lines_equal':True,
                                   'passive_target_lines_excluded_from_input_comparison':True})
    m.pending.clear()  # Keep geometry and flow; prohibit every secondary source.
    run(m,1200,10,600)
    r=results(m);r['preprocess_wall_seconds']=prep
    r['isolation_mode']='initial_source_only; all secondary triggers disabled'
    base.save(folder/'result.json',r);base.save(folder/'rule_manifest.json',manifest)
    np.savez_compressed(folder/'state.npz',t=m.sol.t,y=m.sol.y)
    if not r['ok']:raise RuntimeError('Isolated run incomplete')
    t=m.sol.t;idx=m.rmap[m.initial_room];N=m.N
    native={k:np.interp(t,n['Time'],n[k]) for k in ('ULT_1','HGT_1','HRR_1','HRR_E1','ULO2_1')}
    lite={'ULT_1':m.sol.y[2*N+idx]-273.15,
          'HGT_1':(m.Va[idx]-np.clip(m.sol.y[N+idx],m.Vmin[idx],m.Va[idx]-m.Vmin[idx]))/m.Aa[idx],
          'HRR_1':np.array(r['rooms'][idx]['actual_HRR_kW']),
          'HRR_E1':np.array(r['rooms'][idx]['supply_HRR_kW']),
          'ULO2_1':m.sol.y[4*N+idx]*29/32*100}
    columns=['time_s']+[prefix+'_'+key for key in native for prefix in ('native','lite')]
    with (folder/'overlay.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.writer(f);writer.writerow(columns)
        writer.writerows([[float(t[j])]+[float(data[key][j]) for key in native for data in (native,lite)] for j in range(len(t))])
    peak_n=float(n['ULT_1'][n['Time']<=1200].max());peak_l=float(lite['ULT_1'].max())
    en=float(np.trapezoid(native['HRR_1'],t));el=float(np.trapezoid(lite['HRR_1'],t))
    snapshots={str(ts):{key:{'native':float(np.interp(ts,t,native[key])),
                            'lite':float(np.interp(ts,t,lite[key])),
                            'difference':float(np.interp(ts,t,lite[key]-native[key]))} for key in native} for ts in (300,600)}
    report={'case':name,'native_reference':str(native_folder),'native_engine_sha256':meta['signature']['engine'],
        'complete':True,'physical_input_lines_equal':True,'native_runs':0,
        'native_peak_upper_C':peak_n,'lite_peak_upper_C':peak_l,'peak_difference_percent_C':100*(peak_l/peak_n-1),
        'native_actual_energy_MJ':en/1000,'lite_actual_energy_MJ':el/1000,
        'actual_energy_difference_percent':100*(el/en-1),
        'max_abs_HRR_difference_kW':float(np.max(np.abs(lite['HRR_1']-native['HRR_1']))),
        'max_abs_interface_difference_m':float(np.max(np.abs(lite['HGT_1']-native['HGT_1']))),
        'first_oxygen_limited_sample_s':{'native':first_limited(t,native['HRR_1'],native['HRR_E1']),
                                        'lite':first_limited(t,lite['HRR_1'],lite['HRR_E1'])},
        'limited_diagnostic_tolerance':'expected>1kW and loss>max(1kW,0.1% expected); reporting only',
        'snapshots':snapshots,'wall_seconds':r['integration']['wall_seconds'],
        'classification':'thermal_transport_partition_priority' if abs(el/en-1)<.01 else 'combustion_limit_and_thermal_coupling',
        'causal_limit':'HRR comparison separates heat-input vs thermal-response discrepancy, not proof that one radiation term alone is the cause'}
    base.save(folder/'comparison.json',report)
    print(name,'isolated',json.dumps({k:report[k] for k in ('native_peak_upper_C','lite_peak_upper_C','actual_energy_difference_percent','classification','wall_seconds')}),flush=True)
    return report


def floor_compare():
    result=base.case('3F')
    native=json.loads((ROOT/'simulation/results/room_rule_r8_20261025/selected/analysis.json').read_text('utf-8'))
    def group(rows):
        d={}
        for r in rows:
            if r['actual_peak_kW']>0:
                rid=r['original_room'];time=r['first_actual_positive_HRR_s']
                if rid not in d or time<d[rid]:d[rid]=time
        return d
    ng=group(native['rows']);lg=group(result['room_summary'])
    ns=sorted(ng,key=lambda r:(ng[r],r));ls=sorted(lg,key=lambda r:(lg[r],r))
    # Primary comparison is original rooms. Cell comparison is reported separately.
    same_set=set(ng)==set(lg);same_order=ns==ls
    rows=[]
    for l in result['room_summary']:
        n=next(x for x in native['rows'] if x['cell']==l['cell']) if any(x['cell']==l['cell'] for x in native['rows']) else None
        rows.append({'cell':l['cell'],'original_room':l['original_room'],
            'native_first_actual_HRR_s':n['first_actual_positive_HRR_s'] if n else None,
            'lite_first_actual_HRR_s':l['first_actual_positive_HRR_s'],
            'native_upper_max_C':n['upper_max_C'] if n else None,'lite_upper_max_C':l['upper_max_C'],
            'lite_positive_duration_s':l['longest_positive_HRR_s']})
    comparison={'complete':result['ok'],'passed':bool(result['ok'] and same_set and same_order),
        'native_burning_original_rooms':ng,'lite_burning_original_rooms':lg,
        'sets_equal':same_set,'orders_equal':same_order,'native_order':ns,'lite_order':ls,
        'extra_lite_rooms':sorted(set(lg)-set(ng)),'missing_lite_rooms':sorted(set(ng)-set(lg)),
        'native_integration_s':native['native_wall_seconds'],'lite_integration_s':result['integration']['wall_seconds'],
        'rows':rows,'B2_context':'prior L1a full-spread boundary underprediction; section 1.2 explicitly allows L3',
        'interpretation':'same original-room set/order is a gate, not physical validation; output grids 5s vs 10s'}
    base.save(OUT/'L3/comparison.json',comparison)
    base.save(OUT/'status.json',{'L3':comparison['passed'],'stopped_at':'L3' if not comparison['passed'] else 'L4_pending',
         'reason':'room-set/order or completion gate' if not comparison['passed'] else 'L3 passed; balance gate required before MC',
         'native_runs':0,'MC':'not_run','thermal_or_combustion_repair':'requires user approval; not performed'})
    print('L3',json.dumps({k:comparison[k] for k in ('complete','passed','native_burning_original_rooms','lite_burning_original_rooms','lite_integration_s')},ensure_ascii=False),flush=True)


if __name__=='__main__':
    reports=[isolated(name) for name in ('B2','B3')]
    base.save(OUT/'isolation/comparison.json',reports)
    floor_compare()
