"""Serial, isolated comparisons; never modify the installed scenario."""
from pathlib import Path
import argparse,subprocess,time,json,re,hashlib,os
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'outputs/CAD-속도검증-v27';OUT.mkdir(exist_ok=True)
BASE=ROOT/'outputs/CAD-조건부전이-v26/multifloor.in'
EXE=ROOT/'work/smokeview-demo/firemodels/cfast7/cfast.exe'
def run(name,deck,timeout=3600,flags=None):
    dest=OUT/name;dest.mkdir(exist_ok=True)
    if (dest/'benchmark.json').exists():return json.loads((dest/'benchmark.json').read_text('utf8'))
    (dest/'case.in').write_text(deck,'ascii')
    start=time.perf_counter()
    with (dest/'execution.log').open('w') as log:
        p=subprocess.Popen([str(EXE),'case',*(flags or [])],cwd=dest,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
        (OUT/'active.json').write_text(json.dumps(dict(name=name,pid=p.pid,started=time.time())),'utf8')
        progress=[]
        while p.poll() is None:
            try:code=p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                elapsed=time.perf_counter()-start
                status=dest/'case.status'
                if status.exists():
                    with status.open(errors='replace') as f: line=f.readline().strip()
                    progress.append(dict(wall_seconds=elapsed,status=line))
                    (dest/'progress.json').write_text(json.dumps(progress),'utf8')
                if elapsed>timeout:p.kill();p.wait();break
        code=p.returncode
    elapsed=time.perf_counter()-start
    log=(dest/'execution.log').read_text(errors='replace')
    def find(pattern):
        m=re.search(pattern,log,re.I);return float(m.group(1)) if m else None
    r=dict(name=name,wall_seconds=elapsed,engine_seconds=find(r'execution time\s*=\s*([\d.eE+\-]+)'),
        steps=find(r'Total time steps\s*=\s*(\d+)'),normal_exit='Normal exit' in log and code==0,
        engine_sha256=hashlib.sha256(EXE.read_bytes()).hexdigest(),input_sha256=hashlib.sha256(deck.encode('ascii')).hexdigest(),
        flags=flags or [], output_bytes=sum(p.stat().st_size for p in dest.iterdir() if p.is_file()))
    (dest/'benchmark.json').write_text(json.dumps(r,indent=2),'utf8');print(json.dumps(r),flush=True)
    return r
def deck(duration=120,keyboard=False,lean=False):
    s=BASE.read_text('ascii')
    s=re.sub(r'&TIME .*? /',f'&TIME SIMULATION={duration+1} PRINT={0 if lean else 120} SMOKEVIEW={0 if lean else 5} SPREADSHEET=5 /',s)
    if keyboard:s=s.replace('&TAIL /',"&DIAG KEYBOARD_INPUT='OFF' /\n&TAIL /")
    return s
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--screen',action='store_true');a=parser.parse_args()
    if a.screen:
        for name,k,l in [('baseline120',False,False),('keyboard120',True,False),('lean120',False,True),('lean_keyboard120',True,True)]:
            run(name,deck(120,k,l),300)
