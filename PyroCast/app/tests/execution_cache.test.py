"""Stored alias compatibility without the retired migration generator."""
from pathlib import Path
import sys, tempfile, unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from execution_cache import ExecutionCache
from result_catalog import atomic_json

class CacheLookup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / 'app/tests', prefix='.cache-test-')
        self.root = Path(self.tmp.name)
        self.cache = ExecutionCache(self.root)
        self.folder = self.root / 'cad_interactive' / 'old'
        atomic_json(self.folder / 'playback.json', {'complete': True, 'building_sha256': 'B'})
        atomic_json(self.folder / 'result.json', {'complete': True})
        record = self.cache.seal(self.folder, 'native', 'new', 'B')
        atomic_json(self.cache.path, {'aliases': {'native:new': [record]}})
    def tearDown(self):
        assert self.root.resolve().is_relative_to((ROOT / 'app/tests').resolve())
        self.tmp.cleanup()
    def test_alias_read_only(self):
        before = self.cache.path.read_bytes()
        self.assertEqual(self.cache.lookup('native', 'new', 'B')[0], self.folder)
        self.assertEqual(self.cache.path.read_bytes(), before)
        self.assertFalse(hasattr(self.cache, 'migrate'))
    def test_reject_mismatch(self):
        self.assertIsNone(self.cache.lookup('native', 'new', 'different'))
        atomic_json(self.folder / 'result.json', {'changed': True})
        self.assertIsNone(self.cache.lookup('native', 'new', 'B'))
    def test_direct_first(self):
        direct = self.root / 'cad_interactive' / 'new'
        atomic_json(direct / 'playback.json', {'complete': True, 'building_sha256': 'B'})
        atomic_json(direct / 'result.json', {})
        self.cache.seal(direct, 'native', 'new', 'B')
        self.assertEqual(self.cache.lookup('native', 'new', 'B')[0], direct)

if __name__ == '__main__': unittest.main(verbosity=2)
