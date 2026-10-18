from pathlib import Path
from PIL import Image
import json,base64,io,hashlib
from factory_data import DATA
root=Path(__file__).parent
assets={};hashes={}
def enc(im):
    b=io.BytesIO();im.convert('RGB').save(b,'JPEG',quality=88);return 'data:image/jpeg;base64,'+base64.b64encode(b.getvalue()).decode()
for n in [1,2,3]:
    path=Path('C:/Users/예방/Downloads')/f'{n}층 평면도.jpg'
    hashes[str(n)]=hashlib.sha256(path.read_bytes()).hexdigest()
    im=Image.open(path);w,h=im.size
    y=451 if n==3 else 447;yb=855 if n==3 else 852
    crop=im.crop((round(350/1888*w),round(y/1334*h),round(1384/1888*w),round(yb/1334*h)))
    assets['crop'+str(n)]=enc(crop)
    im.thumbnail((2600,2600));assets[str(n)]=enc(im)
def js(v):return json.dumps(v,ensure_ascii=False).replace('</','<\\/')
boot='window.FACTORY='+js(DATA)+';window.FACTORY_ASSETS='+js(assets)+';'
boot+='(async()=>{try{const core=URL.createObjectURL(new Blob(['+js((root/'three.core.js').read_text(encoding='utf-8'))+'],{type:"text/javascript"}));'
boot+='const lib=URL.createObjectURL(new Blob(['+js((root/'three.module.js').read_text(encoding='utf-8'))+'.replaceAll("./three.core.js",core)],{type:"text/javascript"}));'
boot+='const app=URL.createObjectURL(new Blob(['+js((root/'factory.js').read_text(encoding='utf-8'))+'.replace("__THREE__",lib)],{type:"text/javascript"}));await import(app);'
boot+='}catch(e){document.getElementById("fatal").style.display="block";document.getElementById("fatal").textContent="3D 시작 오류: "+e.message;console.error(e)}})();'
html=(root/'factory.html').read_text(encoding='utf-8').replace('/*BOOT*/',boot)
out=root.parent/'outputs'/'소방공간뷰-당산리공장-1~3층.html';out.write_text(html,encoding='utf-8')
(root/'factory-sample.html').write_text(html,encoding='utf-8')
(root/'factory-hashes.json').write_text(json.dumps(hashes),encoding='utf-8')
(root/'factory-data.json').write_text(js(DATA),encoding='utf-8')
print(out, out.stat().st_size, 'bytes; 3 plans + 3 overlays, offline')
