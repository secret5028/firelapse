import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from mc_display_summary import rooms_max, _sample


class DisplaySummaryTest(unittest.TestCase):
    def test_dedup_unknown_and_cache_invalidation(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            folder = Path(tmp)
            path = folder / 'S00' / 'playback.json'
            path.parent.mkdir()
            value = dict(schema='pyrocast-cad-playback-1', complete=True,
                         building_sha256='sha', time_s=[0, 10],
                         rooms=[dict(key='A_C0', original_room='A', solver_id='a'),
                                dict(key='A_C1', original_room='A', solver_id='a'),
                                dict(key='B', solver_id='b')],
                         solvers={'a': {'conditions': {k: {'scores': {'degree': [0, 1.2]}} for k in ('FO','FGI','backdraft')}},
                                  'b': {'conditions': {'FO': {'scores': {'degree': [0, 2]}}}}})
            path.write_text(json.dumps(value), encoding='utf-8')
            rows = [dict(complete=True), dict(complete=False)]
            first = rooms_max(folder, rows, 'sha')
            self.assertEqual(first['FO'], dict(rooms=2, unknown=False))
            self.assertEqual(first['FGI'], dict(rooms=1, unknown=True))
            with patch('builtins.open', side_effect=AssertionError('cache missed')):
                self.assertEqual(rooms_max(folder, rows, 'sha'), first)
            value['solvers']['a']['conditions']['FO']['scores']['degree'] = [0, 0]
            path.write_text(json.dumps(value), encoding='utf-8')
            self.assertEqual(rooms_max(folder, rows, 'sha')['FO']['rooms'], 1)
            self.assertTrue(rooms_max(folder, rows, 'other')['FO']['unknown'])
            rows[1]['complete'] = True
            self.assertTrue(rooms_max(folder, rows, 'sha')['FO']['unknown'])
            self.assertTrue(rooms_max(folder, [], 'sha')['FO']['unknown'])


if __name__ == '__main__':
    unittest.main()
