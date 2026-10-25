from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import Mock
import time
import numpy as np
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.iteration import merge,iterate
from pyrocast_cfbt.conditions import logic,term,phenomenon,evaluate
from pyrocast_cfbt.spread import assess

ROOT=Path(__file__).resolve().parents[1]


class IterationTests(unittest.TestCase):
    def setUp(self):
        self.m=normalize(json.loads((ROOT/'examples/three_rooms.json').read_text()))
        self.m['spread'].update(iteration_mode='fixed_point',max_runs=6,max_passes=4)

    def event(self,gid='reserve_R2',at=1.,room='R2'):
        return {'group':gid,'room':room,'t_ign_s':at,'event_id':gid,'candidate':'C_1','xyz':[5,2,0]}

    def native(self,sha):
        return {'run':{'input_sha256':sha,'wall_seconds':1},'zone':{'Time':np.arange(3.)}}

    def test_batch_retains_later_event_and_flags_condition_disagreement(self):
        old=[self.event(at=100)]
        new,_,flags=merge(self.m,old,[],[self.event(at=120)],[])
        self.assertEqual(new,old)
        self.assertEqual(flags[0]['kind'],'later_or_missing')

    def test_earlier_event_replaces_location_and_all_terms(self):
        old=self.event(at=100);new=self.event(at=50);new['xyz']=[6,2,0];new['largest_incident_term']='djet'
        events,_,_=merge(self.m,[old],[],[new],[])
        self.assertEqual(events,[new])

    def test_fo_pool_removes_later_solid_and_truncation_rechecks_source(self):
        e=self.event(at=10);fo={'room':'R2','t_ign_s':5}
        es,fs,flags=merge(self.m,[],[],[e],[fo])
        self.assertEqual(es,[]);self.assertEqual(fs,[])
        self.assertEqual({f['kind'] for f in flags},{'pooled_by_fo','fo_without_source'})
        self.m['spread']['max_added_ignitions']=0
        es,fs,flags=merge(self.m,[],[],[self.event(at=1)],[fo])
        self.assertFalse(fs)
        self.assertIn('truncated',{f['kind'] for f in flags})

    def test_no_events_one_pass(self):
        current=self.native('first');run=Mock();assessor=Mock(return_value=([],[],{}))
        result=iterate(self.m,current,[],run,[current['run']],[{}],time.monotonic(),assessor,Mock(return_value=[]),Mock())
        self.assertEqual(result[7],'converged');self.assertTrue(result[-1]['condition_consistent']);run.assert_not_called()

    def test_calculated_prefix_seed_is_reassessed_with_its_existing_source_context(self):
        event=self.event(at=1.)
        self.m['native_prefix_seed']={'basis':'computed_native_prefix','horizon_s':2.,
                                     'events':[event],'transitions':[]}
        current=self.native('seeded');run=Mock();assessor=Mock(return_value=([event],[],{}))
        result=iterate(self.m,current,[],run,[current['run']],[{}],time.monotonic(),assessor,Mock(return_value=[]),Mock())
        self.assertEqual(assessor.call_args.args[3],[event])
        self.assertTrue(assessor.call_args.kwargs['reevaluate'])
        self.assertEqual(result[1],[event]);self.assertTrue(result[-1]['condition_consistent'])
        run.assert_not_called()

    def test_prefix_seed_cannot_import_an_event_from_its_future(self):
        self.m['native_prefix_seed']={'basis':'computed_native_prefix','horizon_s':2.,
                                     'events':[self.event(at=3.)],'transitions':[]}
        with self.assertRaisesRegex(ValueError,'horizon'):normalize(self.m)

    def test_failed_proposal_is_never_committed(self):
        current=self.native('first');e=self.event()
        result=iterate(self.m,current,[],Mock(side_effect=TimeoutError('budget')),[current['run']],[{}],time.monotonic(),Mock(return_value=([e],[],{})),Mock(return_value=[]),Mock())
        self.assertEqual(result[0]['run']['input_sha256'],'first')
        self.assertEqual(result[1],[]);self.assertEqual(result[6],[e]);self.assertEqual(result[7],'time_budget')

    def test_pass_limit_leaves_last_assessed_schedule_and_pending_separate(self):
        self.m['spread']['max_passes']=1;current=self.native('first');run=Mock();e=self.event()
        result=iterate(self.m,current,[],run,[current['run']],[{}],time.monotonic(),Mock(return_value=([e],[],{})),Mock(return_value=[]),Mock())
        run.assert_not_called();self.assertEqual(result[1],[]);self.assertEqual(result[6],[e]);self.assertEqual(result[7],'not_converged')

    def test_stall_is_distinct_from_budget_and_keeps_last_completed_schedule(self):
        from pyrocast_cfbt.native import NativeRunInterrupted
        current=self.native('first');e=self.event()
        run=Mock(side_effect=NativeRunInterrupted('native_progress_stalled',1570,3600,145))
        result=iterate(self.m,current,[],run,[current['run']],[{}],time.monotonic(),
                       Mock(return_value=([e],[],{})),Mock(return_value=[]),Mock())
        self.assertEqual(result[7],'solver_stalled')
        self.assertEqual(result[1],[])
        self.assertEqual(result[0],current)
        self.assertEqual(run.call_count,1)

    def test_reassessment_retains_secondary_radiation_context(self):
        from unittest.mock import patch
        t=np.array([0.,1.,2.]);e=self.event(at=1.5)
        target={'id':'C_1','group':e['group'],'room':'R2','material':self.m['material'],'normal':[1,0,0]}
        native={'zone':{'Time':t},'devices':{'TRGFLXI_1':np.ones(3),'B_TRGFLXI_1':np.ones(3),'TRGGAST_1':np.full(3,20.)}}
        response={'crossing_s':1.4,'surface_C':np.array([20.,30.,400.]),'absorbed_kJ_m2':t,'energy_residual_kJ_m2':0}
        with patch('pyrocast_cfbt.spread.room_series',return_value={}),patch('pyrocast_cfbt.spread.supplementary',return_value=({'secondary':np.ones(3)},False)) as sup,patch('pyrocast_cfbt.spread.plate',return_value=response):
            decisions,views,_=assess(self.m,native,[target],[e],reevaluate=True)
        self.assertEqual(sup.call_args.args[4],[e])
        self.assertEqual(decisions,[])  # Crossing uses contaminated right endpoint t=2.
        np.testing.assert_allclose(views[0]['terms_kW_m2']['secondary'],1.)


