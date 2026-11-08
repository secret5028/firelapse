"""Project room-transition prescription; native ignition, no engine/RHS changes.

This is a different spread model, not an equivalent acceleration of plate ignition.
Each scenario executes once. A separate stock-engine baseline is mandatory.
"""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import re
import time
import numpy as np
from .model import normalize
from .deck import make_deck, gas_sidecar, fire_curve, candidates
from .native import execute, digest, interruption_status
from .exposure import room_series
from .openings import histories as opening_histories, LIMITATION as WINDOW_LIMITATION

PRESETS = {'conservative': (20.,120.), 'standard': (15.,60.), 'aggressive': (10.,30.)}
FUEL_PRESETS = {'conservative':(1.2,180.),'standard':(1.,60.),'aggressive':(.8,30.)}
R4_MODES = ('fuel_r4','ceiling_r4','floor_r4')
LIMITATIONS = [
    '실 단위 전실화재 전환 규칙은 프로젝트 가정이다. 실제 개별 연료 착화·FO 발생 시각의 예측이 아니다.',
    '기본 기준은 바닥 부근 위쪽 면의 입사 복사열이다. 판 온도와 상층 연기 온도를 동일하게 취급하지 않는다.',
    '10/15/20 kW/㎡와 30/60/120초 조합은 민감도 프리셋이며 발생 확률이나 위험의 보수적 상한이 아니다.',
    '실내 문 면적을 독립 외기 공급으로 합산하지 않는다. 입력은 연료 공급 상한이고 실제 연소는 순정 산소 제한을 따른다.',
    '공급 곡선 적분으로 고체 예산을 소진한다. 산소 부족으로 못 탄 공급 연료는 순정 미연 연료로 이동할 수 있다.',
    '실당 대표 점 화원과 2층 존 모델이다. 실내 화염 전파·분산 복사·폭압·천장 전체 속도장은 계산하지 않는다.',
    '문 너머 보충 복사와 개별 연료 판 열응답은 착화 결정에 사용하지 않는다. 기존 방식과 전이 결과가 달라질 수 있다.',
    '프로젝트 bulk/혼합물 추가연소·강제 가스 점화·FO 공급 재확대·적응형 복사는 꺼진다. 순정 플룸·개구부 연소는 유지한다.',
    'FGI·백드래프트 조건은 위험 선별이며 확장 추가연소 발생 결과가 아니다. 조건표는 계산에 피드백하지 않는다.',
    '착화 시각은 순정 정수초 로그와 출력구간으로 관측한 근사값이다. 센서 시계열 보간값은 사건 시점의 정확한 값이 아니다.',
    '시나리오당 순정 적분 1회다. 기준 실행과 프리셋 비교는 각각 별도 실행이며 계산 시간 단축은 보장하지 않는다.',
]

