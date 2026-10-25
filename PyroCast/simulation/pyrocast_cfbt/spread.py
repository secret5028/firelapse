from pathlib import Path
from collections import defaultdict
import hashlib
import json
import time
import numpy as np
from . import __version__
from .model import normalize
from .deck import candidates, make_deck, gas_sidecar, fire_curve, active_fuels
from .native import execute, digest, interruption_status
from .thermal import plate
from .exposure import supplementary, room_series
from .flashover import proposals as fo_proposals, source_curves, pool_inventory, integral
from .openings import device_series, realized_fraction, histories as opening_histories, LIMITATION as WINDOW_LIMITATION


def _plain(obj):
    if isinstance(obj,np.ndarray):return [_plain(v) for v in obj]
    if isinstance(obj,np.generic):return obj.item()
    if isinstance(obj,dict):return {k:_plain(v) for k,v in obj.items()}
    if isinstance(obj,list):return [_plain(v) for v in obj]
    return obj


def assess(model,result,targets,committed,transitions=None,deadline=None,reevaluate=False):
    t=result['zone']['Time']; settings=model['spread']; states=room_series(model,result)
    decisions=[]; views=[]
    active={g['id']:{'t_ign_s':g['initial_time_s']} for g in model['fuel_groups'] if 'initial_time_s' in g}
    active.update({event['group']:event for event in committed})
    pooled={e['room']:e['t_ign_s'] for e in (transitions or [])}
    for index,target in enumerate(targets,1):
        if deadline is not None and time.monotonic()>=deadline:
            views.append({**target,'status':'unevaluated','reason':'postprocessing_time_budget'})
            continue
        material=target['material']
        front=device_series(result,target['id'],'TRGFLXI',index)/material['emissivity']
        back=device_series(result,target['id'],'B_TRGFLXI',index)/material['emissivity']
        gas=device_series(result,target['id'],'TRGGAST',index)
        sup,near=supplementary(model,result,target,states,committed,transitions)
        total=front+sum(sup.values())
        terms={'native':front,**sup}
        if not np.isfinite(total).all() or np.min(total)<-1e-5:
            views.append({**target,'status':'invalid_exposure',
                          'reason':'nonfinite_or_negative_combined_incident_flux'})
            continue
        total=np.maximum(0,total)
        response=plate(material,t,total,back,gas,gas,model['ambient_C'],settings['plate_nodes'],settings['plate_dt_s'],target['normal'][2])
        crossing=response['crossing_s']
        eligible=target['group'] not in active
        if reevaluate and target['group'] in {e['group'] for e in committed}:
            # Never advance from an interval whose right endpoint includes this
            # group's own fire. Preserve the original plate algorithm/threshold.
            # The straddling interval remains explicitly unverified, not reset.
            old=active[target['group']]['t_ign_s']
            before=t[t<old-settings['event_tolerance_s']]
            eligible=crossing is not None and len(before)>0 and crossing<=before[-1]
        if crossing is not None and eligible and material['pilot']!='none' and crossing<pooled.get(target['room'],float('inf')):
            amounts={k:float(np.interp(crossing,t,v)) for k,v in terms.items()}
            decisions.append({'event_id':target['group'],'group':target['group'],'room':target['room'],
                'candidate':target['id'],'t_ign_s':crossing,'xyz':target.get('fire_source_xyz',target['xyz']),
                **({'surface_xyz':target['xyz'],'fire_source_base_m':target['fire_source_base_m']} if 'fire_source_xyz' in target else {}),
                **({'solver_xyz':target.get('solver_fire_xyz',target['solver_xyz'])} if 'solver_xyz' in target else {}),
                **({'cad_key':target['cad_key']} if 'cad_key' in target else {}),
                **{k:target[k] for k in ('unit_id','opening_id','source_cad_key','distance_from_opening_m','fuel_face_height_m','placement_basis','normal') if k in target},
                'pilot_assumption':material['pilot'],'proxy_material':material['proxy'],
                'exposure_case':'local','terms_at_event_kW_m2':amounts,
                'largest_incident_term':max(amounts,key=amounts.get),
                'absorbed_kJ_m2':float(np.interp(crossing,t,response['absorbed_kJ_m2'])),
                'basis':'representative_solid_group_threshold_not_all_contents_ignited'})
        limit=active.get(target['group'],{}).get('t_ign_s')
        if target['room'] in pooled:limit=min(limit if limit is not None else float('inf'),pooled[target['room']])
        surface=response['surface_C'].astype(object)
        if limit is not None:surface[t>limit]=None
        views.append({**target,'status':'ok','q_inc_kW_m2':total,'terms_kW_m2':terms,'surface_C':surface,
                      'crossing_s':crossing,'valid_until_s':limit,'near_flame':near,
                      'plate_energy_residual_kJ_m2':response['energy_residual_kJ_m2']})
    # Several observed faces refer to one shared solid group.
    earliest={}
    for decision in sorted(decisions,key=lambda e:(e['t_ign_s'],e['group'],e['candidate'])):
        earliest.setdefault(decision['group'],decision)
    return list(earliest.values()),views,states


