import json
import unittest
from pathlib import Path
import numpy as np
from scipy.optimize._numdiff import group_columns
from pyrocast_lite.adapter import prepare

class CumulativeStateTests(unittest.TestCase):
    def models(self):
        raw=json.loads((Path(__file__).resolve().parents[2]/'fixtures/room_rule_benchmark_3room_b3.json').read_text('utf-8'))
        p={'smooth_state_bounds':True,'upper_combustion_enabled':True,'oxygen_inventory_mode':False,'remove_cumulative_state':False}
        return prepare(raw,p)[0],prepare(raw,{**p,'remove_cumulative_state':True})[0]

    def test_physical_rhs_unchanged_and_independent_of_removed_energy(self):
        old,new=self.models();n=old.N
        y=old.y0();y[n:2*n]=old.Va*.4;y[2*n:3*n]=950.;y[3*n:4*n]=370.
        y[4*n:6*n]=.18;y[6*n:8*n]=.02;y[8*n+1:]=420.
        for e in (0.,1e12):
            y[8*n]=e
            np.testing.assert_array_equal(np.delete(old.rhs(300,y),8*n),new.rhs(300,np.delete(y,8*n)))
        np.testing.assert_array_equal(np.delete(old.integration_atol(),8*n),new.integration_atol())
        self.assertEqual(len(new.y0()),11*n)
        self.assertEqual(new.sparsity().shape,(11*n,11*n))
        self.assertLess(len(set(group_columns(new.sparsity()))),len(new.y0()))

    def test_sparsity_covers_observed_derivatives_and_excludes_non_neighbors(self):
        _,m=self.models();n=m.N;y=m.y0()
        y[:n]=np.array([20.,-5.,8.]);y[n:2*n]=m.Va*.45
        y[2*n:3*n]=np.array([1000.,650.,400.]);y[3*n:4*n]=340.
        y[4*n:6*n]=.18;y[6*n:8*n]=.03;y[8*n:]=400.
        m.activation.update({r:0. for r in m.by_room})
        f=m.rhs(300,y);pattern=m.sparsity().toarray()
        for col in range(len(y)):
            z=y.copy();z[col]+=max(abs(y[col])*1e-5,1e-6)
            diff=m.rhs(300,z)-f
            self.assertTrue(np.all(diff[~pattern[:,col]]==0),msg=f'Undeclared dependency column {col}')
        self.assertFalse(pattern[0,2]) # R1 and R3 are not direct neighbors.

if __name__=='__main__':unittest.main()
