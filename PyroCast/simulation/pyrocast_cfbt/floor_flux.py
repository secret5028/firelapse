"""Equal-area floor gauges and strict stock CFAST incident-radiation mapping."""
import numpy as np
from .physics_config import defaults

FLOOR_FLUX_REVISION='native_floor_incident_v1'

def gauges(model):
    cfg={**defaults('native_floor_flux'),**model.get('native_floor_flux',{})}
    height=float(cfg['height_m']);emissivity=float(cfg['emissivity'])
    if not np.isfinite(height) or height<=0 or emissivity!=1:
        raise ValueError('Invalid black floor radiation gauge settings')
    parents={r['id']:r.get('parent_room',r['id']) for r in model['rooms']}
    origins={parents[g['room']] for g in model.get('fuel_groups',[]) if 'initial_time_s' in g and g['room'] in parents}
    def room_side(room):
        default=cfg['origin_grid_side'] if parents[room['id']] in origins else cfg['grid_side']
        side=cfg.get('room_grid_sides',{}).get(room['id'],default)
        if not isinstance(side,int) or side<2 or side%2:raise ValueError('Invalid floor gauge grid')
        return side
    return [dict(id=f'FO_FLOOR_{i}_{x*side+y+1}',room=r['id'],local_xyz=[r['size_m'][0]*(x+.5)/side,r['size_m'][1]*(y+.5)/side,min(height,r['size_m'][2]/2)],
                 normal=[0,0,1],weight=1/(side*side),emissivity=emissivity,basis=cfg['basis'],revision=FLOOR_FLUX_REVISION)
            for i,r in enumerate(model['rooms'],1) for side in [room_side(r)] for x in range(side) for y in range(side)]

def read_floor_flux(model,native):
    """Never substitute net/convective flux, a different target, or old temperatures."""
    t=np.asarray(native['compartments']['Time']);table=native.get('devices',{})
    ids=native.get('devices_ids',{});units=native.get('devices_units',{})
    if not np.array_equal(table.get('Time'),t):raise ValueError('Floor radiation timestamps differ')
    output={}
    for gauge in gauges(model):
        keys=[k for k in table if k.startswith('TRGFLXI_') and ids.get(k)==gauge['id']]
        if len(keys)!=1:raise ValueError('Missing/duplicate floor incident radiation: '+gauge['room'])
        key=keys[0];a=np.asarray(table[key],dtype=float)
        if units.get(key)!='kW/m^2' or a.shape!=t.shape or not np.isfinite(a).all() or (a<0).any():
            raise ValueError('Invalid floor incident radiation: '+gauge['room'])
        row=output.setdefault(gauge['room'],dict(values=np.zeros(len(t)),local_max_values=np.zeros(len(t)),
            points=[],basis=gauge['basis'],revision=FLOOR_FLUX_REVISION,aggregation='equal_area_mean'))
        row['values']+=gauge['weight']*a
        row['local_max_values']=np.maximum(row['local_max_values'],a)
        row['points'].append(gauge)
    return output
