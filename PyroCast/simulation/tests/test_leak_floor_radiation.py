import unittest,json
from pathlib import Path
from unittest.mock import patch
import numpy as np
from pyrocast_cfbt.validation import validate_native,SPECIES
from pyrocast_cfbt.floor_flux import read_floor_flux,gauges
from pyrocast_cfbt.criteria import evaluate_cell

class LeakLedger(unittest.TestCase):
    def ledger(self, flow, change, units='kg/s', missing=False):
        t=np.array([0.,1.]);mass={'Time':t};mu={}
        for layer in ('UL','LL'):
            for sp in SPECIES:
                k=f'{layer}M{sp}_1';mass[k]=np.zeros(2);mu[k]='kg'
        mass['ULMN2_1']=np.array([10.,10.+change])
        c=dict(Time=t,PRS_1=np.zeros(2),HRR_1=np.ones(2),HRR_E1=np.ones(2))
        k='L_Room_1_Outside_1'
        native=dict(compartments=c,native_vents={} if missing else {k:np.full(2,flow)},
                    native_vents_ids={k:'Wall Leak A'},native_vents_units={k:units})
        model=dict(rooms=[dict(id='A',leak_area_ratio=[.001,0])],openings=[])
        with patch('pyrocast_cfbt.native.read_native_csv',return_value=(mass,{},mu)):
            return validate_native(native,model,'.')

    def test_native_endpoint_two_outflow_and_inflow(self):
        for flow in (-1.,1.):
            v=self.ledger(flow,-flow)
            self.assertEqual(v['status'],'valid',v)
            self.assertEqual(v['metrics']['mass_balance_error'],0)
            self.assertEqual(v['metrics']['builtin_leak_columns'],1)

    def test_wrong_sign_causes_failure_not_pass(self):
        v=self.ledger(-1.,-1.)
        self.assertEqual(v['status'],'physically_invalid')
        self.assertEqual(v['metrics']['mass_balance_error'],2)

    def test_missing_or_wrong_units_remain_unverified(self):
        for kwargs in ({'missing':True},{'units':'m3/s'}):
            self.assertEqual(self.ledger(-1.,1.,**kwargs)['status'],'unverified')

class FloorRadiation(unittest.TestCase):
    def fixture(self):
        room=dict(id='A',size_m=[4.,5.,3.],origin_m=[100.,0.,20.])
        model=dict(rooms=[room],native_floor_flux={'grid_side':2,'origin_grid_side':2},ambient_C=20,fuel_groups=[dict(room='A',heat_of_combustion_kJ_kg=18000,initial_time_s=0)])
        native=dict(compartments={'Time':np.array([0.,1.])},devices={'Time':np.array([0.,1.]),'TRGFLXT_17':np.array([0.,7.])},
                    devices_ids={'TRGFLXT_17':'FO_FLOOR_1_1'},devices_units={'TRGFLXT_17':'kW/m^2'})
        for j,q in enumerate((10,20,30,60)):
            k=f'TRGFLXI_{17+j}';native['devices'][k]=np.array([0.,q])
            native['devices_ids'][k]=f'FO_FLOOR_1_{j+1}';native['devices_units'][k]='kW/m^2'
        return model,room,native

    def test_radiation_triggers_fo_below_temperature_threshold(self):
        model,room,native=self.fixture();values=read_floor_flux(model,native)['A']['values']
        out=evaluate_cell(model,room,[0,1],[20,400],[3,1],[20,15],[0,0],[0,100],flux_kW_m2=values)
        self.assertEqual(out['FO']['scores']['degree'][1],1.5)
        self.assertTrue(out['FO']['occurred'][1]);self.assertEqual(out['FO']['first_met_s'],1)
        self.assertEqual(gauges(model)[0]['local_xyz'],[1,1.25,.02])

    def test_wrong_identity_units_time_or_missing_rejected(self):
        for alteration in ('identity','units','time','missing'):
            model,room,native=self.fixture()
            if alteration=='identity':native['devices_ids']['TRGFLXI_17']='fuel_target'
            elif alteration=='units':native['devices_units']['TRGFLXI_17']='W/m^2'
            elif alteration=='time':native['devices']['Time']=np.array([0,2])
            else:del native['devices']['TRGFLXI_17']
            with self.assertRaises(ValueError):read_floor_flux(model,native)

    def test_gauge_is_passive_and_existing_triggers_are_preserved(self):
        from pyrocast_cfbt.room_rule_r8 import prepare_native
        from pyrocast_cfbt.deck import make_deck
        raw=json.loads((Path(__file__).resolve().parents[2]/'fixtures/room_rule_benchmark_3room.json').read_text('utf8'))
        model,targets,_=prepare_native(raw);deck=make_deck(model,[],targets)
        for g in gauges(model):
            self.assertIn("&DEVC ID='"+g['id']+"'",deck)
            self.assertNotIn("DEVC_ID='"+g['id']+"'",deck)
        for target in targets:self.assertIn("&DEVC ID='"+target['id']+"'",deck)

if __name__=='__main__':unittest.main()
