"""C7 isolated adapter/service tests; no external AI or solver execution."""
import sys,json,tempfile,shutil,os,uuid,hashlib,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation'),str(ROOT/'simulation/deps')]
import lite_ai_fuel as ai
from pyrocast_lite import screening_v8_approved as approved

def exercise():
    source=ROOT/'simulation/results/room_rule_r8_20261025/source-scenario.json'
    raw=json.loads(source.read_text('utf-8'));sha=raw['cad']['building_sha256']
    building={'floors':[{'name':'3F','use':'factory','rooms':[{'id':r['id'].split('_',2)[2],'names':[r.get('name','')],'area':25} for r in raw['rooms']]}]}
    original=(ai.CONFIG,ai.OVERRIDES,approved.HERE)
    key=uuid.uuid4().hex+uuid.uuid4().hex;env='PYROCAST_C7_TEST_KEY';os.environ[env]=key
    try:
        with tempfile.TemporaryDirectory(dir=ROOT/'simulation/results') as d:
            d=Path(d);ai.CONFIG=d/'ai.json';ai.OVERRIDES=d/'config/fuel-overrides.json';approved.HERE=d/'pyrocast_lite';approved.HERE.mkdir()
            for f in ['fire_load_table.json','approved_uses_v8.json']:shutil.copyfile(original[2]/f,approved.HERE/f)
            assert not ai.status(building,sha)['configured']
            ai.CONFIG.write_text(json.dumps(dict(base_url='http://127.0.0.1:8000/v1',model='fixture',api_key_env=env)))
            assert ai.status(building,sha)['configured']
            before=approved.score(raw,8);rank_before={r['room']:r['rank1'] for r in before['ranked']}
            rows=[dict(room_id='CAD_3F_R2',usage_class='shopping',reason='모의 응답: 판매시설 용도 요청')]
            calls=[]
            def transport(cfg,secret,messages):
                assert secret==key;calls.append(messages)
                assert 'classes' in messages[0]['content'] and 'CAD_3F_R2' in messages[0]['content']
                return '설명\n'+json.dumps(rows) if len(calls)==1 else json.dumps(rows)
            proposal=ai.propose({'message':'3층 R2를 소매점으로','history':[]},building,sha,transport)
            assert proposal['attempts']==2 and len(calls)==2 and not ai.OVERRIDES.exists()
            try:ai.apply({'proposal_id':proposal['proposal_id'],'rooms':['CAD_3F_R1']},building,sha);raise AssertionError('unchecked rows accepted')
            except ValueError:pass
            ai.apply({'proposal_id':proposal['proposal_id'],'rooms':['CAD_3F_R2']},building,sha)
            after=approved.score(raw,8);rank_after={r['room']:r['rank1'] for r in after['ranked']}
            use=after['approved_input']['room_uses']['CAD_3F_R2'];assert use['load_MJ_m2']==600 and use['hrrpua_kW_m2']==250
            assert before['origin_budgets']['CAD_3F_R2']!=after['origin_budgets']['CAD_3F_R2']
            assert rank_before!=rank_after
            for raw_reply in ['```json\n[]\n```','[] trailing',json.dumps([dict(room_id='CAD_3F_R2',usage_class='invented',reason='bad')]),key]:
                tries=[]
                def bad(*args):tries.append(1);return raw_reply
                try:ai.propose({'message':'test','history':[]},building,sha,bad);raise AssertionError('bad response accepted')
                except ValueError as e:assert key not in str(e) and len(tries)==2
            try:ai.apply({'proposal_id':proposal['proposal_id'],'rooms':['CAD_3F_R2']},building,sha);raise AssertionError('replay accepted')
            except ValueError:pass
            for f in d.rglob('*'):
                if f.is_file():assert key.encode() not in f.read_bytes()
            assert key not in json.dumps(proposal)
            # grep the ephemeral key through stdin: no key in argv or captured output.
            grep=subprocess.run(['rg','--fixed-strings','--files-with-matches','--file','-',str(d),str(ROOT/'tools/lite_ai_fuel.py'),str(ROOT/'app/web/panels/ai_fuel.js'),*([str(ROOT/'simulation/results/ui_C7_20261102')] if (ROOT/'simulation/results/ui_C7_20261102').exists() else [])],input=key+'\n',text=True,capture_output=True)
            assert grep.returncode==1, 'Credential found or grep failed'

            return {'passed':True,'api_calls':0,'solver_runs':0,'retry_once':True,'secret_echo_rejected':True,'key_file_matches':0,'key_grep_returncode':grep.returncode,'R2_rank_before':rank_before['CAD_3F_R2'],'R2_rank_after':rank_after['CAD_3F_R2'],'load_after':use['load_MJ_m2'],'hrrpua_after':use['hrrpua_kW_m2']}
    finally:ai.CONFIG,ai.OVERRIDES,approved.HERE=original;os.environ.pop(env,None)

if __name__=='__main__':
    report=exercise();out=ROOT/'simulation/results/ui_C7_20261102';out.mkdir(exist_ok=True)
    (out/'unit-verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