def settings(raw):
    requested=raw.get('room_fire_rule',{})
    name=requested.get('preset','standard')
    if name not in PRESETS:raise ValueError('Unknown room fire preset')
    flux,ramp=PRESETS[name]
    default_mode='floor_r2' if requested.get('prepared') or 'setpoint' in requested else 'fuel_r3'
    out={'enabled':True,'preset':name,'criterion':'FLUX','setpoint':flux,'ramp_s':ramp,
         'decay_energy_fraction':.3,'sensor_height_m':.1,'power_basis':'fuel_supply_native_oxygen',
         'trigger_mode':default_mode,'threshold_multiplier':FUEL_PRESETS[name][0],
         'vent_cap_enabled':False,'vent_cap_k':1.5,'candidate_ids':{}}
    if requested.get('trigger_mode',default_mode)=='fuel_r3':out['ramp_s']=FUEL_PRESETS[name][1]
    if requested.get('trigger_mode')=='parent_r5':
        delay={'conservative':120.,'standard':60.,'aggressive':30.}[name]
        out.update(criterion='TEMPERATURE',setpoint=600.,ramp_s=delay,delay_s=delay,vent_cap_enabled=True,vent_cap_k=1.)
    out.update({k:v for k,v in requested.items() if k in out or k=='baseline_engine'})
    if out['trigger_mode'] in R4_MODES:
        expected={'ceiling_r4':500.,'floor_r4':15.}.get(out['trigger_mode'])
        if expected is not None and 'setpoint' in requested and not requested.get('prepared') and requested['setpoint']!=expected:
            raise ValueError('r4 comparison uses fixed 500 C / 15 kW/m2 thresholds')
        out['vent_cap_enabled']=requested.get('vent_cap_enabled',True)
        out['vent_cap_k']=requested.get('vent_cap_k',1.)
        if out['trigger_mode']=='ceiling_r4':out.update(criterion='TEMPERATURE',setpoint=500.)
        if out['trigger_mode']=='floor_r4':out.update(criterion='FLUX',setpoint=15.)
    if out['criterion'] not in ('FLUX','TEMPERATURE'):raise ValueError('Select one native target criterion; upper gas OR is unsupported')
    if out['trigger_mode'] not in ('floor_r2','fuel_r3','parent_r5',*R4_MODES):raise ValueError('Unknown room rule trigger mode')
    if out['trigger_mode']=='parent_r5':
        if out['criterion']!='TEMPERATURE' or out['setpoint']!=600.:raise ValueError('T4 uses a fixed parent plate threshold of 600 C')
        if isinstance(out['delay_s'],bool) or not np.isfinite(out['delay_s']) or out['delay_s']<=0:raise ValueError('Invalid T4 delay')
    if out['trigger_mode'] in ('fuel_r3','fuel_r4') and 'setpoint' in requested and not requested.get('prepared'):
        raise ValueError('fuel_r3 reuses per-material thresholds; use threshold_multiplier, not the r2 floor setpoint')
    if not isinstance(out['vent_cap_enabled'],bool) or not isinstance(out['candidate_ids'],dict):raise ValueError('Invalid cap/candidate settings')
    for key in ('setpoint','ramp_s','sensor_height_m','decay_energy_fraction','threshold_multiplier','vent_cap_k'):
        if isinstance(out[key],bool) or not isinstance(out[key],(int,float)) or not np.isfinite(out[key]) or out[key]<=0:
            raise ValueError('Invalid room rule '+key)
    if out['decay_energy_fraction']>=1:raise ValueError('Decay fraction must be below one')
    if out['power_basis']!='fuel_supply_native_oxygen':raise ValueError('Dynamic ventilation HRR cap is not implemented')
    return out

def ventilation_cap(model,room,k=1.5,external_priority=False):
    """One opening only; not a solved supply of oxygen or a certified limit."""
    from .openings import policy
    choices=[]
    for opening in model['openings']:
        if room not in (opening['a'],opening['b']) or opening.get('type')=='FLOOR':continue
        p=policy(model,opening)
        fraction=p['post_fraction'] if p else max(row[1] for row in opening.get('schedule',[[0,1]]))
        height=opening['top_m']-opening.get('bottom_m',0)
        area=opening['width_m']*height*fraction
        choices.append({'opening_id':opening['id'],'exterior':'OUTSIDE' in (opening['a'],opening['b']),'effective_area_m2':area,'height_m':height,
                        'fraction':fraction,'A_sqrt_H':area*np.sqrt(height)})
    external=[v for v in choices if v['exterior']]
    discount=.5 if external_priority and not external else 1.
    if external_priority and external:choices=external
    best=max(choices,key=lambda c:c['A_sqrt_H']) if choices else None
    return {'room':room,'opening':best,'k':k,'internal_discount':discount,
            'policy':'external_first_r4' if external_priority else 'single_opening_r3',
            'cap_kW':k*1500*best['A_sqrt_H']*discount if best else 0.,
            'basis':'numerical supply cap; exterior opening first in r4, otherwise internal factor 0.5; future maximum/post-breakage fraction; not solved oxygen availability'}

