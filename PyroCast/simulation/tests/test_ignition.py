from copy import deepcopy
import json
from pathlib import Path
import unittest
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.deck import gas_sidecar
from pyrocast_cfbt.comparison import clipped_playback

ROOT=Path(__file__).resolve().parents[1]


class IgnitionTests(unittest.TestCase):
    def setUp(self):
        self.raw=json.loads((ROOT/'examples/three_rooms.json').read_text())

    def test_selected_room_and_finite_window_sidecar(self):
        self.raw['ignition_assumption']={'room':'R2','time_s':45.,'duration_s':30.,'rate_s_inv':.2,'oxygen_min_vol_percent':10.}
        value=gas_sidecar(normalize(self.raw))
        self.assertIn('force_room=2',value);self.assertIn('force_time_s=45',value)
        self.assertIn('force_o2_min_vol=0.1',value)
        original=deepcopy(self.raw);del original['ignition_assumption']
        self.assertNotIn('force_room',gas_sidecar(normalize(original)))

    def test_invalid_or_disabled_ignition_rejected(self):
        for patch in ({'room':'absent'},{'time_s':-1},{'rate_s_inv':float('nan')},{'duration_s':0}):
            model=deepcopy(self.raw)
            model['ignition_assumption']={'room':'R2','time_s':45.,'duration_s':30.,'rate_s_inv':.2,**patch}
            with self.assertRaises(ValueError):normalize(model)
        self.raw['ignition_assumption']={'room':'R2','time_s':45.,'duration_s':30.,'rate_s_inv':.2}
        self.raw['gas']['enabled']=False
        with self.assertRaises(ValueError):normalize(self.raw)

    def test_comparison_clip_preserves_geometry_and_schedule(self):
        geometry=[[1,2],[3,4],[5,6]];schedule=[[0,0],[5,1],[10,1]]
        payload={'time_s':[0,5,10],'solvers':{'R1':{'Tu':[20,30,40],'tags':{'FO':[False,True,True]}}},
                 'rooms':[{'polys':geometry}],'openings':[{'schedule':schedule,'ab':[[0],[1],[2]],'ba':[[0],[1],[2]],'gas_ab_kW':[0,1,2],'gas_ba_kW':[0,1,2]}],
                 'fires':[{'Q_kW':[0,1,2],'visuals':{'area_m2':[0,1,2],'flame_height_m':[0,1,2]}}]}
        clipped=clipped_playback(payload,5)
        self.assertEqual(clipped['time_s'],[0,5]);self.assertEqual(clipped['solvers']['R1']['tags']['FO'],[False,True])
        self.assertEqual(clipped['rooms'][0]['polys'],geometry)
        self.assertEqual(clipped['openings'][0]['schedule'],schedule)
        self.assertEqual(len(payload['time_s']),3)


if __name__=='__main__':unittest.main()