class ConditionTests(unittest.TestCase):
    def test_three_valued_or_and(self):
        self.assertEqual(logic([[True,False,None],[None,None,False]],'or'),[True,None,None])
        self.assertEqual(logic([[True,False,None],[None,None,False]]),[None,False,False])

    def test_signed_margin_and_null_preserve_actual_reaction(self):
        tr=term('O2','O2',[8.,12.,None],10.,'<','%','criteria.oxygen_deficient_vol_percent',3)
        self.assertEqual(tr['met'],[True,False,None]);self.assertEqual(tr['margin'],[2.,-2.,None])
        p=phenomenon([0.,5.,10.],[tr],{'Q_bulk_kW':[1,2,3]})
        self.assertEqual(p['duration_s'],5.)
        self.assertEqual(p['intensity']['Q_bulk_kW'],[1,None,None])
        self.assertEqual(p['actual_quantities']['Q_bulk_kW'],[1,2,3])

    def test_existing_fgi_screening_preserved_on_completed_case(self):
        r=json.loads((ROOT/'results/cad_exterior_risk_demo_v4_ceiling/result.json').read_text('utf-8'))
        conditions=evaluate(r['scenario'],r)
        for rid in r['rooms']:
            self.assertEqual(conditions[rid]['fgi']['all_met'],r['phenomena'][rid]['tags']['FGI_POTENTIAL'])
            term_=conditions[rid]['fgi']['terms'][0]
            self.assertEqual(term_['threshold'],r['scenario']['criteria']['fgi_fuel_mass_fraction'])
            self.assertNotEqual(term_['threshold'],r['scenario']['gas']['fuel_min_mass_fraction'])
        json.dumps(conditions,allow_nan=False)

    def test_fo_unknown_flux_does_not_override_true_temperature(self):
        r=json.loads((ROOT/'results/cad_exterior_risk_demo_v4_ceiling/result.json').read_text('utf-8'))
        model=deepcopy(r['scenario']);model['flashover']['criterion']='temperature_or_flux'
        for p in r['phenomena'].values():p['floor_incident_flux_kW_m2']=None
        conditions=evaluate(model,r)
        key='CAD_3F_R25';record=conditions[key]['fo']
        for i,temp in enumerate(r['rooms'][key]['T_upper_C']):
            self.assertEqual(record['all_met'][i],True if temp>=model['criteria']['fo_temperature_C'] else None)

    def test_forced_ignition_keeps_separate_oxygen_threshold_and_time_window(self):
        r=json.loads((ROOT/'results/cad_exterior_ignition_demo_v4_ceiling_250/result.json').read_text('utf-8'))
        model=r['scenario'];force=model['ignition_assumption'];record=evaluate(model,r)[force['room']]['upper_gas']
        oxygen=next(x for x in record['terms'] if x['key']=='O2')
        for i,t in enumerate(r['time_s']):
            forced=force['time_s']<=t<force['time_s']+force['duration_s']
            self.assertEqual(record['ignition_context']['forced_window'][i],forced)
            self.assertEqual(oxygen['threshold'][i],force['oxygen_min_vol_percent'] if forced else model['gas']['oxygen_min_vol_percent'])


if __name__=='__main__':unittest.main()
