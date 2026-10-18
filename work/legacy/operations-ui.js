/* Multiple vehicles, explicit waypoint routes, and per-fire size. */
(()=>{
 let view=null,action=null,down=null;
 const $=id=>document.getElementById(id);
 const data=()=>state.operations||(state.operations=structuredClone(window.SAVED_REVIEW_STATE?.operations||{version:1,vehicles:[],routes:[],fires:[]}));
 const id=()=>crypto.randomUUID();
 let vehicleId='',routeId='',fireId='';
 function auto(f){const d=data();let v=d.vehicles.find(v=>v.id===vehicleId)||d.vehicles[0];if(!v&&view){view.scene.traverse(o=>{if(!v&&o.userData.referenceVehicle){const q=new view.T.Vector3();o.getWorldPosition(q);v={id:'reference',position:[q.x,0,q.z]};}});}if(!v){note('자동 경로를 만들려면 차량을 먼저 배치하세요.');return;}const result=window.AutoRoute.generate(state.pages,f,v.position);if(result.error){f.routeError=result.error;note(result.error);return;}delete f.routeError;let r=d.routes.find(r=>r.automatic&&r.fireId===f.id&&r.vehicleId===v.id);if(!r){r={id:id(),vehicleId:v.id};d.routes.push(r);}Object.assign(r,result);routeId=r.id;note('화점까지 자동 경로를 생성했습니다. 층을 바꿔도 경로와 출입문·계단실이 유지됩니다.');}
 function save(){if(typeof saveReview==='function')saveReview();else if(typeof persist==='function')persist();}
 function note(s){if($('opNotice'))$('opNotice').textContent=s;}
 function setAction(a){action=a;note(a==='vehicle'?'도로·지면의 배치 위치를 누르세요.':a==='move'?'차량을 옮길 지면 위치를 누르세요.':a==='fire'?'화점을 놓을 바닥을 누르세요.':a==='route'?'경로를 순서대로 누른 뒤 완료하세요.':'');if(view)view.canvas.style.cursor=a?'crosshair':'';}
 function options(el,items,selected,label){el.replaceChildren();if(!items.length)el.add(new Option('없음',''));for(const [i,v] of items.entries())el.add(new Option(label(v,i),v.id));el.value=items.some(v=>v.id===selected)?selected:items[0]?.id||'';return el.value;}
 function refresh(){
  if(!$('opVehicles'))return;const d=data();vehicleId=options($('opVehicles'),d.vehicles,vehicleId,(_,i)=>'차량 '+(i+1));routeId=options($('opRoutes'),d.routes,routeId,(_,i)=>'경로 '+(i+1));fireId=options($('opFires'),d.fires,fireId,(f,i)=>'화점 '+(i+1)+' · '+(f.floor==null?'바닥':f.floor+'층'));
  const fire=d.fires.find(f=>f.id===fireId);if(fire)$('opFireSize').value=fire.size;
  const route=d.routes.find(r=>r.id===routeId);let length=0;if(route)for(let i=1;i<route.points.length;i++)length+=Math.hypot(...route.points[i].map((x,j)=>x-route.points[i-1][j]));
  $('opRouteInfo').textContent=route?`${route.automatic?'자동 경로':'직접 지정'} · ${route.points.length-1}구간 · 약 ${length.toFixed(1)}m (도면 축척 기준)`:'경로를 추가해 순서대로 지정하세요.';
  for(const key of ['opMove','opVehicleDelete'])$(key).disabled=!vehicleId;for(const key of ['opRouteDelete','opRouteUndo'])$(key).disabled=!routeId;$('opRouteAdd').disabled=!vehicleId;$('opFireDelete').disabled=!fireId;
  render();
 }
 function render(){if(!view)return;const {T,scene,root}=view,d=data();while(root.children.length){const o=root.children[0];root.remove(o);o.traverse(m=>{m.geometry?.dispose();for(const mat of Array.isArray(m.material)?m.material:[m.material]){mat?.map?.dispose();mat?.dispose();}});}
  scene.traverse(o=>{if(o.userData.referenceVehicle)o.visible=!d.vehicles.length;});
  const mesh=(parent,g,color,x,y,z)=>{const o=new T.Mesh(g,new T.MeshStandardMaterial({color,roughness:.8}));o.position.set(x,y,z);parent.add(o);return o;};
  for(const v of d.vehicles){const g=new T.Group();g.position.fromArray(v.position);g.rotation.y=v.heading||0;root.add(g);mesh(g,new T.BoxGeometry(6,1.8,2.3),'#c92d3f',-1,1.5,0);mesh(g,new T.BoxGeometry(2,2,2.3),'#e94248',3,1.5,0);mesh(g,new T.BoxGeometry(.06,.8,1.9),'#4c9bbc',4.03,2,0);for(const x of [-2.5,2.7])for(const z of [-1.2,1.2]){const w=mesh(g,new T.CylinderGeometry(.48,.48,.3,10),'#18252d',x,.5,z);w.rotation.x=Math.PI/2;}for(const z of [-.5,.5])mesh(g,new T.BoxGeometry(4.5,.08,.08),'#e4e7e9',-1,2.5,z);for(let i=0;i<10;i++)mesh(g,new T.BoxGeometry(.07,.07,1),'#e4e7e9',-3+i*.44,2.5,0);if(v.id===vehicleId){const ring=mesh(g,new T.RingGeometry(4.4,4.5,32),'#ffd45b',0,.03,0);ring.rotation.x=-Math.PI/2;}}
  const selected=$('viewFloor')?.value||'all';
  for(const f of d.fires){if(selected!=='all'&&f.levelKey&&selected!==f.levelKey)continue;const g=new T.Group();g.position.fromArray(f.position);root.add(g);const scale={small:.6,medium:1.1,large:1.8}[f.size]||1.1;mesh(g,new T.ConeGeometry(scale*.7,scale*2,7),'#f05223',0,scale,0);mesh(g,new T.ConeGeometry(scale*.38,scale*1.45,7),'#ffd548',scale*.2,scale*.75,scale*.3);if(f.id===fireId){const ring=mesh(g,new T.RingGeometry(scale*.85,scale*.95,24),'#ffed93',0,.04,0);ring.rotation.x=-Math.PI/2;}}
  const active=d.routes.find(r=>r.id===routeId);if(active)renderContext(active,selected);
  for(const r of d.routes){if(r.points.length<2)continue;const points=r.points.map(p=>new T.Vector3(p[0],p[1]+.13,p[2]));root.add(new T.Line(new T.BufferGeometry().setFromPoints(points),new T.LineBasicMaterial({color:r.id===routeId?'#ffe260':'#74858c',transparent:true,opacity:r.id===routeId?1:.35})));for(let i=1;i<points.length;i++){const delta=points[i].clone().sub(points[i-1]);const length=delta.length();if(length>.3)root.add(new T.ArrowHelper(delta.normalize(),points[i-1].clone().lerp(points[i],.6),Math.min(1,length*.3),r.id===routeId?0xffe260:0x74858c,.35,.22));}}
 }

 function renderContext(r,selected){
  if(!window.AutoRoute)return;const {T,root}=view;
  const pages=state.pages.filter(p=>p.included&&p.scale);
  const contexts=r.contexts||pages.map(p=>({levelKey:p.building+'|'+p.floor,leg:r.points.filter(q=>Math.abs(q[1]-(p.elevation??0))<.3).map(q=>[q[0],q[2]])})).filter(c=>c.leg.length>1);
  for(const c of contexts){const p=pages.find(p=>p.building+'|'+p.floor===c.levelKey);if(!p)continue;
   const ctx=AutoRoute.context(p,c.leg,c.stairIndex),g=new T.Group();g.name='route-context-'+c.levelKey;root.add(g);
   const y=p.elevation??(p.floor-1)*p.height;
   // Selected-floor geometry already exists. Overview retains stairs otherwise omitted by LOD.
   if(selected!=='all'&&selected!==c.levelKey){
    const verts=[],edges=[];const quad=(a,b,lo,hi)=>{verts.push(a[0],y+lo,a[1],b[0],y+lo,b[1],b[0],y+hi,b[1],a[0],y+lo,a[1],b[0],y+hi,b[1],a[0],y+hi,a[1]);edges.push(a[0],y+hi,a[1],b[0],y+hi,b[1]);};
    for(const [a,b]of ctx.walls)quad(a,b,0,p.height);
    for(const door of ctx.doors){quad(door.a,door.b,Math.min(2.1,p.height),p.height);const a=door.a,b=door.b;edges.push(a[0],y,a[1],a[0],y+2.1,a[1],a[0],y+2.1,a[1],b[0],y+2.1,b[1],b[0],y+2.1,b[1],b[0],y,b[1]);}
    const geo=new T.BufferGeometry();geo.setAttribute('position',new T.Float32BufferAttribute(verts,3));geo.computeVertexNormals();g.add(new T.Mesh(geo,new T.MeshBasicMaterial({color:0x8bb7bc,transparent:true,opacity:.25,side:T.DoubleSide,depthWrite:false})));
    const lines=new T.BufferGeometry();lines.setAttribute('position',new T.Float32BufferAttribute(edges,3));g.add(new T.LineSegments(lines,new T.LineBasicMaterial({color:0xe4c566,transparent:true,opacity:.8})));
    const floor=[];for(const [x,z,w,h]of ctx.tiles)floor.push(x,y+.02,z,x+w,y+.02,z,x+w,y+.02,z+h,x,y+.02,z,x+w,y+.02,z+h,x,y+.02,z+h);
    const fg=new T.BufferGeometry();fg.setAttribute('position',new T.Float32BufferAttribute(floor,3));g.add(new T.Mesh(fg,new T.MeshBasicMaterial({color:0xa9bdb8,transparent:true,opacity:.25,side:T.DoubleSide,depthWrite:false})));
   }
   if(selected!=='all'&&selected!==c.levelKey&&c.stairIndex!=null&&typeof addFloorDetails==='function'){
    const cp={...p,stairs:[p.stairs[c.stairIndex]],floorPolygons:[],floorOutline:[],roomLabels:[],elevators:[],columns:[]};
    addFloorDetails(T,g,cp,q=>AutoRoute.xy(p,q),y);
   }
  }
 }
 function point(e,groundOnly){const {T,camera,canvas,building}=view,r=canvas.getBoundingClientRect(),ray=new T.Raycaster();ray.setFromCamera(new T.Vector2((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1),camera);
  if(!groundOnly){const floors=[];building.traverse(o=>{if(o.isMesh&&o.visible&&o.userData.layer==='floor')floors.push(o);});const hit=ray.intersectObjects(floors,false)[0];if(hit)return hit.point.toArray();if(action==='fire')return null;}
  const p=new T.Vector3();return ray.ray.intersectPlane(new T.Plane(new T.Vector3(0,1,0),0),p)?p.toArray():null;
 }
 function place(e){const d=data(),p=point(e,action==='vehicle'||action==='move');if(!p){note('표시된 바닥을 선택하세요. 바닥이 없는 층에는 화점을 놓을 수 없습니다.');return;}
  if(action==='vehicle'){const v={id:id(),position:p,heading:0};d.vehicles.push(v);vehicleId=v.id;setAction(null);}
  else if(action==='move'){const v=d.vehicles.find(v=>v.id===vehicleId);if(v){const delta=p.map((x,i)=>x-v.position[i]);v.position=p;for(const r of d.routes.filter(r=>r.vehicleId===v.id))r.points[0]=p.slice();}for(const r of d.routes.filter(r=>r.automatic&&r.vehicleId===vehicleId)){const f=d.fires.find(f=>f.id===r.fireId);if(f)auto(f);}setAction(null);}
  else if(action==='fire'){const selected=$('viewFloor').value,levels=state.pages.filter(p=>p.included);const closest=levels.reduce((a,b)=>Math.abs((a.elevation||0)-p[1])<Math.abs((b.elevation||0)-p[1])?a:b,levels[0]);const f={id:id(),position:p,size:$('opFireSize').value,floor:closest?.floor,levelKey:selected!=='all'?selected:closest?closest.building+'|'+closest.floor:null};d.fires.push(f);fireId=f.id;auto(f);}
  else if(action==='route'){const r=d.routes.find(r=>r.id===routeId);if(r&&Math.hypot(...p.map((x,i)=>x-r.points.at(-1)[i]))>.1)r.points.push(p);}
  save();refresh();
 }
 window.installOperations=(T,scene,camera,canvas,building)=>{if(view)return;const root=new T.Group();root.name='operation-overlays';scene.add(root);view={T,scene,camera,canvas,building,root};
  canvas.addEventListener('pointerdown',e=>{if(!action)return;if(!e.isPrimary)return;e.preventDefault();e.stopImmediatePropagation();down={x:e.clientX,y:e.clientY,id:e.pointerId};canvas.setPointerCapture(e.pointerId);},true);
  canvas.addEventListener('pointermove',e=>{if(action){e.preventDefault();e.stopImmediatePropagation();}},true);
  canvas.addEventListener('pointerup',e=>{if(!action)return;e.preventDefault();e.stopImmediatePropagation();if(down&&e.pointerId===down.id&&Math.hypot(e.clientX-down.x,e.clientY-down.y)<7)place(e);down=null;},true);
  canvas.addEventListener('pointercancel',()=>{down=null;},true);refresh();};
 window.operationsRefresh=()=>render();
 function mount(){const host=$('resultOperations');if(!host)return;host.innerHTML=`<button id="opVehicleAdd">＋ 차량 추가 배치</button><select id="opVehicles" aria-label="차량 선택"></select><div class="opRow"><button id="opMove">이동</button><button id="opVehicleDelete">삭제</button></div><label>경로 선택</label><select id="opRoutes" aria-label="경로 선택"></select><div class="opRow"><button id="opRouteAdd">＋ 경로</button><button id="opRouteDelete">삭제</button></div><button id="opAutoRoute">화점 경로 자동 생성</button><button id="opRouteUndo">마지막 점 취소</button><p id="opRouteInfo"></p><button id="opFireAdd">＋ 화점 설정 · 복수</button><select id="opFires" aria-label="화점 선택"></select><label>화염 크기<select id="opFireSize" aria-label="화염 크기"><option value="small">소</option><option value="medium" selected>중</option><option value="large">대</option></select></label><div class="opRow"><button id="opFireDelete">화점 삭제</button><button id="opDone">완료</button></div><p id="opNotice" role="status"></p><p>화점 지정 시 자동 경로를 생성합니다. 연결이 불명확한 곳은 알림으로 표시합니다.</p>`;
  const style=document.createElement('style');style.textContent='#resultOperations{flex:0 0 auto!important;min-height:0!important}#resultOperations .opRow{display:flex;gap:5px}#resultOperations button{border:1px solid #506a7d!important;padding:5px!important;margin:3px 0!important;text-align:center!important;white-space:normal!important;min-height:30px!important}#resultOperations select{width:100%;margin:4px 0!important;min-height:30px!important;font-size:11px!important}#resultOperations p{margin:5px 0;font-size:10px!important}#opNotice{color:#ffdd77}';document.head.append(style);
  const begin=a=>{if(mode!=='3d')switchMode('3d');setAction(a);};
  $('opVehicleAdd').onclick=()=>begin('vehicle');$('opMove').onclick=()=>begin('move');$('opVehicleDelete').onclick=()=>{const d=data();d.vehicles=d.vehicles.filter(v=>v.id!==vehicleId);d.routes=d.routes.filter(r=>r.vehicleId!==vehicleId);setAction(null);save();refresh();};$('opVehicles').onchange=e=>{vehicleId=e.target.value;render();};
  $('opRouteAdd').onclick=()=>{const v=data().vehicles.find(v=>v.id===vehicleId);if(!v)return;const r={id:id(),vehicleId,points:[v.position.slice()]};data().routes.push(r);routeId=r.id;save();refresh();begin('route');};$('opRoutes').onchange=e=>{routeId=e.target.value;setAction(null);refresh();};$('opRouteDelete').onclick=()=>{data().routes=data().routes.filter(r=>r.id!==routeId);setAction(null);save();refresh();};$('opRouteUndo').onclick=()=>{const r=data().routes.find(r=>r.id===routeId);if(r?.points.length>1){r.points.pop();r.automatic=false;delete r.contexts;}save();refresh();};
  $('opAutoRoute').onclick=()=>{const f=data().fires.find(f=>f.id===fireId);if(f){auto(f);save();refresh();}else note('화점을 먼저 지정하세요.');};$('opFireAdd').onclick=()=>begin('fire');$('opFires').onchange=e=>{fireId=e.target.value;refresh();};$('opFireSize').onchange=e=>{const f=data().fires.find(f=>f.id===fireId);if(f){f.size=e.target.value;save();render();}};$('opFireDelete').onclick=()=>{data().routes=data().routes.filter(r=>r.fireId!==fireId);data().fires=data().fires.filter(f=>f.id!==fireId);save();refresh();};$('opDone').onclick=()=>setAction(null);document.addEventListener('keydown',e=>{if(e.key==='Escape')setAction(null);});$('mode2d').addEventListener('click',()=>setAction(null));refresh();
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();
})();
