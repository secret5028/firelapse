from pathlib import Path
import os,sys,json,time
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
ROOT=Path(__file__).resolve().parents[2]
for p in ('simulation/deps','simulation','tools'):sys.path.insert(0,str(ROOT/p))
import numpy as np
from scipy.integrate._ivp import bdf
from pyrocast_lite.adapter import prepare
from pyrocast_lite.runner import run
source=ROOT/'simulation/results/lite_mc_jobs/models/cad-aabf1346d0e54c94b45ad7d7db7137d4/mc-1793861778317776500-40960b77/S00/sample.json'
sample=json.loads(source.read_text('utf-8'))
m,_=prepare(sample['scenario'],dict(smooth_state_bounds=True,upper_combustion_enabled=True,door_jet_enabled=True,oxygen_inventory_mode=False,remove_cumulative_state=True))
real=bdf.num_jac;events=[];calls=0;captured=False
out=Path(__file__).parent

def trace(fun,t,y,f,threshold,factor,sparsity=None):
 global calls,captured
 calls+=1
 if factor is not None and (not np.isfinite(factor).all() or np.max(factor)>.01):
  ix=int(np.nanargmax(factor)); n=m.N
  if len(events)<30 or not np.isfinite(factor).all():events.append(dict(call=calls,t=float(t),index=ix,cell=m.nodes[ix%n]['id'],block=ix//n,state=float(y[ix]),rhs=float(f[ix]),factor=str(factor[ix]),state_finite=bool(np.isfinite(y).all()),rhs_finite=bool(np.isfinite(f).all())))
  if np.max(factor)>1e100 and not captured:
   captured=True;np.savez_compressed(out/'large-factor-state.npz',t=t,y=y,f=f,factor=factor)
 return real(fun,t,y,f,threshold,factor,sparsity)
bdf.num_jac=trace
run(m,1800,10,180,method='BDF')
(out/'trace.json').write_text(json.dumps(dict(integration=m.integration,jac_calls=calls,events=events),indent=2),encoding='utf-8')
if hasattr(m,'last_trial_state'):np.savez_compressed(out/'last-trial.npz',t=m.last_trial_state[0],y=m.last_trial_state[1])
print(json.dumps(dict(integration=m.integration,jac_calls=calls,events=events[-3:]),default=str),flush=True)
