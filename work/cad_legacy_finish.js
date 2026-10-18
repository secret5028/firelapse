window.installOperations(THREE,legacyRoot,C,R.domElement,S);
window.installHydraulicView(THREE,legacyRoot,C,R.domElement);
const facilities=document.createElement('section');facilities.innerHTML='<h2>소방 설비·계통</h2><button id="legacyNetwork">송수구 · 연결 구역 · 압력</button><p class="small">등록한 계통의 송수구와 연결 말단을 강조합니다. 건축 CAD에 없는 소방 배관은 자동으로 만들지 않습니다.</p>';panel.insertBefore(facilities,advanced);
$ui('legacyNetwork').onclick=()=>window.HydraulicUI.open();
const hydraulicHost=$ui('hydraulic-tool');if(hydraulicHost?.shadowRoot)hydraulicHost.shadowRoot.getElementById('toggle').hidden=true;
// Restore the same 15 m hose rule used by the original hose badge.
const routeInfo=$ui('opRouteInfo'),hoseInfo=document.createElement('p');hoseInfo.id='hoseInfo';routeInfo.after(hoseInfo);
function hoseReadout(){const route=state.operations.routes.find(r=>r.id===$ui('opRoutes').value);const distance=route?.points.slice(1).reduce((n,p,i)=>n+Math.hypot(...p.map((v,k)=>v-route.points[i][k])),0)||0;hoseInfo.textContent=route?'소요 수관 '+Math.ceil(distance/15)+'본 · 1본 15m · 여유분 제외':''}
new MutationObserver(hoseReadout).observe(routeInfo,{childList:true,characterData:true,subtree:true});hoseReadout();
// Reuse the original human geometry (1.75 m) for independent placement.
const personParts=referenceObjects.children.filter(o=>!o.isSprite&&o.position.x>4.7);
const peopleRoot=new THREE.Group();legacyRoot.add(peopleRoot);let placingPerson=false;
function refreshPeople(){
 const selector=$ui('peopleSelect'),selected=selector.value;selector.replaceChildren();
 if(!state.operations.people.length)selector.add(new Option('없음',''));
 while(peopleRoot.children.length){const g=peopleRoot.children.pop();g.traverse(o=>{o.geometry?.dispose();o.material?.dispose()});g.parent=null}
 state.operations.people.forEach((person,i)=>{selector.add(new Option('사람 '+(i+1),person.id));const group=new THREE.Group();group.position.fromArray(person.position);peopleRoot.add(group);for(const part of personParts){const mesh=part.clone();mesh.geometry=part.geometry.clone();mesh.material=part.material.clone();mesh.position.x-=5.1;mesh.position.z+=.4;group.add(mesh)}});
 if(state.operations.people.some(p=>p.id===selected))selector.value=selected;
 $ui('personDelete').disabled=!state.operations.people.length;
}
$ui('personAdd').onclick=()=>{$ui('opDone').click();placingPerson=true;$ui('personNotice').textContent='사람을 놓을 바닥이나 지면을 누르세요.'};
$ui('personDelete').onclick=()=>{state.operations.people=state.operations.people.filter(p=>p.id!==$ui('peopleSelect').value);persist();refreshPeople()};
let personDown=null;
R.domElement.addEventListener('pointerdown',e=>{if(!placingPerson)return;e.stopImmediatePropagation();personDown=[e.clientX,e.clientY];R.domElement.setPointerCapture(e.pointerId)},true);
R.domElement.addEventListener('pointerup',e=>{if(!placingPerson)return;e.stopImmediatePropagation();if(personDown&&Math.hypot(e.clientX-personDown[0],e.clientY-personDown[1])<7){const p=cadPick(e,false)||cadPick(e,true);if(p){state.operations.people.push({id:crypto.randomUUID(),position:p});placingPerson=false;persist();refreshPeople();$ui('personNotice').textContent='사람 배치 완료'}}personDown=null},true);
document.addEventListener('keydown',e=>{if(e.key==='Escape')placingPerson=false});
refreshPeople();syncLegacyFloor();
// Keep the user-facing diagnostic state readable without exposing mutable scene objects.
const previousSnapshot=window.cadViewerSnapshot;
window.cadViewerSnapshot=()=>({...previousSnapshot(),legacy:{vehicles:state.operations.vehicles.length,routes:state.operations.routes.length,fires:state.operations.fires.length,people:state.operations.people.length,hydraulics:!!window.HydraulicUI}});
updateDiagnostic();
