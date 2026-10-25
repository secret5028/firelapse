"""Link the real built source into a small state/stock/conservation harness."""
from pathlib import Path
import csv
import json
import subprocess
import argparse

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--build',type=Path,default=ROOT/'build/mixture_r2/cfbt')
parser.add_argument('--output',type=Path,default=ROOT/'results/mixture_r2_20261022/source_checks')
parser.add_argument('--smooth',action='store_true')
parser.add_argument('--mixing-time',type=float,default=1.)
options=parser.parse_args()
build=options.build.resolve()
out=options.output.resolve()
out.mkdir(parents=True,exist_ok=True)
args=[str(ROOT/'tools/w64devkit/bin/gfortran.exe'),'-O1','-ffree-line-length-none',
      '-I',str(build),str(Path(__file__).with_name('mixture_source.f90')),
      *[str(p) for p in build.glob('*.o') if p.name!='cfast.o'],'-o',str(out/'source-check.exe')]
compiled=subprocess.run(args,capture_output=True)
if compiled.returncode:raise RuntimeError(compiled.stderr.decode('utf-8',errors='replace'))
(out/'source-check.cfbt').write_text('&CFBT enabled=.TRUE. bulk_enabled=.TRUE. mixture_enabled=.TRUE. '
    'gas_ignition_C=20 oxygen_min_vol=.001 activation_J_mol=0 fuel_min_mass_fraction=1.e-12 '+
    (f'mixture_smooth_enabled=.TRUE. mixture_mixing_time_s={options.mixing_time} ' if options.smooth else '')+'/\n',encoding='ascii')
tested=subprocess.run([str(out/'source-check.exe'),*(['smooth',str(options.mixing_time)] if options.smooth else [])],cwd=out,capture_output=True)
if tested.returncode:raise RuntimeError(tested.stderr.decode('utf-8',errors='replace'))
text=tested.stdout.decode('ascii').replace('\r\r\n','\n')
(out/'source-budget.csv').write_text(text,encoding='utf-8')
rows=list(csv.DictReader(text.splitlines()))
report={'cases':['FUEL only','CO only','mixed','oxygen zero','no combustible',
                 'temperature blocked','native oxygen reserved','native fuel/CO reserved'],
        'source_checks_passed':len(rows),
        'maximum_absolute_mass_residual_kg_s':max(abs(float(r['mass_residual_kg_s'])) for r in rows),
        'maximum_absolute_element_residual_kg_s':max(abs(float(r[k])) for r in rows for k in
            ('C_residual_kg_s','H_residual_kg_s','O_residual_kg_s')),
        'maximum_common_rate_error':max(abs(float(r['common_rate_error'])) for r in rows),
        'repeat_error':max(abs(float(r['repeat_error'])) for r in rows),
        'scope':'actual built source before native global species rescaling; native rounded molecular weights allow tiny C/O residual'}
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
