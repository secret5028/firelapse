"""Execution provenance for saved lite MC results; never integrates a model.

Old results are not upgraded without their actual job input, sample, start hash
ledger and compiled rule manifest. A failed check always falls back to history.
"""
import hashlib
import json
import sys
from functools import lru_cache
from pathlib import Path

from result_catalog import atomic_json, read

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'simulation'), str(ROOT/'simulation/deps')]
SCHEMA = 'pyrocast.execution-evidence/1'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


@lru_cache(maxsize=256)
def _file_hash(path, size, modified):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def file_hash(path):
    path = Path(path).resolve()
    st = path.stat()
    return _file_hash(str(path), st.st_size, st.st_mtime_ns)


def engine_hashes():
    return {p.relative_to(ROOT).as_posix(): file_hash(p)
            for p in sorted((ROOT/'simulation/pyrocast_lite').glob('*.py'))}


def rule_dependency_hashes():
    return {p.relative_to(ROOT).as_posix(): file_hash(p)
            for p in sorted((ROOT/'simulation/pyrocast_cfbt').glob('*.py'))}


def normalized_hashes(values):
    return {k.replace('\\', '/'): v for k, v in values.items()}


def door_snapshot(model):
    # These are the corrections actually applied to this saved input. An absent
    # override file today is not evidence about an old run.
    fields = ('door_class', 'door_class_basis', 'door_class_confidence',
              'door_class_reason', 'door_class_revision', 'door_source_fire_flag')
    return {v['id']: {k: v[k] for k in fields if k in v}
            for v in model['openings'] if 'door_class' in v}


def user_doors(model):
    return {v['id']: v['door_class'] for v in model['openings']
            if v.get('door_class_confidence') == 'user'}


def _inputs(folder):
    folder = Path(folder).resolve()
    if not folder.is_relative_to((ROOT/'simulation/results/lite_mc_jobs').resolve()):
        raise ValueError('Not a server MC job result')
    job = folder.parent
    request = read(job/'request.json')
    started = read(job/'started.json')
    raw = read(job/'input.json')
    sample = read(folder/'sample.json')
    summary = read(folder/'summary.json')
    if not all(isinstance(x, dict) for x in (request, started, raw, sample, summary)):
        raise ValueError('Missing job provenance')
    if not summary.get('complete') or summary.get('selected_attempt') not in ('BDF', 'Radau'):
        raise ValueError('Incomplete result')
    attempt = summary['selected_attempt']
    manifest = read(folder/attempt/'rule_manifest.json')
    if not manifest or started.get('building_sha256') != request['building_sha256']:
        raise ValueError('Missing or inconsistent manifest/building')
    return job, request, started, raw, sample, summary, manifest


def _current_matches(request, started, raw, sample, manifest):
    from lite_mc_service import prepare_request
    from run_lite_mc_v8_r2 import PARAMS
    from pyrocast_lite.montecarlo import make_samples
    from pyrocast_cfbt.room_rule_r8 import prepare
    hashes = normalized_hashes(started.get('sha256', {}))
    if hashes != engine_hashes():
        raise ValueError('Engine source ledger differs from current engine')
    if started.get('parameters') != PARAMS:
        raise ValueError('Execution parameters changed')
    body = {k: request[k] for k in ('room', 'samples', 'duration_s', 'seed')}
    if request.get('manual'):body['manual']=True
    _, current = prepare_request(body, request['building_sha256'])
    if digest(current) != digest(raw):
        raise ValueError('Current input, fuel settings or door corrections changed')
    from lite_fixed_openings import sample_fixed_states
    samples = make_samples(current, seed=request['seed'], count=request['samples'], fixed_states=sample_fixed_states(current))
    expected = next((s for s in samples if s['id'] == sample['id']), None)
    if expected is None or digest(expected['scenario']) != digest(sample['scenario']):
        raise ValueError('Sample input differs')
    # Compiles rules only. No run(), solve_ivp(), or CFAST invocation.
    _, _, current_manifest = prepare(sample['scenario'])
    if digest(current_manifest) != digest(manifest):
        raise ValueError('Compiled rules differ from the run-time manifest')


