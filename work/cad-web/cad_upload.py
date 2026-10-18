"""Bridge the existing local upload jobs to the approved CAD extraction/model code."""
from pathlib import Path
import json,sys,re,os,time,subprocess,hashlib,html,shutil,traceback,contextlib,mimetypes
from urllib.parse import unquote

def atomic(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False),'utf8');os.replace(temp,path)

def run(folder,base,report):
    folder=Path(folder);state=folder/'cad-progress.json'
    state.unlink(missing_ok=True)
    cmd=[sys.executable]+([] if getattr(sys,'frozen',False) else [str(Path(__file__).with_name('local_app.py'))])+['--cad-worker',str(folder),str(base)]
    with (folder/'cad-process.log').open('w',encoding='utf8') as log:
        child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        started=time.monotonic()
        while child.poll() is None:
            if time.monotonic()-started>3600:
                child.kill();child.wait();raise ValueError('CAD 처리 시간이 60분을 넘었습니다. 층별 파일로 나누어 다시 처리하세요.')
            if state.exists():
                try:
                    s=json.loads(state.read_text('utf8'));report(s['progress'],s['message'])
                except (OSError,ValueError,KeyError):pass
            time.sleep(.5)
    s=json.loads(state.read_text('utf8')) if state.exists() else {}
    if child.returncode:raise ValueError(s.get('error','CAD 처리 실패. 작업 로그를 확인하세요.'))
    return json.loads((folder/'cad-output/summary.json').read_text('utf8'))

def floor_names(text):
    t=re.sub(r'\s+','',text).upper()
    if re.search(r'지붕|배치도|입면도|단면도',t):return set()
    found=set()
    for m in re.finditer(r'(?:지하|B)(\d+)(?:층|F)?',t):found.add('B'+m[1])
    t=re.sub(r'(?:지하|B)\d+(?:층|F)?','',t)
    if '옥탑' in t or re.search(r'(^|[^A-Z])PH([^A-Z]|$)',t):found.add('PH')
    for m in re.finditer(r'(\d+)(?:층|F)(?![A-Z])',t):found.add(m[1]+'F')
    return found

def inspect_dxf(path,label,override=None):
    import ezdxf
    from cad_stage1_report import texts
    d=ezdxf.readfile(path);strings=[e.dxf.text if e.dxftype()=='TEXT' else e.plain_text() for e in texts(d.modelspace())]
    titles=[s for s in strings if '평면도' in re.sub(r'\s+','',s) and not re.search(r'계단실|상세|확대|부분|단위세대',re.sub(r'\s+','',s))]
    names=set().union(*(floor_names(s) for s in titles)) if titles else set()
    if override and len(names)<=1:names={override}
    elif not names:names=floor_names(label)
    score=len(d.modelspace().query('LINE LWPOLYLINE ARC'))
    # Architectural sheets take precedence over fire/equipment references.
    combined=' '.join(titles)+' '+label
    reference=bool(re.search(r'소방|스프링클러|감지|유도등|전기|배관|설비|천장|반사',combined))
    return dict(floors=sorted(names),texts=strings,score=score,reference=reference)

