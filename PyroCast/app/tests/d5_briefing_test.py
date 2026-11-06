import sys,unittest,tempfile,json,hashlib,os
from pathlib import Path
from unittest.mock import patch
from d5_tools_test import fixtures,ROOT
from lite_ai_briefing import briefing,save_report,list_reports

class BriefingTests(unittest.TestCase):
    def test_saved_three_templates_and_rule_evidence(self):
        cases=list(fixtures())
        if len(cases)<3:self.skipTest('released fixtures unavailable; set FIRELAPSE_D5_FIXTURES')
        for name,s,a,k in cases:
            with self.subTest(name=name):
                before=hashlib.sha256(s.path.read_bytes()).hexdigest()
                result=briefing(s,{**a,'time_s':2770 if name=='hotel' else 1800})
                self.assertEqual(len(result['sections']),4)
                self.assertEqual([r['tool'] for r in result['calls'][:2]],['get_case_summary','get_route'])
                self.assertIn('수관 구간별 할 일',result['text'])
                self.assertIn('발생 확정 아님',result['text'])
                self.assertEqual(set(result['rules']),{r['code'] for r in result['rendered_rules']})
                actual={r['code']:r for r in s.get_tactic_rules(a)['rules']}
                for r in result['rendered_rules']:
                    self.assertEqual(r['text'],actual[r['code']]['text'])
                    self.assertIn(r['text']+' · '+r['notice'],result['text'])
                for unit in ('lpm','초간',' mm'):self.assertNotIn(unit,result['text'])
                self.assertEqual(before,hashlib.sha256(s.path.read_bytes()).hexdigest())
                if name=='wando':
                    self.assertNotIn('X-1',result['rules'])
                    transitions=[(r['code'],r['t_start'],r['t_end']) for r in result['matching_log'] if r['door_id']=='CAD_1F_CUT' and r['code'] in ('B-1','B-3')]
                    self.assertIn(('B-1',540,1320),transitions)
                    self.assertIn(('B-3',1320,2250),transitions)
    def test_explicit_report_save_and_offline_payload(self):
        case=next(fixtures(),None)
        if case is None:self.skipTest('saved fixture unavailable')
        _,s,a,_=case;v=briefing(s,a)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'playback.json';p.write_bytes(s.path.read_bytes())
            with patch.object(s,'cases',return_value={a['case']:p}):
                self.assertFalse((p.parent/'assistant-reports').exists())
                save_report(s,v['briefing_id'])
                report=list_reports(s,a)[0]
                self.assertEqual(report['markdown'],v['text'])
                from lite_export import packed
                import base64,gzip
                blob=packed(dict(assistant_reports=[report]))
                decoded=json.loads(gzip.decompress(base64.b64decode(blob)))
                self.assertEqual(decoded['assistant_reports'][0]['markdown'],v['text'])

if __name__=='__main__':unittest.main()
