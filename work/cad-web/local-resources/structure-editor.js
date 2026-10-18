/* STRUCTURE_EDITOR_V1: local corrections only; never uploads source images. */
(function(){
 document.getElementById('structureEditor')?.remove();
 const clone=x=>JSON.parse(JSON.stringify(x)), storageKey='croquis-edits-v1:'+D.sourceHash;
 const panel=document.createElement('section');panel.id='structureEditor';panel.style.cssText='border:1px solid #6f94aa;border-radius:8px;padding:10px;margin-bottom:14px;background:#172e41';
 panel.innerHTML=`<strong>벽 · 문 · 창 편집</strong><div class="row"><button data-action="select">기존 선 직접 수정</button><button data-action="pan">도면 이동</button></div><div class="row"><button data-action="wall">벽 추가</button><button data-action="door">문 추가</button><button data-action="window">창 추가</button></div><label>선 종류<select id="editShapeType" style="width:100%"><option value="wall">벽</option><option value="door">문</option><option value="window">창</option></select></label><label>문·창 종류<select id="editOpeningType" style="width:100%"></select></label><div class="row"><button id="editHinge">경첩 반대쪽</button><button id="editSwing">열림 방향 반전</button></div><div class="row"><button id="editDelete">선 삭제</button><button id="editUndo">되돌리기</button><button id="editRedo">다시 실행</button></div><button id="editLog" style="width:100%">수정 기록 내려받기</button><p id="editHelp" style="font-size:12px;line-height:1.6">기존 빨간 선 몸통을 바로 끌면 이동, 끝점을 바로 끌면 길이·방향 수정. 추가는 두 점 클릭. Shift: 수평·수직. 빈 곳 드래그: 도면 이동.</p><p id="editNotice" style="font-size:12px;color:#b5dbe8"></p>`;
 document.querySelector('aside').prepend(panel);
 let action='select',hover=-1,selected=-1,firstPoint=null,gesture=null,page=current(),undo=[],redo=[];
 const base=new Map(state.pages.map(p=>[p,JSON.stringify(p.shapes)]));
 let stored={};try{stored=JSON.parse(localStorage.getItem(storageKey)||'{}');}catch{}
 const key=p=>{const i=state.pages.indexOf(p),src=D.pages[i];return src.pageId||`${D.sourceHash}:page-${src.number??i+1}:index-${i}:render-${src.width}x${src.height}`;};
 for(const p of state.pages){const r=stored[key(p)];if(r&&r.base===base.get(p)){p.shapes=r.shapes;p.correctionLog=r.log||[];}}
 const el=id=>document.getElementById(id),notice=t=>el('editNotice').textContent=t;
 function syncPage(){if(page!==current()){page=current();if(!base.has(page))base.set(page,JSON.stringify(page.shapes));selected=-1;hover=-1;firstPoint=null;gesture=null;undo=[];redo=[];sync();}}
 const kinds={door:[['single','외여닫이'],['double','쌍여닫이'],['sliding','미닫이'],['double-sliding','양개 미닫이'],['revolving','회전문'],['folding','접이문']],window:[['fixed','고정창'],['sliding','미닫이창'],['casement','여닫이창']]};
 function sync(){const sh=page.shapes[selected];if(sh)el('editShapeType').value=sh.type;const type=el('editShapeType').value;el('editOpeningType').replaceChildren(...(kinds[type]||[['','해당 없음']]).map(([v,t])=>new Option(t,v)));if(sh)el('editOpeningType').value=sh.openingKind||(type==='door'?(sh.leaves===2?'double':'single'):'fixed');el('editOpeningType').disabled=type==='wall';for(const id of ['editDelete','editHinge','editSwing'])el(id).disabled=!sh||(id!=='editDelete'&&sh.type!=='door');el('editUndo').disabled=!undo.length;el('editRedo').disabled=!redo.length;panel.querySelectorAll('[data-action]').forEach(b=>b.classList.toggle('active',b.dataset.action===action));}
 function persist(){stored[key(page)]={base:base.get(page),shapes:clone(page.shapes),log:clone(page.correctionLog||[])};try{localStorage.setItem(storageKey,JSON.stringify(stored));notice('이 기기에 자동 저장됨 · 3D 보기에서 수정 반영');}catch{notice('자동 저장 공간 부족: 상단 작업 저장으로 파일을 저장하세요.');}}
 function record(before,label){if(JSON.stringify(before)===JSON.stringify(page.shapes))return;const after=clone(page.shapes);page.correctionLog||=[];page.correctionLog.push({version:1,time:new Date().toISOString(),action:label,sourcePage:page.sourcePage,building:page.building,floor:page.floor,before,after});persist();sync();}
 function commit(before,label){undo.push(before);redo=[];record(before,label);draw();}
 function mutate(label,fn){syncPage();const before=clone(page.shapes);fn();commit(before,label);}
 panel.querySelectorAll('[data-action]').forEach(b=>b.onclick=()=>{syncPage();action=b.dataset.action;firstPoint=null;tool=null;first=null;if(['wall','door','window'].includes(action)){selected=-1;el('editShapeType').value=action;}window.hideModelLines=false;sync();draw();});
 el('editShapeType').onchange=()=>{const type=el('editShapeType').value;if(selected>=0)mutate('change-type',()=>{const sh=page.shapes[selected];sh.type=type;delete sh.openingKind;delete sh.leaves;});else if(['wall','door','window'].includes(action))action=type;sync();};
 el('editOpeningType').onchange=()=>{const kind=el('editOpeningType').value;if(selected>=0)mutate('change-opening-kind',()=>{const sh=page.shapes[selected];sh.openingKind=kind;sh.leaves=kind==='double'||kind==='double-sliding'?2:1;});};
 el('editHinge').onclick=()=>mutate('reverse-hinge',()=>{const sh=page.shapes[selected];sh.hinge=sh.hinge==='end'?'start':'end';});
 el('editSwing').onclick=()=>mutate('reverse-swing',()=>{const sh=page.shapes[selected];sh.swingSide=sh.swingSide===-1?1:-1;});
 el('editDelete').onclick=()=>{if(selected<0)return;mutate('delete',()=>{page.shapes.splice(selected,1);selected=-1;});};
 el('editUndo').onclick=()=>{if(!undo.length)return;const before=clone(page.shapes);redo.push(before);page.shapes=undo.pop();selected=-1;record(before,'undo');draw();};
 el('editRedo').onclick=()=>{if(!redo.length)return;const before=clone(page.shapes);undo.push(before);page.shapes=redo.pop();selected=-1;record(before,'redo');draw();};
 el('editLog').onclick=()=>download('도면-수정기록.json',JSON.stringify({version:1,sourceHash:D.sourceHash,coordinateSystem:'source-image-pixels',pages:state.pages.filter(p=>p.correctionLog?.length).map(p=>({sourcePage:p.sourcePage,building:p.building,floor:p.floor,edits:p.correctionLog}))},null,2));
 const pos=e=>{const r=c.getBoundingClientRect();return [(e.clientX-r.left-offset.x)/zoom,(e.clientY-r.top-offset.y)/zoom];};
 const distance=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1]);
 function hit(p){let best=-1,min=11/zoom;page.shapes.forEach((s,i)=>{const dx=s.b[0]-s.a[0],dy=s.b[1]-s.a[1],t=Math.max(0,Math.min(1,((p[0]-s.a[0])*dx+(p[1]-s.a[1])*dy)/(dx*dx+dy*dy||1))),d=distance(p,[s.a[0]+t*dx,s.a[1]+t*dy]);if(d<min||(best>=0&&s.type!=='wall'&&Math.abs(d-min)<2/zoom)){min=d;best=i;}});return best;}
 function bounded(p){return [Math.max(0,Math.min(img.width,p[0])),Math.max(0,Math.min(img.height,p[1]))];}
 function snap(p,anchor,shift){p=bounded(p);if(shift&&anchor){if(Math.abs(p[0]-anchor[0])>Math.abs(p[1]-anchor[1]))p[1]=anchor[1];else p[0]=anchor[0];return p;}let d=8/zoom;page.shapes.forEach((s,i)=>{if(i===selected)return;for(const q of [s.a,s.b])if(distance(p,q)<d){d=distance(p,q);p=q.slice();}});return p;}
 function stop(e){e.preventDefault();e.stopImmediatePropagation();}
 c.addEventListener('pointerdown',e=>{if(mode!=='2d'||e.button!==0||tool)return;syncPage();if(action==='pan'||e.altKey||window.hideModelLines)return;stop(e);c.setPointerCapture(e.pointerId);const p=pos(e);if(['wall','door','window'].includes(action)){const q=snap(p,firstPoint,e.shiftKey);if(!firstPoint)firstPoint=q;else if(distance(firstPoint,q)*zoom>4){const a=firstPoint.slice();mutate('add',()=>{const kind=el('editOpeningType').value;page.shapes.push({type:action,a,b:q,origin:'manual',openingKind:action==='wall'?undefined:kind,leaves:kind==='double'||kind==='double-sliding'?2:1});selected=page.shapes.length-1;});firstPoint=null;action='select';sync();}draw();return;}let endpoint=null;const prior=page.shapes[selected];if(prior)for(const end of ['a','b'])if(distance(p,prior[end])*zoom<12)endpoint=end;if(!endpoint){selected=hit(p);const picked=page.shapes[selected];if(picked)for(const end of ['a','b'])if(distance(p,picked[end])*zoom<12)endpoint=end;}gesture={start:p,last:[e.clientX,e.clientY],before:clone(page.shapes),endpoint,shape:selected>=0?clone(page.shapes[selected]):null};sync();draw();},true);
 c.addEventListener('pointermove',e=>{if(!gesture){if(mode==='2d'&&action==='select'&&!tool&&!window.hideModelLines){const h=hit(pos(e));c.style.cursor=h>=0?'grab':'move';if(h!==hover){hover=h;draw();}}return;}stop(e);if(!gesture.shape){offset.x+=e.clientX-gesture.last[0];offset.y+=e.clientY-gesture.last[1];gesture.last=[e.clientX,e.clientY];}else{const sh=page.shapes[selected],p=pos(e),g=gesture;if(g.endpoint)sh[g.endpoint]=snap(p,g.shape[g.endpoint==='a'?'b':'a'],e.shiftKey);else{const dx=p[0]-g.start[0],dy=p[1]-g.start[1];sh.a=bounded([g.shape.a[0]+dx,g.shape.a[1]+dy]);sh.b=bounded([g.shape.b[0]+dx,g.shape.b[1]+dy]);}}draw();},true);
 c.addEventListener('pointerup',e=>{if(!gesture)return;stop(e);const g=gesture;gesture=null;if(g.shape){if(distance(page.shapes[selected].a,page.shapes[selected].b)<2)page.shapes=g.before;else commit(g.before,g.endpoint?'move-endpoint':'move-line');}draw();},true);
 c.addEventListener('pointercancel',()=>{if(gesture){page.shapes=gesture.before;gesture=null;draw();}},true);
 document.addEventListener('keydown',e=>{if(e.key==='Escape'){if(gesture)page.shapes=gesture.before;gesture=null;firstPoint=null;selected=-1;sync();draw();}});
 const originalDraw=draw;draw=function(){syncPage();originalDraw();panel.style.display=mode==='3d'?'none':'';if(mode!=='2d'||window.hideModelLines)return;const sh=page.shapes[selected>=0?selected:hover];ctx.save();ctx.translate(offset.x,offset.y);ctx.scale(zoom,zoom);if(sh){ctx.strokeStyle='#45e5ff';ctx.lineWidth=3/zoom;ctx.beginPath();ctx.moveTo(...sh.a);ctx.lineTo(...sh.b);ctx.stroke();for(const p of [sh.a,sh.b]){ctx.fillStyle='#45e5ff';ctx.fillRect(p[0]-5/zoom,p[1]-5/zoom,10/zoom,10/zoom);}}if(firstPoint){ctx.fillStyle='#45e5ff';ctx.beginPath();ctx.arc(...firstPoint,5/zoom,0,Math.PI*2);ctx.fill();}ctx.restore();};
 const originalSwitch=switchMode;switchMode=function(m){panel.style.display=m==='3d'?'none':'';return originalSwitch(m);};
 sync();draw();
})();

