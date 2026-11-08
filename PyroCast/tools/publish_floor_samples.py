"""Package a completed floor batch for Git; never modify source calculations."""
import argparse,gzip,hashlib,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation'),str(ROOT/'simulation/deps')]
from result_catalog import read,atomic_json

FILES=('input.json','request.json','scenario.json','playback.json','result.json','summary.json',
       'index-summary.json','status.json','rule_manifest.json','cfast-evidence.json','CFAST/case.in')

def sha(data):return hashlib.sha256(data).hexdigest()

def main(plan_path):
    from saved_briefings import ensure
    from model_library import entries,model_path
    from recalculate_floor_samples import registered_digest,BUILDINGS
    building_hashes={e['id']:registered_digest(model_path(e),e) for e in entries() if e['id'] in BUILDINGS}
    plan=read(plan_path);rows=[];inventory=[]
    if len(plan['rows'])!=25:raise ValueError('Expected 25 distinct floors')
    seen=set()
    for row in plan['rows']:
        key=(row['building'],row['floor'])
        if key in seen:raise ValueError('Duplicate floor')
        seen.add(key);folder=Path(row['folder']);status=read(folder/'status.json')
        if status.get('state') not in ('complete','physically_invalid'):raise ValueError('Incomplete floor: '+str(key))
        pb=read(folder/'playback.json');summary=read(folder/'summary.json');evidence=read(folder/'cfast-evidence.json')
        expected=building_hashes[row['building']]
        assert pb['building_sha256']==expected
        assert read(folder/'request.json')['building_sha256']==expected
        assert read(folder/'input.json')['cad']['building_sha256']==expected
        assert pb['engine_kind']=='cfast_native' and pb['complete'] and pb['time_s'][-1]==3600
        assert pb['fire_key']==row['room'] and pb['condition_version']=='physics_p0_v3'
        from pyrocast_cfbt.floor_flux import gauges
        points=[g for g in gauges(read(folder/'scenario.json')) if g['room']==row['room']]
        deck=(folder/'CFAST/case.in').read_text('ascii')
        assert len(points)==64 and all("ID='"+g['id']+"'" in deck for g in points)
        assert sha((folder/'CFAST/case.in').read_bytes())==evidence['input_sha256']
        for name,digest in evidence['files'].items():
            assert sha((folder/name).read_bytes())==digest,name
        rel=Path('model-library')/row['building']/row['job'];dest=ROOT/'saved_results'/rel
        dest.mkdir(parents=True,exist_ok=True)
        optional=('operator-runtime-extension.json',) if (folder/'operator-runtime-extension.json').is_file() else ()
        if optional:
            extension=read(folder/optional[0])
            assert extension['status']=='native_exited' and extension['native_exit_code']==0
            assert extension['input_sha256']==evidence['input_sha256']
        for name in FILES+optional:
            src=folder/name;data=src.read_bytes();out=dest/(name+'.gz');out.parent.mkdir(parents=True,exist_ok=True)
            if out.exists():
                if gzip.decompress(out.read_bytes())!=data:raise ValueError('Refusing to replace a published sample')
            else:out.write_bytes(gzip.compress(data,compresslevel=9,mtime=0))
            inventory.append(dict(path=(rel/(name+'.gz')).as_posix(),sha256=sha(data),bytes=len(data)))
        brief=ensure(folder/'playback.json')
        atomic_json(dest/'briefing.json',brief)
        origin=pb['solvers'][row['room']]
        maxima={}
        for kind,label in [('FO','FO'),('FGI','FGI'),('backdraft','BD')]:
            vals=[v for v in origin['conditions'][kind]['scores']['degree'] if isinstance(v,(int,float))]
            maxima[label]=round(max(vals)*100,3) if vals else None
        metrics=summary['physical_validation']['metrics']
        rows.append(dict(building=row['building'],label=row['label'],floor=row['floor'],room=row['room'],job=row['job'],
            path=rel.as_posix(),state=status['state'],engine='CFAST 7.7.7',wall_s=status['wall_s'],
            fire_room_indices=maxima,first_FO_s=origin['conditions']['FO'].get('first_met_s'),
            max_pressure_Pa=metrics['max_abs_pressure_Pa'],mass_balance_error=metrics['mass_balance_error'],
            upper_temperature_max_C=max(origin['Tu']),opening_state=row['opening_state'],
            geometry_correction_count=len(row.get('width_corrections',[])),
            equivalent_apertures=row.get('geometry_notes'),input_sha256=evidence['files']['input.json'],
            physical_validation=summary['physical_validation'],runtime_extension=read(folder/'operator-runtime-extension.json')))
        print(row['building'],row['floor'],status['state'],maxima,flush=True)
    target=ROOT/'saved_results/floor-samples-20261108';target.mkdir(exist_ok=True)
    report=dict(schema='firelapse.floor-samples-published/1',date='2026-11-08',count=len(rows),duration_s=3600,
                batch_wall_s=plan.get('finished_at',0)-plan.get('created_at',0),building_hashes=building_hashes,
                engine='CFAST 7.7.7',origin_floor_gauges=64,display_decimal_places=5,mc=False,
                valid_count=sum(r['physical_validation']['status']=='valid' for r in rows),
                invalid_count=sum(r['physical_validation']['status']=='physically_invalid' for r in rows),
                unverified_count=sum(r['physical_validation']['status']=='unverified' for r in rows),
                selection='Existing highest-ranked eligible room on each floor',rows=rows,
                raw_csv='Kept in local new-result folders; Git contains replay, full-precision analysis, inputs, native deck and hashes.')
    atomic_json(target/'manifest.json',report);atomic_json(target/'files.json',inventory)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('plan',type=Path);main(p.parse_args().plan)
