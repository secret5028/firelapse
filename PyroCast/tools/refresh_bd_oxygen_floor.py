"""Re-score saved inverse-oxygen diagnostics. No simulation or physical edit.

Explicit roots only; original files are archived before replacement.
"""
import argparse
import copy
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'simulation'), str(ROOT/'simulation/deps')]
import numpy as np
from pyrocast_cfbt.conditions import screening_scores, OXYGEN_SCORE_FLOOR, OXYGEN_SCORE_REVISION
from pyrocast_lite.montecarlo import aggregate
from result_catalog import read, atomic_json
from export_ui_attention import result_index


def refresh_record(rec):
    if rec.get('status') == 'not_evaluated': return False
    old = rec.get('scores', {})
    if old.get('oxygen_numeric_guard', {}).get('revision') == OXYGEN_SCORE_REVISION: return False
    terms = {t['key']:t for t in rec.get('terms', [])}
    if not all(k in terms for k in ('Tu', 'Yf', 'O2')) or 'degree' not in old: return False
    o = terms['O2']['value']
    if not any(v is not None and np.isfinite(v) and v < OXYGEN_SCORE_FLOOR for v in o): return False
    specs = [(terms[k]['value'], terms[k]['threshold'], k == 'O2') for k in ('Tu', 'Yf', 'O2')]
    fresh = screening_scores(*specs, len(o), old.get('legacy_context_met', rec.get('all_met')))
    for k in ('temperature', 'fuel'): assert old['factors'][k] == fresh['factors'][k]
    rec['scores'] = fresh
    if 'score_coverage' in rec:
        known = sum(v is not None for v in fresh['degree'])
        rec['score_coverage'] = dict(known_samples=known, total_samples=len(o))
        rec['status'] = 'evaluated' if known == len(o) else 'partially_evaluated' if known else 'not_evaluated'
    return True


def refresh_document(doc):
    """Only backdraft records may change; all physical series remain exact."""
    records = ([s.get('conditions', {}) for s in doc['solvers'].values()] if 'solvers' in doc
               else list(doc.get('shared_conditions', {}).get('rooms', {}).values()))
    changed = 0
    for records_by_kind in records:
        rec = records_by_kind.get('backdraft')
        if rec and refresh_record(rec): changed += 1
    return changed


def physical_digest(doc):
    value = copy.deepcopy(doc)
    records = ([s.get('conditions', {}) for s in value['solvers'].values()] if 'solvers' in value
               else list(value.get('shared_conditions', {}).get('rooms', {}).values()))
    for rec in records: rec.pop('backdraft', None)
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def bd_summary(playback):
    t = np.array(playback['time_s']); groups = {}; scores = []
    for r in playback['rooms']:
        rec = playback['solvers'][r['solver_id']]['conditions']['backdraft']
        if rec.get('status') == 'not_evaluated': raise ValueError('Cannot aggregate unevaluated BD')
        values = rec['scores']['degree']
        mask = np.array([v is not None and v >= 1 for v in values])
        room = r.get('original_room', r['key'])
        groups[room] = groups.get(room, np.zeros(len(t), bool)) | mask
        scores.extend(v for v in values if v is not None)
    hits = {room:float(t[np.flatnonzero(mask)[0]]) for room, mask in groups.items() if mask.any()}
    return dict(ever_room_count=len(hits), rooms=hits, first_s=min(hits.values(), default=None),
        max_simultaneous_room_count=int(np.stack(list(groups.values())).sum(axis=0).max()),
        score_max=max(scores, default=None), score_median=float(np.median(scores)) if scores else None)


def run(roots, output):
    output.mkdir(parents=True, exist_ok=True)
    changes=[]; batches=set(); comparisons=[]
    with zipfile.ZipFile(output/'before.zip', 'x', zipfile.ZIP_DEFLATED) as archive:
        backed=set()
        def backup(path):
            if path.exists() and path not in backed:
                archive.write(path, path.relative_to(ROOT).as_posix());backed.add(path)
        def save(path, value):
            backup(path);atomic_json(path, value);changes.append(str(path.relative_to(ROOT)))
        paths=sorted({p for root in roots for p in root.rglob('playback.json')})
        for path in paths:
            pb=read(path);before=copy.deepcopy(pb);digest=physical_digest(pb)
            if not refresh_document(pb): continue
            assert digest == physical_digest(pb)
            for rid, s in pb['solvers'].items():
                old=before['solvers'][rid]['conditions']['backdraft']['scores']['degree']
                new=s['conditions']['backdraft']['scores']['degree']
                if old != new:
                    comparisons.append(dict(path=str(path.relative_to(ROOT)), cell=rid,
                        repaired_samples=sum(a is None and b is not None for a,b in zip(old,new)),
                        before_peak=max((v*100 for v in old if v is not None), default=None),
                        after_peak=max((v*100 for v in new if v is not None), default=None)))
            save(path,pb)
            for dest in [path.with_name('result.json'), path.parent/'BDF/result.json', path.parent/'Radau/result.json']:
                if not dest.exists(): continue
                result=read(dest);digest=physical_digest(result)
                if refresh_document(result):
                    assert digest == physical_digest(result)
                    save(dest,result);backup(dest.with_name('index-summary.json'));result_index(dest)
            dest=path.with_name('summary.json')
            summary=read(dest,{})
            if summary.get('phenomena',{}).get('backdraft'):
                summary['phenomena']['backdraft'].update(bd_summary(pb));save(dest,summary)
                batches.add(path.parent.parent)
        for folder in sorted(batches):
            dest=folder/'summaries.json'
            if not dest.exists(): continue
            rows=read(dest)
            for row in rows:
                current=read(folder/row['sample_id']/'summary.json',{})
                if current.get('phenomena',{}).get('backdraft'):
                    row['phenomena']['backdraft']=current['phenomena']['backdraft']
            save(dest,rows);fresh=aggregate(rows);dest=folder/'aggregate.json';old=read(dest)
            for key in ('condition_sample_rates_random_only','condition_rates_by_original_room_random_only','worst_including_mandatory'):
                value=fresh[key]['backdraft']
                if key=='condition_sample_rates_random_only':
                    value.pop('median_of_sample_medians',None)
                    maxima=[s['phenomena']['backdraft'].get('score_max') for s in rows if s.get('complete') and s['kind']=='random']
                    maxima=[v for v in maxima if v is not None]
                    value['median_of_sample_maxima']=float(np.median(maxima)) if maxima else None
                if key=='worst_including_mandatory' and value and value.get('sample_id'):
                    value['openings']=read(folder/value['sample_id']/'sample.json')['openings']
                old[key]['backdraft']=value
            save(dest,old);dest=folder/'mc-summary.json';summary=read(dest)
            summary['rates']['backdraft']=old['condition_sample_rates_random_only']['backdraft'];save(dest,summary)
    report=dict(revision=OXYGEN_SCORE_REVISION, floor_vol_percent=OXYGEN_SCORE_FLOOR,
        simulation_runs=0, physical_series_unchanged=True, changed_files=changes, comparisons=comparisons)
    atomic_json(output/'report.json',report)
    print(json.dumps(dict(changed_files=len(changes),changed_cells=len(comparisons),
        repaired_samples=sum(r['repaired_samples'] for r in comparisons)),ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',action='append',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    roots=[p.resolve() for p in args.root];out=args.output.resolve()
    if not all(p.is_relative_to(ROOT/'simulation/results') for p in roots): raise ValueError('Results roots only')
    if not out.is_relative_to(ROOT/'simulation/results'): raise ValueError('Backup must be inside results')
    run(roots,out)
