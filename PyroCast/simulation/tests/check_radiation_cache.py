"""Link and test actual compiled exact-cache procedures, without a fire simulation."""
import argparse,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();build=a.build.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
exe=out/'cache-check.exe'
args=[str(ROOT/'tools/w64devkit/bin/gfortran.exe'),'-O2','-ffree-line-length-none','-I',str(build),
      str(Path(__file__).with_name('radiation_cache.f90')),*[str(f) for f in build.glob('*.o') if f.name!='cfast.o'],'-o',str(exe)]
compiled=subprocess.run(args,capture_output=True)
if compiled.returncode:raise RuntimeError(compiled.stderr.decode('utf-8',errors='replace'))
r=subprocess.run([str(exe)],cwd=out,check=True,capture_output=True)
result={'passed':True,'output':r.stdout.decode('ascii').strip()}
(out/'report.json').write_text(json.dumps(result,indent=2),'utf-8');print(json.dumps(result))
