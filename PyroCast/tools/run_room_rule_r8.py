"""Frozen r8 single execution / optional parallel aggressive comparison.
Only result review metadata is published; never replaces operating 3D playback.
"""
import argparse,json,sys,time,hashlib
from pathlib import Path
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor,as_completed
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'simulation'))
from pyrocast_cfbt.room_rule_r8 import prepare
from pyrocast_cfbt.rule_settings import resolve,comparison_options
from pyrocast_cfbt.deck import make_deck
from pyrocast_cfbt.native import digest,load_result
from run_room_rule_r7 import run_case,analyze,ENGINE,SOURCE
RESULTS=ROOT/'simulation/results'

def save(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 temporary=path.with_suffix(path.suffix+'.tmp')
 temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),'utf-8')
 temporary.replace(path)

def baseline_input(model):
 m=deepcopy(model);m['fuel_groups']=[g for g in m['fuel_groups'] if 'initial_time_s' in g]
 m['explicit_candidates']=[]
 return m

def baseline(model,manifest):
 m=baseline_input(model);deck=make_deck(m,[],[])
 bm=deepcopy(manifest);bm['sensors']=[];bm['fallback_sensors']=[]
 key=hashlib.sha256((digest(ENGINE)+'\n'+deck+'\n'+str(m['duration_s'])).encode()).hexdigest()
 folder=RESULTS/'room_rule_r8_baselines'/key[:24]
 record=folder/'completed.json'
 if record.exists():
  cached=json.loads(record.read_text('utf-8'))
  if cached['signature']['engine']!=digest(ENGINE) or (folder/'case.in').read_text('ascii')!=deck or not all(digest(folder/f)==h for f,h in cached['files'].items()):
   raise ValueError('Baseline cache verification failed; no automatic rerun')
  native=load_result(folder,m['duration_s'],cached['run']);report=analyze(m,native,bm,True)
  return {'cache_hit':True,'folder':str(folder),'key':key,'report':report}
 report=run_case(folder,m,[],bm,baseline=True,timeout=1800,display_root=RESULTS)
 return {'cache_hit':False,'folder':str(folder),'key':key,'report':report}

def ranges(reports):
 complete=all(r['complete'] for r in reports.values());rows={}
 for label,report in reports.items():
  if not report['complete']:continue
  byroom={}
  for row in report['rows']:
   at=row['first_actual_positive_HRR_s']
   if at is not None:byroom[row['original_room']]=min(byroom.get(row['original_room'],float('inf')),at)
  for room,at in byroom.items():rows.setdefault(room,{})[label]=at
 return {'all_scenarios_complete':complete,
  'burning_room_count_range':([min(len(r['actual_burning_original_rooms']) for r in reports.values()),max(len(r['actual_burning_original_rooms']) for r in reports.values())] if complete else None),
  'room_first_actual_HRR':{room:{'observed_range_s':[min(v.values()),max(v.values())],
    'by_scenario':v,'not_observed_in':[name for name in reports if name not in v and reports[name]['complete']],
    'unevaluated_in':[name for name in reports if not reports[name]['complete']],
    'basis':'first positive native HRR sample; range conditional on observed combustion, not probability'} for room,v in rows.items()},
  'basis':'comparison of specified settings, not Monte Carlo probability or exhaustive bounds'}

def run_batch(raw,destination,options=None,compare=False):
 if not isinstance(compare,bool):raise ValueError('compare_aggressive must be boolean')
 destination=Path(destination).resolve()
 if not destination.is_relative_to(RESULTS.resolve()):raise ValueError('Result folder must stay inside simulation/results')
 resolve(options) # every setting rejected before any execution
 configurations={'selected':options or {}}
 if compare:configurations['aggressive']=comparison_options(options or {})
 prepared={}
 for label,config in configurations.items():
  m,t,mf=prepare({**deepcopy(raw),'room_rule_r8':config})
  if label=='aggressive':
   for key in ('coverage_default','vent_cap_k'):
    item=mf['rule_settings']['parameters'][key]
    item['source']='comparison_shared'
    item['inherited_source']=prepared['selected'][2]['rule_settings']['parameters'][key]['source']
  mf.update(engine_sha256=digest(ENGINE),duration_s=m['duration_s'],output_step_s=m['output_step_s'],run_timeout_s=1800,stall_timeout_s=0,
     original_rooms=len(raw['rooms']),native_cells=len(m['rooms']),registered_sources=len(m['fuel_groups']))
  prepared[label]=(m,t,mf)
 if (destination/'batch-state.json').exists():raise ValueError('This r8 batch was already attempted; no automatic rerun')
 save(destination/'batch-state.json',{'state':'running','started_unix':time.time(),'compare_aggressive':compare,'automatic_retry':False})
 save(destination/'source-scenario.json',raw)
 started=time.monotonic();reports={};base=None
 try:
  m,t,mf=prepared['selected'];base=baseline(m,mf)
  if not base['report']['complete']:raise RuntimeError('Baseline incomplete; scenarios not started')
  save(destination/'baseline-reference.json',base)
  for label,(m,t,mf) in prepared.items():
   canonical=make_deck(baseline_input(m),[],[])
   if canonical!=(Path(base['folder'])/'case.in').read_text('ascii'):raise ValueError('Comparison baseline inputs differ')
   mf['baseline_native']={'key':base['key'],'folder':base['folder'],'reused_for_comparison':label!='selected','canonical_first_source_only':True}
  with ThreadPoolExecutor(max_workers=len(prepared)) as pool:
   pending={pool.submit(run_case,destination/label,m,t,mf,timeout=1800,display_root=destination):label for label,(m,t,mf) in prepared.items()}
   for future in as_completed(pending):
    label=pending[future];reports[label]=future.result()
    save(destination/'progress.json',{'finished':list(reports),'parallel_requested':compare})
  result={'revision':'room_rule_r8_frozen','complete':all(r['complete'] for r in reports.values()),
   'operating_playback_replaced':False,'requires_user_approval_to_replace_playback':True,
   'wall_seconds':time.monotonic()-started,'parallel_requested':compare,
   'building_sha256':raw.get('cad',{}).get('building_sha256'),
   'source_sha256':hashlib.sha256(json.dumps(raw,sort_keys=True).encode()).hexdigest(),
   'settings':{k:v[2]['rule_settings'] for k,v in prepared.items()},'cases':reports,'baseline_native':base,
   'partial_cases':{k:json.loads((destination/k/'partial-analysis.json').read_text('utf-8')) for k,r in reports.items() if not r['complete'] and (destination/k/'partial-analysis.json').exists()},
   'ranges':ranges(reports),'limits':prepared['selected'][2]['limits']}
  save(destination/'comparison.json',result)
  save(destination/'batch-state.json',{'state':'complete' if result['complete'] else 'incomplete','wall_seconds':result['wall_seconds'],'automatic_retry':False})
  return result
 except Exception as exc:
  save(destination/'batch-state.json',{'state':'failed','error':str(exc),'wall_seconds':time.monotonic()-started,'automatic_retry':False})
  raise

def main():
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,default=SOURCE);p.add_argument('--output',type=Path,default=RESULTS/'room_rule_r8_20261025');p.add_argument('--settings',type=Path);p.add_argument('--compare',action='store_true');a=p.parse_args()
 raw=json.loads(a.input.read_text('utf-8'));options=json.loads(a.settings.read_text('utf-8')) if a.settings else {}
 result=run_batch(raw,a.output,options,a.compare)
 print(json.dumps({'complete':result['complete'],'ranges':result['ranges'],'wall_seconds':result['wall_seconds']},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
