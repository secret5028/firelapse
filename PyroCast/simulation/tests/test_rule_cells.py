import unittest
from copy import deepcopy
from pyrocast_cfbt.rule_cells import partition
from pyrocast_cfbt.rule_graph import delay_parents
from pyrocast_cfbt.room_rule_r6 import DEFAULTS


class CellCoordinatesTests(unittest.TestCase):
    def test_virtual_and_real_apertures_share_cad_frame(self):
        m={'rooms':[{'id':'H','origin_m':[200,0,0],'size_m':[20,10,3],
                     'cad_bounds_m':[100,200,120,210]},
                    {'id':'T','origin_m':[300,0,0],'size_m':[5,5,3],'cad_bounds_m':[120,200,125,205]}],
           'fuel_groups':[],
           'openings':[{'id':'HT','a':'H','b':'T','face':'RIGHT','width_m':1,'offset_m':4.5,
             'bottom_m':0,'top_m':3,'schedule':[[0,1]],
             'cad_geometry':{'center_m':[120,205,1.5],'tangent':[0,1,0],'normal_a_to_b':[1,0,0]}}]}
        out,_=partition(m)
        virtual=next(v for v in out['openings'] if v.get('virtual_cell_boundary'))
        self.assertEqual(virtual['cad_geometry']['center_m'],[110,205,1.5])
        parents,_=delay_parents(out,'H_C0',{'H_C1'},{},DEFAULTS)
        self.assertEqual(parents['T']['delay_s'],30+60+10/.5)
        shifted=deepcopy(m)
        for room in shifted['rooms']:room['origin_m'][0]+=10000
        out2,_=partition(shifted)
        self.assertEqual(parents,delay_parents(out2,'H_C0',{'H_C1'},{},DEFAULTS)[0])
