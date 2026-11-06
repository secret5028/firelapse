from pathlib import Path
import sys,json,subprocess,hashlib
W=Path(__file__).resolve().parent;sys.path.insert(0,str(W/'cad-deps'))
import ezdxf
root=Path('C:/Users/<user>/Desktop/소방 크로키 업-로컬웹앱');tmp=W/'cad-multifloor-check';tmp.mkdir(exist_ok=True)
d=ezdxf.new();m=d.modelspace();m.add_text('1층 평면도');m.add_text('2층 평면도');d.saveas(tmp/'input.dxf')
(tmp/'files.json').write_text(json.dumps([dict(name='two-floors.dxf',stored='input.dxf',floor='1F',sha256=hashlib.sha256((tmp/'input.dxf').read_bytes()).hexdigest())]),'utf8')
r=subprocess.run([str(root/'소방 크로키 업.exe'),'--cad-worker',str(tmp),str(root/'_internal')],timeout=60,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
s=json.loads((tmp/'cad-progress.json').read_text('utf8'));assert r.returncode==1 and '여러 층' in s['error']
record=dict(status='passed',installed_exe_guard='multiple floors rejected even with override',exe_sha256=hashlib.sha256((root/'소방 크로키 업.exe').read_bytes()).hexdigest())
(W.parent/'outputs/CAD-웹앱연결-v11/최종실행파일검사.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf8');print('installed executable guard passed')
