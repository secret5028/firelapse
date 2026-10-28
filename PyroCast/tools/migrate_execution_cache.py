"""One-time migration using the exact previous server bytes, never an invented key."""
import argparse
import hashlib
from pathlib import Path
from cache_key_aliases import CacheAliases,legacy_execution_key
from serve_cfbt_building import SIM,execution_key


def migrate(source):
    data=Path(source).read_bytes()
    engines={'native':SIM/'build/mixture_r2/cfbt/cfast-cfbt.exe','r8':SIM/'build/baseline/cfast-baseline.exe'}
    return CacheAliases(SIM/'results').migrate(
        lambda kind,options,sha:legacy_execution_key(options,sha,engines[kind],SIM,data),
        lambda kind,options,sha:execution_key(options,sha,engines[kind]),hashlib.sha256(data).hexdigest())


if __name__=='__main__':
    import json
    p=argparse.ArgumentParser();p.add_argument('--legacy-server',type=Path,required=True)
    print(json.dumps(migrate(p.parse_args().legacy_server),ensure_ascii=False,indent=2))
