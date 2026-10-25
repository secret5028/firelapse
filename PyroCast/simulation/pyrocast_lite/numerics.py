"""State evaluation bounds; SciPy still owns all steps and error control."""
import numpy as np

def lower(x,lo,width):
    return lo+width*np.logaddexp(0.,(np.asarray(x)-lo)/width)

def bounded(x,lo,hi,width):
    # Use the nearer-bound form to avoid catastrophic cancellation far inside.
    x=np.asarray(x)
    return np.where(x<(lo+hi)/2,
        lo+width*(np.logaddexp(0.,(x-lo)/width)-np.logaddexp(0.,(x-hi)/width)),
        hi-width*(np.logaddexp(0.,(hi-x)/width)-np.logaddexp(0.,(lo-x)/width)))

def upper_reaction(mu,fuel_fraction,oxygen_fraction,temperature,primary_oxygen_rate,parameters,reserved_fuel_rate=None):
    """kg/s from existing inventory, not trial dt. No new pyrolysis or total mass.

    Reserve the plume's upper oxygen draw over the same mixing horizon before
    the additional reaction. Fuel inventory excludes already burned supply.
    """
    from .core import H_O2,oxygen_factor
    tau=parameters['upper_mixing_time_s'];hoc=parameters['dHc'];stoich=hoc/H_O2
    mf=mu*np.maximum(fuel_fraction,0.)
    if reserved_fuel_rate is not None:
        mf=np.maximum(mf-tau*reserved_fuel_rate,0.)
    mo=np.maximum(mu*np.maximum(oxygen_fraction,0.)-tau*primary_oxygen_rate,0.)
    oxygen=np.array([oxygen_factor(float(v),parameters) for v in oxygen_fraction])
    delta=np.maximum(temperature-273.15-parameters['gas_ignition_C'],0.)
    # Strictly zero below configured temperature, C1 numerical onset across
    # 10*T_atol=0.5 K, not a new ignition temperature or an Arrhenius law.
    thermal=-np.expm1(-(np.minimum(delta/parameters['reaction_temperature_width_K'],30.))**2)
    xi=np.minimum(mf/tau,mo/(stoich*tau))*oxygen*thermal
    return xi,stoich*xi,hoc*xi
