import unittest
from copy import deepcopy
from pyrocast_cfbt.rule_graph import delay_parents
from pyrocast_cfbt.room_rule_r6 import DEFAULTS


class DelayGraphTests(unittest.TestCase):
    def model(self):
        # R -> corridor at (15,22), corridor -> T at (15,40).
        # The incoming door names the corridor as b and is on R's RIGHT wall.
        return {'rooms':[
            {'id':'R','origin_m':[10,20,0],'size_m':[5,5,3]},
            {'id':'H','origin_m':[15,20,0],'size_m':[5,20,3]},
            {'id':'T','origin_m':[15,40,0],'size_m':[5,5,3]}],
            'openings':[
            {'id':'RH','a':'R','b':'H','face':'RIGHT','offset_m':1.5,'width_m':1,'schedule':[[0,1]]},
            {'id':'HT','a':'H','b':'T','face':'REAR','offset_m':0,'width_m':0,'schedule':[[0,1]]}]}

    def test_receiving_side_uses_same_absolute_door_point(self):
        m=self.model()
        # Use a real 1m door, centered at x=15.5; distance sqrt(18^2+.5^2).
        m['openings'][1]['width_m']=1
        parents,_=delay_parents(m,'R',{'H'},{},DEFAULTS)
        self.assertEqual(parents['T']['room'],'R')
        self.assertAlmostEqual(parents['T']['delay_s'],120+(18**2+.5**2)**.5/.5)
        reversed_m=deepcopy(m);reversed_m['openings'].reverse()
        self.assertEqual(parents,delay_parents(reversed_m,'R',{'H'},{},DEFAULTS)[0])
        # Reverse the first door's ownership while retaining its physical position.
        m['openings'][0].update(a='H',b='R',face='LEFT')
        self.assertEqual(parents['T']['delay_s'],delay_parents(m,'R',{'H'},{},DEFAULTS)[0]['T']['delay_s'])

    def test_closed_and_fire_door_rules(self):
        m=self.model();m['openings'][0]['schedule']=[[0,0]]
        parents,_=delay_parents(m,'R',{'H'},{},DEFAULTS)
        self.assertEqual(parents['T']['path'][0]['delay_s'],600)
        m['openings'][0]['fire_door']=True
        self.assertNotIn('T',delay_parents(m,'R',{'H'},{},DEFAULTS)[0])

    def test_vertical_only_up(self):
        m=self.model();m['rooms'][2]['origin_m'][2]=3
        m['openings']=[{'id':'V','a':'R','b':'T','type':'FLOOR','schedule':[[0,1]]}]
        self.assertIn('T',delay_parents(m,'R',set(),{},DEFAULTS)[0])
        self.assertNotIn('R',delay_parents(m,'T',set(),{},DEFAULTS)[0])
