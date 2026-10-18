"""Run the unchanged native CFAST executable; cache only complete, matching runs."""
from pathlib import Path
import hashlib,json,re,subprocess,time

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def run_native(exe,folder,stem,flags=(),force=False,timeout=3600):
    folder=Path(folder);exe=Path(exe)
    signature=dict(engine_sha256=sha(exe),input_sha256=sha(folder/f'{stem}.in'),flags=list(flags))
    cache=folder/f'{stem}-cache.json';timing=folder/f'{stem}-timing.json'
    started=time.perf_counter()
    if cache.exists() and not force:
        try:saved=json.loads(cache.read_text('utf8'))
        except (OSError,ValueError):saved={}
        if isinstance(saved,dict) and saved.get('signature')==signature and saved.get('files') and all((folder/name).is_file() and sha(folder/name)==digest for name,digest in saved['files'].items()):
            return dict(saved['timing'],cache_hit=True,lookup_seconds=time.perf_counter()-started)
    with (folder/f'{stem}-execution.log').open('w') as log:
        p=subprocess.Popen([str(exe),stem,*flags],cwd=folder,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL)
        progress=[]
        while p.poll() is None:
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                elapsed=time.perf_counter()-started
                status=folder/f'{stem}.status'
                if status.exists():
                    with status.open(errors='replace') as f:line=f.readline().strip()
                    progress.append(dict(wall_seconds=elapsed,status=line))
                    (folder/f'{stem}-progress.json').write_text(json.dumps(progress),'utf8')
                if elapsed>timeout:
                    p.kill();p.wait();raise TimeoutError('CFAST exceeded execution limit; incomplete result was not cached')
    elapsed=time.perf_counter()-started
    log=(folder/f'{stem}-execution.log').read_text(errors='replace')
    if p.returncode!=0 or 'NORMAL EXIT' not in log.upper():raise RuntimeError(log[-5000:])
    cpu=re.search(r'execution time\s*=\s*([\d.eE+\-]+)',log,re.I)
    steps=re.search(r'Total time steps\s*=\s*(\d+)',log,re.I)
    result=dict(wall_seconds=elapsed,cpu_seconds=float(cpu.group(1)),steps=int(steps.group(1)),cache_hit=False,signature=signature)
    timing.write_text(json.dumps(result,indent=2),'utf8')
    # Native output is still parsed and checked by the caller on every invocation.
    paths=[folder/f'{stem}{suffix}' for suffix in ['_zone.csv','_compartments.csv','_devices.csv','.log','-execution.log']]
    assert all(p.exists() and p.stat().st_size>0 for p in paths), 'Missing required native output'
    temporary=cache.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(dict(signature=signature,files={p.name:sha(p) for p in paths},timing=result),indent=2),'utf8')
    temporary.replace(cache)
    return result
