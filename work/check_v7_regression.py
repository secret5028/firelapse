import pathlib,sys,json,os,subprocess,concurrent.futures
W=pathlib.Path(__file__).resolve().parent;CAD=pathlib.Path(r'C:\Users\<user>\Documents\Codex\2026-09-07\2\CAD3D')
env=dict(os.environ,PYTHONPATH=str(W/'cad-deps'),PYTHONIOENCODING='utf-8')
cases=json.loads((W/'cad-runs/regression.json').read_text(encoding='utf8'))
def run(case):
 name=case['label']+'-'+case['floor'];out=W/'cad-v7-regression'/name;out.mkdir(parents=True,exist_ok=True)
 args=[sys.executable,str(CAD/'cad_pipeline.py'),case['source'],str(out),'--floor',case['floor']]
 ref=CAD/'out'/case['building']
 if (ref/(case['floor']+'_fire.json')).exists():args+=['--fire-json',str(ref/(case['floor']+'_fire.json')),'--fire-reference-plan',str(ref/(case['floor']+'.json'))]
 with (out/'run.log').open('w',encoding='utf8') as log:r=subprocess.run(args,env=env,stdout=log,stderr=subprocess.STDOUT)
 if r.returncode:raise RuntimeError(name+' '+(out/'run.log').read_text(encoding='utf8')[-2000:])
 p=json.loads((out/'plan.json').read_text(encoding='utf8'))
 print(name,len(p['rooms']),len(p['simulation_graph']['excluded_openings']),flush=True)
 return dict(sample=name,rooms=len(p['rooms']),errors=p['quality']['errors'],excluded=p['simulation_graph']['excluded_openings'])
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 result=list(pool.map(run,[c for c in cases if c['label']!='office']))
(W/'cad-v7-regression/regression.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')

