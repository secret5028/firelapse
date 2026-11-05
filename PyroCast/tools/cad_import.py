"""Local CAD import; retained scan importer is a separate, unchanged service."""
import base64, hashlib, json, math, os, re, subprocess, sys, threading, uuid, shutil, time
from pathlib import Path, PurePosixPath
import model_library
from result_catalog import atomic_json

ROOT=model_library.ROOT
STAGING=ROOT/'data/cad-imports'
MAX_BODY=90*1024*1024
LOCK=threading.Lock()

def read(p): return json.loads(Path(p).read_text('utf-8-sig'))
def folder(ident):
    if not isinstance(ident,str) or not re.fullmatch(r'[a-f0-9]{32}',ident): raise ValueError('업로드 ID 오류')
    p=STAGING/ident
    if not (p/'manifest.json').is_file(): raise ValueError('CAD 업로드를 찾을 수 없습니다')
    return p

def status(ident):
    value=read(folder(ident)/'manifest.json')
    if value['state']=='running' and not LOCK.locked():
        value.update(state='interrupted',message='CAD 변환 중단 · 도면을 다시 추가하세요')
    return value

def runtime():
    path=ROOT/'config/cad-import.local.json'
    if not path.is_file(): raise ValueError('CAD 변환기 미설정 · config/cad-import.local.json')
    cfg=read(path)
    if not (Path(cfg['reader_dir'])/'run_building.py').is_file() or not Path(cfg['dwg2dxf']).is_file():
        raise ValueError('CAD 변환기 경로를 확인하세요')
    return cfg

