"""L1 section 1.4 sampling and reporting. No changes to thermal equations."""
from copy import deepcopy
import math
import numpy as np

DEFAULT_PROBABILITIES={'fire_door':.2,'ordinary_door':.5,'operable_window':.3,'fixed_window':0.}
KNOWN_BIAS=('간략 엔진은 CFAST보다 후반 상층 온도가 낮고(단독 화원 −14~−20 %), '
            '전이는 CFAST 표준보다 공격적이고 CFAST 공격 프리셋보다 늦다. '
            '탐색용이며 최종 확인은 CFAST(r8)로 한다.')
BIAS_SCOPE='위 편차 방향과 수치는 검토한 기준 사례의 결과이며 모든 개폐 조합에 대한 보증이 아니다.'

def opening_class(v):
    kind=v.get('kind','').lower()
    if v.get('virtual_cell_boundary') or kind=='cell_boundary':return 'virtual'
    if v.get('fire_door') or v.get('door_type') in ('fire','fire_door') or v.get('fire_rating_minutes',0)>0:return 'fire_door'
    if 'window' in kind or v.get('is_window'):
        if v.get('fixed_window') or v.get('openable') is False or v.get('window_type') in ('fixed','FIX') or 'fixed' in kind:return 'fixed_window'
        return 'operable_window'
    if kind=='open_passage':return 'permanent_open'
    if 'door' in kind:return 'ordinary_door'
    raise ValueError('Unclassified opening: '+v['id'])

def make_samples(raw,seed=20261025,count=20,probabilities=None,mode='bernoulli',fixed_states=None):
    if count<2:raise ValueError('Two mandatory samples required')
    if mode not in ('bernoulli','fixed_count'):raise ValueError('Unknown sampling mode')
    probs={**DEFAULT_PROBABILITIES,**(probabilities or {})};fixed=fixed_states or {}
    if set(probs)!=set(DEFAULT_PROBABILITIES) or any(isinstance(v,bool) or not math.isfinite(v) or not 0<=v<=1 for v in probs.values()):raise ValueError('Invalid probabilities')
    vents=sorted(raw['openings'],key=lambda v:v['id'])
    if len({v['id'] for v in vents})!=len(vents):raise ValueError('Duplicate opening IDs')
    if set(fixed)-{v['id'] for v in vents} or any(type(x) is not bool for x in fixed.values()):raise ValueError('Invalid fixed opening states')
    classes={v['id']:opening_class(v) for v in vents}
    if any(classes[k] in ('permanent_open','virtual') and not state for k,state in fixed.items()):
        raise ValueError('Permanent passages and virtual cell boundaries must remain open')
    inferred={v['id'] for v in vents if classes[v['id']]=='fire_door' and v.get('door_class_confidence')=='inferred'}
    samples=[]
    for index in range(count):
        rng=np.random.default_rng(np.random.SeedSequence([seed,index]))
        kind=['all_fire_doors_open','all_openings_closed'][index] if index<2 else 'random'
        states={}
        for group,p in probs.items():
            ids=[v['id'] for v in vents if classes[v['id']]==group and v['id'] not in fixed]
            if mode=='fixed_count':
                total=sum(classes[v['id']]==group for v in vents)
                locked_open=sum(value and classes[i]==group for i,value in fixed.items())
                k=int(math.floor(total*p+.5))-locked_open
                if not 0<=k<=len(ids):raise ValueError('Fixed states conflict with fixed_count target: '+group)
                chosen=set(rng.choice(ids,size=k,replace=False).tolist()) if k else set()
                states.update({i:i in chosen for i in ids})
            else:states.update({i:bool(rng.random()<(.35 if i in inferred else p)) for i in ids})
        for v in vents:
            i=v['id'];c=classes[i]
            if c in ('permanent_open','virtual'):states[i]=True
            if kind=='all_fire_doors_open' and c=='fire_door':states[i]=True
            if kind=='all_openings_closed' and c not in ('virtual','permanent_open'):states[i]=False
            if i in fixed:states[i]=fixed[i]
        model=deepcopy(raw);model['room_rule_r8']={'preset':'standard','room_supply':'item_peak'}
        model['duration_s']=raw.get('duration_s',3600)
        if model['duration_s'] not in (1800,3600):raise ValueError('MC horizon must be 30 or 60 minutes')
        combinations=[]
        for v in model['openings']:
            c=classes[v['id']];opened=states[v['id']]
            fraction=(.5 if c.endswith('window') else 1.) if opened else 0.
            v['schedule']=[[0.,fraction]]
            combinations.append({'id':v['id'],'class':c,'a':v['a'],'b':v['b'],
                'open':opened,'effective_fraction':fraction,'fixed':v['id'] in fixed,
                'probability':.35 if v['id'] in inferred else probs.get(c),
                'door_class_basis':v.get('door_class_basis'),'door_class_confidence':v.get('door_class_confidence')})
        samples.append({'id':f'S{index:02d}','kind':kind,'seed':seed,'seed_index':index,'rng':'numpy.PCG64/SeedSequence[seed,index]',
            'mode':mode,'probabilities':probs,'fixed_states':fixed,'scenario':model,'openings':combinations,
            'limits':['미분류 창은 개폐창, 미분류 문은 일반문으로 취급한다.',
                '고정 개구부 지정을 우선하며 극단 표본과 충돌하면 실제 조합을 그대로 기록한다.',
                '모든 개구부 닫힘은 개폐 가능한 문·창을 뜻한다. 영구 통로와 가상 셀 경계는 항상 열린다.',
                '창 개방 유효면적은 50%; 초기 상태 고정, 창 파괴 OFF. 기존 r8 공급 상한 가정은 유지한다.',
                '재실자의 개폐는 열림 확률로 대체. 이 확률은 입력 조합 분포이며 화재 발생 확률이 아니다.']})
    return samples

