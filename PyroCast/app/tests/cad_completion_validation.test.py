import json,sys,tempfile,unittest
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import cad_completion as c
from cad_completion_validation import checked_apply,floor_checks,audit
def rect(x,y,w,h):return [[[x,y],[x+w,y],[x+w,y+h],[x,y+h]]]
def floor():
 return dict(name='1F',h=3,slab=rect(0,0,10,10),rooms=[dict(id='A',polys=rect(0,0,2,2),area=4,names=[])],openings=[])
class ValidationTests(unittest.TestCase):
 def test_multifloor_without_vertical_links_is_unconfirmed(self):
  a=floor();a["align"]="verified";b=deepcopy(a);b["name"]="2F"
  v=audit(dict(floors=[a,b]))
  self.assertTrue(v["missing_vertical_connections"]);self.assertEqual(v["status"],"needs_review")
 def test_core_is_inferred_and_cannot_invent_geometry(self):
  f=floor();f['cad_arc_provenance']={'source_sha256':'abc'}
  candidates=c.core_candidates(f);self.assertEqual(len(candidates),2)
  before=deepcopy(f['rooms'][0]['polys'])
  change=c.apply_candidate(f,candidates[0],'api_ai')
  self.assertEqual(f['rooms'][0]['polys'],before)
  self.assertEqual(f['rooms'][0]['ai_core_evidence']['confidence'],'inferred')
  self.assertEqual(change['validation']['status'],'passed')
  with self.assertRaisesRegex(ValueError,'conflicting core'):
   c.validate_decisions(json.dumps({'accept':[x['id'] for x in candidates],'uncertain':[]}),candidates)
 def test_unresolved_endpoint_is_review_not_dangling_error(self):
  f=floor();f['openings']=[{'id':'D','sides':[None,'A']}]
  self.assertEqual(floor_checks(f),[])
 def test_rejects_dangling_door_and_rolls_back(self):
  f=floor();before=deepcopy(f)
  def bad(trial,*args):trial['openings'].append(dict(id='D',sides=['A','imaginary']));return {}
  with self.assertRaisesRegex(ValueError,'dangling_opening'):checked_apply(f,{},'api_ai',bad)
  self.assertEqual(f,before)
 def test_rejects_merge_footprint_loss(self):
  f=floor();before=deepcopy(f)
  def bad(trial,*args):trial['rooms'][0]['polys']=rect(0,0,1,1);return {}
  with self.assertRaisesRegex(ValueError,'footprint'):checked_apply(f,{'type':'merge','id':'m'},'api_ai',bad)
  self.assertEqual(f,before)
 def test_valid_change_preserves_existing_warnings(self):
  f=floor();f['openings']=[dict(id='old',sides=['missing','A'])]
  def good(trial,*args):trial['rooms'][0]['names']=['Office'];return {}
  result=checked_apply(f,{},'geometry',good)
  self.assertEqual(result['validation']['status'],'passed')
  self.assertEqual(f['rooms'][0]['names'],['Office'])
 def test_batches_keep_arc_alternatives_together(self):
  cs=[dict(id=str(i),arc_id=str(i//2)) for i in range(8)]
  bs=list(c.candidate_batches(cs,3))
  self.assertEqual([len(x) for x in bs],[2,2,2,2])
 def test_postcheck_missing_ids_are_unconfirmed(self):
  f=floor();b=dict(floors=[f],model_review={'items':[]})
  with tempfile.TemporaryDirectory(dir=ROOT/'reviews') as tmp:
   source=Path(tmp)/'building.json';source.write_text('{}')
   v=c.post_validate(b,source,tmp,lambda ms:json.dumps({'accept':[],'uncertain':[]}),True)
  self.assertIn('incomplete_response',v['ai_status'])
  self.assertTrue(any(x['id']=='A' for x in b['model_review']['items']))
 def test_unconnected_api_never_reports_reviewed(self):
  b=dict(floors=[floor()],model_review={'items':[]})
  with tempfile.TemporaryDirectory(dir=ROOT/'reviews') as tmp,patch('lite_ai_fuel.settings',return_value=None):
   source=Path(tmp)/'building.json';source.write_text('{}')
   v=c.post_validate(b,source,tmp,None,True)
  self.assertEqual(v['api_calls'],0);self.assertEqual(v['ai_status'],'not_connected')
 def test_postcheck_cannot_mutate_model(self):
  b=dict(floors=[floor()],model_review={'items':[]});before=deepcopy(b['floors'])
  with tempfile.TemporaryDirectory(dir=ROOT/'reviews') as tmp:
   source=Path(tmp)/'building.json';source.write_text('{}')
   v=c.post_validate(b,source,tmp,lambda ms:json.dumps({'accept':['invented'],'uncertain':[]}),True)
  self.assertEqual(b['floors'],before);self.assertIn('failed_or_invalid_response',v['ai_status'])
if __name__=='__main__':unittest.main()
