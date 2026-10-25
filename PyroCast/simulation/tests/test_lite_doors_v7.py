import unittest
from pyrocast_lite.door_classification import classify_doors

class DoorV7Tests(unittest.TestCase):
    def raw(self,area=25,name='ELEV.홀 1',kind=None):
        return {'rooms':[{'id':'A','name':name,'area_m2':area,'size_m':[5,5,3],'core_kind':kind},
                         {'id':'B','name':'생산실','size_m':[10,10,3]}],
                'openings':[{'id':'D','a':'A','b':'B','kind':'door'}]}
    def row(self,raw):return classify_doors(raw)[1]['rows'][0]
    def test_area_gate_cannot_be_bypassed_by_core_kind(self):
        self.assertEqual(self.row(self.raw(80))['rule'],2)
        for kind in (None,'stair','elev'):
            self.assertEqual(self.row(self.raw(80.0001,kind=kind))['rule'],6)
        for area in (0,-1,float('nan')):
            self.assertEqual(self.row(self.raw(area))['rule'],6)
    def test_first_token_not_anywhere_or_longer_word(self):
        for name in ('생산홀 ELEV.홀 1','창작실 계단실 1','계단실용 작업실'):
            self.assertEqual(self.row(self.raw(name=name))['rule'],6)
        for name in (' ELEV.홀 2','계단실1','비상용 승강기'):
            self.assertEqual(self.row(self.raw(name=name))['rule'],2)
        self.assertEqual(self.row(self.raw(name='',kind='elev'))['rule'],2)
        self.assertEqual(self.row(self.raw(name='P.S',kind='shaft'))['rule'],3)
    def test_other_side_core_and_explicit_priority(self):
        raw=self.raw(325)
        raw['rooms'][1].update(core_kind='stair',area_m2=23)
        self.assertEqual(self.row(raw)['rule'],2)
        raw=self.raw(325);raw['openings'][0]['block_name']='FD-90'
        self.assertEqual(self.row(raw)['rule'],1)
        self.assertEqual(classify_doors(raw,{'D':'ordinary'})[1]['rows'][0]['rule'],0)
    def test_previous_auto_flags_do_not_become_explicit(self):
        raw=self.raw(325)
        raw['openings'][0].update(fire_door=True,door_class_basis=2,door_class_confidence='confirmed')
        model,report=classify_doors(raw)
        self.assertEqual(report['rows'][0]['rule'],6)
        self.assertEqual(classify_doors(model)[1]['rows'],report['rows'])
        raw=self.raw(325);raw['openings'][0]['fire_door']=True
        model,report=classify_doors(raw)
        self.assertEqual(report['rows'][0]['rule'],1)
        self.assertEqual(classify_doors(model)[1]['rows'],report['rows'])

if __name__=='__main__':unittest.main()
