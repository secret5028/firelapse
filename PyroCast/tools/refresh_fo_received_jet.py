"""Re-score saved outputs only. No integration, input edit or threshold tuning."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'simulation'),str(ROOT/'simulation/deps'),str(ROOT/'tools')]
import numpy as np
from pyrocast_cfbt.fo_hrr import apply_fo_hrr, REVISION
from pyrocast_cfbt.conditions import fo_required_hrr
from pyrocast_cfbt.native import read_native_csv
from result_catalog import atomic_json
from export_ui_attention import result_index

OUT=ROOT/'simulation/results/fo_received_jet_20261103'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
digest=lambda d:hashlib.sha256(json.dumps(d,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def stats(t,values):
    valid=[(x,i) for i,x in enumerate(values) if x is not None]
    peak,i=max(valid,default=(None,0))
    first=lambda level:next((float(t[j]) for j,v in enumerate(values) if v is not None and v>=level),None)
    return dict(peak=None if peak is None else peak*100,peak_s=float(t[i]) if peak is not None else None,
                first_70_s=first(.7),first_100_s=first(1.))


def compare(t,old,new,**extra):
    delta=[abs(b-a)*100 for a,b in zip(old,new) if a is not None and b is not None]
    return dict(**extra,before=stats(t,old),after=stats(t,new),max_pointwise_delta=max(delta,default=0.))


def refresh_record(rec,own,jet):
    old=copy.deepcopy(rec['scores'])
    required=rec['score_basis']['Q_required_kW']
    apply_fo_hrr(rec,own,jet,required)
    for k in ('temperature','oxygen'):
        assert rec['scores']['factors'][k]==old['factors'][k]
    return old


def refresh_result(d):
    before=digest({k:v for k,v in d.items() if k not in ('shared_conditions','fo_diagnostic_revision')})
    others={rid:{k:v for k,v in rec.items() if k!='FO'} for rid,rec in d['shared_conditions']['rooms'].items()}
    for s in d['rooms']:
        rec=d['shared_conditions']['rooms'][s['id']]['FO']
        own=np.asarray(s['actual_HRR_kW'])+np.asarray(s['upper_HRR_kW'])
        refresh_record(rec,own,s['door_jet_HRR_kW'])
    d['fo_diagnostic_revision']=REVISION
    assert before==digest({k:v for k,v in d.items() if k not in ('shared_conditions','fo_diagnostic_revision')})
    assert others=={rid:{k:v for k,v in rec.items() if k!='FO'} for rid,rec in d['shared_conditions']['rooms'].items()}


def main():
    raise SystemExit("Superseded: use refresh_physics_p0.py with explicit scenario, playback and a new output path; legacy definitions must not overwrite new indices.")
    OUT.mkdir(parents=True,exist_ok=True);start=time.perf_counter()
    rows=[];changed=[];skipped=[]
    # Archive the pre-change files once. Archived trials/fixtures stay immutable.
    archive=OUT/'before.zip'
    if archive.exists():raise RuntimeError('Migration already attempted; inspect evidence before repeating')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=3) as backup:
        def save(path,d):
            if path.exists():backup.write(path,path.relative_to(ROOT).as_posix())
            atomic_json(path,d);changed.append(path.relative_to(ROOT).as_posix())
        # All saved lite playbacks, excluding duplicate review/publish/test copies.
        paths=[]
        for directory,dirs,files in os.walk(ROOT/'simulation/results'):
            dirs[:]=[x for x in dirs if not x.startswith(('github-publish','ui_refactor','server_stage5_test','.')) and x not in ('__pycache__','fo_received_jet_20261103')]
            if 'playback.json' in files:paths.append(Path(directory)/'playback.json')
        for path in sorted(paths):
            p=read(path)
            if p.get('engine_kind')!='pyrocast_lite':continue
            # Old fixtures without the shared three-factor table are not silently
            # reinterpreted; explicit missing-input list is part of the report.
            if not all('Q_required_kW' in s.get('conditions',{}).get('FO',{}).get('score_basis',{})
                       and all(k in s for k in ('Qsolid_kW','Qbulk_kW','Qvent_kW')) for s in p['solvers'].values()):
                skipped.append(dict(path=str(path.relative_to(ROOT)),reason='missing saved three-factor HRR inputs'));continue
            before_physics=digest({rid:{k:v for k,v in s.items() if k!='conditions'} for rid,s in p['solvers'].items()})
            other=digest({rid:{k:v for k,v in s['conditions'].items() if k!='FO'} for rid,s in p['solvers'].items()})
            for rid,s in p['solvers'].items():
                rec=s['conditions']['FO'];old=refresh_record(rec,np.asarray(s['Qsolid_kW'])+s['Qbulk_kW'],s['Qvent_kW'])
                original=next(r.get('original_room',rid) for r in p['rooms'] if r['solver_id']==rid)
                rows.append(compare(p['time_s'],old['degree'],rec['scores']['degree'],
                    case=path.parent.relative_to(ROOT/'simulation/results').as_posix(),cell=rid,room=original,
                    received_jet_peak_kW=max(s['Qvent_kW']),own_peak_kW=max(np.asarray(s['Qsolid_kW'])+s['Qbulk_kW'])))
            assert before_physics==digest({rid:{k:v for k,v in s.items() if k!='conditions'} for rid,s in p['solvers'].items()})
            assert other==digest({rid:{k:v for k,v in s['conditions'].items() if k!='FO'} for rid,s in p['solvers'].items()})
            p.setdefault('provenance',{})['fo_diagnostic_revision']=REVISION
            save(path,p)
            for result_path in [path.with_name('result.json'),path.parent/'BDF/result.json',path.parent/'Radau/result.json']:
                if not result_path.exists():continue
                result=read(result_path)
                if result.get('shared_conditions'):
                    refresh_result(result);save(result_path,result);result_index(result_path)
            print(path.parent.name,flush=True)
        # Stock CFAST cases retain immutable original reports/CSV. New derived
        # three-factor results are stored alongside the migration comparison.
        for case in ('P1','P2','P4'):
            folder=ROOT/f'simulation/results/wando_C11_{case}_20261102'
            model=read(folder/'model.json');series=read(folder/'timeseries.json');old=read(folder/'condition-scores.json')
            c,_,_=read_native_csv(folder/'case_compartments.csv');v,vid,_=read_native_csv(folder/'case_vents.csv')
            openings={o['id']:{'fraction':v[next(k for k in v if k.startswith('WF_') and vid[k]==o['id'])]} for o in model['openings']}
            records={}
            for i,room in enumerate(model['rooms'],1):
                rid=room['id'];rec={'scores':copy.deepcopy(old[rid]['FO'])}
                required=fo_required_hrr(model,{'time_s':c['Time'],'opening_states':openings},room,c['Time'])
                apply_fo_hrr(rec,series[rid]['source_HRR_kW'],c[f'DJET_{i}']/1000,required)
                records[rid]=rec
                rows.append(compare(c['Time'],old[rid]['FO']['degree'],rec['scores']['degree'],case=case,cell=rid,room=rid,
                    temperature_only_peak=max(series[rid]['T_upper_C'])/model['criteria']['fo_temperature_C']*100,
                    received_jet_peak_kW=float(max(c[f'DJET_{i}'])/1000)))
            atomic_json(OUT/f'{case}-conditions.json',dict(revision=REVISION,time_s=c['Time'].tolist(),FO=records,
                source_hashes={f:hashlib.sha256((folder/f).read_bytes()).hexdigest() for f in ('case.in','case_compartments.csv','condition-scores.json')},simulation_runs=0))
        # Preserve the rejected web rendering before replacing it.
        backup.write(ROOT/'data/wando-coldstore/P1-playback.json','data/wando-coldstore/P1-playback.json')
    atomic_json(OUT/'comparison.json',dict(revision=REVISION,rows=rows,updated=changed,skipped=skipped,
        simulation_runs=0,elapsed_s=time.perf_counter()-start,
        invariants={'temperature_oxygen_factors':True,'other_phenomena':True,'physical_series':True}))
    print(json.dumps({'cell_rows':len(rows),'updated_files':len(changed),'skipped':skipped,'seconds':time.perf_counter()-start},ensure_ascii=False))


def refresh_summaries():
    """Refresh dependent saved MC aggregates after the score-only migration."""
    from pyrocast_lite.montecarlo import aggregate
    report=read(OUT/'comparison.json');changed=[];batches=set()
    with zipfile.ZipFile(OUT/'summary-before.zip','x',zipfile.ZIP_DEFLATED) as backup:
        def save(path,data):
            backup.write(path,path.relative_to(ROOT).as_posix());atomic_json(path,data)
            changed.append(path.relative_to(ROOT).as_posix())
        for rel in report['updated']:
            if not rel.endswith('/playback.json'):continue
            path=ROOT/rel;p=read(path);t=np.asarray(p['time_s']);mapping={}
            for r in p['rooms']:mapping.setdefault(r.get('original_room',r['key']),[]).append(r['solver_id'])
            masks={rid:np.any([[v is True for v in p['solvers'][c]['conditions']['FO']['scores']['all_met']] for c in cells],axis=0) for rid,cells in mapping.items()}
            scores=[v for s in p['solvers'].values() for v in s['conditions']['FO']['scores']['degree'] if v is not None]
            hit={rid:float(t[np.flatnonzero(mask)[0]]) for rid,mask in masks.items() if mask.any()}
            fractions={rid:float(np.sum(mask[:-1]*np.diff(t))/(t[-1]-t[0])) for rid,mask in masks.items()}
            for name in ('summary.json','postprocessed-summary.json'):
                dest=path.with_name(name)
                if not dest.exists():continue
                d=read(dest)
                if not d.get('phenomena',{}).get('FO'):continue
                fo=d['phenomena']['FO'];fo.update(ever_room_count=len(hit),rooms=hit,first_s=min(hit.values(),default=None),
                    max_simultaneous_room_count=int(np.stack(list(masks.values())).sum(axis=0).max()),score_max=max(scores,default=None))
                if 'score_median' in fo:fo['score_median']=float(np.median(scores)) if scores else None
                if 'met_time_fraction_by_room' in fo:
                    fo.update(met_time_fraction_by_room=fractions,met_room_time_fraction=float(np.mean(list(fractions.values()))))
                d['fo_diagnostic_revision']=REVISION;save(dest,d)
                batches.add(path.parent.parent)
        for folder in sorted(batches):
            dest=folder/'summaries.json'
            if not dest.exists():continue
            summaries=read(dest)
            for s in summaries:
                path=folder/s['sample_id']/'summary.json'
                if path.exists():
                    updated=read(path)
                    if updated.get('fo_diagnostic_revision')==REVISION:s['phenomena']['FO']=updated['phenomena']['FO'];s['fo_diagnostic_revision']=REVISION
            save(dest,summaries)
            dest=folder/'aggregate.json'
            if not dest.exists():continue
            old=read(dest);fresh=aggregate(summaries)
            for key in ('condition_sample_rates_random_only','condition_rates_by_original_room_random_only','worst_including_mandatory'):
                value=fresh[key]['FO']
                if key=='condition_sample_rates_random_only':
                    value.pop('median_of_sample_medians',None)
                    vals=[s['phenomena']['FO']['score_max'] for s in summaries if s.get('complete') and s['kind']=='random' and s['phenomena']['FO'].get('score_max') is not None]
                    value['median_of_sample_maxima']=float(np.median(vals)) if vals else None
                if key=='worst_including_mandatory' and value.get('sample_id'):
                    sample=folder/value['sample_id']/'sample.json'
                    if sample.exists():value['openings']=read(sample)['openings']
                old[key]['FO']=value
            old['fo_diagnostic_revision']=REVISION;save(dest,old)
            for dest in (folder/'mc-summary.json',ROOT/'simulation/config/lite-viewer.json'):
                if not dest.exists():continue
                d=read(dest)
                if dest.name=='lite-viewer.json':
                    if folder.name!='lite_v8_mc_R2_10_20261026':continue
                    d['mc_summary']['rates']['FO']=old['condition_sample_rates_random_only']['FO']
                else:d['rates']['FO']=old['condition_sample_rates_random_only']['FO']
                save(dest,d)
    report['dependent_summaries_updated']=changed;atomic_json(OUT/'comparison.json',report)
    print('Updated dependent summaries:',len(changed))


if __name__=='__main__':
    refresh_summaries() if '--summaries' in sys.argv else main()
