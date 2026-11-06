"""Automatic future-CAD import orchestration; no conversion, API or solver job."""
import copy, json, sys, tempfile, threading, unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation/plot_deps')]
import cad_import as imp
import model_operation as op
import cad_completion
import apply_hotel_autocorrect

def building():
    polygon=[{'o':[[0,0],[10,0],[10,10],[0,10]],'h':[]}]
    return dict(floors=[dict(name='1F',z=0,h=3,align='verified',slab=polygon,
        rooms=[dict(id='R1',area=100,polys=polygon,names=['Office'])],openings=[],
        simulation_graph={'isolated_rooms':['R1']})],model_review={'items':[]},
        cad_completion=dict(ai_status='not_connected',ai_calls=0))

class PipelineTest(unittest.TestCase):
    def run_import(self,*,expected=None,corrected=None,valid=True,review=False,completion_report=None):
        with tempfile.TemporaryDirectory() as tmp,ExitStack() as stack:
            root=Path(tmp);ident='b'*32;dest=root/'imports'/ident
            (dest/'extraction').mkdir(parents=True)
            def save(p,v):p.write_text(json.dumps(v),encoding='utf8')
            save(dest/'manifest.json',dict(id=ident,state='running',name='Future CAD',files=[],expected=expected or ['1F']))
            save(dest/'extraction/building.json',building());save(dest/'arcs.json',{'floors':[]})
            registry=root/'registry.json';save(registry,{'models':[]})
            # Existing generated model must survive a rejected correction.
            if review:save(dest/'building.json',{'previous':'preserve'})
            original=(dest/'building.json').read_bytes() if review else None
            lock=threading.Lock();lock.acquire()
            stack.enter_context(patch.object(imp,'ROOT',root))
            stack.enter_context(patch.object(imp,'STAGING',root/'imports'))
            stack.enter_context(patch.object(imp,'LOCK',lock))
            stack.enter_context(patch.object(imp.model_library,'REGISTRY',registry))
            stack.enter_context(patch.object(imp.subprocess,'run',return_value=SimpleNamespace(returncode=0)))
            complete=stack.enter_context(patch('cad_completion.complete',return_value=(copy.deepcopy(corrected or building()),completion_report or {})))
            stack.enter_context(patch('apply_hotel_autocorrect.check',return_value=[dict(floor='1F',ok=valid)] if valid else [dict(floor='1F',ok=False,error='invalid input')]))
            # Keep registration real, but do not bind a listener during tests.
            start=stack.enter_context(patch.object(op,'ensure_server'))
            imp.worker(ident,review)
            self.assertFalse(lock.locked())
            value=imp.read(dest/'manifest.json');rows=imp.read(registry)['models']
            preserved=(dest/'building.json').read_bytes()==original if review else None
            return value,rows,complete.call_count,start.call_count,preserved

    def test_new_cad_automatically_reaches_operational_registration(self):
        v,rows,calls,starts,_=self.run_import()
        self.assertEqual(v['state'],'complete');self.assertEqual(calls,1);self.assertEqual(starts,1)
        self.assertEqual(v['pipeline_revision'],imp.PIPELINE_REVISION)
        self.assertEqual([s['stage'] for s in v['pipeline']],['extract','validate','correct','verify','load','register','complete'])
        self.assertTrue(rows[0]['simulation_enabled']);self.assertEqual(v['url'],rows[0]['operation_url'])
        self.assertEqual(rows[0]['execution_mode'],'library_lite')
        self.assertEqual(v['ai_status'],'not_connected');self.assertEqual(v['ai_calls'],0)
        self.assertEqual(v['unresolved'],1)

    def test_missing_floor_stops_before_ai_and_publication(self):
        v,rows,calls,starts,_=self.run_import(expected=['1F','2F'])
        self.assertEqual(v['state'],'blocked');self.assertEqual((rows,calls,starts),([],0,0))

    def test_rejected_post_ai_geometry_preserves_previous_model(self):
        bad=building();bad['floors']=[]
        v,rows,calls,starts,preserved=self.run_import(corrected=bad,review=True)
        self.assertEqual(v['state'],'blocked');self.assertTrue(preserved)
        self.assertEqual((rows,calls,starts),([],1,0))

    def test_independent_geometry_error_blocks_publication(self):
        v,rows,calls,starts,preserved=self.run_import(review=True,completion_report={'completion':{'validation':{'geometry_error_count':1}}})
        self.assertEqual(v['state'],'blocked');self.assertTrue(preserved)
        self.assertEqual((rows,calls,starts),([],1,0))

    def test_loader_failure_keeps_review_without_simulation_claim(self):
        v,rows,_,_,_=self.run_import(valid=False)
        self.assertEqual(v['state'],'complete');self.assertFalse(rows[0]['simulation_enabled'])
        self.assertIsNone(v['operation_url']);self.assertIn('검토 필요',v['message'])

if __name__=='__main__':unittest.main()
