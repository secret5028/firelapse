"""r8 configuration adapter over the frozen r7 native input structure."""
from copy import deepcopy
from .rule_settings import resolve
from .room_rule_r7 import prepare as prepare_r7

def prepare(raw, *, cell_partitioner=None):
 settings=resolve(raw.get('room_rule_r8',{}));m=deepcopy(raw)
 opened_fire_doors=[]
 for vent in m.get('openings',[]):
  is_fire=vent.get('fire_door') or vent.get('door_type') in ('fire','fire_door') or vent.get('fire_rating_minutes',0)>0
  schedule=vent.get('schedule',[[0,1]])
  if is_fire and schedule[0][1]>0 and all(row[1]==schedule[0][1] for row in schedule):
   opened_fire_doors.append(vent['id']);vent['original_fire_door']=True
   for key in ('fire_door','door_type','fire_rating_minutes'):vent.pop(key,None)
 m['room_rule_r7']={**settings['values'],'room_supply':settings['room_supply']}
 model,targets,manifest=prepare_r7(m,supply_coverage_fraction=settings['values']['coverage_default'] if settings['room_supply']=='room_involvement' else None,cell_partitioner=cell_partitioner)
 model['room_rule_r8']=deepcopy(raw.get('room_rule_r8',{}));model['rule_settings']=settings
 manifest.update(revision='room_rule_r8_frozen',frozen_structure='r7',rule_settings=settings,
                 initially_open_fire_doors=opened_fire_doors)
 manifest['limits']=[line for line in manifest['limits'] if not line.startswith(('within-room 300','passages require'))]+[
  settings['assumption'],'single static parent: other heated/burning neighbours do not override the selected parent',
  'passage sensors use the selected inter-room plate threshold; no bypass',
  'native strict threshold exceedance, 5s observation resolution; no probability interpretation',
  'room_involvement coverage controls standby supply only; initial source curve and total fuel energy remain area allocated']
 return model,targets,manifest


def prepare_native(raw):
    from .physics_config import defaults
    from .native_rooms import coalesce
    from .native_apertures import prepare as prepare_apertures
    model,targets,manifest=prepare(prepare_apertures(raw))
    if model.get('equivalent_apertures'):
        manifest['equivalent_apertures']=deepcopy(model['equivalent_apertures'])
    if defaults('native_compartments')['merge_virtual_cells']:
        return coalesce(model,targets,manifest)
    return model,targets,manifest
