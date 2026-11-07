"""Explicit rectangular geometry and finite, disjoint solid-fuel budgets."""
import math
import re
import numpy as np
from .openings import window_targets
from .mixture import primary_ratio


def active_fuels(model,committed):
    """Native fire numbers remain stable when a later event activates an earlier-listed group."""
    if model.get('room_fire_rule',{}).get('prepared'):
        return model['fuel_groups']
    groups={g['id']:g for g in model['fuel_groups']}
    order=[g['id'] for g in model['fuel_groups'] if 'initial_time_s' in g]
    for event in committed:
        if event['group'] not in order:order.append(event['group'])
    return [groups[key] for key in order]


def fire_curve(group, floor_area):
    if 'room_rule_curve' in group:
        curve=group['room_rule_curve']
        return curve['t'],curve['q'],curve['area']
    energy = group["energy_MJ"] * 1000.0  # kJ; integral of kW over seconds
    alpha = group["growth_kW_s2"]
    fraction = group.get("decay_after_fraction", 0.7)
    if not 0 < fraction < 1:
        raise ValueError("decay_after_fraction must be between zero and one")
    x = np.linspace(0.0, 1.0, 41)
    factor = float(np.trapezoid(x*x, x))
    fuel_area = min(floor_area, group.get('fuel_area_m2', floor_area))
    peak = min(group["peak_kW"], fuel_area * group["hrrpua_kW_m2"],
               (fraction * energy * math.sqrt(alpha) / factor) ** (2/3))
    grow_s = math.sqrt(peak/alpha)
    growth_energy = factor * peak * grow_s
    hold_s = max(0.0, (fraction*energy-growth_energy)/peak)
    decay_s = 2*(1-fraction)*energy/peak
    t = list(x*grow_s)
    q = list(peak*x*x)
    if hold_s > 1e-8:
        t.append(grow_s+hold_s); q.append(peak)
    t.append(grow_s+hold_s+decay_s); q.append(0.0)
    area = [min(floor_area, max(0.1, v/group["hrrpua_kW_m2"])) for v in q]
    return t, q, area


def opening_frame(opening, rooms):
    if 'cad_geometry' in opening:
        frame=opening['cad_geometry']
        return tuple(np.array(frame[k],float) for k in ('center_m','tangent','normal_a_to_b'))
    room = rooms[opening["a"]]
    origin = np.array(room["origin_m"], float)
    w, d, _ = room["size_m"]
    offset, half = opening.get("offset_m", 0.0), opening["width_m"]/2
    faces = {
        "FRONT": ([offset+half,0,0], [1,0,0], [0,-1,0]),
        "REAR": ([offset+half,d,0], [-1,0,0], [0,1,0]),
        "RIGHT": ([w,offset+half,0], [0,1,0], [1,0,0]),
        "LEFT": ([0,offset+half,0], [0,-1,0], [-1,0,0]),
    }
    point, tangent, normal = faces[opening["face"]]
    # Tangent orientation does not affect a centered rectangular aperture.
    return origin+point, np.array(tangent,float), np.array(normal,float)


def candidates(model):
    if 'explicit_candidates' in model:
        from copy import deepcopy
        return deepcopy(model['explicit_candidates'])
    rooms = {r["id"]: r for r in model["rooms"]}
    result = []
    for group in model["fuel_groups"]:
        if "initial_time_s" in group:
            continue
        room = rooms[group["room"]]
        lo = np.array(room["origin_m"],float); hi=lo+room["size_m"]
        points = []
        for opening in model.get("openings",[]):
            if group["room"] not in (opening["a"],opening["b"]):
                continue
            center, _, normal = opening_frame(opening, rooms)
            inward = -normal if group["room"] == opening["a"] else normal
            for offset in model["spread"]["candidate_offsets_m"]:
                for height in model["spread"]["candidate_heights_m"]:
                    p=center+inward*offset; p[2]=lo[2]+height
                    if np.all(p>lo+0.01) and np.all(p<hi-0.01):
                        points.append((f"{opening['id']}_{offset:g}_{height:g}",p,-inward))
        p=lo+np.array(room["size_m"])/2; p[2]=lo[2]+0.02
        points.append(("floor",p,np.array([0,0,1])))
        for suffix,p,normal in points:
            result.append({"id": f"C_{len(result)+1}", "label": suffix, "group": group["id"],
                           "room": group["room"],"xyz": p.tolist(),"normal": normal.tolist(),
                           "material": {**model["material"], **group.get("material",{})}})
    return result


