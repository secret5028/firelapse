"""One stock CFAST P1 replay in a new folder, after the serial lite queue ends."""
from datetime import datetime, timezone
import msvcrt
from pathlib import Path
import shutil
import time
from run_overnight_floors import OUT, ROOT, CUTOFF, read, save, sha
import run_wando_c11_p1 as p1

def postprocess_evidence(target):
    save(target/'postprocess-evidence.json',dict(recorded_utc=datetime.now(timezone.utc).isoformat(),
         conditions_sha256=sha(ROOT/'simulation/pyrocast_cfbt/conditions.py'),
         analyzer_sha256=sha(ROOT/'tools/run_wando_c11_p1.py'),deck_sha256=sha(target/'case.in'),
         csv_sha256={name:sha(target/name) for name in ('case_compartments.csv','case_masses.csv','case_vents.csv')}))

def analyze_output(target, elapsed):
    """P1's known 3595 s endpoint is explicit; never invent the last 5 s."""
    p1.OUT=target
    data,_,_=p1.read_native_csv(target/'case_compartments.csv')
    end=float(data['Time'][-1])
    if end not in (3595.,3600.) or 'NORMAL EXIT' not in (target/'case.log').read_text(errors='replace').upper():
        raise ValueError('Unexpected P1 termination; retain failed status')
    p1.analyze()
    postprocess_evidence(target)
    save(target/'nightly-status.json',dict(state='complete' if end==3600 else 'partial_output',
         native_normal_exit=True,wall_s=elapsed,last_csv_s=end,requested_end_s=3600,
         missing_endpoint_s=3600-end,interpolated=False,retry=False))

def main():
    with (OUT/'batch.lock').open('r+b') as lock:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        progress=read(OUT/'progress.json')
        if any(r['state'] in ('queued','running') for r in progress['rows']):
            raise RuntimeError('Lite queue still pending')
        if read(OUT/'control.json',{}).get('stop') or datetime.now(timezone.utc)>=datetime.fromisoformat(CUTOFF):
            raise RuntimeError('Batch stopped or expired')
        source=ROOT/'simulation/results/wando_C11_P1_20261102'
        target=OUT/'wando/P1';target.mkdir(parents=True,exist_ok=True)
        if (target/'attempt.json').exists():raise RuntimeError('Wando already attempted; no automatic retry')
        evidence=read(source/'input-evidence.json')
        if sha(source/'case.in')!=evidence['deck_sha256'] or sha(p1.EXE)!=evidence['hashes'][str(p1.EXE.relative_to(ROOT))]:
            raise RuntimeError('Original deck or stock engine hash changed')
        for name in ('case.in','model.json','input-evidence.json'):
            shutil.copyfile(source/name,target/name)
        save(target/'nightly-source.json',dict(source=str(source),original_hashes={name:sha(source/name) for name in ('case.in','model.json','input-evidence.json')},
             engine='cfast_native',origin='CAVITY (R5 wall lining)',floor='1F',duration_s=3600,budget_s=1800,
             opening_state='P1 original schedule, fan OFF',purpose='Representative Wando scenario, not lite comparison'))
        p1.OUT=target;started=time.monotonic()
        save(target/'nightly-status.json',dict(state='running',started_utc=datetime.now(timezone.utc).isoformat()))
        try:
            try:p1.run()
            except ValueError as exc:
                # Stock P1 is known to exit normally at 3600 but emit CSV only
                # through 3595. Preserve the validator failure as evidence.
                if str(exc)!='Native output did not reach the requested horizon':raise
            analyze_output(target,time.monotonic()-started)
        except Exception as exc:
            save(target/'nightly-status.json',dict(state='failed',wall_s=time.monotonic()-started,error=f'{type(exc).__name__}: {exc}',retry=False))
            raise

if __name__=='__main__':main()
