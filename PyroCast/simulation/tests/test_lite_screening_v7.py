import json,math,unittest
from pathlib import Path
from pyrocast_lite.screening_v7 import score,scenario,compare_pairs,opening_state,settings
from pyrocast_lite.adapter import prepare

class ScreeningV7Tests(unittest.TestCase):
    def raw(self):
        raw=json.loads((Path(__file__).resolve().parents[2]/'fixtures/room_rule_benchmark_3room_b3.json').read_text('utf-8'))
        for v in raw['openings']:v['kind']='window' if 'OUTSIDE' in (v['a'],v['b']) else 'door'
        return raw
    def test_log_clip_and_direct_factors(self):
        raw=self.raw();raw['fuel_groups'][0]['energy_MJ']=1e6;raw['fuel_groups'][0]['peak_kW']=1e8
        s=score(raw,3);r=next(r for r in s['ranked'] if r['room']=='R1')
        self.assertEqual(r['raw']['fuel'],6)
        self.assertGreater(r['raw']['ventilation_restriction'],3)
        self.assertEqual(r['normalization_input']['ventilation_restriction'],3)
        self.assertEqual(r['normalized']['fire_isolation'],1)
        self.assertEqual(r['normalized']['passage_adjacency'],r['raw']['passage_adjacency'])
    def test_confirmed_blocks_inferred_passes_and_graph(self):
        raw=self.raw();raw['rooms'][0]['name']='T.P.S'
        s=score(raw,3)
        r=next(r for r in s['ranked'] if r['room']=='R1')
        self.assertIn('R2',r['reachable_rooms']);self.assertEqual(r['raw']['fire_isolation'],.5)
        data=scenario(s,'R1','open_except_confirmed');_,manifest=prepare(data)
        self.assertTrue(any(e['opening']=='D12' for e in manifest['graph']['edges']))
        raw['openings'][0]['block_name']='FD-90';s=score(raw,3)
        r=next(r for r in s['ranked'] if r['room']=='R1');self.assertNotIn('R2',r['reachable_rooms'])
    def test_extremes_and_source_preservation(self):
        raw=self.raw();before=json.dumps(raw,sort_keys=True);s=score(raw,3)
        for state in ('open_except_confirmed','closed'):
            data=scenario(s,'R3',state)
            self.assertEqual([g['room'] for g in data['fuel_groups'] if 'initial_time_s' in g],['R3'])
            for v in data['openings']:
                self.assertEqual(v['schedule'][0][1],0 if state=='closed' else .5 if v['kind']=='window' else 1.)
        self.assertEqual(json.dumps(raw,sort_keys=True),before)
        raw['openings'][0]['kind']='open_passage'
        raw['openings'][-1]['fixed_window']=True
        data,_=opening_state(raw,'closed');self.assertEqual(data['openings'][0]['schedule'][0][1],1)
        data,_=opening_state(raw,'open_except_confirmed');self.assertEqual(data['openings'][-1]['schedule'][0][1],0)
    def test_pairs_compare_whole_scenario_not_mixed_metrics(self):
        def row(r,state,b,s,fo,ok=True):return dict(room=r,name=r,rank1=1,score=2,state=state,complete=ok,burning_room_count=b,smoke_risk_room_count=s,first_FO_s=fo)
        rows=[row('A','open_except_confirmed',3,1,400),row('A','closed',1,9,10),row('B','open_except_confirmed',20,30,1),row('B','closed',1,1,20,False)]
        result=compare_pairs(rows)
        self.assertEqual(result[0]['worst_state'],'open_except_confirmed');self.assertEqual(result[0]['smoke_risk_room_count'],1)
        self.assertIsNone(result[1]['rank2']);self.assertFalse(result[1]['complete'])

if __name__=='__main__':unittest.main()
