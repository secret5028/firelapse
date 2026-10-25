"""v7 candidate scoring and two-state comparison; no thermal solver changes."""
from copy import deepcopy
import json,math,time
from pathlib import Path
from .door_classification import classify_doors
from .montecarlo import opening_class
from .screening import area,name,validate_n,rank_simulations,summarize

CONFIG=Path(__file__).with_name('screening_v7_settings.json')
FACTORS=('fuel','ventilation_restriction','connectivity','passage_adjacency','fire_isolation')

def settings(options=None):
    c=json.loads(CONFIG.read_text('utf-8'))
    if options:
        if set(options)-{'weights'}:raise ValueError('Only factor weights are configurable here')
        c['weights'].update(options.get('weights',{}))
    if set(c['weights'])!=set(FACTORS) or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in c['weights'].values()) or sum(c['weights'].values())<=0:
        raise ValueError('Five finite nonnegative weights required')
    return c

def confirmed(v):
    return opening_class(v)=='fire_door' and v.get('door_class_confidence') in ('confirmed','user')

def opening_state(classified,state,c=None):
    c=c or settings()
    if state not in c['states']:raise ValueError('Unknown extreme opening state')
    model=deepcopy(classified);rows=[]
    for v in model['openings']:
        cls=opening_class(v)
        if cls in ('permanent_open','virtual'):opened=True
        elif cls=='fixed_window':opened=False
        else:opened=state=='open_except_confirmed' and not confirmed(v)
        fraction=(c['window_open_fraction'] if cls.endswith('window') else 1.) if opened else 0.
        v['schedule']=[[0.,fraction]]
        rows.append({'id':v['id'],'a':v['a'],'b':v['b'],'class':cls,'confirmed':confirmed(v),
                     'open':opened,'effective_fraction':fraction,'classification_reason':v.get('door_class_reason')})
    return model,rows

def score(raw,top_n=None,options=None,door_overrides=None):
    start=time.perf_counter();c=settings(options);classified,classes=classify_doors(raw,door_overrides)
    opened,opening_rows=opening_state(classified,'open_except_confirmed',c)
    rooms={r['id']:r for r in classified['rooms']};areas={k:area(r) for k,r in rooms.items()}
    adj={k:set() for k in rooms};direct={k:set() for k in rooms};doors={k:[] for k in rooms}
    for v in opened['openings']:
        a,b=v['a'],v['b'];cls=opening_class(v)
        if a not in rooms or b not in rooms or cls not in ('ordinary_door','fire_door','permanent_open'):continue
        direct[a].add(b);direct[b].add(a)
        if cls!='permanent_open':doors[a].append(v);doors[b].append(v)
        if v['schedule'][0][1]>0:adj[a].add(b);adj[b].add(a)
    passage={rid for rid,r in rooms.items() if r.get('fuel_default',{}).get('usage') in ('passage','corridor','lobby','hall') or r.get('core_kind') in ('corridor','lobby')}
    rows=[]
    for rid,r in rooms.items():
        fuels=[g for g in classified['fuel_groups'] if g['room']==rid]
        energy=sum(g['energy_MJ'] for g in fuels);peak=sum(g['peak_kW'] for g in fuels)
        if energy<0 or peak<0:raise ValueError('Negative fuel input')
        vent=sum(v['width_m']*max(v['top_m']-v.get('bottom_m',0),0)**1.5 for v in classified['openings'] if rid in (v['a'],v['b']) and v.get('type','WALL')=='WALL')
        limit=1500*vent;ratio=peak/limit if limit>0 else None
        clipped=min(ratio,c['ventilation_ratio_clip']) if ratio is not None else c['ventilation_ratio_clip'] if peak>0 else 0.
        reached=set(adj[rid])
        for neighbor in adj[rid]:reached.update(adj[neighbor])
        reached.discard(rid)
        nc=sum(confirmed(v) for v in doors[rid]);ni=sum(opening_class(v)=='fire_door' and not confirmed(v) for v in doors[rid]);nd=len(doors[rid])
        isolation=(nc+c['inferred_isolation_weight']*ni)/nd if nd else 0.
        eligible=bool(fuels and energy/areas[rid]>=50 and r.get('core_kind') not in ('stair','elev','elevator','shaft'))
        rows.append({'room':rid,'name':name(r),'area_m2':areas[rid],'eligible':eligible,
            'excluded_reason':None if eligible else 'no fuel, below50MJ/m2, or circulation core',
            'raw':{'fuel':math.log10(energy) if energy>0 else None,'ventilation_restriction':ratio,
                   'connectivity':sum(areas[k] for k in reached),'passage_adjacency':int(bool(direct[rid]&passage)), 'fire_isolation':isolation},
            'normalization_input':{'fuel':math.log10(energy) if energy>0 else None,'ventilation_restriction':clipped,'connectivity':sum(areas[k] for k in reached)},
            'fuel_energy_MJ':energy,'fuel_peak_kW':peak,'opening_A_sqrtH':vent,'vent_limit_kW':limit,'vent_ratio_unbounded':limit==0 and peak>0,
            'internal_door_count':nd,'confirmed_fire_door_count':nc,'inferred_fire_door_count':ni,
            'reachable_rooms':sorted(reached),'adjacent_passages':sorted(direct[rid]&passage),
            'cad_polys':r.get('cad_polys',[]),'cad_center_m':r.get('cad_center_m'),'floor':r.get('cad_floor'),'z_m':r.get('z_m',r['origin_m'][2])})
    ranges={}
    for k in ('fuel','ventilation_restriction','connectivity'):
        vals=[r['normalization_input'][k] for r in rows if r['normalization_input'][k] is not None]
        ranges[k]={'min':min(vals,default=0.),'max':max(vals,default=0.)}
    for r in rows:
        norm={}
        for k,b in ranges.items():
            v=r['normalization_input'][k];lo,hi=b['min'],b['max']
            norm[k]=(v-lo)/(hi-lo) if v is not None and hi>lo else c['constant_factor_contribution']
        norm['passage_adjacency']=r['raw']['passage_adjacency'];norm['fire_isolation']=1-r['raw']['fire_isolation']
        r['normalized']=norm;r['weighted']={k:norm[k]*c['weights'][k] for k in FACTORS};r['score']=sum(r['weighted'].values())
        r['reason']=f"연료 {r['fuel_energy_MJ']:.0f}MJ · 공급 {r['fuel_peak_kW']:.0f}kW · 연결 {r['raw']['connectivity']:.1f}m² · 확정/추정 방화문 {r['confirmed_fire_door_count']}/{r['inferred_fire_door_count']}"
    ranked=sorted((r for r in rows if r['eligible']),key=lambda r:(-r['score'],r['room']))
    n=validate_n(c['default_top_n'] if top_n is None else top_n,len(ranked));prev=None;rank=0
    for i,r in enumerate(ranked,1):
        if r['score']!=prev:rank=i
        r.update(rank1=rank,selection_order=i,selected=i<=n);prev=r['score']
    return {'revision':'v7_screening','top_n':n,'eligible_count':len(ranked),'all_room_count':len(rows),'weights':c['weights'],
        'settings':c,'factor_ranges':ranges,'ranked':ranked,'excluded':[r for r in rows if not r['eligible']],
        'classified_model':classified,'opening_states':opening_rows,'door_classification':classes,'score_seconds':time.perf_counter()-start,
        'limits':c['limitations']+['positive-energy log10 normalized across floor; zero fuel contributes0, excluded from log range',
            'vent ratio clipped at3 BEFORE min-max; gross internal/external CAD apertures, not an oxygen-network solution',
            'binary adjacency and1-weighted_fire_fraction are not min-max normalized',
            'closed extreme retains permanent passages; fixed glazing stays closed; no window breakage',
            'N eligibility and existing passage usage unchanged; own room curve retained; no weight tuning']}

