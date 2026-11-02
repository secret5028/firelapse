"""Collect existing C8 regression artifacts only; never starts calculations."""
import json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text('utf-8'))
def save(name,v):(OUT/name).write_text(json.dumps(v,ensure_ascii=False,indent=2),'utf-8')
first=ROOT/'simulation/results/lite_screening_ui_1793596486525636600'
fixed=ROOT/'simulation/results/lite_screening_ui_1793597384213006900'
job=ROOT/'simulation/results/lite_mc_jobs/mc-1793596576284695400-55af780d'
rows=[]
for label,folder in [('screening-extremes',first),('screening-fixed',fixed)]:
 c=read(folder/'comparison.json');save(label+'-comparison.json',c)
 rows.append(dict(step=label,wall_s=c['total_wall_s'],attempted=c['attempted_scenarios'],complete=c['complete_scenarios']))
 for case in c['cases']:
  result=Path(case['result_folder']);save(label+'-'+case['state']+'-index.json',read(result/'index-summary.json'))
  rows.append(dict(step=label,state=case['state'],complete=case['complete'],burning=case['burning_room_count'],
      attention=read(result/'index-summary.json')['attention_room_count'],first_FO_s=case['first_FO_s'],times=case['times']))
for name in ['request','progress','aggregate','mc-summary','started','summaries']:
 shutil.copyfile(job/(name+'.json'),OUT/('mc-'+name+'.json'))
for sid in ['S00','S01']:
 s=read(job/sid/'summary.json');i=read(job/sid/'index-summary.json')
 rows.append(dict(step='MC',sample=sid,complete=s['complete'],burning=len(s['burning_original_rooms']),
     attention=i['attention_room_count'],first_FO_s=s['phenomena']['FO']['first_s'],times=s['times']))
save('numeric-results.json',rows)
print(json.dumps(rows,ensure_ascii=False))
