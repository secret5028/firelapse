import json,unittest,tempfile
from pathlib import Path
import numpy as np
from pyrocast_cfbt.room_rule import prepare,observe
from pyrocast_cfbt.deck import make_deck,fire_curve

class ParentRuleTests(unittest.TestCase):
    def raw(self):
        raw=json.loads((Path(__file__).resolve().parents[2]/'fixtures/room_rule_benchmark_3room.json').read_text('utf-8'))
        raw['room_fire_rule']={'enabled':True,'trigger_mode':'parent_r5'}
        return raw

    def test_parent_device_delay_budget_and_independent_positions(self):
        raw=self.raw();model,targets=prepare(raw);group=model['fuel_groups'][1]
        self.assertEqual(group['room_rule_trigger']['target_id'],'PC_R1')
        self.assertEqual(group['room_rule_trigger']['setpoint'],600)
        self.assertEqual(next(t for t in targets if t['id']=='PC_R1')['room'],'R1')
        self.assertEqual(group['position_m'],[7.5,2.5,0])
        curve=group['room_rule_curve']
        self.assertEqual(curve['t'][:3],[0,60,120]);self.assertEqual(curve['q'][:2],[0,0])
        self.assertAlmostEqual(np.trapezoid(curve['q'],curve['t'])/1000,10000)
        self.assertEqual(fire_curve(model['fuel_groups'][0],25),fire_curve(raw['fuel_groups'][0],25))
        deck=make_deck(model,[],targets)
        self.assertIn("COMP_ID='R2' FIRE_ID='F_reserve_R2' LOCATION=2.5,2.5 IGNITION_CRITERION='TEMPERATURE' DEVC_ID='PC_R1' SETPOINT=600",deck)
        again,other=prepare(model);self.assertEqual(deck,make_deck(again,[],other))

    def test_closed_door_excludes_unreachable_fire_and_alternate_path_is_first_bfs_parent(self):
        raw=self.raw();raw['openings'][1]['schedule']=[[0,0]]
        model,_=prepare(raw)
        self.assertEqual([g['room'] for g in model['fuel_groups']],['R1','R2'])
        self.assertEqual(model['room_fire_rule']['excluded_unreachable_groups'],['reserve_R3'])
        raw['openings'].append({'id':'D13','a':'R1','b':'R3','face':'RIGHT','width_m':.9,'top_m':2.1})
        model,_=prepare(raw)
        self.assertEqual(model['room_fire_rule']['parent_map']['R3']['room'],'R1')

    def test_dynamic_door_is_not_silently_treated_as_fixed_open(self):
        raw=self.raw();raw['openings'][0]['schedule']=[[0,0],[100,1]]
        with self.assertRaisesRegex(ValueError,'fixed internal'):prepare(raw)

    def test_presets_and_fixed_threshold(self):
        for preset,delay in [('conservative',120),('standard',60),('aggressive',30)]:
            raw=self.raw();raw['room_fire_rule']['preset']=preset;model,_=prepare(raw)
            self.assertEqual(model['room_fire_rule']['delay_s'],delay)
            self.assertEqual(model['room_fire_rule']['ramp_s'],delay)
        raw=self.raw();raw['room_fire_rule']['setpoint']=550
        with self.assertRaisesRegex(ValueError,'fixed parent'):prepare(raw)

    def test_observation_uses_parent_id_and_keeps_trigger_separate_from_supply(self):
        model,targets=prepare(self.raw());t=np.array([0.,5.,10.]);devices={};ids={}
        for i,target in enumerate(reversed(targets),1):
            for prefix in ('TRGSURT','TRGFLXI'):
                key=f'{prefix}_{i}';ids[key]=target['id']
                devices[key]=np.array([20.,590.,610.]) if target['room']=='R1' else np.array([20.,30.,40.])
        workspace=Path(__file__).resolve().parents[2]
        test_root=(workspace/'simulation/build/unit_tmp').resolve()
        if not test_root.is_relative_to(workspace):raise ValueError('Unsafe test directory')
        test_root.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=test_root) as name:
            (Path(name)/'case.log').write_text('Object #2 (F_reserve_R2) ignited at 7 seconds')
            native={'run':{'folder':name},'zone':{'Time':t,'HRR_2':np.zeros(3),'HRR_3':np.zeros(3)},
                    'devices':devices,'devices_ids':ids,
                    'compartments':{'IGN_2':np.array([0,0,1]),'IGN_3':np.zeros(3)}}
            events,_,records=observe(model,native,targets)
        self.assertEqual(events[0]['trigger_room'],'R1')
        self.assertEqual(events[0]['t_ign_s'],7.)
        self.assertEqual(events[0]['prescribed_supply_start_s'],67.)
        self.assertEqual(events[0]['prescribed_supply_start_interval_s'],[66.5,67.5])
        self.assertEqual(records[0]['sensor_max'],610.)
        self.assertEqual(records[1]['sensor_max'],40.)
