from pathlib import Path
import sys,os,json,hashlib
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
ROOT=Path.cwd()
for p in ('simulation/deps','simulation','tools'):sys.path.insert(0,str(ROOT/p))
from run_lite_mc_v8_r2 import execute
out=ROOT/'simulation/results/mc-numerical-fix-20261105';out.mkdir(exist_ok=True)
old=ROOT/'simulation/results/lite_mc_jobs/models/cad-aabf1346d0e54c94b45ad7d7db7137d4/mc-1793861778317776500-40960b77'
rows=[]
for id in ['S00','S01']:
 sample=json.loads((old/id/'sample.json').read_text('utf-8'))
 result=execute(sample,out,publish=False)
 row={k:result.get(k) for k in ['sample_id','complete','failure','times','attempts']};row['input_sha256']=hashlib.sha256((old/id/'sample.json').read_bytes()).hexdigest();rows.append(row)
 print(json.dumps(row),flush=True)
 (ROOT/'reviews/mc-export-fix-20261105/fixed-samples.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