def intervals(mask,t):
    out=[];start=None
    for j,flag in enumerate(mask):
        if flag and start is None:start=j
        if start is not None and (not flag or j==len(mask)-1):
            end=j if flag else j-1
            out.append({'start_sample_s':float(t[start]),'end_sample_s':float(t[end]),
                        'duration_lower_bound_s':float(t[end]-t[start])});start=None
    return out

def condition_summary(model,result,sample):
    t=model.sol.t;ys=model.sol.y;n=model.N
    originals=sorted({r['original_room'] for r in result['room_summary']})
    mapping={room:[i for i,r in enumerate(result['room_summary']) if r['original_room']==room] for room in originals}
    phenomena={}
    for title,key in [('FO','flash'),('FGI','fgi'),('backdraft','backdraft'),('untenable','unten')]:
        if title in ('FGI','backdraft') and not result.get('gas_conditions_evaluable',False):
            phenomena[title]={'status':'not_evaluated','ever_room_count':None,'first_s':None,
                'reason':'upper unburned fuel reaction not enabled'}
            continue
        flags=np.asarray(result['flags'][key],bool)
        flags_by_room={room:np.any(flags[ix],axis=0) for room,ix in mapping.items()}
        affected={room:float(t[np.flatnonzero(mask)[0]]) for room,mask in flags_by_room.items() if mask.any()}
        phenomena[title]={'status':'evaluated','ever_room_count':len(affected),'first_s':min(affected.values(),default=None),
            'rooms':affected,'max_simultaneous_room_count':int(np.stack(list(flags_by_room.values())).sum(axis=0).max())}
    if 'shared_conditions' in result:
        for name in ('FO','FGI','backdraft','untenable'):
            records=result['shared_conditions']['rooms']
            if any(records[r['cell']][name]['status']=='not_evaluated' for r in result['room_summary']):
                phenomena[name]={'status':'not_evaluated','ever_room_count':None,'first_s':None,'score_median':None,'score_max':None}
                continue
            by_room={};scores=[]
            for room,ix in mapping.items():
                masks=[]
                for i in ix:
                    rec=records[result['room_summary'][i]['cell']][name]
                    masks.append(np.array([v is True for v in rec.get('scores',{}).get('all_met',rec['all_met'])]))
                    scores.extend(v for v in rec['scores']['degree'] if v is not None and np.isfinite(v))
                by_room[room]=np.any(masks,axis=0)
            hit={room:float(t[np.flatnonzero(mask)[0]]) for room,mask in by_room.items() if mask.any()}
            phenomena[name]={'status':'evaluated','basis':'shared conditions.py','ever_room_count':len(hit),
                'rooms':hit,'first_s':min(hit.values(),default=None),
                'max_simultaneous_room_count':int(np.stack(list(by_room.values())).sum(axis=0).max()),
                'score_median':float(np.median(scores)) if scores else None,'score_max':max(scores,default=None),
                'score_basis':'finite cell-time T/F/O scores; missing factor stays unknown'}
    threshold=model.manifest['rule_settings']['values']['temperature_C']
    room_rows=[]
    for room,ix in mapping.items():
        temp=max(result['room_summary'][i]['upper_max_C'] for i in ix)
        room_rows.append({'room':room,'upper_max_C':temp,'boundary':abs(temp-threshold)<=30,
            'inter_room_threshold_C':threshold,'boundary_halfwidth_C':30})
    cell_rows=[{'cell':r['cell'],'original_room':r['original_room'],'upper_max_C':r['upper_max_C'],
                'boundary':abs(r['upper_max_C']-threshold)<=30} for r in result['room_summary']]
    opening_risk=None
    if sample['kind']=='all_openings_closed' and result.get('gas_conditions_evaluable',False):
        hot=model.input_model.get('gas',{}).get('hot_C')
        if hot is None:opening_risk={'status':'not_evaluated','reason':'No configured hot_C'}
        else:
            tu=ys[2*n:3*n]-273.15;oxygen=ys[4*n:5*n]*29/32;fuel=ys[6*n:7*n]
            flags=(fuel>=model.P['Yf_backdraft'])&(oxygen<model.P['LOC'])&(tu>=hot)
            opening_risk={'status':'evaluated','thresholds':{'fuel_mass_fraction':model.P['Yf_backdraft'],
                'oxygen_vol_fraction_below':model.P['LOC'],'upper_C_at_least':hot},
                'threshold_sources':{'fuel':'legacy Yf_backdraft','oxygen':'legacy LOC','hot':'input gas.hot_C'},
                'rooms':{room:intervals(np.any(flags[ix],axis=0),t) for room,ix in mapping.items()},
                'meaning':'opening-risk conditions in closed-state calculation; opening/ignition itself not simulated'}
    return {'sample_id':sample['id'],'kind':sample['kind'],'complete':bool(result['ok']),
        'safe_end_s':float(t[-1]),'phenomena':phenomena,'room_boundaries':room_rows,'cell_boundaries':cell_rows,
        'boundary_room_count':sum(r['boundary'] for r in room_rows),'original_room_count':len(room_rows),
        'boundary_cell_count':sum(r['boundary'] for r in cell_rows),'opening_risk':opening_risk,
        'burning_original_rooms':sorted({r['original_room'] for r in result['room_summary'] if r['actual_peak_kW']>0}),
        'known_bias':KNOWN_BIAS,'bias_scope':BIAS_SCOPE}

