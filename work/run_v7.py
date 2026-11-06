import pathlib,sys,json,os,subprocess
W=pathlib.Path(__file__).resolve().parent;CAD=pathlib.Path(r'C:\Users\<user>\Documents\Codex\2026-09-07\2\CAD3D')
root=CAD/'out/28-200-2026-00000010';env=dict(os.environ,PYTHONPATH=str(W/'cad-deps'),PYTHONIOENCODING='utf-8')
profile=json.loads((W/'office-1F-review-v6.json').read_text(encoding='utf8'))
profile['source_categories']=[] # wall recovery must now stand on general evidence
(W/'office-1F-review-v7.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2),encoding='utf8')
floors=['1F'] if '--office' in sys.argv else ['B1','1F','2F','3F','4F','5F','6F','7F','PH']
if '--rest' in sys.argv:floors=['3F','4F','5F','6F','7F','PH']
mapping={'B1':'015','PH':'014',**{f'{i}F':f'{i+5:03}' for i in range(1,8)}}
for floor in floors:
 src=next((root/'dxf').glob('A31-'+mapping[floor]+'-*.dxf'));out=W/'cad-v7-runs'/('office-'+floor);out.mkdir(parents=True,exist_ok=True)
 args=[sys.executable,str(CAD/'cad_pipeline.py'),str(src),str(out),'--floor',floor,'--drawing-manifest',str(W/'drawing-manifest-v7.json')]
 if floor=='1F':args+=['--review-profile',str(W/'office-1F-review-v7.json')]
 if (root/(floor+'_fire.json')).exists():args+=['--fire-json',str(root/(floor+'_fire.json')),'--fire-reference-plan',str(root/(floor+'.json'))]
 with (out/'run.log').open('w',encoding='utf8') as log:r=subprocess.run(args,env=env,stdout=log,stderr=subprocess.STDOUT)
 if r.returncode:print((out/'run.log').read_text(encoding='utf8'));raise SystemExit(r.returncode)
 p=json.loads((out/'plan.json').read_text(encoding='utf8'))
 print(floor,'rooms',len(p['rooms']),'uncertain',p['simulation_graph']['excluded_openings'],'cross-layer',len(p['layer_evidence']['accepted']),flush=True)
