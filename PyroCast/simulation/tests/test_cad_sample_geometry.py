import json,math,tempfile,unittest
from copy import deepcopy
from pathlib import Path
from pyrocast_cfbt.cad import adapt,envelope_width,footprint
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.native_apertures import prepare
from pyrocast_lite.montecarlo import opening_class

ROOT=Path(__file__).resolve().parents[2]

class SampleGeometryTests(unittest.TestCase):
    def test_asymmetric_envelope_uses_extent_and_explicit_span_is_preserved(self):
        raw={'polys':[[[0,0],[1,.0],[1,.1],[.1,.1],[.1,2],[0,2]]]}
        dims={'width_m':3.8,'width_source':'CAD_aperture_envelope'}
        width,note=envelope_width(raw,dims)
        self.assertAlmostEqual(width,2);self.assertEqual(note['previous_width_m'],3.8)
        self.assertEqual(envelope_width({**raw,'span':3.8},dims),(3.8,None))
        self.assertEqual(envelope_width(raw,{'width_m':3.8,'width_source':'CAD_span'}),(3.8,None))

    def test_parallel_vent_preserves_flow_area_schedule_and_source(self):
        raw={'rooms':[{'id':'A','size_m':[1.8,.65,3]},{'id':'B','size_m':[5,5,3]}],
             'openings':[{'id':'W','a':'A','b':'B','face':'FRONT','width_m':4.12,
                          'bottom_m':.9,'top_m':2.4,'schedule':[[0,0],[60,.5]],'offset_m':-1}]}
        saved=deepcopy(raw);new=prepare(raw);self.assertEqual(raw,saved)
        vents=new['openings'];self.assertEqual(len(vents),3)
        self.assertAlmostEqual(sum(v['width_m'] for v in vents),4.12)
        for v in vents:
            self.assertGreaterEqual(v['offset_m'],0)
            self.assertLessEqual(v['offset_m']+v['width_m'],1.8)
            self.assertEqual(v['schedule'],raw['openings'][0]['schedule'])
            self.assertEqual((v['a'],v['b'],v['bottom_m'],v['top_m']),('A','B',.9,2.4))

    def test_hotel_b1_preserves_room_area_and_source_bytes(self):
        path=ROOT/'data/parkmarine-hotel/building.json';before=path.read_bytes()
        model=normalize(adapt(ROOT,dict(building_path=str(path),scope_floor='B1',fire_floor='B1',fire_room='R2')))
        for r in model['rooms']:
            self.assertAlmostEqual(math.prod(r['size_m'][:2]),footprint(r['cad_polys']).area)
            self.assertGreater(min(r['size_m'][:2]),.6)
        self.assertEqual(path.read_bytes(),before)
        self.assertTrue(any(v.get('width_correction') for v in model['openings']))

    def test_ramp_is_permanent_open(self):
        self.assertEqual(opening_class({'id':'RAMP','kind':'ramp'}),'permanent_open')

if __name__=='__main__':unittest.main()
