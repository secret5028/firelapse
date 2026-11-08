"""Map stock CFAST species/HRR output to the common screening definition."""
import numpy as np
from .criteria import evaluate_cell, opening_increases
from .validation import SPECIES


def evaluate_native(model, compartments, masses, opening_states=None):
    c=compartments;t=c['Time'];n=len(t)
    if not np.array_equal(t,masses['Time']):raise ValueError('Native mass timestamps differ')
    heat={r['id']:np.zeros(n) for r in model['rooms']}
    for j,g in enumerate(model['fuel_groups'],1):heat[g['room']]+=c[f'HRR_{j}']/1000
    out={}
    for i,r in enumerate(model['rooms'],1):
        rid=r['id'];parent=r.get('parent_room',rid)
        own=sum((heat[s['id']] for s in model['rooms'] if s.get('parent_room',s['id'])==parent),np.zeros(n))
        mass=sum(masses[f'ULM{s}_{i}'] for s in SPECIES)
        yf=np.divide(masses[f'ULMTUHC_{i}'],mass,out=np.full(n,np.nan),where=mass>0)
        heights=[c[f'FLHGT_{j}'] for j,g in enumerate(model['fuel_groups'],1) if g['room']==rid and f'FLHGT_{j}' in c]
        out[rid]=evaluate_cell(model,r,t,c[f'ULT_{i}'],c[f'HGT_{i}'],c[f'ULO2_{i}']*100,yf,heat[rid],
            jet_kW=c.get(f'DJET_{i}',np.zeros(n))/1000,own_fire=own,
            opening_increased=opening_increases(model,r,t,dict(time_s=t,opening_states=opening_states or {})),
            flame_height_m=np.max(heights,axis=0) if heights else None)
        out[rid]['FGI']['rollover']=out[rid]['rollover']
    return out
