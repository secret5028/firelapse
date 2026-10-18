from pathlib import Path
import base64,json,io
from PIL import Image
root=Path(__file__).parent
out=root.parent/'outputs'
out.mkdir(exist_ok=True)
assets={}
def encode(im,quality=85):
    b=io.BytesIO();im.convert('RGB').save(b,format='JPEG',quality=quality)
    return 'data:image/jpeg;base64,'+base64.b64encode(b.getvalue()).decode()
for n in [4,10,12,16,20,21,33]:
    im=Image.open(root/'pdf-review'/f'detail-{n}.png')
    assets[str(n)]=encode(im)
    if n in [12,16]:
        w,h=im.size
        rect=(.566,.501,.700,.826) if n==12 else (.148,.537,.239,.716)
        crop=im.crop(tuple(int(v*(w if i%2==0 else h)) for i,v in enumerate(rect)))
        assets['basement'+('B' if n==12 else 'C')]=encode(crop)
    if n in [20,21]:
        w,h=im.size
        region=(.145,.363,.776,.726) if n==20 else (.145,.363,.776,.726)
        crop=im.crop(tuple(int(v*(w if i%2==0 else h)) for i,v in enumerate(region)))
        assets['floor'+str(n-19)]=encode(crop)
core=(root/'three.core.js').read_text(encoding='utf-8')
module=(root/'three.module.js').read_text(encoding='utf-8')
app=(root/'app.js').read_text(encoding='utf-8')
def js(v): return json.dumps(v,ensure_ascii=False).replace('</','<\\/')
boot='window.ASSETS='+js(assets)+';\n'
boot+='(async()=>{try{\n'
boot+='const coreURL=URL.createObjectURL(new Blob(['+js(core)+'],{type:"text/javascript"}));\n'
boot+='const moduleURL=URL.createObjectURL(new Blob(['+js(module)+'.replaceAll("./three.core.js",coreURL)],{type:"text/javascript"}));\n'
boot+='const appURL=URL.createObjectURL(new Blob(['+js(app)+'.replace("__THREE__",moduleURL)],{type:"text/javascript"}));\n'
boot+='await import(appURL);\n'
boot+='}catch(e){console.error(e);document.getElementById("fatal").style.display="block";document.getElementById("fatal").textContent="3D 화면을 시작하지 못했습니다. 최신 Chrome 또는 Edge에서 열고 그래픽 가속을 확인해주세요. 오류: "+e.message;}})();'
html=(root/'viewer.html').read_text(encoding='utf-8').replace('/*BOOT*/',boot).replace('height: seventy;','')
dest=out/'소방공간뷰-D동-시제품.html'
dest.write_text(html,encoding='utf-8')
print(dest)
print('Bytes',dest.stat().st_size,'embedded images',len(assets),'external dependencies: 0')
