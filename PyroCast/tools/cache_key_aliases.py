"""Verified, one-time old execution-key migration; never promotes named archives."""
import hashlib
import json
from pathlib import Path
from result_catalog import atomic_json, read

KINDS={'native':('cad_interactive','playback.json'),'r8':('cad_r8_review','comparison.json')}


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CacheAliases:
    def __init__(self,root):
        self.root=Path(root).resolve();self.path=self.root/'cache-key-aliases.json'

    def completed(self,folder,kind,building_sha):
        payload=read(folder/KINDS[kind][1],{})
        return payload.get('complete') is True and payload.get('building_sha256')==building_sha

    def seal(self,folder,kind,key,building_sha):
        folder=Path(folder).resolve()
        if not folder.is_relative_to(self.root) or not self.completed(folder,kind,building_sha):return None
        names=[KINDS[kind][1]]+(['result.json'] if kind=='native' else ['batch-state.json'])
        if not all((folder/n).is_file() for n in names):return None
        record=dict(kind=kind,new_key=key,building_sha256=building_sha,folder=folder.relative_to(self.root).as_posix(),files={n:digest(folder/n) for n in names})
        atomic_json(folder/'cache-completed.json',record);return record

    def lookup(self,kind,new_key,building_sha):
        # A current key is always tried before its migrated legacy alias.
        direct=self.root/KINDS[kind][0]/new_key
        records=[read(direct/'cache-completed.json',{})]
        records+=read(self.path,{}).get('aliases',{}).get(kind+':'+new_key,[])
        for record in records:
            if record.get('kind')!=kind or record.get('new_key')!=new_key or record.get('building_sha256')!=building_sha:continue
            folder=(self.root/record.get('folder','')).resolve()
            if not folder.is_relative_to(self.root/KINDS[kind][0]):continue
            try:
                if not record.get('files') or any(Path(n).name!=n or digest(folder/n)!=h for n,h in record['files'].items()):continue
                if not self.completed(folder,kind,building_sha):continue
            except OSError:continue
            return folder,record
        return None

    def migrate(self,old_key_for,new_key_for,legacy_server_sha):
        if self.path.exists():return read(self.path)
        rows=[];aliases={}
        for kind,(directory,_) in KINDS.items():
            for folder in sorted((self.root/directory).glob('*')):
                if not folder.is_dir() or folder.is_symlink():continue
                row=dict(kind=kind,old_key=folder.name,folder=folder.relative_to(self.root).as_posix())
                request=read(folder/'execution-request.json')
                if request is None and kind=='native':
                    scenario=read(folder/'scenario.json',{});cad=scenario.get('cad',{})
                    request=dict(options=cad.get('options'),building_sha256=cad.get('building_sha256'))
                if len(folder.name)!=24 or any(c not in '0123456789abcdef' for c in folder.name):
                    row.update(status='excluded',reason='not the previous 24-character execution_key namespace')
                elif not request or not isinstance(request.get('options'),dict) or not request.get('building_sha256'):
                    row.update(status='excluded',reason='missing exact normalized request/building provenance')
                else:
                    try:
                        options=request['options'];sha=request['building_sha256']
                        if old_key_for(kind,options,sha)!=folder.name:raise ValueError('legacy key does not match current calculation dependencies and exact input')
                        new_key=new_key_for(kind,options,sha);record=self.seal(folder,kind,new_key,sha)
                        if not record:raise ValueError('missing or incomplete output')
                        record={**record,'old_key':folder.name};aliases.setdefault(kind+':'+new_key,[]).append(record)
                        row.update(status='migrated',new_key=new_key)
                    except (OSError,ValueError,KeyError) as exc:row.update(status='excluded',reason=str(exc))
                rows.append(row)
        value=dict(schema='pyrocast.cache-key-aliases/1',legacy_server_sha256=legacy_server_sha,aliases=aliases,entries=rows,
                   scope='execution_key namespaces only; CLI case IDs are not execution keys')
        atomic_json(self.path,value);return value


def legacy_execution_key(options,building_sha,engine,sim,server_bytes):
    implementation=hashlib.sha256();implementation.update(b'serve_cfbt_building.py');implementation.update(server_bytes)
    for p in sorted((sim/'pyrocast_cfbt').glob('*.py')):implementation.update(p.name.encode());implementation.update(p.read_bytes())
    for p in [*sorted((sim/'data').glob('*.json')),*sorted((sim/'extensions/thermal').glob('*.c')),*list((sim/'build').glob('plate.dll'))]:
        implementation.update(p.name.encode());implementation.update(p.read_bytes())
    payload=dict(options=options,building_sha256=building_sha,engine_sha256=digest(engine),implementation_sha256=implementation.hexdigest())
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()[:24]
