"""Clear-height evidence, independent of structural floor spacing and rendering."""
import hashlib
import json
from pathlib import Path


def apply_clear_heights(project, building, rooms, warnings):
    from .cad import footprint
    from shapely.geometry import Point
    root=Path(project);root=root.parent if root.is_file() else root
    evidence=root/'work/cfast_ceiling_heights_v30.json'
    audit=json.loads(evidence.read_text('utf-8')) if evidence.is_file() else {}
    hashes={};tags_used=0
    floors={f['name']:f for f in building['floors']}
    for room in rooms.values():
        floor=floors[room['cad_floor']];structural=room['structural_height_m']
        raw=next((r for r in floor['rooms'] if r['id']==room['cad_room']),{})
        if room['core_kind']:
            h=structural;basis='dedicated_core_structural_height';confidence='structural_proxy';hits=[]
        else:
            hits=[];expected=floor.get('provenance',{}).get('source_sha256')
            shape=footprint(room['cad_polys'])
            for tag in audit.get('all_tags',[]):
                source=Path(tag['source'])
                if source not in hashes:
                    hashes[source]=hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else None
                # The old building JSON hash differs after geometry/render updates.
                # Require the same actual DXF and remap native coordinates into today's polygons.
                if not expected or hashes[source]!=expected:continue
                point=[tag['native_point'][i]*.001*floor.get('scale',1.)+floor['shift'][i]-building['origin'][i] for i in (0,1)]
                if shape.buffer(.05).covers(Point(point)) and 1.8<=tag['height_m']<=structural:
                    hits.append({**tag,'position':point,'source_sha256':expected})
            explicit=raw.get('clear_height_m') or raw.get('ceil_h')
            if explicit:
                h=float(explicit);basis='explicit_room_clear_height';confidence='declared'
            elif hits:
                h=max(t['height_m'] for t in hits);basis='verified_DXF_height_tag_remapped_to_current_room';confidence='tag_interpretation';tags_used+=1
                if len({t['height_m'] for t in hits})>1:warnings.append('반자고 표기 충돌, 최대값 사용: '+room['id'])
            elif floor.get('ceil_h'):
                h=float(floor['ceil_h']);basis='floor_clear_height';confidence='declared_floor_default'
            else:
                h=structural;basis='structural_height_fallback_clear_height_unconfirmed';confidence='unconfirmed'
                warnings.append('반자 높이 미확인 → 구조 층고 사용: '+room['id'])
        if not 1.8<=h<=structural:raise ValueError('Invalid clear height: '+room['id'])
        room.update(height_m=h,clear_height_m=h,height_basis=basis,height_confidence=confidence,ceiling_tags=hits)
    if tags_used:warnings.append(f'원본 DXF 해시·현재 실 형상으로 반자 높이 표기 {tags_used}실 대조. 반자 위 빈 공간은 별도 해석하지 않음.')
