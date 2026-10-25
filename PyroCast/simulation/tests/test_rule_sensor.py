import json,unittest
from pathlib import Path
from pyrocast_cfbt.rule_sensor import gas_proxy_plate
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.deck import make_deck


class RuleSensorTests(unittest.TestCase):
    def model(self):
        path=Path(__file__).resolve().parents[2]/'fixtures/room_rule_benchmark_3room.json'
        return normalize(json.loads(path.read_text('utf-8')))

    def test_fixed_corner_uses_native_material_and_no_ignition_feedback(self):
        model=self.model();room=model['rooms'][0];source=model['fuel_groups'][0]
        sensor=gas_proxy_plate(model,room,source)
        self.assertEqual(sensor['xyz'],[.3,.3,2.5]);self.assertEqual(sensor['normal'],[-1,0,0])
        deck=make_deck(model,[],[sensor])
        self.assertIn('THICKNESS=0.0001 EMISSIVITY=0.05',deck)
        self.assertNotIn('DEVC_ID=',deck);self.assertNotIn('&CFBT',deck)
        self.assertEqual(deck.count('&FIRE '),1)

    def test_farthest_corner_independent_of_origin_and_narrow_room_rejected(self):
        model=self.model();room={**model['rooms'][0],'origin_m':[10,20,30]}
        source={**model['fuel_groups'][0],'position_m':[10.5,20.5,30]}
        sensor=gas_proxy_plate(model,room,source)
        self.assertEqual(sensor['xyz'],[14.7,24.7,32.5]);self.assertEqual(sensor['normal'],[1,0,0])
        room['size_m']=[.6,5,2.7]
        with self.assertRaisesRegex(ValueError,'too small'):gas_proxy_plate(model,room,source)
