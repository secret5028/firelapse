"""r7 immediate-parent delay graph. Costs are assumptions, not transport solutions."""
import heapq,math
from .deck import opening_frame


def delay_parents(model,root,passing,invalid_sensors,settings):
    rooms={r['id']:r for r in model['rooms']};adj={rid:[] for rid in rooms};excluded=[];edges=[]
    vents={v['id']:v for v in model['openings']}
    for v in sorted(model['openings'],key=lambda x:x['id']):
        a,b=v['a'],v['b']
        if a not in rooms or b not in rooms:continue
        schedule=v.get('schedule',[[0,1]])
        if any(f!=schedule[0][1] for _,f in schedule):raise ValueError('r6 does not support dynamic internal opening schedules')
        if v.get('fire_door') or v.get('door_type') in ('fire','fire_door') or v.get('fire_rating_minutes',0)>0:
            excluded.append({'opening':v['id'],'reason':'fire_door'});continue
        fraction=schedule[0][1];pairs=[(a,b),(b,a)]
        if v.get('type')=='FLOOR':
            if fraction<=0:excluded.append({'opening':v['id'],'reason':'closed_vertical'});continue
            if rooms[a]['origin_m'][2]==rooms[b]['origin_m'][2]:
                excluded.append({'opening':v['id'],'reason':'vertical_direction_ambiguous_equal_floor_elevation'});continue
            pairs=[(a,b)] if rooms[a]['origin_m'][2]<rooms[b]['origin_m'][2] else [(b,a)]
            delay=settings['vertical_delay_s'];kind='vertical_up'
        elif v.get('virtual_cell_boundary'):
            delay=math.dist([rooms[a]['origin_m'][i]+rooms[a]['size_m'][i]/2 for i in (0,1)],
                            [rooms[b]['origin_m'][i]+rooms[b]['size_m'][i]/2 for i in (0,1)])/settings['v_spread_m_s'];kind='cell'
        elif fraction>0:delay=settings['open_delay_s'];kind='open_aperture'
        else:delay=settings['closed_delay_s'];kind='closed_ordinary_door_assumption'
        for src,dst in pairs:
            e={'from':src,'to':dst,'opening':v['id'],'delay_s':delay,'kind':kind,'initial_fraction':fraction}
            adj[src].append(e);edges.append(e)
    # Immediate parents, including unfuelled passages. No passage bypass.
    best={root:0.};parents={root:None};queue=[(0.,root)]
    while queue:
        cost,rid=heapq.heappop(queue)
        if cost!=best[rid]:continue
        for edge in adj[rid]:
            distance=cost+edge['delay_s'];dst=edge['to']
            if distance<best.get(dst,float('inf')):
                best[dst]=distance
                parents[dst]={'room':rid,'delay_s':edge['delay_s'],'path':[edge],
                    'total_path_delay_s':distance,'passing_rooms':[rid] if rid in passing else [],
                    'trigger_kind':'cell_flame' if edge['kind']=='cell' and rid not in passing else 'inter_room',
                    'parent_is_passage':rid in passing}
                heapq.heappush(queue,(distance,dst))
    return parents,{'edges':edges,'excluded_edges':excluded,'passing_rooms':sorted(passing),
        'unreachable_combustible_rooms':sorted(set(rooms)-passing-set(parents)),
        'policy':'Dijkstra, immediate adjacent parent; no L/v and no passage skipping',
        'limits':['one static shortest-delay route; actual heating times not part of path choice',
                  'closed-door penetration does not open native VENT; unclassified doors ordinary',
                  'passage sensor can trigger from incoming heat without local fire',
                  'cell distance in solver floor geometry; native rectangular partition is an approximation']}
