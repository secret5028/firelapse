"""Assess an already integrated native prefix and re-evaluate its proposed events.

This is a full CFAST rerun with a calculated initial schedule, not engine restart
and not prescribed ignition. The identical material/FO functions produce seeds.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'simulation'))
from pyrocast_cfbt.native import load_result,digest
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.deck import candidates,make_deck
from pyrocast_cfbt.spread import assess,simulate,_plain,check_causality
from pyrocast_cfbt.flashover import proposals
from pyrocast_cfbt.iteration import merge,prefix_check
from pyrocast_cfbt.playback import package


def run_prepared(m,output,engine):
    seed=m['native_prefix_seed'];source_run=Path(seed['source_folder'])
    if digest(source_run/'case.in')!=seed['source_input_sha256']:
        raise ValueError('Prefix source input changed')
    native=load_result(source_run,seed['horizon_s'],{'folder':str(source_run)},allow_prefix=True)
    result=simulate(m,engine,output)
    first=load_result(Path(result['runs'][0]['folder']),m['duration_s'],result['runs'][0])
    diagnostic=prefix_check(m,native,first,seed['previous_events'],seed['previous_transitions'],
                            seed['events'],seed['transitions'],check_causality)
    result['iteration']['seed_prefix_check']=diagnostic
    if not diagnostic['ok']:
        result['iteration']['condition_consistent']=False
        result['spread_search_complete']=False
    result=_plain(result)
    (output/'result.json').write_text(json.dumps(result,ensure_ascii=False,allow_nan=False),'utf-8')
    payload=package(result)
    tmp=output/'playback.tmp';tmp.write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False,separators=(',',':')),'utf-8');tmp.replace(output/'playback.json')
    print(json.dumps({'status':result['terminated'],'actual':payload['fire_scope_summary']},ensure_ascii=False),flush=True)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--horizon',type=float,default=1800)
    p.add_argument('--engine',type=Path,default=ROOT/'simulation/build/mixture_r2/cfbt/cfast-cfbt.exe')
    p.add_argument('--build-only',action='store_true')
    p.add_argument('--prepared',action='store_true')
    a=p.parse_args()
    if a.prepared:
        return run_prepared(normalize(json.loads((a.output/'scenario.json').read_text('utf-8'))),a.output,a.engine)
    m=normalize(json.loads((a.source/'scenario.json').read_text('utf-8')))
    targets=candidates(m)
    initial=load_result(a.source/'run_00',m['duration_s'],{'folder':str((a.source/'run_00').resolve())})
    decisions,views,states=assess(m,initial,targets,[],[],reevaluate=True)
    fo=proposals(m,initial,states,[],[],views)
    previous,previous_fo,_=merge(m,[],[],decisions,fo)
    text=make_deck(m,previous,targets,previous_fo)
    source_run=a.source/'run_01'
    if text.splitlines()!=(source_run/'case.in').read_text('ascii').splitlines():
        raise ValueError('Reconstructed initial decisions do not match source native input')
    native=load_result(source_run,a.horizon,{'folder':str(source_run.resolve())},allow_prefix=True)
    # No sample later than the prefix participates in thermal integration.
    decisions,views,states=assess(m,native,targets,previous,previous_fo,reevaluate=True)
    fo=proposals(m,native,states,previous,[],views)
    for old in previous_fo:
        prior=native['zone']['Time'][native['zone']['Time']<old['t_ign_s']-m['spread']['event_tolerance_s']]
        fo=[e for e in fo if e['room']!=old['room'] or (len(prior) and e['t_ign_s']<=prior[-1])]
    events,transitions,flags=merge(m,previous,previous_fo,decisions,fo)
    # Seeds are restricted to observations already reached by CFAST.
    assert all(e['t_ign_s']<=a.horizon for e in events+transitions)
    m['native_prefix_seed']={'basis':'computed_native_prefix','horizon_s':a.horizon,
        'source_folder':str(source_run.resolve()),'source_input_sha256':digest(source_run/'case.in'),
        'previous_events':previous,'previous_transitions':previous_fo,
        'events':events,'transitions':transitions,'assessment_flags':flags,
        'note':'Same plate/FO criteria; all proposed times re-evaluated in the next full run'}
    m['spread'].update(run_timeout_s=2400,wall_time_budget_s=10800)
    m=normalize(m);a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'scenario.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({'prefix_s':a.horizon,'old_events':len(previous),'seed_events':len(events),
                      'fo':len(transitions),'groups':[e['group'] for e in events]},ensure_ascii=False),flush=True)
    if a.build_only:return
    run_prepared(m,a.output,a.engine)


if __name__=='__main__':main()
