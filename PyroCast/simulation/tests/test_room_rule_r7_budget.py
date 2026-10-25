import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
import run_room_rule_r7 as runner
from pyrocast_cfbt.native import NativeRunInterrupted
class R7BudgetTests(unittest.TestCase):
 def test_full_budget_without_legacy_stall_watchdog_or_retry(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'simulation/results') as tmp:
   folder=Path(tmp)/'case'
   with patch.object(runner,'OUT',Path(tmp)),patch.object(runner,'make_deck',return_value=''),patch.object(runner,'execute',side_effect=NativeRunInterrupted('wall_time_budget',0,3600,1800)) as execute:
    report=runner.run_case(folder,{'duration_s':3600},[],{},timeout=1800)
   self.assertFalse(report['complete']);self.assertEqual(execute.call_count,1)
   self.assertEqual(execute.call_args.args[-1],1800)
   self.assertEqual(execute.call_args.kwargs['stall_timeout_s'],0)
if __name__=='__main__':unittest.main()
