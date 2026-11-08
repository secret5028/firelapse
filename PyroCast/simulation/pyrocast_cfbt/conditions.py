"""Condition diagnostics only. Never feeds back into ignition or native combustion."""
import numpy as np

ROLLOVER_REVISION = 'fgi_rollover_state_v2'
OXYGEN_SCORE_REVISION = 'inverse_oxygen_floor_v1'
# Numerical division guard in the shared table's oxygen unit (vol%).
# This is machine precision, not a physical oxygen/ignition threshold.
OXYGEN_SCORE_FLOOR = float(np.finfo(np.float64).eps)

def rollover_states(model, t, fgi, actual_hrr, received_jet, result=None, threshold=100.):
    """FGI subsidiary state only; no independent score or exterior-path gate.

    Open connected flame rooms provide ignition. The undirected building
    graph supplies connectivity, not a resolved gas velocity direction.
    Initial physical fire rooms are excluded, including all their cells.
    """
    from .openings import realized_fraction
    t=np.asarray(t);n=len(t);result=result or {'time_s':t}
    if not np.isfinite(threshold) or threshold<0:raise ValueError('Invalid ribbon threshold')
    physical={r['id']:r.get('parent_room',r['id']) for r in model['rooms']}
    nodes=set(physical.values())
    origins={physical[g['room']] for g in model.get('fuel_groups',[]) if 'initial_time_s' in g and g['room'] in physical}
    heat={r:np.zeros(n) for r in nodes};jets={r:np.zeros(n) for r in nodes}
    for rid,room in physical.items():
        if actual_hrr.get(rid) is not None:heat[room]+=np.asarray(actual_hrr[rid])
        if received_jet.get(rid) is not None:jets[room]+=np.asarray(received_jet[rid])
    pilot={r:np.zeros(n,bool) for r in nodes};sources={r:[set() for _ in t] for r in nodes}
    for v in model.get('openings',[]):
        if v['a'] not in physical or v['b'] not in physical:continue
        a,b=physical[v['a']],physical[v['b']]
        if a==b:continue
        opened=np.asarray(realized_fraction(result,v,t))>0
        for target,source in ((a,b),(b,a)):
            on=opened&(heat[source]>0);pilot[target]|=on
            for i in np.flatnonzero(on):sources[target][i].add(source)
    out={}
    for rid,room in physical.items():
        ignition=pilot[room]|(jets[room]>0);excluded=room in origins
        degree=fgi[rid].get('scores',{}).get('degree',[None]*n)
        active=[False if excluded or not ignition[i] else None if v is None else bool(v*100>=threshold) for i,v in enumerate(degree)]
        hits=[i for i,v in enumerate(active) if v is True]
        out[rid]={'revision':ROLLOVER_REVISION,'label':'인접실 원격점화 FGI 조건','active':active,
            'ignition':ignition.tolist(),'excluded_origin':excluded,'threshold':threshold,
            'first_active_s':float(t[hits[0]]) if hits else None,
            'upstream_flame_rooms':[sorted(v) for v in sources[room]],
            'received_door_jet':(jets[room]>0).tolist(),'physical_room':room,
            'basis':'FGI >= ribbon threshold AND ignition; initial origin excluded; open connected flame-room HRR or received door jet; no exterior path',
            'status':fgi[rid].get('status','evaluated')}
    return _finite(out)


def logic(values,op='and'):
    """Kleene three-valued logic: true OR unknown is true."""
    rows=list(zip(*values))
    if op=='and':return [False if False in row else None if None in row else True for row in rows]
    return [True if True in row else None if None in row else False for row in rows]


def term(key,label,values,threshold,op,unit,source,n):
    if values is None:values=[None]*n
    if np.isscalar(values):values=[values]*n
    th=[threshold]*n if np.isscalar(threshold) else threshold
    met=[];margin=[]
    for v,c in zip(values,th):
        if v is None or c is None:met.append(None);margin.append(None);continue
        met.append(bool({'>=':v>=c,'<':v<c,'>':v>c,'==':v==c}[op]))
        margin.append(None if op=='==' else float(c)-float(v) if op=='<' else float(v)-float(c))
    return {'key':key,'label':label,'value':list(values),'threshold':threshold,'op':op,'unit':unit,
            'source':source,'met':met,'margin':margin}


