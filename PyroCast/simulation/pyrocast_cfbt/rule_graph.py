"""r6 fixed-state delay graph. Costs are assumptions, not transport solutions."""
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
            delay=settings['cell_delay_s'];kind='cell'
        elif fraction>0:delay=settings['open_delay_s'];kind='open_aperture'
        else:delay=settings['closed_delay_s'];kind='closed_ordinary_door_assumption'
        for src,dst in pairs:
            e={'from':src,'to':dst,'opening':v['id'],'delay_s':delay,'kind':kind,'initial_fraction':fraction}
            adj[src].append(e);edges.append(e)
    def point(room,v):
        if v.get('type')=='FLOOR':
            other=v['b'] if v['a']==room['id'] else v['a'];above=rooms[other]['origin_m'][2]>room['origin_m'][2]
            return [room['origin_m'][0]+room['size_m'][0]/2,room['origin_m'][1]+room['size_m'][1]/2,room['origin_m'][2]+(room['size_m'][2] if above else 0)]
        # opening_frame adds room a's origin (or uses the CAD absolute point).
        # One aperture has one physical position, independent of traversal side.
        return opening_frame(v,rooms)[0].tolist()
    def passage(rid,entry,exit):
        r=rooms[rid]
        if r.get('core_kind')=='stair':
            return r.get('structural_height_m',r['size_m'][2])*r.get('floor_span_count',1)
        a=point(r,vents[entry]);b=point(r,vents[exit])
        return math.dist(a,b)
    start=(root,'');best={start:0.};previous={};queue=[(0.,root,'')]
    while queue:
        cost,rid,entry=heapq.heappop(queue);key=(rid,entry)
        if cost!=best[key]:continue
        if rid in invalid_sensors and rid not in passing:continue
        for edge in adj[rid]:
            extra=passage(rid,entry,edge['opening'])/settings['passage_speed_m_s'] if rid in passing and entry else 0.
            target=(edge['to'],edge['opening'] if edge['to'] in passing else '')
            distance=cost+edge['delay_s']+extra
            if distance<best.get(target,float('inf')):
                best[target]=distance;previous[target]=(key,{**edge,'passage_delay_s':extra})
                heapq.heappush(queue,(distance,*target))
    result={root:None}
    for rid in sorted(rooms):
        if rid==root or rid in passing or (rid,'') not in best:continue
        path=[];key=(rid,'')
        while key!=start:
            key,e=previous[key];path.append(e)
        path.reverse();parent=root;segment=[]
        for e in path:
            if e['from'] not in passing:parent=e['from'];segment=[]
            segment.append(e)
        result[rid]={'room':parent,'delay_s':sum(e['delay_s']+e['passage_delay_s'] for e in segment),
                     'path':segment,'total_path_delay_s':best[(rid,'')],
                     'passing_rooms':[e['from'] for e in segment if e['from'] in passing]}
    return result,{'edges':edges,'excluded_edges':excluded,'passing_rooms':sorted(passing),
        'unreachable_combustible_rooms':sorted(set(rooms)-passing-set(result)),
        'policy':'Dijkstra with incoming-aperture state for transit distances; stable opening-ID tie order; one route only',
        'limits':['path weights omit future heating/ignition times','closed-door penetration does not open native VENT',
                  'positive fractional openings treated as open in graph; native fraction retained',
                  'internal windows use generic aperture delays; internal glass breakage not modeled',
                  'unclassified doors treated as ordinary; no fire-door inference from nearby room text',
                  'passage length is straight opening-to-opening distance, stairs structural height*floor count; obstacles omitted']}
