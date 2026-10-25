import json
from pathlib import Path
import unittest
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.deck import gas_sidecar

class SmoothSettingsTests(unittest.TestCase):
    def test_old_sidecars_remain_compatible_and_new_widths_are_explicit(self):
        raw=json.loads((Path(__file__).resolve().parents[1]/'examples/three_rooms.json').read_text())
        old=normalize(raw)
        self.assertNotIn('mixture_smooth',gas_sidecar(old))
        old['gas'].update(mixture_enabled=True,mixture_smooth_enabled=True)
        new=normalize(old)
        text=gas_sidecar(new)
        self.assertIn('mixture_smooth_enabled=.TRUE.',text)
        self.assertIn('mixture_o2_width_vol=0.01',text)
        self.assertIn('mixture_mixing_time_s=10',text)
        new['gas']['mixture_o2_width_vol']=0
        with self.assertRaisesRegex(ValueError,'transition widths'):normalize(new)

    def test_mixing_time_must_bound_native_maximum_step(self):
        raw=json.loads((Path(__file__).resolve().parents[1]/'examples/three_rooms.json').read_text())
        raw['gas']={'mixture_enabled':True,'mixture_smooth_enabled':True,'mixture_mixing_time_s':.01}
        raw['max_time_step_s']=.1
        with self.assertRaisesRegex(ValueError,'mixing time'):normalize(raw)
