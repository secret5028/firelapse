"""Opt-in r7 input generator: source-derived sensor, cells and delay graph."""
from copy import deepcopy
import math
from .model import normalize
from .rule_cells import partition
from .rule_graph_r7 import delay_parents
from .rule_sensor import gas_proxy_plate_r6a
from .room_rule import ventilation_cap,supply_curve

DEFAULTS={'temperature_C':600.,'ramp_s':60.,'open_delay_s':60.,'closed_delay_s':600.,
          'cell_temperature_C':300.,'v_spread_m_s':.05,'vertical_delay_s':60.,'passage_load_MJ_m2':50.,'vent_cap_k':1.,'room_supply':'room_involvement','coverage_default':.5}


def prepare(raw, *, supply_coverage_fraction=None, cell_partitioner=None):
    m=deepcopy(raw);settings={**DEFAULTS,**m.get('room_rule_r7',{})}
    if set(settings)!=set(DEFAULTS):raise ValueError('Unknown r7 setting')
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for k,v in settings.items() if k!='room_supply'):raise ValueError('Invalid r7 setting')
    if settings['room_supply'] not in ('room_involvement','item_peak'):raise ValueError('Invalid room_supply')
    if settings['coverage_default']>1:raise ValueError('Coverage must be <=1')
    m.pop('room_fire_rule',None)
    for k in ('ignition_assumption','native_prefix_seed','prescribed_smoke','prescribed_fire_events','prescribed_fo_transitions'):m.pop(k,None)
    m.setdefault('gas',{}).update(enabled=False,bulk_enabled=False,vent_gate_enabled=False,mixture_enabled=False,mixture_smooth_enabled=False,jet_enabled=False)
    m.setdefault('flashover',{})['enabled']=False
    m['flashover'].pop('max_supply_by_room_kW',None) # disabled legacy FO keys refer to pre-split rooms
    m.setdefault('engine_optimization',{}).update(adaptive_radiation=False,radiation_cache=False,wall_cache=False)
    m=normalize(m)
    for g in m['fuel_groups']:
        r=next(r for r in m['rooms'] if r['id']==g['room']);floor=math.prod(r['size_m'][:2])
        coverage=g.get('coverage_fraction',g.get('fuel_area_m2',floor*settings['coverage_default'])/floor)
        if not math.isfinite(coverage) or not 0<coverage<=1:raise ValueError('Invalid fuel coverage')
        g['coverage_basis']='explicit coverage_fraction' if 'coverage_fraction' in g else 'existing fuel_area_m2/floor' if 'fuel_area_m2' in g else 'r7 default 0.5 (user preset)'
        g['fuel_area_m2']=floor*coverage
    m,cells=(cell_partitioner or partition)(m,split_initial=True);rooms={r['id']:r for r in m['rooms']}
    warnings=[];supplies={}

    initial=[g for g in m['fuel_groups'] if 'initial_time_s' in g]
    if len(initial)!=1:raise ValueError('r7 requires one initial fire')
    first=initial[0];root=first['room'];groups=[first];passing=set();omitted=[]
    for r in m['rooms']:
        if r['id']==root:continue
        fuel=[g for g in m['fuel_groups'] if g['room']==r['id']]
        energy=sum(g['energy_MJ'] for g in fuel);area=r['size_m'][0]*r['size_m'][1]
        if not fuel or energy/area<settings['passage_load_MJ_m2'] or r.get('core_kind')=='stair':
            passing.add(r['id']);omitted.append({'room':r['id'],'energy_MJ':energy,'reason':'stair' if r.get('core_kind')=='stair' else 'no fuel or below passage load'})
            continue
        if any(any(g[k]!=fuel[0][k] for k in ('formula','heat_of_combustion_kJ_kg','co_yield')) for g in fuel):raise ValueError('Cannot aggregate different fuel chemistry')
        g=deepcopy(fuel[0]);g.update(energy_MJ=energy,peak_kW=sum(x['peak_kW'] for x in fuel),
            hrrpua_kW_m2=sum(x['hrrpua_kW_m2']*x['energy_MJ'] for x in fuel)/energy,
            fuel_area_m2=min(area,sum(x.get('fuel_area_m2',area) for x in fuel)),source_groups=[x['id'] for x in fuel])
        original_peak=g['peak_kW']
        if settings['room_supply']=='room_involvement' and supply_coverage_fraction is not None:
            g['fuel_area_m2']=area*supply_coverage_fraction
        if settings['room_supply']=='room_involvement':g['peak_kW']=g['fuel_area_m2']*g['hrrpua_kW_m2']
        g['room_vent_cap']=ventilation_cap(m,r['id'],settings['vent_cap_k'],True)
        g['room_rule_curve']=supply_curve(g,area,{'ramp_s':settings['ramp_s'],'decay_energy_fraction':.3,'vent_cap_enabled':True})
        supplies[r['id']]={'mode':settings['room_supply'],'coverage_fraction':g['fuel_area_m2']/area,
            'covered_area_m2':g['fuel_area_m2'],'hrrpua_kW_m2':g['hrrpua_kW_m2'],'item_peak_kW':original_peak,
            'room_potential_kW':g['fuel_area_m2']*g['hrrpua_kW_m2'],'numerical_vent_cap':g['room_vent_cap'],
            'curve_caps':g['room_rule_curve']['caps'],'energy_MJ':energy}
        groups.append(g)
    initial_cap=ventilation_cap(m,root,settings['vent_cap_k'],True)
    scaled_peak=max(first['room_rule_curve']['q'])
    unpartitioned_peak=scaled_peak/first['room_rule_curve']['area_fraction']
    supplies[root]={'mode':'initial_area_share','unpartitioned_peak_kW':unpartitioned_peak,
        'scaled_peak_kW':scaled_peak,'area_fraction':first['room_rule_curve']['area_fraction'],
        'covered_area_m2':first['fuel_area_m2'],'hrrpua_kW_m2':first['hrrpua_kW_m2'],
        'energy_MJ':first['energy_MJ'],'numerical_vent_cap':initial_cap,'cap_applied':False}
    if unpartitioned_peak>initial_cap['cap_kW']:
        warnings.append({'room':root,'message':'Unpartitioned initial input exceeds this cell numerical cap; split by area before use',
            'unpartitioned_peak_kW':unpartitioned_peak,'scaled_peak_kW':scaled_peak,'cap':initial_cap})
    if max(first['room_rule_curve']['q'])>initial_cap['cap_kW']:
        warnings.append({'room':root,'message':'Initial cell peak exceeds numerical cap; area-scaled input shape retained','cap':initial_cap})
    targets=[];invalid={};by_room={g['room']:g for g in groups}
    for rid,r in rooms.items():
        g=by_room.get(rid)
        if g is None:
            pos=[r['origin_m'][i]+r['size_m'][i]*v for i,v in enumerate((.5,.5,0))]
            g={'id':'PASS_'+rid,'position_m':pos,'room_rule_curve':{'t':[0,1],'q':[0,0],'area':[0,0]}}
        target=gas_proxy_plate_r6a(m,r,g,'PC_'+rid,allow_cone_fallback=True)
        target.update(used_for_ignition=True,sensor_role='inter_room_600',passage_without_fire=rid in passing)
        targets.append(target)
    parents,graph=delay_parents(m,root,passing,invalid,settings)
    cell_parents={p['room'] for p in parents.values() if p and p['trigger_kind']=='cell_flame'}
    for rid in sorted(cell_parents):
        r=rooms[rid];g=by_room[rid];pos=list(g.get('solver_position_m',g['position_m']));pos[2]=r['origin_m'][2]+r['size_m'][2]-.2
        material={**m['material'],'conductivity_W_mK':45.,'density_kg_m3':7850.,'specific_heat_kJ_kgK':.46,'thickness_m':.001,'emissivity':.9}
        targets.append({'id':'FC_'+rid,'group':g['id'],'room':rid,'xyz':pos,'solver_xyz':pos,'normal':[0,0,-1],
            'material':material,'used_for_ignition':True,'sensor_role':'cell_flame_300','sensor_quality':'assumed',
            'basis':'r7 assumed cell flame spread: source-overhead plate, not FO or upper average'})
    active=[]
    for g in groups:
        if g['room'] not in parents:
            omitted.append({'room':g['room'],'energy_MJ':g['energy_MJ'],'reason':'unreachable under fixed graph/sensor availability'});continue
        if g is not first:
            parent=parents[g['room']];delay=parent['delay_s'];curve=g['room_rule_curve']
            curve.update(t=[0.]+[x+delay for x in curve['t']],q=[0.]+curve['q'],area=[curve['area'][0]]+curve['area'],delay_s=delay)
            cell=parent['trigger_kind']=='cell_flame'
            g['room_rule_trigger']={'criterion':'TEMPERATURE','setpoint':settings['cell_temperature_C'] if cell else settings['temperature_C'],'target_id':('FC_' if cell else 'PC_')+parent['room']}
            g['parent_transition']=parent
        active.append(g)
    m.update(fuel_groups=active,explicit_candidates=targets,room_rule_r7=settings,
        room_fire_rule={'enabled':True,'prepared':True,'trigger_mode':'parent_r7','delay_s':None,'parent_map':parents})
    # Normalize identifiers and window geometry after remapping, without touching
    # any native solver or source-rate option.
    m=normalize(m)
    manifest={'revision':'room_rule_r7','settings':settings,'cells':cells,'graph':graph,'parents':parents,
        'sensor_placement_unavailable':invalid,'sensors':targets,'omitted_fuel':omitted,
        'initial_source':{'id':first['id'],'room':root,'curve_shape_preserved':True,'area_fraction':first['room_rule_curve']['area_fraction']},
        'supplies':supplies,'warnings':warnings,'fallback_sensors':[t['room'] for t in targets if t.get('sensor_quality')=='fallback'],
        'limits':['sensor upper-layer membership is time dependent','Gaussian plume has no finite cutoff; flame core bound only, local gas tracking is diagnostic',
                  'prescribed transitions are not physical FO predictions','initial energy/HRR footprint divided by cell area; standby energy is not duplicated',
                  'within-room 300C plate and distance/0.05m/s are assumptions, not resolved flame spread',
                  'passages require their own 600C proxy; no unconditional bypass; passage cell edges use 600C because no fire exists',
                  'numerical supply cap reduces unburned fuel and cannot establish FGI likelihood',
                  'stock native output cannot supply project extension diagnostics; these are not fabricated']}
    return m,targets,manifest
