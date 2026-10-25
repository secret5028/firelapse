"""Project-owned executable/CSV adapter. This is not upstream CFAST code."""
from pathlib import Path
import csv
import hashlib
import json
import math
import os
import re
import subprocess
import time
import numpy as np


class NativeRunInterrupted(TimeoutError):
    def __init__(self, reason, native_time_s, duration_s, wall_seconds):
        self.reason=reason
        self.native_time_s=native_time_s
        self.wall_seconds=wall_seconds
        super().__init__(f'CFAST 미완료: {reason}; 마지막 진행 약 {native_time_s:g}/{duration_s:g}초. 부분 결과는 완료로 저장하지 않습니다.')


def interruption_status(exc):
    return 'solver_stalled' if getattr(exc,'reason',None)=='native_progress_stalled' else 'time_budget'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def native_float(value):
    """Fortran E-format omits the E when the exponent needs three digits."""
    value=value.strip()
    try:return float(value)
    except ValueError:
        match=re.fullmatch(r'([+-]?(?:\d+\.\d*|\.\d+))([+-]\d{3,})',value)
        if match:return float(match[1]+'e'+match[2])
        if re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)[dD][+-]?\d+',value):
            return float(value.lower().replace('d','e'))
        raise


def read_native_csv(path,until_s=None):
    with Path(path).open(encoding='utf-8-sig') as f:
        # Native Fortran's fixed repeated format ends a wrapped physical line with a comma.
        # Preserve interior blank unit cells; remove only that known continuation terminator.
        reader=iter(row[:-1] if len(row)==16385 and row[-1]=='' else row for row in csv.reader(f))
        first=next(reader)
        if first[0].strip()=='s':
            # CFAST wraps very wide Smokeview records into physical lines of 16385 cells.
            # Join the units, names, and every numeric record before interpreting timestamps.
            units=list(first); row=next(reader)
            while row[0].strip()!='Time':
                units.extend(row);row=next(reader)
            names=list(row); first_data=None
            for row in reader:
                try:float(row[0])
                except ValueError:names.extend(row);continue
                first_data=row;break
            if len(names)!=len(units) or first_data is None:
                raise ValueError('Malformed wrapped native CSV header')
            ids=names; records=[]; record=[]
            import itertools
            for row in itertools.chain([first_data],reader):
                if not row or not any(v.strip() for v in row):continue
                if not record and until_s is not None and float(row[0])>until_s+1e-3:break
                record.extend(row)
                if len(record)>len(names):raise ValueError('Native CSV record exceeds header width')
                if len(record)==len(names):records.append([native_float(v) for v in record]);record=[]
            if record:raise ValueError('Incomplete wrapped native CSV record')
            rows=records
        else:
            names=first; next(reader); ids=next(reader); units=next(reader)
            rows=[]
            for row in reader:
                if not row or not any(v.strip() for v in row):continue
                if until_s is not None and float(row[0])>until_s+1e-3:break
                rows.append([native_float(v) for v in row])
    data=np.asarray(rows,float)
    if data.ndim!=2 or data.shape[1]!=len(names) or not np.isfinite(data).all():
        raise ValueError(f'Invalid native data: {path}')
    if len(data)<2 or not np.all(np.diff(data[:,0])>0):
        raise ValueError(f'Invalid native time ordering: {path}')
    return {n:data[:,i] for i,n in enumerate(names)}, dict(zip(names,ids)), dict(zip(names,units))


def read_diagnostic(path,until_s=None):
    with Path(path).open(encoding='utf-8-sig') as f:
        rows=list(csv.DictReader(f))
    result=[]
    for row in rows:
        if until_s is not None and float(row['time_s'])>until_s+1e-3:break
        converted={k:native_float(v) for k,v in row.items()}
        if not all(math.isfinite(v) for v in converted.values()):
            raise ValueError(f'Nonfinite CFBT diagnostic: {path}')
        result.append(converted)
    return result


