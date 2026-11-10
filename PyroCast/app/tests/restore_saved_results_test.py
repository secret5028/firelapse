import gzip
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from restore_saved_results import restore

class RestoreTests(unittest.TestCase):
    def test_preserves_existing_and_restores_exact_bytes_once(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);archive=root/'saved_results/case/playback.json.gz';archive.parent.mkdir(parents=True)
            expected=b'{"complete":true}';archive.write_bytes(gzip.compress(expected))
            self.assertEqual(restore(root),1)
            target=root/'simulation/results/case/playback.json';self.assertEqual(target.read_bytes(),expected)
            target.write_bytes(b'preserve user data')
            self.assertEqual(restore(root),0);self.assertEqual(target.read_bytes(),b'preserve user data')
    def test_corrupt_archive_does_not_publish_partial_result(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);archive=root/'saved_results/case/playback.json.gz';archive.parent.mkdir(parents=True)
            archive.write_bytes(b'not gzip')
            with self.assertRaises(gzip.BadGzipFile):restore(root)
            self.assertEqual(list((root/'simulation/results/case').iterdir()),[])

if __name__=='__main__':unittest.main()
