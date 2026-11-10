"""r19 distribution and no-MC boundaries; no numerical solver is run."""
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation')]
from distribution_results import filter_bundle_results
import fixed_calculation as calc

class DistributionNativeTests(unittest.TestCase):
 def test_lite_samples_removed_native_and_evidence_unchanged(self):
  with tempfile.TemporaryDirectory() as tmp:
   app=Path(tmp);root=app/'simulation/results';job=root/'lite_mc_jobs/models/hotel/mc-123-abc'
   for sid,engine in [('S00','pyrocast_lite'),('S01','cfast_native')]:
    p=job/sid;p.mkdir(parents=True);(p/'playback.json').write_text(json.dumps(dict(engine_kind=engine)),'utf8');(p/'result.json').write_text(json.dumps(dict(engine_kind=engine)),'utf8')
   (job/'mc-summary.json').write_text('{}','utf8');(job/'request.json').write_text('{}','utf8')
   evidence=job/'S01/CFAST/case.log';evidence.parent.mkdir();evidence.write_bytes(b'unchanged native execution evidence')
   before={p:p.read_bytes() for p in (job/'S01').rglob('*') if p.is_file()}
   report=filter_bundle_results(app)
   self.assertEqual(len(report['removed_lite_cases']),1)
   self.assertFalse((job/'S00/playback.json').exists());self.assertFalse((job/'mc-summary.json').exists())
   for p,b in before.items():self.assertEqual(p.read_bytes(),b)
   self.assertTrue((job/'request.json').exists())
 def test_nested_cases_keep_their_own_engine_identity(self):
  with tempfile.TemporaryDirectory() as tmp:
   app=Path(tmp);root=app/'simulation/results'
   for rel,engine in [('lite','lite'),('lite/native','cfast_native'),('native','cfast_native'),('native/lite','pyrocast_lite')]:
    folder=root/rel;folder.mkdir(parents=True,exist_ok=True)
    (folder/'playback.json').write_text(json.dumps(dict(engine_kind=engine)),'utf8')
   filter_bundle_results(app)
   self.assertTrue((root/'lite/native/playback.json').exists());self.assertTrue((root/'native/playback.json').exists())
   self.assertFalse((root/'lite/playback.json').exists());self.assertFalse((root/'native/lite/playback.json').exists())
 def test_factory_input_retained_without_lite_result(self):
  with tempfile.TemporaryDirectory() as tmp:
   app=Path(tmp);p=app/'simulation/results/lite_v8_example';p.mkdir(parents=True)
   (p/'playback.json').write_text('{"engine_kind":"lite"}','utf8');(p/'source-scenario.json').write_bytes(b'{"original_input":true}')
   filter_bundle_results(app)
   self.assertEqual((p/'source-scenario.json').read_bytes(),b'{"original_input":true}')
 def test_empty_result_geometry_has_no_fabricated_measurements(self):
  from model_operation import building_preview
  b=dict(floors=[dict(name='1F',z=0,h=3,rooms=[dict(id='R1',polys=[[[0,0],[4,0],[4,4],[0,4]]])])])
  value=building_preview(b,'digest')
  self.assertTrue(value['model_preview']);self.assertFalse(value['complete'])
  self.assertEqual(value['building_sha256'],'digest');self.assertEqual(value['solvers'],{})
  self.assertIsNone(value['fire_key']);self.assertEqual(value['rooms'][0]['key'],'CAD_1F_R1')
 def test_default_request_is_not_a_fabricated_mc_result(self):
  raw=dict(cad=dict(building_sha256='test'),rooms=[dict(id='CAD_1F_R1',size_m=[4,4,3])],openings=[dict(id='door',a='CAD_1F_R1',b='OUTSIDE',schedule=[[0,0.5]])])
  body=dict(engine='cfast',room='CAD_1F_R1',floor='1F',duration_s=3600,use_default_openings=True)
  with tempfile.TemporaryDirectory() as tmp:
   engine=Path(tmp)/'engine';engine.write_bytes(b'mock')
   with patch('model_mc.fixed_inputs',return_value={}),patch('model_mc.prepare_request',return_value=(body,raw)) as prep,patch.object(calc,'ENGINE',engine),patch('pyrocast_cfbt.native.execute') as execute:
    folder,fixed,req,value=calc.prepare('test',body,'hotel')
    self.assertIsNone(folder);self.assertEqual(value,raw);self.assertEqual(fixed['basis'],'application_default')
    self.assertEqual(fixed['states']['door']['effective_fraction'],0.5)
    execute.assert_not_called();prep.assert_called_once()
 def test_explicit_invalid_mc_never_silently_falls_back(self):
  with patch.object(calc,'context',side_effect=ValueError('bad MC')),patch.object(calc,'default_input') as fallback:
   with self.assertRaisesRegex(ValueError,'bad MC'):calc.prepare('test',dict(engine='cfast',room='CAD_1F_R1',floor='1F',duration_s=3600,mc_job_id='bad'),'hotel')
   fallback.assert_not_called()

if __name__=='__main__':unittest.main()