def supply_curve(group, floor_area, rule):
    """Finite linear ramp/hold/decay. Integral is exactly the allocated kJ."""
    energy=group['energy_MJ']*1000.; fraction=rule['decay_energy_fraction']; ramp=rule['ramp_s']
    area=min(floor_area,group.get('fuel_area_m2',floor_area))
    caps={'configured_peak_kW':group['peak_kW'],'area_hrrpua_kW':area*group['hrrpua_kW_m2'],
          'finite_energy_ramp_kW':2*(1-fraction)*energy/ramp}
    if rule.get('vent_cap_enabled'):
        caps['numerical_vent_cap_kW']=group['room_vent_cap']['cap_kW']
    peak=min(caps.values())
    if peak==0:
        return {'t':[0.,1.e9],'q':[0.,0.],'area':[.1,.1],'Q_max_kW':0.,'caps':caps,
                'limiting_cap':'numerical_vent_cap_kW','energy_MJ':energy/1000,'budget_released_MJ':0.}
    hold=max(0.,(1-fraction)*energy/peak-ramp/2)
    decay=2*fraction*energy/peak
    t=[0.,ramp];q=[0.,peak]
    if hold>1e-9:t.append(ramp+hold);q.append(peak)
    t.append(ramp+hold+decay);q.append(0.)
    return {'t':t,'q':q,'area':[min(floor_area,max(.1,v/group['hrrpua_kW_m2'])) for v in q],
            'Q_max_kW':peak,'caps':caps,'limiting_cap':min(caps,key=caps.get),'energy_MJ':energy/1000}

