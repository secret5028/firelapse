from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from pyrocast_cfbt.cad import adapt
from pyrocast_cfbt.topology import corrected_building, vertical_selection
from test_practical import building_fixture


class TopologyTests(unittest.TestCase):
    def temp(self):
        base=Path(__file__).resolve().parents[1]/'results/unit_tmp';base.mkdir(parents=True,exist_ok=True)
        return tempfile.TemporaryDirectory(dir=base)

    def test_correction_is_hash_bound_and_preserves_source(self):
        raw=building_fixture();raw['floors'][0]['provenance']={'source_sha256':'drawing'}
        before=deepcopy(raw)
        change={'action':'reclassify_door','floor':'GF','source_sha256':'drawing',
                'id':'Door','sides':['Office','Passage'],'width_m':.6,'height_m':2.1}
        with self.temp() as tmp:
            path=Path(tmp)/'repairs.json'
            path.write_text(json.dumps({'buildings':[{'building_sha256':'building','changes':[change]}]}))
            unchanged,applied=corrected_building(raw,'different',path)
            self.assertIs(unchanged,raw);self.assertEqual(applied,[])
            result,applied=corrected_building(raw,'building',path)
            self.assertEqual(result['floors'][0]['simulation_graph']['connections'][0]['kind'],'door_service')
            self.assertEqual(raw,before);self.assertEqual(len(applied),1)
            raw['floors'][0]['provenance']['source_sha256']='other_drawing'
            with self.assertRaises(ValueError):corrected_building(raw,'building',path)

    def test_doorless_passage_cannot_be_closed_by_door_setting(self):
        raw=building_fixture()
        raw['floors'][0]['simulation_graph']['connections'][0]['kind']='open_passage'
        with self.temp() as tmp:
            path=Path(tmp)/'building.json';path.write_text(json.dumps(raw))
            model=adapt(path,{'scope_floor':'GF','door_fraction':0.,'opening_overrides':{'CAD_GF_Door':0.}})
        self.assertEqual(model['openings'][0]['schedule'],[[0,1.]])

    def test_confirmed_terrace_is_not_an_indoor_room_or_fuel_source(self):
        raw=building_fixture();raw['floors'][0]['provenance']={'source_sha256':'drawing'}
        before=deepcopy(raw)
        change={'action':'classify_outdoor','floor':'GF','source_sha256':'drawing',
                'id':'Passage','name':'테라스','display_barrier_height_m':1.1}
        with self.temp() as tmp:
            repairs=Path(tmp)/'repairs.json';repairs.write_text(json.dumps({'buildings':[{'building_sha256':'building','changes':[change]}]}))
            fixed,_=corrected_building(raw,'building',repairs)
            path=Path(tmp)/'building.json';path.write_text(json.dumps(fixed))
            model=adapt(path,{'scope_floor':'GF','fire_floor':'GF','fire_room':'Office'})
        self.assertEqual(raw,before)
        self.assertEqual(len(model['rooms']),1)
        self.assertTrue(all(g['room']=='CAD_GF_Office' for g in model['fuel_groups']))
        self.assertEqual(model['openings'][0]['b'],'OUTSIDE')

    def test_vertical_scope_keeps_core_and_access_not_remote_whole_floor(self):
        raw=building_fixture();remote=deepcopy(raw['floors'][0]);remote['name']='UF';remote['z']=3.
        remote['rooms'].append({**deepcopy(remote['rooms'][0]),'id':'Unconnected'})
        raw['floors'].append(remote)
        raw['core_nodes']=[{'floor':'UF','core_id':'Stair','room_id':'Passage'}]
        self.assertEqual(vertical_selection(raw,'GF')['UF'],{'Passage','Office'})


if __name__=='__main__':unittest.main()
