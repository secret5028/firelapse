"""A single paired, explicit ignition scenario on the enriched CAD demonstration."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from pyrocast_cfbt.comparison import compare_ignition

base=json.loads((ROOT/'results/cad_exterior_risk_demo_v4_ceiling/result.json').read_text('utf-8'))
result=compare_ignition(base,'CAD_3F_R4',250.,ROOT/'build/ignition/cfbt/cfast-cfbt.exe',ROOT/'results/cad_exterior_ignition_demo_v4_ceiling_250',duration_s=15.,rate_s_inv=.05)
print(json.dumps({'observed':result['reaction_observed'],'ignitions':result['solid_ignitions'],
    'changes':{r:{k:v['max_abs_change'] for k,v in fields.items()} for r,fields in result['room_differences'].items()},
    'terminated':result['ignited']['status'],'horizon_s':result['comparison_horizon_s']},ensure_ascii=False),flush=True)
