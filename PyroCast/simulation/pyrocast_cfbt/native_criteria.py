"""Map stock CFAST species/HRR output to the common screening definition."""
import numpy as np
from .criteria import evaluate_cell, opening_increases
from .validation import SPECIES

def native_interface(compartments, room, index):
    # CFAST SHAFT is a single upper zone; it does not export HGT/LL fields.
    if room.get('shaft'):return np.zeros(len(compartments['Time']))
    return compartments.get(f'HGT_{index}',np.full(len(compartments['Time']),np.nan))

def evaluate_native(model, compartments, masses, opening_states=None, native=None):
    c=compartments;t=c['Time'];n=len(t)
    if not np.array_equal(t,masses['Time']):raise ValueError('Native mass timestamps differ')
    from .floor_flux import read_floor_flux
    floor_flux=read_floor_flux(model,native) if native is not None else {}
    heat={r['id']:np.zeros(n) for r in model['rooms']}
    for j,g in enumerate(model['fuel_groups'],1):heat[g['room']]+=c[f'HRR_{j}']/1000
    out={}
    for i,r in enumerate(model['rooms'],1):
        rid=r['id'];parent=r.get('parent_room',rid)
        own=sum((heat[s['id']] for s in model['rooms'] if s.get('parent_room',s['id'])==parent),np.zeros(n))
        mass=sum(masses[f'ULM{s}_{i}'] for s in SPECIES)
        yf=np.divide(masses[f'ULMTUHC_{i}'],mass,out=np.full(n,np.nan),where=mass>0)
        heights=[c[f'FLHGT_{j}'] for j,g in enumerate(model['fuel_groups'],1) if g['room']==rid and f'FLHGT_{j}' in c]
        out[rid]=evaluate_cell(model,r,t,c[f'ULT_{i}'],native_interface(c,r,i),c[f'ULO2_{i}']*100,yf,heat[rid],
            jet_kW=c.get(f'DJET_{i}',np.zeros(n))/1000,own_fire=own,flux_kW_m2=floor_flux.get(rid,{}).get('values'),
            opening_increased=opening_increases(model,r,t,dict(time_s=t,opening_states=opening_states or {})),
            flame_height_m=np.max(heights,axis=0) if heights else None)
        out[rid]['FGI']['rollover']=out[rid]['rollover']
        if rid in floor_flux:
            out[rid]['FO']['floor_flux']={k:v for k,v in floor_flux[rid].items() if k!='values'}
        else:
            out[rid]['FO']['limits'].append('바닥 복사열 미평가 · 온도 기준만 평가')
    return out