def make_deck(model, committed, targets, transitions=None):
    windows=window_targets(model)
    window_by_opening={v['opening_id']:v for v in windows}
    if {v['id'] for v in windows} & {v['id'] for v in targets}:
        raise ValueError('Window and fuel target IDs must be distinct')
    rooms={r["id"]:r for r in model["rooms"]}
    wall=model['wall_material']
    lines=["&HEAD VERSION=7500 TITLE='PyroCast CFBT explicit scenario' /",
           f"&TIME SIMULATION={math.ceil(model['duration_s']+max(1,model['output_step_s'])):g} PRINT=0 SMOKEVIEW={model['output_step_s']:g} SPREADSHEET={model['output_step_s']:g} /",
           f"&INIT INTERIOR_TEMPERATURE={model['ambient_C']:g} EXTERIOR_TEMPERATURE={model['ambient_C']:g} /",
               f"&MISC MAX_TIME_STEP={model['max_time_step_s']:g} OVERWRITE=.TRUE."+
               (f" LOWER_OXYGEN_LIMIT={model['gas']['native_lower_oxygen_limit_mass_fraction']}" if model['gas']['native_lower_oxygen_limit_mass_fraction']!=.15 else '')+" /",
           f"&MATL ID='WALL' CONDUCTIVITY={wall['conductivity_W_mK']} DENSITY={wall['density_kg_m3']} SPECIFIC_HEAT={wall['specific_heat_kJ_kgK']} THICKNESS={wall['thickness_m']} EMISSIVITY={wall['emissivity']} /"]
    # Optional input materials only; legacy decks remain byte-identical when absent.
    surface_materials = model.get('surface_materials', {})
    for ident, material in sorted(surface_materials.items()):
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,45}', ident) or ident == 'WALL':
            raise ValueError('Invalid/reserved surface material ID')
        keys = ('conductivity_W_mK','density_kg_m3','specific_heat_kJ_kgK','thickness_m','emissivity')
        vals = [float(material[k]) for k in keys]
        if not all(math.isfinite(v) for v in vals) or min(vals[:4]) <= 0 or not 0 <= vals[4] <= 1:
            raise ValueError('Invalid surface material properties')
        lines.append(f"&MATL ID='{ident}' CONDUCTIVITY={vals[0]} DENSITY={vals[1]} SPECIFIC_HEAT={vals[2]} THICKNESS={vals[3]} EMISSIVITY={vals[4]} /")
    for room in model["rooms"]:
        w,d,h=room["size_m"]; x,y,z=room["origin_m"]
        shaft=" SHAFT=.TRUE." if room.get('shaft') else ''
        leaks=room.get('leak_area_ratio',[.00017,.000052])
        leak_text=','.join(str(v) for v in leaks) if 'leak_area_ratio' in room else '0.00017,0.000052'
        ids = {s:room.get('surface_material_ids',{}).get(s,'WALL') for s in ('ceiling','wall','floor')}
        if any(v != 'WALL' and v not in surface_materials for v in ids.values()):
            raise ValueError('Unknown surface material reference')
        lines.append(f"&COMP ID='{room['id']}' WIDTH={w:.9g} DEPTH={d:.9g} HEIGHT={h:.9g} ORIGIN={x:.9g},{y:.9g},{z:.9g}{shaft} CEILING_MATL_ID='{ids['ceiling']}' WALL_MATL_ID='{ids['wall']}' FLOOR_MATL_ID='{ids['floor']}' LEAK_AREA_RATIO={leak_text} /")
    for opening in model.get("openings",[]):
        schedule=opening.get("schedule",[[0,1]])
        times=','.join(f'{v[0]:g}' for v in schedule); fractions=','.join(f'{v[1]:g}' for v in schedule)
        if opening.get('type')=='FLOOR':
            lines.append(f"&VENT TYPE='FLOOR' ID='{opening['id']}' COMP_IDS='{opening['a']}','{opening['b']}' AREA={opening['area_m2']:.9g} SHAPE='SQUARE' CRITERION='TIME' T={times} F={fractions} /")
            continue
        window=window_by_opening.get(opening['id'])
        control=f"CRITERION='TIME' T={times} F={fractions}"
        if window:
            p=window['policy']
            control=(f"CRITERION='{p['criterion']}' DEVC_ID='{window['id']}' SETPOINT={p['threshold']:.12g} "
                     f"PRE_FRACTION={p['pre_fraction']:.12g} POST_FRACTION={p['post_fraction']:.12g}")
        lines.append(f"&VENT TYPE='WALL' ID='{opening['id']}' COMP_IDS='{opening['a']}','{opening['b']}' WIDTH={opening['width_m']:g} BOTTOM={opening.get('bottom_m',0):g} TOP={opening['top_m']:g} FACE='{opening['face']}' OFFSET={opening.get('offset_m',0):g} {control} /")
    from .ventilation import deck_lines
    lines.extend(deck_lines(model))
    for i,target in enumerate(targets,1):
        mat=target["material"]; pos=np.array(target.get('solver_xyz',target["xyz"]))-rooms[target["room"]]["origin_m"]
        normal=target.get('solver_normal',target['normal'])
        lines.append(f"&MATL ID='M{i}' CONDUCTIVITY={mat['conductivity_W_mK']} DENSITY={mat['density_kg_m3']} SPECIFIC_HEAT={mat['specific_heat_kJ_kgK']} THICKNESS={mat['thickness_m']} EMISSIVITY={mat['emissivity']} /")
        lines.append(f"&DEVC ID='{target['id']}' COMP_ID='{target['room']}' TYPE='PLATE' LOCATION={','.join(map(str,pos))} NORMAL={','.join(map(str,normal))} MATL_ID='M{i}' THICKNESS={mat['thickness_m']} /")
    # Keep fuel device ordering stable; windows are passive, separate targets.
    for target in windows:
        mat=target['material']; mid=target['material_id']
        lines.append(f"&MATL ID='{mid}' CONDUCTIVITY={mat['conductivity_W_mK']} DENSITY={mat['density_kg_m3']} SPECIFIC_HEAT={mat['specific_heat_kJ_kgK']} THICKNESS={mat['thickness_m']} EMISSIVITY={mat['emissivity']} /")
        # Match COMP's nine significant digits exactly: a wall target gets the
        # native exterior rear boundary, instead of two-sided indoor heating.
        pos=','.join(f'{v:.9g}' for v in target['local_xyz'])
        normal=','.join(f'{v:g}' for v in target['normal'])
        lines.append(f"&DEVC ID='{target['id']}' COMP_ID='{target['room']}' TYPE='PLATE' LOCATION={pos} NORMAL={normal} MATL_ID='{mid}' THICKNESS={mat['thickness_m']} /")
    active={f["id"]:{"t_ign_s":f["initial_time_s"],"xyz":f["position_m"],"solver_xyz":f.get('solver_position_m',f['position_m'])} for f in model["fuel_groups"] if "initial_time_s" in f}
    active.update({e["group"]:e for e in committed})
    curves = {}
    if transitions:
        from .flashover import source_curves
        curves, _ = source_curves(model, committed, transitions)
    for group in active_fuels(model,committed):
        rule=group.get('room_rule_trigger')
        event=active.get(group['id']) or {'xyz':group['position_m'],'solver_xyz':group.get('solver_position_m',group['position_m']),'t_ign_s':0}
        room=rooms[group["room"]]
        pos=np.array(event.get('solver_xyz',event["xyz"]))-room["origin_m"]
        if not np.all((pos[:2]>0)&(pos[:2]<np.array(room['size_m'][:2]))) or not 0<=pos[2]<room['size_m'][2]:
            raise ValueError('Fire position is outside its compartment: '+group['id'])
        t,q,area=fire_curve(group, room["size_m"][0]*room["size_m"][1])
        if group['id'] in curves:
            curve=curves[group['id']]
            t=curve['t']-event['t_ign_s']; q=curve['q']; area=curve['area']
        fid='F_'+group["id"]
        trigger=(f"IGNITION_CRITERION='{rule['criterion']}' DEVC_ID='{rule['target_id']}' SETPOINT={rule['setpoint']:.12g}" if rule else
                 f"IGNITION_CRITERION='TIME' SETPOINT={event['t_ign_s']:.12g}")
        lines.append(f"&FIRE ID='{fid}' COMP_ID='{group['room']}' FIRE_ID='{fid}' LOCATION={pos[0]:.8g},{pos[1]:.8g} {trigger} /")
        ratio=primary_ratio(model,group)
        hoc_text=str(group['heat_of_combustion_kJ_kg']) if ratio==1 else format(group['heat_of_combustion_kJ_kg']*ratio,'.12g')
        chemistry=' '.join(f'{key.upper()}={value:.12g}' for key,value in group['formula'].items())
        lines.append(f"&CHEM ID='{fid}' {chemistry} HEAT_OF_COMBUSTION={hoc_text} RADIATIVE_FRACTION=0.35 SOOT_YIELD=0.02 CO_YIELD={group.get('co_yield',.01):.12g} /")
        lines.append(f"&TABL ID='{fid}' LABELS='TIME','HRR','HEIGHT','AREA' /")
        for ti,qi,ai in zip(t,q,area):
            lines.append(f"&TABL ID='{fid}' DATA={ti:.12g},{qi*ratio:.12g},{pos[2]:.12g},{ai:.12g} /")
    return '\n'.join(lines)+'\n'


