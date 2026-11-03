import unittest
from pyrocast_cfbt.conditions import rollover_states

class FgiRolloverTests(unittest.TestCase):
    def model(self):
        return {'rooms':[{'id':r} for r in 'ABCD'], 'fuel_groups':[{'room':'A','initial_time_s':0}],
                'openings':[{'id':'AB','a':'A','b':'B','schedule':[[0,1]]},{'id':'BC','a':'B','b':'C','schedule':[[0,0],[10,1]]}]}
    def records(self,m=None,threshold=100,heat=None,jets=None):
        m=m or self.model();fgi={r['id']:{'scores':{'degree':[.9,1.2],'factors':{'temperature':[2,2],'fuel':[.9,1.2],'oxygen':[2,2]}}} for r in m['rooms']}
        return rollover_states(m,[0,10],fgi,heat or {'A':[1,1],'B':[0,2]},jets or {},threshold=threshold)
    def test_no_exterior_path_and_origin_excluded(self):
        r=self.records(jets={'A':[9,9]})
        self.assertEqual(r['A']['active'],[False,False]);self.assertTrue(r['A']['excluded_origin'])
        self.assertEqual(r['B']['active'],[False,True]);self.assertNotIn('scores',r['B'])
    def test_received_jet_needs_no_adjacent_flame(self):
        self.assertEqual(self.records(jets={'D':[1,1]})['D']['active'],[False,True])
    def test_open_connection_and_threshold(self):
        r=self.records(threshold=80)
        self.assertEqual(r['B']['active'],[True,True]);self.assertEqual(r['C']['active'],[False,True])
        self.assertEqual(self.records(threshold=130)['B']['active'],[False,False])
    def test_all_origin_cells_excluded(self):
        m=self.model();m['rooms'].append({'id':'A2','parent_room':'A'})
        r=self.records(m,jets={'A2':[1,1]});self.assertEqual(r['A2']['active'],[False,False])
    def test_unknown_fgi_is_not_zero(self):
        m=self.model();f={r['id']:{'scores':{'degree':[None,None]}} for r in m['rooms']}
        r=rollover_states(m,[0,10],f,{'A':[1,1]},{})
        self.assertEqual(r['B']['active'],[None,None]);self.assertEqual(r['A']['active'],[False,False])

if __name__=='__main__':unittest.main()
