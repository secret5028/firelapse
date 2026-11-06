"""Expose saved input/geometry facts to briefing tools without changing inputs."""
from copy import deepcopy
from d5_tools import state_at


def enrich(service, args, result):
    from lite_ai_tools import read
    result = deepcopy(result)
    _, geometry = service.building(args['building'])
    geo_rooms = {'CAD_'+f['name']+'_'+r['id']: (f, r)
                 for f in geometry['floors'] for r in f['rooms']}
    p = service.case(args) if args.get('case') else {}
    path = service.cases(args['building']).get(args.get('case')) if p else None
    raw = {}; sample = {}
    if path:
        # Only siblings of an already authorized saved result, never a path in a request.
        raw = read(path.with_name('input.json'), {}) or read(path.parent.parent/'input.json', {})
        sample = read(path.with_name('sample.json'), {})
    uses = raw.get('approved_input', {}).get('room_uses', {})
    for room in result['rooms']:
        f, g = geo_rooms.get(room['id'], ({}, {}))
        room['cavity'] = g.get('cavity') is True  # Never infer from names.
        room['stairwell'] = ('stair' in g.get('tags', []) or g.get('core_type') == 'stair')
        room['evidence_basis'] = 'geometry; fuel unknown unless saved input supplies it'
        room['usage'] = None; room['load'] = None
        if room['id'] in uses:
            use = uses[room['id']]
            room.update(usage=use.get('label'), load=use.get('load_MJ_m2'),
                        usage_class=use.get('usage_class'), evidence_basis='saved input')
            room['stairwell'] |= use.get('usage_class') == 'stairs'
    # Building core nodes explicitly mark stair spaces, including unevaluated floors.
    for core in geometry.get('core_nodes', []):
        if 'stair' not in str(core.get('kind', core.get('type', ''))): continue
        key = 'CAD_'+str(core.get('floor'))+'_'+str(core.get('room_id'))
        for room in result['rooms']:
            if room['id'] == key: room['stairwell'] = True
    graph = {r['id']: r for r in result['openings']}
    saved = p.get('display_opening_state', {}).get('states', {})
    sample_states = {o['id']: o for o in sample.get('openings', [])}
    raw_openings = {o['id']: o for o in raw.get('openings', [])}
    # Raw CAD IDs are preserved; saved simulation sides map directly to these IDs.
    for key, opening in raw_openings.items():
        if key not in graph and key.startswith('CAD_'):
            graph[key] = dict(id=key, kind=opening.get('kind'), sides=[opening.get('cad_a', opening.get('a')), opening.get('cad_b', opening.get('b'))])
    for key, opening in graph.items():
        source = saved.get(key) or sample_states.get(key) or raw_openings.get(key) or {}
        source = {k: deepcopy(v) for k, v in source.items() if k in ('schedule', 'fraction', 'effective_fraction', 'open')}
        opening.update(source, state=state_at(source, args.get('time_s', 0), p.get('time_s', [])))
        opening['state_basis'] = 'saved case' if source else 'unknown'
    # Wando's native opening mapping is explicitly stored in the playback.
    mapping = {c['solver_id']: c.get('original_room') or c['key'] for c in p.get('rooms', [])}
    for key, value in p.get('opening_states', {}).items():
        target = graph.get(key)
        if target is None and key == 'ENTRY' and geometry.get('building_id') == 'wando-coldstore':
            target = graph.get(geometry.get('route_entry_id'))
        if target is None and key == 'CUT' and geometry.get('building_id') == 'wando-coldstore':
            visual = next((o for f in geometry['floors'] for o in f.get('openings', []) if o['id'] == key), None)
            # CUT is an explicit R5 / CAVITY opening in saved native mapping, not a walking route.
            if visual and mapping.get('ROOM') and mapping.get('CAVITY'):
                target = dict(id='CAD_1F_CUT', kind='door', sides=[mapping['ROOM'], mapping['CAVITY']], route_door=False)
                graph[target['id']] = target
        if target is not None:
            target.update(deepcopy(value), state=state_at(value, args.get('time_s', 0), p.get('time_s', [])), state_basis='saved native schedule')
    # Explicit confirmed supply wins only when its case matches this saved result.
    fixed = result.get('fixed_state')
    for opening in graph.values():
        override = (fixed or {}).get('states', {}).get(opening['id'])
        if override and (not p or (fixed or {}).get('case_id') == args.get('case')):
            opening.update({k: deepcopy(v) for k, v in override.items() if k in ('effective_fraction', 'open')})
            opening.pop('schedule', None); opening.pop('fraction', None)
            opening.update(state=state_at(override, args.get('time_s', 0)), state_basis='confirmed supply')
    result['openings'] = list(graph.values())
    result.update(time_s=args.get('time_s', 0), sample_times=p.get('time_s', []),
                  supply_basis='MC '+str(sample.get('id')) if sample else '확정' if fixed else '저장 입력',
                  saved_input_available=bool(raw))
    return result
