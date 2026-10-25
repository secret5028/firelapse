"""Read-only adapter to shared conditions.py; no feedback into physics."""
from copy import deepcopy
import numpy as np
from pyrocast_cfbt.conditions import evaluate,term,phenomenon,_finite
from pyrocast_cfbt.spread import classify
from .core import P0,RG

def factor_scores(record):
    """Report unknown for factors not defined by the shared phenomenon.

    Used only for a record without the three-factor shared scoring definition,
    such as the temperature/interface tenability rule.
    """
    terms={x['key']:x for x in record['terms']};n=len(record['all_met'])
    keys={'temperature':['Tu','auto_T'],'fuel':['Yf'],'oxygen':['O2']}
    factors={}
    for name,candidates in keys.items():
        tr=next((terms[k] for k in candidates if k in terms),None);values=[]
        for j in range(n):
            value=None
            if tr:
                v=tr['value'][j];th=tr['threshold']
                c=th[j] if isinstance(th,(list,np.ndarray)) else th
                if v is not None and c is not None:
                    if tr['op']=='<' and v>0:value=float(c/v)
                    elif tr['op'] in ('>=','>') and c>0:value=float(v/c)
            values.append(value)
        factors[name]=values
    score=[];weak=[];strong=[]
    for j in range(n):
        v={k:a[j] for k,a in factors.items()}
        if any(x is None for x in v.values()):score.append(None);weak.append(None);strong.append(None)
        else:
            score.append(min(v.values()));weak.append(min(v,key=v.get));strong.append(max(v,key=v.get))
    return {'factors':factors,'degree':score,'weakest':weak,'strongest':strong,
        'meaning':'min of defined T/fuel/O2 ratios, not probability; unknown if a criterion does not define all three',
        'criteria_note':'shared boolean gates/strict inequalities remain authoritative; degree does not replace them'}

