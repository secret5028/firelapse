"""Refresh code in a verified portable release while preserving its saved payload.

The base ZIP is immutable input. No solver or application server is started.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[2]
EXCLUDED={'__pycache__','.git','node_modules','.venv'}

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()

def files(root):
    return sorted(p for p in root.rglob('*') if p.is_file() and not EXCLUDED.intersection(p.relative_to(root).parts) and p.suffix not in ('.pyc','.pyo'))

def protected(path):
    return (path.startswith(('runtime/','licenses/','app/simulation/results/','app/simulation/build/','app/simulation/deps/','app/simulation/plot_deps/','app/simulation/vendor/'))
            or path.startswith('app/data/') and Path(path).suffix not in ('.js','.html','.css'))

def source_code(rel):
    if rel.startswith(('app/web/','app/model-library/','tools/','simulation/viewer/','simulation/pyrocast_cfbt/','simulation/pyrocast_lite/')):
        return True
    if rel.startswith(('simulation/tests/','app/tests/','simulation/results/','saved_results/','simulation/deps/','simulation/plot_deps/','simulation/build/','simulation/vendor/')):
        return False
    if rel.startswith('data/'):return Path(rel).suffix in ('.js','.html','.css')
    return (rel.startswith(('config/','simulation/config/')) and rel not in ('simulation/config/lite-viewer.json','simulation/config/lite-screening-selection.json')) or (Path(rel).suffix=='.py' and len(Path(rel).parts)<=2)

def stage(args):
    if sha(args.base_zip)!=args.base_sha256:raise ValueError('Base archive SHA256 mismatch')
    if args.output.exists() and any(args.output.iterdir()):raise ValueError('Output must be new/empty')
    args.output.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.base_zip) as z:
        for n in z.namelist():
            dest=(args.output/n).resolve()
            if not dest.is_relative_to(args.output.resolve()) or not n.startswith('FireLapse/'):raise ValueError('Unsafe archive path')
        if z.testzip():raise ValueError('Base archive CRC failure')
        z.extractall(args.output)
    bundle=args.output/'FireLapse'
    before={p.relative_to(bundle).as_posix():sha(p) for p in files(bundle)}
    names=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode('utf8').split('\0')
    source_manifest={}
    for name in names:
        if not name.startswith('PyroCast/'):continue
        rel=name[len('PyroCast/'):]
        if not source_code(rel):continue
        source=ROOT/name;dest=bundle/'app'/rel
        if not source.is_file():continue
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
        source_manifest[rel]=sha(source)
    for name in ('README.md','LICENSE','THIRD_PARTY_NOTICES.md','KNOWN_ISSUES.md'):
        shutil.copyfile(ROOT/name,bundle/name)
    shutil.copyfile(ROOT/'PyroCast/README.md',bundle/'app/README.md')
    for p in (ROOT/'docs').rglob('*'):
        if p.is_file():
            dest=bundle/'docs'/p.relative_to(ROOT/'docs');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    # Restore the dedicated Wando playback omitted from r17; never overwrite a result.
    wando='data/wando-coldstore/P1-playback.json'
    src=ROOT/'PyroCast'/wando;dest=bundle/'app'/wando
    if not dest.exists():
        shutil.copyfile(src,dest)
    if sha(src)!=sha(dest):raise ValueError('Dedicated Wando result differs from source')
    source_manifest[wando]=sha(src)
    meta=json.loads((bundle/'distribution.json').read_text('utf8'))
    meta.update(version=args.version,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                source_branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
                base_archive=args.base_zip.name,base_sha256=args.base_sha256,new_simulations=0)
    (bundle/'distribution.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n','utf8')
    (bundle/'source-files.json').write_text(json.dumps(source_manifest,indent=2)+'\n','utf8')
    changed=[n for n,h in before.items() if not (bundle/n).is_file() or sha(bundle/n)!=h]
    violation=[n for n in changed if protected(n)]
    if violation:raise ValueError('Protected payload changed: '+str(violation))
    proof=dict(base_archive=args.base_zip.name,base_sha256=args.base_sha256,changed=changed,
               added=[p.relative_to(bundle).as_posix() for p in files(bundle) if p.relative_to(bundle).as_posix() not in before],
               protected_files=sum(protected(n) for n in before),protected_changes=violation,
               source_files=len(source_manifest))
    (args.output/'source-payload-verification.json').write_text(json.dumps(proof,indent=2),'utf8')
    print(json.dumps(proof,ensure_ascii=False),flush=True)

def archive(args):
    bundle=args.output/'FireLapse'
    source=json.loads((bundle/'source-files.json').read_text('utf8'))
    for rel,digest in source.items():
        if sha(ROOT/'PyroCast'/rel)!=digest or sha(bundle/'app'/rel)!=digest:raise ValueError('Source/bundle mismatch: '+rel)
    manifest={p.relative_to(bundle).as_posix():sha(p) for p in files(bundle) if p.name!='files.sha256.json'}
    (bundle/'files.sha256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf8')
    dest=args.output/f'FireLapse-Windows-x64-{args.version}.zip'
    with zipfile.ZipFile(dest,'x',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for p in files(bundle):z.write(p,'FireLapse/'+p.relative_to(bundle).as_posix())
    with zipfile.ZipFile(dest) as z:
        if z.testzip():raise ValueError('Release CRC failure')
        count=len(z.infolist())
    digest=sha(dest)
    report=dict(archive=dest.name,bytes=dest.stat().st_size,sha256=digest,files=count,crc='PASS',
                source_files=len(source),source_match='PASS',payload=json.loads((args.output/'source-payload-verification.json').read_text('utf8')))
    (args.output/'VERIFICATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n','utf8')
    (args.output/'SHA256SUMS.txt').write_text(digest+'  '+dest.name+'\n','ascii')
    print(json.dumps({k:v for k,v in report.items() if k!='payload'}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['stage','zip'],required=True)
    parser.add_argument('--base-zip',type=Path)
    parser.add_argument('--base-sha256')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--version',required=True)
    args=parser.parse_args()
    if args.phase=='stage' and (not args.base_zip or not args.base_sha256):parser.error('stage requires base ZIP and its verified SHA256')
    (stage if args.phase=='stage' else archive)(args)
