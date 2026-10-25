"""Exact-input bulk reaction isolation. Never searches or publishes a scenario."""
import json
from pathlib import Path
import re
from .native import digest, execute, interruption_status


def prepare_bulk_pair(source, output, engine):
    source=Path(source).resolve(); output=Path(output).resolve(); engine=Path(engine).resolve()
    deck=(source/'case.in').read_bytes()
    sidecar=(source/'case.cfbt').read_bytes()
    flag=re.compile(rb'(\bbulk_enabled\s*=\s*)\.TRUE\.',re.I)
    if len(flag.findall(sidecar))!=1:
        raise ValueError('Source must contain exactly one enabled bulk reaction flag')
    off=flag.sub(rb'\g<1>.FALSE.',sidecar)
    planned=source/'planned-execution.json'
    engine_hash=digest(engine)
    if planned.exists() and json.loads(planned.read_text())['engine']!=engine_hash:
        raise ValueError('Use the same engine executable as the source run')
    output.mkdir(parents=True,exist_ok=False)
    for name,contents in [('bulk_on',sidecar),('bulk_off',off)]:
        folder=output/name;folder.mkdir()
        (folder/'case.in').write_bytes(deck)
        (folder/'case.cfbt').write_bytes(contents)
    manifest={'source':str(source),'engine':str(engine),'engine_sha256':engine_hash,
              'input_sha256':digest(source/'case.in'),'source_sidecar_sha256':digest(source/'case.cfbt'),
              'only_change':'bulk_enabled TRUE -> FALSE; all fire/FO schedules and native input bytes fixed',
              'no_automatic_retry':True,'status':'prepared_not_run',
              'limitations':['OFF is the same extended engine with bulk reaction disabled, not pristine CFAST.',
                             'Progress watchdog does not measure internal DASSL step size.',
                             'Passing OFF isolates a reaction dependency, not proof of gate chatter.']}
    (output/'comparison.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return manifest


def run_bulk_pair(output, timeout_s=600., stall_s=90.):
    output=Path(output); path=output/'comparison.json'; report=json.loads(path.read_text('utf-8'))
    if report['status']!='prepared_not_run':raise ValueError('Pair already started; prepare a fresh folder to repeat')
    engine=Path(report['engine'])
    if digest(engine)!=report['engine_sha256']:raise ValueError('Engine changed since preparation')
    for name in ('bulk_on','bulk_off'):
        if digest(output/name/'case.in')!=report['input_sha256']:raise ValueError('Frozen deck changed')
    on=(output/'bulk_on/case.cfbt').read_bytes();off=(output/'bulk_off/case.cfbt').read_bytes()
    if digest(output/'bulk_on/case.cfbt')!=report['source_sidecar_sha256'] or re.sub(
        rb'(\bbulk_enabled\s*=\s*)\.TRUE\.',rb'\g<1>.FALSE.',on,flags=re.I)!=off:
        raise ValueError('Pair settings changed since preparation')
    deck=(output/'bulk_on/case.in').read_text('ascii')
    match=re.search(r'\bSIMULATION\s*=\s*([0-9.eE+\-]+)',deck,re.I)
    if not match:raise ValueError('No native SIMULATION duration')
    duration=float(match[1]);report.update(status='running',cases={})
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    for name in ('bulk_on','bulk_off'):
        folder=output/name
        try:
            result=execute(engine,folder,deck,(folder/'case.cfbt').read_text('ascii'),duration,
                           min(600.,max(.01,timeout_s)),stall_timeout_s=stall_s,preserve_input_files=True)
            record={'status':'completed','wall_seconds':result['run']['wall_seconds'],
                    'last_native_time_s':duration,'input_sha256':result['run']['input_sha256']}
        except (TimeoutError,RuntimeError,ValueError) as exc:
            record={'status':interruption_status(exc) if isinstance(exc,TimeoutError) else 'solver_failed','error':str(exc)}
            state=folder/'execution-state.json'
            if state.exists():record['execution']=json.loads(state.read_text())
        report['cases'][name]=record
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    report['status']='comparison_finished'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report
