from pathlib import Path
import sys,json,shutil,time,datetime
ROOT=Path(r'C:/Users/예방/Documents/ChatGPT/PyroCast')
sys.path.insert(0,str(ROOT/'tools'))
from cad_completion import complete
from cad_import import geometry_checks
from apply_hotel_autocorrect import check
from ai_connection import runtime_settings,runtime_completion
base=Path(__file__).resolve().parent
cfg=runtime_settings()
if not cfg:raise SystemExit('AI not connected; no correction attempted')
work=base/('actual-api-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
work.mkdir()
for p in (base/'extraction').glob('source-*.png'):shutil.copyfile(p,work/p.name)
source=base/'extraction/building.json'
calls=[]
def transport(messages):
    context=json.loads(next(p['text'] for p in messages[1]['content'] if p['type']=='text'))
    row=dict(call=len(calls)+1,floor=context.get('floor'),stage=context.get('stage','correction'),candidates=len(context.get('candidates',[])),image=any(p.get('type')=='image_url' for p in messages[1]['content']))
    messages[0]['content']+='\n검토 전용이다. 제공된 원본 이미지 판독을 위한 native vision 또는 vision_analyze만 허용한다. 셸·파일 수정·네트워크 추가 검색·시뮬레이션은 하지 말고 제공된 이미지와 후보만 판독하라.'
    started=time.monotonic();print(json.dumps(row,ensure_ascii=False),flush=True)
    try:
        response=runtime_completion(messages,purpose='cad_review')
        try:
            data=json.loads(response)
            row['json_response']=isinstance(data,dict)
            if isinstance(data,dict):
                allowed={x['id'] for x in context.get('candidates',[])}
                for key in ('accept','uncertain'):
                    values=data.get(key)
                    if isinstance(values,list):row[key]=[x for x in values if isinstance(x,str) and x in allowed]
                row['schema_keys_ok']=set(data)=={'accept','uncertain'}
        except (ValueError,TypeError):row['json_response']=False
        return response
    except Exception as exc:
        row['error_type']=type(exc).__name__
        raise
    finally:
        row['elapsed_s']=round(time.monotonic()-started,2);calls.append(row)
        (work/'api-calls.json').write_text(json.dumps(calls,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps(row,ensure_ascii=False),flush=True)
started=time.monotonic()
b,report=complete(source,work,arc_evidence=json.loads((base/'arcs.json').read_text(encoding='utf8')),transport=transport)
target=work/'building.json';target.write_text(json.dumps(b,ensure_ascii=False),encoding='utf8')
errors,rows=geometry_checks(b,['1F','2F'])
report['geometry_checks']=dict(errors=errors,floors=rows)
try:report['loader_checks']=check(target)
except Exception as exc:report['loader_checks']=[dict(ok=False,error_type=type(exc).__name__)]
report['actual_api']=dict(model=cfg['model'],calls=len(calls),elapsed_s=round(time.monotonic()-started,2),raw_response_saved=False)
(work/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(dict(work=str(work),ai_status=b['cad_completion']['ai_status'],changes=len(b['cad_completion']['changes']),validation=b['cad_completion']['validation'],loaders=report['loader_checks'],actual_api=report['actual_api']),ensure_ascii=False),flush=True)
