"""Condition diagnostics only. Never feeds back into ignition or native combustion."""
import numpy as np
from collections import deque
from copy import deepcopy

ROLLOVER_REVISION = 'fgi_path_ignition_v1'

def rollover_records(model, t, fgi, actual_hrr, received_jet, result=None):
    """Display only: FGI degree × route gate × ignition gate.

    Collapse solver cells to physical rooms. Use all equal-length shortest
    paths to every exterior-aperture room; upstream means an immediate
    predecessor on one of those shortest paths. No heat/oxygen is added.
    """
    from .openings import realized_fraction
    t=np.asarray(t);n=len(t);result=result or {'time_s':t}
    ids={r['id'] for r in model['rooms']}
    physical={r['id']:r.get('parent_room',r['id']) for r in model['rooms']}
    origins={physical[g['room']] for g in model.get('fuel_groups',[]) if 'initial_time_s' in g and g['room'] in physical}
    cfg=model.get('condition_scoring',{})
    include=cfg.get('rollover_include_origin',True)
    use_open=cfg.get('rollover_open_only',True)
    if not isinstance(include,bool) or not isinstance(use_open,bool):raise ValueError('Rollover settings must be boolean')
    edges=[]
    for v in model.get('openings',[]):
        a,b=v['a'],v['b']
        if a not in ids and b not in ids:continue
        if a not in ids and a!='OUTSIDE' or b not in ids and b!='OUTSIDE':continue
        x,y=physical.get(a,a),physical.get(b,b)
        if x==y:continue
        fraction=realized_fraction(result,v,t) if use_open else np.ones(n)
        edges.append((x,y,np.asarray(fraction)>0))
    nodes=set(physical.values());heat={r:np.zeros(n) for r in nodes};jets={r:np.zeros(n) for r in nodes}
    for rid in ids:
        q=actual_hrr.get(rid)
        if q is not None:heat[physical[rid]]+=np.asarray(q)
        if received_jet.get(rid) is not None:jets[physical[rid]]+=np.asarray(received_jet[rid])
    path={r:np.zeros(n,bool) for r in nodes};pilot={r:np.zeros(n,bool) for r in nodes}
    prevs={r:[[] for _ in t] for r in nodes}
    for j in range(n):
        adj={r:set() for r in nodes};exterior=set()
        for a,b,on in edges:
            if not on[j]:continue
            if a=='OUTSIDE':exterior.add(b)
            elif b=='OUTSIDE':exterior.add(a)
            else:adj[a].add(b);adj[b].add(a)
        predecessors={r:set() for r in nodes};on_path=set()
        for origin in sorted(origins):
            distance={origin:0};queue=deque([origin])
            while queue:
                a=queue.popleft()
                for b in adj[a]:
                    if b not in distance:distance[b]=distance[a]+1;queue.append(b)
            pending=list(exterior.intersection(distance));seen=set(pending)
            while pending:
                x=pending.pop();on_path.add(x)
                for p in adj[x]:
                    if distance.get(p)==distance[x]-1:
                        predecessors[x].add(p)
                        if p not in seen:seen.add(p);pending.append(p)
        for r in nodes:
            path[r][j]=r in on_path and (include or r not in origins)
            prevs[r][j]=sorted(predecessors[r])
            pilot[r][j]=any(heat[p][j]>0 for p in predecessors[r]) or (include and r in origins and heat[r][j]>0)
    out={}
    for rid in ids:
        r=physical[rid];score=deepcopy(fgi[rid]['scores']);base=score['degree']
        jet=jets[r]>0
        ignition=pilot[r]|jet
        degree=[None if v is None else float(v)*int(path[r][j])*int(ignition[j]) for j,v in enumerate(base)]
        score.update(degree=degree,all_met=[None if v is None else v>=1 for v in degree],
                     meaning='FGI index × shortest exterior-path condition × upstream fire/received jet condition; not probability')
        terms=deepcopy(fgi[rid].get('terms',[]))
        terms += [term('path','화점→외기 최단 경로',path[r],True,'==','','saved opening graph',n),
                  term('ignition','상류 연소 또는 수신 분출',ignition,True,'==','','actual HRR > 0 / receiving door jet > 0',n)]
        record=phenomenon(t,terms,{},score['all_met'],'FGI score × path × ignition')
        record.update(scores=score,status=fgi[rid].get('status','evaluated'),label='롤오버 가능 조건',
            score_basis={'revision':ROLLOVER_REVISION,'rollover_include_origin':include,'rollover_open_only':use_open,
                         'physical_room':r,'origins':sorted(origins),'path':path[r].tolist(),'ignition':ignition.tolist(),
                         'upstream_rooms':prevs[r],'received_door_jet':jet.tolist(),
                         'FGI_degree':list(base),'path_basis':'all equal-hop shortest paths; physical rooms; positive effective opening',
                         'origin_ignition':'own actual HRR when include_origin=true'})
        out[rid]=record
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

    Inputs are (value, threshold, lower_is_risk). Zero denominator is retained
    as an unbounded ratio, not a fabricated finite cap.
    """
    factors={};unbounded={}
    for key,spec in [('temperature',temperature),('fuel',fuel),('oxygen',oxygen)]:
        values=[];infinite=[]
        for j in range(n):
            ratio=None
            if spec is not None:
                value,threshold,reverse=spec
                a=value[j] if not np.isscalar(value) else value
                b=threshold[j] if not np.isscalar(threshold) else threshold
                if a is not None and b is not None and np.isfinite(a) and np.isfinite(b):
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
        temperature=tr('Tu','상층 온도',temp,c['fo_temperature_C'],'>=','℃','criteria.fo_temperature_C')
        ft=[tr('own_fire','활성 화원',own,True,'==','','executed fire schedule'),temperature]
        met=temperature['met']
        if model['flashover']['criterion']=='temperature_or_flux':
            flux=tr('floor_flux','바닥 입사열',p['floor_incident_flux_kW_m2'],c['fo_flux_kW_m2'],'>=','kW/㎡','criteria.fo_flux_kW_m2')
            ft.append(flux);met=logic([met,flux['met']],'or')
        met=logic([ft[0]['met'],met])
        fo=phenomenon(t,ft,{'over_C':temp-c['fo_temperature_C'],'Q_actual_kW':qa,
                           'actual_to_supply':np.divide(qa,qi,out=np.full(n,np.nan),where=qi>0)},met,
                      'own_fire AND (temperature OR evaluated floor flux)' if len(ft)==3 else 'own_fire AND temperature')
        bd=phenomenon(t,[tr('Yf','연료 질량분율',yf,c['fuel_rich_mass_fraction'],'>=','','criteria.fuel_rich_mass_fraction'),
            tr('Tu','상층 온도',temp,c['hot_C'],'>=','℃','criteria.hot_C'),
            tr('O2','상층 산소',o2,c['oxygen_deficient_vol_percent'],'<','체적%','criteria.oxygen_deficient_vol_percent')],
            {'fuel_energy_MJ':energy,'fuel_mass_kg':s.get('combustible_upper_kg',s['fuel_upper_kg'])})
        # Preserve legacy FGI_POTENTIAL exactly. Screening settings are not the
        # extension reaction gates, and need no invented autoignition condition.
        fgi=phenomenon(t,[tr('Yf','연료 질량분율',yf,c['fgi_fuel_mass_fraction'],'>=','','criteria.fgi_fuel_mass_fraction'),
            tr('O2','상층 산소',o2,c['fgi_oxygen_vol_percent'],'>=','체적%','criteria.fgi_oxygen_vol_percent'),
            tr('no_solid','실제 고체 발열 >1kW 없음',~own_actual,True,'==','','legacy classify own_fire'),
            tr('no_bulk','현재 상층 추가연소 없음',np.asarray(s['bulk_HRR_W'])<=1e-6,True,'==','','legacy classify reaction diagnostic')],
            {'fuel_energy_MJ':energy,'Q_bulk_kW':bulk},list(map(bool,p['tags']['FGI_POTENTIAL'])))
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
        fo['scores']=screening_scores((temp,c['fo_temperature_C'],False),(qa+bulk,required,False),
            (lower,g['oxygen_min_vol_percent'],False),n,fo['all_met'])
        fo['score_basis']={'Q_required_kW':required,'formula':'7.8*A_internal+378*sum(A_open*sqrt(H))',
            'assumption':True,'internal_area':'bounding surfaces minus effective open area',
            'oxygen_source':'lower layer, gas.oxygen_min_vol_percent',
            'limits':'local solver-cell geometry; virtual vents excluded; not a validated FO prediction'}
        from .fo_hrr import apply_fo_hrr
        # Prefer the explicitly mapped receiving-room total. Stock DJET is
        # already a receiving-compartment sum; do not add directional rows again.
        received=s.get('received_door_jet_HRR_W')
        if received is None:
            received=result.get('zone',{}).get('DJET_'+str(model['rooms'].index(room)+1))
        if received is None:received=p['vent_HRR_W']
        apply_fo_hrr(fo,qa+bulk,np.asarray(received)/1000,required)
        actual_by_room[rid]=qa+bulk;jet_by_room[rid]=np.asarray(received)/1000
        lfl=screening_lfl(model,temp)
        fgi['scores']=screening_scores((temp,g['hot_C'],False),(yf,lfl,False),
            (o2,c['fgi_oxygen_vol_percent'],False),n,fgi['all_met'])
        fgi['score_basis']={'assumption':True,'temperature':'gas.hot_C','fuel_threshold':lfl,
            'fuel_formula':'legacy fire_zone LFL0_hrr/Hc*clip(1-(T_K-293)/1300,.2,1)',
            'limits':'effective-fuel screening approximation; mixed-Hc inputs unknown; legacy boolean unchanged'}
        bd['scores']=screening_scores((temp,c['hot_C'],False),(yf,c['fuel_rich_mass_fraction'],False),
            (o2,c['oxygen_deficient_vol_percent'],True),n,bd['all_met'])
        upper['scores']=screening_scores((temp,g['gas_ignition_C'],False),(yf,g['fuel_min_mass_fraction'],False),
            (o2,g['oxygen_min_vol_percent'],False),n,upper['all_met'])
    rollovers=rollover_records(model,t,{rid:out[rid]['fgi'] for rid in actual_by_room},actual_by_room,jet_by_room,result)
    for rid,record in rollovers.items():out[rid]['rollover']=record
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
