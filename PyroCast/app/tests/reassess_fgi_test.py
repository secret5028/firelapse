"""Reassessing stored FGI records gives what the evaluator gives for the same mixture."""
import copy
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'simulation')]
from pyrocast_cfbt.criteria import evaluate_cell
from reassess_fgi import potential, remote_ignition


class ReassessFgiTest(unittest.TestCase):
    def test_stored_factors_under_the_new_gate_match_the_evaluator(self):
        model = dict(ambient_C=20, rooms=[dict(id='Fire', size_m=[4, 4, 3])], openings=[], gas={},
                     fuel_groups=[dict(room='Fire', initial_time_s=0, heat_of_combustion_kJ_kg=18100)])
        t = np.arange(6.)*5; temperature = [100, 200, 300, 600, 200, 200]; interface = [1, 1, 1, 1, 2.9, 1]
        new = evaluate_cell(model, model['rooms'][0], t, temperature, interface, [15]*6, [.1, .05, np.nan, .1, .1, .1], [100]*6)['FGI']
        self.assertEqual(new['gate'], [True, True, True, False, None, True])
        # What the earlier definition stored for an origin room: factors kept, no score.
        old = copy.deepcopy(new); n = len(t)
        old['gate'] = [None if g is None else False for g in new['gate']]
        old['proximity'] = [None]*n; old['scores']['degree'] = [None]*n
        got = potential(old, np.array([g is not None for g in old['gate']]), np.array(temperature) < 520, t)
        for key in ('gate', 'proximity', 'all_met', 'first_met_s', 'occurred', 'revision', 'occurrence_assessed'):
            self.assertEqual(got[key], new[key], key)
        self.assertEqual(got['scores'], new['scores'])
        self.assertGreaterEqual(got['scores']['degree'][0], 1)

    def test_remote_ignition_follows_the_new_scores_and_keeps_stored_ignition(self):
        state = dict(excluded_origin=False, threshold=100., ignition=[True, True, False, True], active=[None]*4, first_active_s=None, physical_room='A')
        got = remote_ignition(state, [.5, 1.2, 1.5, None], [0., 5., 10., 15.])
        self.assertEqual(got['active'], [False, True, False, None]); self.assertEqual(got['first_active_s'], 5.)
        self.assertEqual(got['ignition'], state['ignition'])
        origin = remote_ignition({**state, 'excluded_origin': True}, [.5, 1.2, 1.5, None], [0., 5., 10., 15.])
        self.assertEqual(origin['active'], [False]*4); self.assertIsNone(origin['first_active_s'])


if __name__ == '__main__':
    unittest.main()
