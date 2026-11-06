"""Portable Windows launcher. Starts only local web servers, never a calculation."""
from pathlib import Path
import argparse, json, os, socket, subprocess, sys, time, webbrowser

ROOT = Path(__file__).resolve().parents[1]
PORTS = (8780, 8832, 8841, 8842, 8843, 8844)

def environment():
    env = os.environ.copy()
    env.pop('PYTHONHOME', None)
    env['PYTHONPATH'] = os.pathsep.join(str(ROOT/p) for p in
        ('simulation/deps', 'simulation/plot_deps', 'simulation', 'tools'))
    env['PYTHONUTF8'] = '1'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PATH'] = str(ROOT.parent/'runtime/node') + os.pathsep + env.get('PATH', '')
    return env

def prepare_paths():
    """Rebase configuration references only; saved calculation bytes remain intact."""
    meta = json.loads((ROOT.parent/'distribution.json').read_text('utf8'))
    marker = ROOT/'config/portable-location.json'
    previous = json.loads(marker.read_text('utf8'))['root'] if marker.exists() else meta['source_root']
    prefixes = {previous.replace('\\','/').rstrip('/'), meta['source_root'].replace('\\','/').rstrip('/')}
    def move(value):
        if isinstance(value, dict): return {k:move(v) for k,v in value.items()}
        if isinstance(value, list): return [move(v) for v in value]
        if isinstance(value, str):
            path = value.replace('\\','/')
            for prefix in prefixes:
                if path.lower().startswith(prefix.lower()+'/'):
                    tail=path[len(prefix)+1:]
                    old='simulation/results/github-publish-20261026/PyroCast/'
                    if tail.startswith(old): tail=tail[len(old):]
                    return str(ROOT/tail)
        return value
    for folder in (ROOT/'config', ROOT/'simulation/config'):
        for path in folder.rglob('*.json'):
            if path.name in ('ai.json','cad-import.local.json','portable-location.json'): continue
            old=json.loads(path.read_text('utf-8-sig')); new=move(old)
            if old!=new: path.write_text(json.dumps(new,ensure_ascii=False,indent=2)+'\n','utf8')
    marker.write_text(json.dumps({'root':str(ROOT)},ensure_ascii=False),'utf8')

def check():
    sys.path[:0]=[str(ROOT/p) for p in ('simulation/deps','simulation/plot_deps','simulation','tools')]
    import numpy, scipy, shapely
    from model_library import entries, model_path
    rows=[]
    for entry in entries():
        path=model_path(entry)
        if not path.is_file(): raise FileNotFoundError(path)
        json.loads(path.read_text('utf8'))
        rows.append(entry['label'])
    required=['simulation/viewer/overlay.js','simulation/viewer/theme.css',
              'cad-project/model.html','data/wando-coldstore/P1-playback.json',
              'cad-project/work/cad-web/local-resources/cad-assets/three.module.js',
              'simulation/build/baseline/cfast-baseline.exe']
    for name in required:
        if not (ROOT/name).is_file(): raise FileNotFoundError(name)
    print(json.dumps({'check':'PASS','buildings':rows,'numpy':numpy.__version__,
                     'scipy':scipy.__version__,'shapely':shapely.__version__,
                     'new_simulations':0},ensure_ascii=False),flush=True)

def serve(name):
    import runpy
    sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'simulation/deps'),str(ROOT/'simulation/plot_deps'),str(ROOT/'simulation')]
    if name=='library':
        script=ROOT/'tools/serve_model_library.py';args=['--port','8841']
    elif name=='wando':
        script=ROOT/'tools/serve_wando_c11.py';args=['--port','8832']
    else:
        script=ROOT/'tools/serve_cfbt_building.py'
        args=[str(ROOT/'cad-project'),'--building',str(ROOT/'cad-project/building.json'),'--port','8780']
    sys.argv=[str(script),*args];runpy.run_path(str(script),run_name='__main__')

def available(port):
    try:
        with socket.socket() as s:s.bind(('127.0.0.1',port))
        return True
    except OSError:return False

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    parser.add_argument('--no-browser',action='store_true');parser.add_argument('--serve',choices=['library','wando','ganghwa'])
    args=parser.parse_args()
    os.chdir(ROOT)
    if args.serve:return serve(args.serve)
    prepare_paths();check()
    if args.check:return
    occupied=[p for p in PORTS if not available(p)]
    if occupied:raise RuntimeError('이미 실행 중인 프로그램의 포트입니다: '+str(occupied)+'\n기존 FireLapse 실행 창을 종료한 뒤 다시 실행하세요. 다른 프로세스를 강제 종료하지 않습니다.')
    logs=ROOT.parent/'logs';logs.mkdir(exist_ok=True)
    children=[];streams=[]
    try:
        for name in ('library','wando','ganghwa'):
            stream=(logs/(name+'.log')).open('a',encoding='utf8');streams.append(stream)
            children.append(subprocess.Popen([sys.executable,'-B','-X','utf8',str(Path(__file__).resolve()),'--serve',name],
                cwd=ROOT,env=environment(),stdout=stream,stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0)))
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            if any(p.poll() is not None for p in children):raise RuntimeError('서버 시작 실패. logs 폴더를 확인하세요.')
            if all(not available(p) for p in PORTS):break
            time.sleep(.25)
        else:raise TimeoutError('서버 준비 시간 초과. logs 폴더를 확인하세요.')
        url='http://127.0.0.1:8842/model.html'
        print('\nFireLapse 실행 중: '+url+'\n이 창을 유지하세요. 종료는 Ctrl+C. 계산 중에는 종료하지 마세요.',flush=True)
        if not args.no_browser:webbrowser.open(url)
        while all(p.poll() is None for p in children):time.sleep(1)
        raise RuntimeError('서버가 종료되었습니다. logs 폴더를 확인하세요.')
    except KeyboardInterrupt:print('\nFireLapse 종료',flush=True)
    finally:
        for child in children:
            if child.poll() is None:child.terminate()
        for child in children:
            try:child.wait(timeout=8)
            except subprocess.TimeoutExpired:child.kill();child.wait()
        for stream in streams:stream.close()

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('실행 실패: '+str(exc),file=sys.stderr,flush=True);sys.exit(1)
