"""v6 cheap candidate ranking and deterministic scenario comparisons; no solver here."""
from copy import deepcopy
import json,math,time
from pathlib import Path
import numpy as np
from .door_classification import classify_doors
from .montecarlo import opening_class

CONFIG=Path(__file__).with_name('screening_settings.json')
FACTORS=('fuel','ventilation_restriction','connectivity','passage_adjacency','fire_isolation')
REVERSE={'ventilation_restriction','fire_isolation'}

def settings(overrides=None):
    c=json.loads(CONFIG.read_text('utf-8'))
    for key,value in (overrides or {}).items():
        if key not in ('weights','probabilities','fixed_states'):raise ValueError('Unknown screening option '+key)
        c[key]={**c[key],**value}
    if set(c['weights'])!=set(FACTORS) or any(isinstance(v,bool) or not math.isfinite(v) or v<0 for v in c['weights'].values()) or not sum(c['weights'].values()):
        raise ValueError('Five finite nonnegative weights required')
    if any(isinstance(v,bool) or not math.isfinite(v) or not 0<=v<=1 for v in c['probabilities'].values()):raise ValueError('Invalid opening probability')
    if any(type(v) is not bool for v in c['fixed_states'].values()):raise ValueError('Fixed opening states must be boolean')
    return c

def validate_n(value,total):
    if type(value) is not int or not 1<=value<=total:raise ValueError(f'N must be an integer from 1 to {total}')
    return value

def area(r):return float(r.get('area_m2',math.prod(r['size_m'][:2])))
def name(r):return r.get('name') or ' / '.join(r.get('cad_names',[])) or r['id']

def representative_openings(raw,c,door_overrides=None):
    model,classification=classify_doors(raw,door_overrides)
    if set(c['fixed_states'])-{v['id'] for v in model['openings']}:raise ValueError('Unknown fixed opening ID')
    rows=[]
    for v in model['openings']:
        cls=opening_class(v);prob_key='inferred_fire_door' if cls=='fire_door' and v.get('door_class_confidence')=='inferred' else cls
        p=c['probabilities'].get(prob_key)
        opened=True if cls in ('virtual','permanent_open') else p>=.5
        if v['id'] in c['fixed_states']:
            opened=c['fixed_states'][v['id']]
            if not opened and cls in ('virtual','permanent_open'):raise ValueError('Permanent opening cannot be closed')
        fraction=(.5 if cls.endswith('window') else 1.) if opened else 0.
        v['schedule']=[[0.,fraction]]
        rows.append({'id':v['id'],'a':v['a'],'b':v['b'],'class':cls,'probability':p,'open':opened,
            'effective_fraction':fraction,'fixed':v['id'] in c['fixed_states'],
            'classification_rule':v.get('door_class_basis'),'classification_reason':v.get('door_class_reason')})
    return model,rows,classification

def score(raw,top_n=None,options=None,door_overrides=None):
    started=time.perf_counter();c=settings(options)
    model,openings,classification=representative_openings(raw,c,door_overrides)
    rooms={r['id']:r for r in model['rooms']};areas={rid:area(r) for rid,r in rooms.items()}
    adjacency={rid:set() for rid in rooms};all_doors={rid:[] for rid in rooms};direct={rid:set() for rid in rooms}
    for v in model['openings']:
        a,b=v['a'],v['b'];cls=opening_class(v)
        if a not in rooms or b not in rooms:continue
        if cls in ('ordinary_door','fire_door','permanent_open'):
            direct[a].add(b);direct[b].add(a)
            if cls!='permanent_open':all_doors[a].append(v);all_doors[b].append(v)
            if v['schedule'][0][1]>0:adjacency[a].add(b);adjacency[b].add(a)
    passage={rid for rid,r in rooms.items() if r.get('fuel_default',{}).get('usage') in ('passage','corridor','lobby','hall') or r.get('core_kind') in ('corridor','lobby')}
    rows=[]
    for rid,r in rooms.items():
        fuels=[g for g in model['fuel_groups'] if g['room']==rid];energy=sum(g['energy_MJ'] for g in fuels)
        vent_sum=sum(v['width_m']*max(v['top_m']-v.get('bottom_m',0),0)**1.5 for v in model['openings'] if rid in (v['a'],v['b']) and v.get('type','WALL')=='WALL')
        reached=set(adjacency[rid])
        for neighbor in adjacency[rid]:reached.update(adjacency[neighbor])
        reached.discard(rid)
        doors=all_doors[rid];isolation=sum(opening_class(v)=='fire_door' for v in doors)/len(doors) if doors else 0.
        eligible=bool(fuels and energy/areas[rid]>=50 and r.get('core_kind') not in ('stair','elev','elevator','shaft'))
        rows.append({'room':rid,'name':name(r),'area_m2':areas[rid],'volume_m3':math.prod(r['size_m']),
            'eligible':eligible,'excluded_reason':None if eligible else 'no fire fuel, load below50MJ/m2, or circulation core',
            'fuel_load_MJ_m2':energy/areas[rid],'fuel_basis':'current input energy/area; scenario multipliers already included',
            'raw':{'fuel':energy,'ventilation_restriction':vent_sum/math.prod(r['size_m']),
                   'connectivity':sum(areas[x] for x in reached),'passage_adjacency':int(bool(direct[rid]&passage)),
                   'fire_isolation':isolation},
            'reachable_rooms':sorted(reached),'adjacent_passages':sorted(direct[rid]&passage),
            'internal_door_count':len(doors),'cad_polys':r.get('cad_polys',[]),'cad_center_m':r.get('cad_center_m'),
            'floor':r.get('cad_floor'),'z_m':r.get('z_m',r['origin_m'][2])})
    ranges={k:{'min':min(r['raw'][k] for r in rows),'max':max(r['raw'][k] for r in rows)} for k in FACTORS}
    for r in rows:
        normalized={}
        for k in FACTORS:
            lo,hi=ranges[k].values()
            value=(r['raw'][k]-lo)/(hi-lo) if hi>lo else 0.
            normalized[k]=(1-value if k in REVERSE else value) if hi>lo else c['constant_factor_contribution']
        r['normalized']=normalized;r['weighted']={k:normalized[k]*c['weights'][k] for k in FACTORS}
        r['score']=sum(r['weighted'].values())
        r['reason']=f"연료 {r['raw']['fuel']:.0f}MJ · 열린 문 2단계 {r['raw']['connectivity']:.1f}m² · 방화문 비율 {r['raw']['fire_isolation']:.0%}"
    ranked=sorted((r for r in rows if r['eligible']),key=lambda r:(-r['score'],r['room']))
    n=validate_n(c['default_top_n'] if top_n is None else top_n,len(ranked))
    prev=None;rank=0
    for index,r in enumerate(ranked,1):
        if r['score']!=prev:rank=index
        r.update(rank1=rank,selection_order=index,selected=index<=n);prev=r['score']
    return {'revision':'v6_screening','top_n':n,'eligible_count':len(ranked),'all_room_count':len(rows),
        'weights':c['weights'],'settings':c,'factor_ranges':ranges,'ranked':ranked,
        'excluded':[r for r in rows if not r['eligible']],'opening_states':openings,'door_classification':classification,
        'score_seconds':time.perf_counter()-started,
        'limits':c['limitations']+[
            'min-max across all original rooms before cell subdivision; constant factors contribute0',
            'ventilation factor uses gross geometrical A sqrt(H), both internal/external, without state or oxygen network prediction',
            'connectivity uses representative open internal doors/passages, two hops, unique area excluding source',
            'passage adjacency uses existing usage/core_kind, not newly inferred OCR classification',
            'existing door classification retained; known oversized OCR room can overclassify fire doors; v6 stage4 not applied',
            'eligible rooms require existing fuel>=50MJ/m2 and no circulation core; ties use room ID only to select exactly N',
            'no frequency, isolation/escape, vertical spread or actual smoke arrival prediction in score'],
        'representative_model':model}

