"""Re-evaluate saved state into a NEW file; never claim changed boundary physics was rerun."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'simulation'))
from pyrocast_cfbt.criteria import evaluate_cell, opening_increases, CONDITION_VERSION
from pyrocast_cfbt.conditions import _finite


def refresh(playback,scenario):
    p=deepcopy(playback);model=deepcopy(scenario)
    stored={r['id']:r for r in model['rooms']}
    if set(p['solvers'])-set(stored):
        raise ValueError('Exact solver-cell scenario required; do not normalize or change archived geometry')
    t=np.asarray(p['time_s']);solvers=p['solvers']
    for rid,s in solvers.items():
        room=stored[rid];parent=room.get('parent_room',rid)
        heat=sum((np.asarray(solvers[r['id']]['Qsolid_kW']) for r in model['rooms'] if r.get('parent_room',r['id'])==parent),np.zeros(len(t)))
        r=evaluate_cell(model,room,t,s['Tu'],s['h'],np.asarray(s['Ou'])*100,s['Fu'],s['Qsolid_kW'],
            bulk_kW=None if p.get('engine_kind')=='cfast_native' else s.get('Qbulk_kW'),jet_kW=s.get('Qvent_kW'),own_fire=heat,
            opening_increased=opening_increases(model,room,t,p))
        r['FGI']['rollover']=r.pop('rollover');s['conditions']=r
    p['condition_version']=CONDITION_VERSION
    p.setdefault('limits',[]).append('저장 상태의 지수만 재평가 · 경계 조건·온도·압력은 재계산하지 않음')
    if p.get('physical_validation'):
        from pyrocast_cfbt.validation import protect_playback
        protect_playback(p,p['physical_validation'])
    return _finite(p)


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('scenario',type=Path);cli.add_argument('playback',type=Path);cli.add_argument('output',type=Path)
    a=cli.parse_args()
    if a.output.exists() or a.output.resolve()==a.playback.resolve():cli.error('Output must be a new file')
    p=json.loads(a.playback.read_text('utf-8'));model=json.loads(a.scenario.read_text('utf-8'))
    if p.get('engine_kind')=='cfast_native':
        from pyrocast_cfbt.native import load_result
        from pyrocast_cfbt.validation import validate_native
        folder=a.playback.parent
        p['physical_validation']=validate_native(load_result(folder,p['time_s'][-1],dict(folder=str(folder))),model,folder)
    a.output.write_text(json.dumps(refresh(p,model),ensure_ascii=False,allow_nan=False),'utf-8')


if __name__=='__main__':main()
