"""Sequential, same-engine timing and result comparison; writes only new folders."""
import argparse
import json
from pathlib import Path
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pyrocast_cfbt.spread import simulate
from pyrocast_cfbt.native import execute,digest
from pyrocast_cfbt.deck import make_deck,candidates,gas_sidecar
from pyrocast_cfbt.model import normalize


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',default='cad_opening_30min')
    parser.add_argument('--engine',type=Path,default=ROOT/'build/cfbt/cfast-cfbt.exe')
    parser.add_argument('--out',type=Path,default=ROOT/'results/iteration_benchmark_20261021')
    parser.add_argument('--horizon-cost',action='store_true')
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    raw=json.loads((ROOT/'results'/args.case/'scenario.json').read_text('utf-8'))
    report={'case':args.case,'engine_sha256':digest(args.engine),'runs':{},'status':'running',
            'scope':'same physics/thresholds/targets; only numerical execution budget and iteration mode differ'}
    def save():
        (args.out/'comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    outputs={}
    for mode in ('earliest_single','fixed_point'):
        print('START',mode,flush=True);start=time.monotonic()
        scenario=json.loads(json.dumps(raw));scenario.setdefault('spread',{}).update(
            iteration_mode=mode,max_runs=12,max_passes=6,wall_time_budget_s=2400,run_timeout_s=480)
        result=simulate(scenario,args.engine,args.out/mode);outputs[mode]=result
        report['runs'][mode]={'wall_seconds':time.monotonic()-start,
            'native_seconds':sum(r['wall_seconds'] for r in result['runs']),
            'cache_hits':[r['cache_hit'] for r in result['runs']],
            'native_runs':result['successful_runs_count'],'attempts':result['attempted_runs_count'],
            'terminated':result['terminated'],'error':result['error'],
            'ignitions':{e['group']:e['t_ign_s'] for e in result['ignitions']},
            'fo':{e['room']:e['t_ign_s'] for e in result['fo_transitions']},
            'iteration':result['iteration']}
        save();print('DONE',mode,json.dumps({k:v for k,v in report['runs'][mode].items() if k not in ('iteration',)},ensure_ascii=False),flush=True)
    a,b=(outputs[x] for x in ('earliest_single','fixed_point'))
    diffs={}
    for rid in a['rooms']:
        diffs[rid]={key:float(np.max(np.abs(np.asarray(a['rooms'][rid][key])-np.interp(a['time_s'],b['time_s'],b['rooms'][rid][key]))))
                    for key in ('T_upper_C','o2_upper_vol','fuel_upper_kg','optical_density_upper_m_inv')}
    report['max_time_series_differences']=diffs
    prior=json.loads((ROOT/'results'/args.case/'result.json').read_text('utf-8'))
    report['legacy_regression']={'same_engine':prior['engine_sha256']==a['engine_sha256'],
        'same_final_input':prior['final_input_sha256']==a['final_input_sha256'],
        'ignition_difference_s':{e['group']:e['t_ign_s']-next((p['t_ign_s'] for p in prior['ignitions'] if p['group']==e['group']),e['t_ign_s']) for e in a['ignitions']}}
    report['legacy_regression']['max_state_differences']={key:max(float(np.max(np.abs(np.asarray(a['rooms'][rid][key])-np.interp(a['time_s'],prior['time_s'],prior['rooms'][rid][key])))) for rid in a['rooms'])
        for key in ('T_upper_C','o2_upper_vol','fuel_upper_kg','optical_density_upper_m_inv')}
    report['screening_differences']={tag:sum(int(np.count_nonzero(np.asarray(a['phenomena'][rid]['tags'][tag])!=b['phenomena'][rid]['tags'][tag])) for rid in a['rooms'])
        for tag in ('FGI_POTENTIAL','BD_POTENTIAL','FO_thermal','UPPER_GAS','VENT_FLAME')}
    save()
    if args.horizon_cost:
        report['horizon_cost']={'basis':'one native run, same final fire/FO schedule; new post-1800s ignitions are not searched','runs':{}}
        for duration in (1800,3600):
            print('START horizon',duration,flush=True)
            scenario=normalize(a['scenario']);scenario['duration_s']=duration
            start=time.monotonic()
            native=execute(args.engine,args.out/f'horizon_{duration}',make_deck(scenario,a['ignitions'],candidates(scenario),a['fo_transitions']),gas_sidecar(scenario),duration,600)
            report['horizon_cost']['runs'][str(duration)]={'native_seconds':native['run']['wall_seconds'],
                'adapter_wall_seconds':time.monotonic()-start,'cache_hit':native['run']['cache_hit'],
                'input_sha256':native['run']['input_sha256'],
                'output_bytes':sum(p.stat().st_size for p in Path(native['run']['folder']).glob('case*.csv')),
                'output_samples':len(native['zone']['Time'])}
            save();print('DONE horizon',duration,report['horizon_cost']['runs'][str(duration)],flush=True)
    report['status']='complete';save()


if __name__=='__main__':main()