def prepare(raw):
    if raw.get('room_fire_rule',{}).get('trigger_mode')=='parent_r5':
        from .parent_rule import prepare_parent
        return prepare_parent(raw)
    rule=settings(raw); patched=deepcopy(raw)
    # Turn off every project reaction path, including CO energy reservation.
    patched.setdefault('gas',{}).update(enabled=False,bulk_enabled=False,vent_gate_enabled=False,
        mixture_enabled=False,mixture_smooth_enabled=False,jet_enabled=False)
    patched.setdefault('flashover',{})['enabled']=False
    patched.setdefault('engine_optimization',{}).update(adaptive_radiation=False,radiation_cache=False,wall_cache=False)
    for key in ('ignition_assumption','native_prefix_seed','prescribed_smoke','prescribed_fire_events','prescribed_fo_transitions'):
        patched.pop(key,None)
    model=normalize(patched)
    r4=rule['trigger_mode'] in R4_MODES
    old_targets=candidates(model) if rule['trigger_mode'] in ('fuel_r3','fuel_r4') else []
    initial=[g for g in model['fuel_groups'] if 'initial_time_s' in g]
    if len(initial)!=1:raise ValueError('Room rule requires exactly one initial fire')
    initial_room=initial[0]['room'];groups=[deepcopy(initial[0])];targets=[];excluded=[]
    warnings=[]
    if r4:
        initial_cap=ventilation_cap(model,initial_room,rule['vent_cap_k'],True)
        if initial[0]['peak_kW']>initial_cap['cap_kW']:
            warnings.append('최초 화원 입력 peak가 r4 수치 공급 상한을 넘음: 초기 곡선은 변경하지 않음')
    for room in model['rooms']:
        fuels=[g for g in model['fuel_groups'] if g['room']==room['id'] and 'initial_time_s' not in g]
        if room['id']==initial_room:
            excluded.extend(g['id'] for g in fuels);continue
        if not fuels:continue
        first=fuels[0]
        if any(any(g[k]!=first[k] for k in ('formula','heat_of_combustion_kJ_kg','co_yield')) for g in fuels):
            raise ValueError('Room fuel aggregation requires identical chemistry: '+room['id'])
        group=deepcopy(first);floor=room['size_m'][0]*room['size_m'][1]
        group['source_groups']=[g['id'] for g in fuels]
        group['energy_MJ']=sum(g['energy_MJ'] for g in fuels)
        group['peak_kW']=sum(g['peak_kW'] for g in fuels)
        group['hrrpua_kW_m2']=sum(g['hrrpua_kW_m2']*g['energy_MJ'] for g in fuels)/group['energy_MJ']
        group['fuel_area_m2']=min(floor,sum(g.get('fuel_area_m2',floor) for g in fuels))
        units=[{**u,'budget_fraction':u['budget_fraction']*g['energy_MJ']/group['energy_MJ']} for g in fuels for u in g.get('fuel_units',[])]
        if units and all(g.get('fuel_units') for g in fuels):group['fuel_units']=units
        else:group.pop('fuel_units',None)
        center=(np.array(room['origin_m'])+np.array(room['size_m'])*[.5,.5,0]).tolist()
        group.setdefault('position_m',center)
        # Existing CAD representative points have already been checked against the polygon.
        sensor=list(group['position_m']);sensor[2]=room['origin_m'][2]+rule['sensor_height_m']
        solver=list(group.get('solver_position_m',group['position_m']));solver[2]=sensor[2]
        local=np.array(solver)-room['origin_m']
        if not np.all((local>0)&(local<room['size_m'])):raise ValueError('Room rule sensor must be strictly inside: '+room['id'])
        target_id='RF_'+room['id']
        material={**model['material'],'conductivity_W_mK':45.,'density_kg_m3':7850.,
                  'specific_heat_kJ_kgK':.46,'thickness_m':.001,'emissivity':.9}
        targets.append({'id':target_id,'group':group['id'],'room':room['id'],'xyz':sensor,'solver_xyz':solver,
                        'normal':[0,0,1],'material':material,'basis':'project floor-facing native incident-radiation sensor'})
        criterion=rule['criterion'];setpoint=rule['setpoint']
        if rule['trigger_mode']=='ceiling_r4':
            if room['size_m'][2]<=.2:raise ValueError('Room too low for ceiling sensor')
            ceiling=targets[-1]
            for key in ('xyz','solver_xyz'):ceiling[key][2]=room['origin_m'][2]+room['size_m'][2]-.2
            ceiling.update(normal=[0,0,-1],basis='1 mm steel plate 0.2 m below ceiling; proxy, not upper gas temperature')
        if rule['trigger_mode'] in ('fuel_r3','fuel_r4'):
            options=[v for v in old_targets if v['group'] in group['source_groups'] and v.get('used_for_ignition',True)]
            selected=rule['candidate_ids'].get(room['id'])
            if selected:options=[v for v in options if selected in (v['id'],v.get('source_candidate_id'))]
            if not options:raise ValueError('No existing representative fuel target for '+room['id'])
            # Deterministic input order; never use future ignition results to pick a target.
            chosen=deepcopy(options[0]);floor_target=targets.pop()
            saved_floor=next((v for v in old_targets if v['room']==room['id'] and v.get('used_for_ignition') is False),None)
            if saved_floor is not None:floor_target=deepcopy(saved_floor)
            chosen.update(id=target_id,group=group['id'],source_candidate_id=options[0].get('source_candidate_id',options[0]['id']),
                          candidate_selection='explicit ID' if selected else 'first existing candidate in input order; other candidates not OR-ed')
            mat=chosen['material']
            criterion='FLUX' if 'ignition_flux_kW_m2' in mat else 'TEMPERATURE'
            setpoint=mat.get('ignition_flux_kW_m2',mat['ignition_C'])*rule['threshold_multiplier']
            if criterion=='TEMPERATURE' and setpoint<=model['ambient_C']:raise ValueError('Fuel ignition threshold must exceed ambient')
            if mat.get('pilot','assumed')=='none':raise ValueError('Native target ignition cannot represent an absent required pilot')
            chosen['used_for_ignition']=True
            floor_target.update(id='RF_FLOOR_'+room['id'],used_for_ignition=False,display_threshold_kW_m2=15.)
            targets.extend([chosen,floor_target])
            if not r4:
                group['position_m']=list(chosen.get('fire_source_xyz',chosen['xyz']))
                group['solver_position_m']=list(chosen.get('solver_fire_xyz',chosen.get('solver_xyz',group['position_m'])))
            group['source_candidate_id']=chosen['source_candidate_id']
        group['room_rule_trigger']={'criterion':criterion,'setpoint':setpoint,'target_id':target_id}
        if rule['vent_cap_enabled']:group['room_vent_cap']=ventilation_cap(model,room['id'],rule['vent_cap_k'],r4)
        group['room_rule_curve']=supply_curve(group,floor,rule)
        groups.append(group)
    if r4:
        for group in groups:
            room=next(r for r in model['rooms'] if r['id']==group['room'])
            for key in ('position_m','solver_position_m'):
                if key in group and not 0<=group[key][2]-room['origin_m'][2]<=.5:
                    raise ValueError('r4 fire base must be 0..0.5 m above floor, independently of sensor: '+group['id'])
    model['fuel_groups']=groups
    model['explicit_candidates']=targets
    if model.get('cad'):
        model['cad']['candidate_basis']='one existing fuel target' if rule['trigger_mode'] in ('fuel_r3','fuel_r4') else 'one native ceiling plate' if rule['trigger_mode']=='ceiling_r4' else 'one native floor-facing room sensor'
        model['cad']['uncovered_fuel_groups']=[]
    model['room_fire_rule']={**rule,'prepared':True,'warnings':warnings,'initial_room_excluded_reserve_groups':excluded,
                            'sensor_basis':'existing fuel target and per-material threshold' if rule['trigger_mode'] in ('fuel_r3','fuel_r4') else 'ceiling plate temperature, not upper gas temperature' if rule['trigger_mode']=='ceiling_r4' else 'target front incident radiation; TEMPERATURE means plate surface, not gas'}
    return model,targets

