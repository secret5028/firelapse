"""Portable Windows launcher. Starts only local web servers, never a calculation."""
from pathlib import Path
import argparse, json, os, socket, subprocess, sys, time
from contextlib import redirect_stderr, redirect_stdout
from tempfile import TemporaryDirectory
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
PORTS = (8780, 8832, 8841, 8842, 8843, 8844)
URL = 'http://127.0.0.1:8842/model.html'
CONTROL_URL = 'http://127.0.0.1:8841/models/firelapse-control'
OPEN_LOCAL = build_opener(ProxyHandler({}))

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
            data_prefix=str(meta.get('source_data_root','')).replace('\\','/').rstrip('/')
            if data_prefix and path.lower().startswith(data_prefix.lower()+'/results/'):
                return str(ROOT/'simulation/results'/path[len(data_prefix)+9:])
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
    elif name=='briefings':
        script=ROOT/'tools/saved_briefings.py';args=[]
    else:
        script=ROOT/'tools/serve_cfbt_building.py'
        args=[str(ROOT/'cad-project'),'--building',str(ROOT/'cad-project/building.json'),'--port','8780']
    sys.argv=[str(script),*args];runpy.run_path(str(script),run_name='__main__')

def available(port):
    try:
        with socket.socket() as s:s.bind(('127.0.0.1',port))
        return True
    except OSError:return False


def shutdown_requested(path):
    try:
        return path.read_text('ascii') == 'stop'
    except FileNotFoundError:
        return False


def background():
    import ctypes
    from ctypes import wintypes
    from runtime_storage import DATA_ROOT

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    mutex = kernel.CreateMutexW(None, False, r'Local\FireLapse-Background')
    if not mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    existing = ctypes.get_last_error() == 183
    logs = DATA_ROOT/'logs'
    try:
        if existing:
            try:
                with OPEN_LOCAL.open(CONTROL_URL, timeout=1) as response:
                    if json.load(response).get('managed') and '--no-browser' not in sys.argv:
                        (logs/'open-browser').touch()
            except (OSError, ValueError):
                pass  # The first instance may still be opening.
            return
        logs.mkdir(parents=True,exist_ok=True)
        with (logs/'launcher.log').open('a',encoding='utf8') as log, redirect_stdout(log), redirect_stderr(log):
            try:
                main()
            except Exception:
                import traceback
                traceback.print_exc()
                raise
    finally:
        kernel.CloseHandle(mutex)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true')
    parser.add_argument('--no-browser',action='store_true');parser.add_argument('--serve',choices=['library','wando','ganghwa','briefings'])
    parser.add_argument('--background',action='store_true')
    args=parser.parse_args()
    os.chdir(ROOT)
    if args.serve:return serve(args.serve)
    prepare_paths();check()
    if args.check:return
    occupied=[p for p in PORTS if not available(p)]
    if occupied:raise RuntimeError('이미 실행 중인 프로그램의 포트입니다: '+str(occupied)+'\n기존 FireLapse 실행 창을 종료한 뒤 다시 실행하세요. 다른 프로세스를 강제 종료하지 않습니다.')
    from runtime_storage import DATA_ROOT
    from app_control import SIGNAL_ENV
    import desktop_browser
    browser_exe = None if args.no_browser else desktop_browser.executable()
    logs=DATA_ROOT/'logs';logs.mkdir(parents=True,exist_ok=True)
    open_request=logs/'open-browser'
    open_request.unlink(missing_ok=True)
    session=TemporaryDirectory(prefix='.session-',dir=logs)
    stop_file=Path(session.name)/'shutdown'
    env={**environment(),SIGNAL_ENV:str(stop_file)}
    executable=Path(sys.executable).with_name('python.exe') if args.background else sys.executable
    flags=(subprocess.CREATE_NO_WINDOW if args.background else getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0))
    children=[];streams=[];browser=None
    try:
        for name in ('library','wando','ganghwa','briefings'):
            stream=(logs/(name+'.log')).open('a',encoding='utf8');streams.append(stream)
            children.append(subprocess.Popen([executable,'-B','-X','utf8',str(Path(__file__).resolve()),'--serve',name],
                cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,creationflags=flags))
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            if any(p.poll() is not None for p in children):raise RuntimeError('서버 시작 실패. logs 폴더를 확인하세요.')
            if all(not available(p) for p in PORTS):break
            time.sleep(.25)
        else:raise TimeoutError('서버 준비 시간 초과. logs 폴더를 확인하세요.')
        print('\nFireLapse 실행 중: '+URL+'\n전용 창을 닫거나 상단 종료 버튼을 누르면 종료합니다.',flush=True)
        if browser_exe:
            browser=desktop_browser.start(browser_exe,DATA_ROOT/'browser-profile',URL)
        visible_deadline=time.monotonic()+30
        window_seen=False;missing_since=None;next_shutdown_check=0
        while all(p.poll() is None for p in children):
            if shutdown_requested(stop_file):
                time.sleep(.5)  # Let the shutdown response reach the browser first.
                return
            if browser is not None:
                handles=desktop_browser.windows(browser.pid) if browser.poll() is None else []
                now=time.monotonic()
                if handles:
                    window_seen=True;missing_since=None
                elif window_seen and missing_since is None:
                    missing_since=now
                if open_request.exists():
                    open_request.unlink(missing_ok=True)
                    if handles:
                        desktop_browser.focus(handles)
                    elif window_seen:
                        desktop_browser.close(browser)
                        browser=desktop_browser.start(browser_exe,DATA_ROOT/'browser-profile',URL)
                        visible_deadline=now+30;window_seen=False;missing_since=None
                if not window_seen and (browser.poll() is not None or now>=visible_deadline):
                    raise RuntimeError('FireLapse 전용 브라우저 창을 시작할 수 없습니다.')
                if missing_since is not None and now-missing_since>=1 and now>=next_shutdown_check:
                    next_shutdown_check=now+2
                    try:
                        request=Request(CONTROL_URL,method='POST',headers={'Origin':URL.split('/model.html',1)[0]})
                        with OPEN_LOCAL.open(request,timeout=15):
                            pass
                    except OSError:
                        pass  # The existing shutdown guard protects in-flight calculations.
            time.sleep(.25)
        raise RuntimeError('서버가 종료되었습니다. logs 폴더를 확인하세요.')
    except KeyboardInterrupt:print('\nFireLapse 종료',flush=True)
    finally:
        try:
            desktop_browser.close(browser)
        except (OSError,subprocess.TimeoutExpired) as exc:
            print('전용 창 종료 실패: '+str(exc),file=sys.stderr,flush=True)
        for child in children:
            if child.poll() is None:child.terminate()
        for child in children:
            try:child.wait(timeout=8)
            except subprocess.TimeoutExpired:child.kill();child.wait()
        for stream in streams:stream.close()
        open_request.unlink(missing_ok=True)
        session.cleanup()

if __name__=='__main__':
    is_background='--background' in sys.argv
    try:
        background() if is_background else main()
    except Exception as exc:
        if is_background:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, str(exc), 'FireLapse 실행 실패', 0x10)
        else:
            print('실행 실패: '+str(exc),file=sys.stderr,flush=True)
        sys.exit(1)
