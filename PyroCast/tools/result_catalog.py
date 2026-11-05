"""Incremental playback-folder index. No simulation and no active-case replacement."""
import hashlib
import json
import os
from pathlib import Path
import threading
import time
import uuid


def read(path, default=None):
    try: return json.loads(Path(path).read_text('utf-8'))
    except (OSError, ValueError): return default


def atomic_json(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n','utf-8')
        tmp.replace(path)
    finally: tmp.unlink(missing_ok=True)


class ResultCatalog:
    def __init__(self, root, aliases):
        self.root=Path(root).resolve();self.aliases=Path(aliases)
        self.file=self.root/'playback-catalog.json';self.lock=threading.RLock();self.checked=0
        self.index=read(self.file,{'schema':'pyrocast.playback-catalog/1','files':{}})

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
                if old and old.get('stamp')==stamp and 'engine_kind' in old:found[rel]=old;continue
                data=read(path)
                record={'stamp':stamp,'valid':False,'engine_kind':None}
                if isinstance(data,dict) and data.get('schema')=='pyrocast-cad-playback-1' and data.get('building_sha256') and data.get('time_s'):
                    record.update(valid=True,building_sha256=data['building_sha256'],engine_kind=data.get('engine_kind'),
                        kind='lite' if data.get('engine_kind')=='pyrocast_lite' else 'native',
                        label=data.get('label') or Path(rel).parent.as_posix(),complete=bool(data.get('complete')))
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
            for row in configured:bypath[Path(row['path']).resolve()]=row
        result=[]
        for rel,row in index.items():
            if not row.get('valid') or row['kind']!=kind or row['building_sha256']!=building_sha:continue
            if kind=='lite' and not row['complete']:continue
            path=self.root/rel;old=bypath.get(path,{})
            result.append({'id':old.get('id','case-'+hashlib.sha256(rel.encode()).hexdigest()[:20]),
                'label':old.get('label',row['label']),'path':str(path),'complete':row['complete'],
                'engine_kind':row.get('engine_kind')})
        order={r['id']:i for i,r in enumerate(configured)}
        return sorted(result,key=lambda r:(order.get(r['id'],len(order)),r['id']))
