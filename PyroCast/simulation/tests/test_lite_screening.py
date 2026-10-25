import json,unittest
from pathlib import Path
from pyrocast_lite.screening import score,scenario,settings,representative_openings,rank_simulations,validate_n

class ScreeningTests(unittest.TestCase):
    def raw(self):
        raw=json.loads((Path(__file__).resolve().parents[2]/'fixtures/room_rule_benchmark_3room_b3.json').read_text('utf-8'))
        for v in raw['openings']:v['kind']='window' if 'OUTSIDE' in (v['a'],v['b']) else 'door'
        return raw
    def test_n_limits_and_original_source_not_mutated(self):
        raw=self.raw();before=json.dumps(raw,sort_keys=True);s=score(raw,2)
        self.assertEqual(len([r for r in s['ranked'] if r['selected']]),2)
        for value in (0,4,True,1.5):
            with self.assertRaises(ValueError):validate_n(value,3)
        new=scenario(s,'R3')
        self.assertEqual([g['room'] for g in new['fuel_groups'] if 'initial_time_s' in g],['R3'])
        self.assertEqual(json.dumps(raw,sort_keys=True),before)
        self.assertEqual([g['energy_MJ'] for g in raw['fuel_groups']],[g['energy_MJ'] for g in new['fuel_groups']])
    def test_digital_probability_and_fixed_states(self):
        raw=self.raw();s=score(raw,2)
        for v in s['opening_states']:
            if v['class']=='ordinary_door':self.assertTrue(v['open'])
            if v['class']=='operable_window':self.assertFalse(v['open'])
        window=next(v['id'] for v in s['opening_states'] if v['class']=='operable_window')
        c=settings({'fixed_states':{window:True}});_,rows,_=representative_openings(raw,c)
        self.assertEqual(next(v['effective_fraction'] for v in rows if v['id']==window),.5)
    def test_normalized_directions_and_constant_factor(self):
        s=score(self.raw(),3)
        for row in s['ranked']:
            self.assertTrue(all(0<=x<=1 for x in row['normalized'].values()))
            for k,bounds in s['factor_ranges'].items():
                if bounds['max']==bounds['min']:self.assertEqual(row['normalized'][k],0.)
        for key in ('ventilation_restriction','fire_isolation'):
            pairs=sorted(s['ranked'],key=lambda r:r['raw'][key])
            self.assertGreaterEqual(pairs[0]['normalized'][key],pairs[-1]['normalized'][key])
    def test_user_ranking_priority_ties_and_incomplete(self):
        def r(room,burn,smoke,fo,ok=True):return dict(room=room,burning_room_count=burn,smoke_risk_room_count=smoke,first_FO_s=fo,complete=ok)
        result=rank_simulations([r('A',2,10,10),r('B',3,1,100),r('C',3,1,100),r('D',99,99,1,False)])
        self.assertEqual([x['room'] for x in result],['B','C','A','D'])
        self.assertEqual([x['rank2'] for x in result],[1,1,3,None])

if __name__=='__main__':unittest.main()
