from pathlib import Path
from PyInstaller.utils.hooks import collect_all
root=Path(SPECPATH)
datas=[(str(root/'local-resources'),'.'),(str(root/'cad_engine'),'cad_engine')]
binaries=[];hiddenimports=['cad_upload','cv2','scipy.ndimage','scipy.spatial']
for package in ['pypdfium2_raw','ezdxf','shapely']:
 d,b,h=collect_all(package);datas+=d;binaries+=b;hiddenimports+=h
hiddenimports += [p.stem for p in (root/'cad_engine').glob('*.py') if p.stem.startswith('cad_') or p.stem in ('cadio','run_building')]
a=Analysis([str(root/'local_app.py')],pathex=[str(root),str(root/'cad_engine')],datas=datas,binaries=binaries,hiddenimports=hiddenimports,excludes=['tkinter','matplotlib','pytest','pandas'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='소방 크로키 업',console=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='소방 크로키 업-로컬웹앱')
