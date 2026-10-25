"""Fetch only the pinned public CFAST sources needed for the native build."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import urllib.request
from engine_sources import VENDOR, source_lock, verify_upstream, digest
import hashlib

ROOT = VENDOR


def fetch(name):
    record=next(r for r in source_lock(ROOT)['files'] if r['file']==name+'.f90')
    path = ROOT/'Source'/record['file']
    if path.exists():
        if digest(path)!=record['sha256']:
            raise ValueError('Refusing to overwrite modified upstream source: '+name)
        return record
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = urllib.request.urlopen(record['url'], timeout=45).read()
    if hashlib.sha256(payload).hexdigest()!=record['sha256']:
        raise ValueError('Downloaded CFAST source differs from the pinned hash: '+name)
    path.write_bytes(payload)
    return record


if __name__ == "__main__":
    names=[Path(r['file']).stem for r in source_lock(ROOT)['files']]
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(fetch,names))
    verify_upstream(ROOT)
    print(f"Verified {len(records)} pinned source files in {ROOT}; source lock unchanged")
