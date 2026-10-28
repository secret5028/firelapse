"""Exercise real HTTP admission/routes with a fake CLI worker, never a solver."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation')]
PROJECT='C:/Users/예방/Documents/Codex/2026-10-14/files-pasted-by-the-user-cad3d'

def child(folder):
    import lite_mc_service as mc
    from result_catalog import atomic_json
    mc.JOBS=Path(folder)/'jobs';mc.LATEST=mc.JOBS/'latest.json'
    def fake_work(out):
        atomic_json(out/'progress.json',dict(state='running',completed=0,total=2,current='S00'))
        time.sleep(2)
        atomic_json(out/'progress.json',dict(state='completed',completed=2,total=2))
    mc.compute=fake_work
    import serve_cfbt_building
    sys.argv=['serve',PROJECT,'--port','8793'];serve_cfbt_building.main()

def request(path,body=None):
    req=urllib.request.Request('http://127.0.0.1:8793'+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=60) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:return e.code,json.load(e)

def main():
    with tempfile.TemporaryDirectory(dir=ROOT/'simulation/results',prefix='server_stage5_test_http') as directory:
        with (Path(directory)/'console.txt').open('w',encoding='utf-8') as log:
            process=subprocess.Popen([sys.executable,'-X','utf8',__file__,'--child',directory],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:
                for _ in range(100):
                    if process.poll() is not None:raise RuntimeError((Path(directory)/'console.txt').read_text('utf-8'))
                    try:code,status=request('/cfbt/lite/mc');break
                    except OSError:time.sleep(.1)
                else:raise RuntimeError('test server timeout')
                assert code==200 and status['available'] and not status['running']
                assert request('/cfbt/lite/mc',dict(room='CAD_3F_R3',samples=1))[0]==400
                code,job=request('/cfbt/lite/mc',dict(room='CAD_3F_R3',samples=2,duration_s=1800,seed=1))
                assert code==202 and job['workers']==1 and job['budget_s_per_sample']==1200
                assert request('/cfbt/lite/mc',dict(room='CAD_3F_R3',samples=2))[0]==409
                assert request('/cfbt/run',{})[0]==409
                for _ in range(50):
                    code,status=request('/cfbt/lite/mc')
                    if status['state']=='completed':break
                    time.sleep(.1)
                assert status['state']=='completed' and not status['running']
                saved=json.loads((Path(directory)/'jobs'/job['id']/'request.json').read_text('utf-8'));assert saved['room']=='CAD_3F_R3'
                code,data=request('/cfbt/lite/screening');assert code==200 and data['attention']['records']
                assert len(data['attention']['records'])==16
                code,catalog=request('/cfbt/lite/catalog.json?mc_room=CAD_3F_R2');assert code==200
                assert {'S06','S09'}<={x['id'] for x in catalog['cases']}
                code,cases=request('/cfbt/cases');assert code==200 and any(x['id']=='windows30' for x in cases)
                output=dict(real_http=True,fake_worker=True,solver_calls=0,accepted=202,duplicate=409,native_while_mc=409,
                    invalid=400,finished=status['state'],attention_records=len(data['attention']['records']),lite_cases=len(catalog['cases']),native_cases=len(cases))
                dest=ROOT/'simulation/results/ui_refactor_stage5A_20261028/http.json';dest.parent.mkdir(exist_ok=True);dest.write_text(json.dumps(output,indent=2)+'\n','utf-8');print(json.dumps(output))
            finally:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()

if __name__=='__main__':
    if '--child' in sys.argv:child(sys.argv[-1])
    else:main()
