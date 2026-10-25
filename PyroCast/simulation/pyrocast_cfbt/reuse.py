"""Strict reuse of a completed native run; no state restart or partial-result promotion."""
from decimal import Decimal,InvalidOperation
import json,re,shutil
from pathlib import Path
from .native import digest,load_result


def scalar_sidecar(text):
    """Restricted CFBT scalar syntax only. Reject arrays, strings and duplicate keys."""
    match=re.fullmatch(r'\s*&CFBT\s+(.*?)\s*/\s*',text,re.I|re.S)
    if not match:raise ValueError('Unsupported CFBT sidecar syntax')
    body=match[1];result={};pos=0
    pattern=re.compile(r'\s*([a-z][a-z0-9_]*)\s*=\s*(\.true\.|\.false\.|[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[ed][+-]?\d+)?)\s*,?',re.I)
    while pos<len(body):
        item=pattern.match(body,pos)
        if not item:raise ValueError('Unsupported CFBT scalar assignment')
        key=item[1].lower();value=item[2].lower()
        if key in result:raise ValueError('Duplicate CFBT scalar')
        if value in ('.true.','.false.'):value=('logical',value=='.true.')
        else:
            try:
                number=Decimal(value.replace('d','e'))
                value=('number',number,number.is_zero() and number.is_signed())
            except InvalidOperation as exc:raise ValueError('Invalid CFBT number') from exc
        result[key]=value;pos=item.end()
    return result


def prime_completed(source,destination,engine,sidecar,duration_s):
    """Seed an empty run folder. execute() still requires the exact future deck hash.

    Only CFBT scalar formatting/order may differ; no missing/default parameters
    are equated. All saved files, original inputs and engine hashes are verified.
    """
    source=Path(source).resolve();destination=Path(destination).resolve()
    if destination.exists():raise ValueError('Reuse destination already exists')
    saved=json.loads((source/'completed.json').read_text('utf-8'));sig=saved['signature']
    if sig!={**sig,'engine':digest(engine),'input':digest(source/'case.in'),
              'sidecar':digest(source/'case.cfbt'),'required_horizon_s':duration_s,
              'flags':['-V'],'validator_version':2}:
        raise ValueError('Completed native signature mismatch')
    if scalar_sidecar((source/'case.cfbt').read_text('ascii'))!=scalar_sidecar(sidecar):
        raise ValueError('CFBT settings differ')
    if not saved.get('files') or not saved['run'].get('normal_exit'):
        raise ValueError('No verified completed output')
    for name,sha in saved['files'].items():
        if Path(name).name!=name or digest(source/name)!=sha:raise ValueError('Completed output changed')
    if 'NORMAL EXIT' not in (source/'case.log').read_text(errors='replace').upper():
        raise ValueError('Missing native completion')
    load_result(source,duration_s,saved['run'])
    shutil.copytree(source,destination)
    (destination/'case.cfbt').write_text(sidecar,'ascii')
    copied=json.loads(json.dumps(saved));copied['signature']['sidecar']=digest(destination/'case.cfbt')
    copied['run']['folder']=str(destination)
    (destination/'completed.json').write_text(json.dumps(copied,indent=2),'utf-8')
    (destination/'reuse-evidence.json').write_text(json.dumps({'source':str(source),
        'original_signature':sig,'sidecar_comparison':'identical typed scalar assignments; order/decimal notation ignored',
        'future_deck_must_match_exactly':True},indent=2),'utf-8')
