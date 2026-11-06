"""Preview-first cleanup of completed calculation artifacts, never model inputs/results."""
import hashlib, json, os, secrets, threading, time
from pathlib import Path
from contextlib import contextmanager
from result_catalog import read, atomic_json
from runtime_storage import DATA_ROOT, result_roots
from export_ui_attention import result_index

_PLANS={}
_LOCK=threading.RLock()
RAW_NAMES={'result.json','state.npz','console.txt','stdout.txt','stderr.txt','solver.log','case.log','case.out','case.err'}
RAW_CSV={'case_compartments.csv','case_devices.csv','case_masses.csv','case_species.csv','case_vents.csv','case_walls.csv','case_resid.csv'}
END={'complete','completed','failed','interrupted','cancelled'}


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def plain(path, root):
    """Reject symlinks/junctions, including any ancestor, before traversal or unlink."""
    path=Path(path);root=Path(root)
    try:rel=path.relative_to(root)
    except ValueError:return False
    for p in [root,*[root.joinpath(*rel.parts[:i]) for i in range(1,len(rel.parts)+1)]]:
        if p.is_symlink() or getattr(p,'is_junction',lambda:False)():return False
        try:
            if getattr(p.lstat(),'st_file_attributes',0)&0x400:return False
        except OSError:return False
    return path.resolve().is_relative_to(root.resolve())


def blocked(folder,root):
    for parent in [folder,*folder.parents]:
        if not parent.is_relative_to(root):break
        for name in ('progress.json','status.json'):
            p=parent/name
            if p.exists():
                state=read(p,{})
                if not isinstance(state,dict) or state.get('state') not in END:return True
        if (parent/'batch.lock').exists():return True
    return False


def sealed_index(folder):
    raw=folder/'result.json'
    if not raw.exists():
        if (folder/'portable-result-index.json').is_file():result_index(raw)
        return None
    if read(folder/'playback.json',{}).get('engine_kind')!='pyrocast_lite':return None
    index=result_index(raw)
    if not index.get('complete'):raise ValueError('미완료 원시 결과')
    return {'schema':'firelapse.portable-result-index/1','playback_sha256':sha(folder/'playback.json'),
            'index':index,'index_sha256':hashlib.sha256(json.dumps(index,sort_keys=True,separators=(',',':')).encode()).hexdigest()}


def collect():
    records=[];skipped=0
    for root in result_roots():
        if not root.is_dir() or not plain(root,root):continue
        for directory,dirs,files in os.walk(root,followlinks=False):
            folder=Path(directory)
            if folder==root:dirs[:]=[n for n in dirs if n in ('model-library','lite_mc_jobs','fixed-calculations','cad_interactive')]
            dirs[:]=[n for n in dirs if not n.startswith(('github-publish','ui_','.')) and n not in ('node_modules','__pycache__') and plain(folder/n,root)]
            if 'playback.json' not in files:continue
            if not plain(folder,root) or blocked(folder,root):skipped+=1;dirs[:]=[];continue
            pb=read(folder/'playback.json',{})
            # A final replay and saved reproducible input are both required.
            if not isinstance(pb,dict) or not pb.get('complete') or not pb.get('time_s') or not pb.get('rooms') or not any((folder/n).is_file() for n in ('input.json','sample.json','scenario.json')):
                skipped+=1;continue
            candidates=[];protected=[];valid=True
            for sub,subdirs,names in os.walk(folder,followlinks=False):
                base=Path(sub);subdirs[:]=[n for n in subdirs if plain(base/n,root)]
                if blocked(base,root):valid=False;break
                for name in names:
                    p=base/name
                    if not plain(p,root):valid=False;break
                    # Only known solver artifacts; unknown files, inputs, manifests and reports stay.
                    if name in RAW_NAMES|RAW_CSV or name.endswith('.tmp'):
                        st=p.stat();candidates.append({'path':str(p),'size':st.st_size,'mtime':st.st_mtime_ns})
                    else:protected.append({'path':str(p),'sha256':sha(p)})
            if not valid or not candidates:continue
            try:
                seal=sealed_index(folder)
            except (ValueError,OSError,KeyError,TypeError):skipped+=1;continue
            # result_index can create a small derived index; include it in the preservation audit.
            protected=[r for r in protected if Path(r['path']).name not in ('index-summary.json','portable-result-index.json')]
            records.append({'folder':str(folder),'root':str(root),'files':candidates,'protected':protected,'seal':seal})
            dirs[:]=[]
    return records,skipped


