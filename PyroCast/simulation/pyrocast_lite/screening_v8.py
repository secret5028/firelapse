"""v8 origin fuel budget and five-key ranking. Thermal engine unchanged."""
from copy import deepcopy
import numpy as np
from pyrocast_cfbt.rule_settings import resolve
from . import screening_v7 as v7


def origin_budgets(raw):
    options=dict(raw.get('room_rule_r8',{}))
    # v8 explicitly uses k=1, unlike the historical room_involvement default .7.
    options.setdefault('vent_cap_k',1.)
    opts=resolve(options)
    coverage=opts['values']['coverage_default'];k=opts['values']['vent_cap_k']
    ids={r['id'] for r in raw['rooms']};out={}
    for r in raw['rooms']:
        rid=r['id'];floor=v7.area(r)
        groups=[g for g in raw['fuel_groups'] if g['room']==rid]
        if len(groups)>1:
            raise ValueError('v8 origin requires one fuel preset per room; no silent mixing')
        energy=sum(g['energy_MJ'] for g in groups)
        hrrpua=groups[0]['hrrpua_kW_m2'] if groups else 0.
        vents=[v for v in raw['openings'] if v.get('type','WALL')=='WALL' and
               rid in (v['a'],v['b']) and (v['b'] if v['a']==rid else v['a']) not in ids]
        ah=sum(v['width_m']*max(v['top_m']-v.get('bottom_m',0.),0.)**1.5 for v in vents)
        fuel=coverage*floor*hrrpua;cap=k*1500*ah;peak=min(fuel,cap)
        out[rid]={'room':rid,'origin_fire_basis':'fuel_based','Q_origin_peak_kW':peak,
            'coverage':coverage,'coverage_source':opts['parameters']['coverage_default']['source'],
            'area_m2':floor,'hrrpua_kW_m2':hrrpua,'hrrpua_source':'current fuel group',
            'fuel_surface_peak_kW':fuel,'external_cap_kW':cap,'external_A_sqrtH':ah,
            'external_opening_ids':[v['id'] for v in vents],'vent_cap_k':k,
            'energy_MJ':energy,'fuel_load_MJ_m2':energy/floor,'energy_source':'current group budget / floor area',
            'growth_kW_s2':.047,'input_peak_used':False,
            'limiting_factor':'no fuel' if not groups else 'external aperture' if cap<fuel else 'fuel surface',
            'opening_basis':'gross external CAD aperture sum, same source curve in both states; no internal fallback',
            'zero_peak_reason':'no external aperture or no fuel' if peak==0 else None}
    return out


def score(raw,top_n=None,options=None,door_overrides=None):
    budgets=origin_budgets(raw);adjusted=deepcopy(raw)
    for g in adjusted['fuel_groups']:g['peak_kW']=budgets[g['room']]['Q_origin_peak_kW']
    result=v7.score(adjusted,top_n,options,door_overrides)
    # Only score numerator uses the adjusted copy. Unselected standby input stays §2.
    original={g['id']:g for g in raw['fuel_groups']}
    result['classified_model']['fuel_groups']=[deepcopy(original[g['id']]) for g in result['classified_model']['fuel_groups']]
    result.update(revision='v8_screening',origin_fire_basis='fuel_based',origin_budgets=budgets)
    result['settings']['ranking_order']=['burning_rooms_desc','smoke_risk_rooms_desc','smoke_caution_rooms_desc','first_FO_s_asc','origin_max_upper_C_desc']
    for row in result['ranked']+result['excluded']:
        row['origin_budget']=budgets[row['room']]
    result['limits']=[x for x in result['limits'] if 'own room curve retained' not in x]+[
        'v8 origin: coverage default .5, current group HRRPUA and energy, alpha .047; input peak unused',
        'external cap uses gross geometry in both states; actual combustion remains oxygen-limited',
        'zero external aperture gives zero origin cap; simulation rejected explicitly rather than inventing fallback',
        'non-origin standby supply remains section2 item_peak; origin siblings receive new source area shares',
        'caution counts any sampled time with 1-2 smoke factors; may overlap risk rooms at other times']
    return result