def check_causality(previous,current,event,settings):
    t=previous['zone']['Time']; cut=event['t_ign_s']-settings['event_tolerance_s']
    mask=t<cut
    for key,identity in previous.get('native_vents_ids',{}).items():
        if not key.startswith('WF_'):continue
        matches=[k for k,v in current.get('native_vents_ids',{}).items() if k.startswith('WF_') and v==identity]
        if len(matches)!=1:raise ValueError('Missing causal opening fraction: '+identity)
        new=realized_fraction(current,{'id':identity},t[mask])
        if not np.array_equal(previous['native_vents'][key][mask],new):
            raise ValueError('Pre-ignition causal mismatch in opening '+identity)
    for key,old in previous['zone'].items():
        family=key.split('_')[0]
        if family not in settings['causality_abs']:continue
        if key not in current['zone']:raise ValueError('Missing causal comparison series: '+key)
        new=np.interp(t[mask],current['zone']['Time'],current['zone'][key])
        if not np.allclose(old[mask],new,rtol=settings['causality_rel'],atol=settings['causality_abs'][family]):
            raise ValueError('Pre-ignition causal mismatch in '+key)
    # Compare species, including the shared gas pool, before committing another solid fire.
    for index in {r['room_index'] for r in previous['rooms']}:
        a=[r for r in previous['rooms'] if r['room_index']==index]
        b=[r for r in current['rooms'] if r['room_index']==index]
        for key in ('fuel_upper_kg','fuel_lower_kg','o2_upper_vol','o2_lower_vol'):
            y=np.interp(t[mask],[r['time_s'] for r in b],[r[key] for r in b])
            if not np.allclose(np.array([r[key] for r in a])[mask],y,rtol=.001,atol=.0001):
                raise ValueError('Pre-ignition species mismatch: '+key)


