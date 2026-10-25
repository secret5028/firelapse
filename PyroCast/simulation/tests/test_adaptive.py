import json
import unittest
from pathlib import Path
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.deck import gas_sidecar

class AdaptiveTests(unittest.TestCase):
    def raw(self):
        return json.loads((Path(__file__).parents[1]/'examples/three_rooms.json').read_text())

    def test_disabled_default_does_not_change_sidecar(self):
        self.assertNotIn('adaptive_',gas_sidecar(normalize(self.raw())))

    def test_opt_in_and_validation(self):
        raw=self.raw();raw['engine_optimization']={'adaptive_radiation':True}
        model=normalize(raw)
        self.assertIn('adaptive_radiation_enabled=.TRUE.',gas_sidecar(model))
        for bad in (0,-1,True,float('nan')):
            raw['engine_optimization']['adaptive_refresh_s']=bad
            with self.assertRaises(ValueError):normalize(raw)

    def test_no_chemistry_or_ignition_changes(self):
        raw=self.raw();before=normalize(raw)
        raw['engine_optimization']={'adaptive_radiation':True}
        after=normalize(raw)
        for key in ('gas','material','fuel_groups','flashover','criteria','spread'):
            self.assertEqual(before[key],after[key])
