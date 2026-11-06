import pathlib,sys,json,os,subprocess,concurrent.futures
W=pathlib.Path(__file__).resolve().parent;CAD=pathlib.Path(r'C:\Users\<user>\Documents\Codex\2026-09-07\2\CAD3D')
manifest=json.loads((W/'drawing-manifest-v7.json').read_text(encoding='utf8'))
env=dict(os.environ,PYTHONPATH=str(W/'cad-deps'),PYTHONIOENCODING='utf-8')
jobs=[dict(source=r['path'],floor=r['floor'],label='office',building=manifest['building']) for r in manifest['drawings'] if r['role']=='architectural_plan']
jobs += [c for c in json.loads((W/'cad-runs/regression.json').read_text(encoding='utf8')) if c['label']!='office']
def run(c):
 folder='cad-v7-runs' if c['label']=='office' else 'cad-v7-regression';name=c['label']+'-'+c['floor'];out=W/folder/name;out.mkdir(parents=True,exist_ok=True)
 args=[sys.executable,str(CAD/'cad_pipeline.py'),c['source'],str(out),'--floor',c['floor']]
 if c['label']=='office':args+=['--drawing-manifest',str(W/'drawing-manifest-v7.json')]
 if name=='office-1F':args+=['--review-profile',str(W/'office-1F-review-v7.json')]
 if name=='office-PH':args+=['--review-profile',str(W/'office-PH-review-v7.json')]
 root=CAD/'out'/c['building'];floor=c['floor']
 if (root/(floor+'_fire.json')).exists():args+=['--fire-json',str(root/(floor+'_fire.json')),'--fire-reference-plan',str(root/(floor+'.json'))]
 with (out/'run.log').open('w',encoding='utf8') as log:r=subprocess.run(args,env=env,stdout=log,stderr=subprocess.STDOUT)
 if r.returncode:raise RuntimeError(name+' '+(out/'run.log').read_text(encoding='utf8')[-2500:])
 p=json.loads((out/'plan.json').read_text(encoding='utf8'));print(name,'rooms',len(p['rooms']),'uncertain',len(p['simulation_graph']['excluded_openings']),'errors',p['quality']['errors'],flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(run,jobs))
