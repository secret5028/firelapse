"""Verified cache lookup; reads existing aliases without generating migrations."""
import hashlib
import json
from pathlib import Path
from result_catalog import atomic_json, read

KINDS={'native':('cad_interactive','playback.json'),'r8':('cad_r8_review','comparison.json')}


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ExecutionCache:
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
        from runtime_storage import locate
        direct=locate(self.root/KINDS[kind][0]/new_key)
        records=[read(direct/'cache-completed.json',{})]
        records+=read(locate(self.path),{}).get('aliases',{}).get(kind+':'+new_key,[])
        for record in records:
            if record.get('kind')!=kind or record.get('new_key')!=new_key or record.get('building_sha256')!=building_sha:continue
            folder=locate(self.root/record.get('folder','')).resolve()
            from runtime_storage import RESULTS, is_result_path
            if self.root==RESULTS.resolve():
                if not is_result_path(folder,KINDS[kind][0]):continue
            elif not folder.is_relative_to(self.root/KINDS[kind][0]):continue
            try:
                if not record.get('files') or any(Path(n).name!=n or digest(folder/n)!=h for n,h in record['files'].items()):continue
                if not self.completed(folder,kind,building_sha):continue
            except OSError:continue
            return folder,record
        return None
