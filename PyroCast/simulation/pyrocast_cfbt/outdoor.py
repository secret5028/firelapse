"""User-confirmed outdoor spaces; preserved solver results are labelled, not rewritten."""
from copy import deepcopy


def correct_terrace_geometry(floor,room,policy,building=None):
    from .cad import footprint,polygon_data
    from shapely.ops import unary_union
    terrace=footprint(room['polys'])
    indoors=unary_union([footprint(r['polys']) for r in floor['rooms'] if 'outdoor' not in r.get('tags',[])])
    # Retain the real shared indoor facade. Only the exposed terrace rim loses
    # the erroneous full-storey extrusion. Its low barrier height is a display proxy.
    exposed=terrace.buffer(.35).difference(indoors.buffer(.55))
    height=policy['display_barrier_height_m'];bands=[]
    for band in floor.get('bands',[]):
        if band['kind'] not in ('wall','win_low','win_head','door_head'):
            bands.append(band);continue
        shape=footprint(band['polys']);outside=shape.intersection(exposed);inside=shape.difference(exposed)
        if not inside.is_empty:bands.append({**band,'polys':polygon_data(inside)})
        top=min(height,band['z1'])
        if not outside.is_empty and top>band['z0']:
            bands.append({**band,'z1':top,'polys':polygon_data(outside),'height_basis':'unconfirmed_terrace_barrier_display_proxy'})
    floor['bands']=bands
    for key in ('ceiling','render_ceiling'):
        if floor.get(key):floor[key]=polygon_data(footprint(floor[key]).difference(terrace.buffer(.02)))
    for top in (building or {}).get('structural_tops',[]):
        if top['from_floor']!=floor['name']:continue
        for key in ('roof_polys','ceiling_polys'):
            if top.get(key):top[key]=polygon_data(footprint(top[key]).difference(terrace.buffer(.02)))
    floor.setdefault('classification_notes',[]).append(f"{room['id']} 테라스: 실내 계산 제외. 노출 테두리 높이 {height:g}m는 표시용 기본값이며 실제 난간 치수 미확인.")


def present_corrected_playback(payload,building):
    """Exclude corrected outdoor display objects without pretending to rerun CFAST."""
    outside={f"CAD_{f['name']}_{r['id']}" for f in building['floors'] for r in f['rooms'] if 'outdoor' in r.get('tags',[])}
    removed=[r for r in payload.get('rooms',[]) if r['key'] in outside]
    if not removed:return payload
    d=deepcopy(payload);keys={r['key'] for r in removed};solvers={r['solver_id'] for r in removed}
    d['rooms']=[r for r in d['rooms'] if r['key'] not in keys]
    d['fires']=[f for f in d.get('fires',[]) if f['cad_key'] not in keys]
    d['solid_groups']=[g for g in d.get('solid_groups',[]) if g['cad_key'] not in keys]
    d['ceiling_jets']=[j for j in d.get('ceiling_jets',[]) if j['room'] not in solvers]
    d['presentation_room_exclusions']=sorted(keys)
    note='테라스 분류 정정: R27은 외부 공간으로 표시·선택·연료 기호에서 제외. 현재 수치는 정정 전 저장 계산이며 새 구획으로 재계산한 결과가 아닙니다.'
    d.setdefault('input_warnings',[]).append(note);d.setdefault('limitations',[]).append(note)
    d['geometry_correction_notice']=note
    summary=d.get('fire_scope_summary')
    if summary:
        d['original_fire_scope_summary']=deepcopy(summary)
        summary['room_count']=len(d['rooms'])
        for key in ('registered_rooms','observed_solid_rooms'):summary[key]=[rid for rid in summary[key] if rid not in solvers]
        if 'target_rooms' in summary:summary['target_met']=len(summary['observed_solid_rooms'])>=summary['target_rooms']
    return d
