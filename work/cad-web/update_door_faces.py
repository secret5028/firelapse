from pathlib import Path
p=Path('work/industrial.js')
s=p.read_text(encoding='utf-8')
helper='''// Exterior-facing door emphasis; inward views retain the original material.
const exteriorDoorMaterials=[];
function exteriorNormal(o){if(o.axis==='x'){if(Math.abs(o.z)<.02)return V(0,0,-1);if(Math.abs(o.z-32)<.02)return V(0,0,1)}else{if(Math.abs(o.x)<.02)return V(-1,0,0);if(Math.abs(o.x-98.6)<.02)return V(1,0,0)}return null}
function exteriorDoorMaterial(o){const normal=exteriorNormal(o);if(!normal)return glass;const material=glass.clone();exteriorDoorMaterials.push({material,normal,point:V(o.x,0,o.z),opacity:glass.opacity});return material}
function updateDoorFaces(){for(const d of exteriorDoorMaterials)d.material.opacity=camera.position.clone().sub(d.point).dot(d.normal)>0?.72:d.opacity}
function slidingExteriorFace(f,o,g){const normal=exteriorNormal(o);if(!normal)return;const m=new THREE.MeshBasicMaterial({color:0xffcf59,transparent:true,opacity:.62,side:THREE.FrontSide,depthWrite:false});const mesh=new THREE.Mesh(new THREE.PlaneGeometry(o.width,o.height),m);mesh.quaternion.setFromUnitVectors(V(0,0,1),normal);mesh.position.set(o.x+(o.axis==='x'?o.width/2:0),f.y+o.height/2,o.z+(o.axis==='z'?o.width/2:0));mesh.position.addScaledVector(normal,.025);g.add(mesh)}
'''
s=s.replace('function door(f,o,g){',helper+'function door(f,o,g){const leafMaterial=exteriorDoorMaterial(o);')
s=s.replace("if(o.kind==='sliding'){line", "if(o.kind==='sliding'){slidingExteriorFace(f,o,g);line")
s=s.replace('a?width:.04,glass,info)', 'a?width:.04,leafMaterial,info)')
s=s.replace('updateHoseSize();renderer.render(scene,camera)', 'updateHoseSize();updateDoorFaces();renderer.render(scene,camera)')
p.write_text(s,encoding='utf-8')
# Update bundled app while preserving its touch controls and other additions.
import json
q=Path('work/fire-site/public/models/industrial.html')
t=q.read_text(encoding='utf-8')
a=t.index('const app=URL.createObjectURL(new Blob([')+len('const app=URL.createObjectURL(new Blob([')
b=t.index('.replace("__THREE__",lib)',a)
t=t[:a]+json.dumps(s,ensure_ascii=False).replace('</','<\\/')+t[b:]
q.write_text(t,encoding='utf-8')