def phenomenon(t,terms,intensity,met=None,expression=None):
    met=logic([v['met'] for v in terms]) if met is None else met
    hits=[i for i,x in enumerate(met) if x is True]
    duration=sum(float(t[i+1]-t[i]) for i in range(len(t)-1) if met[i] is True)
    raw={k:list(v) for k,v in intensity.items()}
    return {'terms':terms,'all_met':met,'expression':expression or 'AND of terms',
            'first_met_s':float(t[hits[0]]) if hits else None,'duration_s':duration,
            'resolution_s':float(np.max(np.diff(t))) if len(t)>1 else 0,
            'intensity':{k:[v if met[i] is True else None for i,v in enumerate(a)] for k,a in raw.items()},
            'actual_quantities':raw,'duration_basis':'left-endpoint output intervals; no extrapolation after final sample'}


def screening_scores(temperature,fuel,oxygen,n,prior_met=None):
    """Shared, display-only section1.5.5 ratios. Never controls ignition.

    Inputs are (value, threshold, lower_is_risk). The inverse oxygen ratio
    uses a numerical positive floor; stored physical values remain untouched.
    Other zero denominators retain the existing unbounded-ratio semantics.
    """
    factors={};unbounded={};oxygen_floored=[False]*n
    for key,spec in [('temperature',temperature),('fuel',fuel),('oxygen',oxygen)]:
        values=[];infinite=[]
        for j in range(n):
            ratio=None
            if spec is not None:
                value,threshold,reverse=spec
                a=value[j] if not np.isscalar(value) else value
                b=threshold[j] if not np.isscalar(threshold) else threshold
                if a is not None and b is not None and np.isfinite(a) and np.isfinite(b):
                    if key=='oxygen' and reverse and a<OXYGEN_SCORE_FLOOR:
                        a=OXYGEN_SCORE_FLOOR;oxygen_floored[j]=True
                    numerator,denominator=(b,a) if reverse else (a,b)
                    ratio=float(numerator/denominator) if denominator>0 else float('inf') if denominator==0 and numerator>0 else None
            values.append(ratio);infinite.append(ratio==float('inf'))
        factors[key]=values;unbounded[key]=infinite
    score=[];weak=[];strong=[];met=[]
    for j in range(n):
        ratios={k:v[j] for k,v in factors.items()}
        if any(v is None for v in ratios.values()):score.append(None);weak.append(None);strong.append(None);met.append(None)
        else:
            score.append(min(ratios.values()));weak.append(min(ratios,key=ratios.get));strong.append(max(ratios,key=ratios.get))
            met.append(bool(score[-1]>=1))
    return _finite({'factors':factors,'unbounded_factors':unbounded,'degree':score,'weakest':weak,'strongest':strong,
        'all_met':met,'legacy_context_met':prior_met,
        'oxygen_numeric_guard':{'revision':OXYGEN_SCORE_REVISION,'floor':OXYGEN_SCORE_FLOOR,
            'unit':'vol%','applied':oxygen_floored,'scope':'inverse oxygen score only; raw values unchanged'},
        'meaning':'project screening ratios, not occurrence probability; three-factor AND; legacy context stored separately'})


def fo_required_hrr(model,result,room,t):
    """Thomas correlation in kW. Virtual cell openings are not physical vents.

    This is a diagnostic correlation, not a native CFAST ignition criterion.
    For cells, local solver dimensions are an explicit geometric approximation.
    """
    from .openings import realized_fraction
    w,d,h=room['size_m'];area=np.full(len(t),2*(w*d+w*h+d*h),dtype=float);vent=np.zeros(len(t))
    for v in model['openings']:
        if room['id'] not in (v['a'],v['b']) or v.get('virtual_cell_boundary'):continue
        if v.get('type')=='FLOOR':continue
        height=v['top_m']-v.get('bottom_m',0.)
        if height<=0:continue
        try:f=realized_fraction(result,v,t)
        except ValueError:return [None]*len(t)
        opened=v['width_m']*height*f
        area-=opened
        vent+=opened*np.sqrt(height)
    return 7.8*np.maximum(area,0.)+378*vent


