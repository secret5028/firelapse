"""D-4 grounded read/proposal tools. Never imports or starts a simulation engine."""
import hashlib,json,math,shutil,subprocess,sys,time,uuid,threading
from pathlib import Path
from functools import lru_cache
ROOT=Path(__file__).resolve().parents[1]
SIM=ROOT/'simulation'
sys.path.insert(0,str(SIM))
TYPES=('FO','FGI','backdraft','rollover')
LABELS={'FO':'FO','FGI':'FGI','backdraft':'백드래프트','rollover':'롤오버'}
PENDING={}
PENDING_LOCK=threading.RLock()

def read(p,default=None):
    return json.loads(Path(p).read_text('utf-8-sig')) if Path(p).is_file() else default

def finite(x):return type(x) in (int,float) and math.isfinite(x)
def at(a,i):return a[i] if isinstance(a,list) and i<len(a) and finite(a[i]) else None

def node(a):
    exe=shutil.which('node') or 'E:/hermes/node/node.exe'
    p=subprocess.run([exe,str(ROOT/'tools/lite_ai_read.mjs')],input=json.dumps(a,ensure_ascii=False),text=True,encoding='utf-8',capture_output=True,timeout=45,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if p.returncode:raise ValueError('기존 경로/순위 어댑터 평가 실패')
    return json.loads(p.stdout)

@lru_cache(maxsize=8)
def playback(path,stamp):return read(path)

class Tools:
    names=('list_buildings','get_building','get_ranking','get_case_summary','get_room_timeline','get_peak_events','get_route','get_mc_summary','propose_fuel','propose_openings','propose_run','get_tactic_rules')
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
        stamps=tuple(p.stat().st_mtime_ns if p.exists() else 0 for p in [SIM/'config/lite-viewer.json',SIM/'results/playback-catalog.json',ROOT/'data/wando-coldstore'])
        cached=self._case_cache.get(meta['id'])
        if cached and cached[0]==stamps:return cached[1]
        cfg=read(SIM/'config/lite-viewer.json',{})
        index=read(SIM/'results/playback-catalog.json',{}).get('files',{})
        for r in cfg.get('cases',[]):
            p=Path(r['path']).resolve()
            if p.is_relative_to(ROOT) and p.is_file():
                rel=p.relative_to(SIM/'results').as_posix() if p.is_relative_to(SIM/'results') else ''
                d=index.get(rel) or playback(str(p),p.stat().st_mtime_ns)
                if d.get('building_sha256')==meta['sha']:out[r['id']]=p
        for rel,r in index.items():
            p=(SIM/'results'/rel).resolve()
            if p.is_relative_to(SIM/'results') and r.get('building_sha256')==meta['sha'] and r.get('valid') and p.is_file() and p not in out.values():out['case-'+hashlib.sha256(rel.encode()).hexdigest()[:20]]=p
        if meta['id']=='wando-coldstore':
            for p in (ROOT/'data/wando-coldstore').glob('*-playback.json'):
                d=read(p)
                if d.get('building_sha256')==meta['sha']:out['wando-'+p.name.removesuffix('-playback.json')]=p
        self._case_cache[meta['id']]=(stamps,out)
        return out
    def case(self,a):
        path=self.cases(a['building']).get(a.get('case'))
        if path is None:raise ValueError('현재 건물에 없는 사례')
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
                doors.append({'id':key,'floor':f['name'],'sides':['OUTSIDE' if s=='out' else 'CAD_'+f['name']+'_'+s for s in e.get('sides',[])],'kind':e.get('kind'),'dimensions':e.get('dimensions'),**byid.get(key,{})})
        return {'name':meta['label'],'rooms':rows,'openings':doors,'fixed_state':report.get('fixed_state'),'obstacles':b.get('obstacles',[])}
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
            rid=c.get('original_room') or c['key'];rec=rows.setdefault(rid,{'room':rid,'phenomenon':kind,'threshold':threshold,'first_s':None,'peak':None,'peak_s':None,'source_cell':None,'partial':False})
            s=p['solvers'][c['solver_id']].get('conditions',{}).get(kind,{})
            degrees=s.get('scores',{}).get('degree',s.get('degree',[]))
            for i,t in enumerate(p['time_s']):
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
                frames.append(r)
            out.append({'cell':c['key'],'rows':frames})
        return {'room':a['room'],'aggregation':'single' if len(cells)==1 else 'none','cells':out,'sampling':'10 s exact saved samples; absent samples null; no interpolation','source_end_s':p['time_s'][-1]}
    def get_case_summary(self,a):
        p=self.case(a);burning=set()
        for f in p.get('fires',[]):
            if any(finite(v) and v>0 for v in f.get('Q_kW',[])):
                c=next((c for c in p['rooms'] if c['key']==f.get('cad_key')),None)
                if c:burning.add(c.get('original_room') or c['key'])
        return {'origin':p.get('fire_key'),'engine':p.get('engine_kind'),'end_s':p['time_s'][-1],'complete':p.get('complete'),'opening_state':p.get('opening_states'),'burning_rooms':sorted(burning),'events':{k:self.get_peak_events({**a,'phenomenon':k,'threshold':100}) for k in TYPES},'limits':p.get('limits',[])}
    def get_route(self,a):
        _,b=self.building(a['building']);p=self.case(a)
        origin=a.get('origin') or p.get('route_target_room_id') or p.get('fire_key')
        c=next((r for r in p['rooms'] if r['key']==origin),None)
        if c:origin=c.get('original_room') or c['key']
        if a.get('vehicle') is not None and (not isinstance(a['vehicle'],list) or len(a['vehicle'])!=3 or not all(finite(x) for x in a['vehicle'])):raise ValueError('차량 좌표 오류')
        return node({'kind':'route','building':b,'playback':p,'case':a['case'],'origin':origin,'vehicle':a.get('vehicle'),'time_s':a.get('time_s',0),'history':a.get('history',False),'settings':a.get('route_settings',{})})
    def get_mc_summary(self,a):
        job=a.get('job')
        import re
        if not isinstance(job,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,120}',job):raise ValueError('작업 ID 오류')
        roots=[SIM/'results'/job,SIM/'results/lite_mc_jobs'/job]
        meta,_=self.building(a['building'])
        for root in roots:
            for name in ('summary.json','mc-summary.json'):
                d=read(root/name)
                if d and d.get('building_sha256')==meta['sha']:return d
        return {'status':'미평가','reason':'해당 건물과 연결된 MC 요약 없음'}
    def propose_fuel(self,a):
        import lite_ai_fuel
        meta,b=self.building(a['building'])
        return lite_ai_fuel.propose({'message':a.get('message'),'history':a.get('history',[])},b,meta['sha'])
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
