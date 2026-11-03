import unittest
from pyrocast_cfbt.conditions import rollover_records

class RolloverRouteTests(unittest.TestCase):
    def model(self):
        def vent(a,b):return dict(id=a+b,a=a,b=b,type='WALL',schedule=[[0,1]])
        return dict(rooms=[{'id':x} for x in 'ABCDE'],fuel_groups=[{'id':'F','room':'A','initial_time_s':0}],
                    openings=[vent('A','B'),vent('A','C'),vent('B','D'),vent('C','D'),vent('A','E'),vent('D','OUTSIDE')])
    def run_records(self,m,heat=None,jets=None):
        fgi={x['id']:{'scores':{'degree':[1.2,1.4],'factors':{'temperature':[2,2],'fuel':[1.2,1.4],'oxygen':[2,2]}}} for x in m['rooms']}
        return rollover_records(m,[0,10],fgi,heat or {'A':[5,5]},jets or {})
    def test_equal_shortest_paths_and_origin(self):
        r=self.run_records(self.model(),{'A':[5,5],'B':[0,1]})
        self.assertEqual(r['A']['scores']['degree'],[1.2,1.4])
        self.assertEqual(r['B']['scores']['degree'],[1.2,1.4])
        self.assertEqual(r['C']['scores']['degree'],[1.2,1.4])
        self.assertEqual(r['D']['scores']['degree'],[0,1.4])
        self.assertEqual(r['E']['scores']['degree'],[0,0])
    def test_received_jet_and_closed_route(self):
        m=self.model();r=self.run_records(m,jets={'D':[1,0]})
        self.assertEqual(r['D']['scores']['degree'],[1.2,0])
        m['openings'][-1]['schedule']=[[0,0],[10,1]]
        r=self.run_records(m)
        self.assertEqual(r['A']['scores']['degree'],[0,1.4])
    def test_exclude_origin_and_keep_fgi_factors(self):
        m=self.model();m['condition_scoring']={'rollover_include_origin':False}
        r=self.run_records(m)
        self.assertEqual(r['A']['scores']['degree'],[0,0])
        self.assertEqual(r['B']['scores']['factors']['fuel'],[1.2,1.4])
    def test_cells_share_physical_ignition(self):
        m=self.model();m['rooms'] += [{'id':'D2','parent_room':'D'}]
        r=self.run_records(m,jets={'D2':[2,0]})
        self.assertEqual(r['D']['scores']['degree'],[1.2,0])
        self.assertEqual(r['D2']['scores']['degree'],[1.2,0])

if __name__=='__main__':unittest.main()
