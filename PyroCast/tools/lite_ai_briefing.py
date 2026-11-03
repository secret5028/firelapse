"""Server-only rule matching and fixed briefing; no tactical text from an LLM."""
import json,time,uuid,datetime,threading
from lite_ai_tools import ROOT,SIM,TYPES,LABELS,read,finite,at,display_label,display_text,rollover_at
from result_catalog import atomic_json
REPORTS={}
LOCK=threading.RLock()

def matches(rule,values):
    def one(c):
        key,op,b=c;a=values.get(key)
        if a is None:return False
        if op=='==':return type(a)==type(b) and a==b or finite(a) and finite(b) and a==b
        if not finite(a) or not finite(b):return False
        return {'>=':a>=b,'<=':a<=b,'<':a<b,'>':a>b}[op]
    return all(one(c) for c in rule.get('all',[])) and (any(one(c) for c in rule['any']) if 'any' in rule else True)

def stamp(t):return '미평가' if not finite(t) else f'{int(t//60):02}:{t%60:05.2f}'.rstrip('0').rstrip('.')
def number(v):return '미평가' if not finite(v) else f'{v:.2f}'.rstrip('0').rstrip('.')

def match_case(service,a,route,rules):
    p=service.case(a);building=service.get_building(a);on_route={r['room'] for r in (route.get('risk') or {}).get('rows',[])}
    path=service.cases(a['building'])[a['case']];sample=read(path.with_name('sample.json'),{})
    openings=sample.get('openings',[]);output=[];seen=set()
    # Evaluate predicates together at one saved cell/time, never combine independent peaks.
    for c in p['rooms']:
        rid=c.get('original_room') or c['key'];s=p['solvers'][c['solver_id']]
        doors=[d for d in building['openings'] if rid in d.get('sides',[]) and 'door' in d.get('kind','')]
        known=[o for o in openings if o.get('id') in {d['id'] for d in doors}]
        closed=any(o.get('open') is False for o in known) if known else None
        for i,t in enumerate(p['time_s']):
            values={k:(v*100 if (v:=at(s.get('conditions',{}).get(k,{}).get('scores',{}).get('degree'),i)) is not None else None) for k in TYPES}
            temp=at(s.get('Tu'),i);prev=at(s.get('Tu'),i-1) if i else None
            values['rollover_active']=rollover_at(s,i)
            values.update(Tu=temp,h=at(s.get('h'),i),door_closed=closed,on_route=rid in on_route,entry_count=len(doors) if doors else None,temperature_rising=temp>prev if temp is not None and prev is not None else None,external_water=None,inside_personnel=None)
            for rule in rules['rules']:
                key=(rid,rule['code'])
                if key not in seen and matches(rule,values):
                    seen.add(key);output.append({'room':rid,'cell':c['key'],'label':display_label(rid,c.get('display_name')),'time_s':t,'code':rule['code'],'text':rule['text'],'notice':rules['notice'],'values':values})
    return output

def event_fact(e,tool_index):
    label=display_label(e['room'],e.get('name'))
    suffix=f" · 롤오버 진행 최초 {stamp(e['rollover_first_s'])}" if e['phenomenon']=='FGI' and e.get('rollover_first_s') is not None else ''
    return {'room':e['room'],'cell':e.get('source_cell'),'time_s':e['peak_s'],'text':f"{label} · {LABELS[e['phenomenon']]} 최고 {number(e['peak'])} @ {stamp(e['peak_s'])} · 최초 기준 도달 {stamp(e['first_s'])}{suffix}",'evidence':{'call':tool_index,'row':e},'numbers':[v for v in [e['peak'],e['peak_s'],e['first_s']] if v is not None]}

def facts_for(call,i):
    name=call['tool'];d=call['data'];facts=[]
    if name=='get_peak_events':return [event_fact(e,i) for e in d if e['peak'] is not None]
    if name=='get_case_summary':
        return [{'room':d['origin'],'cell':d['origin'],'text':f"현재 저장 사례 화점: {d.get('origin_label',display_label(d['origin']))} · {d['engine']} · 종료 {stamp(d['end_s'])}",'evidence':{'call':i,'row':d}}]+[event_fact(e,i) for k in TYPES for e in d['events'][k][:1]]
    if name=='get_ranking':
        for r in d['second'][:3]:
            facts.append({'room':r['room'],'time_s':r.get('first_FO_s'),'text':f"{display_label(r['room'],r.get('name'))} · ② {r.get('rank2') or '미평가'}위 · 연소 {number(r.get('burning_room_count'))} · 주의 {number(r.get('attention_room_count'))} · 최초 FO {stamp(r.get('first_FO_s'))}",'evidence':{'call':i,'row':r}})
    elif name=='get_route':
        r=d['route'];facts.append({'text':display_text(r['error']) if r.get('error') else f"{r.get('entry_label',display_label(r['entry']))} → {r.get('target_label',display_label(r['target']))} · {number(r['length'])} m · 호스 {r['hoses']}본 · 계단 {r['stairs']}회",'room':r.get('target'),'evidence':{'call':i,'row':r}})
        for r in (d.get('risk') or {}).get('rows',[]):
            index=r.get('index');risk='—' if index is None or index==0 else f"{r['phenomenon'] if index>=70 else '—'} {number(index)}"
            tip='미평가: 저장된 지수 없음' if index is None else ('지수 0: 평가됨' if index==0 else '평가된 지수')
            if r.get('partial'):tip+=' · 일부 셀/현상 미평가'
            facts.append({'text':f"{r['label']} · 누적 {number(r['end_m'])} m · {risk}",'tooltip':tip,'room':r.get('room'),'evidence':{'call':i,'row':r}})
    elif name=='get_room_timeline':
        for c in d['cells']:
            for r in c['rows']:
                facts.append({'room':d['room'],'cell':c['cell'],'time_s':r['time_s'],'text':f"{display_label(c['cell'])} @ {stamp(r['time_s'])} · 상층 {number(r['Tu'])} ℃ · O₂ {number(r['Ou']*100 if r['Ou'] is not None else None)} % · 연기층 {number(r['h'])} m",'evidence':{'call':i,'row':r}})
    elif name in ('get_building','list_buildings','get_mc_summary','get_tactic_rules'):
        facts.append({'text':display_text(json.dumps(d,ensure_ascii=False,indent=2)),'evidence':{'call':i,'row':d}})
    return facts

