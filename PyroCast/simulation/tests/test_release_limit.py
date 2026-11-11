"""Fuel release limit of sealed components: budget, curve shape and scope. No native solver runs."""
import unittest
from copy import deepcopy
import numpy as np
from pyrocast_cfbt.leakage import apply_minimum_leakage
from pyrocast_cfbt.release_limit import NOTE, apply, limited_curve, sealed_components
from pyrocast_cfbt.deck import fire_curve, prescribed_curve
from test_physics_p0 import sealed


def model():
    m = sealed(); m['limits'] = []
    m['fuel_groups'][0].update(energy_MJ=40000, growth_kW_s2=.047, peak_kW=8000, hrrpua_kW_m2=500)
    apply_minimum_leakage(m)
    return m


def energy(t, q):
    return float(np.trapezoid(q, t))


class ReleaseLimit(unittest.TestCase):
    def test_budget_from_enclosed_air_and_equivalent_path(self):
        m = apply(model()); record = m['fuel_release_limit'][0]
        self.assertEqual(record['rooms'], ['Fire', 'Stair'])
        self.assertAlmostEqual(record['volume_m3'], 327)
        self.assertAlmostEqual(record['stored_air_energy_MJ'], 327*1.2*3000*.5/1000)
        vent = next(v for v in m['openings'] if v.get('minimum_leakage')); height = vent['top_m']-vent['bottom_m']
        self.assertAlmostEqual(record['path_supply_kW'], 1500*vent['width_m']*height*height**.5)
        self.assertAlmostEqual(record['limited_release_kW'], 1.5*record['path_supply_kW'])
        self.assertEqual(sum(s.startswith(NOTE) for s in m['limits']), 1)
        apply(m); self.assertEqual(sum(s.startswith(NOTE) for s in m['limits']), 1)      # idempotent

    def test_curve_is_followed_then_held_and_keeps_its_fuel(self):
        m = apply(model()); g = m['fuel_groups'][0]; limit = g['release_limit']
        t0, q0, _ = prescribed_curve(g, 100.); t1, q1, a1 = fire_curve(g, 100.)
        self.assertAlmostEqual(energy(t1, q1), energy(t0, q0), delta=1e-6*energy(t0, q0))
        cut = t1[-4]; cap = limit['excess_release_ratio']*limit['supply_kW']
        self.assertEqual(q1[-3:], [cap, cap, 0.])
        self.assertAlmostEqual(t1[-3]-cut, limit['ramp_s'])
        grid = np.linspace(0, cut, 2000); released = np.trapezoid(np.interp(grid, t0, q0), grid)
        self.assertAlmostEqual(released, limit['store_kJ']+limit['supply_kW']*cut, delta=.01*released)   # cut where the budget is spent
        self.assertTrue(all(b > a for a, b in zip(t1, t1[1:])) and min(a1) > 0)
        self.assertLess(max(q1), max(q0))                                         # the prescribed peak is never reached

    def test_a_fire_within_its_budget_is_untouched(self):
        t, q, a = [0., 100., 200.], [0., 50., 0.], [.1, .2, .1]
        self.assertEqual(limited_curve(t, q, a, dict(store_kJ=1e9, supply_kW=10., excess_release_ratio=1.5, ramp_s=10.)), (t, q, a))
        self.assertEqual(limited_curve(t, q, a, dict(store_kJ=0., supply_kW=100., excess_release_ratio=1.5, ramp_s=10.)), (t, q, a))   # below the limited rate

    def test_only_components_without_any_other_air_are_limited(self):
        base = model()
        opened = deepcopy(base); opened['openings'].append(dict(id='W', a='Fire', b='OUTSIDE', schedule=[[0, 0], [600, 1]]))
        self.assertEqual(list(sealed_components(opened)), [])                     # a window that opens later
        fan = deepcopy(base); fan['mechanical_vents'] = [dict(id='F', comp='Fire')]
        self.assertEqual(list(sealed_components(fan)), [])
        above = sealed(); above['limits'] = []
        for r in above['rooms']: r.update(below_grade=False, origin_m=[r['origin_m'][0], 0, 0])
        above['fuel_groups'][0].update(energy_MJ=40000, growth_kW_s2=.047, peak_kW=8000, hrrpua_kW_m2=500)
        apply_minimum_leakage(above); apply(above)
        self.assertNotIn('fuel_release_limit', above)                             # native built-in leakage reaches ambient
        off = deepcopy(base); off['fuel_release_limit_settings'] = {'enabled': False}; apply(off)
        self.assertNotIn('release_limit', off['fuel_groups'][0])


if __name__ == '__main__': unittest.main()
