"""Approved room-use inputs and internal-aperture fallback for v8 stage2.

The mapping is scoped to the reviewed building. It is not an inferred universal
classification rule. Native r8 and all thermal equations remain unchanged.
"""
from copy import deepcopy
import json
from pathlib import Path
from . import screening_v7 as v7
from .screening_v8 import summarize,compare_pairs

HERE=Path(__file__).parent
REVISION='v8_approved_screening'

def prepare_inputs(raw):
    cfg=json.loads((HERE/'approved_uses_v8.json').read_text('utf-8'))
    table=json.loads((HERE/'fire_load_table.json').read_text('utf-8'))
    # User-selected table classes override approved defaults; no thermal equation changes.
    override_path=HERE.parent/'config/fuel-overrides.json'
    overrides=json.loads(override_path.read_text('utf-8')) if override_path.exists() else {}
    if overrides and overrides.get('building_sha256')!=cfg['building_sha256']:
        raise ValueError('Fuel overrides belong to a different building')
    for rid,row in overrides.get('rooms',{}).items():
        if row.get('usage_class') not in table['classes']:raise ValueError('Invalid fuel override class')
        if rid in cfg['rooms']:
            cfg['rooms'][rid]={'class':row['usage_class'],'classification_basis':'사용자 적용 AI 제안 · '+row['reason']}

    if raw.get('cad',{}).get('building_sha256')!=cfg['building_sha256']:
        raise ValueError('Approved room classification belongs to a different building')
    m=deepcopy(raw);rooms={r['id']:r for r in m['rooms']};records={};exclusions=[]
    for rid,choice in cfg['rooms'].items():
        r=rooms[rid];cls=table['classes'][choice['class']];area=v7.area(r)
        load=choice.get('load_override_MJ_m2',cls['mean'])
        record={**choice,'room':rid,'name':v7.name(r),'label':cls['label'],
            'area_m2':area,'load_MJ_m2':load,'hrrpua_kW_m2':cls['rhrf'],
            'coverage':cfg['coverage'],'table_basis':cls['basis'],
            'value_basis':choice.get('load_override_basis','fire_load_table.json mean/rhrf'),
            'passage_without_fire':load<50,'graph_excluded':False}
        if rid in cfg['remove_from_candidate_and_graph']:
            connected=[v['id'] for v in m['openings'] if rid in (v['a'],v['b'])]
            if not area<1 or connected:raise ValueError('Approved tiny-room exclusion geometry changed: '+rid)
            record.update(graph_excluded=True,excluded_reason='user approved: area < 1 m² and no opening; remove candidate and graph')
            exclusions.append(record)
        elif load<50:
            record['excluded_reason']='fuel load < 50 MJ/m²; retain flow/temperature node, no candidate or standby fire'
        records[rid]=record
        r['fuel_default']={**r.get('fuel_default',{}),'usage':('passage' if choice['class']=='transport' else choice['class']),
            'load_MJ_m2':load,'hrrpua_kW_m2':cls['rhrf'],'occupancy_fraction':cfg['coverage'],
            'basis':record['value_basis'],'classification_basis':choice['classification_basis']}
        r['approved_fuel_class']=record
        for g in m['fuel_groups']:
            if g['room']!=rid:continue
            g.update(energy_MJ=load*area,hrrpua_kW_m2=cls['rhrf'],
                     fuel_area_m2=cfg['coverage']*area,coverage_fraction=cfg['coverage'])
            for key in ('room_rule_curve','room_rule_trigger','room_vent_cap'):g.pop(key,None)
            # Existing §2 standby peak is retained. The selected origin is replaced below.
    removed={r['room'] for r in exclusions}
    removed_groups={g['id'] for g in m['fuel_groups'] if g['room'] in removed}
    m['rooms']=[r for r in m['rooms'] if r['id'] not in removed]
    m['fuel_groups']=[g for g in m['fuel_groups'] if g['room'] not in removed]
    if 'explicit_candidates' in m:
        m['explicit_candidates']=[t for t in m['explicit_candidates'] if t.get('room') not in removed and t.get('group') not in removed_groups]
    m['approved_input']={'revision':REVISION,'room_uses':records,'graph_exclusions':exclusions,
        'source_building_sha256':cfg['building_sha256'],'coverage':cfg['coverage'],
        'fuel_overrides':overrides,
        'assumptions':['toilet 40MJ/m² and250kW/m² are user assumptions, not standard values',
         'approved use mapping is specific to this building; unresolved names use default',
         ('R2 user-selected AI table class supersedes 1800MJ/m²' if 'CAD_3F_R2' in overrides.get('rooms',{}) else 'R2 1800MJ/m² explicit override; other loads use table mean'),
         'thermal/flow nodes retained for toilets; no fuel fire below50MJ/m²']}
    return m

