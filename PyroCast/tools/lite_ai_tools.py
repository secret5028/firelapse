"""D-4 grounded read/proposal tools. Never imports or starts a simulation engine."""
import hashlib,json,math,re,shutil,subprocess,sys,time,uuid,threading
from pathlib import Path
from functools import lru_cache
ROOT=Path(__file__).resolve().parents[1]
SIM=ROOT/'simulation'
sys.path.insert(0,str(SIM))
TYPES=('FO','FGI','backdraft')
LABELS={'FO':'FO','FGI':'FGI','backdraft':'BD'}
PENDING={}
PENDING_LOCK=threading.RLock()

def read(p,default=None):
    return json.loads(Path(p).read_text('utf-8-sig')) if Path(p).is_file() else default

def display_text(text):
    # Presentation only: evidence and navigation retain their original IDs.
    return re.sub(r'CAD_[A-Za-z0-9]+_[A-Za-z0-9_]+',lambda m:m[0][4:].replace('_',' '),str(text))

def display_label(identity,name=None):
    short=str(identity).removeprefix('CAD_').replace('_',' ') if identity else '외부'
    return display_text(short+(' · '+name if name and name!=identity else ''))

def finite(x):return type(x) in (int,float) and math.isfinite(x)
def at(a,i):return a[i] if isinstance(a,list) and i<len(a) and finite(a[i]) else None

def rollover_at(s,i,threshold=100):
    f=s.get('conditions',{}).get('FGI',{});r=f.get('rollover',{})
    if isinstance(r.get('active'),list) and i is not None:return r['active'][i] if i<len(r['active']) else None
    if r.get('excluded_origin') is True:return False
    if r.get('excluded_origin') is not False or i is None:return None
    ignition=r.get('ignition',[]);value=at(f.get('scores',{}).get('degree'),i)
    if i>=len(ignition):return None
    if ignition[i] is False:return False
    return value*100>=threshold if ignition[i] is True and value is not None else None