@contextmanager
def exclusive():
    DATA_ROOT.mkdir(parents=True,exist_ok=True)
    with (DATA_ROOT/'cleanup.lock').open('a+b') as f:
        f.seek(0);f.write(b'0');f.flush();f.seek(0)
        if os.name=='nt':
            import msvcrt
            try:msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
            except OSError:raise RuntimeError('다른 정리 작업이 실행 중입니다')
        else:
            import fcntl
            fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield
        finally:
            f.seek(0)
            if os.name=='nt':msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(f,fcntl.LOCK_UN)


def preview():
    with _LOCK,exclusive():
        rows,skipped=collect();token=secrets.token_urlsafe(24)
        _PLANS.clear();_PLANS[token]=(time.monotonic(),rows)
        return {'token':token,'data_path':str(DATA_ROOT),'scope':'이 PC의 전체 계산',
                'bytes':sum(f['size'] for r in rows for f in r['files']),
                'files':sum(len(r['files']) for r in rows),'calculations':len(rows),'skipped':skipped}


def cleanup(token):
    with _LOCK,exclusive():
        when,rows=_PLANS.pop(token,(0,None))
        if rows is None or time.monotonic()-when>600:raise ValueError('용량을 다시 확인하세요')
        # Revalidate the complete preview before deleting any candidate.
        for row in rows:
            folder=Path(row['folder']);root=Path(row['root'])
            if not plain(folder,root) or blocked(folder,root):raise ValueError('계산 상태 변경: 다시 확인하세요')
            for item in row['files']:
                p=Path(item['path'])
                if not plain(p,root) or blocked(p.parent,root):raise ValueError('경로 또는 계산 상태 변경')
                st=p.stat()
                if [st.st_size,st.st_mtime_ns]!=[item['size'],item['mtime']]:raise ValueError('파일 변경: 다시 확인하세요')
            for item in row['protected']:
                p=Path(item['path'])
                if not plain(p,root) or sha(p)!=item['sha256']:raise ValueError('보존 파일 변경: 다시 확인하세요')
        released=0;count=0;errors=[]
        for row in rows:
            folder=Path(row['folder'])
            if row['seal']:
                atomic_json(folder/'portable-result-index.json',row['seal'])
                # Verify the sealed value before releasing the raw matrix.
                if read(folder/'portable-result-index.json')!=row['seal']:raise ValueError('요약 저장 검증 실패')
            for item in row['files']:
                p=Path(item['path'])
                try:
                    if not plain(p,Path(row['root'])) or blocked(p.parent,Path(row['root'])):raise OSError('경로/상태 변경')
                    p.unlink();released+=item['size'];count+=1
                except OSError as exc:errors.append({'file':p.name,'error':str(exc)})
            atomic_json(folder/'cleanup-receipt.json',{'at':time.time(),'preserved':'inputs, playback, MC summaries, provenance','deleted':[i['path'] for i in row['files'] if not Path(i['path']).exists()]})
        return {'bytes':released,'files':count,'errors':errors}


def handle(handler,path):
    if path not in ('/cfbt/storage/preview','/cfbt/storage/cleanup'):return False
    from urllib.parse import urlsplit
    host=handler.headers.get('Host','');origin=handler.headers.get('Origin')
    allowed_host=host.split(':')[0] in ('127.0.0.1','localhost')
    if handler.client_address[0] not in ('127.0.0.1','::1') or not allowed_host or origin not in (None,'http://'+host):
        handler.json({'error':'외부 요청 차단'},403);return True
    try:
        n=int(handler.headers.get('Content-Length','0'))
        if not 0<n<=1024:raise ValueError('요청 크기 오류')
        body=json.loads(handler.rfile.read(n))
        if path.endswith('/preview'):
            if body!={}:raise ValueError('요청 형식 오류')
            value=preview()
        else:
            if not isinstance(body,dict) or set(body)!={'token'} or not isinstance(body['token'],str):raise ValueError('미리보기 필요')
            value=cleanup(body['token'])
        handler.json(value)
    except (ValueError,TypeError,KeyError,OSError,RuntimeError) as exc:handler.json({'error':str(exc)},409)
    return True
