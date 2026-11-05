"""Local finite differences without history-dependent perturbation growth.

SciPy's persistent num_jac factor can grow on a locally insensitive column
until a finite state is perturbed to infinity. Start each Jacobian at SciPy's
sqrt(machine-epsilon) factor, scaled by max(abs(state), positive state atol).
SciPy may still refine that step within the current evaluation. No physical
state, RHS, integration tolerance, event or fuel parameter is changed.
"""
import numpy as np
from scipy.integrate._ivp.common import num_jac
from scipy.optimize._numdiff import group_columns


def fresh_jacobian(fun, atol, sparsity):
    atol = np.asarray(atol, dtype=float)
    if not np.isfinite(atol).all() or np.any(atol <= 0):
        raise ValueError('Jacobian state tolerances must be finite and positive')
    structure = sparsity.tocsc()
    grouped = (structure, group_columns(structure))

    def vectorized(t, ys):
        return np.column_stack([fun(t, ys[:, j]) for j in range(ys.shape[1])])

    def jac(t, y):
        f = fun(t, y)
        if not np.isfinite(y).all() or not np.isfinite(f).all():
            raise ValueError('Non-finite integration state/RHS before Jacobian')
        matrix, _ = num_jac(vectorized, t, y, f, atol, None, grouped)
        if not np.isfinite(matrix.data).all():
            raise ValueError('Non-finite finite-difference Jacobian')
        return matrix

    return jac
