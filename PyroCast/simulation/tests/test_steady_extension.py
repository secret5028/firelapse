"""Quasi-steady extension: detection, extension rules and file round trip. Synthetic tables, no native solver runs."""
import json, tempfile, unittest
from pathlib import Path
import numpy as np
from pyrocast_cfbt import steady_extension as se
from pyrocast_cfbt.native import read_native_csv, validated_result

NAMES = ['Time', 'ULT_1', 'LLT_1', 'HGT_1', 'PRS_1', 'ULO2_1', 'IGN_1', 'PYROL_1', 'HRR_E1', 'HRR_1', 'TRGFEDG_1']
IDS = ['Time', 'R', 'R', 'R', 'R', 'R', 'F_Fuel_R', 'F_Fuel_R', 'F_Fuel_R', 'F_Fuel_R', 'T']
UNITS = ['s', 'C', 'C', 'm', 'Pa', 'mol_frac', '', 'kg/s', 'W', 'W', '']


def deck(decay_at=None):
    rows = [(0, 0), (60, 5000)] + ([(decay_at, 5000), (decay_at+600, 0)] if decay_at else [(9000, 5000)])
    return ("&FIRE ID='F_Fuel_R' COMP_ID='R' FIRE_ID='F_Fuel_R' LOCATION=1,1 IGNITION_CRITERION='TIME' SETPOINT=0 /\n"
            "&TABL ID='F_Fuel_R' LABELS='TIME','HRR','HEIGHT','AREA' /\n"
            + ''.join(f"&TABL ID='F_Fuel_R' DATA={t},{q},0,1 /\n" for t, q in rows))


def table(until=1500., exponent=0.2, burned=1.2e6):
    """Oxygen-limited plateau: 5 MW prescribed, a constant 1.2 MW burns, gas heats as t^exponent."""
    t = np.arange(0., until+1, 5.); ramp = np.minimum(t/60., 1.)
    hot = 20+300*(np.maximum(t, 1.)/1000.)**exponent*ramp
    cols = [t, hot, 20+0.6*(hot-20), np.where(t < 100, 3-t*.029, .1), 40*ramp, np.where(t < 300, .2-t*6.5e-4, .005),
            np.ones_like(t), .3*ramp, 5e6*ramp, burned*ramp, t*1e-4]
    return np.column_stack(cols)


def write(folder, data, partial=True):
    lines = [','.join(NAMES), ','.join(NAMES), ','.join(IDS), ','.join(UNITS)]+[','.join('%.12E' % v for v in row) for row in data]
    if partial: lines.append('%.12E,2.0E+01' % (data[-1, 0]+5))     # the solver was stopped while writing
    (folder/'case_compartments.csv').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    zone = [','.join(UNITS[:5]), ','.join(NAMES[:5])]+[','.join('%.12E' % v for v in row[:5]) for row in data]
    (folder/'case_zone.csv').write_text('\n'.join(zone)+'\n', encoding='utf-8')


