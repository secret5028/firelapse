"""Saved S09/Wando reads only; no engine, network API, or result writes."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from lite_ai_tools import Tools,TYPES

class ReadTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.t=Tools()
    def test_real_series_and_peaks(self):
        for building,case in [('cad-main','S09'),('wando-coldstore','wando-P1')]:
            a={'building':building,'case':case};p=self.t.case(a)
            for typ in TYPES:
                events=self.t.get_peak_events({**a,'phenomenon':typ,'threshold':100})
                self.assertTrue(events)
                for e in events:
                    c=next(c for c in p['rooms'] if c['key']==e['source_cell']) if e['source_cell'] else None
                    if c:
                        i=p['time_s'].index(e['peak_s']);expected=p['solvers'][c['solver_id']]['conditions'][typ]['scores']['degree'][i]*100
                        self.assertEqual(e['peak'],expected)
            c=p['rooms'][0];timeline=self.t.get_room_timeline({**a,'room':c['key'],'t0':0,'t1':20})
            self.assertEqual(timeline['cells'][0]['rows'][1]['Tu'],p['solvers'][c['solver_id']]['Tu'][p['time_s'].index(10)])
    def test_cross_building_and_paths_rejected(self):
        for case in ['S09','../S09']:
            with self.assertRaises(ValueError):self.t.case({'building':'wando-coldstore','case':case})
        with self.assertRaises(ValueError):self.t.propose_openings({'building':'cad-main','openings':[{'id':'fiction','open':True}]})
    def test_routes(self):
        for b,c in [('cad-main','S09'),('wando-coldstore','wando-P1')]:
            r=self.t.get_route({'building':b,'case':c,'time_s':1420})
            self.assertNotIn('error',r['route']);self.assertGreater(r['route']['length'],0);self.assertTrue(r['risk']['rows'])
    def test_proposal_no_execution(self):
        p=self.t.propose_run({'building':'cad-main','kind':'mc','origin':'CAD_3F_R3','samples':2})
        self.assertFalse(p['started']);self.assertTrue(p['requires_user_apply'])
    def test_three_indices_and_subsidiary_rule(self):
        from lite_ai_briefing import matches
        self.assertEqual(TYPES,('FO','FGI','backdraft'))
        rule=next(r for r in self.t.get_tactic_rules({})['rules'] if r['code']=='R-1')
        self.assertTrue(matches(rule,{'FGI':100,'rollover_active':True}))
        for values in ({'FGI':99,'rollover_active':True},{'FGI':150,'rollover_active':False},{'FGI':150}):
            self.assertFalse(matches(rule,values))
        events=self.t.get_peak_events({'building':'wando-coldstore','case':'wando-P1','phenomenon':'FGI','threshold':100})
        r5=next(e for e in events if e['room']=='CAD_1F_R5')
        self.assertEqual(r5['rollover_first_s'],2120)
        with self.assertRaises(ValueError):
            self.t.get_peak_events({'building':'cad-main','case':'S09','phenomenon':'rollover','threshold':100})

if __name__=='__main__':unittest.main()
