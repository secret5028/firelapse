"""B-3 read-only fixed-clock fixture, operated via the browser's controls."""
import threading
import smoke_amplitude_proxy as base

base.OUT = base.ROOT/'simulation/results/ui_B3_hrr_20261028'
base.SCRIPT = base.SCRIPT.replace('<button id="testInspect">', '<button id="testS09_300">S09 300</button><button id="testInspect">')
base.SCRIPT = base.SCRIPT.replace("['testAll','S09',1800,true]", "['testAll','S09',1800,true],['testS09_300','S09',300,false]")
base.SCRIPT = base.SCRIPT.replace("const state={scene:", """const flames=[],lights=[];window.__cad.S.traverse(o=>{
 if(o.material?.uniforms?.uFire?.value===1)flames.push({id:o.userData.fireId??null,q:o.userData.q??null,hrrpua:o.userData.hrrpua??null,cellArea:o.userData.cellArea??null,visible:o.visible,scale:o.scale.toArray(),position:o.position.toArray(),phase:o.material.uniforms.uPhase.value,stage:o.userData.stage??null});
 if(o.isPointLight)lights.push({id:o.userData.fireId??null,intensity:o.intensity,position:o.position.toArray()});});
 const state={flames,lights,flameDisplay:document.getElementById('displayFlameStyle')?.value??'growth',scene:""")

if __name__=='__main__':
    servers=[base.ThreadingHTTPServer(('127.0.0.1',port),base.Handler) for port in (8794,8795)]
    for server in servers:threading.Thread(target=server.serve_forever,daemon=True).start()
    print('B3 before8794 / after8795; GET only',flush=True)
    threading.Event().wait()
