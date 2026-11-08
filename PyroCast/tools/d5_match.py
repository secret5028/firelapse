"""Approved predicates evaluated together at one saved cell/time, never at separate peaks."""
from d5_tools import finite, state_at


def matches(rule, values):
    if values.get('physically_invalid') is True:return False
    when = rule.get('when', rule)
    scope = when.get('scope')
    if scope and scope != 'always' and values.get(scope) is not True: return False
    def one(condition):
        key, op, expected = condition; actual = values.get(key)
        if actual is None: return False
        if op == '==': return type(actual) == type(expected) and actual == expected
        if not finite(actual) or not finite(expected): return False
        return {'>=':actual>=expected, '<=':actual<=expected, '<':actual<expected, '>':actual>expected}[op]
    return all(one(c) for c in when.get('all', [])) and (any(one(c) for c in when['any']) if 'any' in when else True)


def match_timelines(timelines, building, route, rules, origin):
    meta = {r['id']:r for r in building['rooms']}
    onroute = {r['id'] for seg in route.get('hose_segments', []) for r in seg['rooms'] if r['id']}
    openings = building['openings']; times = building.get('sample_times', [])
    adjacent = set()
    for opening in openings:
        sides = opening.get('sides', [])
        if origin in sides: adjacent.update(s for s in sides if s != origin)
    origin_first = min((r['time_s'] for c in timelines.get(origin, {}).get('cells', []) for r in c['rows']
                        if finite(r['indices'].get('FO')) and r['indices']['FO'] >= 100), default=None)
    output = []
    for rid, timeline in timelines.items():
        doors = [d for d in openings if rid in d.get('sides', []) and 'door' in (d.get('kind') or '')]
        for cell in timeline.get('cells', []):
            active = {}; previous = None
            for row in cell['rows']:
                t = row['time_s']
                states = [state_at(d,t,times) for d in openings if d['id'] in building.get('supply_opening_ids',[o['id'] for o in openings])]
                validity=row.get('physical_validation',{})
                values = {**row['indices'], 'physically_invalid':validity.get('status')=='physically_invalid',
                    'validity_passed':validity.get('passed') is True,
                    **{k:row.get(k) for k in ('active_fire','BD_potential','FGI_proximity','bd_raw_hazard')}, 'Tu':row['Tu'], 'h':row['h'],
                    'rollover_active':row.get('rollover_active'),
                    'temperature_rising': row['Tu']>previous if finite(row['Tu']) and finite(previous) else None,
                    'route_room':rid in onroute,'on_route':rid in onroute,'fire_room':rid == origin,
                    'stairwell':meta.get(rid,{}).get('stairwell') is True,
                    'entry_count':sum(d.get('route_door') is not False for d in doors) if doors else None,
                    'closed_majority':states.count('closed')>states.count('open') if states and 'unknown' not in states else None,
                    'after_origin_FO':origin_first is not None and t>=origin_first,
                    'adjacent':rid in adjacent,'cavity':meta.get(rid,{}).get('cavity') is True,
                    'external_water':None,'inside_personnel':None}
                matched = {}
                for rule in rules['rules']:
                    if rule['code']=='G-0':continue
                    needs_door=any(c[0]=='door_closed' for c in rule['when'].get('all',[]))
                    for door in (doors if needs_door else [None]):
                        state=state_at(door,t,times) if door else 'unknown'
                        facts={**values,'door_closed':None if state=='unknown' else state=='closed'}
                        if not matches(rule,facts):continue
                        key=(rule['code'],door['id'] if door else None)
                        matched[key]=(rule,facts)
                for key in list(active):
                    if key not in matched:
                        active[key]['t_end']=t;output.append(active.pop(key))
                for key,(rule,facts) in matched.items():
                    if key not in active:
                        active[key]=dict(room=rid,cell=cell['cell'],time_s=t,t_start=t,t_end=None,
                            code=rule['code'],door_id=key[1],text=rule['text'],notice=rules['notice'],
                            ref=rule['ref'],values=facts)
                previous=row['Tu']
            output.extend(active.values())
    return output


def match_case(service,args,route,rules):
    p=service.case(args)
    if p.get('physical_validation',{}).get('status')=='physically_invalid':return []
    ids={c.get('original_room') or c['key'] for c in p['rooms']}
    timelines={rid:service.get_room_timeline({**args,'room':rid}) for rid in ids}
    return match_timelines(timelines,service.get_building(args),route,rules,p.get('fire_key'))
