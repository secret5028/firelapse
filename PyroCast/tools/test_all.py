"""Run the source regression inventory serially, keeping skips separate from passes."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from restore_saved_results import restore

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--only', help='Comma-separated script names, or simulation')
    args = parser.parse_args()
    out = (args.output or Path(tempfile.mkdtemp(prefix='firelapse-tests-'))).resolve()
    out.mkdir(parents=True, exist_ok=True)
    print('Restored archived inputs:', restore(ROOT), flush=True)
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1',
               PYTHONPATH=os.pathsep.join(str(ROOT/p) for p in ('tools','simulation','simulation/deps')),
               FIRELAPSE_DATA_DIR=str(out/'data'), TEMP=str(out/'tmp'), TMP=str(out/'tmp'))
    (out/'tmp').mkdir(exist_ok=True)
    env.setdefault('PYROCAST_THREE', str(ROOT/'cad-project/work/cad-web/local-resources/cad-assets/three.module.js'))
    # A PowerShell 7 parent can export a module path unsuitable for Windows PowerShell.
    for key in list(env):
        if key.upper() == 'PSMODULEPATH':
            del env[key]
    node = shutil.which('node')
    if not node:
        raise SystemExit('Node.js is required for the JS regression suite.')
    py = [sys.executable, '-B', '-X', 'utf8']
    jobs = [('simulation', py+['-m','unittest','discover','-v','-s','simulation/tests'])]
    for p in sorted((ROOT/'app/tests').iterdir()):
        if p.name.endswith(('.test.py','.unit.py','_test.py')):
            jobs.append((p.name, py+[str(p),'-v']))
        elif p.name.endswith(('.test.mjs','.unit.mjs')):
            extra = []
            if p.name in ('route.test.mjs','route_layer.test.mjs'):
                extra = [str(ROOT/'cad-project/building.json'),env['PYROCAST_THREE']]
            elif p.name in ('route_floor_context.test.mjs','result_scope.test.mjs'):
                extra = [env['PYROCAST_THREE']]
            jobs.append((p.name,[node,str(p),*extra]))
        elif p.name.endswith('test.ps1'):
            # Explicit import avoids command discovery differences in embedded shells.
            command = "Import-Module Microsoft.PowerShell.Utility; & '"+str(p).replace("'","''")+"'"
            jobs.append((p.name,['powershell','-NoProfile','-ExecutionPolicy','Bypass','-Command',command]))
    selected = set(args.only.split(',')) if args.only else None
    if selected and selected-{name for name,_ in jobs}:
        raise SystemExit('Unknown test name: '+str(selected-{name for name,_ in jobs}))
    rows = []
    for name,cmd in jobs:
        if selected and name not in selected:
            continue
        started = time.monotonic()
        try:
            proc = subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,timeout=600 if name=='simulation' else 180)
            content = (proc.stdout+proc.stderr).decode('utf8','replace')
            code = proc.returncode
        except subprocess.TimeoutExpired as exc:
            content = 'TIMEOUT\n'+((exc.stdout or b'')+(exc.stderr or b'')).decode('utf8','replace')
            code = 124
        (out/(name+'.log')).write_text(content,'utf8')
        skips = [line for line in content.splitlines() if 'SKIP:' in line or 'skipped ' in line]
        match = re.search(r'Ran (\d+) tests?',content)
        row = dict(name=name,exit_code=code,seconds=round(time.monotonic()-started,2),
                   tests=int(match[1]) if match else None,skips=skips,
                   status='FAIL' if code else 'PASS_WITH_SKIPS' if skips else 'PASS')
        rows.append(row)
        (out/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8')
        print(json.dumps({k:v for k,v in row.items() if k!='skips'},ensure_ascii=False),flush=True)
    print('Report:',out)
    return int(any(row['exit_code'] for row in rows))

if __name__ == '__main__':
    raise SystemExit(main())
