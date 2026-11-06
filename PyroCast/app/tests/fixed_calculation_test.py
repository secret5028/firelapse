"""Engine boundary: frozen inputs, zero-run reuse, one native call, no real simulation."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation'),str(ROOT/'simulation/deps')]
import fixed_calculation as calc
import model_mc
from result_catalog import atomic_json, read


class FixedCalculationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sha=model_mc.sim.fingerprint('parkmarine')
        cls.source,cls.fixed,cls.req,cls.raw=calc.context(cls.sha,'parkmarine')
        cls.original=read(cls.source.parent/'input.json')

    def body(self, **kw):
        return dict(engine='cfast',room=self.req['room'],floor='5F',duration_s=self.req['duration_s'],**kw)

    def test_frozen_input_no_change(self):
        with patch.object(model_mc,'prepare_request',return_value=({},copy.deepcopy(self.original))):
            _,_,_,raw=calc.prepare(self.sha,self.body(),'parkmarine')
            self.assertEqual(raw,self.raw)
            for vent in raw['openings']:
                self.assertEqual(vent['schedule'][0][1],self.fixed['states'][vent['id']]['effective_fraction'])

    def test_invalid_stale_and_cross_building_rejected(self):
        for key,value in [('engine','other'),('room','CAD_5F_R0'),('floor','6F'),('duration_s',1800)]:
            with self.assertRaises(ValueError):calc.prepare(self.sha,{**self.body(),key:value},'parkmarine')
        with self.assertRaises(ValueError):calc.context('wrong-building','parkmarine')
        changed=copy.deepcopy(self.original);changed['fuel_groups'][0]['energy_MJ']+=1
        with patch.object(model_mc,'prepare_request',return_value=({},changed)):
            with self.assertRaisesRegex(ValueError,'가연물'):calc.prepare(self.sha,self.body(),'parkmarine')

    def test_missing_fixed_and_path_rejected(self):
        with patch.object(calc,'read',return_value={}):
            with self.assertRaises(ValueError):calc.context(self.sha,'parkmarine')
        with self.assertRaises(ValueError):calc.playback(self.sha,'../../escape')

    def test_lite_reuse_runs_no_solver(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'app/tests') as tmp:
            with patch.object(calc,'JOBS',Path(tmp)),patch.object(model_mc,'prepare_request',return_value=({},self.original)),patch('pyrocast_cfbt.native.execute') as execute:
                f=calc.reserve(self.sha,{**self.body(),'engine':'lite'},'parkmarine');calc.compute(f)
                status=read(f/'status.json');self.assertEqual(status['state'],'complete');self.assertEqual(status['solver_runs'],0)
                execute.assert_not_called()
                pb=calc.playback(self.sha,f.name);source=read(self.source/'playback.json')
                self.assertEqual(pb['solvers'],source['solvers']);self.assertEqual(pb['display_opening_state']['states'],self.fixed['states'])
                self.assertEqual(calc.cases(self.sha)[0]['id'],f.name)

    def test_native_single_call_exact_input_and_failure(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'app/tests') as tmp:
            with patch.object(calc,'JOBS',Path(tmp)),patch.object(model_mc,'prepare_request',return_value=({},self.original)),patch('pyrocast_cfbt.native.execute',side_effect=RuntimeError('native fixture timeout')) as execute:
                f=calc.reserve(self.sha,self.body(),'parkmarine');calc.compute(f)
                self.assertEqual(execute.call_count,1)
                args=execute.call_args.args
                self.assertEqual(args[0],calc.ENGINE);self.assertNotIn('&CFBT',args[2]);self.assertEqual(args[4:6],(3600,1800))
                self.assertEqual(read(f/'input.json'),self.raw)
                self.assertEqual(read(f/'status.json')['state'],'failed');self.assertFalse((f/'playback.json').exists())
                self.assertEqual(calc.cases(self.sha),[])

    def test_worker_admission(self):
        with patch.object(model_mc.sim,'_active','MC'):
            with self.assertRaises(RuntimeError):calc.start_model('parkmarine',self.body())

    def test_saved_native_csv_exact_mapping(self):
        import numpy as np
        from pyrocast_cfbt.native import read_native_csv
        from fixed_native_playback import package
        folder=ROOT/'simulation/results/hotel-native-compare-20261105/5F'
        if not (folder/'case_compartments.csv').exists(): self.skipTest('SKIP: evidence folder missing')
        native={}
        for key,suffix in [('zone','zone'),('compartments','compartments'),('native_vents','vents')]:
            native[key],native[key+'_ids'],native[key+'_units']=read_native_csv(folder/('case_'+suffix+'.csv'))
        template=read(ROOT/'simulation/results/overnight-20261104/parkmarine/5F/playback.json')
        model=read(folder/'scenario.json');pb=package(model,native,template,folder)
        self.assertEqual(len(pb['rooms']),23);self.assertEqual(pb['engine_kind'],'cfast_native')
        for i,room in enumerate(model['rooms'],1):
            s=pb['solvers'][room['id']]
            self.assertEqual(s['Tu'],native['compartments'][f'ULT_{i}'].tolist())
            self.assertEqual(s['Ou'],native['compartments'][f'ULO2_{i}'].tolist())
            np.testing.assert_array_equal(s['Qvent_kW'],native['compartments'][f'DJET_{i}']/1000)
            self.assertTrue(all(v is None for v in s['Qbulk_kW']))
        self.assertEqual(set(pb['solvers']),{r['id'] for r in model['rooms']})


if __name__=='__main__':unittest.main()
