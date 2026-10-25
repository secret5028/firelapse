import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock
from pyrocast_cfbt.diagnostics import prepare_bulk_pair,run_bulk_pair
from pyrocast_cfbt.native import execute,NativeRunInterrupted

class IsolationTests(unittest.TestCase):
    def setUp(self):
        base=Path(__file__).resolve().parents[1]/'results/unit_tmp'
        base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source';self.source.mkdir()
        self.engine=self.root/'engine';self.engine.write_bytes(b'test engine')
        self.deck=b'&TIME SIMULATION=3600 /\r\n&FIRE ID="F1" /\r\n'
        self.side=b'&CFBT enabled=.TRUE. bulk_enabled=.TRUE. vent_gate_enabled=.FALSE. oxygen_min_vol=.12 /\r\n'
        (self.source/'case.in').write_bytes(self.deck);(self.source/'case.cfbt').write_bytes(self.side)
        self.out=self.root/'pair'

    def test_pair_freezes_native_deck_and_changes_only_bulk_flag(self):
        prepare_bulk_pair(self.source,self.out,self.engine)
        for name in ('bulk_on','bulk_off'):
            self.assertEqual((self.out/name/'case.in').read_bytes(),self.deck)
        self.assertEqual((self.out/'bulk_off/case.cfbt').read_bytes(),self.side.replace(b'bulk_enabled=.TRUE.',b'bulk_enabled=.FALSE.'))
        process=Mock();process.poll.return_value=None
        folder=self.out/'bulk_off'
        with patch('pyrocast_cfbt.native.subprocess.Popen',return_value=process):
            with self.assertRaises(TimeoutError):
                execute(self.engine,folder,(folder/'case.in').read_text(),(folder/'case.cfbt').read_text(),3600,0,preserve_input_files=True)
        self.assertEqual((folder/'case.in').read_bytes(),self.deck)
        self.assertEqual((self.source/'case.cfbt').read_bytes(),self.side)

    def test_diagnostic_has_two_calls_no_retry_and_explicit_incomplete_result(self):
        prepare_bulk_pair(self.source,self.out,self.engine)
        with patch('pyrocast_cfbt.diagnostics.execute',side_effect=NativeRunInterrupted('native_progress_stalled',1570,3600,145)) as call:
            report=run_bulk_pair(self.out,600)
        self.assertEqual(call.call_count,2)
        self.assertEqual(report['cases']['bulk_on']['status'],'solver_stalled')
        self.assertEqual(report['cases']['bulk_off']['status'],'solver_stalled')
        self.assertFalse((self.out/'playback.json').exists())

    def test_modified_pair_rejected_before_any_engine_call(self):
        prepare_bulk_pair(self.source,self.out,self.engine)
        (self.out/'bulk_off/case.in').write_text('&TIME SIMULATION=30 /')
        with patch('pyrocast_cfbt.diagnostics.execute') as call:
            with self.assertRaisesRegex(ValueError,'Frozen deck'):run_bulk_pair(self.out)
        call.assert_not_called()
