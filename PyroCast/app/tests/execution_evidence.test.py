"""Provenance rejection tests; fixtures only, no solver or production mutations."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools'))
import execution_evidence as e
import runtime_storage
from result_catalog import atomic_json, read
from saved_case_reuse import describe


class Evidence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT/'simulation/results', prefix='server_stage5_test')
        self.root = Path(self.tmp.name)
        self.folder = self.root/'simulation/results/lite_mc_jobs/job/S00'
        self.job = self.folder.parent
        self.root_patch = patch.object(e, 'ROOT', self.root); self.root_patch.start()
        self.storage_patch=patch.object(runtime_storage,'LEGACY_RESULTS',self.root/'simulation/results');self.storage_patch.start()
        self.addCleanup(self.storage_patch.stop)
        self.current = patch.object(e, '_current_matches'); self.check = self.current.start()
        self.request = dict(room='R3', samples=2, seed=1, duration_s=3600, building_sha256='building')
        self.raw = dict(openings=[dict(id='D0', door_class='fire', door_class_confidence='user')])
        for path, value in [
            (self.job/'request.json', self.request),
            (self.job/'started.json', dict(sha256={'simulation\\pyrocast_lite\\core.py':'then'},
                                          parameters={'oxygen_inventory_mode':False}, building_sha256='building')),
            (self.job/'input.json', self.raw),
            (self.folder/'sample.json', dict(id='S00', scenario=self.raw)),
            (self.folder/'summary.json', dict(complete=True, selected_attempt='BDF')),
            (self.folder/'BDF/rule_manifest.json', dict(rule_settings={'temperature_C':600})),
            (self.folder/'playback.json', dict(complete=True)),
            (self.folder/'result.json', dict(ok=True)),
            (self.folder/'index-summary.json', dict(complete=True))]:
            atomic_json(path, value)
        self.proof = e.write_mc(self.folder)

    def tearDown(self):
        self.current.stop(); self.root_patch.stop()
        assert self.root.resolve().is_relative_to((ROOT/'simulation/results').resolve())
        self.tmp.cleanup()

    def test_save_uses_then_values_and_reuse_label(self):
        self.assertEqual(self.proof['engine_files']['simulation/pyrocast_lite/core.py'], 'then')
        self.assertEqual(self.proof['applied_user_door_overrides'], {'D0':'fire'})
        self.assertFalse(self.proof['provenance']['backfilled'])
        self.assertTrue(e.verify(self.folder, 'building')[0])
        row = dict(id='new', path=str(self.folder/'playback.json'))
        self.assertEqual(describe(row, 'lite', 'building', None, None)['label'], '동등 · 검증된 결과 재사용')

    def test_missing_proof_and_building_mismatch(self):
        self.assertFalse(e.verify(self.folder, 'other')[0])
        (self.folder/'execution-evidence.json').unlink()
        row = dict(id='old', path=str(self.folder/'playback.json'))
        self.assertEqual(describe(row, 'lite', 'building', None, None)['reuse_kind'], 'historical_result')

    def test_changed_saved_files_rejected(self):
        for name in self.proof['files']:
            path = self.folder/name; original = path.read_bytes()
            path.write_bytes(original+b' ')
            self.assertFalse(e.verify(self.folder, 'building')[0], name)
            path.write_bytes(original)

    def test_forged_or_partial_evidence_rejected(self):
        for key in ('engine_sha256', 'input_snapshot_sha256', 'rule_settings', 'door_corrections'):
            changed = {**self.proof, key: None}
            atomic_json(self.folder/'execution-evidence.json', changed)
            self.assertFalse(e.verify(self.folder, 'building')[0], key)
        atomic_json(self.folder/'execution-evidence.json', {**self.proof, 'files':{}})
        self.assertFalse(e.verify(self.folder, 'building')[0])

    def test_current_inputs_changed_downgrades_without_solver(self):
        for reason in ('engine changed', 'input changed', 'door override changed', 'rules changed'):
            self.check.side_effect = ValueError(reason)
            row = dict(id='new', path=str(self.folder/'playback.json'))
            value = describe(row, 'lite', 'building', None, None)
            self.assertFalse(value['equivalent']); self.assertEqual(value['solver_runs'], 0)
            self.assertEqual(value['reason'], reason)


if __name__ == '__main__':
    unittest.main(verbosity=2)
