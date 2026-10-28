from pathlib import Path
import sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation')]
from cache_key_aliases import CacheAliases
from result_catalog import atomic_json,read
from saved_case_reuse import describe

class Aliases(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'simulation/results',prefix='server_stage5_test')
        self.root=Path(self.tmp.name);self.cache=CacheAliases(self.root);self.old='a'*24;self.new='b'*24
        self.folder=self.root/'cad_interactive'/self.old
        atomic_json(self.folder/'scenario.json',{'cad':{'options':{'duration_s':1800},'building_sha256':'B'}})
        atomic_json(self.folder/'playback.json',{'complete':True,'building_sha256':'B'})
        atomic_json(self.folder/'result.json',{'complete':True})
    def tearDown(self):self.tmp.cleanup()
    def migrate(self):return self.cache.migrate(lambda *a:self.old,lambda *a:self.new,'old-server')
    def test_one_time_and_fallback(self):
        self.assertIsNone(self.cache.lookup('native',self.new,'B'));value=self.migrate()
        self.assertEqual(value['entries'][0]['status'],'migrated')
        self.assertEqual(self.cache.lookup('native',self.new,'B')[0],self.folder)
        self.assertEqual(self.cache.migrate(lambda *a:1/0,lambda *a:1/0,'different'),value)
    def test_input_building_and_content_must_match(self):
        self.migrate();self.assertIsNone(self.cache.lookup('native','c'*24,'B'));self.assertIsNone(self.cache.lookup('native',self.new,'C'))
        atomic_json(self.folder/'result.json',{'changed':True});self.assertIsNone(self.cache.lookup('native',self.new,'B'))
    def test_no_invented_keys_for_old_namespace(self):
        old=self.root/'cad_interactive'/'cee3fee4fdeb019a';old.mkdir()
        rows=self.migrate()['entries'];self.assertEqual(next(r for r in rows if r['old_key']==old.name)['status'],'excluded')
    def test_mismatch_and_partial_excluded(self):
        value=self.cache.migrate(lambda *a:'x'*24,lambda *a:self.new,'old')
        self.assertFalse(value['aliases']);self.assertIn('does not match',value['entries'][0]['reason'])
    def test_direct_before_alias_and_reuse_label(self):
        self.migrate();direct=self.root/'cad_interactive'/self.new
        atomic_json(direct/'playback.json',{'complete':True,'building_sha256':'B'});atomic_json(direct/'result.json',{})
        atomic_json(direct/'execution-request.json',{'options':{},'building_sha256':'B'})
        self.cache.seal(direct,'native',self.new,'B');self.assertEqual(self.cache.lookup('native',self.new,'B')[0],direct)
        row={'id':'fixture','path':str(direct/'playback.json')}
        self.assertTrue(describe(row,'native','B',self.cache,lambda *a:self.new)['equivalent'])
        self.assertEqual(describe(row,'lite','B',self.cache,lambda *a:self.new)['label'],'과거 결과 재사용')

if __name__=='__main__':unittest.main(verbosity=2)