(function(){
 const details=addFloorDetails;
 addFloorDetails=function(T,group,p,convert,y){
  details(T,group,p,convert,y);
  for(const sh of p.shapes.filter(s=>s.type==='window'&&s.openingKind)){
   const a=convert(sh.a),b=convert(sh.b),mid=[(a[0]+b[0])/2,(a[1]+b[1])/2],points=[];
   if(sh.openingKind==='sliding')points.push([mid[0],y+.9,mid[1]],[mid[0],y+2.1,mid[1]]);
   else if(sh.openingKind==='casement')points.push([a[0],y+.9,a[1]],[b[0],y+1.5,b[1]],[a[0],y+2.1,a[1]]);
   else continue;
   const obj=new T.Line(new T.BufferGeometry().setFromPoints(points.map(q=>new T.Vector3(...q))),new T.LineBasicMaterial({color:0xffe375}));obj.userData.layer='opening';group.add(obj);
  }
 };
})();

// Alternate door symbols use the same source opening endpoints as their frames.
(function(){
 const swing=addDoorSwing;
 addDoorSwing=function(T,group,sh,a,b,y){
  const kind=sh.openingKind;if(kind==='double-acting'){for(const side of [-1,1])swing(T,group,{...sh,openingKind:'single',leaves:1,swingSide:side},a,b,y);return;}if(!['sliding','double-sliding','revolving','folding'].includes(kind))return swing(T,group,sh,a,b,y);
  const length=Math.hypot(b[0]-a[0],b[1]-a[1]),u=[(b[0]-a[0])/length,(b[1]-a[1])/length],v=[-u[1],u[0]],mat=new T.LineBasicMaterial({color:0xefa927});
  function line(points){const obj=new T.Line(new T.BufferGeometry().setFromPoints(points.map(([x,h,z])=>new T.Vector3(a[0]+u[0]*x+v[0]*z,y+h,a[1]+u[1]*x+v[1]*z))),mat);obj.userData.layer='opening';group.add(obj);}
  function panel(x1,x2,z=0){line([[x1,0,z],[x2,0,z],[x2,2.1,z],[x1,2.1,z],[x1,0,z]]);}
  if(kind==='revolving'){line(Array.from({length:33},(_,i)=>[length/2+length/2*Math.cos(i*Math.PI/16),.04,length/2*Math.sin(i*Math.PI/16)]));for(let i=0;i<3;i++){const t=i*Math.PI*2/3;line([[length/2,0,0],[length/2+length/2*Math.cos(t),0,length/2*Math.sin(t)],[length/2+length/2*Math.cos(t),2.1,length/2*Math.sin(t)],[length/2,2.1,0]]);}}
  else if(kind==='folding'){for(let i=0;i<4;i++)line([[i*length/4,0,i%2?.3:0],[(i+1)*length/4,0,(i+1)%2?.3:0],[(i+1)*length/4,2.1,(i+1)%2?.3:0],[i*length/4,2.1,i%2?.3:0],[i*length/4,0,i%2?.3:0]]);}
  else{panel(0,length*.55);panel(length*.45,length,.07);line([[0,.05,-.15],[length,.05,-.15]]);if(kind==='double-sliding')line([[length/2,0,0],[length/2,2.1,0]]);}
 };
})();
