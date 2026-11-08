import sys,json,hashlib,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation')]
from model_simulation import prepare_floor
from pyrocast_lite.screening_v8_approved import scenario
from pyrocast_cfbt.room_rule_r8 import prepare_native

class DefaultInputsIntegration(unittest.TestCase):
    def prepared(self,floor,settings=None):
        p=ROOT/'data/parkmarine-hotel/building.json'
        return prepare_floor(p,floor,hashlib.sha256(p.read_bytes()).hexdigest(),json.dumps(settings or {}))

    def test_mixed_hotel_basement_retains_fire_and_review(self):
        raw,score=self.prepared('B1')
        use=raw['approved_input']['room_uses']['CAD_B1_R3']
        self.assertEqual(use['usage_class'],'default')
        self.assertTrue(use['classification_basis']['review_required'])
        self.assertGreater(use['load_MJ_m2'],50)
        self.assertTrue(any(g['room']=='CAD_B1_R3' for g in raw['fuel_groups']))

    def test_explicit_class_is_not_overwritten(self):
        raw,_=self.prepared('B1',{'rooms':{'CAD_B1_R3':{'usage_class':'office','multiplier':1.2}}})
        use=raw['approved_input']['room_uses']['CAD_B1_R3']
        self.assertEqual(use['usage_class'],'office');self.assertEqual(use['load_MJ_m2'],504)
        self.assertEqual(use['classification_basis']['basis'],'user')

    def test_hotel_open_doors_closed_windows_native_sources_survive(self):
        raw,score=self.prepared('5F');data=scenario(score,'CAD_5F_R16','open_except_confirmed')
        for vent in data['openings']:
            if vent['id'] in ('CAD_5F_W12','CAD_5F_W18','CAD_5F_W25','CAD_5F_W26'):vent['schedule']=[[0,0]]
            if vent['id'] in ('CAD_5F_D7','CAD_5F_D15'):vent['schedule']=[[0,1]]
        model,_,manifest=prepare_native(data)
        for rid in ('CAD_5F_R6','CAD_5F_R11'):
            groups=[g for g in model['fuel_groups'] if g['room']==rid]
            self.assertTrue(groups)
            self.assertTrue(all(max(g['room_rule_curve']['q'])>0 for g in groups))
        first=next(g for g in data['fuel_groups'] if 'initial_time_s' in g)
        self.assertAlmostEqual(first['growth_kW_s2'],1000/300**2)
        self.assertIn('미입력',manifest['input_basis']['ventilation'])

if __name__=='__main__':unittest.main()
