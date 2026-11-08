import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from pyrocast_cfbt.native import execute,NativeRunInterrupted


class Heartbeat(unittest.TestCase):
    def run_fake(self,advancing):
        with tempfile.TemporaryDirectory() as name:
            folder=Path(name);clock=[0.]
            class Process:
                returncode=0
                killed=False
                waits=0
                def poll(self):return 0 if self.waits>=5 or self.killed else None
                def kill(self):self.killed=True
                def wait(self,timeout=None):
                    if self.killed:return 0
                    self.waits+=1;clock[0]+=4
                    assert (folder/'case.query').exists()
                    (folder/'case.query').unlink()
                    # Rounded simulation time remains unchanged while accepted steps advance.
                    (folder/'case.status').write_text(f'Status at T = 1.42E+03 DT = 1E-04 STEPS = {100+self.waits if advancing else 100}')
            process=Process()
            def launch(*args,**kwargs):
                (folder/'case.status').write_text('Status at T = 1.42E+03 DT = 1E-04 STEPS = 100')
                (folder/'case.log').write_text('NORMAL EXIT')
                return process
            with patch('pyrocast_cfbt.native.time.monotonic',side_effect=lambda:clock[0]),patch('pyrocast_cfbt.native.subprocess.Popen',side_effect=launch),patch('pyrocast_cfbt.native.load_result',return_value={'compartments':{'Time':np.array([0,3600])}}),patch('pyrocast_cfbt.validation.validate_native',return_value={'status':'valid'}):
                if advancing:
                    execute(Path(__file__),folder,'&HEAD /','',3600,50,6)
                    self.assertFalse(process.killed)
                    self.assertTrue((folder/'completed.json').exists())
                    self.assertEqual(json.loads((folder/'execution-state.json').read_text())['accepted_steps'],104)
                else:
                    with self.assertRaises(NativeRunInterrupted) as error:execute(Path(__file__),folder,'&HEAD /','',3600,50,6)
                    self.assertEqual(error.exception.reason,'native_progress_stalled')
                    self.assertTrue(process.killed);self.assertFalse((folder/'completed.json').exists())
    def test_accepted_steps_prevent_false_stall(self):self.run_fake(True)
    def test_real_stall_still_terminates_owned_process(self):self.run_fake(False)
