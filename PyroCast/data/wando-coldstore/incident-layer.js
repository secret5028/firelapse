// Wando-only static investigation overlay. No fire/oxygen/flow state changes.
export function createIncidentLayer(T,scene,building,tactical,pane){
 const root=new T.Group(),obstacles=new T.Group(),people=new T.Group(),resources=[],elements=[];
 root.name='wando-incident';obstacles.name='wando-obstacles';people.name='wando-person-markers';root.add(obstacles,people);scene.add(root);
 const own=o=>(resources.push(o),o);
 function label(text,position,group,{width=2.5,height=.55,color='#eaf4ff',background='#132c3e',square=false}={}){
  const c=document.createElement('canvas');c.width=square?128:512;c.height=128;const ctx=c.getContext('2d');ctx.fillStyle=background;ctx.fillRect(0,0,c.width,128);ctx.fillStyle=color;ctx.font=`bold ${square?100:58}px sans-serif`;ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(text,c.width/2,65);
  const s=new T.Sprite(own(new T.SpriteMaterial({map:own(new T.CanvasTexture(c)),transparent:true,depthTest:false,depthWrite:false})));
  s.position.fromArray(position);s.scale.set(width,height,1);s.renderOrder=81;s.raycast=()=>{};group.add(s);return s;
 }
 for(const o of building.obstacles||[]){
  const mesh=new T.Mesh(own(new T.BoxGeometry(...o.size_m)),own(new T.MeshBasicMaterial({color:o.color,transparent:true,opacity:.85,depthTest:false,depthWrite:false})));
  mesh.name=o.id;mesh.position.fromArray(o.center_m);mesh.renderOrder=74;mesh.userData.basis=o.basis;mesh.raycast=()=>{};obstacles.add(mesh);
  const edge=new T.LineSegments(own(new T.EdgesGeometry(mesh.geometry)),own(new T.LineBasicMaterial({color:'#e6f5ff',transparent:true,opacity:.95,depthTest:false,depthWrite:false})));
  edge.position.copy(mesh.position);edge.renderOrder=75;edge.raycast=()=>{};obstacles.add(edge);
  label(o.name,[o.center_m[0],o.center_m[1],o.center_m[2]+o.size_m[2]/2+.35],obstacles,{width:o.id==='COOLER'?2.8:2});
 }
 for(const p of tactical.people){
  const marker=label(['','①','②','③','④','⑤'][p.number],[p.position_m[0],p.position_m[1],.65],people,{width:.85,height:.85,color:'#fff5ca',background:'#273e55',square:true});
  marker.name='person-'+p.number;marker.userData.basis=p.basis;
  const dot=new T.Mesh(own(new T.CircleGeometry(.16,16)),own(new T.MeshBasicMaterial({color:'#fff2a0',depthTest:false,transparent:true,opacity:1})));
  dot.position.set(p.position_m[0],p.position_m[1],.08);dot.renderOrder=80;dot.raycast=()=>{};people.add(dot);
 }
 const controls=document.createElement('section');controls.id='wandoIncidentControls';
 const heading=document.createElement('h3');heading.textContent='완도 현장 배치';controls.append(heading);
 for(const [id,name,group] of [['wandoObstacles','실내 장애물',obstacles],['wandoInvestigation','사고 조사 ①–⑤',people]]){
  const row=document.createElement('label');row.className='displayToggle';const text=document.createElement('span');text.textContent=name;
  const input=document.createElement('input');input.type='checkbox';input.id=id;input.checked=true;input.setAttribute('role','switch');input.onchange=()=>group.visible=input.checked;row.append(text,input);controls.append(row);
 }
 const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent='배치 근거 · 가정과 한계';details.append(summary);
 for(const text of [tactical.route_origin.basis,...(building.obstacles||[]).map(o=>o.name+' — '+o.basis),...tactical.people.map(p=>p.number+' — '+p.basis),...tactical.limits,'장애물은 경로에만 적용하며 P1 CFAST 열·유동 계산에는 소급 반영하지 않음']){
  const p=document.createElement('p');p.textContent=text;details.append(p);
 }
 controls.append(details);pane.append(controls);elements.push(controls);
 return {setFloor(f){root.visible=f===null||f==='1F';},dispose(){scene.remove(root);resources.forEach(r=>r.dispose());elements.forEach(e=>e.remove());}};
}