def output_balance_diagnostic(model):
    from .core import P0,RG,CP
    t=model.sol.t;ys=model.sol.y;n=model.N
    mass=[];energy=[];mr=[];er=[];mi=[];ei=[]
    for j,ts in enumerate(t):
        y=ys[:,j];d=model.rhs(float(ts),model.sol.y[:,j],diag=True)
        vu=np.clip(y[n:2*n],model.Vmin,model.Va-model.Vmin);vl=model.Va-vu
        tu=np.maximum(y[2*n:3*n],200);tl=np.maximum(y[3*n:4*n],200)
        mass.append(float(np.sum(P0/RG*(vu/tu+vl/tl))))
        wall_offset=8*n+(0 if model.P.get('remove_cumulative_state') else 1)
        energy.append(float(np.sum(P0/RG*(CP-RG)*model.Va))+float(np.sum(y[wall_offset:].reshape(n,3)*model.finite_walls.capacity)))
        mr.append(d['boundary_mass_in']-d['boundary_mass_out']+d['pyro_mass_rate'])
        er.append(d['boundary_enthalpy_in']-d['boundary_enthalpy_out']+d['Q']+CP*model.P['T_pyro']*d['pyro_mass_rate']-d['wall_back_W'])
        mi.append(d['boundary_mass_in']+d['pyro_mass_rate']);ei.append(d['boundary_enthalpy_in']+d['Q']+CP*model.P['T_pyro']*d['pyro_mass_rate'])
    def cum(x):return np.r_[0.,np.cumsum((np.asarray(x)[1:]+np.asarray(x)[:-1])*.5*np.diff(t))]
    m=float(np.max(np.abs(np.asarray(mass)-mass[0]-cum(mr))/np.maximum(mass[0],cum(mi)))*100)
    e=float(np.max(np.abs(np.asarray(energy)-energy[0]-cum(er))/np.maximum(energy[0],cum(ei)))*100)
    return {'basis':'10s output diagnostic; not accepted-step conservation certification','mass_percent':m,'energy_percent':e,
        'limits_percent':{'mass':None,'energy':.1},'passed':bool(model.sol.success and e<=.1),
        'mass_interpretation':'report only per section1.5; output quadrature vs model closure error not isolated'}

