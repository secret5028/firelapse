"""Distribution-only result policy. Never rewrite a result or its evidence."""
import json
from pathlib import Path

LITE_ENGINES={'lite','pyrocast_lite'}

def _read(path):
    try:return json.loads(path.read_text('utf-8-sig'))
    except (OSError,ValueError):return {}

def result_policy(root):
    root=Path(root).resolve()
    playbacks=list(root.rglob('playback.json')) if root.exists() else []
    lite=[];native=[];removed=[]
    for p in playbacks:
        value=_read(p);engine=value.get('engine_kind')
        if engine in LITE_ENGINES:
            lite.append(p.parent);removed.append(dict(path=p.relative_to(root).as_posix(),engine_kind=engine,bytes=p.stat().st_size))
        elif engine=='cfast_native':native.append(p.parent)
    # Parent MC aggregates are not valid when their Lite samples are omitted.
    lite_jobs={p.parent for p in lite if p.name.startswith('S') and p.name[1:].isdigit()}
    def keep(path):
        path=Path(path).resolve()
        if not path.is_relative_to(root):raise ValueError('Result file outside packaging root')
        if path.name=='source-scenario.json':return True # required immutable factory input
        owners=[p for p in lite+native if path.is_relative_to(p)]
        if owners:return max(owners,key=lambda p:len(p.parts)) in native
        if path.parent in lite_jobs and path.name not in ('request.json','input.json'):
            return False
        if path.name=='playback-catalog.json':return False # rebuilt in external cache
        if path.name in ('result.json','summary.json','mc-summary.json','index-summary.json') and _read(path).get('engine_kind') in LITE_ENGINES:
            return False
        if path.relative_to(root).parts[0].startswith(('lite_v8_','mc-numerical-fix-')):
            return any(p.is_relative_to(path.parent) for p in native)
        return True
    return keep,native,removed

def filter_bundle_results(app):
    """Delete only excluded files in an isolated distribution copy, with evidence."""
    app=Path(app).resolve();root=app/'simulation/results'
    keep,native,cases=result_policy(root);removed=[]
    for p in sorted(root.rglob('*')):
        if not p.is_file() or keep(p):continue
        resolved=p.resolve()
        if not resolved.is_relative_to(root.resolve()) or p.is_symlink():raise ValueError('Unsafe distribution cleanup path')
        removed.append(dict(path=p.relative_to(app).as_posix(),bytes=p.stat().st_size));p.unlink()
    remaining=[p.relative_to(app).as_posix() for p in root.rglob('playback.json') if _read(p).get('engine_kind') in LITE_ENGINES]
    if remaining:raise ValueError('Lite playback remains: '+str(remaining))
    return dict(removed_lite_cases=cases,removed_files=removed,removed_bytes=sum(r['bytes'] for r in removed),remaining_lite_playbacks=len(remaining),preserved_native_playbacks=len(native))


def filter_bundle_standalone(bundle):
    """Exclude embedded Lite replays from an isolated package, not source samples."""
    import base64,gzip,re
    bundle=Path(bundle).resolve();removed=[];native=[]
    pattern=re.compile(r'<script\s+id=["\']pcOfflineData["\'][^>]*>(.*?)</script>',re.S)
    for path in sorted(bundle.rglob('*.html')):
        match=pattern.search(path.read_text('utf-8-sig'))
        if not match:continue
        value=json.loads(gzip.decompress(base64.b64decode(match[1].strip(),validate=True)))
        engines={v.get('engine_kind') for v in value.get('routes',{}).values() if isinstance(v,dict) and 'solvers' in v}
        if engines & LITE_ENGINES:
            if 'cfast_native' in engines:raise ValueError('Mixed native/Lite standalone sample; manual review required')
            if path.is_symlink() or not path.resolve().is_relative_to(bundle):raise ValueError('Unsafe standalone cleanup path')
            removed.append(dict(path=path.relative_to(bundle).as_posix(),bytes=path.stat().st_size,engine_kinds=sorted(engines)))
            path.unlink()
        elif 'cfast_native' in engines:native.append(path.relative_to(bundle).as_posix())
    return dict(removed_lite_html=removed,removed_bytes=sum(r['bytes'] for r in removed),preserved_native_html=native)
