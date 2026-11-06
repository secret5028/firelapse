import base64
import gzip
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
import re

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

    def test_model_service_external_entry_and_offline_assets(self):
        playback={'complete':True,'building_sha256':'b','time_s':[0,10], 'rooms':[], 'solvers':{},'fires':[]}
        routes={'/':(ROOT/'app/model-library/operation.html').read_bytes(),
          '/operation.js':b"import * as T from 'three'; import {attach} from '/app/web/entry.js';",
          '/vendor/three.module.js':b'export const Scene=1;',
          '/app/web/entry.js':b'export const attach=1;',
          '/building.json':{'floors':[]},'/cfbt/lite/result/saved':playback,
          '/cfbt/lite/doors':{'fixed_state':{'source':'this-building'}},
          '/cfbt/lite/screening':{},'/cfbt/lite/fire-load-table':{},
          '/cfbt/theme.css':b':root{--text:#eaf3f8}', '/cfbt/model-info':{'label':'새 건물'},'/cfbt/overlay.css':b'.pyroShell{color:red}',
          '/cfbt/lite/catalog.json':{'cases':[{'id':'saved','label':'저장 결과'}]}}
        requested=[]
        class Response:
            def __init__(self,url):self.url=url;self.path=urlsplit(url).path;requested.append(self.path)
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):
                value=routes[self.path]
                return value if isinstance(value,bytes) else json.dumps(value).encode()
        state={'route':{'vehicle':[1,2,0]},'route_result':{'length':23},'fuelSettings':{'data':{'revision':'saved'}}}
        with patch('lite_export.urlopen',side_effect=lambda url,**kw:Response(url)):
            html,info=build_export('http://127.0.0.1:1','saved',state,model_service=True)
        text=html.decode()
        self.assertNotIn('src="/operation.js"',text)
        self.assertIn('.pyroShell{color:red}',text)
        self.assertIn(':root{--text:#eaf3f8}',text)
        self.assertNotIn('href="/cfbt/theme.css"',text)
        payload=re.search(r'id="pcOfflineData"[^>]*>([^<]+)',text)[1]
        data=json.loads(gzip.decompress(base64.b64decode(payload)))
        self.assertEqual(data['state'],state)
        self.assertEqual(data['fixed_openings'],{'source':'this-building'})
        self.assertEqual(data['routes']['/cfbt/model-info']['label'],'새 건물')
        self.assertIn('/vendor/three.module.js',data['modules'])
        self.assertTrue(data['scripts']);self.assertEqual(info['modules'],2)
        self.assertFalse(any('legacy-context' in r or 'hydraulics' in r for r in requested))
        routes['/cfbt/lite/catalog.json']={'cases':[]}
        with patch('lite_export.urlopen',side_effect=lambda url,**kw:Response(url)):
            with self.assertRaisesRegex(ValueError,'목록이 바뀌었습니다'):
                build_export('http://127.0.0.1:1','saved',state,model_service=True)

if __name__=='__main__':unittest.main()