def shared_conditions(model,result):
    t=model.sol.t;y=model.sol.y;n=model.N;size=len(t)
    room_oxygen=model.P.get('oxygen_inventory_mode',False)
    if room_oxygen:
        indicator=model.oxygen_indicator(y);y=model.expand(y)
    source=deepcopy(model.input_model);enabled=model.P.get('upper_combustion_enabled',False)
    source['condition_scoring']={'LFL0_hrr':model.P['LFL0_hrr']}
    source['gas'].update(enabled=enabled,bulk_enabled=enabled,mixture_enabled=False,mixture_smooth_enabled=False)
    states={};inventory={};zone={'Time':t};ignitions=[]
    for index,g in enumerate(source['fuel_groups'],1):
        i=model.rmap[g['room']];r=result['rooms'][i]
        q=np.asarray(r['actual_HRR_kW'])*1000;sup=np.asarray(r['supply_HRR_kW'])
        zone[f'HRR_{index}']=q
        inventory[g['id']]={'actual_HRR_W':q,'prescribed_pyrolysis_kW':sup,
            'pyrolysis_supply_kg_s':sup*1000/model.P['dHc']}
        if g['room'] in model.activation:
            at=model.activation[g['room']]+(0 if 'initial_time_s' in g else model.manifest['parents'][g['room']]['delay_s'])
            if 'initial_time_s' not in g:ignitions.append({'group':g['id'],'room':g['room'],'t_ign_s':at})
    for i,node in enumerate(model.nodes):
        vu=np.clip(y[n+i],model.Vmin[i],model.Va[i]-model.Vmin[i]);temp=np.maximum(y[2*n+i],200)
        mass=P0/(RG*temp)*vu;fuel=mass*np.maximum(y[6*n+i],0)
        states[node['id']]={'T_upper_C':temp-273.15,'o2_upper_vol':indicator[i] if room_oxygen else y[4*n+i]*29/32,
            'o2_lower_vol':indicator[i] if room_oxygen else y[5*n+i]*29/32,
            'upper_mass_kg':mass,'fuel_upper_kg':fuel,'fuel_upper_J':fuel*model.P['dHc'],
            'bulk_HRR_W':np.asarray(result['rooms'][i].get('upper_HRR_kW',np.zeros(size)))*1000}
    classified=classify(source,{'zone':zone,'slabs':[],'vents':[]},states,ignitions,[])
    payload={'time_s':t,'zone':zone,'rooms':states,'solid_fuel_inventory':inventory,'phenomena':classified,
        'opening_states':{v['id']:{'fraction':[v['schedule'][0][1]]*size} for v in source['openings']},
        'ignitions':ignitions,'candidates':[],'directional_vent_reactions':[]}
    shared=evaluate(source,payload)
    out={}
    for i,node in enumerate(model.nodes):
        rid=node['id'];s=shared[rid]
        # No native tenability function exists in conditions.py: use its common
        # term/AND evaluator with the unchanged legacy lite thresholds.
        z=(model.Va[i]-np.clip(y[n+i],model.Vmin[i],model.Va[i]-model.Vmin[i]))/model.Aa[i]
        unten=phenomenon(t,[term('height','연기층 경계 높이',z,model.P['z_ten'],'<','m','legacy z_ten',size),
            term('Tu','통행 높이 고온층',y[2*n+i]-273.15,model.P['T_ten']-273.15,'>','℃','legacy T_ten',size)],{})
        records={'FO':s['fo'],'FGI':s['fgi'],'backdraft':s['backdraft'],
                 'rollover':s['upper_gas'],'untenable':unten}
        for name,rec in records.items():
            rec['status']='evaluated'
            if name in ('FGI','backdraft','rollover') and not enabled:
                rec['status']='not_evaluated';rec['all_met']=[None]*size;rec['first_met_s']=None
                rec['reason']='upper unburned-fuel reaction absent; historical inventory not qualified'
            if 'scores' not in rec:rec['scores']=factor_scores(rec)
            if room_oxygen:
                rec['oxygen_basis']='single room mass-ratio proxy mO2/m_room; layer fields are internal aliases only'
                for tr in rec['terms']:
                    if tr['key']=='O2':
                        tr['label']='실평균 산소 대용 지표';tr['unit']='질량비%';tr['source']+='; section3.0 room mass-ratio proxy'
                if name=='FO':rec['score_basis']['oxygen_source']='single room mass-ratio proxy; no lower-layer O2 state'
            if name!='untenable' and rec['status']=='evaluated':
                known=sum(v is not None for v in rec['scores']['degree'])
                rec['score_coverage']={'known_samples':known,'total_samples':size}
                if known==0:
                    rec['status']='not_evaluated';rec['reason']='A required scoring factor has no defined input'
                elif known<size:rec['status']='partially_evaluated'
            if rec['status']=='not_evaluated':
                rec['scores']={'factors':{k:[None]*size for k in ('temperature','fuel','oxygen')},
                    'degree':[None]*size,'weakest':[None]*size,'strongest':[None]*size}
        records['rollover']['label']='상층 연소 조건(롤오버 가능 조건); 실제 롤오버 확정 아님'
        records['rollover']['actual_upper_reaction_kg_s']=result['rooms'][i].get('upper_reaction_kg_s',[0.]*size)
        records['opening_combustion']={'label':'개구부 분출 연소(간략 계산)',
            'status':'evaluated' if model.P.get('door_jet_enabled',False) else 'not_evaluated',
            'HRR_kW':result['rooms'][i].get('door_jet_HRR_kW',[0.]*size),
            'lower_oxygen_consumption_kg_s':result['rooms'][i].get('door_jet_lower_oxygen_kg_s',[0.]*size),
            'meaning':'receiving-room jet heat; separate from rollover and upper bulk reaction; not a new solid ignition'}
        out[rid]=records
    return _finite({'engine':'shared pyrocast_cfbt.conditions.evaluate','rooms':out,
        'units':{'temperature':'upper-layer average Celsius, not plate or local ceiling jet',
                 'oxygen':'mO2/m_room mass-ratio proxy, same value for all conditions; not physical vol%' if room_oxygen else 'stored mass fraction *29/32 -> volume fraction, shared table uses vol%',
                 'fuel':'upper unburned mass/upper total mass, no separately resolved CO',
                 'HRR':'primary source and upper reaction separate, W for shared evaluator'},
        'limits':['FO display adds Thomas HRR and configured lower O2 factors; transition rules unchanged',
                  'FGI display adds configured hot_C temperature factor; probability not estimated',
                  'rollover maps to upper_gas condition table, not native RO reaction flag or flame propagation',
                  'door-jet surrogate is reported separately when enabled; detailed oxygen-inflow causality remains unassessed',
                  'tenability uses existing lite temperature/interface rule; no PPE/FED/visibility evaluation']})