def scenario(scoring,rid,duration=3600):
    if rid not in {r['room'] for r in scoring['ranked']}:raise ValueError('Ineligible source room')
    raw=deepcopy(scoring['representative_model'])
    for g in raw['fuel_groups']:g.pop('initial_time_s',None)
    candidates=[g for g in raw['fuel_groups'] if g['room']==rid]
    # Source inputs have one group per room; refuse silently discarding fuel.
    if len(candidates)!=1:raise ValueError('Source room must have one existing fuel group')
    candidates[0]['initial_time_s']=0.
    raw['duration_s']=duration;raw['room_rule_r8']={'preset':'standard','room_supply':'item_peak'}
    raw['screening_source']={'room':rid,'initial_curve':'own existing fuel group, no transfer of another room HRR',
        'opening_policy':'p>=.5 digital representative state'}
    return raw

def summarize(model,result):
    t=np.asarray(result['t']);rooms={};fo=[]
    for i,row in enumerate(result['room_summary']):
        origin=row['original_room'];record=rooms.setdefault(origin,{'burning':False,'smoke_risk':False,'first_FO_s':None})
        record['burning']|=row['actual_peak_kW']>0
        z=np.asarray(result['rooms'][i]['z_int']);temp=np.asarray(result['rooms'][i]['T_u'])
        yf=np.maximum(model.sol.y[6*model.N+i],0.)
        lfl=model.P['LFL0_hrr']/model.P['dHc']*np.clip(1-(temp+273.15-293)/1300,.2,1.)
        hot=model.input_model['gas']['hot_C']
        # Only ranking metric; does not enable the future 3D smoke-stage display.
        smoke=(temp>=hot)&(yf>=lfl)&((model.Ha[i]-z>=.3)|(z<=1.8))
        record['smoke_risk']|=bool(smoke.any())
        mask=result['shared_conditions']['rooms'][row['cell']]['FO']['occurred']
        hits=[float(t[j]) for j,v in enumerate(mask) if v is True]
        if hits:
            record['first_FO_s']=min(record['first_FO_s'] if record['first_FO_s'] is not None else float('inf'),min(hits));fo.extend(hits)
    return {'complete':result['ok'],'safe_end_s':float(t[-1]),
        'burning_room_count':sum(r['burning'] for r in rooms.values()),
        'smoke_risk_room_count':sum(r['smoke_risk'] for r in rooms.values()),'first_FO_s':min(fo,default=None),
        'rooms':rooms,'metric_basis':'original rooms; union across cells/time, actual HRR>0; smoke3factor per4.2; FO shared three-factor all_met'}

def rank_simulations(rows):
    good=[r for r in rows if r.get('complete')]
    def key(r):return (-r['burning_room_count'],-r['smoke_risk_room_count'],r['first_FO_s'] if r['first_FO_s'] is not None else float('inf'))
    good.sort(key=lambda r:(key(r),r['room']))
    prev=None;rank=0
    for index,r in enumerate(good,1):
        if key(r)!=prev:rank=index
        r['rank2']=rank;prev=key(r)
    for r in rows:
        if not r.get('complete'):r['rank2']=None
    return good+[r for r in rows if not r.get('complete')]
