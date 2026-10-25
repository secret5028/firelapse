"""Build and run one actual CAD-building scenario, then package its native results."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pyrocast_cfbt.cad import adapt
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.spread import simulate


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('project',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'results/cad_building')
    parser.add_argument('--options',type=Path)
    parser.add_argument('--build-only',action='store_true')
    parser.add_argument('--building',type=Path)
    parser.add_argument('--profile',choices=['practical','legacy'],default='practical')
    args=parser.parse_args()
    options=json.loads(args.options.read_text('utf-8')) if args.options else {}
    options['profile']=args.profile
    if args.building:options['building_path']=str(args.building.resolve())
    model=normalize(adapt(args.project,options))
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'scenario.json').write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'solver_rooms':len(model['rooms']),'cad_rooms':len(model['cad']['display_rooms']),
                      'wall_vents':sum(v.get('type')!='FLOOR' for v in model['openings']),
                      'floor_vents':sum(v.get('type')=='FLOOR' for v in model['openings']),
                      'targets':len(model['explicit_candidates']),'duration_s':model['duration_s']},ensure_ascii=False),flush=True)
    if args.build_only:return
    result=simulate(model,ROOT/'build/cfbt/cfast-cfbt.exe',args.output)
    from pyrocast_cfbt.playback import package
    payload=package(result)
    (args.output/'playback.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('terminated','error','successful_runs_count','committed_ignitions_count')},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
