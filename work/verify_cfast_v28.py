from pathlib import Path
import csv, hashlib, json, math
from cfast_combustion import sustained_intervals

root=Path(__file__).resolve().parent.parent
out=root/'outputs/CAD-연소표현-v28'
base=json.loads((root/'outputs/CAD-속도검증-v27/final/cfast-demo.json').read_text(encoding='utf8'))
new=json.loads((out/'cfast-demo.json').read_text(encoding='utf8'))
stripped=json.loads(json.dumps(new)); stripped.pop('combustion')
stripped['assumptions']=[a.replace('기본 모드는 구획별 수치를 표시하고 실감보기의 문·천장 방향 불꽃은 연출로 표시',
                                  '문·천장을 따라 이어지는 국소 화염 형상은 아직 표시하지 않음') for a in stripped['assumptions']]
for f in stripped['fires']:
    f.pop('expected_hrr');f.pop('pyrolysis_kg_s')
assert stripped==base, 'Existing solver data was modified'
assert sustained_intervals([0,5,10,15],[False,True,False,False])==[]
assert sustained_intervals([0,5,10,15],[True,True,True,False])==[dict(onset=0,confirmed=10,end=15)]
assert sustained_intervals([0,5,10],[True,True,True])==[dict(onset=0,confirmed=10,end=None)]
assert sustained_intervals([0,5,10],[False,False,False])==[]
c=new['combustion'];assert len(c['jets'])==1
j=c['jets'][0];assert j['solver_key']=='3F_R2' and j['anchor']['vent_id']=='3F_D14'
assert j['onset']==635 and abs(j['peak_kW']-816.952)<.001
assert j['peak_time']==1000 and j['hrr'][0]==0
assert sum(1 for f in new['fires'] if f['ignition_time'] is not None)==3
for r in c['rooms']:
    assert len(r['expected_kW'])==361
    for e in r['intervals']:
        assert e['confirmed']-e['onset']==10
        start=int(e['onset']/5);stop=int(e['confirmed']/5)
        assert all(r['limited'][start:stop+1])
assert c['rooms'][0]['intervals'][0]['onset']==635
assert not c['rooms'][1]['intervals'] and not c['rooms'][2]['intervals']
before=(out/'backup/model.html').read_text(encoding='utf8')
after=(out/'model.html').read_text(encoding='utf8')
marker='// Coupled CFAST results on the original CAD scene.'
assert before.split(marker)[0]==after.split(marker)[0], 'Legacy viewer prefix changed'
report=dict(status='passed',physical_validation=False,solver_rerun=False,
    existing_result_data_unchanged=True,legacy_ui_prefix_unchanged=True,
    first_limitation_seconds=635,confirmation_seconds=645,jet_peak_kW=j['peak_kW'],jet_peak_seconds=1000,
    native_jet_resolution='compartment',jet_ribbons_removed=True,
    synthetic_interval_cases_passed=True,
    result_sha256=hashlib.sha256((out/'cfast-demo.json').read_bytes()).hexdigest(),
    model_sha256=hashlib.sha256((out/'model.html').read_bytes()).hexdigest(),
    building_sha256=new['building_sha256'])
(out/'검증결과.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(report,ensure_ascii=False))
