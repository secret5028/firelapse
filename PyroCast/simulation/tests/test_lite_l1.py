"""L1 contract and event-continuation regressions, not physical validation."""
import json
from pathlib import Path
import sys
import unittest
import numpy as np
from scipy.sparse import eye

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'simulation'))
from pyrocast_lite.adapter import prepare
from pyrocast_lite.runner import run
from pyrocast_lite.core import oxygen_factor


class EventToy:
    """Known continuous ODE: T=20+t, crossing 600 C at t=580 s."""
    N=1;Vmin=np.array([.01])
    def __init__(self):
        self.pending={'child'};self.activation={};self.curves={};self.events_log=[]
    def y0(self):
        y=np.zeros(9);y[2]=293.15;return y
    def rhs(self,t,y):
        dy=np.zeros(9);dy[2]=1.;return dy
    def sparsity(self):return eye(9,format='csr')
    def key(self,r):return ('inter_room','parent')
    def trigger_value(self,key,t,y):return y[2]-873.15
    def activate(self,key,t):
        self.pending.clear();self.events_log.append(t)


class LiteTests(unittest.TestCase):
    def setUp(self):
        self.raw=json.loads((ROOT/'fixtures/room_rule_benchmark_3room.json').read_text('utf-8'))

    def test_closed_fire_component_gets_shared_leakage(self):
        for room in self.raw['rooms']:
            room.update(cad_floor='B3',below_grade=True,leak_area_ratio=[0,0])
        self.raw['openings']=[v for v in self.raw['openings'] if 'OUTSIDE' not in (v['a'],v['b'])]
        model,_=prepare(self.raw)
        self.assertTrue(any(v[1]==model.N for v in model.vents))
        self.assertTrue(model.input_model['minimum_leakage'])
        self.assertFalse(model.sealed_pressure_rooms)
        run(model,60,5,30)
        self.assertTrue(model.integration['complete'])
        self.assertLess(np.max(np.abs(model.sol.y[:model.N])),1000)
        self.assertLess(np.min(model.sol.y[4*model.N+model.ig]),model.y0()[4*model.N+model.ig])
    def test_root_event_continues_state_and_grid(self):
        toy=EventToy();sol=run(toy,700,10,10)
        self.assertTrue(sol.success)
        self.assertAlmostEqual(toy.events_log[0],580,places=6)
        np.testing.assert_allclose(sol.y[2],293.15+sol.t,atol=1e-8)
        self.assertEqual(toy.integration['from_zero_replays'],0)
        self.assertEqual(toy.integration['event_restarts'],1)
        self.assertEqual(len(sol.t),71)
        self.assertAlmostEqual(toy.integration['segments'][1]['start_s'],580,places=6)
    def test_delay_not_applied_twice(self):
        m,_=prepare(self.raw);key=m.key('R2');m.activate(key,100.)
        delay=m.manifest['parents']['R2']['delay_s']
        before=m.fire_sources(100+delay,0)
        after=m.fire_sources(100+delay+1,0)
        self.assertFalse(any(i==m.rmap['R2'] for i,*_ in before))
        self.assertTrue(any(i==m.rmap['R2'] for i,*_ in after))
        self.assertEqual(m.events_log[0]['supply_start_s'],100+delay)
    def test_activation_irreversible_and_not_duplicated(self):
        m,_=prepare(self.raw);key=m.key('R2');m.activate(key,100.);m.activate(key,200.)
        self.assertEqual(m.activation['R2'],100.)
        self.assertEqual(len(m.events_log),1)
    def test_cell_uses_shared_upper_temperature_not_hrr(self):
        m,_=prepare(self.raw)
        y=m.y0();key=('cell_flame','R1');i=m.rmap['R1']
        self.assertLess(m.trigger_value(key,10.,y),0)
        y[2*m.N+i]=573.15
        self.assertAlmostEqual(m.trigger_value(key,10.,y),0)
        y[2*m.N+i]+=1
        self.assertGreater(m.trigger_value(key,10.,y),0)
        self.assertLess(m.trigger_value(('inter_room','R1'),10.,y),0)
        self.raw['room_rule_r8']={'cell_temperature_C':350}
        other,_=prepare(self.raw)
        self.assertLess(other.trigger_value(key,10.,y),0)
    def test_bad_shared_setting_rejected(self):
        self.raw['room_rule_r8']={'temperature_C':449}
        with self.assertRaises(ValueError):prepare(self.raw)
    def test_supply_energy_and_fixed_window_fraction(self):
        m,_=prepare(self.raw)
        for g in m.groups:
            curve=g['room_rule_curve'];energy=np.trapezoid(curve['q'],curve['t'])/1000
            self.assertLessEqual(energy,g['energy_MJ']*(1+1e-9))
        native={v['id']:v for v in m.input_model['openings']}
        for v in m.vents:
            if v[5] in native:self.assertEqual(v[7],native[v[5]]['schedule'][0][1])
        self.assertEqual(m.nb,0)
        self.assertFalse(m.P['pyro_feedback'])
        self.assertEqual(len(m.y0()),11*m.N)  # v6 adopts removal of cumulative E.

    def test_shared_inputs_and_no_duplicate_door_leaks(self):
        m,_=prepare(self.raw)
        self.assertEqual(m.P['kpc'],96000.)
        self.assertEqual(m.P['eps'],.94)
        self.assertEqual(m.P['chi_r'],.35)
        self.assertEqual(m.P['T_out'],293.15)
        self.assertTrue(all(v[8]==0 for v in m.vents))
        for node in m.nodes:
            leaks=[v for v in m.shared['leak_vents'] if v['room']==node['id']]
            self.assertAlmostEqual(sum(x['area'] for x in leaks),node['per']*node['H']*.00017+node['A']*.000052)
        with self.assertRaises(ValueError):prepare(self.raw,{'kpc':1.35e6})

    def test_finite_wall_energy_exchange_closes(self):
        m,_=prepare(self.raw);y=m.y0()
        tu=np.full(m.N,800.);tl=np.full(m.N,300.);height=np.full(m.N,1.5)
        rad=np.array([350000.,0.,0.])
        u,l,d,stats=m.finite_walls.exchange(m,y,tu,tl,height,rad)
        stored=np.sum(d.reshape(m.N,3)*m.finite_walls.capacity)
        self.assertAlmostEqual(stored,float(np.sum(u+l+rad))-stats['wall_back_W'],places=6)
        zero=m.finite_walls.exchange(m,y,np.full(m.N,293.15),np.full(m.N,293.15),height,np.zeros(m.N))
        np.testing.assert_array_equal(zero[2],np.zeros(3*m.N))

    def test_native_oxygen_mass_threshold_and_flow_coefficient(self):
        m,_=prepare(self.raw)
        self.assertEqual(m.P['Cd'],.70)
        self.assertEqual(oxygen_factor(.15,m.P),0.)
        self.assertAlmostEqual(oxygen_factor(.155,m.P),.5,places=12)
        self.assertEqual(oxygen_factor(.16,m.P),1.)
        self.assertEqual(oxygen_factor(.14,m.P),0.)
        self.assertEqual(oxygen_factor(.232,m.P),1.)

    def test_grey_radiation_partition_and_opposite_wall_exchange(self):
        from pyrocast_lite.radiation import upper_absorptivity,wall_to_upper
        m,_=prepare(self.raw,{'gas_radiation_enabled':True});y=m.y0()
        tu=np.full(m.N,800.);tl=np.full(m.N,300.);height=np.full(m.N,1.5)
        rad=np.array([350000.,0.,0.])
        u,l,d,stats=m.finite_walls.exchange(m,y,tu,tl,height,rad)
        storage=float(np.sum(d.reshape(m.N,3)*m.finite_walls.capacity))
        self.assertAlmostEqual(storage-float(np.sum(u+l))+stats['gas_fire_radiation_W']+stats['wall_back_W'],float(rad.sum()),places=6)
        self.assertAlmostEqual(stats['wall_fire_radiation_W']+stats['gas_fire_radiation_W'],float(rad.sum()),places=6)
        self.assertLess(stats['gas_wall_radiation_W'],0.)
        eps,beam=upper_absorptivity(m.Aa,m.pera,m.Ha-height)
        np.testing.assert_allclose(beam,1.8*m.Aa*(m.Ha-height)/(m.Aa+.5*m.pera*(m.Ha-height)))
        cold=np.full((m.N,3),300.);hot=np.full((m.N,3),900.)
        self.assertTrue(np.all(wall_to_upper(tu,cold,m.finite_walls.eps,m.finite_walls.area,eps)<0))
        self.assertTrue(np.all(wall_to_upper(tu,hot,m.finite_walls.eps,m.finite_walls.area,eps)>0))
        np.testing.assert_array_equal(upper_absorptivity(m.Aa,m.pera,np.zeros(m.N))[0],np.zeros(m.N))
        np.testing.assert_array_equal(wall_to_upper(tu,np.full((m.N,3),800.),m.finite_walls.eps,m.finite_walls.area,eps),np.zeros((m.N,3)))


if __name__=='__main__':unittest.main()
