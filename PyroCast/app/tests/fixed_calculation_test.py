"""Engine boundary: frozen saved inputs, CFAST-only requests, no real simulation."""
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
        import gzip
        cls.temp=tempfile.TemporaryDirectory(prefix='firelapse-fixed-contract-')
        cls.addClassCleanup(cls.temp.cleanup)
        folder=Path(cls.temp.name)
        fixture=ROOT/'app/tests/fixtures/fixed-calculation'
        def saved(name):return json.loads(gzip.decompress((fixture/(name+'.gz')).read_bytes()))
        config=saved('config.json');fixed=config['fixed_state'];cls.sha=fixed['building_sha256']
        job=folder/'jobs/parkmarine'/fixed['job_id'];sample=job/fixed['sample_id']
        for name in ('input.json','request.json'):atomic_json(job/name,saved(name))
        for name in ('sample.json','summary.json'):atomic_json(sample/name,saved(name))
        atomic_json(folder/'fixed.json',config)
        engine=folder/'test-engine.exe';engine.write_bytes(b'test marker; execution is mocked')
        for patcher in (patch.object(model_mc,'JOBS',folder/'jobs'),patch.object(model_mc,'config_path',return_value=folder/'fixed.json'),patch.object(calc,'ENGINE',engine),patch('cfast_calculation.ENGINE',engine)):
            patcher.start();cls.addClassCleanup(patcher.stop)
        cls.source,cls.fixed,cls.req,cls.raw=calc.context(cls.sha,'parkmarine')
        cls.original=read(cls.source.parent/'input.json')

    def test_loaded_case_identity_is_catalog_id_without_rewriting_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'playback.json'
            raw=dict(building_sha256='abc',case_id='new-run',fire_input={})
            atomic_json(path,raw);before=path.read_bytes()
            with patch.object(calc,'playback_file',return_value=path):
                value=calc.playback('abc','calc-123-abcdef')
            self.assertEqual(value['case_id'],'calc-123-abcdef')
            self.assertEqual(path.read_bytes(),before)

    def body(self, **kw):
        return dict(engine='cfast',room=self.req['room'],floor='5F',duration_s=self.req['duration_s'],**kw)

    def test_native_smoke_uses_validation_csv_units(self):
        import numpy as np
        from fixed_native_playback import smoke_optics
        columns={'Time':np.array([0.,10.]),'ULOD_1':np.array([0.,264.6903])}
        upper,lower=smoke_optics(columns,{'ULOD_1':'R1'},{'ULOD_1':'mg/m^3'},'R1',1)
        np.testing.assert_allclose(upper,[0.,1.])
        self.assertEqual(lower,[None,None])
        with self.assertRaisesRegex(ValueError,'room identity'):
            smoke_optics(columns,{'ULOD_1':'R2'},{'ULOD_1':'mg/m^3'},'R1',1)

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

    def test_new_lite_request_is_rejected_without_reusing_saved_result(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'app/tests') as tmp:
            with patch.object(calc,'JOBS',Path(tmp)),patch.object(model_mc,'prepare_request',return_value=({},self.original)),patch('pyrocast_cfbt.native.execute') as execute:
                with self.assertRaisesRegex(ValueError,'CFAST'):
                    calc.reserve(self.sha,{**self.body(),'engine':'lite'},'parkmarine')
                execute.assert_not_called()
                self.assertEqual(calc.cases(self.sha),[])

    def test_native_single_call_exact_input_and_failure(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'app/tests') as tmp:
            with patch.object(calc,'JOBS',Path(tmp)),patch.object(model_mc,'prepare_request',return_value=({},self.original)),patch('pyrocast_cfbt.native.execute',side_effect=RuntimeError('native fixture timeout')) as execute:
                f=calc.reserve(self.sha,self.body(),'parkmarine');calc.compute(f)
                self.assertEqual(execute.call_count,1)
                args=execute.call_args.args
                from cfast_calculation import runtime_settings
                self.assertEqual(args[0],calc.ENGINE);self.assertNotIn('&CFBT',args[2]);self.assertEqual(args[4:6],(3600,runtime_settings()['max_wall_s']))
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
        native['run']={'engine_sha256':'saved-csv-fixture'}
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
