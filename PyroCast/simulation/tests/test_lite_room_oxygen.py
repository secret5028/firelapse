import json,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from pyrocast_lite.adapter import prepare
from pyrocast_lite.core import H_O2

@unittest.skip('retired mode: oxygen_inventory_mode / rollover sample key / visualization.states — 2026-10 이후 폐기')
class RoomOxygenTests(unittest.TestCase):
    def model(self,upper=False):
        raw=json.loads((Path(__file__).resolve().parents[2]/'fixtures/room_rule_benchmark_3room_b3.json').read_text('utf-8'))
        return prepare(raw,{'oxygen_inventory_mode':True,'smooth_state_bounds':True,'upper_combustion_enabled':upper})[0]
    def test_one_stock_per_room_and_initial_proxy(self):
        m=self.model();n=m.N;y=m.y0()
        self.assertEqual(len(y),10*n+1)
        np.testing.assert_allclose(m.oxygen_indicator(y),.23)
        self.assertEqual(m.sparsity().shape,(len(y),len(y)))
        self.assertEqual(len(m.integration_atol()),len(y))
        np.testing.assert_array_equal(m.compact(m.expand(y)),y)
    def test_linear_oxygen_cap_no_lol_and_no_negative_stock_reset(self):
        m=self.model();y=m.y0();n=m.N;y[4*n:5*n]=.3
        with patch('pyrocast_lite.core.oxygen_factor',side_effect=AssertionError('LOL must not run')):
            d=m.rhs(300,y,True)
        self.assertAlmostEqual(d['room_Q'][0],H_O2*.3/10)
        self.assertAlmostEqual(d['primary_room_oxygen_kg_s'][0],.03)
        y[4*n:5*n]=0.;d=m.rhs(300,y,True)
        self.assertEqual(d['room_Q'].sum(),0.)
    def test_internal_transport_conserves_oxygen_no_fresh_air_reset(self):
        m=self.model();m.activation.clear();m.pending.clear()
        m.vp0[m.vj==m.N]=0.;m.vl[:]=0
        y=m.y0();n=m.N;y[0]+=30
        y[4*n:5*n]*=np.array([.1,.6,1.])
        d=m.rhs(0,y,True)
        self.assertAlmostEqual(sum(d['room_oxygen_rate_kg_s']),0.,places=10)
        self.assertLess(d['room_oxygen_rate_kg_s'][0],0)
    def test_primary_and_upper_share_one_budget_and_fuel_heat_balance(self):
        m=self.model(True);n=m.N;y=m.y0();y[n:2*n]=m.Va/2;y[2*n:3*n]=1000.
        y[4*n:5*n]=1.;y[5*n:6*n]=.1 # compact upper fuel block
        with patch('pyrocast_lite.core.oxygen_factor',side_effect=AssertionError('LOL must not run')):
            d=m.rhs(300,y,True)
        used=d['primary_room_oxygen_kg_s']+d['upper_oxygen_consumption_kg_s']
        self.assertTrue(np.all(used<=.1+1e-12))
        np.testing.assert_allclose(d['upper_HRR_W'],d['upper_oxygen_consumption_kg_s']*H_O2)
        np.testing.assert_allclose(d['upper_HRR_W'],d['upper_reaction_kg_s']*m.P['dHc'])
        self.assertEqual(d['upper_HRR_W'][0],0.)
        self.assertGreater(d['upper_HRR_W'][1],0.)
    def test_stage_constants_not_silently_overridden(self):
        m=self.model()
        with self.assertRaises(ValueError):prepare(m.input_model,{'oxygen_inventory_mode':True,'oxygen_inventory_tau_s':1.})

if __name__=='__main__':unittest.main()
