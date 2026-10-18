from pathlib import Path
import json
p=Path('work/industrial.js');s=p.read_text(encoding='utf-8')
a=s.index('// Exterior-facing door emphasis;');b=s.index('function door(f,o,g){',a)
s=s[:a]+'''// Exterior doors gain only a stronger frame when viewed from outside.
const exteriorDoorMaterials=[];
function exteriorNormal(o){if(o.axis==='x'){if(Math.abs(o.z)<.02)return V(0,0,-1);if(Math.abs(o.z-32)<.02)return V(0,0,1)}else{if(Math.abs(o.x)<.02)return V(-1,0,0);if(Math.abs(o.x-98.6)<.02)return V(1,0,0)}return null}
function exteriorDoorFrame(f,o,g){const normal=exteriorNormal(o);if(!normal)return;const group=new THREE.Group();g.add(group);const m=new THREE.MeshBasicMaterial({color:0xffb800});const a=o.axis==='x',t=.19;for(const u of [0,o.width])box(group,o.x+(a?u:0)-t/2,f.y,o.z+(a?0:u)-t/2,t,o.height,t,m);box(group,o.x-t/2,f.y+o.height-t/2,o.z-t/2,a?o.width+t:t,t,a?t:o.width+t,m);exteriorDoorMaterials.push({group,normal,point:V(o.x,0,o.z)})}
function updateDoorFaces(){for(const d of exteriorDoorMaterials)d.group.visible=camera.position.clone().sub(d.point).dot(d.normal)>0}
'''+s[b:]
s=s.replace('const leafMaterial=exteriorDoorMaterial(o);','exteriorDoorFrame(f,o,g);').replace('slidingExteriorFace(f,o,g);','').replace('a?width:.04,leafMaterial,info)','a?width:.04,glass,info)')
p.write_text(s,encoding='utf-8')
q=Path('work/fire-site/public/models/industrial.html');t=q.read_text(encoding='utf-8');a=t.index('const app=URL.createObjectURL(new Blob([')+len('const app=URL.createObjectURL(new Blob([');b=t.index('.replace("__THREE__",lib)',a);q.write_text(t[:a]+json.dumps(s,ensure_ascii=False).replace('</','<\\/')+t[b:],encoding='utf-8')
