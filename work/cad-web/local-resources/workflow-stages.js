/* Three tasks share the same editor state and saved project. */
(()=>{
 const nav=document.getElementById('modeNav');if(!nav)return;
 const style=document.createElement('style');
 style.textContent=`#modeNav{display:flex!important;gap:7px!important}#modeNav button{min-width:0!important;white-space:normal}body[data-task='drawing'] #resultOperations,body[data-task='model'] #resultOperations{display:none!important}body[data-task='objects'] #resultOperations{display:block!important}body[data-task='objects'] #workspacePanel{display:none!important}body[data-task='model'] #structureEditor,body[data-task='objects'] #structureEditor{display:none!important}#workflowHint{padding:7px 12px;background:#20394a;font-size:12px;line-height:1.4}body[data-task='drawing'] #resultEdit{display:none!important}`;
 document.head.append(style);
 const hint=document.createElement('div');hint.id='workflowHint';
 document.getElementById('topTools').after(hint);
 const drawing=document.getElementById('mode2d'),model=document.getElementById('mode3d');
 drawing.textContent='① 도면 읽기·수정';model.textContent='② 3D 생성·확인';
 const objects=document.createElement('button');objects.id='modeObjects';objects.textContent='③ 차량·오브젝트 배치';
 nav.replaceChildren(drawing,model,objects);
 const descriptions={drawing:'도면·층과 축척 확인 → 벽(노랑)·창(파랑)·문(빨강) 수정 → 작업 저장',model:'수정한 도면으로 3D 생성 · 층고·개구부·계단·설비 확인',objects:'3D에서 소방차·화점·경로 배치 · 이동·삭제 후 작업 저장'};
 let task='drawing';
 const originalSwitch=switchMode;
 function mark(value){task=value;document.body.dataset.task=value;document.body.classList.toggle('drawing-tools-open',value==='drawing');hint.textContent=descriptions[value];for(const [b,t]of [[drawing,'drawing'],[model,'model'],[objects,'objects']])b.classList.toggle('active',t===value);}
 function activate(value){document.getElementById('opDone')?.click();mark(value);originalSwitch(value==='drawing'?'2d':'3d');mark(value);window.dispatchEvent(new Event('resize'));}
 switchMode=function(mode){activate(mode==='2d'?'drawing':'model');};
 drawing.onclick=()=>activate('drawing');model.onclick=()=>activate('model');objects.onclick=()=>activate('objects');
 window.reviewWorkflow={activate,getStage:()=>task};
 activate('drawing');
})();
