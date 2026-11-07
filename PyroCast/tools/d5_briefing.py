"""Build a hose-by-hose briefing from saved simulation evidence."""
import re

from d5_match import match_timelines
from d5_tools import finite

LIMITS = '지수 100은 계산상 조건 충족이며 현상 발생 확정 아님. 실 상태는 저장된 표본 기준.'
SIGNS = '화재실 상층 화염·중성대 급강하·개구부 유속 증가 = FO 전조 / 맥동·뜨거운 문·기름 응축 = BD 전조'
PHENOMENA = (('FO', 'FO'), ('FGI', 'FGI'), ('BD', 'backdraft'))
TEMPLATE_VERSION = 'D5/2'
SMOKE_HEIGHT_M = 1.8
DOOR_STATES = {'open': '열림', 'closed': '닫힘', 'unknown': '미확인'}


def space_name(room):
    usage = room.get('usage')
    if usage and usage != '기타(미분류)':
        return '복도·로비' if usage == '교통 공용공간(복도·로비)' else usage
    tokens = {re.sub(r'\s+', '', s) for s in re.split(r' / | · ', room.get('name') or '')}
    # CAD strings also contain dimensions, revisions and nearby equipment notes.
    return next((word for word in ('방풍실', '로비', '복도', '계단실') if word in tokens), '')


def stair_labels(route, floors):
    def floor_label(floor):
        if re.fullmatch(r'\d+F', floor):
            return floor[:-1] + '층'
        if re.fullmatch(r'B\d+', floor):
            return '지하 ' + floor[1:] + '층'
        return floor

    return {
        e['from']: f"{floor_label(floors[e['from']])} → {floor_label(floors[e['to']])} 계단"
        for e in route.get('edges', [])
        if e.get('kind') == 'stair' and floors.get(e['from']) and floors.get(e['to'])
    }


def route_line(route, segment, label, stairs):
    stops = []
    start, end = segment['from_m'], segment['to_m']
    for part in route.get('segments', []):
        if min(end, part['end']) <= max(start, part['start']):
            continue
        rid = part.get('room')
        stop = stairs.get(rid, '계단') if part.get('stair') else label(rid)
        if not stops or stops[-1] != stop:
            stops.append(stop)
    return ' → '.join(stops) or '경로 미평가'


def initial_supply(openings, number):
    groups = {}
    for opening in openings:
        kind = opening.get('kind') or ''
        outside = 'OUTSIDE' in opening.get('sides', [])
        name = ('외부 창' if outside else '창') if 'window' in kind else (
            '외부 문' if outside else '방문') if 'door' in kind else '개구부'
        state = opening.get('initial_state', 'unknown')
        percent = opening.get('initial_percent')
        setting = f'{number(percent)}% 개방' if state == 'open' and finite(percent) else DOOR_STATES[state]
        groups[name, setting] = groups.get((name, setting), 0) + 1
    order = ('외부 창', '창', '외부 문', '방문', '개구부')
    items = sorted(groups.items(), key=lambda item: order.index(item[0][0]))
    return ' · '.join(f'{name} {count}개 {state}' for (name, state), count in items) or '화점실 개구부 미평가'