class SteadyExtension(unittest.TestCase):
    def setUp(self): self.cfg = se.settings()

    def test_detects_a_constant_fire_and_rejects_changing_ones(self):
        data = table()
        self.assertTrue(se.assess(NAMES, IDS, data, deck(), self.cfg)['steady'])
        self.assertFalse(se.assess(NAMES, IDS, data[:100], deck(), self.cfg)['steady'])          # shorter than three windows
        growing = data.copy(); growing[:, 9] = 4e3*growing[:, 0]
        self.assertIn('heat release still changing', se.assess(NAMES, IDS, growing, deck(), self.cfg)['reasons'])
        runaway = data.copy(); runaway[-60:, 1] += np.linspace(0, 80, 60)**1.5/10
        self.assertTrue(any('accelerating' in s for s in se.assess(NAMES, IDS, runaway, deck(), self.cfg)['reasons']))
        moving = data.copy(); moving[-60:, 4] += np.linspace(0, 30, 60)
        self.assertIn('pressure still moving', se.assess(NAMES, IDS, moving, deck(), self.cfg)['reasons'])

    def test_extension_rules(self):
        data = table(); new_t = np.arange(1505., 3600.1, 5.)
        fire = se.future_fire(NAMES, IDS, data, deck(), new_t)
        self.assertTrue(fire['known']); self.assertTrue(np.all(fire['f'] == 1))
        rows, note = se.extend(NAMES, UNITS, data, new_t, fire, self.cfg)
        self.assertAlmostEqual(rows[-1, 0], 3600.)
        self.assertLess(abs(rows[-1, 1]-(20+300*3.6**.2)), 3.)                 # wall-heating power law recovered
        for i in (3, 4, 5, 9): self.assertTrue(np.all(rows[:, i] == data[-1, i]))   # layer, pressure, oxygen, heat release held
        self.assertAlmostEqual(rows[-1, 10], 0.36, places=6)                   # cumulative dose keeps its rate
        self.assertEqual(note['counts']['temperature'], 2)

    def test_planned_decay_lowers_heat_release_and_temperature(self):
        data = table(); new_t = np.arange(1505., 3600.1, 5.)
        fire = se.future_fire(NAMES, IDS, data, deck(decay_at=3000), new_t)
        steady = se.future_fire(NAMES, IDS, data, deck(), new_t)
        self.assertEqual(fire['f'][int(np.searchsorted(new_t, 3000))], 1.)     # still oxygen-limited at the start of the decay
        self.assertAlmostEqual(fire['f'][-1], 0.)
        low = se.extend(NAMES, UNITS, data, new_t, fire, self.cfg)[0]; high = se.extend(NAMES, UNITS, data, new_t, steady, self.cfg)[0]
        self.assertEqual(low[-1, 9], 0.); self.assertLess(low[-1, 1], high[-1, 1])
        self.assertAlmostEqual(fire['requested'][8][-1], 0.)

    def test_pace(self):
        slow = [(0., 0.), (600., 900.), (900., 990.)]
        self.assertTrue(se.overrun(slow, 3600, 4200, self.cfg))
        self.assertFalse(se.overrun([(0., 0.), (600., 3000.)], 3600, 4200, self.cfg))
        self.assertFalse(se.overrun([(0., 0.), (100., 5.)], 3600, 4200, self.cfg))       # too early to judge

    def test_files_are_extended_and_the_native_prefix_is_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp); write(folder, table()); (folder/'case.in').write_text(deck(), encoding='ascii')
            original = (folder/'case_compartments.csv').read_bytes()
            self.assertTrue(se.probe(folder, deck(), 3600, self.cfg))
            info = se.finish(folder, deck(), 3600, self.cfg, trigger='wall_time_budget', exit_kind='stopped_by_request', wall_seconds=4200., accepted_steps=9)
            self.assertEqual((info['native_until_s'], info['horizon_s'], info['extended_samples']), (1500., 3600., 420))
            self.assertEqual((folder/'native-prefix/case_compartments.csv').read_bytes(), original)
            self.assertEqual(json.loads((folder/'steady-extension.json').read_text(encoding='utf-8'))['revision'], se.REVISION)
            for name in ('compartments', 'zone'):
                values, _, _ = read_native_csv(folder/f'case_{name}.csv')
                self.assertEqual((len(values['Time']), values['Time'][-1]), (721, 3600.))
            kept, _, _ = read_native_csv(folder/'case_compartments.csv', 1500.)
            self.assertTrue(np.allclose(kept['ULT_1'], table()[:, 1], rtol=1e-11, atol=0))   # native samples untouched
            self.assertTrue(se.notice(info).startswith(se.NOTICE)); self.assertIn('25:00', se.notice(info))

    def test_an_unsteady_run_is_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp); data = table(); data[:, 9] = 4e3*data[:, 0]; write(folder, data)
            before = {p.name: p.read_bytes() for p in folder.iterdir()}
            self.assertFalse(se.probe(folder, deck(), 3600, self.cfg))
            self.assertIsNone(se.finish(folder, deck(), 3600, self.cfg, trigger='wall_time_budget', exit_kind='x', wall_seconds=1., accepted_steps=1))
            self.assertEqual({p.name: p.read_bytes() for p in folder.iterdir()}, before)

    def test_extended_runs_are_never_reported_valid(self):
        info = dict(revision=se.REVISION, trigger='wall_time_budget', native_until_s=1500., horizon_s=3600.)
        checked = se.qualify(dict(status='valid', passed=True, reasons=[], unknown=[]), info)
        self.assertEqual((checked['status'], checked['passed'], checked['unknown']), ('unverified', False, ['quasi_steady_extension']))
        self.assertEqual(se.qualify(dict(status='physically_invalid', passed=False, reasons=[1], unknown=[]), info)['status'], 'physically_invalid')


if __name__ == '__main__': unittest.main()
