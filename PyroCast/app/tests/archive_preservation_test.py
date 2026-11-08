import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import result_catalog,saved_briefings,runtime_storage

class ArchivePreservation(unittest.TestCase):
    def test_catalog_and_refreshed_briefing_write_only_to_external_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp);archive=data/'results';archive.mkdir()
            p=archive/'case'/'playback.json';p.parent.mkdir()
            p.write_text(json.dumps(dict(schema='pyrocast-cad-playback-1',complete=True,time_s=[0,10],building_sha256='B',engine_kind='pyrocast_lite',rooms=[])),'utf8')
            legacy=p.with_name('playback-briefing.json');legacy.write_text('{"version":1}','utf8')
            catalog=archive/'playback-catalog.json';catalog.write_text('{"files":{}}','utf8')
            before={f:f.read_bytes() for f in archive.rglob('*') if f.is_file()}
            service=Mock();service.bind_saved_case.return_value=service
            public=dict(case='case',building='B',text='new briefing',sections=[],template_version=3,calls=[])
            with patch.object(runtime_storage,'DATA_ROOT',data),patch.object(saved_briefings,'DATA_ROOT',data),patch.object(saved_briefings,'service_for_hash',return_value=service),patch.object(saved_briefings,'briefing_value',return_value=public):
                result_catalog.ResultCatalog(archive,data/'aliases.json').scan(force=True)
                saved_briefings.ensure(p)
            self.assertEqual(before,{f:f.read_bytes() for f in archive.rglob('*') if f.is_file()})
            self.assertEqual(len(list((data/'cache/briefings').glob('*.json'))),1)
            self.assertEqual(len(list((data/'cache/catalogs').glob('*.json'))),1)

if __name__=='__main__':unittest.main()
