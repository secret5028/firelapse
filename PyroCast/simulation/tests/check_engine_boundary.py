"""Build provenance plus native regression after separating engine ownership."""
from pathlib import Path
import json
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from engine_sources import digest
from verify_engine_boundary import verify_generated, verify_builds
from pyrocast_cfbt.native import execute, load_result


def main():
    build=ROOT/'build/engine-boundary-check'
    report=verify_generated();report['builds']=verify_builds(build)
    canonical={v:digest(ROOT/'build'/v/('cfast-baseline.exe' if v=='baseline' else 'cfast-cfbt.exe')) for v in ('baseline','cfbt')}
    fixture=ROOT/'results/fo_transition_check'
    out=ROOT/'results/verification/engine_boundary'
    records=[]
    for name,variant,source in (('baseline','baseline','run_00'),('extension_off','cfbt','run_00'),('fo_supply','cfbt','run_01')):
        old=fixture/source
        exe=build/variant/('cfast-baseline.exe' if variant=='baseline' else 'cfast-cfbt.exe')
        current=execute(exe,out/name,(old/'case.in').read_text(),(old/'case.cfbt').read_text(),180,120)
        previous=load_result(old,180,{'folder':str(old)})
        differences={family:max(float(np.max(np.abs(value-current['zone'][key])))
                     for key,value in previous['zone'].items() if key.startswith(family+'_'))
                     for family in ('ULT','LLT','HGT','HRR','DJET')}
        if max(differences.values())>1e-8:
            raise AssertionError('Separating source ownership changed native output: '+str(differences))
        records.append({'case':name,'normal_exit':current['run']['normal_exit'],
                        'max_native_difference':differences,'input_sha256':current['run']['input_sha256']})
    for variant,expected in canonical.items():
        assert digest(ROOT/'build'/variant/('cfast-baseline.exe' if variant=='baseline' else 'cfast-cfbt.exe'))==expected
    report['native_checks']=records
    report['canonical_binaries_unchanged']=canonical
    report['purpose']='source ownership refactor regression; not new building simulation'
    path=ROOT/'results/verification/engine_boundary_checks.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
