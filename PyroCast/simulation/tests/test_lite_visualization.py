import json, unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
from pyrocast_lite.visualization import states

class LiteVisualTests(unittest.TestCase):
    def test_priority_and_independent_smoke_extent(self):
        # Same upper-layer extent, different fuel/oxygen: changing colour must
        # not erase the gray layer or confuse bulk reaction with door jets.
        y=np.zeros((8,6));y[1]=5.;y[2]=np.array([20,400,400,600,600,600])+273.15
        y[4]=np.array([.21,.21,.21,.05,.21,.21])*32/29
        y[6]=[0,0,.1,.1,.1,.1]
        m=SimpleNamespace(N=1,sol=SimpleNamespace(y=y),nodes=[{'id':'R'}],
            Va=np.array([10.]),Vmin=np.array([.1]),Aa=np.array([5.]),Ha=np.array([2.]),
            P={'LFL0_hrr':1.,'dHc':100.,'LOC':.12,'T_ai':793.15},
            input_model={'gas':{'hot_C':300.}},manifest={'rule_settings':{'values':{'temperature_C':600.}}})
        r={'rooms':[{'upper_reaction_kg_s':[0]*6}],
           'shared_conditions':{'rooms':{'R':{'FO':{'scores':{'all_met':[False]*5+[True]}}}}}}
        s=states(m,r)['R']
        self.assertEqual(s['color'],['#9ca3af','#9ca3af','#a855f7','#facc15','#a855f7','#ef4444'])
        self.assertEqual(s['rollover_band'],[False,False,False,False,True,False])
        self.assertEqual(s['boundary'],[False,False,False,True,True,True])
        self.assertEqual(s['smoke_stage'],[1,1,2,2,2,2])

    def test_saved_stage4_symbols_inside_their_cad_cells(self):
        p=Path(__file__).resolve().parents[2]/'simulation/results/lite_v8_stage4_R2_20261026/playback.json'
        if not p.exists():self.skipTest('Local approved CAD result is not bundled')
        d=json.loads(p.read_text('utf-8'));shapes={r['key']:unary_union([Polygon(x['o'],x.get('h',[])) for x in r['cad_polys']]) for r in d['rooms']}
        self.assertEqual(set(shapes),set(d['solvers']))
        self.assertGreater(len(d['fuel_symbols']),0)
        for f in d['fires']:
            self.assertTrue(shapes[f['cad_key']].covers(Point(f['position_m'][:2])))
            q=d['solvers'][f['solver_id']]['Qsolid_kW']
            self.assertTrue(all((h>0)==(v>0) for h,v in zip(f['visuals']['flame_height_m'],q)))
        for u in d['fuel_symbols']:self.assertTrue(shapes[u['room']].covers(Point(u['position_m'][:2])))
        # Gray smoke remains visible in cells that never meet a coloured risk.
        self.assertTrue(any(any(v>0 for v in s['ODu']) and not any(c in ('#ef4444','#a855f7','#facc15') for c in s['display_v8']['color']) for s in d['solvers'].values()))

    def test_mc_duration_accepts_untenable_record_level_mask(self):
        root=Path(__file__).resolve().parents[2]
        p=root/'simulation/results/lite_v8_mc_R2_10_20261026/S00'
        if not (p/'BDF/result.json').exists():self.skipTest('Local MC output is not bundled')
        import sys
        sys.path.insert(0,str(root/'tools'))
        from run_lite_mc_v8_r2 import summarize,PARAMS
        from pyrocast_lite.adapter import prepare
        sample=json.loads((p/'sample.json').read_text('utf-8'))
        r=json.loads((p/'BDF/result.json').read_text('utf-8'))
        m,_=prepare(sample['scenario'],PARAMS);z=np.load(p/'BDF/state.npz')
        m.sol=SimpleNamespace(t=z['t'],y=z['y'])
        s=summarize(m,r,sample)
        self.assertTrue(s['complete'])
        for v in s['phenomena']['untenable']['met_time_fraction_by_room'].values():
            self.assertGreaterEqual(v,0);self.assertLessEqual(v,1)

if __name__=='__main__':unittest.main()
