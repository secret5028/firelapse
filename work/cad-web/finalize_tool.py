from pathlib import Path
s=Path('work/check_runtime_v3.mjs').read_text(encoding='utf-8')
s=s.replace("get('invertY').onchange({target:{checked:false}});assert.equal(ctx.window.fireViewer.state.invertY,false);", "assert.equal(ctx.window.fireViewer.state.invertY,true);")
s+='''
for(const key of ['structure','doors','windows','corridors','stairs','lifts']){
assert(vm.runInContext('layerNodes.'+key+'.length',ctx)>0);
get('layer-'+key).onchange({target:{checked:false}});assert(vm.runInContext('layerNodes.'+key+'.every(o=>!o.visible)',ctx));
get('layer-'+key).onchange({target:{checked:true}});assert(vm.runInContext('layerNodes.'+key+'.every(o=>o.visible)',ctx));
}
ctx.window.fireViewer.setMode('detail');get('layerRoutes').checked=false;get('layerRoutes').onchange({target:{checked:false}});assert.equal(vm.runInContext('routesGroup.visible',ctx),false);ctx.window.fireViewer.setFloor('2');assert.equal(vm.runInContext('routesGroup.visible',ctx),false);
assert.equal(vm.runInContext('equipMeshes[0].children[0].material.color.getHexString()',ctx),'ffd343');
console.log('PASS independent geometry layers, persistent hidden route layer, yellow mechanical symbols.');
'''
Path('work/check_layers.mjs').write_text(s,encoding='utf-8')
p=Path('work/folder_review.html');s=p.read_text(encoding='utf-8')
s=s.replace('<button id="save" style="margin-left:auto">', '<button id="export" style="margin-left:auto">HTML 저장</button><button id="save">')
s=s.replace("function download(name,content){", "function download(name,content,mime='application/json;charset=utf-8'){")
s=s.replace("type:'application/json;charset=utf-8'", "type:mime")
s=s.replace("$('save').onclick=", "$('export').onclick=()=>{const clone=document.documentElement.cloneNode(true);clone.querySelector('#three').innerHTML='';clone.querySelector('#pages').innerHTML='';clone.querySelector('#embeddedState')?.remove();const saved=document.createElement('script');saved.id='embeddedState';saved.textContent='window.SAVED_REVIEW_STATE='+JSON.stringify(state).replaceAll('</','<\\\\/')+';';clone.querySelector('header').before(saved);download(D.name.replace(/\\.[^.]+$/,'')+'-3D초안.html','<!doctype html>'+clone.outerHTML,'text/html;charset=utf-8')};$('save').onclick=")
s=s.replace("$('mode3d').onclick=()=>switchMode('3d');select(0);", "$('mode3d').onclick=()=>switchMode('3d');if(window.SAVED_REVIEW_STATE?.sourceHash===D.sourceHash)state.pages=window.SAVED_REVIEW_STATE.pages;select(0);")
p.write_text(s,encoding='utf-8')
print('Layer checks and editable HTML export prepared.')
