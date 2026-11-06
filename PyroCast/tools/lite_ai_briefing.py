"""Server-only rule matching and fixed briefing; no tactical text from an LLM."""
import json,time,uuid,datetime,threading
from lite_ai_tools import ROOT,SIM,TYPES,LABELS,read,finite,at,display_label,display_text,rollover_at
from result_catalog import atomic_json
REPORTS={}
LOCK=threading.RLock()

from d5_match import matches, match_case

def stamp(t):return '미평가' if not finite(t) else f'{int(t//60):02}:{t%60:05.2f}'.rstrip('0').rstrip('.')
def number(v):return '미평가' if not finite(v) else f'{v:.2f}'.rstrip('0').rstrip('.')

def event_fact(e,tool_index):
    label=display_label(e['room'],e.get('name'))
    suffix=f" · 롤오버 조건 충족 최초 {stamp(e['rollover_first_s'])}" if e['phenomenon']=='FGI' and e.get('rollover_first_s') is not None else ''
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
    from d5_briefing import fill
    from d5_polish import polish
    value=polish(fill(service,a))
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
        report={'id':token,'case':v['case'],'building':v['building'],'created':datetime.datetime.now(datetime.timezone.utc).isoformat(),'markdown':v['text'],'rules':v['rules'],'source_sha256':item['source_sha'],'calls':v['calls'],'matching_log':v.get('matching_log',[]),'template_version':v.get('template_version')}
        atomic_json(root/(token+'.json'),report);(root/(token+'.md')).write_text(v['text']+'\n','utf-8');return {'id':token,'case':v['case'],'saved':True}

def list_reports(service,a):
    path=service.cases(a['building']).get(a['case'])
    if not path:raise ValueError('사례 없음')
    return [{'id':r['id'],'case':r['case'],'created':r['created'],'markdown':r['markdown']} for p in sorted((path.parent/'assistant-reports').glob('*.json')) if (r:=read(p)).get('case')==a['case']]
