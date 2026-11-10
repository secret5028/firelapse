"""Legacy material inspection must not allocate native output gauge slots."""
import json
from pathlib import Path
import unittest
from pyrocast_lite.screening_v8_approved import score,scenario
from pyrocast_lite.adapter import prepare
from pyrocast_cfbt.deck import make_deck

class CapacityTests(unittest.TestCase):
    def test_native_guard_retained_for_large_legacy_model(self):
        root=Path(__file__).resolve().parents[2]
        raw=json.loads((root/'simulation/results/room_rule_r8_20261025/source-scenario.json').read_text('utf8'))
        model=scenario(score(raw,5),'CAD_3F_R1','open_except_confirmed')
        before=json.dumps(model,sort_keys=True)
        prepared,_=prepare(model)
        self.assertTrue(prepared.shared['materials_by_room'])
        self.assertEqual(json.dumps(model,sort_keys=True),before)
        with self.assertRaisesRegex(ValueError,'Floor radiation gauges exceed'):
            make_deck(prepared.input_model,[],[])

if __name__=='__main__':unittest.main()