def observe(model,native,targets):
    """Read ID-mapped sensors and native IGN; do not infer ignition from temperature."""
    t=native['zone']['Time'];devices=native['devices'];ids=native['devices_ids']
    events=[];views=[];records=[]
    log=(Path(native['run']['folder'])/'case.log').read_text(errors='replace')
    logged={m[1]:float(m[2]) for m in re.finditer(r'\((F_[A-Za-z0-9_]+)\) ignited at\s+(\d+) seconds',log)}
    targetmap={v['id']:v for v in targets}
    def view_for(target):
        def column(prefix):
            found=[key for key,id_ in ids.items() if id_.strip()==target['id'] and key.startswith(prefix)]
            if len(found)!=1:raise ValueError('Missing/ambiguous target column '+prefix+' '+target['id'])
            return devices[found[0]]
        return {**target,'status':'ok','surface_C':column('TRGSURT_'),'q_inc_kW_m2':column('TRGFLXI_'),
                'used_for_ignition':target.get('used_for_ignition',True),'evaluation_basis':'native target; no supplementary heat feedback'}
    views=[view_for(target) for target in targets]
    for index,group in enumerate(model['fuel_groups'],1):
        if 'initial_time_s' in group:continue
        target=targetmap[group['room_rule_trigger']['target_id']]
        view=next(v for v in views if v['id']==target['id']);flux=view['q_inc_kW_m2'];surface=view['surface_C']
        flags=native['compartments'][f'IGN_{index}']
        hits=np.flatnonzero(flags>.5)
        at=None;interval=None
        if len(hits):
            j=int(hits[0]);lo=float(t[max(0,j-1)]);hi=float(t[j]);rounded=logged.get('F_'+group['id'])
            if rounded is not None:lo=max(lo,rounded-.5);hi=min(hi,rounded+.5)
            if lo>hi:raise ValueError('Ignition log/CSV disagree')
            at=(lo+hi)/2;interval=[lo,hi]
            event={'event_id':'room_rule_'+group['room'],'group':group['id'],'room':group['room'],
                't_ign_s':at,'time_interval_s':interval,'time_basis':'native IGN output bracket intersect rounded native log',
                'xyz':group['position_m'],'solver_xyz':group.get('solver_position_m',group['position_m']),
                'candidate':target['id'],'largest_incident_term':'native_room_rule',
                'placement_basis':'one representative source for assumed room-wide supply'}
            events.append(event)
            if model['room_fire_rule']['trigger_mode']=='parent_r5':
                delay=model['room_fire_rule']['delay_s']
                event.update(trigger_room=target['room'],transition_assumption=True,
                             prescribed_supply_start_s=at+delay,prescribed_supply_start_interval_s=[x+delay for x in interval],
                             basis='parent plate trigger followed by prescribed zero-HRR delay; not physical ignition prediction')
        trigger=group['room_rule_trigger'];curve=group['room_rule_curve'];sensor=flux if trigger['criterion']=='FLUX' else surface
        records.append({'room':group['room'],'group':group['id'],'target_id':target['id'],'ignition_s':at,'time_interval_s':interval,
            'fire_position_m':group['position_m'],'sensor_position_m':target['xyz'],
            'sensor_room':target['room'],'delay_s':model['room_fire_rule'].get('delay_s',0),
            'sensor_max':float(np.max(sensor)),'sensor_at_ignition_interpolated':None if at is None else float(np.interp(at,t,sensor)),
            'criterion':trigger['criterion'],'setpoint':trigger['setpoint'],'source_candidate_id':group.get('source_candidate_id'),
            'vent_cap':group.get('room_vent_cap'),
            'Q_max_kW':curve['Q_max_kW'],'power_basis':curve['limiting_cap'],'power_caps':curve['caps'],
            'energy_MJ':curve['energy_MJ'],'actual_peak_kW':float(np.max(native['zone'][f'HRR_{index}']))/1000})
    return sorted(events,key=lambda e:e['t_ign_s']),views,records