def briefing(service,a):
    calls=[]
    def get(name,**kwargs):
        result=service.call(name,{**a,**kwargs});calls.append(result);return result['data']
    ranking=get('get_ranking');summary=get('get_case_summary');route=get('get_route')
    peaks={k:get('get_peak_events',phenomenon=k,threshold=100) for k in TYPES}
    rules=get('get_tactic_rules');rules['matched']=match_case(service,a,route,rules)
    facts=[];lines=[f"[{a.get('floor') or '선택 건물'} 화재 위험 브리핑 · 사례 {a['case']} · {summary['engine']}]",'1. 최위험 화점 (저장된 ② 순위)']
    for f in facts_for(calls[0],0):facts.append(f);lines.append('   '+f['text'])
    if not ranking['second']:lines.append('   미평가')
    lines.append('2. 진입 경로')
    for f in facts_for(calls[2],2):facts.append(f);lines.append('   '+f['text'])
    lines.append('3. 경로상 위험 (전 구간 최고, 현재 시각과 구분)')
    route_rooms={r['room'] for r in (route.get('risk') or {}).get('rows',[])}
    for i,k in enumerate(TYPES,3):
        for e in peaks[k]:
            if e['room'] in route_rooms and e['peak'] is not None and e['peak']>=70:
                f=event_fact(e,i);facts.append(f);lines.append('   '+f['text'])
    lines.append('4. 전술 참고 · '+rules['status'])
    used=[]
    for m in rules['matched']:
        if m['room'] not in route_rooms:continue
        used.append(m['code']);f={'room':m['room'],'cell':m['cell'],'time_s':m['time_s'],'text':f"{m['label']} @ {stamp(m['time_s'])} [{m['code']}] {m['text']} · {m['notice']}",'evidence':{'call':len(calls)-1,'row':m}};facts.append(f);lines.append('   '+f['text'])
    if not used:lines.append('   규칙 없음 또는 판정자료 미평가')
    lines.append('5. 한계: 조건 충족 지수이며 발생 예측 아님. 다중 셀 방 평균 없음. 전술 규칙은 사용자 제공 초안이며 현장 지휘관 판단 우선.')
    lines.extend('   '+display_text(v) for v in summary['limits'])
    value={'building':a['building'],'case':a['case'],'text':'\n'.join(lines),'facts':facts,'calls':calls,'rules':sorted(set(used)),'proposals':[],'status':'초안 · 사용자(CFBT) 검수 필요'}
    token=uuid.uuid4().hex;value['briefing_id']=token
    with LOCK:
        for k in list(REPORTS):
            if REPORTS[k]['expires']<time.monotonic():del REPORTS[k]
        if len(REPORTS)>=100:del REPORTS[next(iter(REPORTS))]
        REPORTS[token]={'value':value,'expires':time.monotonic()+3600,'source_sha':__import__('hashlib').sha256(service.cases(a['building'])[a['case']].read_bytes()).hexdigest()}
    return value

def save_report(service,token):
    with LOCK:
        item=REPORTS.get(token)
        if not item or item['expires']<time.monotonic():raise ValueError('브리핑이 만료되었습니다')
        v=item['value'];path=service.cases(v['building'])[v['case']]
        if __import__('hashlib').sha256(path.read_bytes()).hexdigest()!=item['source_sha']:raise ValueError('사례가 바뀌었습니다. 브리핑을 다시 생성하세요')
        root=path.parent/'assistant-reports';root.mkdir(exist_ok=True)
        report={'id':token,'case':v['case'],'building':v['building'],'created':datetime.datetime.now(datetime.timezone.utc).isoformat(),'markdown':v['text'],'rules':v['rules'],'source_sha256':item['source_sha'],'calls':v['calls']}
        atomic_json(root/(token+'.json'),report);(root/(token+'.md')).write_text(v['text']+'\n','utf-8');return {'id':token,'case':v['case'],'saved':True}

def list_reports(service,a):
    path=service.cases(a['building']).get(a['case'])
    if not path:raise ValueError('사례 없음')
    return [{'id':r['id'],'case':r['case'],'created':r['created'],'markdown':r['markdown']} for p in sorted((path.parent/'assistant-reports').glob('*.json')) if (r:=read(p)).get('case')==a['case']]
