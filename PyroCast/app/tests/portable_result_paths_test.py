"""Bundled results remain readable from deep Windows extraction folders."""
import hashlib,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import runtime_storage as storage
import fixed_calculation as calc
from result_catalog import atomic_json,_io_path

class PortableResultPaths(unittest.TestCase):
 def test_deep_bundled_fixed_result_is_listed_and_read_without_rewriting(self):
  temp_base=('\\\\?\\'+tempfile.gettempdir()) if os.name=='nt' else tempfile.gettempdir()
  with tempfile.TemporaryDirectory(dir=temp_base) as temp:
   root=Path(temp.removeprefix('\\\\?\\'))/('a'*60)/('b'*60)/('c'*40)
   old=root/'app/simulation/results';new=root/'data/results'
   sha='a'*64;case='calc-1234567890123456789-abcdef12'
   folder=old/'fixed-calculations'/sha/case;file=folder/'playback.json'
   value=dict(label='retained',building_sha256=sha,engine_kind='cfast_native',complete=True,
              time_s=[0,60],rooms=[],solvers={},fire_input={})
   atomic_json(file,value);atomic_json(folder/'status.json',dict(state='complete'))
   before=hashlib.sha256(_io_path(file).read_bytes()).hexdigest()
   self.assertGreater(len(str(file)),260)
   with patch.object(storage,'RESULTS',new),patch.object(storage,'LEGACY_RESULTS',old),patch.object(calc,'JOBS',new/'fixed-calculations'):
    self.assertEqual(storage.locate(new/'fixed-calculations'/sha/case),folder)
    self.assertEqual([r['id'] for r in calc.cases(sha)],[case])
    self.assertEqual(calc.playback(sha,case),{**value,'case_id':case})
    self.assertEqual(json.loads(storage.playback_path(file).read_text('utf8')),value)
   self.assertEqual(hashlib.sha256(_io_path(file).read_bytes()).hexdigest(),before)

if __name__=='__main__':unittest.main()
