"""Auditable CAD corrections; source drawings/building JSON remain read-only."""
from pathlib import Path
from copy import deepcopy
import json

REPAIRS=Path(__file__).resolve().parents[1]/'data/cad_topology_corrections.json'


def corrected_building(building,source_sha,path=REPAIRS):
    if not path.is_file():return building,[]
    records=json.loads(path.read_text('utf-8')).get('buildings',[])
    record=next((r for r in records if r['building_sha256']==source_sha),None)
    if record is None:return building,[]
    b=deepcopy(building);applied=[]
    for change in record['changes']:
        floor=next(f for f in b['floors'] if f['name']==change['floor'])
        if floor.get('provenance',{}).get('source_sha256')!=change['source_sha256']:
            raise ValueError('CAD correction evidence does not match source DXF')
        if change['action']=='classify_outdoor':
            room=next(r for r in floor['rooms'] if r['id']==change['id'])
            room['tags']=list(dict.fromkeys([*room.get('tags',[]),'outdoor','terrace']))
            room['names']=[change['name']];room['usage_candidate']='outdoor_terrace'
            room['classification_correction']=change
            from .outdoor import correct_terrace_geometry
            correct_terrace_geometry(floor,room,change,building=b)
            applied.append(change);continue
        if change['action']=='reclassify_door':
            opening=next(o for o in floor['openings'] if o['id']==change['id'])
            connection=next(o for o in floor['simulation_graph']['connections'] if o['id']==change['id'])
            if set(connection['sides'])!=set(change['sides']):raise ValueError('CAD correction endpoints changed')
            opening['kind']=connection['kind']='door_service'
            connection['dimensions'].update(width_m=change['width_m'],bottom_m=0.,top_m=change['height_m'])
        elif change['action']=='add_open_passage':
            if any(o['id']==change['id'] for o in floor['openings']):raise ValueError('Duplicate corrected CAD opening')
            opening={'id':change['id'],'kind':'open_passage','sides':change['sides'],'polys':[change['polygon']['o']]}
            connection={'id':change['id'],'kind':'open_passage','sides':change['sides'],
                        'dimensions':{'width_m':change['width_m'],'bottom_m':0.,'top_m':change['height_m']}}
            floor['openings'].append(opening);floor['simulation_graph']['connections'].append(connection)
        else:raise ValueError('Unsupported CAD correction action')
        opening['topology_correction']=connection['topology_correction']=change
        applied.append(change)
    return b,applied


def vertical_selection(building,fire_floor):
    """Remote cores plus their actual adjoining access rooms, never whole remote floors."""
    selected={}
    for f in building['floors']:
        if f['name']==fire_floor:continue
        nodes=[n for n in building.get('core_nodes',[]) if n['floor']==f['name']]
        core_ids={n['room_id'] for n in nodes if n.get('room_id')}
        keep=core_ids|{k for n in nodes for k in n.get('access_room_ids',[]) if k!='out'}
        for v in f.get('simulation_graph',{}).get('connections',[]):
            if core_ids.intersection(v['sides']):keep.update(k for k in v['sides'] if k!='out')
        selected[f['name']]=keep
    return selected