def scenario(scored,rid,state,duration=3600):
    if rid not in {r['room'] for r in scored['ranked']}:raise ValueError('Ineligible source')
    raw,opening_rows=opening_state(scored['classified_model'],state,scored['settings'])
    for g in raw['fuel_groups']:g.pop('initial_time_s',None)
    sources=[g for g in raw['fuel_groups'] if g['room']==rid]
    if len(sources)!=1:raise ValueError('Exactly one source fuel group required')
    sources[0]['initial_time_s']=0.;raw['duration_s']=duration
    raw['room_rule_r8']={'preset':'standard','room_supply':'item_peak'}
    raw['screening_source']={'revision':'v7','room':rid,'state':state,'opening_states':opening_rows,'initial_curve':'own room existing curve'}
    return raw

def worse_key(r):
    return (-r['burning_room_count'],-r['smoke_risk_room_count'],r['first_FO_s'] if r['first_FO_s'] is not None else float('inf'))

def compare_pairs(cases):
    grouped={}
    for r in cases:grouped.setdefault(r['room'],[]).append(r)
    rows=[]
    for rid,pair in grouped.items():
        if len(pair)!=2 or {r['state'] for r in pair}!={'open_except_confirmed','closed'}:raise ValueError('Two distinct states required')
        valid=[r for r in pair if r['complete']]
        worst=min(valid,key=worse_key) if valid else None
        complete=len(valid)==2
        row={k:pair[0][k] for k in ('room','name','rank1','score')}
        row.update(complete=complete,state_results=pair,worst_state=worst['state'] if complete else None,
                   tied_states=[r['state'] for r in valid if worse_key(r)==worse_key(worst)] if complete else [],
                   observed_worst_state=worst['state'] if worst else None)
        for k in ('burning_room_count','smoke_risk_room_count','first_FO_s'):row[k]=worst[k] if complete else None
        rows.append(row)
    return rank_simulations(rows)
