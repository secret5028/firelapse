"""Separate conservation failures from prescribed-fire applicability checks."""
import unittest
from unittest.mock import patch
import numpy as np
from pyrocast_cfbt.validation import SPECIES,validate_native,protect_playback


class FuelValidation(unittest.TestCase):
    def fixture(self, fuel=0., background=1., ratio=.2, mass_error=False):
        t=np.array([0.,3600.]);m={'Time':t};units={};ids={}
        for layer in ('UL','LL'):
            for s in SPECIES:
                k=f'{layer}M{s}_1';m[k]=np.zeros(2);units[k]='kg';ids[k]='Fire'
        m['ULMN2_1'][:]=background;m['ULMTUHC_1'][:]=fuel
        if mass_error:m['ULMN2_1'][1]+=10
        c=dict(Time=t,PRS_1=np.zeros(2),HRR_1=np.full(2,1000*ratio),HRR_E1=np.full(2,1000.),DJET_1=np.full(2,100.),
               ULT_1=np.array([45.,45.]),ULO2_1=np.array([.001,.001]),VOL_1=np.array([30.,30.]))
        model=dict(rooms=[dict(id='Fire',leak_area_ratio=[0,0])],openings=[])
        with patch('pyrocast_cfbt.native.read_native_csv',return_value=(m,ids,units)):
            return validate_native(dict(compartments=c),model,'.')

    def test_oxygen_limited_hrr_is_diagnostic_not_failure(self):
        v=self.fixture()
        self.assertTrue(v['passed']);self.assertEqual(v['reasons'],[])
        self.assertEqual(v['metrics']['source_hrr_energy_ratio'],.2)
        self.assertEqual(v['metrics']['source_actual_energy_J'],720000)
        self.assertEqual(v['metrics']['source_prescribed_energy_J'],3600000)
        self.assertEqual(v['metrics']['vent_jet_energy_J'],360000)
        self.assertNotIn('burned_fraction',v['metrics'])

    def test_b1_peak_has_real_denominator_and_requires_input_review(self):
        v=self.fixture(31.0756435205,31.07731995512307-31.0756435205)
        self.assertEqual(v['status'],'unverified');self.assertFalse(v['passed'])
        self.assertEqual(v['reasons'],[])
        p=v['metrics']['upper_fuel_peak']
        self.assertAlmostEqual(p['fraction'],.9999460560104446)
        self.assertAlmostEqual(p['upper_mixture_mass_kg'],31.07731995512307)
        self.assertEqual(p['room'],'Fire');self.assertEqual(p['oxygen_vol_percent'],.1)

    def test_b2_peak_is_not_initial_solid_fuel_fraction(self):
        v=self.fixture(42.9497682305,43.10421450731757-42.9497682305)
        p=v['metrics']['upper_fuel_peak']
        self.assertAlmostEqual(p['fraction'],.9964169100728804)
        self.assertAlmostEqual(sum(p['species_mass_kg'].values()),p['upper_mixture_mass_kg'])

    def test_empty_layer_does_not_divide_by_zero(self):
        v=self.fixture(0,0,1)
        self.assertTrue(v['passed']);self.assertEqual(v['metrics']['max_upper_fuel_fraction'],0)

    def test_peak_time_and_mass_basis_match_the_same_sample(self):
        t=np.array([0.,60.,3600.]);m={'Time':t};units={};ids={}
        for layer in ('UL','LL'):
            for s in SPECIES:
                key=f'{layer}M{s}_1';m[key]=np.zeros(3);units[key]='kg';ids[key]='B1 R2'
        m['ULMN2_1']=np.array([100.,90.,1.]);m['ULMTUHC_1']=np.array([0.,10.,99.])
        c=dict(Time=t,PRS_1=np.zeros(3),HRR_1=np.ones(3),HRR_E1=np.ones(3))
        model=dict(rooms=[dict(id='B1 R2',leak_area_ratio=[0,0])],openings=[])
        with patch('pyrocast_cfbt.native.read_native_csv',return_value=(m,ids,units)):
            v=validate_native(dict(compartments=c),model,'.')
        p=v['metrics']['upper_fuel_peak']
        self.assertEqual((p['room'],p['time_s'],p['fuel_mass_kg'],p['upper_mixture_mass_kg']),('B1 R2',3600,99,100))

    def test_nonzero_mass_residual_is_not_downgraded_by_review(self):
        v=self.fixture(99,1,mass_error=True)
        self.assertFalse(v['passed']);self.assertIn('mass_balance_zero_source',v['unknown'])

    def test_review_is_shown_without_falsely_labelling_calculation_failure(self):
        v=self.fixture(99,1)
        pb=dict(time_s=[0,3600],solvers={})
        protect_playback(pb,v)
        self.assertTrue(any(s.startswith('입력 가정 검토 필요:') for s in pb['limits']))
        self.assertTrue(any(s.startswith('연소 진단:') for s in pb['limits']))
        self.assertFalse(any(s.startswith('물리 타당성 검사 실패:') for s in pb['limits']))


if __name__=='__main__':unittest.main()
