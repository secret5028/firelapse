"""Build a results-only portable bundle. No solver runs; source results stay unchanged."""
import argparse, hashlib, json, os, shutil, sys, time, zipfile
from pathlib import Path

EXCLUDE={'__pycache__','.git','node_modules','.venv'}
PRIMARY={'model-library','lite_mc_jobs','fixed-calculations','overnight-20261104',
         'hotel-native-compare-20261105','mc-numerical-fix-20261105',
         'lite_v8_mc_R2_10_20261026','lite_v8_stage4_R2_20261026'}

def files(root):
    if not root.exists():return
    for base,dirs,names in os.walk(root):
        dirs[:]=sorted(d for d in dirs if d not in EXCLUDE and not Path(base,d).is_symlink())
        for name in sorted(names):
            p=Path(base,name)
            if not p.is_symlink() and p.suffix not in ('.pyc','.pyo'):yield p

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--python-runtime',type=Path,required=True);p.add_argument('--node-runtime',type=Path,required=True)
    p.add_argument('--phase',choices=['stage','zip'],default='stage');a=p.parse_args()
    root=a.source.resolve();out=a.output.resolve();bundle=out/'FireLapse';app=bundle/'app'
    out.mkdir(parents=True,exist_ok=True)
    if a.phase=='zip':
        rows=json.loads((out/'inventory.json').read_text('utf8'))
        zip_parts(out,bundle,rows['archive_sources']);return
    if bundle.exists():raise SystemExit('Output exists; choose a fresh destination, no overwrite')
    records=[]
    def copy(src,dst):
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
        records.append({'path':dst.relative_to(bundle).as_posix(),'bytes':dst.stat().st_size,'sha256':sha(dst)})
    def tree(src,dst,predicate=lambda p:True):
        for f in files(src):
            if predicate(f):copy(f,dst/f.relative_to(src))
    tree(root/'docs/screenshots',bundle/'docs/screenshots')
    tree(root/'docs/screenshots',app/'docs/screenshots')
    tree(root/'distribution/licenses',bundle/'licenses')
    for folder in ('app','tools'):
        tree(root/folder,app/folder,lambda f:f.suffix in ('.py','.mjs','.js','.css','.html','.json','.md','.txt') and 'tests' not in f.parts)
    tree(root/'config',app/'config',lambda f:f.name not in ('ai.json','cad-import.local.json','portable-location.json'))
    for folder in ('pyrocast_lite','pyrocast_cfbt','viewer','config','examples','extensions','vendor','data'):
        tree(root/'simulation'/folder,app/'simulation'/folder)
    for f in (root/'simulation').glob('*.py'):copy(f,app/'simulation'/f.name)
    for f in (root/'simulation').glob('*.txt'):copy(f,app/'simulation'/f.name)
    copy(root/'simulation/requirements.txt',app/'simulation/requirements.txt')
    registry_source=json.loads((root/'config/model-library.json').read_text('utf8'))
    tree(root/'data/wando-coldstore',app/'data/wando-coldstore')
    for entry in registry_source['models']:
        if entry['id']!='ganghwa':copy(root/entry['path'],app/entry['path'])
    cad=root/'cad-project'
    if not cad.exists():cad=root/'simulation/results/github-publish-20261026/PyroCast/cad-project'
    for name in ('building.json','model.html') :copy(cad/name,app/'cad-project'/name)
    tree(cad/'work/cad-web/local-resources/cad-assets',app/'cad-project/work/cad-web/local-resources/cad-assets')
    tree(root/'simulation/build/baseline',app/'simulation/build/baseline',lambda f:f.suffix in ('.exe','.dll','.json'))
    tree(root/'simulation/build/mixture_r2',app/'simulation/build/mixture_r2',lambda f:f.suffix in ('.exe','.dll','.json'))
    # Runtime has only Python standard library and named numerical/image dependencies.
    for f in a.python_runtime.iterdir():
        if f.is_file() and (f.suffix in ('.exe','.dll') or f.name=='LICENSE.txt'):copy(f,bundle/'runtime/python'/f.name)
    tree(a.python_runtime/'DLLs',bundle/'runtime/python/DLLs')
    tree(a.python_runtime/'Lib',bundle/'runtime/python/Lib',lambda f:'site-packages' not in f.parts and 'test' not in f.parts and 'tests' not in f.parts and '__phello__' not in f.parts)
    keep={'deps':('scipy','shapely'),'plot_deps':('numpy','PIL','pillow')}
    for folder in ('deps','plot_deps'):
        for dep in (root/'simulation'/folder).iterdir():
            if dep.is_dir() and dep.name.startswith(keep[folder]):
                tree(dep,app/'simulation'/folder/dep.name,lambda f:'tests' not in f.parts and 'test' not in f.parts)
    # Node is used by the existing read-only route/briefing adapter.
    for name in ('node.exe','LICENSE'):copy(a.node_runtime/name,bundle/'runtime/node'/name)
    site=bundle/'runtime/python/Lib/site-packages';site.mkdir(parents=True,exist_ok=True)
    (site/'firelapse.pth').write_text('../../../../app/simulation/deps\n../../../../app/simulation/plot_deps\n','utf8')
    # Original result bytes are copied unchanged; temporary UI fixtures and nested Git checkouts are excluded.
    sys.path.insert(0,str(root/'tools'))
    from runtime_storage import RESULTS as external_results
    result_sources=[root/'simulation/results',external_results]
    archive=[];playbacks=0;excluded_bytes=0
    portable_indices=0
    omitted_lite=[];omitted_lite_bytes=0
    from distribution_results import result_policy
    for results in result_sources:
        if not results.exists():continue
        keep_result,native_folders,lite_cases=result_policy(results)
        omitted_lite.extend(lite_cases)
        # Some approved final cases live in historic ui_* experiment folders.
        # Keep only catalog-validated final-result directories, never UI captures/fixtures.
        known_hashes={e.get('sha256') for e in registry_source['models']}
        catalog=results/'playback-catalog.json'
        indexed=json.loads(catalog.read_text('utf8')).get('files',{}) if catalog.exists() else {}
        ui_finals={(results/rel).resolve().parent for rel,row in indexed.items()
                   if row.get('valid') and row.get('building_sha256') in known_hashes
                   and Path(rel).parts[0].startswith('ui_') and (results/rel).resolve().is_relative_to(results.resolve())}
        for top in sorted(results.iterdir()):
            if not top.is_dir() or top.name.startswith('github-publish') or top.name in ('unit_tmp','verification'):continue
            if top.name.startswith('ui_') and not any(d.is_relative_to(top.resolve()) for d in ui_finals):continue
            for f in files(top):
                if top.name.startswith('ui_') and f.parent.resolve() not in ui_finals:continue
                if not keep_result(f):
                    omitted_lite_bytes+=f.stat().st_size
                    continue
                rel=Path('simulation/results')/f.relative_to(results)
                if f.name.endswith(('.lock','.pid')):continue
                # Final playback and small settings/summaries only. Raw solver matrices,
                # CSV/logs/plots, retries and intermediate attempts are not distributed.
                include=any(f.is_relative_to(folder) for folder in native_folders) or f.name=='playback.json' or (f.suffix=='.json' and f.stat().st_size<2*1024*1024
                    and f.name not in ('result.json','execution-evidence.json','started.json','build.json','worker.json','control.json')
                    and not any(s in f.name for s in ('before','backup','trace','debug')))
                if include:copy(f,app/rel);playbacks+=int(f.name=='playback.json')
                else:excluded_bytes+=f.stat().st_size
        # A sealed, small result index keeps MC ordering usable without raw matrices.
        sys.path.insert(0,str(root/'tools'))
        from export_ui_attention import summarize,KINDS
        for source in results.rglob('index-summary.json'):
            rel=Path('simulation/results')/source.relative_to(results)
            if not (app/rel).is_file():continue
            raw_path=source.with_name('result.json');pb=source.with_name('playback.json')
            if not raw_path.exists() or not pb.exists() or not (app/'simulation/results'/pb.relative_to(results)).exists():continue
            cached=json.loads(source.read_text('utf8'));st=raw_path.stat()
            if cached.get('source_stamp')!=[st.st_mtime_ns,st.st_size] or cached.get('kinds')!=list(KINDS):
                raw=raw_path.read_bytes();v=json.loads(raw)
                cached={'schema':'pyrocast.result-index/1','threshold':70,'kinds':list(KINDS),**summarize(v),
                        'complete':bool(v['ok']),'source_stamp':[st.st_mtime_ns,st.st_size],'source_sha256':hashlib.sha256(raw).hexdigest()}
            sealed={'schema':'firelapse.portable-result-index/1','playback_sha256':sha(pb),'index':cached,
                    'index_sha256':hashlib.sha256(json.dumps(cached,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
            dest=app/rel.parent/'portable-result-index.json';dest.write_text(json.dumps(sealed,ensure_ascii=False,indent=2),'utf8');portable_indices+=1
    # Operational model registry gets portable paths, without changing model JSON hashes.
    registry=app/'config/model-library.json';data=json.loads(registry.read_text('utf8'))
    for entry in data['models']:
        if entry['id']=='ganghwa':entry['path']='cad-project/building.json'
        entry.pop('source_path',None)
    registry.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf8')
    # Packaging never copies API connection secrets. Custom CAD converter remains optional.
    meta={'name':'FireLapse','version':'2026.11.06','source_root':str(root),'source_data_root':str(external_results.parent),'platform':'Windows x64',
          'models':[{k:e.get(k) for k in ('id','label','source_kind','floor_count','room_count','simulation_enabled')} for e in data['models']],
          'playback_count':playbacks,'new_simulations':0,'portable_indices':portable_indices,'excluded_bytes':excluded_bytes,
          'excluded_lite_results':omitted_lite,'excluded_lite_bytes':omitted_lite_bytes,
          'excluded':['Raw solver matrices/CSV/logs/intermediate attempts','API keys and connection secrets','nested Git checkout','UI test captures and temporary unit fixtures'],
          'cad_import':'External DWG/DXF extraction toolchain must be configured separately; existing 7 models are bundled'}
    (bundle/'distribution.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n','utf8')
    cmd='@echo off\r\nchcp 65001 >nul\r\ncd /d "%~dp0"\r\n"%~dp0runtime\\python\\python.exe" -B -X utf8 "%~dp0app\\tools\\launch_firelapse.py" %*\r\nif errorlevel 1 pause\r\n'
    copy(root/'distribution/FireLapse.cmd',bundle/'FireLapse.cmd')
    (bundle/'Check-FireLapse.cmd').write_bytes(cmd.replace('%*','--check').replace('if errorlevel 1 pause','pause').encode('utf8'))
    for name in ('README.md','THIRD_PARTY_NOTICES.md'):
        source=root/name if name=='README.md' and (root/name).exists() else root/'distribution'/name
        copy(source,bundle/name)
    records=[{'path':f.relative_to(bundle).as_posix(),'bytes':f.stat().st_size,'sha256':sha(f)} for f in files(bundle)]
    (bundle/'files.sha256.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n','utf8')
    (out/'inventory.json').write_text(json.dumps({'app_files':len(records),'app_bytes':sum(r['bytes'] for r in records),'playbacks':playbacks,
        'archive_bytes':sum(r['bytes'] for r in archive),'archive_sources':archive},ensure_ascii=False,indent=2),'utf8')
    print(json.dumps({'app_files':len(records),'app_bytes':sum(r['bytes'] for r in records),'playbacks':playbacks,'archive_bytes':sum(r['bytes'] for r in archive)},ensure_ascii=False),flush=True)

def zip_parts(out,bundle,archive):
    assets=[]
    dest=out/'FireLapse-Windows-x64-2026.11.06.zip'
    with zipfile.ZipFile(dest,'x',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for i,f in enumerate(files(bundle)):
            z.write(f,'FireLapse/'+f.relative_to(bundle).as_posix())
            if i%500==0:print('app files',i,flush=True)
    assets.append(dest);print('APP ZIP',dest.stat().st_size,flush=True)
    # Separate ordinary ZIPs (not split binary streams), each below GitHub's asset limit.
    z=None;part=0;archive_manifest=[]
    try:
        for row in archive:
            if z is None or z.fp.tell()>1400*1024*1024:
                if z:z.close();print('ARCHIVE',dest.name,dest.stat().st_size,flush=True)
                part+=1;dest=out/f'FireLapse-Calculation-Archive-{part:02d}.zip'
                z=zipfile.ZipFile(dest,'x',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True);assets.append(dest)
            f=Path(row['source']);z.write(f,row['path']);archive_manifest.append({'path':row['path'],'asset':dest.name,'bytes':f.stat().st_size,'sha256':sha(f)})
    finally:
        if z:z.close()
    if archive_manifest:
        manifest=out/'calculation-archive-manifest.json';manifest.write_text(json.dumps(archive_manifest,ensure_ascii=False,indent=2),'utf8');assets.append(manifest)
    info=[{'name':f.name,'bytes':f.stat().st_size,'sha256':sha(f)} for f in assets]
    (out/'release-assets.json').write_text(json.dumps(info,indent=2),'utf8')
    (out/'SHA256SUMS.txt').write_text(''.join(r['sha256']+'  '+r['name']+'\n' for r in info),'utf8')
    print(json.dumps(info,indent=2),flush=True)

if __name__=='__main__':main()