def worker(folder,base):
    folder=Path(folder);base=Path(base);engine=base/'cad_engine'
    if not engine.exists():engine=Path(__file__).with_name('cad_engine')
    sys.path.insert(0,str(engine))
    from cad_pipeline import main as extract
    from cad_review_ui import enhance_review
    from cad_stage1_report import metadata
    from run_building import sl_level,key
    import cad_build3d
    from cad_model_transport import prepare_model
    status=folder/'cad-progress.json';out=folder/'cad-output';out.mkdir(exist_ok=True)
    def progress(p,m):atomic(status,dict(progress=p,message=m))
    files=json.loads((folder/'files.json').read_text('utf8'));records=[];groups={};warnings=[]
    try:
        inputs=folder/'cad-converted';inputs.mkdir(exist_ok=True)
        for i,f in enumerate(files):
            src=folder/f['stored']
            if src.suffix not in ('.dwg','.dxf'):continue
            progress(28+10*i/len(files),'CAD 층·도면 정보 확인 · '+f['name'])
            dxf=src
            if src.suffix=='.dwg':
                dxf=inputs/(src.stem+'.dxf');converter=base/'cad-tools/dwg2dxf.exe'
                r=subprocess.run([str(converter),'-y','-o',str(dxf),str(src)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=600,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                (inputs/(src.stem+'.log')).write_bytes(r.stdout)
                if r.returncode or not dxf.exists():raise ValueError(f['name']+': DWG 변환 실패. DXF로 저장해 다시 올려주세요.')
            info=inspect_dxf(dxf,f['name'],f.get('floor'))
            record=dict(path=str(dxf),name=f['name'],sha256=hashlib.sha256(dxf.read_bytes()).hexdigest(),floors=info['floors'],role='related_drawing',score=info['score'],reference=info['reference'])
            records.append(record)
            if len(info['floors'])==1:
                n=info['floors'][0];record['floor']=n;groups.setdefault(n,[]).append(record)
            elif len(info['floors'])>1:raise ValueError(f['name']+': 한 파일에서 여러 층 평면이 발견됐습니다. CAD에서 층별 파일로 분리해 올려주세요.')
            else:warnings.append(f['name']+': 층을 판독하지 못해 참조 도면으로 보관')
        if not groups:raise ValueError('층 평면도를 찾지 못했습니다. 업로드 목록에서 각 CAD의 층을 지정해 다시 처리하세요.')
        order=sorted(groups,key=key);primary={}
        for n,rows in groups.items():
            candidates=[r for r in rows if not r['reference']]
            if not candidates:
                warnings.append(n+': 건축 평면이 없어 참조 도면만 보관');continue
            primary[n]=max(candidates,key=lambda r:r['score']);primary[n]['role']='architectural_plan'
            if len(candidates)>1:warnings.append(n+': 건축 후보 중 선 객체가 가장 많은 도면을 기준으로 선택 — '+primary[n]['name'])
        order=[n for n in order if n in primary]
        if not order:raise ValueError('건축 평면 CAD가 필요합니다. 소방·설비 도면만으로 모델을 만들지 않았습니다.')
        manifest=dict(drawings=records,coverage_note='같은 층 도면을 묶어 원본 목록을 보존. 보조 도면의 자동 좌표 융합은 수행하지 않음.')
        atomic(out/'drawings.json',manifest)
        profiles={}
        for p in (engine/'profiles').glob('*.json'):
            profiles[json.loads(p.read_text('utf8'))['source_sha256']]=p
        plans={}
        for i,n in enumerate(order):
            r=primary[n];dest=out/n;progress(40+42*i/len(order),f'1단계 · {n} 벽·문·창·공간 추출 ({i+1}/{len(order)})')
            args=[r['path'],str(dest),'--floor',n,'--drawing-manifest',str(out/'drawings.json'),'--map',str(engine/'layer_map.json')]
            if r['sha256'] in profiles:args+=['--review-profile',str(profiles[r['sha256']])]
            code=extract(args)
            if code:raise ValueError(n+': 추출 형상 검사 실패. 해당 층 결과와 로그를 확인하세요.')
            p=json.loads((dest/'plan.json').read_text('utf8'))
            if not p.get('rooms'):raise ValueError(n+': 공간을 추출하지 못했습니다. 건축 평면 및 CAD 단위를 확인하세요.')
            plans[n]=p;enhance_review(dest);atomic(dest/'floor_metadata.json',metadata(r['path'],p))
        progress(85,'계단·승강기 기준 층 정렬·연결')
        levels=[sl_level(primary[n]['path']) for n in order]+[None]
        height_sources=['CAD_SL_GL' if x is not None else 'default' for x in levels]
        # Reuse the existing level-table reader for uploaded elevations/sections.
        for r in records:
            table,top=cad_build3d.levels_from_elev(r['path'])
            for i,n in enumerate(order):
                v=top if n=='PH' else table.get(key(n))
                if levels[i] is None and v is not None:levels[i]=v;height_sources[i]=r['name']
            if levels[-1] is None and levels[-2] is not None:
                higher=[v for v in list(table.get('_extra',[]))+([top] if top is not None else []) if v>levels[-2]+1]
                if higher:levels[-1]=min(higher);height_sources[-1]=r['name']
        reviewed_path=engine/'reviewed_levels.json'
        reviewed=json.loads(reviewed_path.read_text('utf8')) if reviewed_path.exists() else {}
        for i,n in enumerate(order):
            known=reviewed.get(primary[n]['sha256'])
            if known and known['floor']==n:
                levels[i]=known['level'];height_sources[i]='previous_reviewed_CAD_source_hash'
                if i==len(order)-1:levels[-1]=known['top'];height_sources[-1]='previous_reviewed_CAD_source_hash'
        atomic(out/'height-sources.json',dict(levels=levels,sources=height_sources))
        argv=[str(out/'assembled')]+[str(out/n/'plan.json') for n in order]+['--names',','.join(order)]
        if any(v is not None for v in levels):argv+=['--levels='+','.join('nan' if v is None else str(v) for v in levels)]
        oldargs=sys.argv
        try:sys.argv=['cad_build3d.py']+argv;cad_build3d.main()
        finally:sys.argv=oldargs
        b=json.loads((out/'assembled.json').read_text('utf8'));progress(93,'2단계 · 3D 모델 생성')
        model,audit=prepare_model(b,plans);atomic(out/'building.json',model);atomic(out/'position-audit.json',audit)
        for floor in model['floors']:
            if 'unconfirmed' in floor['align'] or floor['align']=='none':warnings.append(floor['name']+': 계단·승강기 기준 층 정렬이 미확정입니다.')
        (out/'model.html').write_text((engine/'integrated_viewer.html').read_text('utf8'),'utf8')
        rows=''.join(f'<article><h2>{html.escape(n)}</h2><p>공간 {len(plans[n]["rooms"])} · 개구부 {len(plans[n]["openings"])}</p><a href="{n}/index.html">평면도 보기</a> · <a href="{n}/layers.html">원본 레이어</a><p>{html.escape(primary[n]["name"])}</p></article>' for n in order)
        notes=''.join('<li>'+html.escape(x)+'</li>' for x in warnings)
        (out/'plans.html').write_text('<!doctype html><meta charset="utf-8"><style>body{font:16px/1.6 system-ui;margin:25px;background:#edf2f6;color:#21374c}article{background:white;padding:18px;margin:15px 0;border-radius:10px}a{color:#086698}</style><h1>1단계 · 평면도 추출</h1><a href="model.html">3D 모델 보기</a> · <a href="drawings.json">층별 도면 목록</a>'+rows+'<ul>'+notes+'</ul>','utf8')
        summary=dict(version='cad-upload-v1',floors=order,rooms=sum(len(p['rooms']) for p in plans.values()),openings=sum(len(p['openings']) for p in plans.values()),vertical_links=len(model['vertical_connections']),warnings=warnings,levels_source=model.get('levels_src'),height_sources=height_sources,aligned=[dict(floor=f['name'],method=f['align']) for f in model['floors']])
        atomic(out/'summary.json',summary)
        (out/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><style>body{margin:0;font:15px system-ui;background:#edf2f6}nav{padding:12px;display:flex;gap:12px;align-items:center}button{padding:9px 16px;cursor:pointer}iframe{width:100%;height:calc(100vh - 66px);border:0}</style><nav><button data-page="plans.html">1. 평면도 추출</button><button data-page="model.html">2. 3D 모델</button><button disabled>3. 시뮬레이션</button><a href="building.json" download>모델 데이터 저장</a><a href="../../result/'+folder.name+'?legacy=1">기존 도면 검토</a></nav><iframe id="view" title="CAD 작업 결과" src="plans.html"></iframe><script>document.querySelectorAll("[data-page]").forEach(b=>b.onclick=()=>document.getElementById("view").src=b.dataset.page)</script></html>','utf8')
        progress(99,'평면도·3D 모델 저장 완료');return 0
    except Exception as e:
        atomic(status,dict(progress=0,message='처리 실패',error=str(e)[:600]));traceback.print_exc();return 1

def serve(handler,path,home,base):
    match=re.fullmatch(r'/cad-result/([a-f0-9]{32})/(.+)',path)
    if match:root=Path(home)/match[1]/'cad-output';rel=unquote(match[2])
    elif path.startswith('/cad-assets/'):root=Path(base)/'cad-assets';rel=unquote(path[len('/cad-assets/'):])
    else:return False
    if match and rel=='legacy-context.json':
        folder=root.parent
        if not (root/'building.json').is_file():
            handler.send({'error':'모델이 없습니다.'},404);return True
        manifest=json.loads((folder/'files.json').read_text('utf8'))
        digest=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
        state=folder/'cad-ui-state.json'
        handler.send(dict(jobId=match[1],buildingId=digest,state=json.loads(state.read_text('utf8')) if state.exists() else None));return True
    target=(root/rel).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file() or target.suffix.lower() not in ('.html','.json','.svg','.png','.js','.css'):
        handler.send({'error':'찾을 수 없습니다.'},404);return True
    mime={'.js':'text/javascript','.json':'application/json','.html':'text/html','.svg':'image/svg+xml'}.get(target.suffix,mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
    handler.send(target.read_bytes(),mime=mime);return True
