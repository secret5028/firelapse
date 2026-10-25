"""Compare all existing native/project CSV output lines, not just selected room metrics."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('before',type=Path);p.add_argument('after',type=Path)
p.add_argument('--prefix',action='store_true',help='Compare completed common lines only; no completeness claim')
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();records={}
for f in sorted(a.before.glob('case_*.csv')):
    if f.name in ('case_cfbt_radiation_cache.csv','case_cfbt_wall_cache.csv'):continue
    other=a.after/f.name
    if not other.exists():raise RuntimeError('Missing output '+str(other))
    # Native termination of a budget-limited run can leave an incomplete final row.
    x=f.read_bytes().splitlines(keepends=True);y=other.read_bytes().splitlines(keepends=True)
    x=[r.rstrip(b'\r\n') for r in x if r.endswith(b'\n')]
    y=[r.rstrip(b'\r\n') for r in y if r.endswith(b'\n')]
    n=min(len(x),len(y)) if a.prefix else max(len(x),len(y))
    equal=x[:n]==y[:n]
    records[f.name]={'identical':equal,'before_lines':len(x),'after_lines':len(y),'compared_lines':n}
result={'before':str(a.before.resolve()),'after':str(a.after.resolve()),'common_prefix_only':a.prefix,
        'all_identical':bool(records) and all(r['identical'] for r in records.values()),'files':records}
a.output.write_text(json.dumps(result,indent=2),'utf-8');print(json.dumps(result,indent=2))
if not result['all_identical']:raise SystemExit(1)
