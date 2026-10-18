(function(){
 document.getElementById('learningPanel')?.remove();
 const A=AnnotationStore, panel=document.createElement('section');panel.id='learningPanel';
 panel.style.cssText='border:1px solid #759cac;padding:10px;margin:10px 0;background:#183447';
 panel.innerHTML=`<b>수정 기록 · 학습 자료</b><p>수정은 이력으로 저장됩니다. 검수 완료한 영역·항목만 학습 자료에 포함합니다.</p><button id="reviewRegion">검수 영역 두 점 지정</button><button id="reviewWhole">현재 페이지 전체 선택</button><p id="reviewBounds">영역을 선택하세요.</p><label><input type="checkbox" id="reviewGeometry" checked>벽·문·창 위치와 종류</label><label><input type="checkbox" id="reviewKinds">문·창 세부 종류</label><label><input type="checkbox" id="reviewDirection">문 경첩·열림 방향</label><button id="reviewConfirm">선택 범위 검수 완료</button><button id="reviewRevoke">현재 페이지 검수 취소</button><button id="learningExport">검수된 학습 자료 저장</button><button id="learningHistory">전체 수정 이력 저장</button><button id="learningRestore">이 기기 저장 작업 복구</button><p id="learningStatus" role="status"></p><small>이 기기에 저장 · 외부 전송 및 모델 학습은 하지 않습니다.</small>`;
 document.querySelector('aside').prepend(panel);
 const el=id=>document.getElementById(id);let region=null,selecting=false,anchor=null,owner=-1,pointer=false,timer,dirty=0,db;
 const status=s=>el('learningStatus').textContent=s;
 if(!state.learning&&window.SAVED_REVIEW_STATE?.sourceHash===D.sourceHash){state.learning=window.SAVED_REVIEW_STATE.learning;state.operations??=window.SAVED_REVIEW_STATE.operations;}
 const init=()=>A.ensure(state,D);init();
 const summary=document.createElement('p');summary.id='learningSummary';panel.append(summary);
 function summarize(){const rec=state.learning?.pages[current().pageId];if(rec)summary.textContent=`수정 ${rec.events.length}건 · 유효 검수 ${rec.reviews.filter(r=>r.status==='confirmed').length}개 · 재검수 ${rec.reviews.filter(r=>r.status==='stale').length}개`;}
 const ready=new Promise((resolve,reject)=>{const q=indexedDB.open('croquis-learning-v1',1);q.onupgradeneeded=()=>q.result.createObjectStore('projects');q.onsuccess=()=>{db=q.result;resolve(db);};q.onerror=()=>reject(q.error);});
 ready.catch(()=>status('기기 저장소를 열지 못했습니다. 작업 저장으로 파일을 보관하세요.'));
 let queue=Promise.resolve();
 function persist(){const payload=JSON.parse(JSON.stringify(state));queue=queue.catch(()=>{}).then(()=>ready).then(()=>new Promise((resolve,reject)=>{const tx=db.transaction('projects','readwrite');tx.objectStore('projects').put(payload,D.sourceHash);tx.oncomplete=()=>{status('이 기기에 저장됨 · 수정 이력과 검수 포함');resolve();};tx.onerror=tx.onabort=()=>reject(tx.error);})).catch(()=>status('기기 저장 실패 · 상단 작업 저장으로 파일을 보관하세요.'));return queue;}
 function sync(label){try{const changed=A.sync(state,D,label);if(changed){dirty++;persist();}return changed;}catch(e){status(e.message);return 0;}}
 function refresh(){if(owner!==index){region=null;anchor=null;selecting=false;owner=index;el('reviewBounds').textContent='영역을 선택하세요.';}panel.style.display=mode==='2d'?'':'none';summarize();}
 const previousDraw=draw;draw=function(){refresh();previousDraw();clearTimeout(timer);timer=setTimeout(()=>{if(!pointer)sync('editor-change');},250);if(mode==='2d'&&region){ctx.save();ctx.translate(offset.x,offset.y);ctx.scale(zoom,zoom);ctx.strokeStyle='#ac7bff';ctx.lineWidth=2/zoom;ctx.strokeRect(region[0],region[1],region[2]-region[0],region[3]-region[1]);ctx.restore();}};
 const oldSelect=select;select=function(i){sync('page-change');oldSelect(i);refresh();};
 document.addEventListener('pointerdown',()=>{pointer=true;},true);
 document.addEventListener('pointerup',()=>{pointer=false;queueMicrotask(()=>sync('pointer-edit'));},true);
 document.addEventListener('pointercancel',()=>{pointer=false;queueMicrotask(()=>sync('cancel-edit'));},true);
 for(const event of ['change','click','keyup'])document.addEventListener(event,()=>queueMicrotask(()=>{if(!pointer)sync(event);}),true);
 function showBounds(){el('reviewBounds').textContent=region?region.map(Math.round).join(', ')+' px':'영역을 선택하세요.';draw();}
 el('reviewRegion').onclick=()=>{switchMode('2d');owner=index;region=null;anchor=null;selecting=true;window.hideModelLines=false;c.style.pointerEvents='';status('원본에서 검수할 사각 영역의 두 모서리를 클릭하세요.');};
 // Capture before existing canvas drag handlers; review clicks never edit geometry.
 document.addEventListener('pointerdown',e=>{if(!selecting||e.target!==c)return;e.preventDefault();e.stopImmediatePropagation();pointer=false;const rect=c.getBoundingClientRect(),src=D.pages[index];const q=[Math.max(0,Math.min(src.width,(e.clientX-rect.left-offset.x)/zoom)),Math.max(0,Math.min(src.height,(e.clientY-rect.top-offset.y)/zoom))];if(!anchor)anchor=q;else{region=[Math.min(anchor[0],q[0]),Math.min(anchor[1],q[1]),Math.max(anchor[0],q[0]),Math.max(anchor[1],q[1])];selecting=false;anchor=null;showBounds();}},true);
 el('reviewWhole').onclick=()=>{owner=index;region=[0,0,D.pages[index].width,D.pages[index].height];selecting=false;showBounds();};
 el('reviewConfirm').onclick=()=>{try{if(!region)throw Error('검수할 영역을 먼저 선택하세요.');const attrs=[['reviewGeometry','geometry'],['reviewKinds','openingKind'],['reviewDirection','doorDirection']].filter(([key])=>el(key).checked).map(([,value])=>value);A.confirm(state,D,index,region,attrs);dirty++;persist();status('검수 완료 · 이후 도면 수정 시 검수가 해제됩니다.');}catch(e){status(e.message);}};
 el('reviewRevoke').onclick=()=>{init();for(const r of state.learning.pages[current().pageId].reviews)if(r.status==='confirmed')r.status='revoked';dirty++;persist();};
 el('learningExport').onclick=()=>{try{const bundle=A.exportDataset(state,D);if(!bundle.samples.length)throw Error('현재 수정본에 유효한 검수 완료 영역이 없습니다.');download('검수-학습자료.json',JSON.stringify(bundle));status(`${bundle.samples.length}개 검수 영역을 내보냈습니다. 모델 학습은 별도입니다.`);}catch(e){status(e.message);}};
 el('learningHistory').onclick=()=>{sync('history-export');download('전체-수정이력.json',JSON.stringify({sourceHash:D.sourceHash,learning:state.learning},null,2));};
 el('learningRestore').onclick=async()=>{try{await queue;await ready;const start=dirty;const saved=await new Promise((resolve,reject)=>{const q=db.transaction('projects').objectStore('projects').get(D.sourceHash);q.onsuccess=()=>resolve(q.result);q.onerror=()=>reject(q.error);});if(start!==dirty)throw Error('복구 중 수정되었습니다. 다시 시도하세요.');if(!saved||saved.sourceHash!==D.sourceHash||saved.pages.length!==D.pages.length)throw Error('이 도면의 저장 작업이 없습니다.');state.pages=saved.pages;state.operations=saved.operations;state.learning=saved.learning;init();dirty++;select(index);draw();status('이 기기 작업을 복구했습니다.');}catch(e){status(e.message);}};
 for(const key of ['save','export']){const fn=el(key).onclick;el(key).onclick=e=>{sync('save');persist();return fn(e);};}
 const loader=el('jsonFile').onchange;el('jsonFile').onchange=async e=>{sync('before-load');const oldPages=state.pages;await loader(e);if(oldPages!==state.pages){const saved=JSON.parse(await e.target.files[0].text());state.learning=saved.learning;state.operations=saved.operations;init();sync('loaded-work');dirty++;persist();draw();}};
 window.reviewLearning={sync,persist,getState:()=>state.learning};refresh();
})();