def aggregate(summaries):
    complete=[s for s in summaries if s.get('complete')]
    random=[s for s in complete if s['kind']=='random']
    rates={};worst={};room_rates={}
    for name in ('FO','FGI','backdraft'):
        if any(name not in s['phenomena'] or s['phenomena'][name].get('status','evaluated')=='not_evaluated' for s in complete):
            rates[name]={'status':'not_evaluated','fraction':None};worst[name]=None;room_rates[name]=None;continue
        rates[name]={'numerator':sum(s['phenomena'][name]['ever_room_count']>0 for s in random),
            'denominator_completed_random':len(random),'fraction':sum(s['phenomena'][name]['ever_room_count']>0 for s in random)/len(random) if random else None}
        medians=[s['phenomena'][name].get('score_median') for s in random if s['phenomena'][name].get('score_median') is not None]
        maxima=[s['phenomena'][name].get('score_max') for s in random if s['phenomena'][name].get('score_max') is not None]
        rates[name].update(median_of_sample_medians=float(np.median(medians)) if medians else None,
                          maximum_score=max(maxima,default=None))
        room_ids=sorted({r['room'] for s in random for r in s.get('room_boundaries',[])})
        room_rates[name]={room:{'numerator':sum(room in s['phenomena'][name].get('rooms',{}) for s in random),
             'denominator':len(random),'fraction':sum(room in s['phenomena'][name].get('rooms',{}) for s in random)/len(random)} for room in room_ids}
        ranked=sorted(complete,key=lambda s:(-s['phenomena'][name]['ever_room_count'],s['phenomena'][name]['first_s'] if s['phenomena'][name]['first_s'] is not None else float('inf'),s['sample_id']))
        if ranked and ranked[0]['phenomena'][name]['ever_room_count']:
            best=ranked[0];worst[name]={'sample_id':best['sample_id'],'kind':best['kind'],
                'output_diagnostic_passed':best.get('balance_diagnostic',{}).get('passed'),**best['phenomena'][name]}
        else:worst[name]={'status':'none_in_completed_samples','sample_id':None}
    pairden=sum(s['original_room_count'] for s in random);pairnum=sum(s['boundary_room_count'] for s in random)
    return {'attempted':len(summaries),'completed':len(complete),'failed_or_incomplete':len(summaries)-len(complete),
        'failure_fraction':(len(summaries)-len(complete))/len(summaries) if summaries else None,
        'random_completed':len(random),'random_attempted':sum(s['kind']=='random' for s in summaries),
        'mandatory_completed':len(complete)-len(random),'condition_sample_rates_random_only':rates,
        'condition_rates_by_original_room_random_only':room_rates,
        'worst_including_mandatory':worst,'boundary_room_sample_pairs':{'numerator':pairnum,'denominator':pairden,'fraction':pairnum/pairden if pairden else None},
        'samples_with_boundary_fraction_random':sum(s['boundary_room_count']>0 for s in random)/len(random) if random else None,
        'output_diagnostic_failures':[s['sample_id'] for s in complete if not s.get('balance_diagnostic',{}).get('passed',False)],
        'ratio_meaning':'completed random input samples only; not real-world fire probability. Mandatory cases and failures are reported separately.',
        'known_bias':KNOWN_BIAS,'bias_scope':BIAS_SCOPE}
