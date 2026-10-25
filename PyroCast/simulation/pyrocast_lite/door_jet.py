"""§3.1 lightweight vent burning; no independent fuel or oxygen reservoir.

Burn only fuel already transported by the flow ledger. All incident jets share
one receiving lower-layer oxygen rate budget after local plume withdrawal.
"""
import numpy as np

def react(fuel_u,fuel_l,source_K,to,eligible,lower_mass,lower_Yo,plume_o2_rate,p):
    from .core import H_O2
    fuel=np.maximum(fuel_u+fuel_l,0.)
    delta=np.maximum(source_K-(p['T_in']+p['door_jet_onset_delta_K']),0.)
    thermal=-np.expm1(-np.minimum(delta/p['reaction_temperature_width_K'],30.)**2)
    demand=np.where(eligible,fuel*thermal,0.)
    n=len(lower_mass);hoc=p['dHc'];s=hoc/H_O2
    total=np.bincount(to,weights=demand,minlength=n)
    available=np.maximum(lower_mass*np.maximum(lower_Yo,0.)/p['door_jet_mixing_time_s']-plume_o2_rate,0.)
    scale=np.ones(n);positive=total>0
    scale[positive]=np.minimum(1.,available[positive]/(s*total[positive]))
    xi=demand*scale[to]
    fraction=np.divide(fuel_u,fuel,out=np.zeros_like(fuel),where=fuel>0)
    burn_u=xi*fraction;burn_l=xi-burn_u
    byroom=np.bincount(to,weights=xi,minlength=n)
    return dict(reaction_kg_s=xi,oxygen_kg_s=s*xi,heat_W=hoc*xi,
                burn_into_upper_kg_s=burn_u,burn_into_lower_kg_s=burn_l,
                room_reaction_kg_s=byroom,room_oxygen_kg_s=s*byroom,
                room_heat_W=hoc*byroom,available_lower_oxygen_kg_s=available,
                incoming_fuel_kg_s=fuel,demand_kg_s=demand)
