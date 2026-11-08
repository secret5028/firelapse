"""Incremental playback-folder index. No simulation and no active-case replacement."""
import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path
import threading
import time
import uuid


def _io_path(path):
    path=Path(path)
    if os.name!='nt':
        return path
    absolute=os.path.abspath(path)
    if len(absolute)<240 or absolute.startswith('\\\\?\\'):
        return path
    if absolute.startswith('\\\\'):
        return Path('\\\\?\\UNC\\'+absolute[2:])
    return Path('\\\\?\\'+absolute)


def read(path, default=None):
    try: return json.loads(_io_path(path).read_text('utf-8'))
    except (OSError, ValueError): return default


def atomic_json(path, value):
    path=Path(path)
    tmp=_io_path(path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp'))
    path=_io_path(path)
    tmp.parent.mkdir(parents=True,exist_ok=True)
    try:
        tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n','utf-8')
        for attempt in range(5):
            try:
                tmp.replace(path)
                break
            except PermissionError as exc:
                if getattr(exc,'winerror',None) not in (5,32) or attempt==4:
                    raise
                time.sleep(.05)
    finally: tmp.unlink(missing_ok=True)


def playback_origin(data):
    """Map the fire cell back to the exact CAD room used by the scene picker."""
    key = data.get('fire_key')
    return next((room.get('original_room') or room['key']
                 for room in data.get('rooms', []) if key and room.get('key') == key), None)


def playback_coverage(data):
    if data.get('complete') is not True or len(data.get('time_s') or []) < 2:
        return []
    solvers = data.get('solvers') or {}
    return sorted({room.get('original_room') or room['key'] for room in data.get('rooms', [])
                   if room.get('key') and solvers.get(room.get('solver_id'))})


def playback_metadata(path):
    stat = path.stat()
    return _playback_metadata(path, stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=512)
def _playback_metadata(path, mtime_ns, size):
    data = read(path)
    if not isinstance(data, dict):
        data = {}
    return dict(origin_room_id=playback_origin(data), covered_room_ids=playback_coverage(data),
                engine_kind=data.get('engine_kind'), complete=data.get('complete') is True,
                saved_at_ms=mtime_ns//1_000_000)


class ResultCatalog:
    def __init__(self, root, aliases):
        self.root=Path(root).resolve();self.aliases=Path(aliases)
        from runtime_storage import DATA_ROOT
        key=hashlib.sha256(str(self.root).encode()).hexdigest()
        self.file=DATA_ROOT/'cache'/'catalogs'/(key+'.json');self.lock=threading.RLock();self.checked=0
        self.index=read(self.file,read(self.root/'playback-catalog.json',{'schema':'pyrocast.playback-catalog/1','files':{}}))

    def scan(self, force=False):
        with self.lock:
            if not force and time.monotonic()-self.checked<15:return self.index
            previous=self.index.get('files',{});found={}
            for directory,dirs,files in os.walk(self.root,followlinks=False):
                dirs[:]=[d for d in dirs if d not in ('.git','__pycache__','node_modules') and not d.startswith(('github-publish','ui_refactor','server_stage5_test')) and not Path(directory,d).is_symlink()]
                if 'playback.json' not in files:continue
                path=Path(directory,'playback.json').resolve()
                if not path.is_relative_to(self.root):continue
                try: stat=path.stat()
                except OSError:continue
                rel=path.relative_to(self.root).as_posix();stamp=[stat.st_mtime_ns,stat.st_size]
                old=previous.get(rel)
                if old and old.get('stamp')==stamp and 'covered_room_ids' in old:found[rel]=old;continue
                data=read(path)
                record={'stamp':stamp,'valid':False,'engine_kind':None,'origin_room_id':None,'covered_room_ids':[]}
                if isinstance(data,dict) and data.get('schema')=='pyrocast-cad-playback-1' and data.get('building_sha256') and data.get('time_s'):
                    record.update(valid=True,building_sha256=data['building_sha256'],engine_kind=data.get('engine_kind'),
                        kind='lite' if data.get('engine_kind')=='pyrocast_lite' else 'native',
                        label=data.get('label') or Path(rel).parent.as_posix(),complete=bool(data.get('complete')),
                        origin_room_id=playback_origin(data),covered_room_ids=playback_coverage(data))
                # Cache parse failures only until the file changes; partial writes never enter cases.
                found[rel]=record
            self.index={'schema':'pyrocast.playback-catalog/1','files':found}
            atomic_json(self.file,self.index);self.checked=time.monotonic();return self.index

    def cases(self, building_sha, kind, configured=()):
        index=self.scan()['files'];aliases=read(self.aliases,{})
        bypath={}
        if kind=='native':
            for key,row in aliases.items():bypath[(self.root/row['relative_path']).resolve()]={'id':key,'label':row['label']}
        else:
            from runtime_storage import app_path
            for row in configured:bypath[app_path(row['path']).resolve()]=row
        result=[]
        for rel,row in index.items():
            if not row.get('valid') or row['kind']!=kind or row['building_sha256']!=building_sha:continue
            if kind=='lite' and not row['complete']:continue
            path=self.root/rel;old=bypath.get(path,{})
            result.append({'id':old.get('id','case-'+hashlib.sha256(rel.encode()).hexdigest()[:20]),
                'label':old.get('label',row['label']),'path':str(path),'complete':row['complete'],
                'engine_kind':row.get('engine_kind'),'origin_room_id':row.get('origin_room_id'),
                'covered_room_ids':row.get('covered_room_ids',[]),
                'saved_at_ms':row['stamp'][0]//1_000_000})
        order={r['id']:i for i,r in enumerate(configured)}
        return sorted(result,key=lambda r:(order.get(r['id'],len(order)),r['id']))

class CombinedResultCatalog:
    """Read bundled history and external runs without changing legacy case identifiers."""
    def __init__(self, root, aliases):
        from runtime_storage import RESULTS
        self.catalogs=[ResultCatalog(root,aliases),ResultCatalog(RESULTS,aliases)]
    def scan(self, force=False):
        return [c.scan(force=force) for c in self.catalogs]
    def cases(self, building_sha, kind, configured=()):
        found={}
        for c in self.catalogs:
            for row in c.cases(building_sha,kind,configured):found[row['id']]=row
        return list(found.values())
