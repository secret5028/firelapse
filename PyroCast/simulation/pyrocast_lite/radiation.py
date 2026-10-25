"""Section 1.3 reduced grey-gas exchange; not native RAD4/view-factor solution.

CFAST 7.7.7 radiation.f90:53,87-92: defabsup=0.50 m^-1 only when
fgasabsorb is OFF. The ordinary absorb() uses CO2/H2O/soot (lines 921-947).
Mean beam: radiation.f90:59-62, equivalent to 3.6*Vu/(2*A+perimeter*depth).
Sigma: prec.f90:19. Lower gas absorption is intentionally omitted by spec.
"""
import numpy as np

KAPPA_UPPER = 0.50
SIGMA = 5.67e-8


def upper_absorptivity(area, perimeter, depth):
    depth=np.maximum(depth,0.)
    beam=3.6*area*depth/(2*area+perimeter*depth)
    return -np.expm1(-KAPPA_UPPER*beam),beam


def wall_to_upper(upper_K,wall_K,wall_emissivity,contact_area,gas_emissivity):
    # Factorized fourth-power difference preserves exact zero at equilibrium.
    gas=upper_K[:,None]
    return (gas_emissivity[:,None]*wall_emissivity*SIGMA*
            (wall_K-gas)*(wall_K+gas)*(wall_K**2+gas**2)*contact_area)
