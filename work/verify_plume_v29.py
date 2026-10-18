from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parent.parent;out=root/'outputs/CAD-공식플룸-v29'
old=json.loads((out/'backup/cfast-demo.json').read_text(encoding='utf8'));new=json.loads((out/'cfast-demo.json').read_text(encoding='utf8'))
stripped=json.loads(json.dumps(new));stripped.pop('plume_postprocess')
for f in stripped['fires']:f.pop('plume_inputs')
assert old==stripped,'Original numerical data changed'
marker='// Coupled CFAST results on the original CAD scene.'
before=(out/'backup/model.html').read_text(encoding='utf8');after=(out/'model.html').read_text(encoding='utf8')
assert before.split(marker)[0]==after.split(marker)[0],'Legacy UI changed'
assert 'rib.positions.set' not in after
assert all(f['plume_inputs']['chi']==.33 and not f['plume_inputs']['hall'] for f in new['fires'])
report=dict(status='passed',building_sha256=new['building_sha256'],model_sha256=hashlib.sha256((out/'model.html').read_bytes()).hexdigest(),result_sha256=hashlib.sha256((out/'cfast-demo.json').read_bytes()).hexdigest(),existing_numerical_data_unchanged=True,legacy_ui_unchanged=True,full_building_solver_rerun=False,isolated_native_probe_run=True,physical_validation=False)
(out/'검증결과.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(report)
