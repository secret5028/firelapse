"""Shared stock-CFAST execution for single calculations, screening and MC.

Geometry and reporting adapters do not integrate any Lite thermal state.
"""
from pathlib import Path
from copy import deepcopy
import math,time
import numpy as np
from result_catalog import atomic_json

ROOT=Path(__file__).resolve().parents[1]
ENGINE=ROOT/'simulation/build/baseline/cfast-baseline.exe'
KINDS=('FO','FGI','backdraft')


def runtime_settings():
    from pyrocast_cfbt.physics_config import defaults
    cfg=defaults('native_execution')
    for key in ('max_wall_s','progress_stall_s'):
        if type(cfg[key]) not in (int,float) or not math.isfinite(cfg[key]) or cfg[key]<=0:
            raise ValueError('Invalid CFAST runtime budget: '+key)
    return cfg


def execution_dependencies():
    from execution_evidence import rule_dependency_hashes,file_hash
    paths=[ROOT/'config/physics_defaults.json',ROOT/'config/building-rules.json',ROOT/'simulation/building_rules.py',ROOT/'simulation/pyrocast_lite/fire_load_table.json',ROOT/'simulation/pyrocast_lite/screening_v8_approved.py',ROOT/'tools/model_simulation.py',Path(__file__),ROOT/'tools/fixed_native_playback.py',ROOT/'tools/run_cfast_mc.py',ROOT/'tools/display_playback.py',ROOT/'tools/result_catalog.py']
    return {**rule_dependency_hashes(),**{p.relative_to(ROOT).as_posix():file_hash(p) for p in paths}}


def seal(folder):
    from pyrocast_cfbt.native import digest
    folder=Path(folder)
    if not (folder/'CFAST/case.in').is_file():return
    atomic_json(folder/'cfast-evidence.json',dict(schema='firelapse.cfast-execution/1',engine_kind='cfast_native',
        engine_sha256=digest(ENGINE),input_sha256=digest(folder/'CFAST/case.in'),rule_dependencies=execution_dependencies(),
        files={name:digest(folder/name) for name in ('input.json','scenario.json','playback.json','result.json','summary.json','index-summary.json')}))


def geometry(model,raw):
    from shapely.geometry import Polygon,Point
    from shapely.ops import unary_union
    originals={r['id']:r for r in raw['rooms']};rows=[];fires=[];symbols=[]
    for r in model['rooms']:
        rid=r['id'];src=originals[r.get('parent_room',rid)]
        polys=src.get('cad_polys')
        if not polys:
            x,y=src['origin_m'][:2];w,d=src['size_m'][:2]
            polys=[dict(o=[[x,y],[x+w,y],[x+w,y+d],[x,y+d]],h=[])]
        shape=unary_union([Polygon(p['o'],p.get('h',[])) for p in polys]);center=shape.representative_point();bounds=shape.bounds
        floor=src.get('cad_floor',raw.get('floor','unknown'))
        rows.append(dict(key=rid,solver_id=rid,original_room=rid,cad_floor=floor,
            cad_room=src.get('cad_room',rid),cad_names=src.get('cad_names',[]),
            cad_center_m=[center.x,center.y],cad_polys=deepcopy(polys),area_m2=float(shape.area),
            z_m=r['origin_m'][2],height_m=r['size_m'][2]))
        groups=[g for g in model['fuel_groups'] if g['room']==rid]
        for g in groups:
            xy=[bounds[k]+(g['position_m'][k]-src['origin_m'][k])/src['size_m'][k]*(bounds[k+2]-bounds[k]) for k in (0,1)]
            if not shape.covers(Point(xy)):xy=[center.x,center.y]
            fires.append(dict(id=g['id'],solver_id=rid,cad_key=rid,cad_floor=floor,
                              position_m=[*xy,r['origin_m'][2]]))
        if groups:
            step=max(2.,math.sqrt(shape.area/12))
            for x in np.arange(bounds[0]+step/2,bounds[2],step):
                for y in np.arange(bounds[1]+step/2,bounds[3],step):
                    if shape.contains(Point(x,y)):symbols.append(dict(room=rid,position_m=[float(x),float(y),r['origin_m'][2]+.2]))
    origin=next(g['room'] for g in model['fuel_groups'] if 'initial_time_s' in g)
    return dict(rooms=rows,fires=fires,fuel_symbols=symbols,fire_key=origin)


