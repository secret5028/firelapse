"""Auditable numeric and rule checks over the filled server briefing."""
import json,re,math
from d5_match import matches
from d5_tools import finite
NUM=re.compile(r'\d+(?:\.\d+)?')

def audit(value):
    from lite_ai_briefing import number,stamp
    from d5_briefing import LIMITS,SIGNS
    allowed=set(NUM.findall(LIMITS+' '+SIGNS+' 1 2 3 4 1.8 '+str(len(value['calls']))))
    def walk(x):
        if isinstance(x,dict):
            for k,v in x.items():walk(k);walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
        elif finite(x):
            allowed.update(NUM.findall(str(x)+' '+number(x)+' '+stamp(x)))
        elif isinstance(x,str):allowed.update(NUM.findall(x))
    for call in value['calls']:walk(call['data'])
    walk(value['matching_log']);walk(value['case'])
    printed=NUM.findall(value['text'])
    bad=sorted(set(printed)-allowed)
    rules=next(c['data'] for c in value['calls'] if c['tool']=='get_tactic_rules')
    table={r['code']:r for r in rules['rules']}
    invalid=[]
    for row in value['matching_log']:
        if row['text']!=table[row['code']]['text'] or not matches(table[row['code']],row['values']):invalid.append(row['code'])
    used=set(value['rules']); rendered={r['code'] for r in value['rendered_rules']}
    printed_codes=set(re.findall(r'\[([A-Z]-\d+)\]',value['text']))
    if used!=rendered or used!=printed_codes:invalid.append('display/log mismatch')
    for row in value['rendered_rules']:
        if row['code']!='G-0' and row not in value['matching_log']:invalid.append('unmatched '+row['code'])
        if row['text']!=table[row['code']]['text']:invalid.append('rewritten '+row['code'])
    route=next(c['data'] for c in value['calls'] if c['tool']=='get_route')
    segments=route['hose_segments']; r=route['route']
    hose_ok=not r.get('error') and len(segments)==r['hoses']
    if segments:
        width=segments[0]['to_m']-segments[0]['from_m']
        hose_ok &= len(segments)==math.ceil(r['length']/width)
    return dict(numeric_tokens=len(printed),numeric_mismatches=bad,rule_mismatches=invalid,
                forbidden_units=re.findall(r'(?i)lpm|초간|\bmm\b',value['text']),hose_count_matches=hose_ok,
                call_count=len(value['calls']),rule_codes=sorted(used))
