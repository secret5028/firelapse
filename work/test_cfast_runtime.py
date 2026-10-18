"""Cache integrity tests using a tiny stand-in process, not a physics validation."""
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
from cfast_runtime import run_native

base=(Path(__file__).resolve().parent.parent/'outputs/CAD-속도검증-v27/runtime-tests').resolve()
base.mkdir(exist_ok=True)
with TemporaryDirectory(dir=base) as tmp:
    p=Path(tmp)
    assert p.resolve().parent==base
    (p/'case.in').write_text('scenario A')
    (p/'case').write_text('''from pathlib import Path
p=Path('count');p.write_text(str(int(p.read_text())+1) if p.exists() else '1')
for suffix in ['_zone.csv','_compartments.csv','_devices.csv','.log']:
 Path('case'+suffix).write_text('verified fixture')
print('Total execution time = 0.01 seconds\\nTotal time steps = 2\\nNormal exit')
''')
    first=run_native(sys.executable,p,'case');assert not first['cache_hit']
    second=run_native(sys.executable,p,'case');assert second['cache_hit'] and (p/'count').read_text()=='1'
    (p/'case.in').write_text('scenario B')
    assert not run_native(sys.executable,p,'case')['cache_hit']
    (p/'case_devices.csv').write_text('corrupted')
    assert not run_native(sys.executable,p,'case')['cache_hit']
    assert not run_native(sys.executable,p,'case',force=True)['cache_hit']
    assert (p/'count').read_text()=='4'
    (p/'case-cache.json').write_text('{incomplete')
    assert not run_native(sys.executable,p,'case')['cache_hit']
    assert (p/'count').read_text()=='5'
    (p/'case').write_text("print('failed simulation')")
    try:run_native(sys.executable,p,'case',force=True)
    except RuntimeError:pass
    else:raise AssertionError('Failed run accepted')
print('PASS: identical input reuse, changed input invalidation, output corruption invalidation, force, malformed cache recovery, failed run rejection')
