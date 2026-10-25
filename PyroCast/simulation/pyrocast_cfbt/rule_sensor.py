"""r6 fixed gas-proxy plate prescription; experimental until benchmark gates pass."""
import math


def gas_proxy_plate(model,room,source,target_id=None):
    """Choose the farthest inset corner before seeing results; break ties by x/y."""
    origin=room['origin_m'];w,d,h=room['size_m']
    if w<=.6 or d<=.6 or h<=.2:
        raise ValueError('Room too small for r6 fixed 0.3m wall / 0.2m ceiling inset')
    point=source.get('solver_position_m',source['position_m'])
    corners=[(origin[0]+x,origin[1]+y) for x in (.3,w-.3) for y in (.3,d-.3)]
    x,y=min(corners,key=lambda xy:(-math.hypot(xy[0]-point[0],xy[1]-point[1]),xy))
    walls=[(abs(x-origin[0]),0,[-1,0,0]),(abs(x-origin[0]-w),1,[1,0,0]),
           (abs(y-origin[1]),2,[0,-1,0]),(abs(y-origin[1]-d),3,[0,1,0])]
    # Equal 0.3m insets are resolved by fixed wall order, not float roundoff.
    normal=min(walls,key=lambda wall:(round(wall[0],10),wall[1]))[2]
    xyz=[x,y,origin[2]+h-.2]
    material={**model['material'],'conductivity_W_mK':45.,'density_kg_m3':7850.,
              'specific_heat_kJ_kgK':.46,'thickness_m':.0001,'emissivity':.05}
    return {'id':target_id or 'GP_'+room['id'],'group':source['id'],'room':room['id'],
            'xyz':xyz,'solver_xyz':xyz,'normal':normal,'material':material,
            'basis':'r6 low-emissivity plate at deterministic farthest inset corner; gas temperature proxy is unvalidated',
            'used_for_ignition':False}


def gas_proxy_plate_r6a(model,room,source,target_id=None,allow_cone_fallback=False):
    """Apply r6a's fixed height; do not invent a finite Gaussian plume cutoff."""
    from .deck import fire_curve
    target=gas_proxy_plate(model,room,source,target_id)
    point=source.get('solver_position_m',source['position_m'])
    r=math.hypot(target['solver_xyz'][0]-point[0],target['solver_xyz'][1]-point[1])
    ceiling=room['origin_m'][2]+room['size_m'][2];h=ceiling-point[2]
    if h<=0:raise ValueError('T4b placement unavailable: source reaches ceiling')
    delta=h*.112*(1-math.exp(-2.24*max(r/h,.26)))
    z=max(1.2,room['size_m'][2]-max(delta+.1,.5))
    if z>=room['size_m'][2]-delta or z>=room['size_m'][2] or z<point[2]-room['origin_m'][2]:
        raise ValueError('T4b placement unavailable: floor minimum conflicts with jet/source geometry')
    # A sufficient bound for being outside the unattenuated flame cone, NOT
    # the Gaussian tail. Native corner reflection can multiply the fire area.
    _,_,areas=fire_curve(source,room['size_m'][0]*room['size_m'][1]);area=max(areas)
    x,y=[point[i]-room['origin_m'][i] for i in (0,1)]
    corner=min(x,room['size_m'][0]-x)<=math.sqrt(area)/2 and min(y,room['size_m'][1]-y)<=math.sqrt(area)/2
    cone_bound=math.sqrt(area*(4 if corner else 1)/math.pi)
    if r<=cone_bound and not allow_cone_fallback:raise ValueError('T4b placement unavailable: cannot establish outside unattenuated flame cone')
    target['xyz'][2]=target['solver_xyz'][2]=room['origin_m'][2]+z
    target.update(basis='r6a fixed height below native ceiling jet; Gaussian plume tail checked by measured local gas, not assumed absent',
        placement={'ceiling_jet_depth_m':delta,'horizontal_radius_m':r,'source_to_ceiling_m':h,
                   'local_height_m':z,'below_ceiling_m':room['size_m'][2]-z,'outside_ceiling_jet':True,'flame_cone_radius_upper_bound_m':cone_bound,
                   'outside_unattenuated_flame_cone':r>cone_bound,'finite_plume_cutoff_exists':False,
                   'upper_layer_membership':'time-dependent; verify against HGT, no geometry-only guarantee'})
    if allow_cone_fallback:
        target['sensor_quality']='fallback' if r<=cone_bound else 'nominal'
        target['quality_label']='판정 불확실' if r<=cone_bound else '가스 온도 대용'
        if r<=cone_bound:target['basis']+='; r7 farthest-corner fallback, local flame heating may bias the trigger'
    return target
