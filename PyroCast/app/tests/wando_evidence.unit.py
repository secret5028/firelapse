"""Diagnostic/spec edits are allowed; engine, deck and physical model are not."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from run_wando_c11_p1 import immutable_hashes_match

class EvidencePaths(unittest.TestCase):
    def test_same_exception_policy_across_platforms(self):
        for sep in ('/','\\'):
            self.assertTrue(immutable_hashes_match({sep.join(['specs','test.md']):False,sep.join(['simulation','pyrocast_cfbt','conditions.py']):False,'engine.exe':True}))
    def test_engine_and_model_changes_still_rejected(self):
        for path in ('engine.exe','simulation/pyrocast_cfbt/deck.py','simulation\\pyrocast_cfbt\\model.py','specs-other/file'):
            self.assertFalse(immutable_hashes_match({path:False}))

if __name__=='__main__':unittest.main()
