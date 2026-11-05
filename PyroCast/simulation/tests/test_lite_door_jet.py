import json,unittest
from pathlib import Path
import numpy as np
from pyrocast_lite.adapter import prepare
from pyrocast_lite.door_jet import react
from pyrocast_lite.core import P0,RG,H_O2
from pyrocast_lite.numerics import upper_reaction

class DoorJetTests(unittest.TestCase):
    def model(self,on):
        raw=json.loads((Path(__file__).resolve().parents[2]/'fixtures/room_rule_benchmark_3room_b3.json').read_text('utf-8'))
        return prepare(raw,{'door_jet_enabled':on,'upper_combustion_enabled':False})[0]
    def test_shared_budget_stoichiometry_and_zero_limits(self):
        p=self.model(True).P
        fu=np.array([.4,.4]);fl=np.array([.1,.1]);to=np.zeros(2,int)
        r=react(fu,fl,np.ones(2)*900,to,np.ones(2,bool),np.array([10.]),np.array([.2]),np.array([.05]),p)
        self.assertAlmostEqual(sum(r['oxygen_kg_s']),.15)
        np.testing.assert_allclose(r['heat_W'],r['reaction_kg_s']*p['dHc'])
        np.testing.assert_allclose(r['heat_W'],r['oxygen_kg_s']*H_O2)
        np.testing.assert_allclose(r['burn_into_upper_kg_s']+r['burn_into_lower_kg_s'],r['reaction_kg_s'])
        self.assertTrue(np.all(r['reaction_kg_s']<=fu+fl))
        for oxygen,temperature,enabled in [(0,900,True),(.2,p['T_in']+200,True),(.2,900,False)]:
            z=react(fu,fl,np.ones(2)*temperature,to,np.ones(2,bool)*enabled,np.array([10.]),np.array([oxygen]),np.array([0.]),p)
            np.testing.assert_array_equal(z['reaction_kg_s'],0.)
    def test_rhs_no_duplicate_mass_heat_fuel_oxygen(self):
        a=self.model(True);b=self.model(False);n=a.N
        for m in (a,b):m.pending.clear();m.activation.clear()
        y=a.y0();y[n:2*n]=a.Va/2;y[2*n:3*n]=350.;y[2*n]=900.
        y[4*n:5*n]=0.;y[5*n:6*n]=.23;y[6*n:8*n]=0.;y[6*n]=.1
        y[0]+=30.
        da=a.rhs(10,y,True);db=b.rhs(10,y,True);diff=a.rhs(10,y)-b.rhs(10,y)
        self.assertGreater(sum(da['door_jet_HRR_W']),0)
        mu=P0/(RG*y[2*n:3*n])*y[n:2*n];ml=P0/(RG*y[3*n:4*n])*(a.Va-y[n:2*n])
        np.testing.assert_allclose(diff[5*n:6*n]*ml,-da['door_jet_room_oxygen_kg_s'],atol=1e-12)
        self.assertAlmostEqual(sum(diff[6*n:7*n]*mu+diff[7*n:8*n]*ml),-sum(da['door_jet_reaction_kg_s']),places=10)
        self.assertAlmostEqual(da['heat_rate']-db['heat_rate'],sum(da['door_jet_HRR_W']),places=6)
        self.assertEqual(da['mass_rate'],db['mass_rate']);self.assertEqual(da['Qp'],db['Qp'])
        np.testing.assert_array_equal(da['room_Q'],db['room_Q'])
    def test_upper_fuel_reservation(self):
        p=self.model(True).P;p['gas_ignition_C']=520.
        args=(np.array([10.]),np.array([.1]),np.array([.23]),np.array([1000.]),np.array([0.]),p)
        normal=upper_reaction(*args)[0]
        reserved=upper_reaction(*args,reserved_fuel_rate=np.array([.05]))[0]
        self.assertGreater(normal[0],0);self.assertEqual(reserved[0],0)
    def test_off_default_and_nonphysical_vent_exclusion(self):
        a=self.model(False);p=a.P.copy();p.pop('door_jet_enabled')
        raw=json.loads((Path(__file__).resolve().parents[2]/'fixtures/room_rule_benchmark_3room_b3.json').read_text('utf-8'))
        b=prepare(raw,{'upper_combustion_enabled':False,'door_jet_enabled':False})[0]
        np.testing.assert_array_equal(a.rhs(50,a.y0()),b.rhs(50,b.y0()))
        self.assertTrue(prepare(raw)[0].P['door_jet_enabled'])
        for k,v in enumerate(a.vents):
            if v[1]==a.N:self.assertFalse(a.door_jet_eligible[k])

    def test_room_oxygen_mode_rejected(self):
        raw=json.loads((Path(__file__).resolve().parents[2]/'fixtures/room_rule_benchmark_3room_b3.json').read_text('utf-8'))
        with self.assertRaisesRegex(ValueError,'Room oxygen inventory mode has been removed'):
            prepare(raw,{'oxygen_inventory_mode':True,'door_jet_enabled':True})

    def test_virtual_cell_boundaries_excluded(self):
        root=Path(__file__).resolve().parents[2]
        raw=json.loads((root/'simulation/results/room_rule_r8_20261025/source-scenario.json').read_text('utf-8'))
        m,_=prepare(raw,{'door_jet_enabled':True})
        virtual={v['id'] for v in m.input_model['openings'] if v.get('virtual_cell_boundary')}
        self.assertTrue(virtual)
        for k,v in enumerate(m.vents):
            if v[5] in virtual:self.assertFalse(m.door_jet_eligible[k])

if __name__=='__main__':unittest.main()
