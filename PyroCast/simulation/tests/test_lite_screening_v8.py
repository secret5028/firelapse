import json,unittest
from pathlib import Path
import numpy as np
from pyrocast_lite.screening_v8 import score,scenario,origin_budgets,compare_pairs
from pyrocast_cfbt.deck import fire_curve
from pyrocast_lite.adapter import prepare

ROOT=Path(__file__).resolve().parents[2]
class ScreeningV8Tests(unittest.TestCase):
    def raw(self):return json.loads((ROOT/'simulation/results/room_rule_r8_20261025/source-scenario.json').read_text('utf-8'))
    def test_input_peak_independence_and_preservation(self):
        raw=self.raw();before=json.dumps(raw,sort_keys=True);s=score(raw,5)
        for g in raw['fuel_groups']:g['peak_kW']=1234567.
        other=score(raw,5)
        self.assertEqual([(r['room'],r['score']) for r in s['ranked']],[(r['room'],r['score']) for r in other['ranked']])
        for state in ('closed','open_except_confirmed'):
            for source in (s,other):
                d=scenario(source,'CAD_3F_R1',state);g=next(g for g in d['fuel_groups'] if g['room']=='CAD_3F_R1')
                self.assertAlmostEqual(g['peak_kW'],s['origin_budgets']['CAD_3F_R1']['Q_origin_peak_kW'])
                t,q,_=fire_curve(g,s['origin_budgets']['CAD_3F_R1']['area_m2'])
                self.assertAlmostEqual(np.trapezoid(q,t)/1000,g['energy_MJ'],places=6)
                self.assertAlmostEqual(q[1]/t[1]**2,.047)
        self.assertEqual(json.dumps(self.raw(),sort_keys=True),before)
    def test_formula_and_no_internal_fallback(self):
        raw=self.raw();b=origin_budgets(raw)
        self.assertAlmostEqual(b['CAD_3F_R1']['Q_origin_peak_kW'],1500*b['CAD_3F_R1']['external_A_sqrtH'])
        self.assertAlmostEqual(b['CAD_3F_R2']['Q_origin_peak_kW'],.5*b['CAD_3F_R2']['area_m2']*400)
        self.assertEqual(b['CAD_3F_R6']['Q_origin_peak_kW'],0)
        with self.assertRaisesRegex(ValueError,'Zero fuel'):scenario(score(raw,5),'CAD_3F_R6','closed')
    def test_source_cell_budget_and_other_rooms_unchanged(self):
        raw=self.raw();s=score(raw,5);d=scenario(s,'CAD_3F_R1','open_except_confirmed')
        original={g['id']:g for g in raw['fuel_groups']}
        for g in d['fuel_groups']:
            if g['room']!='CAD_3F_R1':self.assertEqual(g['peak_kW'],original[g['id']]['peak_kW'])
        m,manifest=prepare(d)
        gs=[g for g in m.input_model['fuel_groups'] if g.get('original_room')=='CAD_3F_R1' or g['room'].startswith('CAD_3F_R1_C')]
        self.assertGreater(len(gs),1)
        self.assertAlmostEqual(sum(g['energy_MJ'] for g in gs),s['origin_budgets']['CAD_3F_R1']['energy_MJ'],places=5)
        initial=next(g for g in gs if 'initial_time_s' in g)
        t,q,_=fire_curve(initial,1e6)
        share=initial['energy_MJ']/s['origin_budgets']['CAD_3F_R1']['energy_MJ']
        self.assertAlmostEqual(max(q),s['origin_budgets']['CAD_3F_R1']['Q_origin_peak_kW']*share,places=5)
    def test_five_keys_and_partial_pairs(self):
        def pair(r,c,temp,ok=True):
            return [dict(room=r,name=r,rank1=1,score=1,state=state,complete=(ok or state=='open_except_confirmed'),
                burning_room_count=1,smoke_risk_room_count=0,smoke_caution_room_count=c,first_FO_s=None,
                origin_max_upper_C=temp+(10 if state=='closed' else 0)) for state in ('closed','open_except_confirmed')]
        rows=compare_pairs(pair('A',2,900)+pair('B',3,400)+pair('C',3,500)+pair('D',99,1000,False))
        self.assertEqual([r['room'] for r in rows],['C','B','A','D'])
        self.assertEqual(rows[0]['worst_state'],'closed');self.assertIsNone(rows[-1]['rank2'])

if __name__=='__main__':unittest.main()

