// Restored from the CAD reference model: 8 m truck and 1.75 m human.
// Display scale only; not incident positions or simulation participants.
export function createScaleReference(T){
 const ref=new T.Group();ref.name='scale-reference-source';ref.visible=false;
 ref.userData.includeScalePerson=true;
 const materials={};const material=color=>materials[color]||(materials[color]=new T.MeshBasicMaterial({color}));
 function box(w,h,d,x,y,z,color){const m=new T.Mesh(new T.BoxGeometry(w,h,d),material(color));m.position.set(x,y,z);ref.add(m);return m;}
 function cylinder(r,h,x,y,z,color,rotate=false){const m=new T.Mesh(new T.CylinderGeometry(r,r,h,20),material(color));m.position.set(x,y,z);if(rotate)m.rotation.x=Math.PI/2;ref.add(m);return m;}
 // Eight metre reference vehicle: chassis, cab, equipment body, roller doors and roof ladder.
 box(8,.24,2.35,0,.8,0,'#35444e');box(5.25,1.95,2.35,-1.25,1.9,0,'#bd2435');box(2.3,2.1,2.4,2.75,1.95,0,'#d73542');
 box(.04,.85,2.05,3.92,2.36,0,'#315a70');for(const z of [-1.211,1.211]){box(1.5,.8,.025,2.6,2.4,z,'#315a70');box(7.7,.16,.03,0,1.31,z,'#f3eee2');box(.28,.12,.05,3.5,1.03,z,'#fff3bc');for(const x of [-2.9,-1.25,.4]){box(1.35,1.38,.025,x,2.02,z,'#a4b0b7');for(let j=0;j<8;j++)box(1.29,.022,.038,x,1.45+j*.16,z,'#677781');}}
 for(const x of [-2.5,2.75])for(const z of [-1.18,1.18]){cylinder(.52,.28,x,.52,z,'#17232b',true);cylinder(.26,.3,x,.52,z,'#aebac1',true);}
 box(2.4,.15,2.6,2.7,.89,0,'#aebac1');box(1.4,.16,.35,2.7,3.1,0,'#458ce4');
 for(const z of [-.43,.43])box(4.9,.065,.065,-1.4,3.03,z,'#e9e9dd');for(let i=0;i<13;i++)box(.06,.055,.86,-3.7+i*.37,3.03,0,'#e9e9dd');
 // Human height is 1.75m, with feet resting on the same ground as the vehicle.
 const hx=5.1,hz=-.4;for(const dx of [-.12,.12]){box(.15,.67,.18,hx+dx,.42,hz,'#354956');box(.17,.12,.3,hx+dx,.06,hz+.055,'#202a33');}
 box(.45,.57,.23,hx,1.02,hz,'#e4ac36');for(const dx of [-.29,.29]){const arm=box(.13,.54,.15,hx+dx,1.0,hz,'#dca640');arm.rotation.z=dx>0?.10:-.10;}
 cylinder(.15,.28,hx,1.46,hz,'#d8ac83');const helmet=new T.Mesh(new T.SphereGeometry(.18,18,12,0,Math.PI*2,0,Math.PI/2),material('#efd267'));helmet.position.set(hx,1.57,hz);ref.add(helmet);

 ref.children.forEach((o,i)=>{o.name=(o.position.x>4.7?'scale-person:':'scale-truck:')+i;o.raycast=()=>{};});
 ref.userData.dispose=()=>{const resources=new Set();ref.traverse(o=>{if(o.geometry)resources.add(o.geometry);if(o.material)resources.add(o.material);});for(const r of resources)r.dispose();ref.removeFromParent();};
 return ref;
}
