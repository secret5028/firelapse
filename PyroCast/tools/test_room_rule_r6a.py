"""One r6a A measurement at the source-derived fixed position. No sensor sweep."""
import argparse,json,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'simulation'));sys.path.insert(0,str(ROOT/'tools'))
from test_room_rule_r6 import save,crossing,ENGINE,FIXTURE
from pyrocast_cfbt.rule_sensor import gas_proxy_plate_r6a
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.deck import make_deck
from pyrocast_cfbt.native import execute,load_result,digest
OUT=ROOT/'simulation/results/room_rule_r6a_20261025'

def intervals(t,mask):
    """Observed sample spans and entry/exit brackets, no inferred continuous times."""
    spans=[];indices=np.flatnonzero(mask)
    for batch in np.split(indices,np.flatnonzero(np.diff(indices)>1)+1):
        if not len(batch):continue
        a,b=int(batch[0]),int(batch[-1])
        spans.append({'observed_samples_s':[float(t[a]),float(t[b])],
                      'entry_bracket_s':None if a==0 else [float(t[a-1]),float(t[a])],
                      'exit_bracket_s':None if b==len(t)-1 else [float(t[b]),float(t[b+1])]})
    return spans

def stage_a(analyze_only=False):
    model=normalize(json.loads(FIXTURE.read_text('utf-8')));source=next(g for g in model['fuel_groups'] if 'initial_time_s' in g)
    room=next(r for r in model['rooms'] if r['id']==source['room']);folder=OUT/'A'
    audit={'plume':'fire.f90:1084-1093 default layer; fire required, Tu>=Tl, point at/above fire; 1125-1131 cone core then Gaussian radial attenuation, no finite cutoff',
       'ceiling_jet':'fire.f90:999-1006 default local layer; 1011 active-fire gate; 1020-1027 delta=h*.112*(1-exp(-2.24*max(r/h,.26))), active at z>=ceiling-delta; 1031-1038 radial/hallway correlations without outer radial cutoff',
       'combination':'fire.f90:904-909 layer default; 951-957 takes max(layer, plume, ceiling jet); target.f90:329-335 uses it for target convection',
       'not_a_certified_plume_free_placement':'No finite plume cutoff exists. Fixed r6a geometry is tested once; exact local-vs-layer output differences are reported rather than adding a decay tolerance.',
       'source_hashes':{n:digest(ROOT/'simulation/vendor/cfast-7.7.7/Source'/n) for n in ('fire.f90','target.f90')}}
    save(OUT/'source-audit.json',audit)
    try:new=gas_proxy_plate_r6a(model,room,source,'T4BA_R1')
    except ValueError as exc:
        save(folder/'analysis.json',{'complete':False,'passed':False,'placement_status':'T4b placement unavailable','reason':str(exc),'native_runs':0});raise
    old={**new,'id':'T4_OLD_R1','xyz':[*source['position_m'][:2],room['origin_m'][2]+room['size_m'][2]-.2],
        'normal':[0,0,-1],'material':{**new['material'],'thickness_m':.001,'emissivity':.9},'basis':'r5 unchanged reference plate'}
    old['solver_xyz']=old['xyz'];old.pop('placement',None)
    deck=make_deck(model,[],[old,new]);assert 'DEVC_ID=' not in deck and '&CFBT' not in deck
    manifest={'mode':'r6a A measurement only','sensors':[old,new],'fixture_sha256':digest(FIXTURE),
              'engine_sha256':digest(ENGINE),'threshold_C':600,'max_temperature_difference_C':50,'source_audit':audit}
    if analyze_only:
        assert (folder/'case.in').read_text('ascii')==deck
        cache=json.loads((folder/'completed.json').read_text('utf-8'));native=load_result(folder,1200,cache['run'])
    else:
        if (folder/'execution.json').exists():raise ValueError('A already measured; use --analyze-only')
        save(folder/'rule_manifest.json',manifest);started=time.monotonic()
        native=execute(ENGINE,folder,deck,'',1200,model['spread']['run_timeout_s'])
        save(folder/'execution.json',{'complete':True,'wall_seconds':time.monotonic()-started})
    t=native['zone']['Time'];c=native['compartments'];d=native['devices'];ids=native['devices_ids']
    def series(prefix):return next(v for k,v in d.items() if k.startswith(prefix) and ids[k].strip()==new['id'])
    upper=c['ULT_1'];lower=c['LLT_1'];gas=series('TRGGAST_');plate=series('TRGSURT_');z=new['placement']['local_height_m']
    in_lower=c['HGT_1']>z;layer=np.where(in_lower,lower,upper);above=~in_lower
    report={'complete':True,'passed':bool(abs(max(plate)-max(upper))<=50),'native_wall_seconds':native['run']['wall_seconds'],
       'sensor':new,'upper_max_C':float(max(upper)),'plate_max_C':float(max(plate)),
       'difference_of_maxima_C':float(max(plate)-max(upper)),
       'plate_600C_bracket_s':crossing(t,plate),'upper_600C_bracket_s':crossing(t,upper),
       'local_gas_exactly_equal_to_upper_all_samples':bool(np.array_equal(gas,upper)),
       'local_gas_max_abs_difference_from_upper_C':float(max(abs(gas-upper))),
       'local_gas_exactly_equal_to_upper_while_in_upper':bool(np.array_equal(gas[above],upper[above])),
       'local_gas_max_abs_difference_while_in_upper_C':float(max(abs(gas[above]-upper[above]))) if np.any(above) else None,
       'local_gas_max_abs_difference_from_appropriate_layer_C':float(max(abs(gas-layer))),
       'lower_layer_sample_spans':intervals(t,in_lower),
       'tracking_near_600C':'not evaluated if neither upper layer nor plate reaches 600 C; no new near-threshold band invented',
       'native_runs':1,'sensor_sweep':False,'B_started':False,'C_started':False,'manifest':manifest}
    save(folder/'analysis.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ('manifest','sensor')},ensure_ascii=False,indent=2))
    return report


def stage_b(analyze_only=False):
    from pyrocast_cfbt.room_rule import prepare,observe
    from test_room_rule_r4 import longest
    a=json.loads((OUT/'A/analysis.json').read_text('utf-8'))
    if not a.get('passed'):raise ValueError('A must pass before B')
    cases={}
    for name in ('B1','B2','B3'):
        path=FIXTURE if name=='B1' else ROOT/f'fixtures/room_rule_benchmark_3room_{name.lower()}.json'
        raw=json.loads(path.read_text('utf-8'));raw['room_fire_rule']={'enabled':True,'trigger_mode':'parent_r5','preset':'standard'}
        model,_=prepare(raw);targets=[]
        # B fixtures have three <=150m2 fuel-bearing rooms, only open serial
        # doors: Dijkstra and BFS both give R1->R2->R3, each edge 60s.
        # This benchmark adapter does not claim general r6 graph support.
        assert len(model['rooms'])==3
        for room in model['rooms']:
            group=next(g for g in model['fuel_groups'] if g['room']==room['id'])
            target=gas_proxy_plate_r6a(model,room,group,'PC_'+room['id']);target['used_for_ignition']=True;targets.append(target)
        model['explicit_candidates']=targets
        deck=make_deck(model,[],targets);folder=OUT/'B'/name
        assert '&CFBT' not in deck
        manifest={'revision':'r6a T4b benchmark B','fixture_sha256':digest(path),'engine_sha256':digest(ENGINE),
            'sensor_rule':'r6a fixed source-derived position','sensors':targets,'parents':model['room_fire_rule']['parent_map'],
            'delay_s':60,'ramp_s':60,'threshold_C':600,'numerical_supply_cap':'r4 exterior-priority k=1',
            'graph_scope':'B fixtures only: three fuel-bearing small rooms, open serial doors; no pass-through/closed/vertical/cell edges present',
            'source_rule':'explicit assumed transition, not physical FO/ignition prediction'}
        if analyze_only:
            assert (folder/'case.in').read_text('ascii')==deck
            cached=json.loads((folder/'completed.json').read_text('utf-8'));native=load_result(folder,1200,cached['run'])
        else:
            if (folder/'execution.json').exists():raise ValueError('B case already measured; use --analyze-only')
            save(folder/'rule_manifest.json',manifest);save(folder/'requested-scenario.json',raw)
            print('START B',name,flush=True);start=time.monotonic()
            native=execute(ENGINE,folder,deck,'',1200,raw['spread']['run_timeout_s'])
            save(folder/'execution.json',{'complete':True,'wall_seconds':time.monotonic()-start})
        events,_,records=observe(model,native,targets);t=native['zone']['Time'];rows=[]
        for i,g in enumerate(model['fuel_groups'],1):
            event=next((e for e in events if e['group']==g['id']),None);q=native['compartments'][f'HRR_{i}']/1000
            hit=np.flatnonzero(q>0);record=next((r for r in records if r['group']==g['id']),None)
            rows.append({'room':g['room'],'trigger_s':event['t_ign_s'] if event else g.get('initial_time_s'),
                'supply_start_s':event['prescribed_supply_start_s'] if event else g.get('initial_time_s'),
                'first_actual_positive_HRR_s':float(t[hit[0]]) if len(hit) else None,
                'actual_source_peak_kW':float(max(q)),'longest_positive_HRR_s':longest(t,q),
                'native_vent_peak_kW':float(max(native['compartments'][f'DJET_{i}']))/1000,
                'upper_max_C':float(max(native['compartments'][f'ULT_{i}'])),
                'sensor':record})
        passed=(not events) if name=='B1' else all(r['longest_positive_HRR_s']>=60 for r in rows[1:])
        case={'complete':True,'passed':passed,'rows':rows,'events':events,'native_wall_seconds':native['run']['wall_seconds'],
              'engine_sha256':digest(ENGINE),'rule_manifest':manifest,'native_runs':1}
        save(folder/'analysis.json',case);cases[name]=case
        print(name,json.dumps({'passed':passed,'seconds':case['native_wall_seconds'],'rows':rows},ensure_ascii=False),flush=True)
    report={'cases':cases,'passed':all(c['passed'] for c in cases.values()),'C_started':False,'threshold_tuning':False}
    save(OUT/'B/comparison.json',report);return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['A','B'],default='A');p.add_argument('--analyze-only',action='store_true');args=p.parse_args()
    (stage_a if args.stage=='A' else stage_b)(args.analyze_only)
