from pathlib import Path
import shutil
W=Path(__file__).resolve().parent;S=W/'cad-web';O=W.parent/'outputs/CAD-웹앱연결-v11'
p=S/'local-resources/local_index.html';s=p.read_text('utf-8-sig').replace("$('download').hidden=true","$('download').hidden=JSON.parse(lastJobs||'[]').find(j=>j.id===id)?.message?.startsWith('CAD ')||false")
p.write_text(s,'utf8');(S/'local_index.html').write_text(s,'utf8')
shutil.copy2(p,O/'배포본/소방 크로키 업-로컬웹앱/_internal/local_index.html')
code=O/'소스';code.mkdir(exist_ok=True)
for p in S.glob('*.py'):shutil.copy2(p,code/p.name)
shutil.copy2(S/'cad_local.spec',code/'cad_local.spec')
shutil.copytree(S/'cad_engine',code/'cad_engine',dirs_exist_ok=True)
for p in ['test_cad_upload.py','finalize_cad_assets.py']:shutil.copy2(W/p,code/p)