def simulate_room_rule(raw,exe,output_folder):
    from .spread import _plain, classify, solid_inventory, neutral_planes
    from .conditions import evaluate
    from . import __version__
    model,targets=prepare(raw);folder=Path(output_folder).resolve();folder.mkdir(parents=True,exist_ok=True)
    started=time.monotonic();runs=[];settings_=model['spread'];rule=model['room_fire_rule']
    baseline_exe=Path(rule.get('baseline_engine') or Path(__file__).resolve().parents[1]/'build/baseline/cfast-baseline.exe')
    if not baseline_exe.is_file():raise ValueError('Stock CFAST baseline executable required: '+str(baseline_exe))
    if digest(baseline_exe)==digest(exe):raise ValueError('Baseline must use the separate stock build')
    (folder/'scenario.json').write_text(json.dumps(model,ensure_ascii=False,indent=2),'utf-8')
    baseline=deepcopy(model)
    for g in baseline['fuel_groups']:
        if 'room_rule_trigger' in g:g['room_rule_trigger']['setpoint']=1e20
    # Same targets and standby fires, unreachable criterion. Keep native max dt identical.
    for name,engine,current in [('baseline_native',baseline_exe,baseline),('run_00',exe,model)]:
        remaining=settings_['wall_time_budget_s']-(time.monotonic()-started)
        try:
            if remaining<=0:raise TimeoutError('Room-rule pair time budget exhausted')
            result=execute(engine,folder/name,make_deck(current,[],targets),gas_sidecar(current),model['duration_s'],
                           min(settings_['run_timeout_s'],remaining),stall_timeout_s=settings_.get('stall_timeout_s',90.))
            runs.append(result['run'])
        except (TimeoutError,RuntimeError,ValueError) as exc:
            status_path=folder/name/'case.status'
            failure={'terminated':interruption_status(exc) if isinstance(exc,TimeoutError) else 'solver_failed','error':str(exc),
                     'failed_stage':name,'simulation_complete_to_requested_horizon':False,'runs':runs,
                     'spread_model':'room_flashover_rule_v1','automatic_retry':False,'room_fire_rule':rule,
                     'engine_sha256':digest(engine),'last_native_time_s':getattr(exc,'native_time_s',None),
                     'wall_seconds':getattr(exc,'wall_seconds',None),
                     'native_status':status_path.read_text(errors='replace').strip() if status_path.exists() else None}
            (folder/'summary.json').write_text(json.dumps(failure,ensure_ascii=False,indent=2),'utf-8');raise
        if name=='baseline_native':base=result
    native=result;t=native['zone']['Time'];states=room_series(model,native)
    events,views,records=observe(model,native,targets)
    # These rays are diagnostic only. Never add them to the native sensor or
    # integrate a second target/ignition response; no rerun can be triggered here.
    from .exposure import supplementary
    for target,view in zip(targets,views):
        terms,near=supplementary(model,native,target,states,events)
        view['supplementary_display_kW_m2']=terms
        view['supplementary_used_for_ignition']=False
    inventory=solid_inventory(model,native,events)
    for event in events:
        inventory[event['group']]['supply_integral_method']='piecewise_linear_curve_with_observed_ignition_time; timing is approximate'
        inventory[event['group']]['ignition_time_interval_s']=event['time_interval_s']
    # A prescribed whole-room transition is reported separately from FO thermal conditions.
    transitions=[] if rule['trigger_mode']=='parent_r5' else [{**e,'kind':'room_rule_transition'} for e in events]
    config_hash=hashlib.sha256(json.dumps(model,sort_keys=True).encode()).hexdigest()
    out={'version':__version__,'spec_version':'20261025-room-rule-v1','scenario':model,'config_sha256':config_hash,
         'engine_sha256':digest(exe),'engine':{'version':'7.7.7','sha256':digest(exe),'role':'native physics with project diagnostics; reactions disabled'},
         'spread_model':'room_flashover_rule_v1','room_fire_rule':{**rule,'rooms':records},
         'terminated':'room_rule_completed','error':None,'simulation_complete_to_requested_horizon':True,
         'spread_search_complete':True,'fo_transition_search_complete':False,
         'attempted_runs_count':2,'successful_runs_count':2,'scenario_runs_count':1,'baseline_runs_count':1,
         'committed_ignitions_count':len(events),'runs':runs,'attempts':[],
         'baseline_native':{'engine_sha256':digest(baseline_exe),'run':base['run'],'basis':'stock binary, same geometry/targets/fire tables; standby thresholds unreachable'},
         'final_input_sha256':native['run']['input_sha256'],'ignitions':events,'fo_transitions':transitions,
         'room_rule_transitions':events if rule['trigger_mode']=='parent_r5' else [],
         'pending_candidates':[],'time_s':t,'candidates':views,'rooms':states,
         'directional_vent_reactions':native['vents'],'directional_flow_slabs':native['slabs'],
         'invalid_exposure_count':0,'unevaluated_groups':[],
         'solid_fuel_inventory':inventory,'room_fuel_pools':{},'ceiling_jets':native.get('jets',[]),'mixture_diagnostics':[],
         'neutral_planes':neutral_planes(model,states,t,native),'opening_states':opening_histories(model,native),
         'phenomena':classify(model,native,states,events,views,transitions),
         'assumptions':{'spread':'native target trigger followed by prescribed room-wide supply',
                        'supplementary_radiation':'not used for ignition; no external plate loop',
                        'gas':'native oxygen/plume/vent combustion only; extension bulk and CO reserve disabled',
                        'fo_execution':'one native integration per scenario; baseline separate',
                        'fuel_energy':'integrated prescribed pyrolysis budget, not actual oxygen-limited HRR integral',
                        'sensor_material':'1 mm steel proxy; flux criterion does not use target thermal inertia',
                        'initial_room':'initial input curve retained; other unignited reserve groups in initial room excluded'},
         'iteration':{'mode':'native_room_rule','passes':1,'external_event_reruns':0},
         'execution_profile':model.get('execution_profile','legacy'),'limitations':LIMITATIONS+[WINDOW_LIMITATION],
         'input_warnings':model.get('cad',{}).get('warnings',[]),'wall_seconds':time.monotonic()-started}
    out['physical_validation']=native.get('physical_validation')
    out['conditions']=evaluate(model,out)
    out['conditions']['_room_rule']=out['room_fire_rule']
    from .conditions import term,phenomenon,_finite
    for group in model['fuel_groups'][1:]:
        trigger=group['room_rule_trigger'];view=next(v for v in views if v['id']==trigger['target_id'])
        event=next((e for e in events if e['group']==group['id']),None)
        at=event['t_ign_s'] if event else float('inf')
        values=view['q_inc_kW_m2'] if trigger['criterion']=='FLUX' else view['surface_C']
        item=phenomenon(t,[term('native_sensor','순정 대표 연료 센서' if rule['trigger_mode'] in ('fuel_r3','fuel_r4') else '순정 실 전환 센서',values,trigger['setpoint'],'>',
                              'kW/㎡' if trigger['criterion']=='FLUX' else '℃','room_fire_rule',len(t))],
                       {'sensor':values})
        item.update(room=group['room'],state=['active' if x>=at else 'inactive' for x in t],
                    ignition_s=None if event is None else at,cause='native_room_rule' if event else None,
                    supplementary_display_kW_m2=view['supplementary_display_kW_m2'],supplementary_used_for_ignition=False)
        from .combustion_display import group_display
        item.update(group_display(inventory[group['id']],t,at))
        if rule['trigger_mode']=='parent_r5':
            item.update(transition_assumption=True,parent_room=group['parent_transition']['room'],
                        prescribed_supply_start_s=event['prescribed_supply_start_s'] if event else None,
                        delay_s=rule['delay_s'])
            item['terms'][0]['label']='출발실 천장 강판 온도 · 전이 가정'
        out['conditions']['_groups'][group['id']]=_finite(item)
    if rule['trigger_mode'] in ('fuel_r3','fuel_r4'):
        out['spec_version']='20261025-room-rule-r3'
        out['assumptions']['sensor_material']='existing selected fuel candidate position/material; native target response differs from Python plate plus supplementary heat'
        out['limitations']=[s for s in out['limitations'] if not s.startswith(('기본 기준은','10/15/20'))]
        out['limitations']+=['기존 대표 후보 위치·물성·기준값을 재사용하지만 순정 타깃 열응답은 기존 Python 판+보충복사와 동등하지 않다. 여러 후보의 OR 조건도 실당 하나로 축소한다.',
            'r3 프리셋은 기존 착화 기준값의 1.2/1.0/0.8배와 상승180/60/30초라는 프로젝트 가정이다. 바닥15kW/㎡는 표시 전용이다.',
            '선택적 공급 상한은 k*1500*max(A√H)다. 미래 개방/창 파괴 후 면적을 사용하는 수치 안정용 가정이며 실제 환기 한계가 아니다. 상한으로 미연 가스와 문 연소량이 감소할 수 있다.']
        for view in views:
            if view.get('used_for_ignition') is False:
                out['conditions'][view['room']]['room_transition_display']=_finite(phenomenon(t,[term('floor_flux','표시용 실 전환 조건',view['q_inc_kW_m2'],15.,'>=','kW/㎡','display_only_not_ignition',len(t))],{'flux_kW_m2':view['q_inc_kW_m2']}))
    if rule['trigger_mode'] in R4_MODES:
        out['spec_version']='20261025-room-rule-r4'
        out['limitations']=[s for s in out['limitations'] if not s.startswith(('기본 기준은','10/15/20','선택적 공급 상한은'))]
        out['input_warnings']+=rule.get('warnings',[])
        out['assumptions'].update(fire_position='independent of sensor; floor or fuel base <=0.5 m',
            sensor_material='existing fuel target' if rule['trigger_mode']=='fuel_r4' else '1 mm steel proxy',
            supply_cap='k*1500*max exterior A sqrt(H), otherwise internal max times 0.5; numerical assumption')
        out['limitations']+=['r4 천장500℃는 판 온도 기준이며 상층 가스500℃와 동일하지 않다. 외기 우선 공급 상한과 내부0.5계수는 프로젝트 가정이다.',
            '착화 조건/연료 공급과 실제 화원 HRR을 구분한다. IGN만으로 연소 중으로 표시하지 않는다. 최종 표준 선택 전 실험 모드다.']
    if rule['trigger_mode']=='parent_r5':
        out['spec_version']='20261025-room-rule-r5-T4'
        out['input_warnings']+=rule.get('warnings',[])
        out['assumptions'].update(spread='single open-door BFS parent plate >600 C, then prescribed delay and room supply',
            sensor_material='1mm downward steel plate, 0.2m below parent ceiling; not parent gas temperature',
            fire_position='r4 floor/fuel base <=0.5m, independent of parent sensor',
            supply_cap='r4 exterior-priority cap with internal 0.5 fallback; numerical assumption, not exact ventilation limit')
        out['limitations']=[s for s in out['limitations'] if not s.startswith(('기본 기준은','10/15/20'))]+[
            'T4는 출발실 판온도600℃ 조건 이후 지정 지연만큼 기다렸다가 연료를 공급하는 전이 가정이다. 실제 FO/착화 예측이 아니다.',
            '첫 BFS 부모 하나만 사용한다. 다른 경로와 부모의 실제 연소 여부를 조건으로 추가하지 않으며, 연기 유입으로 가열된 부모도 조건을 만족할 수 있다.',
            'native IGN은 출발실 조건 충족 시각이며 실제 연료 공급은 지연 후 시작한다. 실제 양수 HRR 시작은 별도 확인한다.']
    out['implementation_hashes']={p.name:digest(p) for p in Path(__file__).parent.glob('*.py')}
    clean=_plain(out)
    (folder/'result.json').write_text(json.dumps(clean,ensure_ascii=False,allow_nan=False),'utf-8')
    (folder/'summary.json').write_text(json.dumps({k:clean[k] for k in ('spread_model','terminated','error','scenario_runs_count','baseline_runs_count','wall_seconds','ignitions','room_fire_rule','baseline_native')},ensure_ascii=False,indent=2),'utf-8')
    return clean
