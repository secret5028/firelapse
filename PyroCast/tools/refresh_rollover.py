"""Score-only migration. Never imports or invokes an integration runner."""
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'simulation'),str(ROOT/'simulation/deps'),str(ROOT/'tools')]
import numpy as np
from pyrocast_cfbt.conditions import rollover_records, ROLLOVER_REVISION
from pyrocast_cfbt.native import read_native_csv
from result_catalog import atomic_json
from export_ui_attention import result_index

OUT=ROOT/'simulation/results/rollover_route_20261103'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
digest=lambda d:hashlib.sha256(json.dumps(d,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def peak(t,a):
    valid=[i for i,v in enumerate(a) if v is not None]
    if not valid:return (None,None,None)
    j=max(valid,key=lambda i:a[i])
    return (a[j]*100,float(t[j]),next((float(t[i]) for i in valid if a[i]>=1),None))

def graph_for_playback(p,source):
    rooms=[{'id':r['solver_id'],'parent_room':r.get('original_room',r['solver_id'])} for r in p['rooms']]
    reps={r['parent_room']:r['id'] for r in rooms};ids={r['id'] for r in rooms}
    openings=[]
    for raw in source['openings']:
        v=copy.deepcopy(raw)
        for k in ('a','b'):v[k]=reps.get(v[k],v[k])
        if all(v[k]=='OUTSIDE' or v[k] in ids for k in ('a','b')):openings.append(v)
    groups=[{'room':f['solver_id'],'initial_time_s':f.get('time_s',0)} for f in p['fires'] if f.get('kind')=='initial']
    if not groups:raise ValueError('initial fire source unavailable')
    return {'rooms':rooms,'openings':openings,'fuel_groups':groups,'condition_scoring':{'rollover_include_origin':True,'rollover_open_only':True}}

def main():
    OUT.mkdir(exist_ok=True,parents=True);rows=[];updated=[];unavailable=[];batches=set()
    resume='--resume' in sys.argv
    with zipfile.ZipFile(OUT/'before.zip','a' if resume else 'x',zipfile.ZIP_DEFLATED,compresslevel=3) as archive:
        archived={ROOT/name for name in archive.namelist()}
        def original(path):
            return json.loads(archive.read(path.relative_to(ROOT).as_posix())) if path in archived else read(path)
        def save(path,d):
            if path.exists() and path not in archived:archive.write(path,path.relative_to(ROOT).as_posix());archived.add(path)
            atomic_json(path,d);updated.append(path.relative_to(ROOT).as_posix())
        def compare(case,t,old,new,mapping):
            for room in sorted(set(mapping.values())):
                cells=[c for c,r in mapping.items() if r==room]
                def combined(records):
                    return [max((records[c][i] for c in cells if records[c][i] is not None),default=None) for i in range(len(t))]
                a=peak(t,combined(old));b=peak(t,combined({c:r['scores']['degree'] for c,r in new.items()}))
                rows.append(dict(case=case,room=room,before_peak=a[0],before_peak_s=a[1],before_100_s=a[2],after_peak=b[0],after_peak_s=b[1],after_100_s=b[2]))
        paths=[]
        for directory,dirs,files in os.walk(ROOT/'simulation/results'):
            dirs[:]=[x for x in dirs if not x.startswith(('github-publish','ui_refactor','server_stage5_test','.')) and x not in ('__pycache__',OUT.name)]
            if 'playback.json' in files:paths.append(Path(directory)/'playback.json')
        for path in sorted(paths):
            p=read(path)
            if not any(r.get('cad_floor')=='3F' for r in p.get('rooms',[])):continue
            case=path.parent.relative_to(ROOT/'simulation/results').as_posix()
            if p.get('provenance',{}).get('rollover_revision')==ROLLOVER_REVISION:
                old=original(path);mapping={r['solver_id']:r.get('original_room',r['solver_id']) for r in p['rooms']}
                compare(case,p['time_s'],{r:s['conditions']['rollover']['scores']['degree'] for r,s in old['solvers'].items()},
                        {r:s['conditions']['rollover'] for r,s in p['solvers'].items()},mapping)
                batches.add(path.parent.parent);continue
            if not all('scores' in s.get('conditions',{}).get('FGI',{}) and all(k in s for k in ('Qsolid_kW','Qbulk_kW','Qvent_kW')) for s in p['solvers'].values()):
                unavailable.append({'case':case,'reason':'saved FGI degree and/or actual HRR unavailable (pre-index native archive); retained unchanged, not zero'});continue
            source=None
            for name in ('sample.json','input.json','scenario.json','model.json'):
                q=path.with_name(name)
                if q.exists():
                    d=read(q);candidate=d.get('scenario',d)
                    if 'openings' in candidate and 'rooms' in candidate:source=candidate;break
            if source is None:unavailable.append({'case':case,'reason':'saved opening input unavailable'});continue
            model=graph_for_playback(p,source);t=p['time_s'];sol=p['solvers']
            invariant=digest({r:{k:v for k,v in s.items() if k!='conditions'} for r,s in sol.items()})
            other=digest({r:{k:v for k,v in s['conditions'].items() if k!='rollover'} for r,s in sol.items()})
            new=rollover_records(model,t,{r:s['conditions']['FGI'] for r,s in sol.items()},
                {r:np.asarray(s['Qsolid_kW'])+s['Qbulk_kW'] for r,s in sol.items()},
                {r:s['Qvent_kW'] for r,s in sol.items()},p)
            mapping={r['id']:r['parent_room'] for r in model['rooms']}
            compare(case,t,{r:s['conditions']['rollover']['scores']['degree'] for r,s in sol.items()},new,mapping)
            for r,s in sol.items():s['conditions']['rollover']=new[r]
            assert invariant==digest({r:{k:v for k,v in s.items() if k!='conditions'} for r,s in sol.items()})
            assert other==digest({r:{k:v for k,v in s['conditions'].items() if k!='rollover'} for r,s in sol.items()})
            p.setdefault('provenance',{})['rollover_revision']=ROLLOVER_REVISION;save(path,p)
            for q in (path.with_name('result.json'),path.parent/'BDF/result.json',path.parent/'Radau/result.json'):
                if not q.exists():continue
                d=read(q)
                if not d.get('shared_conditions'):continue
                for rid,record in new.items():d['shared_conditions']['rooms'][rid]['rollover']=record
                d['rollover_revision']=ROLLOVER_REVISION;save(q,d)
                idx=q.with_name('index-summary.json')
                if idx.exists() and idx not in archived:archive.write(idx,idx.relative_to(ROOT).as_posix());archived.add(idx)
                result_index(q)
            masks={room:np.any([[v is True for v in new[c]['scores']['all_met']] for c,r in mapping.items() if r==room],axis=0) for room in set(mapping.values())}
            scores=[v for rec in new.values() for v in rec['scores']['degree'] if v is not None]
            hit={r:float(t[np.flatnonzero(a)[0]]) for r,a in masks.items() if a.any()}
            for name in ('summary.json','postprocessed-summary.json'):
                q=path.with_name(name)
                if not q.exists():continue
                d=read(q)
                if 'rollover' not in d.get('phenomena',{}):continue
                rec=d['phenomena']['rollover'];rec.update(ever_room_count=len(hit),rooms=hit,first_s=min(hit.values(),default=None),max_simultaneous_room_count=int(np.stack(list(masks.values())).sum(axis=0).max()),score_max=max(scores,default=None))
                if 'score_median' in rec:rec['score_median']=float(np.median(scores)) if scores else None
                if 'met_time_fraction_by_room' in rec:
                    fractions={r:float(np.sum(a[:-1]*np.diff(t))/(t[-1]-t[0])) for r,a in masks.items()}
                    rec.update(met_time_fraction_by_room=fractions,met_room_time_fraction=float(np.mean(list(fractions.values()))))
                d['rollover_revision']=ROLLOVER_REVISION;save(q,d);batches.add(path.parent.parent)
            print(case,flush=True)
        # Wando's immutable native CSV supplies the receiving-room jet and WF.
        wando=[ROOT/f'simulation/results/wando_C11_{k}_20261102' for k in ('P1','P2','P4')]
        wando += [ROOT/f'simulation/results/wando_C11_P5_20261103/{k}' for k in (400,450,500)]
        for folder in wando:
            model=read(folder/'model.json');series=read(folder/'timeseries.json');scores=read(folder/'condition-scores.json');t=series['time_s']
            old_scores=original(folder/'condition-scores.json');native='FGI' not in scores['ROOM']
            ids=[r['id'] for r in model['rooms']]
            fg={r:scores[r]['fgi'] if native else {'scores':scores[r]['FGI']} for r in ids}
            vents,vid,_=read_native_csv(folder/'case_vents.csv')
            states={v['id']:{'fraction':vents[next(k for k in vents if k.startswith('WF_') and vid.get(k)==v['id'])]} for v in model['openings']}
            records=rollover_records(model,t,fg,
                {r:series[r]['source_HRR_kW'] for r in ids},
                {r:series[r]['door_jet_kW'] for r in ids}, {'time_s':t,'opening_states':states})
            prior={r:old_scores[r].get('rollover',old_scores[r].get('upper_gas'))['scores']['degree'] if native else old_scores[r]['rollover']['degree'] for r in ids}
            compare(folder.relative_to(ROOT/'simulation/results').as_posix(),t,prior,records,{r:r for r in ids})
            for r,rec in records.items():scores[r]['rollover']=rec if native else rec['scores'];series[r]['rollover']=[None if v is None else v*100 for v in rec['scores']['degree']]
            save(folder/'condition-scores.json',scores);save(folder/'timeseries.json',series)
            save(folder/'rollover-conditions.json',{'revision':ROLLOVER_REVISION,'time_s':t,'rooms':records,'simulation_runs':0})
            summary=read(folder/'summary.json')
            # Preserve historical plots; updated index data and comparison are explicit.
            for r,rec in records.items():
                pk=peak(t,rec['scores']['degree'])
                if r in summary.get('rooms',{}):summary['rooms'][r]['indices']['rollover']={'first_70_s':next((t[i] for i,v in enumerate(rec['scores']['degree']) if v is not None and v>=.7),None),'first_100_s':pk[2],'peak':{'value':pk[0],'time_s':pk[1]}}
            for label,values in summary.get('times',{}).items():
                j=int(np.argmin(abs(np.asarray(t)-float(label))))
                values['rollover']=series['ROOM']['rollover'][j]
            summary['historical_plots_note']='Original PNG plots predate rollover revision; use rollover-conditions.json and room-comparison.csv.'
            summary['rollover_revision']=ROLLOVER_REVISION;save(folder/'summary.json',summary)
            if folder.name=='wando_C11_P1_20261102':
                q=ROOT/'data/wando-coldstore/P1-playback.json';p=read(q)
                for r,rec in records.items():p['solvers'][r]['conditions']['rollover']=rec
                p.setdefault('provenance',{})['rollover_revision']=ROLLOVER_REVISION;save(q,p)
                evidence=q.with_name('playback-evidence.json');e=read(evidence);e['playback_sha256']=hashlib.sha256(q.read_bytes()).hexdigest();e['rollover_revision']=ROLLOVER_REVISION;save(evidence,e)
        from pyrocast_lite.montecarlo import aggregate
        for folder in sorted(batches):
            q=folder/'summaries.json'
            if not q.exists():continue
            summaries=read(q)
            for s in summaries:
                f=folder/s['sample_id']/'summary.json'
                if f.exists():s['phenomena']['rollover']=read(f)['phenomena']['rollover']
            save(q,summaries);q=folder/'aggregate.json'
            if not q.exists():continue
            old=read(q);fresh=aggregate(summaries)
            for k in ('condition_sample_rates_random_only','condition_rates_by_original_room_random_only','worst_including_mandatory'):old[k]['rollover']=fresh[k]['rollover']
            old['rollover_revision']=ROLLOVER_REVISION;save(q,old)
            for q in (folder/'mc-summary.json',ROOT/'simulation/config/lite-viewer.json'):
                if not q.exists():continue
                d=read(q)
                if q.name=='lite-viewer.json':
                    if folder.name!='lite_v8_mc_R2_10_20261026':continue
                    d['mc_summary']['rates']['rollover']=old['condition_sample_rates_random_only']['rollover']
                else:d['rates']['rollover']=old['condition_sample_rates_random_only']['rollover']
                save(q,d)
    atomic_json(OUT/'comparison.json',{'revision':ROLLOVER_REVISION,'rows':rows,'updated':sorted(set(updated)|{p.relative_to(ROOT).as_posix() for p in archived}),'unavailable':unavailable,'simulation_runs':0,'physical_and_other_indices_unchanged':True})
    with (OUT/'room-comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print(json.dumps({'updated_files':len(updated),'room_rows':len(rows),'unavailable':len(unavailable)},ensure_ascii=False))

if __name__=='__main__':main()
