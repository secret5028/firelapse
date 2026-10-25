import json,unittest
from pathlib import Path
import numpy as np
from pyrocast_lite.adapter import prepare
from pyrocast_lite.numerics import lower,bounded,upper_reaction
from pyrocast_lite.core import H_O2,P0,RG,CP

class L1eTests(unittest.TestCase):
    def model(self,enabled=True):
        raw=json.loads((Path(__file__).resolve().parents[2]/'fixtures/room_rule_benchmark_3room_b3.json').read_text('utf-8'))
        return prepare(raw,{'upper_combustion_enabled':enabled})[0]
    def test_softplus_extremes_and_interior(self):
        x=np.array([-1e20,0,1,2,1e20]);v=bounded(x,0,2,.01)
        self.assertTrue(np.isfinite(v).all());self.assertTrue(np.all((v>=0)&(v<=2)))
        self.assertAlmostEqual(v[2],1)
        self.assertGreater(lower(0.,0.,1e-5),0)
    def test_reaction_no_empty_inventory_or_cold_burning(self):
        p=self.model().P;mass=np.ones(3)
        xi,_,_=upper_reaction(mass,np.array([0.,.1,.1]),np.array([.23,0.,.23]),np.array([900.,900.,500.]),np.zeros(3),p)
        np.testing.assert_array_equal(xi,np.zeros(3))
    def test_reaction_exact_stoichiometry_and_reserved_oxygen(self):
        p=self.model().P;mu=np.ones(2)*10;yf=np.ones(2)*.1;yo=np.ones(2)*.23
        primary=np.array([0.,10*.23/20])
        xi,o,q=upper_reaction(mu,yf,yo,np.ones(2)*1000,primary,p)
        self.assertGreater(xi[0],0);self.assertEqual(xi[1],0)
        np.testing.assert_allclose(q,p['dHc']*xi);np.testing.assert_allclose(o,q/H_O2)
        self.assertTrue(np.all(o*20+primary*20<=mu*yo+1e-12))
        self.assertTrue(np.all(xi*20<=mu*yf))
    def test_rhs_reaction_balances_no_duplicate_solid_or_mass(self):
        a=self.model(True);b=self.model(False);n=a.N
        a.pending.clear();b.pending.clear();a.activation.clear();b.activation.clear()
        y=a.y0();y[n:2*n]=a.Va/2;y[2*n:3*n]=1000.;y[4*n:5*n]=.23;y[6*n:7*n]=.1
        da=a.rhs(0,y,True);db=b.rhs(0,y,True);diff=a.rhs(0,y)-b.rhs(0,y)
        mu=P0/(RG*y[2*n:3*n])*y[n:2*n]
        np.testing.assert_allclose(diff[4*n:5*n]*mu,-da['upper_oxygen_consumption_kg_s'])
        np.testing.assert_allclose(diff[6*n:7*n]*mu,-da['upper_reaction_kg_s'])
        self.assertAlmostEqual(da['heat_rate']-db['heat_rate'],sum(da['upper_HRR_W']),places=6)
        self.assertEqual(da['mass_rate'],db['mass_rate']);self.assertEqual(da['Qp'],db['Qp'])
        np.testing.assert_array_equal(da['room_Q'],db['room_Q'])
    def test_missing_ignition_configuration_rejected(self):
        with self.assertRaises(ValueError):
            m=self.model();prepare(m.input_model,{'upper_combustion_enabled':True,'gas_ignition_C':None})
if __name__=='__main__':unittest.main()