def neutral_planes(model,states,t,native=None):
    rooms={r['id']:r for r in model['rooms']}; output={}
    for opening in model.get('openings',[]):
        a,b=opening['a'],opening['b']
        if opening.get('type')=='FLOOR':
            output[opening['id']]={'method':'vertical_native_vent_no_wall_neutral_plane','values':None}; continue
        if b=='OUTSIDE':
            output[opening['id']]={'method':'not_computed_for_exterior_in_v1','values':None}; continue
        result=[]
        fractions=realized_fraction(native or {},opening,t)
        for i in range(len(t)):
            if fractions[i]<=0:result.append({'status':'closed','roots_m':[]}); continue
            bottom=rooms[a]['origin_m'][2]+opening.get('bottom_m',0)
            top=rooms[a]['origin_m'][2]+opening['top_m']
            def pressure(rid,z):
                state=states[rid]; dz=z-rooms[rid]['origin_m'][2]
                height=state['interface_m'][i]
                return state['floor_pressure_Pa'][i]-9.81*(state['rho_lower_kg_m3'][i]*min(dz,height)+state['rho_upper_kg_m3'][i]*max(0,dz-height))
            knots=sorted({bottom,top,*[rooms[r]['origin_m'][2]+states[r]['interface_m'][i] for r in (a,b) if bottom<rooms[r]['origin_m'][2]+states[r]['interface_m'][i]<top]})
            roots=[]; values=[pressure(a,z)-pressure(b,z) for z in knots]
            if max(abs(v) for v in values)<1e-8:
                result.append({'status':'equal_pressure','roots_m':[]}); continue
            for j in range(len(knots)-1):
                p,q=values[j:j+2]
                if abs(p)<1e-8:roots.append(knots[j])
                elif p*q<0:roots.append(knots[j]-p/(q-p)*(knots[j+1]-knots[j]))
            if abs(values[-1])<1e-8:roots.append(knots[-1])
            result.append({'status':'roots' if roots else 'one_way','roots_m':roots})
        output[opening['id']]={'method':'piecewise_hydrostatic_pressure','values':result}
    return output


def classify(model,result,states,events,views,transitions=None):
    t=result['zone']['Time']; c=model['criteria']; output={}
    own_fire={r['id']:np.zeros(len(t),bool) for r in model['rooms']}
    for index,group in enumerate(active_fuels(model,events),1):
        own_fire[group['room']]|=np.asarray(result['zone'].get(f'HRR_{index}',np.zeros(len(t))))>1000.
    incoming={r['id']:{'o2':np.zeros(len(t)),'fuel':np.zeros(len(t))} for r in model['rooms']}
    time_index={float(v):i for i,v in enumerate(t)}
    for row in result['slabs']:
        ri=int(row['room_to'])-1
        if not 0<=ri<len(model['rooms']):continue
        rid=model['rooms'][ri]['id']; j=time_index.get(row['time_s'])
        if j is not None:
            incoming[rid]['o2'][j]+=row['o2_kg_s']; incoming[rid]['fuel'][j]+=row['fuel_kg_s']
    for ri,room in enumerate(model['rooms'],1):
        rid=room['id']; s=states[rid]
        past=np.maximum(t[0],t-c['window_s']); elapsed=np.maximum(t-past,1e-12)
        rate=(s['T_upper_C']-np.interp(past,t,s['T_upper_C']))/elapsed
        fuel_fraction=s.get('combustible_upper_kg',s['fuel_upper_kg'])/np.maximum(s['upper_mass_kg'],1e-12)
        wait=(s['o2_upper_vol']<c['oxygen_deficient_vol_percent']/100)&(fuel_fraction>=c['fuel_rich_mass_fraction'])&(s['T_upper_C']>=c['hot_C'])
        history=np.maximum.accumulate(wait)
        ventq=np.zeros(len(t))
        for row in result['vents']:
            j=time_index.get(row['time_s'])
            if row['room_to']==ri and j is not None:ventq[j]+=row['HRR_W']
        gasq=s['bulk_HRR_W']+ventq; gas=gasq>1e-6; rapid=rate>=c['rapid_C_s']
        bd=history&gas&rapid&(incoming[rid]['o2']>1e-8)
        transported=np.cumsum(incoming[rid]['fuel'])>1e-8
        floor_views=[view for view in views if view.get('status','ok')=='ok' and view['room']==rid and view['normal'][2]>.99]
        floor_flux=np.max([v['q_inc_kW_m2'] for v in floor_views],axis=0) if floor_views else None
        thermal=(s['T_upper_C']>=c['fo_temperature_C'])
        if floor_flux is not None:thermal=thermal|(floor_flux>=c['fo_flux_kW_m2'])
        transition_start=min((e['t_ign_s'] for e in (transitions or []) if e['room']==rid),default=float('inf'))
        potential=(fuel_fraction>=c['fgi_fuel_mass_fraction'])&(s['o2_upper_vol']>=c['fgi_oxygen_vol_percent']/100)&(s['bulk_HRR_W']<=1e-6)&~own_fire[rid]
        force=model.get('ignition_assumption',{})
        assisted=(t>=force.get('time_s',float('inf')))&(t<force.get('time_s',float('inf'))+force.get('duration_s',0))&(rid==force.get('room'))&(s['bulk_HRR_W']>1e-6)
        tags={'BD':bd,'BD_POTENTIAL':wait,'RO':gas,'UPPER_GAS':s['bulk_HRR_W']>1e-6,'FGI':gas&transported,'FGI_POTENTIAL':potential,
              'IGNITION_ASSUMED':assisted,'VENT_FLAME':ventq>1e-6,'FO':t>=transition_start,
              'FO_thermal':thermal,'FO_transition':t>=transition_start,'RAPID':rapid}
        output[rid]={'temperature_rate_C_s':rate,'gas_HRR_W':gasq,'bulk_HRR_W':s['bulk_HRR_W'],
                     'vent_HRR_W':ventq,'oxygen_in_kg_s':incoming[rid]['o2'],
                     'fuel_in_kg_s':incoming[rid]['fuel'],'BD_condition':wait,
                     'floor_incident_flux_kW_m2':floor_flux,
                     'floor_flux_evaluated':bool(floor_views),
                     'tags':tags,'first_times_s':{key:(float(t[np.flatnonzero(v)[0]]) if np.any(v) else None) for key,v in tags.items()},
                     'cause_basis':'model_reaction_records_and_history; not_an_intervention_proof',
                     'FGI_scope':'POTENTIAL uses user fuel mass/O2 screening thresholds, not a measured LFL or probability; FGI is reaction-with-transport only',
                     'FO_scope':'latched_prescribed_room_supply_transition; FO_thermal is a separate screening condition'}
    return output