def screening_lfl(model,temperature_C):
    """Reuse fire_zone's existing temperature-dependent screening LFL.

    1.4e6, 293 K, 1300 K and clip[.2,1] are the legacy formula, not new
    calibration constants or a measured limit of the actual mixed smoke.
    A mixed-Hc native deck has no unique effective Hc: leave it unknown.
    """
    heats={float(g['heat_of_combustion_kJ_kg'])*1000 for g in model['fuel_groups']}
    if len(heats)!=1 or min(heats)<=0:return [None]*len(temperature_C)
    scale=model.get('condition_scoring',{}).get('LFL0_hrr',1.4e6)
    return scale/next(iter(heats))*np.clip(1-(np.asarray(temperature_C)+273.15-293)/1300,.2,1.)


def evaluate(model,result):
    t=np.asarray(result['time_s']);n=len(t);out={};c=model['criteria'];g=model['gas']
    inventory=result['solid_fuel_inventory'];pools=result.get('room_fuel_pools',{});actual_by_room={};jet_by_room={}
    if not result['rooms']:return out
    for room in model['rooms']:
        rid=room['id'];s=result['rooms'][rid];p=result['phenomena'][rid]
        mass_basis='combustible_mixture_FUEL_plus_actual_CO' if model['gas'].get('mixture_enabled') else 'legacy_FUEL_only'
        temp=np.asarray(s['T_upper_C']);o2=np.asarray(s['o2_upper_vol'])*100
        yf=np.asarray(s.get('combustible_upper_kg',s['fuel_upper_kg']))/np.maximum(s['upper_mass_kg'],1e-12)
        energy=np.asarray(s.get('available_heat_J',s['fuel_upper_J']))/1e6;bulk=np.asarray(s['bulk_HRR_W'])/1000
        groups=[f for f in model['fuel_groups'] if f['room']==rid]
        qa=sum((np.asarray(inventory[f['id']].get('actual_HRR_W',np.zeros(n)))/1000 for f in groups),np.zeros(n))
        own_actual=np.logical_or.reduce([np.asarray(inventory[f['id']].get('actual_HRR_W',np.zeros(n)))>1000 for f in groups]) if groups else np.zeros(n,bool)
        qi=sum((np.asarray(inventory[f['id']].get('prescribed_pyrolysis_kW',np.zeros(n))) for f in groups),np.zeros(n))
        starts=[f['initial_time_s'] for f in groups if 'initial_time_s' in f]+[e.get('prescribed_supply_start_s',e['t_ign_s']) for e in result['ignitions'] if e['room']==rid]
        own=t>=min(starts,default=float('inf'))
        def tr(key,label,value,threshold,op,unit,source):return term(key,label,value,threshold,op,unit,source,n)
        fo={};bd={};fgi={}
        force=model.get('ignition_assumption') or {};forced=(rid==force.get('room'))&(t>=force.get('time_s',float('inf')))&(t<force.get('time_s',float('inf'))+force.get('duration_s',0))
        pilot=bool(g['pilot_assumed'])&(t>=g['pilot_start_s'])&(t<=g['pilot_end_s'])
        ignition=(temp>=g['gas_ignition_C'])|(pilot&(temp>=g['hot_C']))|forced
        gate_o2=np.where(forced,force.get('oxygen_min_vol_percent',10),g['oxygen_min_vol_percent'])
        gt=[tr('enabled','상층 반응 계산 사용',g['enabled'] and g['bulk_enabled'],True,'==','','gas.enabled AND gas.bulk_enabled'),
            tr('Yf','연료 질량분율',yf,g['fuel_min_mass_fraction'],'>=','','gas.fuel_min_mass_fraction'),
            tr('O2','상층 산소',o2,gate_o2,'>=','체적%','gas.oxygen_min_vol_percent / ignition_assumption.oxygen_min_vol_percent'),
            tr('ignition','온도 또는 설정 점화 경로',ignition,True,'==','','gas.gas_ignition_C OR (pilot window AND gas.hot_C) OR forced ignition window')]
        gas_met=logic([v['met'] for v in gt])
        gt += [tr('auto_T','자동착화 경로 온도',temp,g['gas_ignition_C'],'>=','℃','gas.gas_ignition_C'),
               tr('pilot_T','점화원 경로 온도',temp,g['hot_C'],'>=','℃','gas.hot_C'),
               tr('pilot_window','점화원 가정·시간창',pilot,True,'==','','gas.pilot_assumed AND gas.pilot_start_s..pilot_end_s'),
               tr('forced_window','강제 점화 가정·시간창',forced,True,'==','','ignition_assumption.room / time_s / duration_s')]
        upper=phenomenon(t,gt,{'Q_bulk_kW':bulk,'cumulative_bulk_MJ':np.r_[0,np.cumsum(np.diff(t)*(bulk[:-1]+bulk[1:])/2)]/1000},
                         gas_met,'enabled AND fuel AND oxygen AND (auto_T OR (pilot_T AND pilot_window) OR forced_window)')
        upper['ignition_context']={'autoignition_C':g['gas_ignition_C'],'pilot_hot_C':g['hot_C'],
            'pilot_assumed':g['pilot_assumed'],'pilot_start_s':g['pilot_start_s'],'pilot_end_s':g['pilot_end_s'],
            'forced_window':forced,'scope':'sampled extension gates only; not native plume combustion or proof of rollover'}
        if g.get('mixture_smooth_enabled'):
            upper['ignition_context']['reaction_transition']={
                'mode':'one_sided_C1_with_shared_mixing_limited_rate',
                'oxygen_width_percentage_points':100*g['mixture_o2_width_vol'],
                'temperature_width_C':g['mixture_temperature_width_C'],
                'fuel_mass_fraction_width':g['mixture_fuel_width'],
                'mixing_time_s':g['mixture_mixing_time_s'],
                'rate_cap_s_inv':1/g['mixture_mixing_time_s'],
                'scope':'threshold separate from reaction; fixed mixing-horizon native stock reservation; widths and mixing time are project assumptions'}
        rapid=phenomenon(t,[tr('rate','상층 온도 상승률',p['temperature_rate_C_s'],c['rapid_C_s'],'>=','℃/s','criteria.rapid_C_s')],{'rise_C_s':p['temperature_rate_C_s']})
        out[rid]={'fo':fo,'backdraft':bd,'fgi':fgi,'upper_gas':upper,'rapid':rapid,
                  'context':{'mass_basis':mass_basis,'T_upper_C':temp,'oxygen_upper_vol_percent':o2,'incoming_fuel_kg_s':p['fuel_in_kg_s'],
                  'Q_bulk_kW':bulk,'Q_vent_kW':np.asarray(p['vent_HRR_W'])/1000}}
        lower=s.get('o2_lower_vol')
        if lower is None:
            lower=result.get('zone',{}).get('LLO2_'+str(model['rooms'].index(room)+1))
        lower=[None]*n if lower is None else np.asarray(lower)*100
        required=fo_required_hrr(model,result,room,t)
        # Prefer the explicitly mapped receiving-room total. Stock DJET is
        # already a receiving-compartment sum; do not add directional rows again.
        received=s.get('received_door_jet_HRR_W')
        if received is None:
            received=result.get('zone',{}).get('DJET_'+str(model['rooms'].index(room)+1))
        if received is None:received=p['vent_HRR_W']
        actual_by_room[rid]=qa+bulk;jet_by_room[rid]=np.asarray(received)/1000
        from .criteria import evaluate_cell, opening_increases
        parent=room.get('parent_room',rid)
        siblings={r['id'] for r in model['rooms'] if r.get('parent_room',r['id'])==parent}
        parent_heat=sum((np.asarray(inventory[f['id']].get('actual_HRR_W',np.zeros(n))) for f in model['fuel_groups'] if f['room'] in siblings),np.zeros(n))/1000
        shared=evaluate_cell(model,room,t,temp,s.get('interface_m'),o2,yf,qa,bulk,
            np.asarray(received)/1000,p.get('floor_incident_flux_kW_m2'),own_fire=parent_heat,
            opening_increased=opening_increases(model,room,t,result))
        shared['FO']['diagnostics']={'Thomas_required_kW':required,'label':'셀·대공간에서는 무효인 진단값; 근접도에 미사용'}
        shared['FGI']['rollover']=shared['rollover']
        out[rid].update(fo=shared['FO'],fgi=shared['FGI'],backdraft=shared['backdraft'],rollover=shared['rollover'])
        upper['scores']=screening_scores((temp,g['gas_ignition_C'],False),(yf,g['fuel_min_mass_fraction'],False),
            (o2,g['oxygen_min_vol_percent'],False),n,upper['all_met'])
    rollovers=rollover_states(model,t,{rid:out[rid]['fgi'] for rid in actual_by_room},actual_by_room,jet_by_room,result)
    for rid,record in rollovers.items():out[rid]['fgi']['remote_ignition_condition']=record
    out['_groups']={}
    for f in model['fuel_groups']:
        views=[v for v in result['candidates'] if v['group']==f['id'] and v.get('status')=='ok']
        surfaces=[];flux=[]
        for i in range(n):
            valid=[v for v in views if v['surface_C'][i] is not None]
            v=max(valid,key=lambda v:v['surface_C'][i]) if valid else None
            surfaces.append(v['surface_C'][i] if v else None);flux.append(v['q_inc_kW_m2'][i] if v else None)
        event=next((e for e in result['ignitions'] if e['group']==f['id']),None)
        at=event['t_ign_s'] if event else f.get('initial_time_s',float('inf'))
        pooled=pools.get(f['room'],{}).get('time_s',float('inf'))
        mat=views[0]['material'] if views else model['material']
        terms=[term('surface','후보면 표면 온도',surfaces,mat['ignition_C'],'>=','℃','candidate.material.ignition_C',n),
               term('inactive','미착화·FO 통합 전 연료',t<min(at,pooled),True,'==','','executed ignition/FO schedule',n),
               term('pilot','점화원 가정',mat['pilot']!='none',True,'==','','candidate.material.pilot',n)]
        record=phenomenon(t,terms,{'q_inc_kW_m2':flux})
        record.update(room=f['room'],state=['fo_pool' if x>=pooled else 'active' if x>=at else 'inactive' for x in t],
                      ignition_s=None if not np.isfinite(at) else at,cause=event.get('largest_incident_term') if event else None)
        from .combustion_display import group_display
        record.update(group_display(result.get('solid_fuel_inventory',{}).get(f['id'],{}),t,at))
        out['_groups'][f['id']]=record
    vent_series={};time_index={float(x):i for i,x in enumerate(t)}
    ids=[r['id'] for r in model['rooms']]+['OUTSIDE']
    for row in result['directional_vent_reactions']:
        key=(int(row['vent_index']),int(row['room_from']),int(row['room_to']))
        if key not in vent_series:
            vent_series[key]={'vent':model['openings'][key[0]-1]['id'],'from':ids[key[1]-1],
                              'to':ids[key[2]-1],'Q_kW':np.zeros(n),'basis':'native per-vent directional reaction'}
        vent_series[key]['Q_kW'][time_index[float(row['time_s'])]]+=row['HRR_W']/1000
    out['_vents']=list(vent_series.values())
    return _finite(out)


def _finite(value):
    if isinstance(value,np.ndarray):return _finite(value.tolist())
    if isinstance(value,np.generic):return _finite(value.item())
    if isinstance(value,dict):return {k:_finite(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [_finite(v) for v in value]
    if isinstance(value,float) and not np.isfinite(value):return None
    return value
