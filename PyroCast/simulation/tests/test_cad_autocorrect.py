import unittest
from copy import deepcopy
from cad_autocorrect import repair_floor

def rect(x,y,w,h):return [[x,y],[x+w,y],[x+w,y+h],[x,y+h]]
def fixture():
    return dict(name='1F',rooms=[dict(id='A',polys=[rect(-3,-3,3,6)]),dict(id='B',polys=[rect(0,-3,3,6)])],
        openings=[dict(id='D',kind='door',polys=[rect(-.05,-.5,.1,1)],sides=['A',None])])

class AutoCorrectTests(unittest.TestCase):
    def test_unique_sides_and_idempotence(self):
        f=fixture();original=deepcopy(f['openings'][0]['polys']);r=repair_floor(f)
        self.assertEqual(len(r['changes']),1);self.assertEqual(set(f['openings'][0]['sides']),{'A','B'})
        self.assertEqual(f['openings'][0]['polys'],original);self.assertEqual(repair_floor(f)['changes'],[])
    def test_overlap_stays_ambiguous(self):
        f=fixture();f['rooms'].append(dict(id='C',polys=[rect(0,-3,3,6)]))
        r=repair_floor(f);self.assertFalse(r['changes']);self.assertTrue(r['reviews'][0]['overlapping_hits'])
        self.assertEqual(f['openings'][0]['sides'],['A',None])
    def test_never_invents_exterior(self):
        f=fixture();f['rooms'].pop();self.assertFalse(repair_floor(f)['changes'])
        self.assertEqual(f['openings'][0]['sides'],['A',None])
    def test_declared_exterior_preserved(self):
        f=fixture();f['openings'][0]['sides']=['A','out'];self.assertFalse(repair_floor(f)['changes'])
    def test_valid_conflicting_connection_preserved(self):
        f=fixture();f['rooms'].append(dict(id='C',polys=[rect(9,9,2,2)]));f['openings'][0]['sides']=['A','C']
        r=repair_floor(f);self.assertFalse(r['changes']);self.assertEqual(r['reviews'][0]['kind'],'ambiguous_connection')
        self.assertEqual(f['openings'][0]['sides'],['A','C'])
    def test_mixed_door_planes_split_without_joining(self):
        f=fixture();f['openings'][0]['leaves']=[dict(hinge=[0,0],closed=[0,1]),dict(hinge=[0,0],closed=[1,0])]
        r=repair_floor(f);self.assertTrue(r['changes'])
        self.assertEqual(f['openings'][0]['superseded_by'],['D_ARC0'])
        self.assertEqual(set(f['openings'][1]['sides']),{'A','B'})
    def test_sparse_annotation_removed_from_width_only(self):
        f=fixture();o=f['openings'][0];o['polys']=[rect(-.1,-.44,.2,.88),[[0,2],[.4,2],[.4,2.01],[.01,2.01],[.01,3],[0,3]]]
        original=deepcopy(o['polys']);r=repair_floor(f)
        self.assertAlmostEqual(o['span'],.88);self.assertEqual(o['polys'],original)
        self.assertTrue(any(x['kind']=='aperture_width' for x in r['changes']))
    def test_two_rectangles_not_guessed(self):
        f=fixture();o=f['openings'][0];o['polys']=[rect(-.1,-.44,.2,.88),rect(-.1,2,.2,.88)]
        repair_floor(f);self.assertNotIn('span',o)

if __name__=='__main__':unittest.main()