def solid_inventory(model,result,events,transitions=None):
    """Exact integral of the piecewise-linear prescribed pyrolysis curve."""
    active={g['id']:g['initial_time_s'] for g in model['fuel_groups'] if 'initial_time_s' in g}
    active.update({e['group']:e['t_ign_s'] for e in events})
    rooms={r['id']:r for r in model['rooms']}; output={}
    fire_indices={g['id']:i for i,g in enumerate(active_fuels(model,events),1)}
    t=result['zone']['Time']
    curves,pools=source_curves(model,events,transitions) if transitions else ({},{})
    for group in model['fuel_groups']:
        total_mass=group['energy_MJ']*1000/group['heat_of_combustion_kJ_kg']
        if group['id'] not in active:
            output[group['id']]={'state':'not_activated','allocated_mass_kg':total_mass,
                                  'remaining_solid_kg':np.full(len(t),total_mass)}
            continue
        index=fire_indices[group['id']]; room=rooms[group['room']]
        knots,q,_=fire_curve(group,room['size_m'][0]*room['size_m'][1]); knots=np.array(knots); q=np.array(q)
        accumulated=np.r_[0,np.cumsum(np.diff(knots)*(q[:-1]+q[1:])/2)]
        age=np.clip(t-active[group['id']],0,knots[-1]); positions=np.minimum(len(knots)-2,np.searchsorted(knots,age,side='right')-1)
        delta=age-knots[positions]; slope=(q[positions+1]-q[positions])/(knots[positions+1]-knots[positions])
        supplied=accumulated[positions]+q[positions]*delta+.5*slope*delta**2
        q_input=np.interp(age,knots,q); q_input[t<active[group['id']]]=0
        from .mixture import primary_ratio
        ratio=primary_ratio(model,group)
        actual=result['zone'][f'HRR_{index}']; burning=actual>1e-6
        state=np.full(len(t),'inactive',dtype=object)
        state[burning]='fuel_supply_limited'
        state[burning&(actual<q_input*1000*ratio*(1-1e-3))]='oxygen_or_mixing_limited'
        output[group['id']]={'state':'activated','room':group['room'],'allocated_mass_kg':total_mass,
            'remaining_solid_kg':np.maximum(0,total_mass-supplied/group['heat_of_combustion_kJ_kg']),
            'prescribed_pyrolysis_kW':q_input,'actual_HRR_W':actual,
            'pyrolysis_supply_kg_s':result['compartments'][f'PYROL_{index}'],
            'limiting_state':state,'supply_integral_method':'exact_piecewise_linear_input_curve'}
    if transitions:
        t=np.asarray(t)
        for rid,pool in pools.items():
            groups=[g for g in model['fuel_groups'] if g['room']==rid]
            supplied=np.zeros(len(t)); after=t>=pool['time_s']
            for g in groups:
                if g['id'] in curves:
                    curve=curves[g['id']]; supplied+=integral(curve['t'],curve['q'],t)
            remaining=np.maximum(0,pool['total_allocated_kJ']-supplied)
            for group in groups:
                key=group['id']; entry=output[key]
                share=pool['remaining_by_group_kJ'][key]/pool['remaining_at_switch_kJ']
                entry['remaining_solid_kg'][after]=remaining[after]*share/group['heat_of_combustion_kJ_kg']
                entry['pooled_after_s']=pool['time_s']; entry['pool_owner_group']=pool['owner_group']
                entry['remaining_basis']='pre-switch individual supply; post-switch proportional shares of one room pool'
                if key in curves:
                    curve=curves[key]; q_input=np.interp(t,curve['t'],curve['q'],left=0,right=0)
                    ratio=primary_ratio(model,group)
                    actual=result['zone'][f'HRR_{fire_indices[key]}']
                    entry['prescribed_pyrolysis_kW']=q_input
                    limit=np.full(len(t),'inactive',dtype=object)
                    limit[actual>1e-6]='fuel_supply_limited'
                    limit[(actual>1e-6)&(actual<q_input*1000*ratio*(1-1e-3))]='oxygen_or_mixing_limited'
                    entry['limiting_state']=limit
                else:
                    entry['state']='pooled_without_separate_fire'
    return output


