// Classification review only. Never rewrites a completed fire simulation.
export async function attachLiteDoors(panel,viewer){
 const host=document.createElement('details');host.id='liteDoorClasses';
 const title=document.createElement('summary');title.textContent='간략 탐색 · 문 자동 분류와 정정';host.append(title);
 const note=document.createElement('p');note.textContent='자동 분류는 도면·실 이름 기반 프로젝트 가정입니다. 방화 성능 확인이 아닙니다. 변경은 저장 후 다음 탐색에 적용됩니다.';host.append(note);
 const toggle=document.createElement('input');toggle.type='checkbox';const label=document.createElement('label');label.append(toggle,' 3D 문 분류 기호 표시 · 기호 클릭으로 분류 변경');host.append(label);
 const status=document.createElement('p');status.setAttribute('role','status');host.append(status);
 const table=document.createElement('table');host.append(table);(panel.querySelector('#cfbtBody')||panel).append(host);
 const {THREE:T,S,C,R}=viewer,group=new T.Group();S.add(group);const marks=[];
 const fetchData=async()=>{const res=await fetch('/cfbt/lite/doors');if(!res.ok)throw Error('문 분류 API를 불러오지 못했습니다');return res.json();};
 const update=async(row)=>{
  const value=row.door_class==='fire'?'ordinary':'fire';status.textContent='저장 중…';
  try{const response=await fetch('/cfbt/lite/doors',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:row.id,door_class:value})});const data=await response.json();if(!response.ok)throw Error(data.error);render(data);status.textContent=`${row.id}: ${value==='fire'?'방화문':'일반문'}으로 저장. 기존 계산 결과는 그대로입니다.`;}catch(error){status.textContent=error.message;}
 };
 function render(data){
  table.replaceChildren();const head=table.insertRow();for(const h of ['문','연결 실','분류 / 근거','수정']){const th=document.createElement('th');th.textContent=h;head.append(th);}
  for(const m of marks){group.remove(m);m.geometry.dispose();m.material.dispose();}marks.length=0;
  for(const row of data.rows){
   const tr=table.insertRow();tr.insertCell().textContent=row.id;tr.insertCell().textContent=`${row.a} ↔ ${row.b} (${row.connected_names.join(' / ')})`;
   const confidence={confirmed:'규칙상 확정',inferred:'추정',default:'기본 분류',user:'사용자 정정',not_applicable:'해당 없음'}[row.confidence]||row.confidence;
   tr.insertCell().textContent=`${row.door_class==='fire'?'방화문':'일반/외기문'} · 규칙 ${row.rule} · ${confidence} · ${row.reason}`;
   const button=document.createElement('button');button.textContent=row.door_class==='fire'?'일반문으로':'방화문으로';button.onclick=()=>update(row);tr.insertCell().append(button);
   if(row.position_m){const m=new T.Mesh(new T.SphereGeometry(.35,10,8),new T.MeshBasicMaterial({color:row.door_class==='fire'?(row.confidence==='inferred'?0xffb14d:0xed637d):0x7ccbc2,depthTest:false}));m.position.set(...row.position_m);m.position.z+=1.3;m.userData.door=row;m.renderOrder=50;group.add(m);marks.push(m);}
  }
 }
 const ray=new T.Raycaster();const click=event=>{if(!group.visible)return;const rect=R.domElement.getBoundingClientRect();ray.setFromCamera(new T.Vector2((event.clientX-rect.left)/rect.width*2-1,-(event.clientY-rect.top)/rect.height*2+1),C);const hit=ray.intersectObjects(marks);if(hit.length){event.stopImmediatePropagation();host.open=true;update(hit[0].object.userData.door);}};R.domElement.addEventListener('click',click,true);
 const show=()=>{group.visible=toggle.checked&&['all','3F'].includes(viewer.getFloor());};toggle.onchange=show;
 let disposed=false;const timer=setInterval(show,250);const dispose=()=>{if(disposed)return;disposed=true;clearInterval(timer);window.removeEventListener('pagehide',dispose);R.domElement.removeEventListener('click',click,true);for(const m of marks){m.geometry.dispose();m.material.dispose();}marks.length=0;group.clear();group.removeFromParent();host.remove();};window.addEventListener('pagehide',dispose,{once:true});show();
 try{render(await fetchData());}catch(error){status.textContent=error.message;}
 return {dispose};
}
