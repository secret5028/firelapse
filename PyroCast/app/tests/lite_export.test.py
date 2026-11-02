import base64
import gzip
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from lite_export import packed,sample_playback,build_export


class ExportTests(unittest.TestCase):
    def test_default_keeps_original(self):
        source={'time_s':[0,10,20]}
        self.assertIs(sample_playback(source,10),source)

    def test_20s_keeps_geometry_events_and_last(self):
        source={'time_s':[0,10,20,30], 'solvers':{'R1':{'Tu':[20,30,40,50],
          'conditions':{'FO':{'scores':{'degree':[0,1,2,3]}}}}},
          'fires':[{'Q_kW':[0,10,20,30],'position_m':[1,2,3],
                    'visuals':{'flame_height_m':[0,1,2,3]}}],
          'rooms':[{'polygon':[1,2,3,4]}], 'events':[{'time_s':10}]}
        result=sample_playback(source,20)
        self.assertEqual(result['time_s'],[0,20,30])
        self.assertEqual(result['solvers']['R1']['Tu'],[20,40,50])
        self.assertEqual(result['fires'][0]['visuals']['flame_height_m'],[0,2,3])
        self.assertEqual(result['rooms'],source['rooms'])
        self.assertEqual(result['events'],source['events'])
        self.assertEqual(source['time_s'],[0,10,20,30])

    def test_json_cannot_close_script(self):
        value={'label':'</script><script>alert(1)</script>한글'}
        data=packed(value)
        self.assertNotIn('<',data)
        self.assertEqual(json.loads(gzip.decompress(base64.b64decode(data))),value)

    def test_reject_path_traversal_before_io(self):
        with self.assertRaises(ValueError):build_export('http://127.0.0.1:1','../../secret',{})
        with self.assertRaises(ValueError):sample_playback({},15)

if __name__=='__main__':unittest.main()