def origin_budgets(m):
    ids={r['id'] for r in m['rooms']};out={}
    for r in m['rooms']:
        rid=r['id'];a=v7.area(r);groups=[g for g in m['fuel_groups'] if g['room']==rid]
        if len(groups)>1:raise ValueError('Only one reviewed fuel group per room is supported')
        energy=sum(g['energy_MJ'] for g in groups);h=groups[0]['hrrpua_kW_m2'] if groups else 0.
        ext=[];inside=[]
        for v in m['openings']:
            if v.get('type','WALL')!='WALL' or rid not in (v['a'],v['b']):continue
            ah=v['width_m']*max(v['top_m']-v.get('bottom_m',0),0)**1.5
            (inside if (v['b'] if v['a']==rid else v['a']) in ids else ext).append((v['id'],ah))
        external=sum(v for _,v in ext);internal=max((v for _,v in inside),default=0.)
        cap=1500*external if external>0 else 750*internal;potential=.5*a*h
        out[rid]={'room':rid,'origin_fire_basis':'fuel_based','Q_origin_peak_kW':min(potential,cap),
            'area_m2':a,'coverage':.5,'hrrpua_kW_m2':h,'energy_MJ':energy,'fuel_load_MJ_m2':energy/a,
            'fuel_surface_peak_kW':potential,'ventilation_cap_kW':cap,'external_A_sqrtH':external,
            'internal_max_A_sqrtH':internal,'cap_basis':'external sum' if external>0 else '0.5 × internal maximum',
            'external_opening_ids':[i for i,_ in ext],
            'internal_max_opening_ids':[i for i,v in inside if v==internal],
            'vent_cap_k':1.,'growth_kW_s2':.047,'input_peak_used':False,
            'classification':m['approved_input']['room_uses'].get(rid),
            'opening_basis':'gross geometric aperture, same source curve across both states; actual oxygen limitation preserved'}
    return out

def score(raw,top_n=None,options=None,door_overrides=None):
    m=prepare_inputs(raw);budgets=origin_budgets(m);adjusted=deepcopy(m)
    for g in adjusted['fuel_groups']:g['peak_kW']=budgets[g['room']]['Q_origin_peak_kW']
    s=v7.score(adjusted,top_n,options,door_overrides)
    s['classified_model']['fuel_groups']=deepcopy(m['fuel_groups'])
    s.update(revision=REVISION,origin_fire_basis='fuel_based',origin_budgets=budgets,
             approved_input=m['approved_input'],original_room_count=len(raw['rooms']))
    s['settings']['ranking_order']=['burning_rooms_desc','smoke_risk_rooms_desc','smoke_caution_rooms_desc','first_FO_s_asc','origin_max_upper_C_desc']
    for r in s['ranked']+s['excluded']:r['origin_budget']=budgets[r['room']]
    s['limits']=[x for x in s['limits'] if 'own room curve retained' not in x]+m['approved_input']['assumptions']+[
        'origin supply uses approved table HRRPUA, coverage .5 and external-sum / half-internal-max cap',
        'original demo peak unused for origin; §2 standby item_peak retained with revised load/HRRPUA/coverage',
        'caution and risk are unions over sampled times, may overlap across time']
    return s

def scenario(scored,rid,state,duration=3600):
    d=v7.scenario(scored,rid,state,duration);b=scored['origin_budgets'][rid]
    if b['Q_origin_peak_kW']<=0:raise ValueError('Zero source cap')
    g=next(g for g in d['fuel_groups'] if g['room']==rid)
    g.update(peak_kW=b['Q_origin_peak_kW'],growth_kW_s2=.047,
             coverage_fraction=.5,fuel_area_m2=.5*b['area_m2'])
    d['origin_fire_basis']='fuel_based'
    d['room_rule_r8'].update(coverage_default=.5,vent_cap_k=1.)
    d['screening_source'].update(revision=REVISION,initial_curve='fuel_based',origin_budget=deepcopy(b))
    return d
