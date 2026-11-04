"""One unfinished/corrupt case must not prevent other results from opening."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'tools'))
import model_operation as op

class CatalogIsolation(unittest.TestCase):
    def test_broken_and_incomplete_cases_are_isolated(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            root=Path(temp)
            def case(name, status, request=None, outputs=True):
                folder=root/'hotel'/name; folder.mkdir(parents=True)
                (folder/'status.json').write_text(status, encoding='utf8')
                if request is not None: (folder/'request.json').write_text(json.dumps(request), encoding='utf8')
                if outputs:
                    for file in ('input.json','playback.json'): (folder/file).write_text('{}',encoding='utf8')
            request=dict(building_sha256='same', floor='5F', room='R1')
            case('valid', '{"state":"complete"}', request)
            case('bom', '\ufeff{"state":"complete"}', request)
            case('writing', '{"state":"running"}')
            case('truncated', '{')
            case('missing-request', '{"state":"complete"}')
            case('partial-copy', '{"state":"complete"}', request, False)
            case('bad-request', '{"state":"complete"}', [])
            case('other-building', '{"state":"complete"}', {**request,'building_sha256':'other'})
            with patch.object(op.sim,'RESULTS',root), patch.object(op.sim,'fingerprint',return_value='same'):
                with self.assertLogs(op.__name__,level='WARNING') as warnings:
                    excluded=[]
                    self.assertEqual({p.name for p,r in op.jobs('hotel',excluded)},{'valid','bom'})
                self.assertEqual(len(warnings.output),4)
                self.assertEqual(len(excluded),4)

if __name__=='__main__': unittest.main()
