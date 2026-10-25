"""Single mixture-progress extension; existing species remain native state variables."""
CO_HEAT_J_KG=10102784.35278703
CO_OXYGEN_KG_KG=15.9994/28.0101

def validate_stoichiometry(group):
    """Reject yields/formulas that require negative native combustion products."""
    import math
    f=group['formula'];weights={'carbon':.01201,'hydrogen':.001008,'oxygen':.016,
                               'nitrogen':.01401,'chlorine':.03545}
    if set(f)!=set(weights) or not all(math.isfinite(v) and v>=0 for v in f.values()):
        raise ValueError('Mixture mode requires a complete nonnegative effective fuel formula')
    mw=sum(weights[k]*f[k] for k in weights)
    if mw<=0:raise ValueError('Effective fuel formula has zero molar mass')
    co=group['co_yield']*mw/.02801;soot=.02*mw/.01201
    co2=f['carbon']-co-soot;water=(f['hydrogen']-f['chlorine'])/2
    oxygen=co2+(water+co-f['oxygen'])/2
    if min(co2,water,oxygen)<-1e-12:
        raise ValueError('Fuel formula and native soot/CO yields require negative products or oxygen demand')


def primary_ratio(model,group):
    if not model['gas'].get('mixture_enabled',False):return 1.
    if model['gas'].get('energy_basis')!='total_potential_assumption':
        raise ValueError('Mixture mode requires explicit total-potential fuel energy basis')
    yield_co=group.get('co_yield',.01)
    ratio=1-yield_co*CO_HEAT_J_KG/(group['heat_of_combustion_kJ_kg']*1000)
    if not 0<ratio<=1:raise ValueError('CO reserve exceeds total supplied chemical energy')
    return ratio


def package_jets(config,rows,times):
    import numpy as np
    from .exposure import _inside,_polygon_exit
    rooms=config['rooms'];groups={};index={round(float(t),7):i for i,t in enumerate(times)}
    for row in rows:
        room=rooms[int(row['room_index'])-1]
        if 'cad_bounds_m' not in room:continue
        key=(room['id'],int(row['sample_index']));n=len(times)
        jet=groups.setdefault(key,{'room':room['id'],'sample':key[1],'position_m':None,'direction':[0,0,0],
            'speed_m_s':[0.]*n,'temperature_C':[None]*n,'thickness_m':[0.]*n,'display_length_m':0.})
        i=index[round(float(row['time_s']),7)];x0,y0,x1,y1=room['cad_bounds_m'];w,d,h=room['size_m']
        pos=np.array([x0+row['x_m']/w*(x1-x0),y0+row['y_m']/d*(y1-y0),room['origin_m'][2]+row['z_m']])
        if not _inside(pos[:2],room['cad_polys']):continue
        direction=np.array([row['vx_m_s']*(x1-x0)/w,row['vy_m_s']*(y1-y0)/d,0.]);mag=np.linalg.norm(direction)
        if mag<=1e-10:continue
        direction/=mag
        length=_polygon_exit(pos,direction,room['cad_polys'])
        if length is None or length<.02:continue
        if jet['position_m'] is None:jet.update(position_m=pos.tolist(),direction=direction.tolist(),display_length_m=min(1.5,length*.95))
        # A changing representative source is not silently mapped to a fixed trail.
        if np.linalg.norm(pos-np.array(jet['position_m']))>.02:continue
        jet['speed_m_s'][i]=float(np.hypot(row['vx_m_s'],row['vy_m_s']))
        jet['temperature_C'][i]=row['temperature_C'];jet['thickness_m'][i]=row['thickness_m']
    return [j for j in groups.values() if j['position_m'] is not None]
