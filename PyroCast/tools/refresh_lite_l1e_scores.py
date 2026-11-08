"""Apply the final §1.5.5 definitions to saved states; never integrate."""
import hashlib,json,time
from types import SimpleNamespace
import numpy as np
import run_lite_l1e as runmod
from pyrocast_lite.adapter import prepare
from pyrocast_lite.result_adapter import shared_conditions
from pyrocast_lite.montecarlo import aggregate,condition_summary

def refresh(folder,raw,params,statepath,sample=None):
    r=runmod.read(folder/'result.json');m,_=prepare(raw,params)
    for e in r['events']:
        m.activation[e['room']]=e['condition_time_s'];m.pending.discard(e['room'])
    h=hashlib.sha256(statepath.read_bytes()).hexdigest()
    state=np.load(statepath);m.sol=SimpleNamespace(t=state['t'],y=state['y'],success=r['ok'])
    r['shared_conditions']=shared_conditions(m,r)
    r['lite_revision']='L1e_section1.5'
    r.pop('rollover',None)
    r['rollover_state_source']='shared_conditions.rooms.<cell>.FGI.rollover'
    r['score_revision']='1.5.5_20261025_final_three_factor_AND'
    runmod.base.save(folder/'result.json',r)
    if sample:
        old=runmod.read(folder/'summary.json');s=condition_summary(m,r,sample)
        for k in ('times','solver_fallback','selected_attempt','balance_diagnostic','failure'):s[k]=old[k]
        runmod.base.save(folder/'summary.json',s)
    else:s=None
    assert hashlib.sha256(statepath.read_bytes()).hexdigest()==h
    return s,{'state':str(statepath),'sha256':h,'unchanged':True}

def main():
    raise SystemExit("Superseded: use refresh_physics_p0.py with explicit scenario, playback and a new output path; legacy definitions must not overwrite new indices.")
    out=runmod.OUT;start=time.perf_counter()
    previous=runmod.read(out/'mc-aggregate.json')
    assert len(list((out/'mc').glob('*/summary.json')))==20
    params={'smooth_state_bounds':True,'upper_combustion_enabled':True}
    rows=[];checks=[]
    for folder in sorted((out/'mc').iterdir()):
        sample=runmod.read(folder/'sample.json');old=runmod.read(folder/'summary.json')
        s,c=refresh(folder,sample['scenario'],params,folder/old['selected_attempt']/'state.npz',sample)
        rows.append(s);checks.append(c)
    a=aggregate(rows)
    for k in ('wall_seconds','numerical_gate_passed','solver_fallback_count'):a[k]=previous[k]
    for w in a['worst_including_mandatory'].values():
        if w and w.get('sample_id'):w['opening_combination']=runmod.read(out/'mc'/w['sample_id']/'sample.json')['openings']
    a['score_revision']='1.5.5 final; three-factor AND separate from legacy boolean context'
    a['score_refresh_wall_seconds']=time.perf_counter()-start
    runmod.base.save(out/'mc-aggregate.json',a)
    for key in ('B3','3F'):
        raw=runmod.read(runmod.base.inputs()[key]);raw['duration_s']=1200 if key=='B3' else 3600
        if key=='3F':raw['room_rule_r8']={'preset':'standard','room_supply':'item_peak'}
        _,c=refresh(out/'validation'/key,raw,params,out/'validation'/key/'state.npz');checks.append(c)
    runmod.base.save(out/'score-refresh-verification.json',{'no_integration':True,'state_checks':checks,
        'rules':['Thomas internal surface excludes effective opening area','T/F/O AND independent of legacy context',
            'legacy fire_zone temperature-dependent LFL used in shared scoring; mixed-Hc unknown',
            'FGI hot_C taken from gas.hot_C as specified; no new physical thresholds']})
    runmod.reaggregate()
    print('Refreshed saved scores only',len(rows),flush=True)
if __name__=='__main__':main()
