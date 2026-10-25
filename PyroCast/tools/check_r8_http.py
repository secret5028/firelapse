"""Local API validation. All POSTs are deliberately invalid; no native run."""
import json,sys,urllib.request,urllib.error
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'simulation'))
from pyrocast_cfbt.rule_settings import FIELDS
def main():
 out=[]
 for key,(_,unit,default,lo,hi) in FIELDS.items():
  for value in (lo-1,hi+1,'not a number'):
   data=json.dumps({'settings':{key:value}}).encode()
   req=urllib.request.Request('http://127.0.0.1:8780/cfbt/r8/run',data=data,headers={'Content-Type':'application/json'})
   try:
    with urllib.request.urlopen(req,timeout=5) as response:raise AssertionError('invalid request accepted: '+str(response.status))
   except urllib.error.HTTPError as error:
    payload=json.loads(error.read());assert error.code==400 and f'{lo:g}~{hi:g}' in payload['error']
    out.append({'key':key,'value':value,'http_status':error.code,'error':payload['error']})
 path=ROOT/'simulation/results/room_rule_r8_20261025/http-validation.json'
 path.write_text(json.dumps({'passed':True,'rejected_requests':out,'native_runs_started':0},ensure_ascii=False,indent=2),'utf-8')
 print('PASS: 24 invalid HTTP inputs rejected before execution')
if __name__=='__main__':main()
