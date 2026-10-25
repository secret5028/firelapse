import unittest
from pyrocast_cfbt.combustion_display import classify_source

class CombustionDisplayTests(unittest.TestCase):
    def test_ignition_and_starvation_are_not_flame_or_fuel_exhaustion(self):
        self.assertEqual(classify_source([0,0,0,50,0],[0,0,.1,.1,0],[False,True,True,True,True]),
                         ['inactive','activated_no_supply','supply_without_burning','burning','activated_no_supply'])

    def test_any_positive_native_source_hrr_counts_but_not_ignition_alone(self):
        self.assertEqual(classify_source([1e-12,0],[.1,.1],[True,True]),['burning','supply_without_burning'])

    def test_reject_mismatched_native_series(self):
        with self.assertRaises(ValueError):classify_source([0,1],[0],[False,True])