def gas_sidecar(model):
    gas=model["gas"]
    fields={k:gas[k] for k in ("enabled","bulk_enabled","vent_gate_enabled","gas_ignition_C","hot_C",
                              "fuel_min_mass_fraction","rate_ref_s_inv","reference_K","activation_J_mol",
                              "vent_ignition_C","pilot_assumed","pilot_start_s","pilot_end_s")}
    fields["oxygen_min_vol"]=gas["oxygen_min_vol_percent"]/100
    # Keep diagnostics when reactions are OFF; neither native gate nor RHS changes.
    fields["enabled"]=True
    fields["bulk_enabled"]=gas["enabled"] and gas["bulk_enabled"]
    fields["vent_gate_enabled"]=gas["enabled"] and gas["vent_gate_enabled"]
    if model.get('engine_optimization',{}).get('radiation_cache'):
        fields['radiation_cache_enabled']=True
    if model.get('engine_optimization',{}).get('wall_cache'):
        fields['wall_cache_enabled']=True
    if model.get('engine_optimization',{}).get('adaptive_radiation'):
        fields['adaptive_radiation_enabled']=True
        for key in ('adaptive_min_age_s','adaptive_stable_s','adaptive_refresh_s'):
            fields[key]=model['engine_optimization'][key]
    for flag in ('mixture_enabled','jet_enabled'):
        if gas.get(flag):fields[flag]=True
    if gas.get('mixture_smooth_enabled'):
        for key in ('mixture_smooth_enabled','mixture_o2_width_vol','mixture_temperature_width_C','mixture_fuel_width','mixture_mixing_time_s'):
            fields[key]=gas[key]
    force=model.get('ignition_assumption')
    if force:
        fields.update(force_room=next(i for i,r in enumerate(model['rooms'],1) if r['id']==force['room']),
                      force_time_s=force['time_s'],force_duration_s=force['duration_s'],force_rate_s_inv=force['rate_s_inv'],
                      force_o2_min_vol=force.get('oxygen_min_vol_percent',10.)/100)
    def value(v):
        return ('.TRUE.' if v else '.FALSE.') if isinstance(v,bool) else f'{v:.14g}'
    return '&CFBT\n'+''.join(f' {k}={value(v)}\n' for k,v in fields.items())+'/\n'
