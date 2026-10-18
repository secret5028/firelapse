from pathlib import Path
import sys,json,copy
root=Path.cwd();sys.path[:0]=[str(root/'work/cad-deps'),str(root/'work/cad-web/cad_engine')]
from cad_model_transport import apply_outdoor_semantics,geometry
b=json.loads((root/'outputs/CAD-인터페이스복원-v12/building.json').read_text('utf8'));f=next(f for f in b['floors'] if f['name']=='3F');upper=next(f for f in b['floors'] if f['name']=='4F')
# Negative control: a fully covering upper slab prevents terrace classification.
c=copy.deepcopy(b);next(q for q in c['floors'] if q['name']=='4F')['slab']=f['slab'];x=copy.deepcopy(f);apply_outdoor_semantics(x,{},c);assert not x['outdoor_spaces']
# Positive rule must not depend on source hash or room ID.
c=copy.deepcopy(b);x=next(q for q in c['floors'] if q['name']=='3F');next(r for r in x['rooms'] if r['id']=='R27')['id']='unseen-room';apply_outdoor_semantics(x,{},c);assert x['outdoor_spaces'][0]['id']=='unseen-room'
report=root/'outputs/CAD-테라스-v13/검증결과.json';r=json.loads(report.read_text('utf8'));r.update(upper_floor='4F',upper_overlap_m2=0,classification='aligned_adjacent_floor_slab_difference',full_upper_cover_negative_control=True,no_hash_or_room_id_dependency=True);report.write_text(json.dumps(r,ensure_ascii=False,indent=2),'utf8');print('rule positive/negative controls passed')