def fill(service, args):
    from lite_ai_briefing import stamp, number
    from lite_ai_tools import display_label, display_text

    calls = []

    def get(name, **kwargs):
        result = service.call(name, {**args, **kwargs})
        calls.append(result)
        return result['data']

    playback = service.case(args)
    summary = get('get_case_summary')
    origin = summary.get('origin_room') or summary['origin']
    route = get('get_route', origin=playback.get('route_target_room_id') or origin)
    segments = route['hose_segments']
    path = route['route']
    route_ids = list(dict.fromkeys(room['id'] for seg in segments for room in seg['rooms'] if room['id']))
    rules = get('get_tactic_rules')
    building = get('get_building')
    rooms = {r['id']: r for r in building['rooms']}
    short_names = {rid: space_name(room) for rid, room in rooms.items()}
    stairs = stair_labels(path, {rid: room.get('floor') for rid, room in rooms.items()})

    def label(rid):
        if not rid:
            return '외부'
        short = short_names.get(rid)
        return f'{display_label(rid)} ({short})' if short else display_label(rid)

    openings = [o for o in building['openings'] if origin in o.get('sides', [])]
    windows = {tag: get('get_index_windows', room=origin, phenomenon=tag) for tag, _ in PHENOMENA}
    timelines = {
        rid: get('get_room_timeline', room=rid) if service.cells(playback, rid) else {'cells': []}
        for rid in dict.fromkeys([*route_ids, origin])
    }
    matches = match_timelines(timelines, building, route, rules, origin)
    now = args.get('time_s', 0)
    rendered = []

    def interval(row):
        return stamp(row['t_start']) + '–' + (stamp(row['t_end']) if row['t_end'] is not None else '저장 끝')

    def action(row):
        rendered.append(row)
        door = display_text(row['door_id']) + ' · ' if row.get('door_id') else ''
        return f"- {interval(row)} · {door}[{row['code']}] {row['text']}"

    events = {rid: {} for rid in timelines}
    for tag, kind in PHENOMENA:
        for event in summary['events'][kind]:
            if event['room'] in events and finite(event['peak']):
                events[event['room']][tag] = event

    def peak_text(tag, event):
        return f"{tag} {number(event['peak'])} ({stamp(event['peak_s'])})"

    def threshold_status(tag):
        data = windows[tag]
        if data['windows']:
            return ' · '.join(dict.fromkeys(interval(row) for row in data['windows']))
        if data['partial']:
            return '일부 미평가' if data['evaluated'] else '미평가'
        return '기준 미도달' if data['evaluated'] else '미평가'

    origin_progress = []
    for tag, _ in PHENOMENA:
        event = events[origin].get(tag)
        if event is None:
            origin_progress.append(f'{tag} 미평가')
        elif finite(event['first_s']):
            origin_progress.append(f"{tag} 100 최초 {stamp(event['first_s'])} · 최고 {peak_text(tag, event)}")
        else:
            status = '저장값 기준 100 미도달' if event.get('partial') else '100 미도달'
            origin_progress.append(f'{tag} {status} · 최고 {peak_text(tag, event)}')

    all_rows = {rid: [row for cell in data['cells'] for row in cell['rows']] for rid, data in timelines.items()}

    def first_low(rid):
        return min((r for r in all_rows[rid] if finite(r['h']) and r['h'] <= SMOKE_HEIGHT_M),
                   key=lambda r: r['time_s'], default=None)

    smoke = min(((row['time_s'], rid, row['h']) for rid in route_ids if (row := first_low(rid)) is not None),
                default=None)
    if path.get('error'):
        smoke_text = '미평가 · 진입 경로 미확인'
    elif smoke:
        t, rid, h = smoke
        smoke_text = f'{label(rid)}에서 {stamp(t)}에 연기 경계 높이 {number(h)} m (1.8 m 이하 최초 저장 표본)'
    elif any(finite(r['h']) for rid in route_ids for r in all_rows[rid]):
        smoke_text = '평가된 경로 실의 저장 표본에서 연기 경계 높이 1.8 m 이하 미확인'
    else:
        smoke_text = '미평가 · 경로 실의 연기 경계 높이 자료 없음'

    use = rooms.get(origin, {})
    fuel = number(use['load']) + ' MJ/m²' if finite(use.get('load')) else '미평가'
    sections = [dict(title='■ 1. 화재 위험 요약', text='\n'.join([
        f'[{label(origin)}]',
        '',
        '가정',
        f"- 연료: {use['usage']} · {fuel}" if use.get('usage') else f'- 연료: {fuel}',
        '- 급기(초기 저장 입력): ' + initial_supply(openings, number),
        '- 진행(화재 시작 기준): ' + ' / '.join(origin_progress),
        '- 경로: ' + smoke_text,
        '- 확인사항(교재 전조): ' + SIGNS,
    ]))]

    def room_state(rid):
        data = timelines[rid]['cells']
        interface = []
        for cell in data:
            latest = next((r for r in reversed(cell['rows']) if r['time_s'] <= now), None)
            if latest and finite(latest['h']):
                name = display_label(cell['cell']) + ' ' if len(data) > 1 else ''
                interface.append(f"{name}{number(latest['h'])} m ({stamp(latest['time_s'])})")
        hot = max((r for r in all_rows[rid] if finite(r['Tu'])), key=lambda r: r['Tu'], default=None)
        peak = max(events[rid].items(), key=lambda item: item[1]['peak'], default=None)
        if not interface and hot is None and peak is None:
            return None
        parts = ['연기 경계 높이 ' + (' / '.join(interface) or '미평가')]
        low = first_low(rid)
        if low:
            parts.append(f"1.8 m 이하 최초 {stamp(low['time_s'])}")
        parts.append(f"상층 최고온도 {number(hot['Tu'])} ℃ ({stamp(hot['time_s'])})" if hot else '상층 최고온도 미평가')
        parts.append('최고 위험 지수 ' + (peak_text(*peak) if peak else '미평가'))
        return ' · '.join(parts)

    def room_actions(rid):
        found = {}
        for row in matches:
            if row['room'] == rid and row['t_start'] <= now and (row['t_end'] is None or now < row['t_end']):
                found.setdefault((row['code'], row['door_id']), row)
        return found.values()

    if path.get('error'):
        parts = ['진입 경로: 미평가 · ' + display_text(path['error'])]
    else:
        target = '화점실' if path.get('target') == origin else label(path.get('target'))
        parts = [
            f"진입 경로: 차량 → {target} {number(path['length'])} m · 수관 최소 {path['hoses']}본 (모델 경로)",
            f"상태 기준: {stamp(now)} · 최고값은 전체 저장 시간 기준",
        ]
    for seg in segments:
        ids = list(dict.fromkeys(r['id'] for r in seg['rooms'] if r['id']))
        lines = [
            f"{seg['n']}본 ({number(seg['from_m'])}–{number(seg['to_m'])} m)",
            '경로: ' + route_line(path, seg, label, stairs),
        ]
        evaluated = [(rid, state) for rid in ids if (state := room_state(rid)) is not None]
        if not evaluated:
            lines.extend(['상태: 미평가', '할 일: 판정자료 미평가 (실내 구간)' if ids else '할 일: 실 상태 미평가 (외부 구간)'])
        else:
            unassessed = [label(rid) for rid in ids if not any(rid == room for room, _ in evaluated)]
            if unassessed:
                lines.append('미평가 실: ' + ' · '.join(unassessed))
            for i, (rid, state) in enumerate(evaluated, start=1):
                actions = list(room_actions(rid))
                lines.extend([f'{i}. {label(rid)}', '상태: ' + state, '할 일:'])
                lines.extend([action(row) for row in actions] or ['- 현재 시각에 매칭된 교재 규칙 없음'])
        parts.append('\n'.join(lines))

    doors = [o for o in openings if 'door' in (o.get('kind') or '')]
    doorlines = [
        f'화점실 문 앞: {label(origin)}',
        '문 상태: ' + (' · '.join(display_text(o['id']) + ' ' + DOOR_STATES[o['state']] for o in doors) or '미평가'),
        *(f'{tag} 지수 ≥100: {threshold_status(tag)}' for tag in ('BD', 'FGI', 'FO')),
    ]
    origin_actions = [row for row in matches if row['room'] == origin and row['code'] not in ('C-1', 'V-1', 'V-2')]
    seen = {(r['room'], r['code'], r['door_id'], r['t_start'], r['t_end']) for r in rendered}
    origin_actions = [r for r in origin_actions if (r['room'], r['code'], r['door_id'], r['t_start'], r['t_end']) not in seen]
    if origin_actions:
        doorlines.extend(['할 일(조건 충족 시각):', *(action(row) for row in origin_actions)])
    parts.append('\n'.join(doorlines))
    sections.append(dict(title='■ 2. 수관 구간별 할 일', text='\n\n'.join(parts)))

    common = next(rule for rule in rules['rules'] if rule['code'] == 'G-0')
    rendered.append({**common, 'notice': rules['notice']})
    sections.append(dict(title='■ 3. 공통', text='\n'.join([
        f"[G-0] {common['text']} · {rules['notice']}", LIMITS,
    ])))
    text = '\n\n'.join(section['title'] + '\n' + section['text'] for section in sections)
    return dict(building=args['building'], case=args['case'], text=text, sections=sections, facts=[], calls=calls,
                rules=sorted({row['code'] for row in rendered}), proposals=[], status='', matching_log=matches,
                rendered_rules=rendered, template_version=TEMPLATE_VERSION, polishing='offline deterministic', time_s=now)
