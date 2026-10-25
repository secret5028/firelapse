"""Small, ID-based playback payload. No recomputation or invented fire/flow events."""
from collections import defaultdict
import json
from pathlib import Path
import re
import numpy as np
from .deck import active_fuels
from .native import digest,read_native_csv
from .exposure import _inside
from .openings import realized_fraction


def fire_visuals(result):
    """Read actual final-run flame heights and input areas without rerunning the solver."""
    folder=Path(result['runs'][-1]['folder'])
    if digest(folder/'case.in')!=result['final_input_sha256']:
        raise ValueError('Fire display metadata does not match final solver input')
    text=(folder/'case.in').read_text('ascii')
    native,_,units=read_native_csv(folder/'case_compartments.csv')
    t=np.asarray(result['time_s']);mask=native['Time']<=t[-1]+1e-6
    if not np.allclose(native['Time'][mask],t):raise ValueError('Fire display timestamps do not match result')
    model=result['scenario'];bygroup={e['group']:e for e in result['ignitions']};output={}
    for index,group in enumerate(active_fuels(model,result['ignitions']),1):
        fid='F_'+group['id']; escaped=re.escape(fid)
        chem=re.search(r"&CHEM\s+ID='"+escaped+r"'\s+(.*?)/",text,re.S)[1]
        chi=float(re.search(r'RADIATIVE_FRACTION=([0-9.eE+-]+)',chem)[1])
        rows=[list(map(float,m[1].split(','))) for m in re.finditer(r"&TABL\s+ID='"+escaped+r"'\s+DATA=([^/]+)/",text)]
        if not rows or max(row[2] for row in rows)-min(row[2] for row in rows)>1e-9:raise ValueError('Unsupported varying fire base height')
        event=bygroup.get(group['id'])
        if event is None and 'initial_time_s' not in group:continue
        start=event['t_ign_s'] if event else group['initial_time_s']
        expected=np.asarray(result['solid_fuel_inventory'][group['id']]['actual_HRR_W'])
        if units[f'HRR_{index}']!='W' or not np.allclose(native[f'HRR_{index}'][mask],expected,rtol=1e-9,atol=1e-6):
            raise ValueError('Native flame output belongs to a different active fire ordering')
        from .combustion_display import classify_source
        output[group['id']]={'flame_height_m':native[f'FLHGT_{index}'][mask].tolist(),
            'combustion_state':classify_source(expected,native[f'PYROL_{index}'][mask],native[f'IGN_{index}'][mask]>.5),
            'native_pyrolysis_kg_s':native[f'PYROL_{index}'][mask].tolist(),
            'area_m2':np.interp(t-start,[row[0] for row in rows],[row[3] for row in rows]).tolist(),
            'base_height_m':rows[0][2],'radiative_fraction':chi,
            'basis':'matching final native FLHGT and source TABL AREA/HEIGHT, CHEM RADIATIVE_FRACTION'}
    return output


