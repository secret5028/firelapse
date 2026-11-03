"""Reclassify saved results only. No integration/runner imports."""
import copy,csv,hashlib,json,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'simulation'),str(ROOT/'simulation/deps'),str(ROOT/'tools')]
import numpy as np
from pyrocast_cfbt.conditions import rollover_states,ROLLOVER_REVISION
from pyrocast_cfbt.native import read_native_csv
from export_ui_attention import result_index
from pyrocast_lite.montecarlo import aggregate

OUT=ROOT/'simulation/results/fgi_rollover_state_20261103'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def graph(p,source):
    rooms=[{'id':r['solver_id'],'parent_room':r.get('original_room',r['solver_id'])} for r in p['rooms']]
    reps={r['parent_room']:r['id'] for r in rooms};ids={r['id'] for r in rooms};vents=[]
    for raw in source['openings']:
        v=copy.deepcopy(raw)
        for k in ('a','b'):v[k]=reps.get(v[k],v[k])
        if all(v[k]=='OUTSIDE' or v[k] in ids for k in ('a','b')):vents.append(v)
    return {'rooms':rooms,'openings':vents,'fuel_groups':[{'room':f['solver_id'],'initial_time_s':f.get('time_s',0)} for f in p['fires'] if f.get('kind')=='initial']}

