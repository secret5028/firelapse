"""Run the requested floor scenario only after the isolated r3 regression passes."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'simulation'))
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.spread import simulate
from pyrocast_cfbt.playback import package
from pyrocast_cfbt.native import digest
from pyrocast_cfbt.deck import gas_sidecar
from pyrocast_cfbt.reuse import prime_completed
from pyrocast_cfbt.practical import execution_limits

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output-root',type=Path,default=ROOT/'simulation/results/mixture_r3c_20261023')
    p.add_argument('--engine',type=Path,default=ROOT/'simulation/build/mixture_r3c/cfbt/cfast-cfbt.exe')
    args=p.parse_args();base=args.output_root.resolve();engine=args.engine.resolve()
    small=json.loads((base/'small/comparison.json').read_text('utf-8'))
    stress=json.loads((base/'stalled/comparison.json').read_text('utf-8'))
    if not small['differences']['smooth_vs_half_step']['accepted']:
        raise RuntimeError('Small-step convergence check failed')
    if stress['cases'].get('smooth',{}).get('status')!='completed':
        raise RuntimeError('Stalled case has not completed; do not start floor search')
    if not small['engines']['new']==stress['engines']['new']==digest(engine):
        raise RuntimeError('Requested engine differs from tested engine')
    source=ROOT/'simulation/results/floor_spread_20261022/r2_ventilated/scenario.json'
    m=json.loads(source.read_text('utf-8'))
    if small.get('radiation_cache_enabled')!=stress.get('radiation_cache_enabled'):
        raise RuntimeError('Cache policy differs between verification cases')
    m['engine_optimization']={'radiation_cache':bool(stress.get('radiation_cache_enabled'))}
    if bool(small.get('wall_cache_enabled'))!=bool(stress.get('wall_cache_enabled')):
        raise RuntimeError('Wall cache policy differs between verification cases')
    m['engine_optimization']['wall_cache']=bool(stress.get('wall_cache_enabled'))
    m['gas'].update(mixture_smooth_enabled=True,mixture_o2_width_vol=.01,
                    mixture_temperature_width_C=10.,mixture_fuel_width=.0001,mixture_mixing_time_s=10.)
    m['spread'].update(iteration_mode='fixed_point',**execution_limits(m['duration_s']))
    m=normalize(m);out=base/'floor60';out.mkdir(parents=True,exist_ok=False)
    (out/'scenario.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),'utf-8')
    # The comparison already solved this candidate schedule. Reuse it only if
    # the normal event loop independently generates exactly the same native deck.
    prime_completed(base/'stalled/smooth',out/'run_01',engine,gas_sidecar(m),m['duration_s'])
    result=simulate(m,engine,out)
    payload=package(result)
    (out/'playback.json').write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False,separators=(',',':')),'utf-8')
    scope=payload.get('fire_scope_summary',{})
    print(json.dumps({'status':result['terminated'],
                      'observed_solid_rooms':len(scope.get('observed_solid_rooms',[])),
                      'peak_concurrent_rooms':scope.get('peak_concurrent_rooms'),
                      'target_met':scope.get('target_met'),
                      'spread_search_complete':result['spread_search_complete']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
