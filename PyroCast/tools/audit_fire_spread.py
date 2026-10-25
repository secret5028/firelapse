"""Count actual native solid combustion, independently of registered fire events."""
import argparse
import json
from pathlib import Path
import numpy as np


def audit(folder):
    p=json.loads((folder/'playback.json').read_text('utf-8'))
    t=np.asarray(p['time_s']); step=float(t[1]-t[0]); rooms={}
    for fire in p['fires']:
        rooms.setdefault(fire['solver_id'],np.zeros(len(t)))
        rooms[fire['solver_id']]+=np.asarray(fire['Q_kW'])
    rows=[]
    for room,q in rooms.items():
        hit=np.flatnonzero(q>1)
        rows.append(dict(room=room,peak_kW=float(q.max()),
            first_observed_s=float(t[hit[0]]) if len(hit) else None,
            last_observed_s=float(t[hit[-1]]) if len(hit) else None,
            sampled_duration_above_1kW_s=int(np.sum(q>1))*step,
            sampled_duration_above_100kW_s=int(np.sum(q>100))*step))
    n=np.sum([q>1 for q in rooms.values()],axis=0); i=int(np.argmax(n))
    active100=np.sum([q>100 for q in rooms.values()],axis=0)
    result=dict(duration_s=float(t[-1]),indoor_rooms=len(p['rooms']),
        target_rooms=16,threshold_kW=1,registered_rooms=len(rooms),
        ever_burning_rooms=sum(r['peak_kW']>1 for r in rows),
        peak_concurrent_burning_rooms=int(n[i]),peak_concurrent_time_s=float(t[i]),
        concurrent_target_met=bool(n.max()>=16),
        peak_concurrent_above_100kW=int(active100.max()),
        fire_rooms=sorted(rows,key=lambda r:r['first_observed_s'] or 0),
        status=p['status'],iteration=p.get('iteration'),
        basis='native solid HRR, 5s observations; neither registered supply nor whole-room engulfment')
    (folder/'fire-spread-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('fire_rooms','iteration')},ensure_ascii=False))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path)
    audit(parser.parse_args().folder)