def execute(exe, folder, deck, sidecar, duration_s, timeout_s, stall_timeout_s=90., *, preserve_input_files=False):
    exe=Path(exe).resolve(); folder=Path(folder).resolve(); folder.mkdir(parents=True,exist_ok=True)
    if preserve_input_files:
        if (folder/'case.in').read_text('ascii')!=deck or (folder/'case.cfbt').read_text('ascii')!=sidecar:
            raise ValueError('Frozen native inputs do not match the requested diagnostic')
    else:
        (folder/'case.in').write_text(deck,encoding='ascii')
        (folder/'case.cfbt').write_text(sidecar,encoding='ascii')
    signature={'engine':digest(exe),'input':digest(folder/'case.in'),'sidecar':digest(folder/'case.cfbt'),
               'flags':['-V'],'required_horizon_s':duration_s,'validator_version':2}
    (folder/'planned-execution.json').write_text(json.dumps(signature,indent=2),encoding='utf-8')
    cache=folder/'completed.json'
    if cache.exists():
        saved=json.loads(cache.read_text())
        if saved.get('signature')==signature and all((folder/name).exists() and digest(folder/name)==sha for name,sha in saved.get('files',{}).items()):
            if saved.get('files'):
                native_log=folder/'case.log'
                if native_log.exists() and 'NORMAL EXIT' in native_log.read_text(errors='replace').upper():
                    return load_result(folder,duration_s,dict(saved['run'],cache_hit=True))
    cache.unlink(missing_ok=True)
    # A retry must not treat the previous run's final status as new progress.
    (folder/'case.status').unlink(missing_ok=True)
    started=time.monotonic(); last_progress=started; last_time=0.
    statefile=folder/'execution-state.json'
    def state(status, reason=None):
        payload={'status':status,'reason':reason,'last_native_time_s':last_time,
                 'requested_horizon_s':duration_s,'wall_seconds':time.monotonic()-started}
        tmp=statefile.with_suffix('.tmp');tmp.write_text(json.dumps(payload,indent=2),encoding='utf-8');tmp.replace(statefile)
    state('running')
    with (folder/'execution.log').open('w',encoding='utf-8') as log:
        process=subprocess.Popen([str(exe),'case','-V'],cwd=folder,stdout=log,stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            while process.poll() is None:
                try:
                    header=(folder/'case.status').read_text(errors='replace').splitlines()[0]
                    match=re.search(r'T\s*=\s*([0-9.Ee+\-]+)',header)
                    value=float(match[1]) if match else last_time
                    if value>last_time:
                        last_time=value;last_progress=time.monotonic();state('running')
                except (OSError,ValueError,IndexError):pass
                elapsed=time.monotonic()-started
                reason=('wall_time_budget' if elapsed>=timeout_s else
                        'native_progress_stalled' if stall_timeout_s and time.monotonic()-last_progress>=stall_timeout_s else None)
                if reason:
                    state('incomplete',reason)
                    raise NativeRunInterrupted(reason,last_time,duration_s,elapsed)
                try:process.wait(timeout=.5)
                except subprocess.TimeoutExpired:pass
        except BaseException:
            if process.poll() is None:process.kill();process.wait()
            raise
    log=(folder/'execution.log').read_text(encoding='utf-8',errors='replace')
    if (folder/'case.log').exists():
        log+='\n'+(folder/'case.log').read_text(encoding='utf-8',errors='replace')
    if process.returncode!=0 or 'NORMAL EXIT' not in log.upper():
        state('failed','abnormal_native_exit')
        raise RuntimeError('CFAST failed: '+log[-3000:])
    run={'folder':str(folder),'engine_sha256':signature['engine'],'input_sha256':signature['input'],
         'wall_seconds':time.monotonic()-started,'cache_hit':False,'normal_exit':True}
    try:result=load_result(folder,duration_s,run)
    except (ValueError,OSError,StopIteration):
        state('failed','invalid_native_output');raise
    last_time=float(duration_s);state('completed')
    files=[p for p in folder.glob('case*.csv')]+[folder/'execution.log',folder/'case.log']
    payload={'signature':signature,'run':run,'files':{p.name:digest(p) for p in files}}
    temporary=folder/'completed.json.tmp'
    temporary.write_text(json.dumps(payload,indent=2),encoding='utf-8'); temporary.replace(cache)
    return result


def load_result(folder,duration_s,run,allow_prefix=False):
    folder=Path(folder)
    result={'run':run}
    for key,suffix in [('zone','_zone.csv'),('compartments','_compartments.csv'),('devices','_devices.csv'),('native_vents','_vents.csv')]:
        path=folder/('case'+suffix)
        # Stock CFAST creates an empty devices CSV when the deck has no devices.
        # A transport-only floor run is valid; do not manufacture target values.
        if key in ('devices','native_vents') and path.exists() and path.stat().st_size==0:
            kind='DEVC' if key=='devices' else 'VENT'
            if re.search(r'&'+kind+r'\b',(folder/'case.in').read_text(encoding='ascii'),re.I):
                raise ValueError('Empty '+key+' output for a deck containing '+kind)
            result[key]={'Time':result['zone']['Time'].copy()}
            result[key+'_ids']={'Time':'Time'}; result[key+'_units']={'Time':'s'}
            continue
        data,ids,units=read_native_csv(path,duration_s if allow_prefix else None)
        if data['Time'][-1]<duration_s-max(1e-6,1e-7*duration_s):
            raise ValueError('Native output did not reach the requested horizon')
        mask=data['Time']<=duration_s+1e-3
        if data['Time'][mask][-1]<duration_s-1e-3:
            raise ValueError('Requested horizon sample is missing')
        result[key]={k:v[mask] for k,v in data.items()}; result[key+'_ids']=ids; result[key+'_units']=units
    if not np.array_equal(result['devices']['Time'],result['zone']['Time']):
        raise ValueError('Inconsistent native output timestamps')
    if not np.array_equal(result['native_vents']['Time'],result['zone']['Time']):
        raise ValueError('Inconsistent native vent output timestamps')
    # Smokeview zone HRR uses kW; compartment fire outputs use W.
    for key,unit in result['zone_units'].items():
        if key.startswith('HRR_') and unit=='kW':
            result['zone'][key]=result['zone'][key]*1000
            result['zone_units'][key]='W'
    for key,value in result['compartments'].items():
        if key.startswith(('HRR_','HRRC_','DJET_')):
            result['zone'][key]=value
            result['zone_units'][key]=result['compartments_units'][key]
    for key in ('rooms','vents','slabs','mixture','jets'):
        path=folder/f'case_cfbt_{key}.csv'
        rows=[r for r in read_diagnostic(path,duration_s if allow_prefix else None) if r['time_s']<=duration_s+1e-3] if path.exists() else []
        timestamps=result['zone']['Time']
        for row in rows:
            position=int(np.searchsorted(timestamps,row['time_s']))
            options=[j for j in (position-1,position) if 0<=j<len(timestamps)]
            nearest=min(options,key=lambda j:abs(timestamps[j]-row['time_s']))
            if abs(timestamps[nearest]-row['time_s'])>max(1e-7,abs(row['time_s'])*1e-10):
                raise ValueError('Unaligned CFBT/native diagnostic timestamp')
            row['time_s']=float(timestamps[nearest])
        result[key]=rows
    return result