def write_mc(folder, *, backfill=False):
    folder = Path(folder).resolve()
    job, request, started, raw, sample, summary, manifest = _inputs(folder)
    # Save the recorded run even if current settings have since changed. The
    # reader decides equivalence. Never substitute today's engine for the log.
    hashes = normalized_hashes(started['sha256'])
    # Older jobs did not log hashes of the shared rule sources. Validate their
    # compiled manifest now, then lock this verification context for later reads.
    # Do not mislabel these verification-time hashes as run-time engine hashes.
    if backfill:
        _current_matches(request, started, raw, sample, manifest)
    refs = ['../request.json', '../started.json', '../input.json', 'sample.json',
            'summary.json', summary['selected_attempt']+'/rule_manifest.json',
            'playback.json', 'result.json', 'index-summary.json']
    evidence = dict(schema=SCHEMA, engine_kind='pyrocast_lite',
        building_sha256=request['building_sha256'],
        input_snapshot_sha256=digest(sample['scenario']),
        job_input_sha256=digest(raw), engine_files=hashes, engine_sha256=digest(hashes),
        parameters=started['parameters'], rule_settings=manifest['rule_settings'],
        rule_manifest_sha256=digest(manifest), door_corrections=door_snapshot(raw),
        applied_user_door_overrides=user_doors(raw),
        verification_rule_dependencies=started.get('shared_rule_sha256', rule_dependency_hashes()),
        files={name: file_hash(folder/name) for name in refs},
        provenance=dict(job=job.name, sample=sample['id'], backfilled=backfill,
            engine_source='job started.json sha256 ledger',
            input_source='job input.json and sample.json scenario',
            rule_source=summary['selected_attempt']+'/rule_manifest.json',
            door_source='applied classifications in job input.json',
            shared_source_hash_basis='job started.json' if 'shared_rule_sha256' in started else
                'evidence creation time; compiled manifest verified against run log',
            equivalence_scope='same saved sample under current source inputs, engine source and compiled rules; not physical accuracy'))
    atomic_json(folder/'execution-evidence.json', evidence)
    return evidence


def verify(folder, building_sha):
    folder = Path(folder).resolve()
    evidence = read(folder/'execution-evidence.json')
    if not evidence:
        return False, 'No execution-evidence.json'
    try:
        if evidence.get('schema') != SCHEMA or evidence.get('building_sha256') != building_sha:
            raise ValueError('Evidence schema or building mismatch')
        job, request, started, raw, sample, summary, manifest = _inputs(folder)
        required = {'../request.json', '../started.json', '../input.json', 'sample.json',
                    'summary.json', summary['selected_attempt']+'/rule_manifest.json',
                    'playback.json', 'result.json', 'index-summary.json'}
        if set(evidence.get('files', {})) != required:
            raise ValueError('Incomplete file seal')
        for name, value in evidence['files'].items():
            if file_hash(folder/name) != value:
                raise ValueError('Saved file changed: '+name)
        hashes = normalized_hashes(started['sha256'])
        if evidence.get('verification_rule_dependencies') != rule_dependency_hashes():
            raise ValueError('Shared rule/condition source changed since evidence verification')
        if ('shared_rule_sha256' in started and
                evidence['verification_rule_dependencies'] != started['shared_rule_sha256']):
            raise ValueError('Shared rule source does not match execution log')
        if (evidence.get('engine_files') != hashes or evidence.get('engine_sha256') != digest(hashes)
                or evidence.get('input_snapshot_sha256') != digest(sample['scenario'])
                or evidence.get('job_input_sha256') != digest(raw)
                or evidence.get('parameters') != started['parameters']
                or evidence.get('rule_settings') != manifest['rule_settings']
                or evidence.get('rule_manifest_sha256') != digest(manifest)
                or evidence.get('door_corrections') != door_snapshot(raw)
                or evidence.get('applied_user_door_overrides') != user_doors(raw)):
            raise ValueError('Evidence does not match execution logs')
        _current_matches(request, started, raw, sample, manifest)
        return True, 'Saved input, engine source, rule manifest and applied door corrections match current values'
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        return False, str(exc)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--backfill', type=Path, nargs='+', required=True)
    for folder in p.parse_args().backfill:
        e = write_mc(folder, backfill=True)
        ok, reason = verify(folder, e['building_sha256'])
        print(json.dumps(dict(folder=str(folder), equivalent=ok, reason=reason), ensure_ascii=False))
        if not ok:
            raise SystemExit(1)
