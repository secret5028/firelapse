import unittest
from copy import deepcopy
from cad_model_axioms import apply_model_axioms
from cad_connectivity_shared import match_vertical_cores
from cad_autocorrect import repair_floor
from building_rules import vertical_feature_allowed

def poly(x,y,w,h):return [dict(o=[[x,y],[x+w,y],[x+w,y+h],[x,y+h]],h=[])]
def fixture():
    return dict(shafts=[],floors=[dict(name=str(i+1)+'F',z=i*3,h=3,align='base' if i==0 else 'cores aligned',
        rooms=[dict(id='C',polys=poly(0,0,.8,.8),area=.64,names=['C3'] if i==1 else [],tags=[]),
               dict(id='R',polys=poly(2,0,4,4),area=16,names=['office'],tags=[])],
        columns=[dict(x=.4,y=.4)],openings=[]) for i in range(3)])
def core(f,z,kind='stair'):
    return dict(floor=f,z0=z,z1=z+3,kind=kind,x=1,y=1,w=2,h=2,core_id='K',room_id='R',align='base')

class AxiomTests(unittest.TestCase):
    def test_repeated_labelled_column_archived_not_lost(self):
        b=fixture();old=deepcopy(b);r=apply_model_axioms(b)
        self.assertEqual(len(r['changes']),3)
        for a,f in zip(old['floors'],b['floors']):
            self.assertEqual([r['id'] for r in f['rooms']],['R'])
            self.assertEqual(f['structural_columns'][0]['source_room'],a['rooms'][0])
        self.assertFalse(apply_model_axioms(b)['changes'])
    def test_position_without_column_label_not_enough(self):
        b=fixture();b['floors'][1]['rooms'][0]['names']=[]
        self.assertFalse(apply_model_axioms(b)['changes'])
    def test_shaft_label_not_reclassified_as_column(self):
        b=fixture();b['floors'][0]['rooms'][0]['names']=['PS']
        self.assertFalse(apply_model_axioms(b)['changes']) # fewer than 3 supported floors
    def test_weak_alignment_not_used(self):
        b=fixture();b['floors'][0]['align']='unconfirmed'
        self.assertFalse(apply_model_axioms(b)['changes'])
    def test_valid_door_prevents_room_removal(self):
        b=fixture();b['floors'][0]['openings']=[dict(id='D',sides=['C','R'])]
        r=apply_model_axioms(b);self.assertFalse(r['changes']);self.assertEqual(r['reviews'][0]['kind'],'column_conflict')
    def test_core_envelope_does_not_promote_large_hall(self):
        b=fixture();b['shafts']=[dict(kind='stair',x=3,y=1,w=1,h=1,floors=['1F','2F','3F'])]
        r=apply_model_axioms(b)
        self.assertTrue(any(x['kind']=='core_region_unresolved' for x in r['reviews']))
        self.assertTrue(all(r.get('axiom_core_kind') is None for f in b['floors'] for r in f['rooms']))
    def test_matching_repeated_core_sets_identity(self):
        b=fixture();b['shafts']=[dict(kind='elev',x=4,y=2,w=4,h=4,floors=['1F','2F','3F'])]
        apply_model_axioms(b)
        self.assertTrue(all(f['rooms'][0]['axiom_core_kind']=='elev' for f in b['floors']))
    def test_only_stair_elevator_vertical_links(self):
        for kind in ['stair','elev','column','ramp','shaft']:
            shafts,issues=match_vertical_cores([core('1F',0,kind),core('2F',3,kind)])
            self.assertEqual(bool(shafts),kind in ('stair','elev'))
    def test_no_floor_skip_or_ph_shortcut(self):
        shafts,_=match_vertical_cores([core('1F',0),core('3F',6)])
        self.assertEqual(shafts,[])
        shafts,_=match_vertical_cores([core('2F',3),core('PH',6)],['1F','2F','3F','PH'])
        self.assertEqual(shafts,[])
    def test_ramp_preserved_as_source_not_vertical_model(self):
        b=fixture();b['floors'][0]['model_ramps']=[dict(id='RAMP')]
        apply_model_axioms(b)
        self.assertEqual(b['floors'][0]['source_model_ramps'],[dict(id='RAMP')]);self.assertEqual(b['floors'][0]['model_ramps'],[dict(id='RAMP')])
        self.assertFalse(vertical_feature_allowed(b,'ramp'));self.assertTrue(vertical_feature_allowed({},'ramp'))
        self.assertTrue(vertical_feature_allowed(b,'stair'));self.assertTrue(vertical_feature_allowed(b,'elev'))
    def test_unverified_ai_review_is_marked_without_stopping_model(self):
        f=fixture()['floors'][0];f['ai_connection_reviews']=[dict(id='AI_BAD',source_sha256='stale')]
        r=repair_floor(f)
        self.assertEqual(r['reviews'][0]['kind'],'ai_review_unconfirmed');self.assertEqual(f['openings'],[])

if __name__=='__main__':unittest.main()
