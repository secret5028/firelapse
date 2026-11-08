import sys,unittest,tempfile,json,copy
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation')]
from result_catalog import atomic_json,read
import cfast_calculation as native
import fixed_calculation as fixed
import model_simulation as single
import run_cfast_mc as mc


class CfastOnly(unittest.TestCase):
    def test_old_engine_requests_rejected_before_reading_results(self):
        with patch.object(fixed,'context',side_effect=AssertionError('must not access saved data')):
            with self.assertRaisesRegex(ValueError,'CFAST'):
                fixed.prepare('sha',dict(engine='lite',room='R1',floor='B1',duration_s=1800))

    def test_fixed_and_library_use_same_native_service(self):
        with tempfile.TemporaryDirectory() as name:
            p=Path(name)
            atomic_json(p/'input.json',{'test':'unchanged'})
            atomic_json(p/'request.json',dict(engine='cfast',floor='B1',room='CAD_B1_R1',building='test',building_sha256='sha',opening_state='closed'))
            atomic_json(p/'fixed-state.json',dict(states={}))
            pb=dict(engine_kind='cfast_native',complete=True,physical_validation={'status':'valid'})
            with patch.object(native,'run_case',return_value=(pb,{},{})) as run:
                fixed.compute(p);self.assertEqual(read(p/'status.json')['state'],'complete');self.assertEqual(run.call_count,1)
                single.execute(p);self.assertEqual(run.call_count,2)
                self.assertEqual(read(p/'input.json'),{'test':'unchanged'})

    def test_new_mc_runs_native_for_every_sample_and_preserves_old_result(self):
        raw=json.loads((ROOT/'fixtures/room_rule_benchmark_3room_b3.json').read_text('utf8'));raw['duration_s']=1800
        raw['cad']=dict(building_sha256='sha')
        for vent in raw['openings']:vent['kind']='door'
        with tempfile.TemporaryDirectory() as name:
            p=Path(name);old=p/'historical-playback.json';old.write_bytes(b'old Lite result unchanged')
            atomic_json(p/'input.json',raw);atomic_json(p/'request.json',dict(room='R1',building_sha256='sha',samples=3,seed=15,duration_s=1800))
            called=[]
            def run(data,folder,**kw):
                sample=kw['sample'];called.append(copy.deepcopy(sample))
                s=dict(sample_id=sample['id'],kind=sample['kind'],complete=True,ranking_eligible=sample['id']!='S01',
                    phenomena={k:dict(ever_room_count=0,first_s=None,score_max=.5) for k in mc.aggregate([])['condition_sample_rates_random_only']},
                    original_room_count=3,boundary_room_count=0,burning_original_rooms=['R1'],smoke_risk_rooms=[])
                return {},{},s
            with patch('runtime_storage.is_result_path',return_value=True),patch('runtime_storage.result_relative',side_effect=lambda path:path.relative_to(p)),patch.object(mc,'run_case',side_effect=run):
                result=mc.run_batch(p/'request.json',p)
                self.assertEqual(len(called),3);self.assertEqual(result['engine_kind'],'cfast_native')
                self.assertEqual(result['excluded_physically_invalid'],1);self.assertEqual(result['rates']['FO']['denominator_completed_random'],1)
                self.assertEqual(old.read_bytes(),b'old Lite result unchanged')
                with self.assertRaises(RuntimeError):mc.run_batch(p/'request.json',p)

    def test_null_not_applicable_does_not_make_native_mc_unknown(self):
        from export_ui_attention import summarize
        r=dict(engine_kind='cfast_native',t=[0,1],room_summary=[dict(cell='R1',original_room='R1')],
            shared_conditions={'rooms':{'R1':{k:dict(status='evaluated',scores={'degree':[None,None]}) for k in ('FO','FGI','backdraft')}}})
        self.assertEqual(summarize(r)['unknown_rooms'],[])
        r['shared_conditions']['rooms']['R1']['FO']['status']='physically_invalid'
        self.assertEqual(summarize(r)['unknown_rooms'],['R1'])

    def test_facade_will_not_overwrite_completed_playback(self):
        with tempfile.TemporaryDirectory() as name:
            p=Path(name);(p/'playback.json').write_bytes(b'preserve')
            with self.assertRaisesRegex(ValueError,'덮어쓰지'):native.run_case({},p)
            self.assertEqual((p/'playback.json').read_bytes(),b'preserve')

if __name__=='__main__':unittest.main()
