"""v5 section3.0a-3: one run after removal of cumulative state."""
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
import cProfile
import hashlib
import json
import pstats
import time
from unittest.mock import patch
import run_lite_l1 as base
import numpy as np
import scipy.integrate._ivp.bdf as bdf
from pyrocast_lite.adapter import prepare
from pyrocast_lite.runner import run,results

OUT=base.ROOT/'simulation/results/lite_v5_sparse_20261025'
OLD=base.ROOT/'simulation/results/lite_l1e_20261025/validation/3F'
PARAMS={'oxygen_inventory_mode':False,'smooth_state_bounds':True,'upper_combustion_enabled':True,'remove_cumulative_state':True}
def read(p):return json.loads(p.read_text('utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    if (OUT/'started.json').exists():raise RuntimeError('One profile already attempted; no automatic rerun')
    guarded=list((base.ROOT/'simulation/pyrocast_lite').glob('*.py'))
    guarded += [base.Path(p) for p in read(base.ROOT/'simulation/results/lite_l1_20261025/source-guard.json')]
    hashes={str(p):sha(p) for p in guarded}
    spec=base.ROOT/'specs/Claude명세-확정상태-v5-20261025.md'
    base.save(OUT/'started.json',{'spec':str(spec),'spec_bytes':spec.stat().st_size,'spec_sha256':sha(spec),
        'parameters':PARAMS,'workers':1,'profile_runs':1,'budget_s':1200,'code_sha256':hashes,
        'scope':'cumulative removal and local sparsity only; no further optimization, MC, native, UI or physical changes'})
    raw=read(base.inputs()['3F']);raw['duration_s']=3600.
    raw['room_rule_r8']={'preset':'standard','room_supply':'item_peak'}
    base.save(OUT/'input.json',raw)
    start=time.perf_counter();model,manifest=prepare(raw,PARAMS);prep=time.perf_counter()-start
    assert not model.P.get('oxygen_inventory_mode')
    assert len(model.y0())==11*model.N
    from scipy.optimize._numdiff import group_columns
    matrix=model.sparsity()
    base.save(OUT/'static-sparsity.json',{'state_count':matrix.shape[0],'nnz':matrix.nnz,
        'column_groups':int(group_columns(matrix).max()+1),'cumulative_states':0})
    base.save(OUT/'rule_manifest.json',manifest)
    base.save(OUT/'contract.json',model.contract)
    counter={'rhs_calls':0,'rhs_seconds':0.,'rhs_jac_calls':0,'rhs_jac_seconds':0.,
        'jac_calls':0,'jac_seconds':0.,'jac_initial_calls':0,'jac_initial_seconds':0.,
        'bdf_initializations':0,'bdf_initialization_seconds':0.,'rhs_initialization_calls':0,
        'rhs_initialization_seconds':0.}
    context={'jac':0,'init':0,'last_notice':time.perf_counter()}
    original_rhs=model.rhs;original_jac=bdf.num_jac;original_init=bdf.BDF.__init__
    def counted_rhs(t,y,diag=False):
        stamp=time.perf_counter()
        try:return original_rhs(t,y,diag)
        finally:
            elapsed=time.perf_counter()-stamp
            if not diag:
                counter['rhs_calls']+=1;counter['rhs_seconds']+=elapsed
                if context['jac']:
                    counter['rhs_jac_calls']+=1;counter['rhs_jac_seconds']+=elapsed
                if context['init']:
                    counter['rhs_initialization_calls']+=1;counter['rhs_initialization_seconds']+=elapsed
                now=time.perf_counter()
                if now-context['last_notice']>=30:
                    print('PROGRESS trial_time_s',round(t,3),'rhs_calls',counter['rhs_calls'],flush=True)
                    context['last_notice']=now
    def counted_jac(*args,**kwargs):
        stamp=time.perf_counter();context['jac']+=1;counter['jac_calls']+=1
        try:return original_jac(*args,**kwargs)
        finally:
            elapsed=time.perf_counter()-stamp;counter['jac_seconds']+=elapsed;context['jac']-=1
            if context['init']:
                counter['jac_initial_calls']+=1;counter['jac_initial_seconds']+=elapsed
    def counted_init(self,*args,**kwargs):
        stamp=time.perf_counter();context['init']+=1;counter['bdf_initializations']+=1
        try:return original_init(self,*args,**kwargs)
        finally:
            counter['bdf_initialization_seconds']+=time.perf_counter()-stamp;context['init']-=1
    model.rhs=counted_rhs
    profiler=cProfile.Profile()
    print('START one profile: oxygen_inventory_mode=False; states',len(model.y0()),flush=True)
    try:
        with patch.object(bdf,'num_jac',counted_jac),patch.object(bdf.BDF,'__init__',counted_init):
            profiler.enable()
            try:run(model,3600,10,1200)
            finally:profiler.disable()
    finally:
        model.rhs=original_rhs
        profiler.dump_stats(str(OUT/'integration.prof'))
        base.save(OUT/'counters.json',counter)
    result=results(model)
    base.save(OUT/'result.json',result)
    np.savez_compressed(OUT/'state.npz',t=model.sol.t,y=model.sol.y)
    segments=model.integration['segments'];wall=model.integration['wall_seconds']
    counter.update(rhs_mean_ms=1000*counter['rhs_seconds']/max(counter['rhs_calls'],1),
        reported_nfev=model.integration['nfev'],reported_njev=sum(s['njev'] for s in segments),
        reported_nlu=sum(s['nlu'] for s in segments),event_restarts=model.integration['event_restarts'],
        input_knot_restarts=sum(s['reason']=='input_knot' for s in segments),
        accepted_steps=model.integration['accepted_steps'],profiled_integration_s=wall,
        jac_noninitial_calls=counter['jac_calls']-counter['jac_initial_calls'],
        jac_noninitial_seconds=counter['jac_seconds']-counter['jac_initial_seconds'])
    stats=pstats.Stats(profiler)
    funcs=[{'file':k[0],'line':k[1],'function':k[2],'primitive_calls':v[0],'calls':v[1],
        'self_seconds':v[2],'cumulative_seconds':v[3]} for k,v in stats.stats.items()]
    selfsort=sorted(funcs,key=lambda x:x['self_seconds'],reverse=True)
    cumsort=sorted(funcs,key=lambda x:x['cumulative_seconds'],reverse=True)
    base.save(OUT/'functions.json',{'by_self_time':selfsort,'by_cumulative_time':cumsort})
    with (OUT/'profile-top.txt').open('w',encoding='utf-8') as stream:
        pstats.Stats(profiler,stream=stream).strip_dirs().sort_stats('tottime').print_stats(30)
        pstats.Stats(profiler,stream=stream).strip_dirs().sort_stats('cumulative').print_stats(30)
    old=read(OLD/'result.json');old_state=np.load(OLD/'state.npz')
    old_physical=np.delete(old_state['y'],8*model.N,axis=0)
    def burning(r):
        groups={}
        for row in r['room_summary']:
            t=row['first_actual_positive_HRR_s'];room=row['original_room']
            if t is not None:groups[room]=min(groups.get(room,float('inf')),t)
        return groups
    oldburn=burning(old);newburn=burning(result)
    samegrid=np.array_equal(model.sol.t,old_state['t'])
    same_shape=model.sol.y.shape==old_physical.shape
    pairs=[{'room':r,'old_s':oldburn[r],'new_s':newburn[r],'difference_s':newburn[r]-oldburn[r]}
        for r in sorted(set(oldburn)&set(newburn))]
    old_events={e['room']:e for e in old['events']};event_diff=[]
    for e in result['events']:
        if e['room'] in old_events:
            event_diff.append({'room':e['room'],'condition_time_difference_s':e['condition_time_s']-old_events[e['room']]['condition_time_s'],
                'supply_start_difference_s':e['supply_start_s']-old_events[e['room']]['supply_start_s']})
    comparison={'reference':str(OLD),'reference_wall_s':old['integration']['wall_seconds'],
        'manifest_identical':manifest==read(OLD/'rule_manifest.json'),
        'old_burning':oldburn,'new_burning':newburn,'burning_set_identical':set(oldburn)==set(newburn),
        'ignition_comparison':pairs,'time_within_10s':all(abs(p['difference_s'])<=10 for p in pairs),
        'event_time_differences':event_diff,'output_grid_identical':samegrid,
        'state_arrays_identical':bool(samegrid and same_shape and np.array_equal(model.sol.y,old_physical)),
        'max_abs_state_difference_mixed_units':float(np.max(abs(model.sol.y-old_physical))) if samegrid and same_shape else None}
    if samegrid and same_shape:
        absdiff=abs(model.sol.y-old_physical)
        relative=absdiff/np.maximum(abs(old_physical),1e-12)
        blocks={};n=model.N
        for i,label in enumerate(('pressure_Pa','upper_volume_m3','upper_K','lower_K','upper_O2_mass','lower_O2_mass','upper_fuel_mass','lower_fuel_mass')):
            blocks[label]={'max_abs':float(absdiff[i*n:(i+1)*n].max()),'max_relative':float(relative[i*n:(i+1)*n].max())}
        blocks['walls_K']={'max_abs':float(absdiff[8*n:].max()),'max_relative':float(relative[8*n:].max())}
        comparison.update(max_relative_state_difference=float(relative.max()),relative_denominator='max(abs(reference),1e-12) per element; removed E excluded',
            state_tolerance_pass=bool(relative.max()<=1e-6),state_difference_by_block=blocks)
        comparison['events_exact']=len(result['events'])==len(old['events']) and all(x['condition_time_difference_s']==0 and x['supply_start_difference_s']==0 for x in event_diff)
        comparison['gate_passed']=bool(result['ok'] and comparison['state_tolerance_pass'] and comparison['burning_set_identical'] and comparison['events_exact'])
    frozen=all(sha(base.Path(p))==v for p,v in hashes.items())
    summary={'complete':result['ok'],'oxygen_inventory_mode':False,'state_count':len(model.y0()),
        'times':{'preprocess_s':prep,'profiled_integration_s':wall,'postprocess_s':result['postprocess_wall_seconds']},
        'counters':counter,'top5_self':selfsort[:5],'top5_cumulative':cumsort[:5],
        'comparison':comparison,'guarded_files_unchanged':frozen,'guarded_file_count':len(hashes),
        'physical_runs':1,'parallel_workers':1,'optimization_applied':'cumulative state removal + local sparsity only','stopped_after_stage3':True,
        'measurement_limit':'cProfile and wrappers add overhead; nested cumulative times must not be summed; RHS timings exclude postprocessing; counts include finite difference RHS calls omitted by nfev'}
    base.save(OUT/'summary.json',summary);base.save(OUT/'counters.json',counter)
    print('FINISHED',json.dumps({'wall_s':wall,'complete':result['ok'],'counters':counter,
        'same_burning':comparison['burning_set_identical'],'same_states':comparison['state_arrays_identical'],
        'frozen':frozen},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
