"""r5 T4 input prescription; no native engine, transport or chemistry changes."""
from collections import deque
from copy import deepcopy

def bfs_parents(model,root):
    adjacency={r['id']:[] for r in model['rooms']}
    for opening in model['openings']:
        a,b=opening['a'],opening['b']
        if a not in adjacency or b not in adjacency or opening.get('type')=='FLOOR' or opening.get('kind')=='window':continue
        schedule=opening.get('schedule',[[0,1.]])
        if any(row[1]!=schedule[0][1] for row in schedule):raise ValueError('T4 requires fixed internal door states')
        if schedule[0][1]<=0:continue
        adjacency[a].append((b,opening['id']));adjacency[b].append((a,opening['id']))
    parents={root:None};queue=deque([root])
    while queue:
        room=queue.popleft()
        for other,opening in adjacency[room]:
            if other in parents:continue
            parents[other]={'room':room,'opening_id':opening};queue.append(other)
    return parents

def prepare_parent(raw):
    from .room_rule import prepare,settings
    rule=settings(raw);base=deepcopy(raw)
    # Reuse r4 aggregation, source heights, numerical cap and disabled extensions.
    base['room_fire_rule']={**rule,'trigger_mode':'ceiling_r4','criterion':'TEMPERATURE','setpoint':500.}
    model,_=prepare(base)
    initial=next(g for g in model['fuel_groups'] if 'initial_time_s' in g)
    parents=bfs_parents(model,initial['room']);excluded=[];groups=[]
    for group in model['fuel_groups']:
        if group['room'] not in parents:excluded.append(group['id']);continue
        if 'initial_time_s' not in group:
            parent=parents[group['room']]
            group['room_rule_trigger']={'criterion':'TEMPERATURE','setpoint':600.,'target_id':'PC_'+parent['room']}
            group['parent_transition']=parent
            curve=group['room_rule_curve'];delay=rule['delay_s']
            curve.update(t=[0.]+[v+delay for v in curve['t']],q=[0.]+curve['q'],area=[curve['area'][0]]+curve['area'],delay_s=delay)
        groups.append(group)
    targets=[]
    for room in model['rooms']:
        if room['id'] not in parents:continue
        if room['size_m'][2]<=.2:raise ValueError('Room too low for T4 parent plate')
        owner=next((g for g in groups if g['room']==room['id']),None)
        xyz=list(owner['position_m']) if owner else [room['origin_m'][i]+room['size_m'][i]/2 for i in range(3)]
        solver=list(owner.get('solver_position_m',xyz)) if owner else list(xyz)
        xyz[2]=solver[2]=room['origin_m'][2]+room['size_m'][2]-.2
        material={**model['material'],'conductivity_W_mK':45.,'density_kg_m3':7850.,'specific_heat_kJ_kgK':.46,'thickness_m':.001,'emissivity':.9}
        targets.append({'id':'PC_'+room['id'],'group':owner['id'] if owner else 'monitor_'+room['id'],
                        'room':room['id'],'xyz':xyz,'solver_xyz':solver,'normal':[0,0,-1],'material':material,
                        'basis':'parent ceiling plate, T4 assumption; not physical flashover','used_for_ignition':True})
    inherited=model['room_fire_rule']
    model.update(fuel_groups=groups,explicit_candidates=targets,
                 room_fire_rule={**rule,'prepared':True,'parent_map':parents,'excluded_unreachable_groups':excluded,
                     'warnings':inherited.get('warnings',[]),'initial_room_excluded_reserve_groups':inherited.get('initial_room_excluded_reserve_groups',[]),
                     'sensor_basis':'cross-compartment parent ceiling plate; first open-door BFS path in input order'})
    return model,targets
