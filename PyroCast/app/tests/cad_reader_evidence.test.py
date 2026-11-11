"""CAD reader plan normalisation; geometry only, never runs a fire simulation."""
import sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT.parent/'work/cad-web/cad_engine'),str(ROOT/'simulation/deps'),str(ROOT/'simulation/plot_deps')]
try:
    from cad_evidence import normalize_plan
except ImportError as exc:
    normalize_plan=None;REASON='SKIP: CAD reader libraries missing: '+str(exc)

@unittest.skipIf(normalize_plan is None,globals().get('REASON',''))
class CollapsedContourTest(unittest.TestCase):
    def test_collapsed_contour_is_recorded_and_left_out(self):
        square=[[0,0],[4,0],[4,3],[0,3]]
        plan=dict(walls=[dict(o=[[0,0],[1,0]],h=[]),dict(o=[[5,0],[6,0],[6,1],[5,1]],h=[[[5.2,.2],[5.4,.2]]])],footprint=[],checks=[],openings=[],
            rooms=[dict(id='R1',polys=[dict(o=square,h=[]),dict(o=[[9,9]],h=[])])])
        out=normalize_plan(plan)
        self.assertEqual(len(out['walls']),1)
        self.assertEqual(out['walls'][0]['h'],[])
        self.assertEqual(len(out['rooms'][0]['polys']),1)
        self.assertAlmostEqual(out['rooms'][0]['area'],12)
        self.assertEqual(sum('붕괴' in c['note'] for c in out['checks']),2)

if __name__=='__main__':unittest.main()