def main():
    OUT.mkdir(exist_ok=True,parents=True);previous=read(ROOT/'simulation/results/rollover_route_20261103/comparison.json')
    cases=sorted({r['case'] for r in previous['rows'] if not r['case'].startswith('wando_')})
    rows=[];changed=[];batches=set();resume='--resume' in sys.argv
    with zipfile.ZipFile(OUT/'before.zip','a' if resume else 'x',zipfile.ZIP_DEFLATED,compresslevel=1) as backup:
        archived=set(backup.namelist())
        def original(p):return json.loads(backup.read(p.relative_to(ROOT).as_posix())) if p.relative_to(ROOT).as_posix() in archived else read(p)
        def preserve(p):
            rel=p.relative_to(ROOT).as_posix()
            if p.exists() and rel not in archived:backup.write(p,rel);archived.add(rel)
        def save(p,d):
            preserve(p);p.write_text(json.dumps(d,ensure_ascii=False,allow_nan=False),encoding='utf-8');changed.append(p.relative_to(ROOT).as_posix())
        def report(case,t,oldfg,newfg,oldroll,states,mapping):
            for room in sorted(set(mapping.values())):
                cells=[r for r in mapping if mapping[r]==room]
                def peak(records):
                    values=[(v,i) for c in cells for i,v in enumerate(records[c]) if v is not None]
                    if not values:return None,None
                    v,i=max(values,key=lambda p:(p[0],-p[1]));return v*100,t[i]
                before,bt=peak(oldfg);after,at=peak(newfg);assert before==after and bt==at
                first_old=next((t[i] for i in range(len(t)) if any(oldroll[c][i] is not None and oldroll[c][i]>=1 for c in cells)),None)
                first=next((t[i] for i in range(len(t)) if any(states[c]['active'][i] is True for c in cells)),None)
                rows.append(dict(case=case,room=room,FGI_before_peak=before,FGI_after_peak=after,FGI_peak_s=at,old_rollover_index_first100_s=first_old,rollover_active_first_s=first,origin_excluded=any(states[c]['excluded_origin'] for c in cells)))
        for case in cases:
            folder=ROOT/'simulation/results'/case;path=folder/'playback.json';p=read(path);old=original(path)
            mapping={r['solver_id']:r.get('original_room',r['solver_id']) for r in p['rooms']};t=p['time_s']
            if p.get('provenance',{}).get('rollover_revision')==ROLLOVER_REVISION:
                states={r:s['conditions']['FGI']['rollover'] for r,s in p['solvers'].items()}
            else:
                source=next((read(folder/n) for n in ('sample.json','input.json','scenario.json','model.json') if (folder/n).exists()),None)
                if source is None:raise ValueError('Missing opening source: '+case)
                source=source.get('scenario',source);m=graph(p,source);s=p['solvers']
                states=rollover_states(m,t,{r:v['conditions']['FGI'] for r,v in s.items()},{r:np.asarray(v['Qsolid_kW'])+v['Qbulk_kW'] for r,v in s.items()},{r:v['Qvent_kW'] for r,v in s.items()},p)
                physics=sha({r:{k:v for k,v in x.items() if k!='conditions'} for r,x in s.items()})
                for r,v in s.items():v['conditions'].pop('rollover',None);v['conditions']['FGI']['rollover']=states[r]
                assert physics==sha({r:{k:v for k,v in x.items() if k!='conditions'} for r,x in s.items()})
                p.setdefault('provenance',{})['rollover_revision']=ROLLOVER_REVISION;save(path,p)
                for q in (folder/'result.json',folder/'BDF/result.json',folder/'Radau/result.json'):
                    if not q.exists():continue
                    d=read(q)
                    if not d.get('shared_conditions'):continue
                    for r,rec in d['shared_conditions']['rooms'].items():rec.pop('rollover',None);rec['FGI']['rollover']=states[r]
                    d.pop('rollover',None);d['rollover_state_source']='shared_conditions.rooms.<cell>.FGI.rollover';d['rollover_revision']=ROLLOVER_REVISION
                    save(q,d);preserve(q.with_name('index-summary.json'));result_index(q)
                for name in ('summary.json','postprocessed-summary.json'):
                    q=folder/name
                    if not q.exists():continue
                    d=read(q);d.get('phenomena',{}).pop('rollover',None);d['rollover_revision']=ROLLOVER_REVISION;save(q,d)
            report(case,t,{r:v['conditions']['FGI']['scores']['degree'] for r,v in old['solvers'].items()},
                   {r:v['conditions']['FGI']['scores']['degree'] for r,v in p['solvers'].items()},
                   {r:v['conditions']['rollover']['scores']['degree'] for r,v in old['solvers'].items()},states,mapping)
            batches.add(folder.parent);print(case,flush=True)
        folders=[ROOT/f'simulation/results/wando_C11_{k}_20261102' for k in ('P1','P2','P4')]+[ROOT/f'simulation/results/wando_C11_P5_20261103/{k}' for k in (400,450,500)]
        for folder in folders:
            m=read(folder/'model.json');s=read(folder/'timeseries.json');scores=read(folder/'condition-scores.json');old=original(folder/'condition-scores.json');ids=[r['id'] for r in m['rooms']];t=s['time_s'];native='fgi' in scores[ids[0]]
            fgi={r:scores[r]['fgi'] if native else {'scores':scores[r]['FGI']} for r in ids}
            v,vid,_=read_native_csv(folder/'case_vents.csv');openings={o['id']:{'fraction':v[next(k for k in v if k.startswith('WF_') and vid.get(k)==o['id'])]} for o in m['openings']}
            states=rollover_states(m,t,fgi,{r:s[r]['source_HRR_kW'] for r in ids},{r:s[r]['door_jet_kW'] for r in ids},{'time_s':t,'opening_states':openings})
            oldfg={r:old[r]['fgi']['scores']['degree'] if native else old[r]['FGI']['degree'] for r in ids}
            oldroll={r:old[r]['rollover']['scores']['degree'] if native else old[r]['rollover']['degree'] for r in ids}
            report(folder.relative_to(ROOT/'simulation/results').as_posix(),t,oldfg,{r:fgi[r]['scores']['degree'] for r in ids},oldroll,states,{r:r for r in ids})
            summary=read(folder/'summary.json')
            for r in ids:
                scores[r].pop('rollover',None)
                if native:scores[r]['fgi']['rollover']=states[r]
                else:scores[r]['FGI_rollover']=states[r]
                s[r].pop('rollover',None);s[r]['rollover_active']=states[r]['active']
                if r in summary.get('rooms',{}):summary['rooms'][r].get('indices',{}).pop('rollover',None);summary['rooms'][r]['rollover_first_active_s']=states[r]['first_active_s']
            for sample in summary.get('times',{}).values():sample.pop('rollover',None)
            summary['rollover_revision']=ROLLOVER_REVISION;summary['historical_plots_note']='Archived PNG/CSV with four indices are historical. Current data has three indices and FGI.rollover state.'
            save(folder/'condition-scores.json',scores);save(folder/'timeseries.json',s);save(folder/'summary.json',summary)
            save(folder/'rollover-conditions.json',{'revision':ROLLOVER_REVISION,'time_s':t,'FGI_rollover':states,'simulation_runs':0})
            if 'P1_' in folder.name:
                q=ROOT/'data/wando-coldstore/P1-playback.json';p=read(q)
                for r in ids:p['solvers'][r]['conditions'].pop('rollover',None);p['solvers'][r]['conditions']['FGI']['rollover']=states[r]
                p.setdefault('provenance',{})['rollover_revision']=ROLLOVER_REVISION;save(q,p)
                q=q.with_name('playback-evidence.json');d=read(q);d['playback_sha256']=hashlib.sha256((q.parent/'P1-playback.json').read_bytes()).hexdigest();d['rollover_revision']=ROLLOVER_REVISION;save(q,d)
        for folder in batches:
            q=folder/'summaries.json'
            if not q.exists():continue
            d=read(q)
            for s in d:s.get('phenomena',{}).pop('rollover',None)
            save(q,d)
            q=folder/'aggregate.json'
            if not q.exists():continue
            old=read(q);fresh=aggregate(d)
            for k in ('condition_sample_rates_random_only','condition_rates_by_original_room_random_only','worst_including_mandatory'):old[k]=fresh[k]
            old['rollover_revision']=ROLLOVER_REVISION;save(q,old)
            for q in (folder/'mc-summary.json',ROOT/'simulation/config/lite-viewer.json'):
                if not q.exists():continue
                a=read(q)
                if q.name=='lite-viewer.json':
                    if folder.name!='lite_v8_mc_R2_10_20261026':continue
                    a['mc_summary']['rates']={k:v for k,v in a['mc_summary']['rates'].items() if k in ('FO','FGI','backdraft')}
                else:a['rates']={k:v for k,v in a.get('rates',{}).items() if k in ('FO','FGI','backdraft')}
                save(q,a)
    output={'revision':ROLLOVER_REVISION,'rows':rows,'updated':sorted(archived|set(changed)),'unavailable':previous['unavailable']+[{'case':'Wando P3','reason':'No saved simulation result found; no simulation run requested'}],'simulation_runs':0,'FGI_unchanged':True}
    (OUT/'comparison.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    with (OUT/'room-comparison.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    print('rows',len(rows),'unavailable',len(output['unavailable']))

if __name__=='__main__':main()
