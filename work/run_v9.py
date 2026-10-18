import pathlib,sys,json,os,subprocess,concurrent.futures
W=pathlib.Path(__file__).resolve().parent;CAD=pathlib.Path(r'C:\Users\예방\Documents\Codex\2026-09-07\2\CAD3D')
manifest=json.loads((W/'drawing-manifest-v7.json').read_text(encoding='utf8'))
env=dict(os.environ,PYTHONPATH=str(W/'cad-deps'),PYTHONIOENCODING='utf-8')
OUT=W.parent/'outputs/CAD-평면연결-v9';OUT.mkdir(exist_ok=True)
jobs=[r for r in manifest['drawings'] if r['role']=='architectural_plan']
def run(c):
 floor=c['floor'];out=OUT/('office-'+floor);out.mkdir(exist_ok=True)
 args=[sys.executable,str(CAD/'cad_pipeline.py'),c['path'],str(out),'--floor',floor,'--drawing-manifest',str(W/'drawing-manifest-v7.json')]
 if floor in ('1F','PH'):args+=['--review-profile',str(W/f'office-{floor}-review-v7.json')]
 with (out/'run.log').open('w',encoding='utf8') as log:r=subprocess.run(args,env=env,stdout=log,stderr=subprocess.STDOUT)
 if r.returncode:raise RuntimeError(floor+' '+(out/'run.log').read_text(encoding='utf8')[-2500:])
 p=json.loads((out/'plan.json').read_text(encoding='utf8'));print(floor,'rooms',len(p['rooms']),'cores',len(p['cores']),'ramps',len(p['ramps']),'errors',p['quality']['errors'],flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(run,jobs))
floors=['B1']+[f'{i}F' for i in range(1,8)]+['PH']
args=[sys.executable,str(CAD/'cad_build3d.py'),str(OUT/'building')]+[str(OUT/('office-'+f)/'plan.json') for f in floors]+['--names',','.join(floors),'--levels=-4.2,.9,6.4,11.9,17.4,21.9,26.4,30.9,36.6,39.9']
with (OUT/'assembly.log').open('w',encoding='utf8') as log:r=subprocess.run(args,env=env,stdout=log,stderr=subprocess.STDOUT)
print((OUT/'assembly.log').read_text(encoding='utf8'),flush=True)
if r.returncode:raise SystemExit(r.returncode)
