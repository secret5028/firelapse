"""One screening definition for all solvers. No feedback into the combustion solver.

Thresholds are project screening assumptions, not occurrence probabilities.
BD is a potential; an opening increase is additionally required for occurred.
FGI is a potential of the smoke-layer mixture in every room, the origin included;
whether that mixture ignites is not assessed.
"""
import numpy as np
from .physics_config import defaults

BASE_REVISION = 'physics_p0_v3'
FGI_REVISION = 'fgi_layer_potential_v1'
CONDITION_VERSION = BASE_REVISION + '+' + FGI_REVISION


def settings(model):
    c={**defaults('criteria'),**model.get('criteria',{})}
    gas=model.get('gas',{})
    c['gas_ignition_C']=model.get('criteria',{}).get('gas_ignition_C',gas.get('gas_ignition_C',c['gas_ignition_C']))
    y=gas.get('native_lower_oxygen_limit_mass_fraction',.15)
    # Convert solver oxygen mass fraction to mole fraction using configured molar masses.
    c['native_oxygen_limit_vol_percent']=100*(y/c['oxygen_molar_mass'])/(y/c['oxygen_molar_mass']+(1-y)/c['background_molar_mass'])
    # Native LOL limits the solver's combustion rate; it is not a measured LOC
    # for the effective smoke mixture. Preserve the separately declared FGI
    # screening assumption (user correction after the Wando R5 comparison).
    c['oxygen_loc_vol_percent']=c['fgi_oxygen_vol_percent']
    if c['oxygen_loc_vol_percent']<=0 or c['fo_temperature_C']<=model.get('ambient_C',20):
        raise ValueError('Invalid screening oxygen/temperature reference')
    return c


def flammability(model,temperature):
    c=settings(model);heats={float(g['heat_of_combustion_kJ_kg'])*1000 for g in model.get('fuel_groups',[])}
    if len(heats)!=1:return np.full(len(temperature),np.nan),np.full(len(temperature),np.nan)
    heat=next(iter(heats));delta=(np.asarray(temperature)+273.15-c['lfl_reference_K'])/c['lfl_temperature_span_K']
    lfl=c['lfl_heat_J_kg']/heat*np.clip(1-delta,c['lfl_min_factor'],1)
    # UFL is an explicit configurable effective-fuel proxy, not measured vehicle smoke.
    ufl=np.minimum(1,c['ufl_heat_J_kg']/heat*np.maximum(1+delta,1))
    return lfl,ufl


def opening_increases(model,room,t,result=None):
    from .openings import realized_fraction
    t=np.asarray(t);active=np.zeros(len(t),bool);physical=room.get('parent_room',room['id'])
    members={r['id'] for r in model['rooms'] if r.get('parent_room',r['id'])==physical}
    for v in model.get('openings',[]):
        if v.get('virtual_cell_boundary') or not members.intersection((v['a'],v['b'])):continue
        try:f=np.asarray(realized_fraction(result or {'time_s':t},v,t))
        except (ValueError,KeyError):continue
        for at in t[1:][np.diff(f)>0]:active|=(t>=at)&(t-at<=settings(model)['window_s'])
    return active