def upload(body):
    files=body.get('files')
    if not isinstance(files,list) or not 1<=len(files)<=40: raise ValueError('CAD 파일 1~40개를 추가하세요')
    decoded=[]; names=set(); total=0
    for f in files:
        if not isinstance(f,dict): raise ValueError('파일 형식 오류')
        name=f.get('name',''); p=PurePosixPath(name.replace('\\','/'))
        if not name or len(name)>300 or p.is_absolute() or '..' in p.parts or ':' in name: raise ValueError('파일 경로 오류')
        if p.suffix.lower() not in ('.dwg','.dxf'): raise ValueError('DWG·DXF CAD 파일만 지원합니다')
        if p.name.casefold() in names: raise ValueError('동일한 파일명은 하나만 추가하세요: '+p.name)
        names.add(p.name.casefold())
        try: data=base64.b64decode(f['data'],validate=True)
        except (ValueError,KeyError,TypeError): raise ValueError('파일 데이터 오류') from None
        total+=len(data)
        if not data or total>64*1024*1024: raise ValueError('전체 CAD 파일 64MB 한도')
        if p.suffix.lower()=='.dwg' and not re.match(b'AC10[0-9]{2}',data[:6]): raise ValueError('DWG 파일 헤더 오류: '+p.name)
        decoded.append((p.name,data))
    runtime()
    ident=uuid.uuid4().hex; dest=STAGING/ident; (dest/'source').mkdir(parents=True)
    rows=[]
    for name,data in decoded:
        (dest/'source'/name).write_bytes(data)
        rows.append(dict(name=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    value=dict(id=ident,state='uploaded',files=rows,message='CAD 파일 준비됨',errors=[])
    atomic_json(dest/'manifest.json',value);return value

def expected_floors(body):
    from model_import import floor_number,floor_label
    lo,hi=floor_number(body.get('lowest')),floor_number(body.get('highest'))
    if lo>hi: raise ValueError('최저층·최고층 순서 오류')
    return [floor_label(n) for n in range(lo,hi+1) if n]

def geometry_checks(building,expected):
    from prepare_building_graph import geometry
    errors=[]; rows=[]; floors=building.get('floors',[])
    actual=[f.get('name') for f in floors]
    missing=set(expected)-set(actual)
    if missing: errors.append('누락 층: '+', '.join(sorted(missing)))
    if len(actual)!=len(set(actual)): errors.append('층 중복')
    for f in floors:
        slab=geometry(f.get('slab',[])); rooms=f.get('rooms',[])
        area=sum(geometry(r.get('polys',[])).area for r in rooms)
        coverage=area/slab.area if slab.area else 0
        height=f.get('h',0)
        if not rooms or slab.is_empty or not math.isfinite(height) or height<=0:
            errors.append(f"{f['name']}: 실·외곽·층고 결측")
        # A floor with almost all enclosed space missing is not a usable model.
        if coverage<.25: errors.append(f"{f['name']}: 실 형상 심각한 결측 (바닥 대비 {coverage:.0%})")
        rows.append(dict(floor=f['name'],rooms=len(rooms),openings=len(f.get('openings',[])),coverage=round(coverage,3),height_m=height))
    return errors,rows

def generate(ident,body):
    dest=folder(ident); value=read(dest/'manifest.json')
    if value['state']=='complete': return value
    if value['state']!='uploaded': raise ValueError('이미 처리한 도면입니다. 수정 도면을 새로 추가하세요')
    name=body.get('name','').strip()
    if not name or len(name)>100: raise ValueError('건물 이름을 입력하세요')
    expected=expected_floors(body);runtime()
    if not LOCK.acquire(False): raise RuntimeError('다른 CAD 도면 처리 중입니다')
    value.update(state='running',message='CAD 변환·층별 형상 검사 중…',name=name,expected=expected)
    atomic_json(dest/'manifest.json',value)
    threading.Thread(target=worker,args=(ident,),daemon=True).start()
    return value

def review(ident):
    dest=folder(ident);value=read(dest/'manifest.json')
    if value['state']!='complete':raise ValueError('완료된 CAD 모델만 다시 검토할 수 있습니다')
    if not LOCK.acquire(False):raise RuntimeError('다른 CAD 도면 처리 중입니다')
    value.update(state='running',message='공리 자동보정·API AI 검토 중…');atomic_json(dest/'manifest.json',value)
    threading.Thread(target=worker,args=(ident,True),daemon=True).start();return value

def worker(ident,review_only=False):
    dest=folder(ident); value=read(dest/'manifest.json')
    try:
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1'}
        with (dest/'conversion.log').open('w',encoding='utf8') as log:
            process=subprocess.run([sys.executable,'-B','-X','utf8',str(Path(__file__)), '--arcs' if review_only else '--convert',str(dest)],
                cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1200,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if process.returncode: raise ValueError('CAD 형상 추출 실패 · conversion.log 확인')
        source=dest/'extraction/building.json'; building=read(source)
        errors,rows=geometry_checks(building,value['expected'])
        value.update(floors=rows,errors=errors)
        if errors:
            value.update(state='blocked',message='생성 불가 · 층 누락 또는 심각한 형상 결측')
        else:
            from cad_completion import complete
            from apply_hotel_autocorrect import check
            value['message']='층 정렬·미연결 공간 공리 검토 중…';atomic_json(dest/'manifest.json',value)
            work=dest/'completion'/str(time.time_ns());work.mkdir(parents=True)
            for image in (dest/'extraction').glob('source-*.png'):shutil.copyfile(image,work/image.name)
            decisions=read(dest/'codex-review.json') if (dest/'codex-review.json').exists() else None
            building,report=complete(source,work,arc_evidence=read(dest/'arcs.json'),recorded_review=decisions)
            for floor in building['floors']:
                if 'unconfirmed' in str(floor.get('align','')):
                    building['model_review']['items'].append(dict(floor=floor['name'],id='ALIGN',kind='alignment_unconfirmed',detail='층간 위치 정렬 미확정 · 원본 좌표 유지'))
            target=dest/'building.json'
            if target.exists():shutil.copyfile(target,work/'previous-generated-building.json')
            atomic_json(target,building)
            loaders=check(target)
            value['floors']=[dict(floor=f['name'],rooms=len(f['rooms']),openings=len(f['openings']),height_m=f['h']) for f in building['floors']]
            for row in loaders:
                if not row['ok']: building['model_review']['items'].append(dict(floor=row['floor'],id='LOADER',kind='loader_failed',detail=row['error']))
            building['model_provenance']=dict(source_kind='cad',simulation_allowed=any(r['ok'] for r in loaders),import_id=ident,files=value['files'],ai_review=building['cad_completion']['ai_status'])
            building['notes']=['CAD 자동 추출 · 미확인 연결은 검토 목록 참조', '층고 출처: '+str(building.get('levels_src','미확인'))]
            atomic_json(target,building);atomic_json(dest/'graph-report.json',report);atomic_json(work/'report.json',report)
            mid='cad-'+ident
            from model_import import PUBLISH_LOCK
            with PUBLISH_LOCK:
                registry=read(model_library.REGISTRY)
                entry=dict(id=mid,label=value['name'],path=target.relative_to(ROOT).as_posix(),source_kind='cad',
                    sha256=hashlib.sha256(target.read_bytes()).hexdigest(),floor_count=len(building['floors']),room_count=sum(len(f['rooms']) for f in building['floors']),
                    simulation_enabled=False,execution_note='CAD 모델 생성 · 연결·층고 검토 후 계산 연결',
                    source_evidence='DWG/DXF 원본 보존 · 공리 보정 · AI '+building['cad_completion']['ai_status'],operation_url=None,review_url=None)
                from model_operation import register_cad, ensure_server
                register_cad(entry,loaders,registry)
                existing=next((e for e in registry['models'] if e['id']==mid),None)
                if existing:
                    previous=model_library.model_path(existing)
                    if previous!=target and previous.exists():
                        shutil.copyfile(previous,work/'previous-building.json')
                        atomic_json(previous,building)
                        entry['path']=existing['path']
                    existing.update(entry)
                else:registry['models'].append(entry)
                atomic_json(model_library.REGISTRY,registry)
            ensure_server(entry)
            value.update(state='complete',model_id=mid,url=entry.get('operation_url') or '/models/?id='+mid,operation_url=entry.get('operation_url'),message='3D 생성 완료 · 층별 계산 가능' if entry['simulation_enabled'] else '3D 생성 완료 · 계산 층 검토 필요',loaders=loaders,
                unresolved=sum(len(f['simulation_graph']['isolated_rooms']) for f in building['floors']),review_count=len(building['model_review']['items']),ai_status=building['cad_completion']['ai_status'],ai_calls=building['cad_completion']['ai_calls'])
    except Exception as e: value.update(state='failed',message=str(e),errors=[str(e)])
    finally:
        atomic_json(dest/'manifest.json',value);LOCK.release()

if __name__=='__main__':
    import runpy
    mode=sys.argv[1];cfg=runtime(); dest=Path(sys.argv[2]).resolve()
    if not dest.is_relative_to(STAGING.resolve()): raise ValueError('Invalid staging path')
    sys.path[:0]=[str(ROOT/'simulation/deps'),str(ROOT/'simulation/plot_deps'),*cfg.get('dependency_paths',[])]
    if mode=='--convert':
        sys.argv=['run_building.py',str(dest/'source'),'--out',str(dest/'extraction'),'--dwg2dxf',cfg['dwg2dxf']]
        runpy.run_path(str(Path(cfg['reader_dir'])/'run_building.py'),run_name='__main__')
    from extract_cad_arcs import extract
    arcs=extract(read(dest/'extraction/building.json'),dest/'source',Path(cfg['reader_dir']),Path(cfg['dwg2dxf']),dest/'extraction/dxf',render_dir=dest/'extraction')
    atomic_json(dest/'arcs.json',arcs)
