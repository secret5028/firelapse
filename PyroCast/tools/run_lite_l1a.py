"""L1 section 1.1 shared-input rerun, preserving first-attempt results."""
import json
from pathlib import Path
import run_lite_l1 as base

base.OUT=base.ROOT/'simulation/results/lite_l1a_20261025'


def main():
    base.contract()
    gates={}
    for name in ('B1','B2','B3'):
        result=base.case(name)
        root=result['fire_room']
        active=[r for r in result['room_summary'] if r['cell']!=root and r['actual_peak_kW']>0]
        passed=result['ok'] and (not active if name=='B1' else len(active)==2 and all(r['longest_positive_HRR_s']>=60 for r in active))
        gates[name]={'passed':bool(passed),'rooms':result['room_summary'],
                     'integration_s':result['integration']['wall_seconds']}
        base.save(base.OUT/'L2/gates.json',gates)
        if name=='B1' and not passed:
            base.save(base.OUT/'status.json',{'stopped_at':'L2/B1','reason':'B1 negative control failed','L3':'not_run','L4':'not_run','MC':'not_run'})
            print('STOP: B1 gate failed',flush=True);return
    if not all(x['passed'] for x in gates.values()):
        base.save(base.OUT/'status.json',{'stopped_at':'L2','reason':'positive control failed','L3':'not_run','L4':'not_run','MC':'not_run'})
        return
    base.save(base.OUT/'status.json',{'L2':'passed','next':'L3 single comparison','MC':'not_run'})


if __name__=='__main__':main()