def report(playback,model,sample=None):
    t=np.asarray(playback['time_s']);rooms=playback['solvers'];summary_rows=[];phenomena={};burning=[]
    invalid=playback.get('physical_validation',{}).get('status')=='physically_invalid'
    for rid,s in rooms.items():
        q=np.array(s['Qsolid_kW']);hits=np.flatnonzero(q>0)
        if len(hits):burning.append(rid)
        summary_rows.append(dict(cell=rid,original_room=rid,actual_peak_kW=float(q.max()),
            first_actual_positive_HRR_s=float(t[hits[0]]) if len(hits) else None,
            upper_max_C=max(x for x in s['Tu'] if x is not None),
            upper_oxygen_min_vol_percent=100*min(x for x in s['Ou'] if x is not None)))
    caution=set();risk=set()
    for kind in KINDS:
        affected={};scores=[];masks=[];fractions={}
        for rid,s in rooms.items():
            record=s['conditions'][kind];values=record.get('scores',{}).get('degree',[])
            valid=[x for x in values if isinstance(x,(float,int)) and math.isfinite(x)]
            scores.extend(valid)
            if any(x>=.7 for x in valid):caution.add(rid)
            if any(x>=1 for x in valid):risk.add(rid)
            mask=np.array([x is not None and x>=1 for x in values],bool)
            if len(mask)!=len(t):mask=np.zeros(len(t),bool)
            masks.append(mask);hits=np.flatnonzero(mask)
            if len(hits):affected[rid]=float(t[hits[0]])
            fractions[rid]=float(np.sum(np.diff(t)*mask[:-1])/(t[-1]-t[0])) if t[-1]>t[0] else None
        phenomena[kind]=dict(status='not_evaluated' if invalid else 'evaluated',
            ever_room_count=len(affected) if not invalid else None,rooms=affected,
            first_s=min(affected.values(),default=None),score_max=max(scores) if scores else None,
            max_simultaneous_room_count=int(np.stack(masks).sum(axis=0).max()),
            met_time_fraction_by_room=fractions,met_room_time_fraction=float(np.mean(list(fractions.values()))),
            score_basis='CFAST saved native conditions; applicable cell-time maxima')
    threshold=model['rule_settings']['values']['temperature_C']
    boundary=sum(any(v is not None and abs(v-threshold)<=30 for v in s['Tu']) for s in rooms.values())
    result=dict(ok=True,engine_kind='cfast_native',t=t.tolist(),room_summary=summary_rows,
        shared_conditions={'rooms':{rid:s['conditions'] for rid,s in rooms.items()}},
        physical_validation=playback['physical_validation'],condition_version=playback['condition_version'])
    summary=dict(complete=True,ranking_eligible=playback.get('physical_validation',{}).get('status')=='valid',engine_kind='cfast_native',
        sample_id=(sample or {}).get('id'),kind=(sample or {}).get('kind','single'),
        selected_attempt='CFAST',original_room_count=len(rooms),burning_original_rooms=burning,
        burning_room_count=len(burning),smoke_caution_rooms=sorted(caution),smoke_risk_rooms=sorted(risk),
        smoke_risk_room_count=len(risk),smoke_caution_room_count=len(caution),attention_room_count=len(caution),unknown_rooms=list(rooms) if invalid else [],
        origin_max_upper_C=max(rooms[playback['fire_key']]['Tu']),
        phenomena=phenomena,first_FO_s=phenomena['FO']['first_s'],boundary_room_count=boundary,
        room_boundaries=[dict(room=r) for r in rooms],balance_diagnostic=playback['physical_validation'],
        physical_validation=playback['physical_validation'],safe_end_s=float(t[-1]),failure=None)
    return result,summary


def run_case(raw,folder,label='CFAST',budget_s=None,sample=None):
    from pyrocast_cfbt.room_rule_r8 import prepare_native
    from pyrocast_cfbt.deck import make_deck
    from pyrocast_cfbt.native import execute,digest
    from fixed_native_playback import package
    from fixed_calculation import fire_details
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    if (folder/'playback.json').exists():raise ValueError('완료된 결과는 덮어쓰지 않습니다')
    if not ENGINE.is_file():raise ValueError('순정 CFAST 실행 파일 없음')
    started=time.monotonic();model,targets,manifest=prepare_native(raw)
    atomic_json(folder/'input.json',raw);atomic_json(folder/'scenario.json',model)
    native_dir=folder/'CFAST'
    settings=runtime_settings()
    result=execute(ENGINE,native_dir,make_deck(model,[],targets),'',model['duration_s'],budget_s if budget_s is not None else settings['max_wall_s'],settings['progress_stall_s'],validation_model=model)
    manifest['basement_pressure']=model.get('basement_pressure');manifest['limits']=model.get('limits',[])
    atomic_json(folder/'scenario.json',model);atomic_json(folder/'rule_manifest.json',manifest)
    atomic_json(native_dir/'rule_manifest.json',manifest)
    pb=package(model,result,geometry(model,raw),native_dir)
    pb.update(label=label,case_id=folder.name,boundary_revision=model.get('boundary_revision'),
        minimum_leakage=model.get('minimum_leakage',[]),ventilation_assumptions=model.get('ventilation_assumptions',{}))
    pb['fire_input']=fire_details(raw,manifest,pb)
    from pyrocast_cfbt.input_basis import describe
    pb['input_basis']=describe(raw)
    pb['fire_input']['input_basis']=pb['input_basis']
    for r in pb['rooms']:
        use=raw.get('approved_input',{}).get('room_uses',{}).get(r['original_room'],{})
        if use:r.update(display_name=use.get('label'),approved_fuel_class=use.get('usage_class'))
    data,summary=report(pb,model,sample);summary['times']=dict(total_s=time.monotonic()-started,integration_s=result['run']['wall_seconds'])
    # Aggregate/rank from full precision before making the display-only copy.
    from display_playback import save_playback
    pb=save_playback(folder/'playback.json',pb)
    for name,value in [('result.json',data),('summary.json',summary)]:atomic_json(folder/name,value)
    from export_ui_attention import result_index
    result_index(folder/'result.json')
    seal(folder)
    return pb,data,summary
