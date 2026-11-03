"""D-4 acceptance flows with a test-only mock LLM and real saved results."""
import sys,os,json,re,unittest,uuid,tempfile,hashlib
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation'),str(ROOT/'simulation/deps')]
from lite_ai_tools import Tools,TYPES,apply_opening_proposal,SIM
from lite_ai_briefing import briefing,matches,save_report,list_reports
import lite_ai_chat as chat

def plan(*calls,finish=True,missing=False):return json.dumps({'calls':[{'name':n,'arguments':a} for n,a in calls],'finish':finish,'rules_missing':missing})

class Acceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.s=Tools();cls.ctx={'building':'cad-main','case':'S09','floor':'3F','time_s':1420}
    def invoke(self,text,replies):
        values=iter(replies);secret=uuid.uuid4().hex;env={'D4_TEST_KEY':secret}
        with patch.dict(os.environ,env),patch.object(chat,'settings',return_value={'base_url':'http://127.0.0.1:1/v1','model':'test','api_key_env':'D4_TEST_KEY'}):
            value=chat.chat(self.s,{'context':self.ctx,'message':text},completion=lambda *args:next(values))
        self.assertNotIn(secret,json.dumps(value));self.assert_numbers(value);return value
    def assert_numbers(self,value):
        # Every displayed fact must point at a row returned by a recorded tool.
        # Compare extracted numeric tokens to the actual cited row, including
        # allowed decimal formatting, clock formatting and volume-% unit format.
        from lite_ai_briefing import facts_for,event_fact,number,stamp
        for fact in value['facts']:
            ev=fact['evidence'];call=value['calls'][ev['call']]
            encoded=json.dumps(call['data'],ensure_ascii=False,sort_keys=True)
            self.assertIn(json.dumps(ev['row'],ensure_ascii=False,sort_keys=True),encoded)
            if call['tool']=='get_peak_events':expected=event_fact(ev['row'],ev['call'])['text']
            else:expected=next(f['text'] for f in facts_for(call,ev['call']) if f['evidence']['row']==ev['row'])
            self.assertEqual(re.findall(r'\d+(?:\.\d+)?',fact['text']),re.findall(r'\d+(?:\.\d+)?',expected))
    def test_1_ranking(self):
        v=self.invoke('3층에서 불나면 제일 위험한 실 어디야',[plan(('get_ranking',{'floor':'3F'}))]);self.assertTrue(v['facts'])
    def test_2_route_peak(self):
        v=self.invoke('R3 진입 경로상 백드래프트 최고 실과 시각',[plan(('get_route',{'origin':'CAD_3F_R3'}),('get_peak_events',{'phenomenon':'backdraft','threshold':100}))]);self.assertTrue(v['facts'])
    def test_3_ventilation_proposals_no_run(self):
        rows=self.s.get_building(self.ctx)['openings'];window=next(r for r in rows if 'window' in r.get('kind','') and 'CAD_3F_R2' in r['sides'])
        v=self.invoke('거기 배연하면?',[plan(('propose_openings',{'openings':[{'id':window['id'],'open':True}]}),('propose_run',{'kind':'screening','origin':'CAD_3F_R3','N':8}))]);self.assertEqual(len(v['proposals']),2)
        self.assertFalse(v['proposals'][1]['started'])
        with tempfile.TemporaryDirectory(dir=ROOT/'app/tests',prefix='d4-temp-') as tmp:
            p=Path(tmp)/'doors.json';p.write_bytes((SIM/'config/lite-door-overrides.json').read_bytes())
            fixed=apply_opening_proposal(v['proposals'][0]['proposal_id'],self.s.building('cad-main')[0]['sha'],p)
            self.assertTrue(fixed['states'][window['id']]['open'])
            with self.assertRaises(ValueError):apply_opening_proposal(v['proposals'][0]['proposal_id'],self.s.building('cad-main')[0]['sha'],p)
    def test_4_fuel_proposal(self):
        import lite_ai_fuel
        def fake(cfg,key,messages):
            ctx=json.loads(messages[0]['content'].split('\n',1)[1]);return json.dumps([{'room_id':r['id'],'usage_class':'warehouse','reason':'테스트 전용 응답: 타이어 전용 클래스 없어 창고 대용'} for r in ctx['rooms'] if r['floor']=='2F'])
        secret=uuid.uuid4().hex
        with patch.dict(os.environ,{'D4_TEST_KEY':secret}),patch.object(lite_ai_fuel,'settings',return_value={'base_url':'http://127.0.0.1:1/v1','model':'test','api_key_env':'D4_TEST_KEY'}),patch.object(chat,'transport',fake):
            v=self.invoke('2층은 타이어창고로 바꿔',[plan(('propose_fuel',{}))])
        self.assertTrue(v['proposals'][0]['rows']);self.assertTrue(all(r['room_id'].startswith('CAD_2F_') for r in v['proposals'][0]['rows']))
    def test_5_briefing(self):
        b=briefing(self.s,self.ctx)
        self.assertEqual([c['tool'] for c in b['calls']],['get_ranking','get_case_summary','get_route',*['get_peak_events']*3,'get_tactic_rules'])
        for f in b['facts']:
            row=f['evidence']['row'];encoded=json.dumps(b['calls'][f['evidence']['call']]['data'],sort_keys=True)
            self.assertIn(json.dumps(row,sort_keys=True),encoded)
        self.assertIn('초안',b['text']);self.assertTrue(b['facts'])
    def test_display_labels_and_zero_tooltips(self):
        from lite_ai_briefing import facts_for
        value=briefing(self.s,self.ctx)
        self.assertNotIn('CAD_',value['text'])
        self.assertIn('3F R3 · 계측기보관실',value['text'])
        self.assertIn('1F D3',value['text'])
        for index,tip in [(0,'지수 0: 평가됨'),(None,'미평가: 저장된 지수 없음'),(22,'평가된 지수')]:
            row={'room':'CAD_3F_R3','label':'3F R3','end_m':94,'phenomenon':'FO','index':index}
            call={'tool':'get_route','data':{'route':{'entry':'CAD_1F_D3','target':'CAD_3F_R3','length':94,'hoses':7,'stairs':2},'risk':{'rows':[row]}}}
            fact=facts_for(call,0)[1]
            self.assertTrue(fact['text'].endswith('— 22' if index==22 else '—'))
            self.assertEqual(fact['tooltip'],tip)
            self.assertEqual(fact['room'],'CAD_3F_R3')
            self.assertIs(fact['evidence']['row'],row)
        for tool in ['get_building','get_mc_summary']:
            call={'tool':tool,'data':{'room':'CAD_3F_R3','door':'CAD_1F_D3'}}
            fact=facts_for(call,0)[0]
            self.assertNotIn('CAD_',fact['text'])
            self.assertEqual(fact['evidence']['row']['door'],'CAD_1F_D3')

    def test_6_no_rule(self):
        v=self.invoke('분무 각도는?',[plan(missing=True)]);self.assertEqual(v['text'],'규칙표에 없음');self.assertEqual(v['facts'],[])
    def test_unknown_is_not_safe_and_predicates_same_frame(self):
        rules=self.s.get_tactic_rules({})['rules'];clear=next(r for r in rules if r['code']=='C-1');back=next(r for r in rules if r['code']=='B-1')
        self.assertFalse(matches(clear,{}));self.assertFalse(matches(back,{'backdraft':120}));self.assertTrue(matches(back,{'backdraft':120,'door_closed':True}))
    def test_model_fiction_rejected(self):
        with self.assertRaises(ValueError):self.invoke('test',['{"text":"R99 9999 ℃"}']*2)
        with self.assertRaises(ValueError):self.invoke('test',[plan(('propose_run',{'kind':'mc','origin':'CAD_3F_R999','samples':2}))])
    def test_report_explicit_save_only(self):
        b=briefing(self.s,self.ctx)
        with tempfile.TemporaryDirectory(dir=ROOT/'app/tests',prefix='d4-temp-') as tmp:
            source=self.s.cases(self.ctx['building'])['S09'];p=Path(tmp)/'playback.json';p.write_bytes(source.read_bytes())
            with patch.object(self.s,'cases',return_value={'S09':p}):
                self.assertFalse((p.parent/'assistant-reports').exists());save_report(self.s,b['briefing_id']);self.assertEqual(len(list_reports(self.s,self.ctx)),1)

if __name__=='__main__':unittest.main()
