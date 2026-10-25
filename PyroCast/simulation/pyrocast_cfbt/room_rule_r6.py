"""Opt-in r6a input generator: source-derived sensor, cells and delay graph."""
from copy import deepcopy
import math
from .model import normalize
from .rule_cells import partition
from .rule_graph import delay_parents
from .rule_sensor import gas_proxy_plate_r6a
from .room_rule import ventilation_cap,supply_curve

DEFAULTS={'temperature_C':600.,'ramp_s':60.,'open_delay_s':60.,'closed_delay_s':600.,
          'cell_delay_s':30.,'vertical_delay_s':60.,'passage_speed_m_s':.5,'passage_load_MJ_m2':50.,'vent_cap_k':1.}


def prepare(raw):
    m=deepcopy(raw);settings={**DEFAULTS,**m.get('room_rule_r6',{})}
    if set(settings)!=set(DEFAULTS):raise ValueError('Unknown r6 setting')
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in settings.values()):raise ValueError('Invalid r6 setting')
    m.pop('room_fire_rule',None)
    for k in ('ignition_assumption','native_prefix_seed','prescribed_smoke','prescribed_fire_events','prescribed_fo_transitions'):m.pop(k,None)
    m.setdefault('gas',{}).update(enabled=False,bulk_enabled=False,vent_gate_enabled=False,mixture_enabled=False,mixture_smooth_enabled=False,jet_enabled=False)
    m.setdefault('flashover',{})['enabled']=False
    m['flashover'].pop('max_supply_by_room_kW',None) # disabled legacy FO keys refer to pre-split rooms
    m.setdefault('engine_optimization',{}).update(adaptive_radiation=False,radiation_cache=False,wall_cache=False)
    m=normalize(m);m,cells=partition(m);rooms={r['id']:r for r in m['rooms']}
    initial=[g for g in m['fuel_groups'] if 'initial_time_s' in g]
    if len(initial)!=1:raise ValueError('r6 requires one initial fire')
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
        g['room_vent_cap']=ventilation_cap(m,r['id'],settings['vent_cap_k'],True)
        g['room_rule_curve']=supply_curve(g,area,{'ramp_s':settings['ramp_s'],'decay_energy_fraction':.3,'vent_cap_enabled':True})
        groups.append(g)
    targets=[];invalid={}
    for g in groups:
        r=rooms[g['room']]
        try:
            target=gas_proxy_plate_r6a(m,r,g,'PC_'+r['id']);target['used_for_ignition']=True;targets.append(target)
        except ValueError as exc:invalid[r['id']]=str(exc)
    if root in invalid:raise ValueError('Initial room T4b placement unavailable: '+invalid[root])
    parents,graph=delay_parents(m,root,passing,invalid,settings)
    active=[]
    for g in groups:
        if g['room'] not in parents:
            omitted.append({'room':g['room'],'energy_MJ':g['energy_MJ'],'reason':'unreachable under fixed graph/sensor availability'});continue
        if g is not first:
            parent=parents[g['room']];delay=parent['delay_s'];curve=g['room_rule_curve']
            curve.update(t=[0.]+[x+delay for x in curve['t']],q=[0.]+curve['q'],area=[curve['area'][0]]+curve['area'],delay_s=delay)
            g['room_rule_trigger']={'criterion':'TEMPERATURE','setpoint':settings['temperature_C'],'target_id':'PC_'+parent['room']}
            g['parent_transition']=parent
        active.append(g)
    m.update(fuel_groups=active,explicit_candidates=targets,room_rule_r6=settings,
        room_fire_rule={'enabled':True,'prepared':True,'trigger_mode':'parent_r6a','delay_s':None,'parent_map':parents})
    # Normalize identifiers and window geometry after remapping, without touching
    # any native solver or source-rate option.
    m=normalize(m)
    manifest={'revision':'room_rule_r6a','settings':settings,'cells':cells,'graph':graph,'parents':parents,
        'sensor_placement_unavailable':invalid,'sensors':targets,'omitted_fuel':omitted,
        'initial_source':{'id':first['id'],'room':root,'curve_preserved':True},
        'limits':['sensor upper-layer membership is time dependent','Gaussian plume has no finite cutoff; flame core bound only, local gas tracking is diagnostic',
                  'prescribed transitions are not physical FO predictions','initial whole-room curve stays in its source cell once; other cells do not duplicate that energy budget',
                  'stock native output cannot supply project extension diagnostics; these are not fabricated']}
    return m,targets,manifest
