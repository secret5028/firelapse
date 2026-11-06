"""Source-bound CAD corrections; API mocks exist only in this test file."""
import json, sys, tempfile, unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import cad_completion as c

def rectangle(x,y,w,h):return [[[x,y],[x+w,y],[x+w,y+h],[x,y+h]]]
def floor():
    points=[(0,0),(3,0),(8,0),(0,4),(3,4),(8,7),(2,9)]
    return dict(name='1F',slab=rectangle(0,0,10,10),columns=[dict(x=x,y=y) for x,y in points],rooms=[],openings=[])
def merge(room='A',target='B'):
    return dict(id=f'1F:merge:{room}:{target}',type='merge',floor='1F',room=room,target=target,source_sha256='abc')

class CompletionTests(unittest.TestCase):
    def test_alignment_unique_columns_preserves_geometry(self):
        a=floor();b=deepcopy(a);b['name']='2F';c.translate_floor(b,[85,0])
        answer=c.alignment_candidate(a,b,c.policy())
        self.assertTrue(answer['verified']);self.assertEqual(answer['matches'],7)
        self.assertEqual(answer['delta_m'],[-85,0]);c.translate_floor(b,answer['delta_m'])
        self.assertEqual(b['slab'],a['slab'])
    def test_alignment_rejects_sparse_or_collinear_evidence(self):
        a=floor();a['columns']=a['columns'][:2]
        self.assertIsNone(c.alignment_candidate(a,a,c.policy()))
        a['columns']=[dict(x=i,y=0) for i in range(8)]
        self.assertFalse(c.alignment_candidate(a,a,c.policy())['verified'])
    def test_alignment_requires_slab_agreement(self):
        a=floor();b=deepcopy(a);b['slab']=rectangle(0,0,25,25)
        self.assertFalse(c.alignment_candidate(a,b,c.policy())['verified'])
    def test_translation_holes_and_evidence(self):
        f=floor();f['rooms']=[dict(polys=[dict(o=rectangle(0,0,4,4)[0],h=rectangle(1,1,1,1))],area=15,
            connection_evidence=dict(point=[9,9]))]
        c.translate_floor(f,[10,20]);r=f['rooms'][0]
        self.assertEqual(r['polys'][0]['h'][0][0],[11,21]);self.assertEqual(r['area'],15)
        self.assertEqual(r['connection_evidence']['point'],[9,9])
    def test_api_rejects_text_unknown_ids_and_conflicting_merges(self):
        candidates=[merge(),merge('A','C'),merge('B','C')]
        for text in ['```json {}```',json.dumps(dict(accept=['invented'],uncertain=[])),
                     json.dumps(dict(accept=[candidates[0]['id'],candidates[1]['id']],uncertain=[])),
                     json.dumps(dict(accept=[candidates[0]['id'],candidates[2]['id']],uncertain=[]))]:
            result=c.ai_decisions({},candidates,lambda _,v=text:v)
            self.assertEqual(result['accepted'],[]);self.assertEqual(result['status'],'failed_or_invalid_response')
    def test_api_requires_known_candidates_and_marks_inferred(self):
        candidate=merge();messages=[]
        def reply(ms):messages.extend(ms);return json.dumps(dict(accept=[candidate['id']],uncertain=[]))
        result=c.ai_decisions(dict(floor='1F'),[candidate],reply)
        self.assertEqual(result['accepted'],[candidate]);self.assertEqual(result['calls'],1)
        self.assertIn('좌표',messages[0]['content'])
    def test_missing_connection_never_applies_fake_ai(self):
        with patch('lite_ai_fuel.settings',return_value=None):
            result=c.ai_decisions({},[merge()])
        self.assertEqual(result['calls'],0);self.assertEqual(result['accepted'],[])
        self.assertEqual(result['status'],'not_connected')
    def test_invalid_api_config_retains_geometry_only(self):
        with patch('lite_ai_fuel.settings',side_effect=ValueError('invalid config')):
            result=c.ai_decisions({},[merge()])
        self.assertEqual(result['accepted'],[]);self.assertEqual(result['calls'],0)
        self.assertEqual(result['status'],'failed_configuration')
    def test_merge_preserves_area_source_and_connections(self):
        f=floor();f['cad_arc_provenance']=dict(source_sha256='abc')
        f['rooms']=[dict(id='A',polys=rectangle(0,0,1,1),area=1),dict(id='B',polys=rectangle(1,0,2,1),area=2)]
        f['openings']=[dict(id='D',sides=['A','out'])]
        c.apply_merge(f,merge(),'api_ai')
        self.assertEqual(len(f['rooms']),1);self.assertEqual(f['rooms'][0]['area'],3)
        self.assertEqual(f['openings'][0]['sides'],['B','out'])
        self.assertEqual(f['review_archived_regions'][0]['source_room']['id'],'A')
        self.assertEqual(f['review_archived_regions'][0]['mode'],'api_ai')
    def test_merge_rejects_source_mismatch(self):
        f=floor();f['cad_arc_provenance']=dict(source_sha256='other')
        with self.assertRaisesRegex(ValueError,'source mismatch'):c.apply_merge(f,merge(),'api_ai')
    def test_recorded_review_requires_exact_source(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'source.json';source.write_text('{"floors":[]}',encoding='utf8')
            with self.assertRaisesRegex(ValueError,'source mismatch'):
                c.complete(source,Path(d)/'out',recorded_review=dict(source_sha256='wrong'))

if __name__=='__main__':unittest.main()
