import pathlib,sys,json,os,subprocess
W=pathlib.Path(__file__).resolve().parent;CAD=pathlib.Path(r'C:\Users\예방\Documents\Codex\2026-09-07\2\CAD3D')
old=json.loads((W.parent/'outputs/CAD-벽공리-v5/office-1F/plan.json').read_text(encoding='utf8'))
raw=json.loads((W/'raw8-hall.json').read_text(encoding='utf8'))
profile=dict(source_sha256=old['provenance']['source_sha256'],source_categories=[dict(handle=p['source']['handle'],expected_layer='TEX',category='wall',note='D18 아래 문틀부터 기존 하부 경계까지 원본 벽선 복구. 단차·무대 전체를 새 실로 폐합하지 않음') for p in raw if p['index']==4444],exclude_candidates=[])
for alias,reason,note in [('W65','surface_line_on_continuous_wall','연속 벽면의 선을 창으로 오인: 벽은 유지'),('W89','repeated_grating_detail','기둥 하부 반복 빗살 상세를 창으로 오인')]:
 o=next(o for o in old['openings'] if o['id']==alias);pts=[q for poly in o['polys'] for q in poly];xs,ys=zip(*pts)
 profile['exclude_candidates'].append(dict(alias=alias,reason=reason,note=note,bounds_m=[min(xs)-.15,min(ys)-.15,max(xs)+.15,max(ys)+.15]))
(W/'office-1F-review-v6.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2),encoding='utf8')
case=next(c for c in json.loads((W/'cad-runs/regression.json').read_text(encoding='utf8')) if c['label']=='office' and c['floor']=='1F')
out=W/'cad-v6-runs/office-1F';out.mkdir(parents=True,exist_ok=True)
env=dict(os.environ,PYTHONPATH=str(W/'cad-deps'),PYTHONIOENCODING='utf-8')
args=[sys.executable,str(CAD/'cad_pipeline.py'),case['source'],str(out),'--floor','1F','--review-profile',str(W/'office-1F-review-v6.json'),'--fire-json',str(CAD/'out'/case['building']/'1F_fire.json'),'--fire-reference-plan',str(CAD/'out'/case['building']/'1F.json')]
if not (CAD/'out'/case['building']/'1F_fire.json').exists():args=args[:args.index('--fire-json')]
with (out/'run.log').open('w',encoding='utf8') as log:r=subprocess.run(args,env=env,stdout=log,stderr=subprocess.STDOUT)
print('exit',r.returncode,flush=True)
if r.returncode:print((out/'run.log').read_text(encoding='utf8'));sys.exit(r.returncode)
p=json.loads((out/'plan.json').read_text(encoding='utf8'));print('rooms',len(p['rooms']),'excluded',p['simulation_graph']['excluded_openings'])
for id in ['D6','D7','D8','D13','D16','D17','D18']:
 o=next((o for o in p['openings'] if o['id']==id),None);print(id,[(k,o.get(k)) for k in ('sides','leaves')] if o else None)
