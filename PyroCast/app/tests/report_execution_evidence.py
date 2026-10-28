"""Read-only production verification: 42 archived cases and two MC results."""
import hashlib
import json
from pathlib import Path
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'simulation/results/ui_refactor_stage5A_evidence_20261028'
JOB = ROOT/'simulation/results/lite_mc_jobs/mc-1793171631584057100-c3f54953'


def read(path):
    return json.loads(path.read_text('utf-8-sig'))


def main():
    prior = read(ROOT/'simulation/results/ui_refactor_stage5A_cache_20261028/case-reuse.json')
    cases = [(r['kind'], r['id'], r['case_label'], False) for r in prior]
    cases += [('lite', 'case-4f1aaf47fcd5424d9d4f', 'R3 MC S00', True),
              ('lite', 'case-d51b948a8e78fb4b56a7', 'R3 MC S01', True)]
    rows = []
    for kind, key, label, expected in cases:
        start = time.perf_counter()
        with urlopen(f'http://127.0.0.1:8780/cfbt/reuse/{kind}/{key}', timeout=60) as response:
            value = json.load(response)
        assert value['equivalent'] is expected, (key, value)
        assert value['solver_runs'] == 0
        rows.append(dict(kind=kind, id=key, case_label=label, **value,
                         response_ms=round((time.perf_counter()-start)*1000, 2)))
    old = read(ROOT/'simulation/results/ui_refactor_stage5A_mc_20261028/run-report.json')
    unchanged = {r['id']: hashlib.sha256((JOB/r['id']/'playback.json').read_bytes()).hexdigest()
                 == r['playback_sha256'] for r in old['rows']}
    assert all(unchanged.values())
    with urlopen('http://127.0.0.1:8780/cfbt/lite/mc', timeout=30) as response:
        status = json.load(response)
    assert status['id'] == JOB.name and status['state'] == 'completed' and not status['running']
    OUT.mkdir(parents=True, exist_ok=True)
    report = dict(rows=rows, historical=42, equivalent=2, solver_runs=0,
                  playback_unchanged=unchanged, mc_status=status)
    (OUT/'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', 'utf-8')
    lines = ['| 유형 | ID | 사례 | 판정 | 재계산 |', '|---|---|---|---|---:|']
    lines += [f"| {r['kind']} | {r['id']} | {r['case_label']} | {r['label']} | 0 |" for r in rows]
    (OUT/'cases.md').write_text('\n'.join(lines)+'\n', 'utf-8')
    print(json.dumps({k: report[k] for k in ('historical', 'equivalent', 'solver_runs', 'playback_unchanged')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
