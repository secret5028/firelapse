import json,re,unittest
from pathlib import Path
import numpy as np
from pyrocast_cfbt.model import normalize
from pyrocast_cfbt.deck import make_deck,candidates
from pyrocast_cfbt.mixture import primary_ratio,CO_HEAT_J_KG
from pyrocast_cfbt.thermal import plate,_plate_python

ROOT=Path(__file__).resolve().parents[1]
class MixtureTests(unittest.TestCase):
 def test_mass_supply_and_total_chemical_energy_survive_partition(self):
  m=normalize(json.loads((ROOT/'examples/three_rooms.json').read_text()));g=m['fuel_groups'][0]
  off=make_deck(m,[],candidates(m));m['gas']['mixture_enabled']=True;on=make_deck(m,[],candidates(m));ratio=primary_ratio(m,g)
  for a,b in zip(re.findall(r'DATA=([^/]+)',off),re.findall(r'DATA=([^/]+)',on)):
   qa=float(a.split(',')[1]);qb=float(b.split(',')[1]);self.assertAlmostEqual(qa/g['heat_of_combustion_kJ_kg'],qb/(g['heat_of_combustion_kJ_kg']*ratio),places=10)
  self.assertAlmostEqual(g['heat_of_combustion_kJ_kg']*1000*ratio+g['co_yield']*CO_HEAT_J_KG,g['heat_of_combustion_kJ_kg']*1000)
 def test_invalid_energy_basis_is_rejected(self):
  raw=json.loads((ROOT/'examples/three_rooms.json').read_text());raw['gas'].update(mixture_enabled=True,energy_basis='unknown')
  with self.assertRaises(ValueError):normalize(raw)
 def test_impossible_product_yield_or_oxygen_demand_is_rejected(self):
  for formula in ({'carbon':.001,'hydrogen':4.,'oxygen':0.,'nitrogen':0.,'chlorine':0.},
                  {'carbon':1.,'hydrogen':4.,'oxygen':20.,'nitrogen':0.,'chlorine':0.}):
   raw=json.loads((ROOT/'examples/three_rooms.json').read_text());raw['gas']['mixture_enabled']=True
   raw['fuel_groups'][0]['formula']=formula
   with self.assertRaisesRegex(ValueError,'negative products'):normalize(raw)
 def test_compiled_plate_matches_reference_and_crossing(self):
  m=normalize(json.loads((ROOT/'examples/three_rooms.json').read_text()));t=np.arange(0,601,5.);q=5+20*np.sin(t/600*np.pi)**2;gf=20+500*(1-np.exp(-t/60));qb=np.ones(len(t))*.4;gb=np.ones(len(t))*20
  a=_plate_python(m['material'],t,q,qb,gf,gb,nodes=17,dt=.2);b=plate(m['material'],t,q,qb,gf,gb,nodes=17,dt=.2)
  np.testing.assert_allclose(a['surface_C'],b['surface_C'],atol=1e-9,rtol=0);self.assertAlmostEqual(a['crossing_s'],b['crossing_s'],places=9)