def node(a):
    exe=shutil.which('node') or 'E:/hermes/node/node.exe'
    p=subprocess.run([exe,str(ROOT/'tools/lite_ai_read.mjs')],input=json.dumps(a,ensure_ascii=False),text=True,encoding='utf-8',capture_output=True,timeout=45,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if p.returncode:raise ValueError('기존 경로/순위 어댑터 평가 실패')
    return json.loads(p.stdout)

@lru_cache(maxsize=8)
def playback(path,stamp):return read(path)

class Tools:
    _saved_case = None
    names=('list_buildings','get_building','get_ranking','get_case_summary','get_room_timeline','get_index_windows','get_peak_events','get_route','get_mc_summary','propose_fuel','propose_openings','propose_run','get_tactic_rules')
    def __init__(self):
        candidates=[('cad-main','기존 CAD 건물',ROOT/'cad-project/building.json'),('cad-main','기존 CAD 건물',SIM/'results/github-publish-20261026/PyroCast/cad-project/building.json'),('wando-coldstore','완도 저온창고',ROOT/'data/wando-coldstore/operating-building.json')]
        self.buildings={}
        self._case_cache={}
        for key,label,path in candidates:
            if key not in self.buildings and path.is_file():self.buildings[key]={'id':key,'label':label,'path':path,'sha':hashlib.sha256(path.read_bytes()).hexdigest()}
    def building(self,key):
        row=next((v for k,v in self.buildings.items() if key in (k,v['sha'])),None)
        if row is None:raise ValueError('등록되지 않은 건물')
        return row,read(row['path'])
    def cases(self,key):
        meta,_=self.building(key);out={}
        from runtime_storage import result_roots, is_result_path, app_path
        roots=result_roots()
        aliases=SIM/'config/native-case-aliases.json'
        stamps=tuple(p.stat().st_mtime_ns if p.exists() else 0 for p in [SIM/'config/lite-viewer.json',aliases,*[r/'playback-catalog.json' for r in roots],ROOT/'data/wando-coldstore'])
        cached=self._case_cache.get(meta['id'])
        if cached and cached[0]==stamps:return cached[1]
        cfg=read(SIM/'config/lite-viewer.json',{})
        index=read(SIM/'results/playback-catalog.json',{}).get('files',{})
        for r in cfg.get('cases',[]):
            p=app_path(r['path']).resolve()
            if (p.is_relative_to(ROOT) or is_result_path(p)) and p.is_file():
                rel=p.relative_to(SIM/'results').as_posix() if p.is_relative_to(SIM/'results') else ''
                d=index.get(rel) or playback(str(p),p.stat().st_mtime_ns)
                if d.get('building_sha256')==meta['sha']:out[r['id']]=p
        for root in reversed(roots):
            for rel,r in read(root/'playback-catalog.json',{}).get('files',{}).items():
                p=(root/rel).resolve()
                if p.is_relative_to(root.resolve()) and r.get('building_sha256')==meta['sha'] and r.get('valid') and p.is_file() and p not in out.values():out['case-'+hashlib.sha256(rel.encode()).hexdigest()[:20]]=p
        for ident,row in read(aliases,{}).items():
            path=(SIM/'results'/row['relative_path']).resolve()
            if path in out.values():out[ident]=path
        if meta['id']=='wando-coldstore':
            for p in (ROOT/'data/wando-coldstore').glob('*-playback.json'):
                d=read(p)
                if d.get('building_sha256')==meta['sha']:out['wando-'+p.name.removesuffix('-playback.json')]=p
        self._case_cache[meta['id']]=(stamps,out)
        return out
    def bind_saved_case(self, building, case, path):
        self._saved_case = (building, case, path)
        return self

    def case_path(self,a):
        case=a.get('case')
        if self._saved_case is not None:
            building,ident,path=self._saved_case
            if a['building']==building and case==ident:return path
        path=self.cases(a['building']).get(case)
        if path is None and isinstance(case,str) and case.startswith('calc-'):
            from fixed_calculation import playback_file
            meta,_=self.building(a['building'])
            path=playback_file(meta['sha'],case)
        if path is None:raise ValueError('현재 건물에 없는 사례')
        return path
    def case(self,a):
        path=self.case_path(a)
        return playback(str(path),path.stat().st_mtime_ns)
    def call(self,name,a):
        if name not in self.names or not isinstance(a,dict):raise ValueError('도구/입력 오류')
        value=getattr(self,name)(a)
        return {'tool':name,'building':a.get('building'),'case':a.get('case'),'data':value,'missing_value':'미평가'}
    def list_buildings(self,a):
        return [{'building':k,'name':v['label'],'floors':len((b:=read(v['path']))['floors']),'rooms':sum(len(f['rooms']) for f in b['floors']),'cases':len(self.cases(k))} for k,v in self.buildings.items()]
    def get_building(self,a):
        meta,b=self.building(a['building']);rows=[]
        import lite_ai_fuel
        try:rows=lite_ai_fuel.context(b,meta['sha'])['rooms']
        except ValueError:
            # Another building's saved override must never leak into this one.
            rows=[{'id':'CAD_'+f['name']+'_'+r['id'],'floor':f['name'],'name':' / '.join(r.get('names',[])),'area':r.get('area'),'usage':None,'load':None} for f in b['floors'] for r in f['rooms']]
        doors=[]
        if meta['id']=='cad-main':
            from lite_fixed_openings import door_report
            raw=read(SIM/'results/room_rule_r8_20261025/source-scenario.json')
            report=door_report(raw,read(SIM/'config/lite-door-overrides.json',{}))
        else:report={'rows':[],'fixed_state':None}
        byid={r['id']:r for r in report.get('rows',[])}
        for f in b['floors']:
            for e in f.get('simulation_graph',{}).get('connections',[]):
                key='CAD_'+f['name']+'_'+e['id']
                doors.append({'id':key,'floor':f['name'],'sides':['OUTSIDE' if s in ('out','OUTSIDE') else 'CAD_'+f['name']+'_'+s for s in e.get('sides',[])],'kind':e.get('kind'),'dimensions':e.get('dimensions'),**byid.get(key,{})})
        from d5_evidence import enrich
        return enrich(self,a,{'name':meta['label'],'rooms':rows,'openings':doors,'fixed_state':report.get('fixed_state'),'obstacles':b.get('obstacles',[])})
    def get_ranking(self,a):
        meta,_=self.building(a['building'])
        if meta['id']!='cad-main':return {'first':[],'second':[],'status':'미평가'}
        import lite_screening_service
        p=lite_screening_service.payload();floor=a.get('floor')
        first=[r for r in p['score']['ranked'] if not floor or r.get('floor')==floor]
        second=node({'kind':'ranking','payload':p})
        ids={r['room'] for r in first}
        return {'first':first,'second':[r for r in second if r['room'] in ids],'fuel_rerun_required':p.get('fuel_rerun_required'),'opening_mode':p.get('opening_mode')}
    def cells(self,p,room=None):
        return [r for r in p['rooms'] if room is None or room in (r['key'],r.get('original_room'))]
    def get_peak_events(self,a):
        p=self.case(a);kind=a.get('phenomenon');threshold=a.get('threshold',100)
        if kind not in TYPES or not finite(threshold) or threshold<0:raise ValueError('현상/기준 오류')
        rows={}
        for c in self.cells(p):
            rid=c.get('original_room') or c['key'];rec=rows.setdefault(rid,{'room':rid,'name':c.get('display_name'),'phenomenon':kind,'threshold':threshold,'first_s':None,'peak':None,'peak_s':None,'source_cell':None,'partial':False,'rollover_first_s':None})
            solver=p['solvers'][c['solver_id']];s=solver.get('conditions',{}).get(kind,{})
            degrees=s.get('scores',{}).get('degree',s.get('degree',[]))
            for i,t in enumerate(p['time_s']):
                if kind=='FGI' and rollover_at(solver,i,threshold) is True and (rec['rollover_first_s'] is None or t<rec['rollover_first_s']):rec['rollover_first_s']=t
                v=at(degrees,i)
                if v is None:rec['partial']=True;continue
                v*=100 # Same presentation scaling as read.js; not a new condition.
                if v>=threshold and (rec['first_s'] is None or t<rec['first_s']):rec['first_s']=t
                if rec['peak'] is None or v>rec['peak']:rec.update(peak=v,peak_s=t,source_cell=c['key'])
        return sorted(rows.values(),key=lambda r:-(r['peak'] if r['peak'] is not None else -1))
    def get_room_timeline(self,a):
        p=self.case(a);cells=self.cells(p,a.get('room'))
        if not cells:raise ValueError('사례에 없는 실')
        t0=a.get('t0',0);t1=a.get('t1',p['time_s'][-1])
        if not finite(t0) or not finite(t1) or t0<0 or t1<t0 or t1>p['time_s'][-1]:raise ValueError('시간 범위 오류')
        times={t:i for i,t in enumerate(p['time_s'])};out=[]
        for c in cells:
            s=p['solvers'][c['solver_id']];frames=[]
            for t in range(math.ceil(t0/10)*10,math.floor(t1/10)*10+1,10):
                i=times.get(t);r={'time_s':t,'Tu':None,'Ou':None,'fuel':None,'h':None,'indices':{},'bottleneck':{}}
                for key in ('Tu','Ou','fuel','h'):r[key]=at(s.get('Fu' if key=='fuel' else key),i) if i is not None else None
                for key in TYPES:
                    scores=s.get('conditions',{}).get(key,{}).get('scores',{});v=at(scores.get('degree'),i) if i is not None else None
                    r['indices'][key]=v*100 if v is not None else None
                    weak=scores.get('weakest',[]);r['bottleneck'][key]=weak[i] if i is not None and i<len(weak) else None
                r['rollover_active']=rollover_at(s,i)
                frames.append(r)
            out.append({'cell':c['key'],'rows':frames})
        return {'room':a['room'],'aggregation':'single' if len(cells)==1 else 'none','cells':out,'sampling':'10 s exact saved samples; absent samples null; no interpolation','source_end_s':p['time_s'][-1]}
    def get_index_windows(self,a):
        from d5_tools import windows
        p=self.case(a)
        if not self.cells(p,a.get('room')):
            return {'room':a.get('room'),'phenomenon':a.get('phenomenon'),'threshold':a.get('threshold',100),'windows':[],'evaluated':False,'partial':True}
        return windows(self.get_room_timeline(a),a.get('phenomenon'),a.get('threshold',100))
    def get_case_summary(self,a):
        p=self.case(a);burning=set()
        for f in p.get('fires',[]):
            if any(finite(v) and v>0 for v in f.get('Q_kW',[])):
                c=next((c for c in p['rooms'] if c['key']==f.get('cad_key')),None)
                if c:burning.add(c.get('original_room') or c['key'])
        events={k:self.get_peak_events({**a,'phenomenon':k,'threshold':100}) for k in TYPES}
        path=self.case_path(a);sample=read(path.with_name('sample.json'),{})
        origin=p.get('fire_key');cell=next((c for c in p['rooms'] if c['key']==origin),{})
        return {'origin':origin,'origin_room':cell.get('original_room') or origin,'origin_label':display_label(origin,cell.get('display_name')),'engine':p.get('engine_kind'),'end_s':p['time_s'][-1],'complete':p.get('complete'),'opening_state':p.get('opening_states') or sample.get('openings'),'burning_rooms':sorted(burning),'burning_basis':'저장된 실제 화원 HRR > 0 표본이 있는 원래 방','events':events,
            'first_100':{k:min((e for e in rows if e['first_s'] is not None),key=lambda e:e['first_s'],default=None) for k,rows in events.items()},
            'worst':{k:next((e for e in rows if e['peak'] is not None),None) for k,rows in events.items()},'limits':p.get('limits',[])}
    def get_route(self,a):
        _,b=self.building(a['building']);p=self.case(a)
        if not finite(a.get('time_s',0)) or not 0<=a.get('time_s',0)<=p['time_s'][-1] or type(a.get('history',False)) is not bool:raise ValueError('경로 시간/이력 오류')
        settings=a.get('route_settings',{})
        if not isinstance(settings,dict) or set(settings)-{'hose_m','stair_factor'} or any(not finite(v) or v<1 for v in settings.values()):raise ValueError('호스/계단 설정 오류')
        origin=a.get('origin') or p.get('route_target_room_id') or p.get('fire_key')
        c=next((r for r in p['rooms'] if r['key']==origin),None)
        if c:origin=c.get('original_room') or c['key']
        if a.get('vehicle') is not None and (not isinstance(a['vehicle'],list) or len(a['vehicle'])!=3 or not all(finite(x) for x in a['vehicle'])):raise ValueError('차량 좌표 오류')
        result=node({'kind':'route','building':b,'playback':p,'case':a['case'],'origin':origin,'vehicle':a.get('vehicle'),'time_s':a.get('time_s',0),'history':a.get('history',False),'settings':a.get('route_settings',{})})
        names={'CAD_'+f['name']+'_'+r['id']:' / '.join(r.get('names',[])) for f in b['floors'] for r in f['rooms']}
        for c in p['rooms']:
            label=c.get('display_name') or ' / '.join(c.get('cad_names',[]))
            if label:names[c.get('original_room') or c['key']]=label
        route=result['route'];route['entry_label']=display_label(route.get('entry'));route['target_label']=display_label(route.get('target'),names.get(route.get('target')))
        for row in (result.get('risk') or {}).get('rows',[]):row['label']=display_label(row.get('room'),names.get(row.get('room')))
        from d5_tools import hose_segments
        result['hose_segments']=hose_segments(result,self.get_building(a),settings.get('hose_m',15))
        return result
    def get_mc_summary(self,a):
        job=a.get('job')
        import re
        if not isinstance(job,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,120}',job):raise ValueError('작업 ID 오류')
        from runtime_storage import result_roots
        roots=[p for r in result_roots() for p in (r/job,r/'lite_mc_jobs'/job)]
        meta,_=self.building(a['building'])
        for root in roots:
            for name in ('summary.json','mc-summary.json'):
                d=read(root/name)
                if d and d.get('building_sha256')==meta['sha']:
                    from lite_fixed_openings import ranked_samples
                    try:ranking=ranked_samples(root,meta['sha'])
                    except (ValueError,KeyError,OSError):ranking=[]
                    d={**d,'rates':{k:v for k,v in d.get('rates',{}).items() if k in TYPES}}
                    return {**d,'ranking':ranking,'worst':ranking[0] if ranking else None,'ratio_basis':'표본 분포 내 조건 충족 비율; 발생 확률 아님'}
        return {'status':'미평가','reason':'해당 건물과 연결된 MC 요약 없음'}
    def propose_fuel(self,a):
        import lite_ai_fuel
        from lite_ai_chat import transport
        meta,b=self.building(a['building'])
        return lite_ai_fuel.propose({'message':a.get('message'),'history':a.get('history',[])},b,meta['sha'],transport=transport)
    def propose_openings(self,a):
        rows=a.get('openings');available={r['id']:r for r in self.get_building(a)['openings']}
        if not isinstance(rows,list) or not rows or len(rows)>len(available):raise ValueError('개구부 제안 목록 오류')
        seen=set()
        for r in rows:
            if not isinstance(r,dict) or set(r)!={'id','open'} or r['id'] not in available or type(r['open']) is not bool or r['id'] in seen:raise ValueError('개구부 ID/상태 오류')
            seen.add(r['id'])
        meta,_=self.building(a['building'])
        if meta['id']!='cad-main':raise ValueError('이 건물은 개구부 적용 경로가 없습니다')
        config=SIM/'config/lite-door-overrides.json';old=read(config,{})
        token=uuid.uuid4().hex
        with PENDING_LOCK:
            for k in list(PENDING):
                if PENDING[k]['expires']<time.monotonic():del PENDING[k]
            if len(PENDING)>=100:raise ValueError('적용 대기 제안이 너무 많습니다')
            PENDING[token]={'sha':meta['sha'],'rows':rows,'revision':hashlib.sha256(json.dumps(old,sort_keys=True).encode()).hexdigest(),'expires':time.monotonic()+1800}
        return {'proposal_id':token,'kind':'openings','openings':rows,'requires_user_apply':True,'applied':False,'basis':'기존 확정 급기, 없으면 저장된 원본 입력의 나머지 개구부 상태 유지'}
    def propose_run(self,a):
        rooms={r['id'] for r in self.get_building(a)['rooms']}
        if a.get('kind') not in ('screening','mc') or a.get('origin') not in rooms:raise ValueError('실행 종류/화점 오류')
        n=a.get('N',8) if a['kind']=='screening' else a.get('samples',2)
        if type(n) is not int or not (1 if a['kind']=='screening' else 2)<=n<= (len(rooms) if a['kind']=='screening' else 1000):raise ValueError('표본/N 범위 오류')
        return {'kind':a['kind'],'origin':a['origin'],'N':n if a['kind']=='screening' else None,'samples':n if a['kind']=='mc' else None,'requires_user_apply':True,'started':False}
    def get_tactic_rules(self,a):return read(ROOT/'config/tactic_rules.json',{'status':'미평가','rules':[]})

def apply_opening_proposal(token,sha,config_path=None):
    from lite_fixed_openings import fixed_for
    from result_catalog import atomic_json
    config_path=config_path or SIM/'config/lite-door-overrides.json'
    with PENDING_LOCK:
        p=PENDING.get(token)
        if not p or p['sha']!=sha or p['expires']<time.monotonic():raise ValueError('제안 만료/건물 불일치')
        old=read(config_path,{})
        if hashlib.sha256(json.dumps(old,sort_keys=True).encode()).hexdigest()!=p['revision']:raise ValueError('문 설정이 바뀌었습니다. 제안을 다시 요청하세요')
        raw=read(SIM/'results/room_rule_r8_20261025/source-scenario.json');vents={v['id']:v for v in raw['openings']}
        states=json.loads(json.dumps((old.get('fixed_state') or {}).get('states') or {v['id']:{'a':v['a'],'b':v['b'],'open':v['schedule'][0][1]>0,'effective_fraction':v['schedule'][0][1]} for v in raw['openings']}))
        for row in p['rows']:
            v=vents.get(row['id'])
            if v is None:raise ValueError('원본 입력에 없는 개구부')
            states[row['id']].update(open=row['open'],effective_fraction=(.5 if 'window' in v.get('kind','') else 1.) if row['open'] else 0.)
        fixed={'building_sha256':sha,'states':states,'source':'user_applied_assistant_proposal','proposal_id':token}
        fixed_for(raw,{'fixed_state':fixed});atomic_json(config_path,{**old,'fixed_state':fixed});del PENDING[token]
        return fixed
