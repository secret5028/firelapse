import unittest,json
from copy import deepcopy
from pathlib import Path
from cad_arc_doors import apply_arc_doors,bind_leaf
from cad_connectivity_shared import geometry,build_graph
from cad_autocorrect import CONFIG
from cad_reviewed_connections import apply_reviewed_connections

P=json.loads(CONFIG.read_text('utf-8'))
def rect(x,y,w,h):return [[x,y],[x+w,y],[x+w,y+h],[x,y+h]]
def leaf(h=(0,0),e=(0,1)):
    return dict(hinge=list(h),closed=list(e),open=[h[0]+1,h[1]],r=1.)
def floor():
    return dict(name='1F',h=3,slab=[rect(-4,-4,8,8)],rooms=[dict(id='A',area=32,polys=[rect(-4,-4,4,8)]),dict(id='B',area=32,polys=[rect(0,-4,4,8)])],
        openings=[dict(id='D',kind='door',sides=['A','A'],polys=[rect(-.05,0,.1,1)],leaves=[leaf()],open_fraction=.5)])

class ArcTests(unittest.TestCase):
    def test_single_door_keeps_state_and_geometry(self):
        f=floor();old=deepcopy(f['openings'][0]);r=apply_arc_doors(f,P)
        self.assertEqual(len(r['changes']),1);self.assertEqual(set(f['openings'][0]['sides']),{'A','B'})
        for k in ('leaves','polys','open_fraction'):self.assertEqual(old[k],f['openings'][0][k])
        self.assertFalse(apply_arc_doors(f,P)['changes'])
    def test_nested_connection_is_inferred(self):
        f=floor();f['rooms'][0].update(area=64,polys=f['slab'])
        apply_arc_doors(f,P);self.assertEqual(f['openings'][0]['connection_confidence'],'inferred')
    def test_equal_overlap_not_guessed(self):
        f=floor();f['rooms'].append(dict(id='C',area=32,polys=f['rooms'][1]['polys']))
        self.assertFalse(apply_arc_doors(f,P)['changes'])
    def test_valid_original_preserved(self):
        f=floor();f['openings'][0]['sides']=['A','out'];self.assertFalse(apply_arc_doors(f,P)['changes'])
    def test_never_invent_outside(self):
        f=floor();f['rooms'].pop();self.assertFalse(apply_arc_doors(f,P)['changes'])
    def test_double_door_one_flow_edge(self):
        f=floor();f['openings'][0]['leaves'].append(leaf((0,2),(0,1)))
        apply_arc_doors(f,P);g=build_graph(f['rooms'],f['openings'])
        self.assertEqual(len(g['connections']),1);self.assertEqual(g['connections'][0]['dimensions']['width_m'],2)
    def test_disjoint_doors_not_merged(self):
        f=floor();f['openings'][0]['leaves'].append(leaf((0,2),(0,3)))
        apply_arc_doors(f,P);self.assertEqual(len(build_graph(f['rooms'],f['openings'])['connections']),2)
    def test_unknown_arc_is_door_without_vent(self):
        f=floor();f['openings']=[];f['cad_arcs']=[dict(id='ARC1',inside_building=True,center=[2,2],radius_m=.5,start=[2.5,2],end=[2,2.5],radial_line_support=[False,False])]
        r=apply_arc_doors(f,P);self.assertFalse(r['changes']);self.assertEqual(r['inventory'][0]['connection_state'],'unresolved')
        self.assertEqual(r['inventory'][0]['door_presence'],'user_assumed_from_interior_arc')
    def test_exterior_arc_excluded(self):
        f=floor();f['cad_arcs']=[dict(id='OUT',inside_building=False)]
        self.assertEqual(apply_arc_doors(f,P)['inventory'],[])
    def test_raw_arc_closed_plane_not_open_leaf(self):
        f=floor();f['openings']=[];f['cad_arcs']=[dict(id='ARC1',inside_building=True,center=[0,0],radius_m=1,start=[1,0],end=[0,1],radial_line_support=[True,False])]
        apply_arc_doors(f,P);self.assertEqual(f['openings'][0]['leaves'][0]['closed'],[0,1])
        self.assertFalse(apply_arc_doors(f,P)['changes'])
    def test_raw_duplicate_same_door_not_extra_vent(self):
        f=floor();f['openings']=[];a=dict(id='ARC1',inside_building=True,center=[0,0],radius_m=1,start=[1,0],end=[0,1],radial_line_support=[True,False]);f['cad_arcs']=[a,{**a,'id':'ARC2'}]
        apply_arc_doors(f,P);self.assertEqual(len(f['openings']),1)
    def test_r17_real_mixed_bundle(self):
        root=Path(__file__).resolve().parents[2]
        b=json.loads((root/'reviews/cad-interior-arcs-20261104/building-before.json').read_text('utf-8'))
        f=next(f for f in b['floors'] if f['name']=='5F');apply_arc_doors(f,P)
        o=next(o for o in f['openings'] if o['id']=='D0_ARC1')
        self.assertEqual(set(o['sides']),{'R1','R17'});self.assertEqual(o['span'],.95)
        self.assertEqual(o['connection_confidence'],'inferred')
    def test_15_degree_frame_line_is_not_assumed_open(self):
        root=Path(__file__).resolve().parents[2]
        b=json.loads((root/'reviews/cad-interior-arcs-20261104/building-before.json').read_text('utf-8'))
        f=next(f for f in b['floors'] if f['name']=='5F')
        f['cad_arcs']=[dict(id='TEST_INSPECTION',inside_building=True,center=[12.420007,53.740081],radius_m=.74,start=[11.680007,53.740081],end=[11.705222,53.548555],radial_line_support=[True,False])]
        apply_arc_doors(f,P)
        self.assertEqual(set(next(o for o in f['openings'] if o['id']=='TEST_INSPECTION')['sides']),{'R12','R17'})
    def test_small_arc_cannot_probe_across_wall(self):
        f=floor();f['rooms'][0]['polys']=[rect(-4,-4,3.9,8)];f['rooms'][1]['polys']=[rect(.1,-4,3.9,8)]
        b=bind_leaf(leaf((0,0),(0,.002)),{r['id']:geometry(r['polys']) for r in f['rooms']},P)
        self.assertIsNone(b['sides'])
    def test_review_source_and_geometry_are_required(self):
        f=floor();f['cad_arc_provenance']={'source_sha256':'same'}
        d=dict(id='REVIEW',source_sha256='wrong',closed_plane=[[0,0],[0,1]],sides=['A','B'],kind='door',axiom='A',evidence='test')
        f['ai_connection_reviews']=[d]
        with self.assertRaisesRegex(ValueError,'SHA'):apply_reviewed_connections(f,P)
        d['source_sha256']='same';d['sides']=['A','MISSING']
        with self.assertRaisesRegex(ValueError,'geometry'):apply_reviewed_connections(f,P)
        d['sides']=['A','B'];self.assertEqual(len(apply_reviewed_connections(f,P)['changes']),1)
        self.assertFalse(apply_reviewed_connections(f,P)['changes'])

if __name__=='__main__':unittest.main()