def scenario(scored,rid,state,duration=3600):
    data=v7.scenario(scored,rid,state,duration);b=scored['origin_budgets'][rid]
    if b['Q_origin_peak_kW']<=0:raise ValueError('Zero fuel-based source cap; no external-aperture fallback authorized')
    g=next(g for g in data['fuel_groups'] if g['room']==rid)
    for key in ('room_rule_curve','room_rule_trigger','room_rule_vent_cap'):g.pop(key,None)
    g.update(peak_kW=b['Q_origin_peak_kW'],growth_kW_s2=b['growth_kW_s2'],
             fuel_area_m2=b['coverage']*b['area_m2'],coverage_fraction=b['coverage'])
    data['room_rule_r8']={**data['room_rule_r8'],'coverage_default':b['coverage'],'vent_cap_k':b['vent_cap_k']}
    data['origin_fire_basis']='fuel_based'
    data['screening_source'].update(revision='v8',initial_curve='fuel_based',origin_budget=deepcopy(b))
    return data


def summarize(model,result):
    summary=v7.summarize(model,result)
    rid=model.input_model['screening_source']['room'];origin_max=[]
    for i,row in enumerate(result['room_summary']):
        record=summary['rooms'][row['original_room']]
        temp=np.asarray(result['rooms'][i]['T_u']);z=np.asarray(result['rooms'][i]['z_int'])
        yf=np.maximum(model.sol.y[6*model.N+i],0.)
        lfl=model.P['LFL0_hrr']/model.P['dHc']*np.clip(1-(temp+273.15-293)/1300,.2,1.)
        count=(temp>=model.input_model['gas']['hot_C']).astype(int)+(yf>=lfl).astype(int)+((model.Ha[i]-z>=.3)|(z<=1.8)).astype(int)
        record['smoke_caution']=record.get('smoke_caution',False) or bool(((count>=1)&(count<=2)).any())
        # Ranking uses the unrounded diagnostic, not the one-decimal viewer series.
        if row['original_room']==rid:origin_max.append(row['upper_max_C'])
    summary.update(smoke_caution_room_count=sum(r['smoke_caution'] for r in summary['rooms'].values()),
                   origin_max_upper_C=max(origin_max),origin_fire_basis='fuel_based',
                   origin_budget=model.input_model['screening_source']['origin_budget'])
    return summary


METRICS=('burning_room_count','smoke_risk_room_count','smoke_caution_room_count','first_FO_s','origin_max_upper_C')

def worse_key(r):
    return (-r['burning_room_count'],-r['smoke_risk_room_count'],-r['smoke_caution_room_count'],
            r['first_FO_s'] if r['first_FO_s'] is not None else float('inf'),-r['origin_max_upper_C'])

def compare_pairs(cases):
    grouped={}
    for r in cases:grouped.setdefault(r['room'],[]).append(r)
    rows=[]
    for rid,pair in grouped.items():
        if len(pair)!=2 or {r['state'] for r in pair}!={'open_except_confirmed','closed'}:raise ValueError('Two distinct states required')
        valid=[r for r in pair if r['complete']];complete=len(valid)==2
        worst=min(valid,key=worse_key) if valid else None
        row={k:pair[0][k] for k in ('room','name','rank1','score')}
        row.update(complete=complete,state_results=pair,worst_state=worst['state'] if complete else None,
                   observed_worst_state=worst['state'] if worst else None,
                   tied_states=[r['state'] for r in valid if worse_key(r)==worse_key(worst)] if complete else [])
        row.update({k:worst[k] if complete else None for k in METRICS});rows.append(row)
    good=sorted((r for r in rows if r['complete']),key=lambda r:(worse_key(r),r['room']))
    prev=None;rank=0
    for i,r in enumerate(good,1):
        if worse_key(r)!=prev:rank=i
        r['rank2']=rank;prev=worse_key(r)
    bad=[r for r in rows if not r['complete']]
    for r in bad:r['rank2']=None
    return good+bad
