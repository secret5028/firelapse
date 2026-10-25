"""One approved R2/open reference, then package for the existing CAD viewer."""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import json,time
from pathlib import Path
import numpy as np
import run_lite_l1 as base
from pyrocast_lite.adapter import prepare
from pyrocast_lite.runner import run,results
from pyrocast_lite.montecarlo import output_balance_diagnostic
from pyrocast_lite.visualization import package

ROOT=base.ROOT;OUT=ROOT/'simulation/results/lite_v8_stage4_R2_20261026'
PARAMS=dict(smooth_state_bounds=True,upper_combustion_enabled=True,oxygen_inventory_mode=False,remove_cumulative_state=True)
if __name__=='__main__':
    if (OUT/'started.json').exists():raise RuntimeError('Already attempted')
    raw=json.loads((ROOT/'simulation/results/lite_v8_approved_n8_20261025/CAD_3F_R2/open_except_confirmed/input.json').read_text('utf-8'))
    base.save(OUT/'input.json',raw);base.save(OUT/'started.json',{'time':time.time(),'parameters':PARAMS,'budget_s':1200})
    m,manifest=prepare(raw,PARAMS);base.save(OUT/'rule_manifest.json',manifest)
    run(m,3600,10,1200);r=results(m);base.save(OUT/'result.json',r)
    np.savez_compressed(OUT/'state.npz',t=m.sol.t,y=m.sol.y)
    base.save(OUT/'balance.json',output_balance_diagnostic(m))
    if not r['ok']:raise RuntimeError(r['msg'])
    pb=package(m,r,raw,'R2 화점 · 승인 연료 · 확정 방화문 닫힘/나머지 열림 · 1시간')
    base.save(OUT/'playback.json',pb)
    cfg={'active_path':str(OUT/'playback.json'),'cases':[{'id':'stage4','label':pb['label'],'path':str(OUT/'playback.json')}],
         'progress_text':'4단계 R2 1건 완료 · 문 분출 ON · MC 아직 미실행'}
    base.save(ROOT/'simulation/config/lite-viewer.json',cfg)
    print(json.dumps({'complete':r['ok'],'integration_s':r['integration']['wall_seconds'],'rooms':r['room_summary'],'playback':str(OUT/'playback.json')},ensure_ascii=False),flush=True)
