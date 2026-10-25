"""Bound diagnostics. Trial-state snapshots must never be called accepted states."""
import numpy as np
from .core import P0,RG

def describe(model,t,y):
    n=model.N;rows=[]
    for i,node in enumerate(model.nodes):
        vu=float(y[n+i]);tu=float(y[2*n+i]);tl=float(y[3*n+i])
        effective=np.clip(vu,model.Vmin[i],model.Va[i]-model.Vmin[i])
        rows.append({'cell':node['id'],'raw_upper_volume_m3':vu,
            'lower_volume_bound':float(model.Vmin[i]),'upper_volume_bound':float(model.Va[i]-model.Vmin[i]),
            'at_lower_clip':bool(vu<=model.Vmin[i]),'at_upper_clip':bool(vu>=model.Va[i]-model.Vmin[i]),
            'upper_mass_kg':float(P0/(RG*max(tu,200))*effective),
            'lower_mass_kg':float(P0/(RG*max(tl,200))*(model.Va[i]-effective)),
            'upper_C':tu-273.15,'lower_C':tl-273.15,
            'species':{key:{'raw':float(y[k*n+i]),'nonpositive':bool(y[k*n+i]<=0)}
                for key,k in [('oxygen_upper',4),('oxygen_lower',5),('fuel_upper',6),('fuel_lower',7)]},
            'openings':[{'id':v[5],'fraction':float(v[7]),'other':model.nodes[v[1] if v[0]==i else v[0]]['id']
                        if (v[1] if v[0]==i else v[0])<n else 'OUTSIDE'}
                        for v in model.vents if i in v[:2]]})
    return {'time_s':float(t),'finite':bool(np.isfinite(y).all()),'rooms':rows,
            'near_zero_mass_definition_kg':1e-6,
            'near_zero_mass_cells':[r['cell'] for r in rows if min(r['upper_mass_kg'],r['lower_mass_kg'])<1e-6]}
