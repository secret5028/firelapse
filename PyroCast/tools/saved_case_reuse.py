"""Read-only case reuse, distinct from a verified current-engine execution cache."""
from pathlib import Path
from result_catalog import read


def describe(row,kind,building_sha,execution_cache,new_key_for):
    folder=Path(row['path']).parent
    if kind=='lite':
        from execution_evidence import verify
        equivalent,reason=verify(folder,building_sha)
        if equivalent:
            return dict(case_id=row['id'],reuse_kind='verified_cache',label='동등 · 검증된 결과 재사용',equivalent=True,solver_runs=0,
                        evidence='execution-evidence.json',reason=reason)
        return dict(case_id=row['id'],reuse_kind='historical_result',label='과거 결과 재사용',equivalent=False,solver_runs=0,reason=reason)
    proof=read(folder/'execution-request.json')
    reason='exact current input/engine/dependency proof was not stored; archived output only'
    if kind=='native' and proof and isinstance(proof.get('options'),dict) and proof.get('building_sha256')==building_sha:
        key=new_key_for('native',proof['options'],building_sha)
        hit=execution_cache.lookup('native',key,building_sha)
        if hit and hit[0]==folder.resolve():
            return dict(case_id=row['id'],reuse_kind='verified_cache',label='검증된 캐시 반환',equivalent=True,solver_runs=0,request_id=key)
        reason='current execution fingerprint or sealed output does not match'
    return dict(case_id=row['id'],reuse_kind='historical_result',label='과거 결과 재사용',equivalent=False,solver_runs=0,reason=reason)
