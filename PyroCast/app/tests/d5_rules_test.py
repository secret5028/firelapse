import sys,unittest,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from d5_match import matches,match_timelines
RULES=json.loads((ROOT/'config/tactic_rules.json').read_text('utf8'))

class RulesTests(unittest.TestCase):
    def rule(self,code):return next(r for r in RULES['rules'] if r['code']==code)
    def test_threshold_boundaries_and_scope(self):
        r=self.rule('G-1')
        self.assertTrue(matches(r,dict(route_room=True,FGI=70,temperature_rising=True)))
        for v in (dict(FGI=80,temperature_rising=True),dict(route_room=True,FGI=100,temperature_rising=True),dict(route_room=True,FGI=80)):
            self.assertFalse(matches(r,v))
        self.assertFalse(matches(self.rule('B-1'),dict(backdraft=120,door_closed=True)))
        self.assertTrue(matches(self.rule('B-1'),dict(backdraft=120,door_closed=True,fire_room=True)))
    def test_missing_not_clear_or_cavity(self):
        self.assertFalse(matches(self.rule('C-1'),{}))
        self.assertFalse(matches(self.rule('C-1'),dict(FO=0,FGI=0)))
        self.assertTrue(matches(self.rule('C-1'),dict(FO=0,FGI=0,backdraft=0)))
        self.assertFalse(matches(self.rule('X-1'),dict(FGI=90)))
        self.assertTrue(matches(self.rule('X-1'),dict(FGI=90,cavity=True)))
        self.assertFalse(matches(self.rule('S-1'),dict(Tu=800,external_water=True)))
    def test_or_and_adjacency(self):
        self.assertTrue(matches(self.rule('O-1'),dict(Tu=600)))
        self.assertFalse(matches(self.rule('E-3'),dict(route_room=True,after_origin_FO=True)))
        self.assertFalse(matches(self.rule('E-2'),dict(FGI=100)))
    def test_opening_windows_split_and_no_independent_peaks(self):
        frames=[dict(time_s=t,Tu=200,h=2,indices=dict(FO=0,FGI=0,backdraft=120),rollover_active=False) for t in (0,10,20,30)]
        timeline={'R':dict(cells=[dict(cell='R',rows=frames)])}
        building=dict(rooms=[dict(id='R')],openings=[dict(id='D',kind='door',sides=['R','OUTSIDE'],schedule=[[0,0],[20,.5]])])
        route=dict(hose_segments=[dict(rooms=[dict(id='R')])])
        rows=match_timelines(timeline,building,route,RULES,'R')
        self.assertEqual([(r['code'],r['t_start'],r['t_end']) for r in rows if r['code'] in ('B-1','B-3')],[('B-1',0,20),('B-3',20,None)])
        # BD peak while closed, then FGI peak after it falls: no E-2 at FGI time.
        frames[2]['indices']=dict(FO=0,FGI=120,backdraft=0)
        rows=match_timelines(timeline,building,route,RULES,'R')
        self.assertFalse(any(r['code']=='B-1' and r['t_start']>=20 for r in rows))
    def test_approved_rule_set_and_no_extra_units(self):
        self.assertEqual(len(RULES['rules']),17)
        self.assertEqual(RULES['notice'],'참고이며 현장 지휘관 판단 우선')
        for r in RULES['rules']:
            self.assertTrue(r['ref']['doc'])
            for word in ('lpm','초간','mm'):self.assertNotIn(word,r['text'])

if __name__=='__main__':unittest.main()
