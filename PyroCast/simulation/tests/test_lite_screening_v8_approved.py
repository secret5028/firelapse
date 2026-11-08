import json,unittest
from pathlib import Path
import numpy as np
from pyrocast_lite.screening_v8_approved import prepare_inputs,origin_budgets,score,scenario
from pyrocast_lite.adapter import prepare
from pyrocast_cfbt.deck import fire_curve

ROOT=Path(__file__).resolve().parents[2]
class ApprovedInputsTests(unittest.TestCase):
    def raw(self):return json.loads((ROOT/'simulation/results/room_rule_r8_20261025/source-scenario.json').read_text('utf-8'))
    def test_approved_values_no_mutation(self):
        raw=self.raw();before=json.dumps(raw,sort_keys=True);m=prepare_inputs(raw);u=m['approved_input']['room_uses']
        self.assertEqual((u['CAD_3F_R2']['load_MJ_m2'],u['CAD_3F_R2']['hrrpua_kW_m2']),(1800,250))
        self.assertEqual((u['CAD_3F_R3']['load_MJ_m2'],u['CAD_3F_R3']['hrrpua_kW_m2']),(1180,500))
        self.assertEqual(u['CAD_3F_R23']['load_MJ_m2'],285)
        for rid in ('R11','R16','R17','R24'):
            x=u['CAD_3F_'+rid];self.assertEqual(x['load_MJ_m2'],40);self.assertTrue(x['passage_without_fire'])
        self.assertEqual(before,json.dumps(raw,sort_keys=True))
    def test_caps_and_peak_independence(self):
        raw=self.raw();s=score(raw,5);b=s['origin_budgets'];a=b['CAD_3F_R8']
        self.assertAlmostEqual(a['ventilation_cap_kW'],750*a['internal_max_A_sqrtH'])
        self.assertAlmostEqual(b['CAD_3F_R1']['Q_origin_peak_kW'],76071.03259454285)
        self.assertAlmostEqual(b['CAD_3F_R2']['Q_origin_peak_kW'],40634.225)
        for g in raw['fuel_groups']:g['peak_kW']=123456.
        s2=score(raw,5)
        self.assertEqual([(r['room'],r['score']) for r in s['ranked']],[(r['room'],r['score']) for r in s2['ranked']])
    def test_exclusion_guards(self):
        raw=self.raw();s=score(raw,5);self.assertEqual(s['eligible_count'],17)
        self.assertEqual(len(s['approved_input']['graph_exclusions']),2)
        for rid in ('R11','R16','R17','R24','R14','R28'):
            self.assertNotIn('CAD_3F_'+rid,{r['room'] for r in s['ranked']})
        raw['openings'][0]['b']='CAD_3F_R14'
        with self.assertRaisesRegex(ValueError,'geometry changed'):prepare_inputs(raw)
        raw=self.raw();raw['cad']['building_sha256']='different'
        with self.assertRaisesRegex(ValueError,'different building'):prepare_inputs(raw)
    def test_prepared_graph_and_source_energy(self):
        s=score(self.raw(),5);d=scenario(s,'CAD_3F_R1','open_except_confirmed');m,manifest=prepare(d)
        g=next(g for g in d['fuel_groups'] if g['room']=='CAD_3F_R1');t,q,_=fire_curve(g,s['origin_budgets']['CAD_3F_R1']['area_m2'])
        self.assertAlmostEqual(np.trapezoid(q,t)/1000,g['energy_MJ'],places=5)
        self.assertEqual(g['growth_kW_s2'],s['origin_budgets']['CAD_3F_R1']['growth_kW_s2'])
        nodes={r['id'] for r in m.input_model['rooms']};fires={g['room'] for g in m.input_model['fuel_groups']}
        for rid in ('R11','R16','R17','R24'):
            self.assertIn('CAD_3F_'+rid,nodes);self.assertNotIn('CAD_3F_'+rid,fires)
        for rid in ('R14','R28'):
            self.assertNotIn('CAD_3F_'+rid,nodes);self.assertNotIn('CAD_3F_'+rid,json.dumps(manifest['graph']))

if __name__=='__main__':unittest.main()