def evaluate_cell(model,room,t,temperature,interface,oxygen,fuel,solid_kW,
                  bulk_kW=None,jet_kW=None,flux_kW_m2=None,own_fire=None,
                  opening_increased=None,flame_height_m=None):
    c=settings(model);t=np.asarray(t);n=len(t)
    def arr(v,default=np.nan):return np.full(n,default) if v is None else np.broadcast_to(np.asarray(v,dtype=float),(n,))
    temp=arr(temperature);o2=arr(oxygen);yf=arr(fuel);solid=arr(solid_kW);bulk=arr(bulk_kW,0);jet=arr(jet_kW,0)
    depth=room['size_m'][2]-arr(interface);deep=depth>=c['min_layer_depth_m']
    own=arr(own_fire) if own_fire is not None else solid>0
    pT=np.maximum(0,(temp-model.get('ambient_C',20))/(c['fo_temperature_C']-model.get('ambient_C',20)))
    flux=arr(flux_kW_m2);pFlux=flux/c['fo_flux_kW_m2']
    fo_gate=deep&((own>0)|(jet>0))
    fo=np.fmax(pT,pFlux)
    lfl,ufl=flammability(model,temp);too_rich=yf>ufl
    pF=np.where(too_rich,0,np.maximum(yf,0)/lfl);pO=np.maximum(o2,0)/c['oxygen_loc_vol_percent']
    # The mixture is judged wherever a layer exists; a fire in the room does not remove it.
    fgi_gate=deep&(temp<c['gas_ignition_C'])
    bd=np.minimum(np.maximum(yf,0)/c['fuel_rich_mass_fraction'],np.maximum(0,(c['ambient_oxygen_vol_percent']-o2)/(c['ambient_oxygen_vol_percent']-c['oxygen_deficient_vol_percent'])))
    opened=arr(opening_increased,0)>0
    def record(gate,proximity,factors,occurred=None,label=''):
        known=deep&np.isfinite(proximity);value=np.where(gate&known,proximity,np.nan)
        met=gate&known&(proximity>=1) if occurred is None else gate&known&occurred
        def values(a):return [float(x) if np.isfinite(x) else None for x in a]
        flags=[bool(x) if d and (not g or k) else None for x,d,g,k in zip(met,deep,gate,known)]
        hits=np.flatnonzero(met)
        keys=list(factors);weak=[];strong=[]
        for i in range(n):
            valid={k:float(a[i]) for k,a in factors.items() if np.isfinite(a[i])}
            weak.append(min(valid,key=valid.get) if valid else None);strong.append(max(valid,key=valid.get) if valid else None)
        return dict(revision=BASE_REVISION,status='evaluated',label=label,gate=[bool(g) if d else None for g,d in zip(gate,deep)],proximity=values(value),occurred=flags,
                    all_met=flags,first_met_s=float(t[hits[0]]) if len(hits) else None,terms=[],
                    scores=dict(degree=values(value),all_met=flags,factors={k:values(a) for k,a in factors.items()},weakest=weak,strongest=strong),
                    limits=['condition proximity, not occurrence probability'])
    out={
        'FO':record(fo_gate,fo,{'temperature':pT,'flux':pFlux},label='FO'),
        'FGI':record(fgi_gate,np.minimum(pF,pO),{'fuel':pF,'oxygen':pO},label='FGI'),
        'backdraft':record(deep,bd,{'fuel':np.maximum(yf,0)/c['fuel_rich_mass_fraction'],'oxygen':np.maximum(0,(c['ambient_oxygen_vol_percent']-o2)/(c['ambient_oxygen_vol_percent']-c['oxygen_deficient_vol_percent']))},occurred=(bd>=1)&opened,label='BD 잠재(개방 시)')}
    out['FGI'].update(revision=FGI_REVISION,occurrence_assessed=False,occurred=[None]*n,
        applicability='all rooms including origin; gas mixture potential, not observed ignition')
    out['FGI'].update(too_rich=too_rich.tolist(),fuel_lfl=arr(lfl).tolist(),fuel_ufl=arr(ufl).tolist(),remote_ignition=(jet>0).tolist())
    out['FGI']['thresholds']=dict(oxygen_vol_percent=c['oxygen_loc_vol_percent'],native_combustion_limit_vol_percent=c['native_oxygen_limit_vol_percent'],basis='configured FGI screening assumption, not a measured mixture LOC; independent of native combustion LOL')
    out['backdraft']['thresholds']={k:c[k] for k in ('fuel_rich_mass_fraction','oxygen_deficient_vol_percent')}
    out['backdraft']['potential']=out['backdraft']['proximity'];out['backdraft']['opening_increased']=opened.tolist()
    rollover=deep&((bulk>c['q_min_kW'])|(arr(flame_height_m)>=room['size_m'][2])|((temp>=c['gas_ignition_C'])&(yf>=lfl)&(yf<=ufl)&(o2>=c['oxygen_loc_vol_percent'])))
    hits=np.flatnonzero(rollover)
    out['rollover']=dict(revision=BASE_REVISION,label='롤오버 조건',active=[bool(x) if d else None for x,d in zip(rollover,deep)],status='evaluated',first_active_s=float(t[hits[0]]) if len(hits) else None)
    return out
