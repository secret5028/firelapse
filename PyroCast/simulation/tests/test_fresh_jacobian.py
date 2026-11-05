"""Finite-difference regression without a fire simulation."""
from pathlib import Path
import sys, unittest
ROOT=Path(__file__).resolve().parents[2]
for part in ('simulation/deps','simulation'):sys.path.insert(0,str(ROOT/part))
import numpy as np
from scipy.sparse import csc_matrix
from scipy.integrate import solve_ivp
from pyrocast_lite.jacobian import fresh_jacobian


class FreshJacobianTests(unittest.TestCase):
    def test_flat_column_nonzero_rhs_does_not_grow(self):
        jac=fresh_jacobian(lambda t,y:np.ones_like(y),[1e-6,1e-6],csc_matrix(np.eye(2)))
        with np.errstate(all='raise'):
            for _ in range(400):
                np.testing.assert_array_equal(jac(0,np.array([-7.27e-12,0.])).toarray(),np.zeros((2,2)))

    def test_coupled_stiff_system(self):
        a=np.array([[-1000.,2.],[0.,-1.]])
        fun=lambda t,y:a@y
        jac=fresh_jacobian(fun,[1e-6,1e-6],csc_matrix(a!=0))
        np.testing.assert_allclose(jac(0,np.array([1.,2.])).toarray(),a,rtol=1e-6)
        for method in ('BDF','Radau'):
            sol=solve_ivp(fun,(0,1),[1.,2.],method=method,jac=jac,rtol=1e-6,atol=1e-8)
            self.assertTrue(sol.success)
            np.testing.assert_allclose(sol.y[:,-1],[4/999*np.exp(-1),2*np.exp(-1)],rtol=1e-5)

    def test_invalid_values_fail_not_silently_clamped(self):
        with self.assertRaises(ValueError):fresh_jacobian(lambda t,y:y,[0],csc_matrix([[1]]))
        jac=fresh_jacobian(lambda t,y:y,[1e-6],csc_matrix([[1]]))
        with self.assertRaises(ValueError):jac(0,np.array([np.nan]))

if __name__=='__main__':unittest.main()