def simulate(raw,exe,output_folder):
    if raw.get('room_fire_rule',{}).get('enabled'):
        from .room_rule import simulate_room_rule
        return simulate_room_rule(raw,exe,output_folder)
    model=normalize(raw); folder=Path(output_folder).resolve(); folder.mkdir(parents=True,exist_ok=True)
    settings=model['spread']; targets=candidates(model); committed=[]; transitions=[]; runs=[]; attempts=[]
    prescribed=bool(model.get('prescribed_smoke'))
    if prescribed:
        from copy import deepcopy
        committed=deepcopy(model.get('prescribed_fire_events',[]))
        transitions=deepcopy(model.get('prescribed_fo_transitions',[]))
    elif model.get('native_prefix_seed'):
        from copy import deepcopy
        committed=deepcopy(model['native_prefix_seed']['events'])
        transitions=deepcopy(model['native_prefix_seed']['transitions'])
    started=time.monotonic(); pending=[]; error=None
    def run(events,fo_events):
        for trial in range(2 if settings.get('automatic_retry',False) else 1):
            if len(attempts)>=settings['max_runs']:raise TimeoutError('Maximum native attempts reached')
            index=len(attempts)
            remaining=settings['wall_time_budget_s']-(time.monotonic()-started)
            if remaining<=0:raise TimeoutError('Overall wall-time budget reached')
            execution_model={**model,'max_time_step_s':model['max_time_step_s']/(2**trial)}
            attempt={'attempt':index,'proposed_groups':[e['group'] for e in events],
                     'proposed_room_transitions':[e['room'] for e in fo_events],
                     'max_time_step_s':execution_model['max_time_step_s']}
            attempts.append(attempt)
            try:
                return execute(exe,folder/f'run_{index:02d}',make_deck(execution_model,events,targets,fo_events),gas_sidecar(model),
                               model['duration_s'],min(settings['run_timeout_s'],remaining),
                               stall_timeout_s=settings.get('stall_timeout_s',90.))
            except TimeoutError as exc:
                attempt.update(error=str(exc),stop_reason=getattr(exc,'reason','wall_time_budget'),
                               last_native_time_s=getattr(exc,'native_time_s',None),
                               wall_seconds=getattr(exc,'wall_seconds',None))
                raise
            except (RuntimeError,ValueError) as exc:
                attempt['error']=str(exc)
                if trial or not settings.get('automatic_retry',False) or len(attempts)>=settings['max_runs']:raise
    try:current=run(committed,transitions)
    except (TimeoutError,RuntimeError,ValueError) as exc:
        (folder/'summary.json').write_text(json.dumps({'terminated':interruption_status(exc) if isinstance(exc,TimeoutError) else 'solver_failed',
            'error':str(exc),'simulation_complete_to_requested_horizon':False,'spread_search_complete':False,
            'attempted_runs_count':len(attempts),'successful_runs_count':0,'attempts':attempts},ensure_ascii=False,indent=2),encoding='utf-8')
        raise
    runs.append(current['run'])
    iteration=None
    if settings['iteration_mode']=='fixed_point' and not prescribed:
        from .iteration import iterate
        current,committed,transitions,decisions,views,states,pending,terminated,error,iteration=iterate(
            model,current,targets,run,runs,attempts,started,assess,fo_proposals,check_causality)
    while iteration is None:
        if prescribed:
            views=[];states=room_series(model,current);terminated='prescribed_smoke';break
        decisions,views,states=assess(model,current,targets,committed,transitions,
                                     **({'deadline':started+settings['wall_time_budget_s']} if model.get('execution_profile')=='practical' else {}))
        if not settings['enabled']:decisions=[]
        decisions+=fo_proposals(model,current,states,committed,transitions,views)
        last=max((e['t_ign_s'] for e in committed+transitions),default=-float('inf'))
        if any(e['t_ign_s']<last-settings['event_tolerance_s'] for e in decisions):
            terminated='causality_failed'; error='A newly discovered solid ignition predates a committed event'; pending=decisions; break
        pending=sorted(decisions,key=lambda e:(e['t_ign_s'],e.get('kind','ignition'),e['event_id']))
        if not settings['enabled'] and not model['flashover']['enabled']:terminated='spread_disabled'; break
        if not pending:
            active_groups={g['id'] for g in model['fuel_groups'] if 'initial_time_s' in g}|{e['group'] for e in committed}
            valid_groups={v['group'] for v in views if v.get('status','ok')=='ok'}
            pooled_rooms={e['room'] for e in transitions}
            unevaluated=[g['id'] for g in model['fuel_groups'] if g['id'] not in active_groups|valid_groups and g['room'] not in pooled_rooms]
            terminated='incomplete_exposure' if settings['enabled'] and unevaluated else 'no_new_ignition'
            break
        if pending[0].get('kind')!='fo_transition' and len(committed)>=settings['max_added_ignitions']:terminated='max_added_ignitions'; break
        if len(attempts)>=settings['max_runs']:terminated='max_runs'; break
        if time.monotonic()-started>=settings['wall_time_budget_s']:terminated='time_budget'; break
        event=pending[0]
        is_fo=event.get('kind')=='fo_transition'
        try:
            updated=run(committed if is_fo else committed+[event],transitions+[event] if is_fo else transitions)
            check_causality(current,updated,event,settings)
        except TimeoutError as exc:
            terminated=interruption_status(exc); error=str(exc); break
        except (RuntimeError,ValueError) as exc:
            terminated='causality_failed' if 'mismatch' in str(exc) else 'solver_failed'
            error=str(exc); break
        (transitions if is_fo else committed).append(event); current=updated; runs.append(current['run'])
    # Validate the actual per-door total, independent of exposure geometry.
    directional_totals=defaultdict(float)
    for row in current['vents']:
        directional_totals[(row['time_s'],int(row['room_to']))]+=row['HRR_W']
    for i,room in enumerate(model['rooms'],1):
        for j,ti in enumerate(current['zone']['Time']):
            total=directional_totals[(float(ti),i)]
            if not np.isclose(total,current['zone'][f'DJET_{i}'][j],rtol=2e-8,atol=1e-5):
                raise ValueError('Per-vent DJET diagnostics do not match native room total')
    config_hash=hashlib.sha256(json.dumps(model,sort_keys=True).encode()).hexdigest()
    valid_groups={v['group'] for v in views if v.get('status','ok')=='ok'}
    active_groups={g['id'] for g in model['fuel_groups'] if 'initial_time_s' in g}|{e['group'] for e in committed}
    unevaluated=[g['id'] for g in model['fuel_groups'] if g['id'] not in valid_groups|active_groups and g['room'] not in {e['room'] for e in transitions}]
    result={'version':__version__,'spec_version':'20261021-practical-0.2' if model.get('execution_profile')=='practical' else '20261020-integrated-1.0','scenario':model,
            'config_sha256':config_hash,'engine_sha256':digest(exe),'terminated':terminated,'error':error,
            'simulation_complete_to_requested_horizon':True,
            'spread_search_complete':settings['enabled'] and terminated=='no_new_ignition',
            'fo_transition_search_complete':model['flashover']['enabled'] and terminated=='no_new_ignition',
            'attempted_runs_count':len(attempts),'successful_runs_count':len(runs),'committed_ignitions_count':len(committed),
            'final_input_sha256':current['run']['input_sha256'],'runs':runs,'attempts':attempts,
            'ignitions':committed,'fo_transitions':transitions,'pending_candidates':pending,'time_s':current['zone']['Time'],
            'candidates':views,'rooms':states,'directional_vent_reactions':current['vents'],
            'invalid_exposure_count':sum(v.get('status')=='invalid_exposure' for v in views),
            'unevaluated_groups':unevaluated,
            'solid_fuel_inventory':solid_inventory(model,current,committed,transitions),
            'room_fuel_pools':pool_inventory(model,current,committed,transitions),
            'ceiling_jets':current.get('jets',[]),'mixture_diagnostics':current.get('mixture',[]),
            'directional_flow_slabs':current['slabs'],'neutral_planes':neutral_planes(model,states,current['zone']['Time'],current),
            'opening_states':opening_histories(model,current),
            'phenomena':classify(model,current,states,committed,views,transitions),
            'assumptions':{'supplementary_radiation':'passive_one_way','djet_source':'native_per_vent_direction',
                           'partial_opening':'centered_effective_width','bulk_heat':'upper_gas_source_then_native_layer_radiation',
                           'lower_layer_bulk_reaction':'not_implemented','gas_rate':'project_exploration_profile_not_validated',
                           'fo_transition':'threshold_and_finite_prescribed_supply; not material phase change or validated FO prediction',
                           'fo_radiation':'native point plume retained; optional bounded distributed postprocessing radiation blended over transition_s',
                           'fo_execution':'external event loop, full rerun; not continuous-engine optimization'}}
    result['implementation_hashes']={path.name:digest(path) for path in Path(__file__).parent.glob('*.py')}
    result['wall_seconds']=time.monotonic()-started
    if iteration is not None:
        result['iteration']=iteration
        complete=terminated=='converged' and iteration['condition_consistent'] and not unevaluated
        result['spread_search_complete']=settings['enabled'] and complete
        result['fo_transition_search_complete']=model['flashover']['enabled'] and complete
        result['assumptions']['iteration']='batch full reruns; earlier-only retained schedule; not a guaranteed conservative bound'
        result['assumptions']['self_heating_boundary']='Existing event straddling output intervals are unverified; no advancement from contaminated right endpoints'
        if model.get('native_prefix_seed'):
            result['assumptions']['native_prefix_seed']='events computed with the same plate/FO criteria on a validated native prefix; not manually prescribed times'
            result['native_prefix_seed']=model['native_prefix_seed']
    else:
        result['iteration']={'mode':'earliest_single' if not prescribed else 'prescribed_smoke','passes':len(runs),
                             'terminated':terminated,'native_seconds':[0 if r.get('cache_hit') else r.get('wall_seconds',0) for r in runs]}
    from .conditions import evaluate
    result['conditions']=evaluate(model,result)
    result['effective_engine_gates']={'extended_temperature_scope':['vent_jet'] if model['gas']['enabled'] and model['gas']['vent_gate_enabled'] else [],
        'native_oxygen_rate_limit_mass_fraction':model['gas']['native_lower_oxygen_limit_mass_fraction'],
        'extension_oxygen_ignition_vol_percent':model['gas']['oxygen_min_vol_percent'],
        'bulk_reaction_rate_limit':'native chemistry with available upper-layer oxygen; stock reserved after native outflow'}
    from .practical import LIMITATIONS
    result['execution_profile']=model.get('execution_profile','legacy')
    result['limitations']=list(LIMITATIONS)
    if model['engine_optimization']['adaptive_radiation']:
        result['assumptions']['adaptive_radiation']='experimental native-derived linear response in T^4 and fire radiation; optical geometry held only in mature stable rooms; smooth native fallback; no added oxygen or heat source'
        result['limitations'].append('기존 화재실 적응형 복사는 안정된 실의 광학·형상 계수를 잠시 유지하는 시험 근사다. 새 착화식과 산소·연소식은 유지하지만 열 노출 및 전파 결과는 달라질 수 있다. NIST 검증 모델이 아니며 비교 합격 전 기본 적용하지 않는다.')
    if model['engine_optimization']['radiation_cache']:
        result['assumptions']['radiation_cache']='project execution optimization: reuse native RAD4 outputs only for bit-identical complete inputs; no lag, rounding or extra heat source'
    if model['engine_optimization']['wall_cache']:
        result['assumptions']['wall_cache']='project execution optimization: exact native wall derivatives reused only for update=0 with identical inputs including trial dt and previous wall profile; accepted-state updates always native'
    if model['gas'].get('mixture_smooth_enabled'):
        result['assumptions']['mixture_reaction']='r3c: state-only C1 gates and shared rate capped at 1/tau; native consumption reserved over fixed tau; MAX_TIME_STEP <= tau; no exponential step correction'
        result['limitations'].append('혼합시간 tau 동안 순정 반응·유출이 사용할 재고를 먼저 예약하는 보수적 근사다. 추가연소를 억제할 수 있으며 실제 혼합시간 또는 화염 전파시간으로 검증된 값이 아니다. 수치 단계 제한과 물리 반응률 상한을 구분한다.')
        result['limitations'].append('추가연소 r3의 산소/온도/연료 전환 폭은 프로젝트 설정이다. 기준 미만에서 반응하지 않지만 기준 위의 발열/잔여가스는 기존과 달라진다. 순정 CFAST 검증 범위를 승계하지 않는다.')
    if model['window_breakage'].get('enabled') or result['opening_states']:
        result['limitations'].append(WINDOW_LIMITATION)
        result['assumptions']['window_breakage']='stock conditional VENT; native WF; 5s observation; exact-box-boundary exterior rear'
    if prescribed:
        result['limitations'].append('전층 연기 간편 재생: 고체 착화·FO 시각은 이전 국부 사례에서 가져온 시나리오 지정값이다. 전층 조건에서 새 착화 시각을 재검증하지 않았으며 연기·온도·산소와 실제 발열은 전층 native 계산값이다.')
        result['fire_event_evaluation']='prescribed_from_local_scenario_not_repredicted_for_floor'
    result['input_warnings']=model.get('cad',{}).get('warnings',[])
    clean=_plain(result)
    (folder/'result.json').write_text(json.dumps(clean,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    (folder/'summary.json').write_text(json.dumps({k:clean[k] for k in ('version','terminated','error','attempted_runs_count','successful_runs_count','committed_ignitions_count','ignitions','fo_transitions','final_input_sha256')},ensure_ascii=False,indent=2),encoding='utf-8')
    return clean
