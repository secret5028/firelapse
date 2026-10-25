"""v8 stage3: serial B3 reference comparisons and one historical 3F run."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import hashlib,json,time
import numpy as np
import run_lite_l1 as base
from pyrocast_lite.adapter import prepare
from pyrocast_lite.runner import run,results
from pyrocast_lite.montecarlo import output_balance_diagnostic
from pyrocast_cfbt.native import read_native_csv
from run_lite_l1c import grouped

ROOT=base.ROOT
OUT=ROOT/'simulation/results/lite_v8_door_jet_20261026'
PARAMS=dict(smooth_state_bounds=True,upper_combustion_enabled=True,
            remove_cumulative_state=True,oxygen_inventory_mode=False,door_jet_enabled=True)
def read(p):return json.loads(p.read_text('utf-8'))

def gate(r):
    std=read(ROOT/'simulation/results/room_rule_r8_20261025/selected/analysis.json')
    agg=read(ROOT/'simulation/results/room_rule_r8_20261025/aggressive/partial-analysis.json')
    ns=grouped(std['rows']);na=grouped(agg['rows']);li=grouped(r['room_summary'])
    triggers={}
    for row in agg['rows']:
        t=row.get('trigger_estimate_s')
        if t is not None and t<=2850:
            rid=row['original_room'];triggers[rid]=min(triggers.get(rid,float('inf')),t)
    # The initial fire is not necessarily recorded as a trigger event.
    for rid,t in na.items():
        if t<=5:triggers.setdefault(rid,0.)
    differences=[]
    for a in sorted(li):
        for b in sorted(li):
            if a>=b or a not in na or b not in na:continue
            sign=lambda x:(x>0)-(x<0)
            if sign(na[a]-na[b])!=sign(li[a]-li[b]):
                differences.append(dict(a=a,b=b,native_times=[na[a],na[b]],lite_times=[li[a],li[b]]))
    subset=set(ns)<=set(li)<=set(triggers)
    return dict(horizon_s=2850,native_standard=ns,native_aggressive_actual=na,
        native_aggressive_triggered=triggers,lite=li,lite_full_3600=grouped(r['room_summary'],3600),
        subset_pass=subset,order_pass=not differences,order_differences=differences,
        passed=bool(r['ok'] and subset and not differences),native_aggressive_complete=False,
        order_basis='first actual positive solid HRR, native5s/lite10s; equal times are cohorts, not invented order')

def execute(name,raw,primary_only=False):
    folder=OUT/name
    if (folder/'started.json').exists():raise RuntimeError('Already attempted: '+name)
    base.save(folder/'started.json',dict(time=time.time(),parameters=PARAMS,primary_only=primary_only,
        code_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'simulation/pyrocast_lite').glob('*.py')}))
    base.save(folder/'input.json',raw)
    start=time.perf_counter();m,manifest=prepare(raw,PARAMS)
    if primary_only:m.pending.clear()
    prep=time.perf_counter()-start
    base.save(folder/'rule_manifest.json',manifest);base.save(folder/'contract.json',m.contract)
    run(m,raw['duration_s'],10,1200)
    r=results(m);r['lite_revision']='v8_stage3_door_jet_trial'
    r['engine_use']='stage3 gate comparison; not adopted for ranking/MC/operational playback'
    base.save(folder/'result.json',r);np.savez_compressed(folder/'state.npz',t=m.sol.t,y=m.sol.y)
    audit=output_balance_diagnostic(m);base.save(folder/'balance.json',audit)
    diag=[m.rhs(float(t),m.sol.y[:,j],True) for j,t in enumerate(m.sol.t)]
    checks=dict(max_heat_stoichiometry_error_W=max(abs(sum(d['door_jet_HRR_W'])-sum(d['door_jet_reaction_kg_s'])*m.P['dHc']) for d in diag),
        max_lower_oxygen_budget_excess_kg_s=max(float(np.max(d['door_jet_room_oxygen_kg_s']-d['door_jet_available_lower_oxygen_kg_s'])) for d in diag),
        min_upper_oxygen_mass_fraction=float(m.sol.y[4*m.N:5*m.N].min()),
        min_lower_oxygen_mass_fraction=float(m.sol.y[5*m.N:6*m.N].min()),
        min_fuel_mass_fraction=float(m.sol.y[6*m.N:8*m.N].min()),
        note='saved10s samples and independent RHS unit tests; not proof for every internal solver trial')
    summary=dict(complete=r['ok'],times=dict(preprocess_s=prep,integration_s=m.integration['wall_seconds'],
        postprocess_s=r['postprocess_wall_seconds'],total_s=time.perf_counter()-start),
        integration=m.integration,rooms=r['room_summary'],events=r['events'],balance=audit,reaction_checks=checks,
        door_jet_peaks=[{k:v[k] for k in ('vent','from','to','peak_kW','cumulative_heat_MJ')} for v in r['door_jet']['directions']],
        cumulative_door_jet_MJ=r['door_jet']['cumulative_heat_MJ'],cumulative_upper_MJ=r['upper_combustion']['cumulative_heat_MJ'])
    if name=='3F':summary['gate']=gate(r)
    base.save(folder/'summary.json',summary)
    print(json.dumps(dict(case=name,complete=r['ok'],seconds=summary['times']['total_s'],
        jet_MJ=summary['cumulative_door_jet_MJ'],balance=audit,gate=summary.get('gate')),ensure_ascii=False),flush=True)
    return summary

def native_reference():
    rows=[]
    for mode,rel in [('primary_only','T4/baseline_native'),('T4','T4/run_00'),('T0_final','T0/run_02')]:
        p=ROOT/'simulation/results/room_rule_r5_20261025/compare/B3'/rel/'case_compartments.csv'
        if not p.exists():continue
        data,ids,units=read_native_csv(p)
        rows.append(dict(mode=mode,path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
            jets=[dict(column=k,id=ids[k],units=units[k],peak=float(max(v))) for k,v in data.items() if 'DJET' in k]))
    base.save(OUT/'native-reference.json',rows)
    print('NATIVE',json.dumps(rows,ensure_ascii=False),flush=True)

if __name__=='__main__':
    native_reference()
    b3=read(base.inputs()['B3']);b3['duration_s']=1200
    execute('B3_primary_only',b3,True)
    execute('B3_transition',b3)
    raw=read(base.inputs()['3F']);raw['room_rule_r8']=dict(preset='standard',room_supply='item_peak');raw['duration_s']=3600
    execute('3F',raw)
