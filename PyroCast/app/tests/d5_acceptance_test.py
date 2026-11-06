import sys,unittest,json,os
from unittest.mock import patch
from d5_tools_test import fixtures,ROOT
from lite_ai_briefing import briefing
from d5_audit import audit
from d5_polish import polish

class Acceptance(unittest.TestCase):
    def test_three_saved_numeric_and_rule_audit(self):
        rows=list(fixtures())
        if len(rows)<3:self.skipTest('released fixtures unavailable')
        reports={}
        for name,s,a,_ in rows:
            with patch('lite_ai_fuel.settings',return_value=None):
                value=briefing(s,{**a,'time_s':2770 if name=='hotel' else 1800})
            check=audit(value);reports[name]=check
            self.assertEqual(check['numeric_mismatches'],[],name)
            self.assertEqual(check['rule_mismatches'],[],name)
            self.assertEqual(check['forbidden_units'],[],name)
            self.assertTrue(check['hose_count_matches'],name)
            self.assertEqual(value['polishing'],'offline deterministic')
        print(json.dumps(reports,ensure_ascii=False))
    def test_provider_cannot_add_or_change_advice_numbers_names(self):
        original=dict(sections=[dict(title='■ 1. 화재 위험 요약',text='R16 FO 115 @46:10 · [O-1] 진입 보류')],polishing='offline deterministic')
        with patch('lite_ai_fuel.settings',return_value={'api_key_env':'D5_TEST_KEY'}),patch.dict(os.environ,{'D5_TEST_KEY':'test-only'}):
            for replacement in ('R99 FO 999 @46:10 · [O-1] 진입 보류','R16 FO 115 @46:10 · [O-1] 진입 가능','R16 FO 115 @46:10 · [O-1] 진입 보류 · 송풍기 가동'):
                value=json.loads(json.dumps(original))
                polish(value,lambda *a:json.dumps(dict(sections=[dict(title=original['sections'][0]['title'],text=replacement)])))
                self.assertEqual(value['sections'],original['sections']);self.assertIn('fallback',value['polishing'])
            value=json.loads(json.dumps(original));polish(value,lambda *a:json.dumps(dict(sections=value['sections'])))
            self.assertEqual(value['polishing'],'verified unchanged claims')
    def test_no_key_never_calls_provider(self):
        with patch('lite_ai_fuel.settings',return_value=None):
            value=polish({'sections':[]},lambda *a:self.fail('provider called without key'))
            self.assertEqual(value,{'sections':[]})

if __name__=='__main__':unittest.main()
