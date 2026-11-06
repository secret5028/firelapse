import pathlib,sys,json,hashlib
W=pathlib.Path(__file__).resolve().parent;CAD=pathlib.Path(r'C:\Users\<user>\Documents\Codex\2026-09-07\2\CAD3D');sys.path[:0]=[str(W/'cad-deps'),str(CAD)]
from cad_pipeline import finalize_plan
from cad_review_rules import apply_source_review
from cad_evidence import geometry,polygon_parts
from cadio import load,units_to_m
manifest=json.loads((W/'drawing-manifest-v7.json').read_text(encoding='utf8'))
ph=W/'cad-v7-runs/office-PH';base=json.loads((ph/'architecture.json').read_text(encoding='utf8'));r=next(r for r in base['rooms'] if r['id']=='R0');g=geometry(polygon_parts(r));lo=g.bounds
profile=dict(source_sha256=base['provenance']['source_sha256'],non_compartment_regions=[dict(bounds_m=[lo[0]-.1,lo[1]-.1,lo[2]+.1,lo[3]+.1],kind='roof_surface',note='원본 동일 영역 내부의 지붕SL바닥 표기를 대조: 옥상 지붕면을 실내 구획에서 제외하고 참고 형상으로 보존')])
(W/'office-PH-review-v7.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2),encoding='utf8')
src=next(r['path'] for r in manifest['drawings'] if r.get('floor')=='PH');doc,prims,_=load(src)
base['source_review']=apply_source_review(src,prims,['other']*len(prims),profile)
# These are finalization-only changes. Preserve extraction provenance; record
# the latest review/finalization modules which actually execute below.
for folder in (W/'cad-v7-runs',W/'cad-v7-regression'):
 for out in folder.iterdir():
  if not out.is_dir() or not (out/'architecture.json').exists():continue
  p=base if out.name=='office-PH' else json.loads((out/'architecture.json').read_text(encoding='utf8'))
  current=json.loads((out/'plan.json').read_text(encoding='utf8'));p['source_coverage']=current.get('source_coverage',{})
  # apply_source_review itself is unchanged; new space review is a finalizer.
  p['provenance']['code_sha256']['cad_review_rules.py']=hashlib.sha256((CAD/'cad_review_rules.py').read_bytes()).hexdigest()
  floor=current['floor'];case=next((c for c in json.loads((W/'cad-runs/regression.json').read_text(encoding='utf8')) if out.name==c['label']+'-'+c['floor']),None)
  fire=ref=None
  if case:
   root=CAD/'out'/case['building']
   if (root/(floor+'_fire.json')).exists():fire=root/(floor+'_fire.json');ref=root/(floor+'.json')
  p=finalize_plan(p,out,floor=floor,fire_json=fire,fire_reference_plan=ref)
  assert not p['quality']['errors'];print(out.name,len(p['rooms']),flush=True)
