"""D-5 read-only unit checks; optional released results via FIRELAPSE_D5_FIXTURES."""
import os, sys, json, math, unittest, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'), str(ROOT/'simulation'), str(ROOT/'simulation/deps')]
from lite_ai_tools import Tools, read
from d5_tools import windows, hose_segments, state_at

class SavedTools(Tools):
    def __init__(self, building, case, path, name):
        self.meta=dict(id=name,label=name,path=building,sha=hashlib.sha256(building.read_bytes()).hexdigest())
        self.path=path;self.case_id=case
    def building(self,key):
        if key not in (self.meta['id'],self.meta['sha']):raise ValueError('다른 건물')
        return self.meta,read(self.meta['path'])
    def cases(self,key):self.building(key);return {self.case_id:self.path}
    def case(self,a):
        if a['case']!=self.case_id:raise ValueError('다른 사례')
        if not hasattr(self,'_pb'):self._pb=read(self.path)
        return self._pb

def fixtures():
    root=Path(os.environ.get('FIRELAPSE_D5_FIXTURES',str(ROOT)))
    specs=[('hotel','data/parkmarine-hotel/building.json','simulation/results/lite_mc_jobs/models/parkmarine/mc-1793838045078030100-57e5a0b2/S08/playback.json','S08','CAD_5F_R16',('FO','BD')),
           ('intech','data/model-library/intech-cad/building.json','simulation/results/lite_mc_jobs/models/cad-aabf1346d0e54c94b45ad7d7db7137d4/mc-1793866167503118800-d936ebef/S04/playback.json','S04','CAD_1F_R3',('BD',)),
           ('wando','data/wando-coldstore/operating-building.json','data/wando-coldstore/P1-playback.json','wando-P1','CAD_1F_R5',('FGI','BD'))]
    for name,b,p,case,room,kinds in specs:
        if not (root/b).is_file() or not (root/p).is_file():continue
        service=SavedTools(root/b,case,root/p,name)
        yield name,service,dict(building=name,case=case,room=room,origin=room),kinds

class WindowsTests(unittest.TestCase):
    def timeline(self, values):
        return dict(room='R',aggregation='single',source_end_s=10*(len(values)-1),sampling='exact',
                    cells=[dict(cell='R',rows=[dict(time_s=i*10,indices={'FO':v,'FGI':v},rollover_active=None) for i,v in enumerate(values)])])
    def test_reentry_gap_and_end(self):
        out=windows(self.timeline([0,100,130,99,150,None,160,170]),'FO')
        self.assertEqual([(w['t_start'],w['t_end'],w['peak'],w['t_peak']) for w in out['windows']],[(10,30,130,20),(40,50,150,40),(60,None,170,70)])
        self.assertTrue(out['partial'])
    def test_missing_not_safe(self):
        self.assertFalse(windows(self.timeline([None,None]),'FO')['evaluated'])
        self.assertEqual(windows(self.timeline([100,120]),'rollover')['windows'],[])
    def test_cells_not_averaged(self):
        t=self.timeline([110,120]);t['cells']+=self.timeline([0,0])['cells'];t['aggregation']='none'
        self.assertEqual(windows(t,'FO')['windows'][0]['peak'],120)
    def test_bad_threshold(self):
        for value in (-1,True,float('nan')):
            with self.assertRaises(ValueError):windows(self.timeline([100]),'FO',value)
    def test_schedule_partial_and_right_value(self):
        o=dict(schedule=[[0,0],[1320,0],[1320,.5],[1800,1]])
        self.assertEqual([state_at(o,t) for t in (1310,1320,1800)],['closed','open','open'])
        self.assertEqual(state_at({},0),'unknown')
    def test_room_straddles_hose_boundary(self):
        r=dict(route=dict(length=36,entry='D0',segments=[dict(start=0,end=5,room=None),dict(start=5,end=36,room='R')],edges=[]))
        segments=hose_segments(r,dict(rooms=[dict(id='R',name='방')],openings=[dict(id='D0',state='closed')]))
        self.assertEqual(len(segments),3)
        self.assertEqual([(s['rooms'][-1]['enter_m'],s['rooms'][-1]['exit_m']) for s in segments],[(5,15),(15,30),(30,36)])
        self.assertEqual(segments[0]['doors'],[dict(id='D0',state='closed')])
    def test_saved_windows_include_peak_and_hoses_match(self):
        rows=list(fixtures())
        if len(rows)<3:self.skipTest('set FIRELAPSE_D5_FIXTURES to the released app containing three saved cases')
        for name,s,a,kinds in rows:
            for kind in kinds:
                with self.subTest(name=name,kind=kind):
                    out=s.get_index_windows({**a,'phenomenon':kind})
                    event=next(e for e in s.get_peak_events({**a,'phenomenon':'backdraft' if kind=='BD' else kind}) if e['room']==a['room'])
                    self.assertTrue(out['evaluated'])
                    if event['peak']>=100:
                        self.assertTrue(any(w['t_start']<=event['peak_s'] and (w['t_end'] is None or event['peak_s']<w['t_end']) for w in out['windows']))
                    else:self.assertEqual(out['windows'],[])
            route=s.get_route(a)
            self.assertFalse(route['route'].get('error'))
            self.assertEqual(len(route['hose_segments']),math.ceil(route['route']['length']/15))
            self.assertEqual(len(route['hose_segments']),route['route']['hoses'])

if __name__=='__main__':unittest.main()
