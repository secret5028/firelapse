"""Local GET-only preview server. No execution API or simulation dependency."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import json
from urllib.parse import urlsplit, unquote

ROOT=Path(__file__).resolve().parents[1]


class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        path=urlsplit(self.path).path
        if path.startswith('/cfbt/storage/'):
            from storage_cleanup import handle
            if handle(self,path):return
        if path.startswith('/cfbt/lite/ai/'):
            from lite_ai_http import handle
            return handle(self,path)
        return self.send_error(405)

    def json(self,value,status=200):
        data=json.dumps(value,ensure_ascii=False).encode('utf-8')
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)

    def do_GET(self):
        path=urlsplit(self.path).path
        data_dir=ROOT/'data/wando-coldstore'
        read=lambda name:json.loads((data_dir/name).read_text(encoding='utf-8'))
        if path=='/':
            self.send_response(302);self.send_header('Location','/data/wando-coldstore/model.html');self.end_headers();return
        if path in ('/cfbt/lite/active.json','/cfbt/lite/result/wando-P1'):return self.json(read('P1-playback.json'))
        if path=='/cfbt/lite/catalog.json':
            from result_catalog import playback_origin, playback_coverage
            payload=read('P1-playback.json')
            return self.json({'cases':[{'id':'wando-P1','label':'완도 P1 · 순정 CFAST · 59:55','engine_kind':'cfast_native','complete':payload.get('complete') is True,'origin_room_id':playback_origin(payload),'covered_room_ids':playback_coverage(payload)}],'progress_text':'마지막 5 s 미출력','reuse_by_case':{'wando-P1':{'label':'P1 원본 CSV 재생 · 재계산 없음','equivalent':False}}})
        if path=='/cfbt/calculation':return self.json({'state':'idle','available':False,'cfast_available':False,'running':False,'server_busy':False})
        if path=='/cfbt/lite/mc':return self.json({'available':False,'running':False,'error':'P1 저장 결과 보기 전용'})
        if path=='/cfbt/reuse/lite/wando-P1':return self.json({'case_id':'wando-P1','label':'P1 원본 CSV 재생 · 재계산 없음','equivalent':False})
        if path=='/cfbt/lite/doors':
            b=read('operating-building.json');rows=[]
            for e in b['floors'][0]['simulation_graph']['connections']:
                rows.append(dict(id='CAD_1F_'+e['id'],a='CAD_1F_'+e['sides'][0],b='OUTSIDE',door_class='external',confidence='confirmed',connected_names=e['sides'],reason='C11 저장 입력',fixed_state={'open':True,'effective_fraction':1}))
            return self.json({'rows':rows,'fixed_state':None})
        if path=='/cfbt/lite/screening':return self.json({'score':{'top_n':0,'ranked':[],'excluded':[],'opening_states':[]},'manual_origins':[],'selection':{},'comparison':None,'progress':{'running':False}})
        if path=='/cfbt/lite/ai/fuel':return self.json({'configured':False,'message':'P1 저장 결과 보기 전용','rooms':[]})
        if path=='/cfbt/model-info':return self.json({'building_id':'wando-coldstore','label':'완도 저온창고','read_only':True})
        if path=='/cfbt/lite/fire-load-table':
            src=ROOT/'simulation/pyrocast_lite/fire_load_table.json'
            return self.json(json.loads(src.read_text(encoding='utf-8')))
        if path.startswith('/cfbt/'):
            name=unquote(path[len('/cfbt/'):]);src=ROOT/'simulation/viewer'/name
            if not any(c in name for c in '/\\') and src.is_file():
                self.path='/simulation/viewer/'+name;return super().do_GET()
            return self.send_error(404)
        if path in ('/vendor/three.module.js','/vendor/OrbitControls.js'):
            name='three.module.js' if path.endswith('three.module.js') else 'addons/controls/OrbitControls.js'
            paths=[ROOT/'cad-project/work/cad-web/local-resources/cad-assets/three.module.js',
                   ROOT/'simulation/results/github-publish-20261026/PyroCast/cad-project/work/cad-web/local-resources/cad-assets/three.module.js']
            paths=[p.parent/name for p in paths]
            src=next((p for p in paths if p.exists()),None)
            if src is None:return self.send_error(404,'Bundled Three.js missing')
            data=src.read_bytes();self.send_response(200);self.send_header('Content-Type','text/javascript');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
        if not path.startswith(('/data/wando-coldstore/','/app/web/')):
            return self.send_error(404)
        return super().do_GET()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8831);args=parser.parse_args()
    print(f'http://127.0.0.1:{args.port}/data/wando-coldstore/preview.html',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),partial(Handler,directory=str(ROOT))).serve_forever()
