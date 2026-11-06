"""Server/CLI contracts only. Solver calls and process execution are mocked."""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation')]
from result_catalog import ResultCatalog,atomic_json,read
from export_ui_attention import result_index,comparison_attention
import lite_mc_service as service
import runtime_storage
import serve_cfbt_building as server


def result(ok=True):
    return dict(ok=ok,t=[0,10],room_summary=[{'original_room':'R','cell':'C'}],
        shared_conditions={'rooms':{'C':{k:{'scores':{'degree':[0,.8]}} for k in ['FO','FGI','backdraft','rollover']}}})


class Contracts(unittest.TestCase):
    def test_batch_publication_serial_and_stable_ids(self):
        import run_lite_mc as cli
        with tempfile.TemporaryDirectory(dir=ROOT/'simulation/results',prefix='server_stage5_test') as directory:
            out=Path(directory);request=dict(room='R3',samples=2,seed=1,duration_s=1800,building_sha256='A')
            atomic_json(out/'request.json',request);atomic_json(out/'input.json',{'rooms':[{'id':'R3','approved_fuel_class':{'label':'공장'}}]})
            samples=[dict(id='S00',kind='mandatory',openings={}),dict(id='S01',kind='mandatory',openings={})];calls=[]
            config=ROOT/'simulation/config/lite-viewer.json';before=config.read_bytes()
            def execute(sample,out,publish):
                calls.append((sample['id'],sample['source_room'],publish))
                if sample['id']=='S01':raise RuntimeError('fixture failure')
                atomic_json(out/sample['id']/'playback.json',{'schema':'pyrocast-cad-playback-1','engine_kind':'pyrocast_lite','time_s':[0,1800],'complete':True,'building_sha256':'A','rooms':[{'original_room':'R3'}]})
                return dict(sample_id=sample['id'],kind=sample['kind'],complete=True,burning_original_rooms=['R3'])
            aggregate=dict(completed=1,failed_or_incomplete=1,condition_sample_rates_random_only={},worst_including_mandatory={})
            def evidence(folder):
                self.assertIn('공장',read(folder/'playback.json')['rooms'][0]['display_name'])
            with patch.object(cli,'write_mc',side_effect=evidence) as proof,patch.object(cli.adopted,'make_samples',return_value=samples),patch.object(cli.adopted,'current_hashes',return_value={}),patch.object(cli.adopted,'execute',side_effect=execute),patch.object(cli.adopted,'aggregate',return_value=aggregate):
                summary=cli.run_batch(out/'request.json',out)
                proof.assert_called_once_with(out/'S00')
            self.assertEqual(calls,[('S00','R3',False),('S01','R3',False)])
            self.assertEqual(read(out/'progress.json')['failed_or_incomplete'],1)
            self.assertEqual(read(out/'started.json')['budget_s_per_sample'],1200)
            self.assertEqual(read(out/'S00/playback.json')['rooms'][0]['display_name'],'공장 (승인 용도)')
            index=ResultCatalog(ROOT/'simulation/results',ROOT/'simulation/config/native-case-aliases.json')
            rel=(out/'S00/playback.json').relative_to(ROOT/'simulation/results').as_posix()
            self.assertEqual(summary['rows'][0]['id'],'case-'+hashlib.sha256(rel.encode()).hexdigest()[:20])
            self.assertFalse(summary['rows'][1]['complete']);self.assertEqual(config.read_bytes(),before)
            with self.assertRaises(RuntimeError):cli.run_batch(out/'request.json',out)

    def test_catalog_discovery_aliases_and_bad_files(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'simulation/results',prefix='server_stage5_test') as directory:
            root=Path(directory);aliases=root/'aliases.json';atomic_json(aliases,{'old':{'label':'kept','relative_path':'native/playback.json'}})
            pb=dict(schema='pyrocast-cad-playback-1',time_s=[0,10],building_sha256='A',complete=True,label='new')
            atomic_json(root/'native/playback.json',pb)
            atomic_json(root/'lite/playback.json',{**pb,'engine_kind':'pyrocast_lite'})
            atomic_json(root/'partial/playback.json',{**pb,'engine_kind':'pyrocast_lite','complete':False})
            atomic_json(root/'different/playback.json',{**pb,'building_sha256':'B'})
            (root/'bad').mkdir();(root/'bad/playback.json').write_text('{')
            index=ResultCatalog(root,aliases);index.scan(True)
            self.assertEqual([x['id'] for x in index.cases('A','native')],['old'])
            self.assertEqual(len(index.cases('A','lite')),1)
            cfg=[dict(id='S09',label='keep S09',path=str(root/'lite/playback.json'))]
            self.assertEqual(index.cases('A','lite',cfg)[0]['id'],'S09')
            atomic_json(root/'new/playback.json',pb);index.scan(True)
            self.assertEqual(len(index.cases('A','native')),2)
            (root/'new/playback.json').unlink();index.scan(True)
            self.assertEqual(len(index.cases('A','native')),1)
            self.assertTrue((root/'playback-catalog.json').is_file())

    def test_attention_invalidation_and_unknown(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'simulation/results',prefix='server_stage5_test') as directory:
            root=Path(directory);source=root/'BDF/result.json';r=result();atomic_json(source,r)
            a=result_index(source);self.assertEqual(a['attention_room_count'],1)
            self.assertEqual(a,result_index(source))
            for k in r['shared_conditions']['rooms']['C']:r['shared_conditions']['rooms']['C'][k]['scores']['degree']=[None,0]
            atomic_json(source,r);b=result_index(source)
            self.assertNotEqual(a['source_sha256'],b['source_sha256']);self.assertEqual(b['unknown_rooms'],['R'])
            case=dict(room='R',state='open',result_folder=str(root),selected_attempt='BDF',complete=True,times={'total_s':1},burning_room_count=1,first_FO_s=None,safe_end_s=10)
            self.assertEqual(len(comparison_attention({'rows':[{'state_results':[case]}]},root)['records']),1)
            case['result_folder']=str(root.parent)
            with self.assertLogs(level='WARNING') as warning:
                skipped=comparison_attention({'rows':[{'state_results':[case]}]},root)
            self.assertEqual(skipped['records'],[])
            self.assertEqual(skipped['attention_skipped'],1)
            self.assertEqual(warning.output,['WARNING:root:screening attention skipped: result outside workspace: result.json'])

    def test_cache_excludes_server_not_engine_inputs(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'simulation/results',prefix='server_stage5_test') as directory:
            root=Path(directory);(root/'pyrocast_cfbt').mkdir();code=root/'pyrocast_cfbt/core.py';code.write_text('a=1');(root/'building_rules.py').write_text('rules=1')
            engine=root/'engine.exe';engine.write_bytes(b'engine');transport=root/'server.py';transport.write_text('v1')
            with patch.object(server,'SIM',root),patch.object(server,'__file__',str(transport)):
                first=server.execution_key({'a':1},'A',engine);transport.write_text('v2')
                self.assertEqual(first,server.execution_key({'a':1},'A',engine))
                self.assertNotEqual(first,server.execution_key({'a':2},'A',engine))
                code.write_text('a=2');self.assertNotEqual(first,server.execution_key({'a':1},'A',engine))
                code.write_text('a=1');engine.write_bytes(b'new');self.assertNotEqual(first,server.execution_key({'a':1},'A',engine))

    def test_validation_and_origin_input(self):
        raw=read(service.locate(service.RESULTS/'room_rule_r8_20261025/source-scenario.json'));sha=raw['cad']['building_sha256']
        for value in [1,0,True,2.5,1001]:
            with self.assertRaises(ValueError):service.prepare_request(dict(room='CAD_3F_R2',samples=value),sha)
        for body in [dict(room='no',samples=2),dict(room='CAD_3F_R2',samples=2,duration_s=25),dict(room='CAD_3F_R2',samples=2,seed=-1)]:
            with self.assertRaises(ValueError):service.prepare_request(body,sha)
        req,model=service.prepare_request(dict(room='CAD_3F_R3',samples=3,duration_s=1800,seed=1),sha)
        self.assertEqual(req['room'],'CAD_3F_R3');self.assertEqual(model['duration_s'],1800)
        self.assertEqual(model['cad']['fire_key'],'CAD_3F_R3');self.assertEqual([g['room'] for g in model['fuel_groups'] if 'initial_time_s' in g],['CAD_3F_R3'])

    def test_reserve_process_wrapper_and_interrupted_state(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'simulation/results',prefix='server_stage5_test') as directory:
            root=Path(directory);jobs=root/'lite_mc_jobs';request=dict(room='R',samples=2,duration_s=1800,seed=1,building_sha256='A')
            with patch.object(runtime_storage,'RESULTS',root),patch.object(service,'JOBS',jobs),patch.object(service,'LATEST',jobs/'latest.json'):
                folder=service.reserve(request,{})
                self.assertTrue(service.status('A')['running'])
                self.assertEqual(service.status('B')['state'],'idle')
                with patch.object(service.subprocess,'Popen') as launch:
                    launch.return_value.pid=123;launch.return_value.wait.return_value=0
                    atomic_json(folder/'progress.json',{'state':'completed'})
                    service.compute(folder);args=launch.call_args.args[0]
                    self.assertIn('run_lite_mc.py',args[3]);self.assertNotIn('shell',launch.call_args.kwargs)
                atomic_json(folder/'progress.json',{'state':'running'})
                with patch.object(service,'process_alive',return_value=False):self.assertEqual(service.status('A')['state'],'interrupted')
                with patch.object(service.subprocess,'Popen',side_effect=OSError('fixture')):
                    with self.assertRaises(OSError):service.compute(folder)
                self.assertEqual(service.status('A')['state'],'failed')

    def test_adopted_budget_and_no_viewer_replacement(self):
        import run_lite_mc_v8_r2 as adopted
        import numpy as np
        with tempfile.TemporaryDirectory(dir=ROOT/'simulation/results',prefix='server_stage5_test') as directory:
            folder=Path(directory);budgets=[];calls=[];config=ROOT/'simulation/config/lite-viewer.json';before=config.read_bytes()
            model=SimpleNamespace(P={},contract={},sol=SimpleNamespace(t=np.array([0,1800]),y=np.zeros((1,2))))
            def fake_run(m,horizon,step,budget,method):
                budgets.append(budget);calls.append((horizon,step,method));m.integration={'wall_seconds':17 if method=='BDF' else 22,'failure':'numerical fixture' if method=='BDF' else None}
            with patch.object(adopted,'prepare',return_value=(model,{})),patch.object(adopted,'run',side_effect=fake_run),patch.object(adopted,'results',side_effect=lambda m:{**result(m.integration['failure'] is None),'postprocess_wall_seconds':0}),patch.object(adopted,'summarize',return_value={'complete':True}),patch.object(adopted,'output_balance_diagnostic',return_value={}),patch.object(adopted,'package',return_value={'label':'fixture'}):
                adopted.execute(dict(id='S00',kind='random',seed=1,scenario={'duration_s':1800}),out=folder,publish=False)
            self.assertEqual(budgets,[1200,1183]);self.assertEqual(calls,[(1800,10,'BDF'),(1800,10,'Radau')]);self.assertEqual(config.read_bytes(),before)
            self.assertTrue((folder/'S00/index-summary.json').exists())


if __name__=='__main__':unittest.main(verbosity=2)
