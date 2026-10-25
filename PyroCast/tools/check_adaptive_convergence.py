"""Small active-operator time-step and refresh-interval checks; not a floor rerun."""
import json,re
from test_adaptive_radiation import OUT,ENGINE,differences,diagnostics
from pyrocast_cfbt.native import execute,load_result

base=OUT/'controlled';source=base/'adaptive'
deck=(source/'case.in').read_text('ascii');side=(source/'case.cfbt').read_text('ascii')
reference=load_result(source,600,{})
half,n=re.subn(r'MAX_TIME_STEP\s*=\s*[\d.eE+-]+','MAX_TIME_STEP=0.5',deck,count=1)
if n!=1:raise ValueError('Missing native step control')
report={'basis':'controlled two-fire/vent-change fixture with active reduction; no production threshold changes','cases':{}}
for name,text,settings in [('half_step',half,side),('half_refresh',deck,side.rsplit('/',1)[0]+' adaptive_refresh_s=5\n/\n')]:
    run=execute(ENGINE,base/name,text,settings,600,90)
    delta=differences(reference,run)
    report['cases'][name]={'run':run['run'],'differences':delta,'adaptive':diagnostics(base/name),
        'accepted':max(delta['T_upper_C'],delta['T_lower_C'])<1 and delta['o2_upper_vol']<.1 and delta['bulk_relative_difference']<.03}
    print(json.dumps({name:report['cases'][name]},ensure_ascii=False),flush=True)
report['accepted']=all(r['accepted'] for r in report['cases'].values())
(base/'convergence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