def package(result):
    config=result['scenario']; cad=config.get('cad')
    if not cad:raise ValueError('CAD provenance required for a building playback')
    t=np.asarray(result['time_s']); n=len(t); room_ids=[r['id'] for r in config['rooms']]
    data={'schema':'pyrocast-cad-playback-1','time_s':result['time_s'],
          'building_sha256':cad['building_sha256'],'config_sha256':result['config_sha256'],
          'engine_sha256':result['engine_sha256'],'final_input_sha256':result['final_input_sha256'],
          'status':result['terminated'],'error':result['error'],
          'complete':result['simulation_complete_to_requested_horizon'],
          'spread_search_complete':result['spread_search_complete'],
          'scope':cad['scope'],'fire_key':cad['fire_key'],
          'topology_corrections':cad.get('topology_corrections',[]),
          'vertical_smoke':cad.get('vertical_smoke',False),
          'rooms':cad['display_rooms'],'excluded':cad['excluded'],'solvers':{},
          'openings':[],'fires':[],'ignitions':result['ignitions'],
          'fo_transitions':result.get('fo_transitions',[]),
          'solid_groups':[{'id':g['id'],'cad_key':g['cad_key'],'energy_MJ':g['energy_MJ'],
                           'position_m':g.get('position_m'),'room':g['room'],
                           'pool_owner_group':result['solid_fuel_inventory'][g['id']].get('pool_owner_group'),
                           'initial': 'initial_time_s' in g} for g in config['fuel_groups']],
          'solid_targets_count':len(config.get('explicit_candidates',[])),
          'fuel_units':[u for g in config['fuel_groups'] for u in g.get('fuel_units',[])],
          'fuel_layout':cad.get('fuel_layout'),
          'solid_candidates':[{k:v for k,v in c.items() if k in ('id','group','unit_id','cad_key','xyz','normal','opening_id','source_cad_key','distance_from_opening_m','fuel_face_height_m','placement_basis')} for c in config.get('explicit_candidates',[])],
          'candidate_basis':cad.get('candidate_basis','legacy room representative point'),
          'uncovered_fuel_groups':cad.get('uncovered_fuel_groups',[]),
          'pending_candidates':result['pending_candidates'],
          'settings':{'gas':config['gas'],'criteria':config['criteria'],'material':config['material'],
                      'flashover':config.get('flashover',{'enabled':False}),
                      'window_breakage':config.get('window_breakage',{'enabled':False}),
                      'options':cad['options'],'spread':config['spread']},
          'geometry_basis':cad['geometry_basis'],'vertical_basis':cad['vertical_basis'],
          'flow_columns':['mass_kg_s','o2_kg_s','fuel_kg_s','soot_kg_s','z_m','temperature_C','velocity_m_s'],
          'assumptions':result['assumptions']}
    from .mixture import package_jets
    data['ceiling_jets']=package_jets(config,result.get('ceiling_jets',[]),t)
    data['gas_model']='mixture_v1' if config['gas'].get('mixture_enabled') else 'legacy_fuel_bulk'
    data['condition_version']='common_table_v2'
    data['execution_profile']=result.get('execution_profile','legacy')
    data['limitations']=result.get('limitations',[])
    if result.get('spread_model'):
        data['spread_model']=result['spread_model']
        data['room_fire_rule']=result.get('room_fire_rule')
        data['baseline_native']=result.get('baseline_native')
    data['input_warnings']=result.get('input_warnings',[])
    # Carry uncertainty with the dataset, never infer it from the current scene.
    fallback=[target for target in config.get('explicit_candidates',[]) if target.get('sensor_quality')=='fallback']
    if fallback:
        roommap={r['id']:r for r in config['rooms']}
        data['sensor_uncertainty']=[{'sensor_id':target['id'],'room':target['room'],
            'parent_room':roommap[target['room']].get('parent_room',target['room']),
            'cad_key':roommap[target['room']].get('cad_key'),'sensor_quality':'fallback',
            'label':'판정 불확실','reason':'화염 원뿔 밖 배치를 보장하지 못한 대체 센서; 국부 가열로 조건 충족이 빨라질 수 있음'} for target in fallback]
    data['unevaluated_groups']=result.get('unevaluated_groups',[])
    data['invalid_exposure_count']=result.get('invalid_exposure_count',0)
    data['ignition_assumption']=config.get('ignition_assumption')
    data['demonstration']=config.get('demonstration')
    data['smoke_scope']=config.get('smoke_scope')
    data['window_events']=[{'opening_id':vid,**state} for vid,state in result.get('opening_states',{}).items() if state['changed']]
    data['iteration']=result.get('iteration',{'mode':'earliest_single','passes':len(result['runs']),
        'terminated':result['terminated'],'basis':'completed legacy run records; no batch diagnostics'})
    if 'conditions' not in result:
        from .conditions import evaluate
        result={**result,'conditions':evaluate(config,result)}
    data['conditions']=result['conditions']
    data['condition_ranges']={}
    for phenomenon,key in {'fo':'over_C','upper_gas':'Q_bulk_kW','backdraft':'fuel_energy_MJ','fgi':'fuel_energy_MJ','rapid':'rise_C_s'}.items():
        values=[v for rid in room_ids for v in data['conditions'].get(rid,{}).get(phenomenon,{}).get('intensity',{}).get(key,[]) if v is not None]
        data['condition_ranges'][phenomenon]={'key':key,'min':min(values) if values else None,'max':max(values) if values else None}
    for room in config['rooms']:
        rid=room['id']; state=result['rooms'][rid]; p=result['phenomena'][rid]
        mapping={'Tu':'T_upper_C','Tl':'T_lower_C','h':'interface_m','Ou':'o2_upper_vol',
                 'Ol':'o2_lower_vol','Fu':'fuel_upper_kg','ODu':'optical_density_upper_m_inv',
                 'ODl':'optical_density_lower_m_inv'}
        optional={'optical_density_lower_m_inv'} if room.get('shaft') else set()
        if any(k not in state and k not in optional for k in mapping.values()):raise ValueError('Native optical density data missing')
        data['solvers'][rid]={**{key:state.get(value,[None]*n) for key,value in mapping.items()},
              'single_zone':bool(room.get('shaft')),
              'core_kind':room.get('core_kind'),
              'combustible_kg':state.get('combustible_upper_kg',state['fuel_upper_kg']),
              'co_kg':state.get('co_upper_kg',[None]*n),
              'mixture_O2_kg_s':state.get('mixture_o2_kg_s',[0.]*n),
              'available_heat_MJ':(np.asarray(state.get('available_heat_J',state['fuel_upper_J']))/1e6).tolist(),
              'co_burn_kg_s':state.get('co_burn_kg_s',[0.]*n),
              'Qbulk_kW':(np.asarray(state['bulk_HRR_W'])/1000).tolist(),
              'Qvent_kW':(np.asarray(p['vent_HRR_W'])/1000).tolist(),
              'height_m':room['size_m'][2],'Qgas_kW':(np.asarray(p['gas_HRR_W'])/1000).tolist(),
              'rise_C_s':p['temperature_rate_C_s'],'Oin_kg_s':p['oxygen_in_kg_s'],
              'Fin_kg_s':p['fuel_in_kg_s'],'tags':p['tags']}
        data['solvers'][rid]['tags']={**p['tags'],'UPPER_GAS':(np.asarray(state['bulk_HRR_W'])>1e-6).tolist()}
        data['solvers'][rid]['conditions']=data['conditions'].get(rid,{})
    flows=np.zeros((len(config['openings']),2,n,7))
    gas=np.zeros((len(config['openings']),2,n))
    index={round(float(v),7):i for i,v in enumerate(t)}
    def destination(row):
        vi=int(row['vent_index'])-1
        source='OUTSIDE' if row['room_from']>len(room_ids) else room_ids[int(row['room_from'])-1]
        return vi,0 if source==config['openings'][vi]['a'] else 1,index[round(row['time_s'],7)]
    for row in result['directional_flow_slabs']:
        vi,di,j=destination(row); mass=row['mass_kg_s']; slot=flows[vi,di,j]
        slot += np.array([mass,row['o2_kg_s'],row['fuel_kg_s'],row['soot_kg_s'],
                          mass*(row['bottom_m']+row['top_m'])/2,mass*row['temperature_C'],mass*row['mean_velocity_m_s']])
    for row in result['directional_vent_reactions']:
        vi,di,j=destination(row); gas[vi,di,j]+=row['HRR_W']/1000
    mask=flows[:,:,:,0]>1e-12
    flows[:,:,:,4:]=np.divide(flows[:,:,:,4:],flows[:,:,:,0:1],out=np.zeros_like(flows[:,:,:,4:]),where=mask[:,:,:,None])
    for vi,opening in enumerate(config['openings']):
        data['openings'].append({k:v for k,v in opening.items() if k not in ('face','offset_m')})
        data['openings'][-1].update(ab=flows[vi,0].tolist(),ba=flows[vi,1].tolist(),
                                  gas_ab_kW=gas[vi,0].tolist(),gas_ba_kW=gas[vi,1].tolist())
        data['openings'][-1]['fraction']=realized_fraction(result,opening).tolist()
        data['openings'][-1]['window_state']=result.get('opening_states',{}).get(opening['id'])
    bygroup={e['group']:e for e in result['ignitions']}
    visuals=fire_visuals(result)
    legacy_units={}
    source=Path(cad['source_path'])
    legacy_file=source.parents[4]/'outputs/CAD-대표연료-v35/cfast-demo.json' if len(source.parents)>4 else None
    if legacy_file is not None and legacy_file.is_file() and result.get('execution_profile')!='practical':
        legacy=json.loads(legacy_file.read_text('utf-8'))
        legacy_units={f.get('room_key'):f.get('fuel_units',[]) for f in legacy.get('fires',[])}
    display_rooms={room['key']:room for room in cad['display_rooms']}
    for group in config['fuel_groups']:
        event=bygroup.get(group['id'])
        if event is None and 'initial_time_s' not in group:continue
        xyz=event['xyz'] if event else group['position_m']
        room=next(r for r in config['rooms'] if r['id']==group['room'])
        if not np.isclose(visuals[group['id']]['base_height_m'],xyz[2]-room['origin_m'][2],atol=1e-7):
            raise ValueError('Native flame base height does not match committed physical ignition position')
        data['fires'].append({'id':group['id'],'solver_id':group['room'],'cad_key':group['cad_key'],
            'cad_floor':group['cad_floor'],'cad_room':group['cad_room'],
            'position_m':event['xyz'] if event else group['position_m'],
            'time_s':event['t_ign_s'] if event else group['initial_time_s'],
            'kind':'additional' if event else 'initial',
            'transition_assumption':event.get('transition_assumption',False) if event else False,
            'prescribed_supply_start_s':event.get('prescribed_supply_start_s') if event else None,
            'placement':{k:event[k] for k in ('candidate','unit_id','opening_id','source_cad_key','distance_from_opening_m','fuel_face_height_m','fire_source_base_m','surface_xyz','placement_basis','normal') if k in event} if event else None,
            'visuals':visuals[group['id']],
            'fuel_units':[u for u in ([] if group.get('fuel_units') else legacy_units.get(group['cad_key'].removeprefix('CAD_'),[]))
                          if _inside(u['position'],display_rooms[group['cad_key']]['cad_polys'])],
            'Q_kW':(np.asarray(result['solid_fuel_inventory'][group['id']]['actual_HRR_W'])/1000).tolist(),
            'cause':event.get('largest_incident_term') if event else 'prescribed_initial_fire'})
    data['real_view']={'renderer':'restored_v35_polygon_masked_volume_raymarch',
                       'flame_dimensions':'native final-run FLHGT and input area',
                       'plume':'legacy CFAST7.7.7 correlation postprocessing; does not feed heat back',
                       'furniture':'retained illustrative v35 units inside the current CAD room only',
                       'animation':'visual smoke billows and flame flicker; not resolved CFD motion'}
    observed=sorted({f['solver_id'] for f in data['fires'] if max(f['Q_kW'],default=0)>0.})
    registered=sorted({f['solver_id'] for f in data['fires']})
    data['fire_scope_summary']={'registered_rooms':registered,'observed_solid_rooms':observed,
        'room_count':len(room_ids),'observation_threshold_kW':0.,
        'basis':'at least one final-run native source HRR sample > 0; not whole room involvement; tiny positive numerical values included'}
    solid_by_room={rid:np.zeros(len(data['time_s'])) for rid in room_ids}
    for fire in data['fires']:
        solid_by_room[fire['solver_id']]+=np.asarray(fire['Q_kW'])
    concurrent=np.sum([q>0. for q in solid_by_room.values()],axis=0)
    peak_index=int(np.argmax(concurrent))
    data['fire_scope_summary'].update(concurrent_solid_rooms=concurrent.tolist(),
        peak_concurrent_rooms=int(concurrent[peak_index]),peak_concurrent_time_s=float(data['time_s'][peak_index]))
    target=(config.get('demonstration') or {}).get('target_rooms')
    if target:
        data['fire_scope_summary'].update(target_rooms=int(target),target_met=len(observed)>=int(target),
            concurrent_target_met=bool(np.max(concurrent)>=int(target)))
    goal=re.search(r'at least\s*(\d+) of\s*(\d+)',str((config.get('demonstration') or {}).get('goal','')))
    if goal:
        data['fire_scope_summary'].update(target_rooms=int(goal[1]),target_met=len(observed)>=int(goal[1]))
    if config.get('demonstration',{}).get('fuel_energy_multiplier'):
        # Display actual input values rather than stale descriptive notes from earlier trials.
        caps={g['room']:g['peak_kW'] for g in config['fuel_groups'] if 'initial_time_s' in g}
        caps.update(config['flashover'].get('max_supply_by_room_kW',{}))
        data['scenario_note']=f"연료 에너지 {config['demonstration']['fuel_energy_multiplier']}배 가정 · 공급 상한 " + ', '.join(f'{k.removeprefix("CAD_")} {v/1000:g}MW' for k,v in caps.items())
        demo=config['demonstration']
        if demo.get('loaded_passages'):data['scenario_note']+=' · 통로 적치1200MJ/㎡·점유50% 별도 가정'
        if demo.get('secondary_peak_cap_kW'):data['scenario_note']+=f" · 일반 추가 화원 상한 {demo['secondary_peak_cap_kW']/1000:g}MW"
        if demo.get('fire_source_base_m') is not None:data['scenario_note']+=f" · 바닥 연료 화원 기부 {demo['fire_source_base_m']:g}m 가정(열응답 표면과 분리)"
        data['input_warnings']=[w for w in data['input_warnings'] if not w.startswith('가산시연 추가가정:') and not (not cad.get('vertical_smoke') and w.startswith('화재층 전체 + 다른 층의 확인된'))]
        data['input_warnings'].append(data['scenario_note']+' · 실제 적재물 조사값 아님. 창별 실제 초기 상태와 파괴정책은 저장 입력/개방 이력 참조.')
    def plain(value):
        if isinstance(value,np.ndarray):return plain(value.tolist())
        if isinstance(value,np.generic):return plain(value.item())
        if isinstance(value,dict):return {k:plain(v) for k,v in value.items()}
        if isinstance(value,(list,tuple)):return [plain(v) for v in value]
        if isinstance(value,float):return round(value,7)
        return value
    return plain(data)
