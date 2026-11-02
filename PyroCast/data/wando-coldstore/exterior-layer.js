// Photo-based architectural shell, deliberately outside the simulation model.
export function createExteriorLayer(T,scene,config,pane,redraw=()=>{}){
 const root=new T.Group(),resources=[];root.name='wando-photo-exterior';scene.add(root);
 const own=o=>(resources.push(o),o),mat=color=>own(new T.MeshBasicMaterial({color,side:T.DoubleSide,transparent:true,opacity:.28,depthWrite:false}));
 const white=mat('#d1d8dc'),side=mat('#aebdc6'),blue=mat(config.main_roof.color),darkBlue=mat('#3187a1'),cap=mat('#e8eceb'),glass=mat('#546b74');
 function mesh(geometry,material){const o=new T.Mesh(own(geometry),material);o.renderOrder=11;o.raycast=()=>{};root.add(o);return o;}
 function box(x,y,z,w,d,h,material){const o=mesh(new T.BoxGeometry(w,d,h),material);o.position.set(x,y,z);return o;}
 function face(points,material){const g=new T.BufferGeometry(),pos=[];for(let i=1;i<points.length-1;i++)for(const p of [points[0],points[i],points[i+1]])pos.push(...p);g.setAttribute('position',new T.Float32BufferAttribute(pos,3));g.computeVertexNormals();return mesh(g,material);}
 function lines(points,color='#dbe7eb'){const o=new T.Line(own(new T.BufferGeometry().setFromPoints(points.map(p=>new T.Vector3(...p)))),own(new T.LineBasicMaterial({color,transparent:true,opacity:.3,depthWrite:false})));o.renderOrder=12;o.raycast=()=>{};root.add(o);return o;}
 const r=config.main_roof,mid=(r.y0+r.y1)/2,peak=r.eave_z+r.ridge_rise;
 face([[r.x0,r.y0,r.eave_z],[r.x1,r.y0,r.eave_z],[r.x1,mid,peak],[r.x0,mid,peak]],blue);
 face([[r.x0,mid,peak],[r.x1,mid,peak],[r.x1,r.y1,r.eave_z],[r.x0,r.y1,r.eave_z]],darkBlue);
 for(const x of [r.x0,r.x1])face([[x,r.y0,r.eave_z],[x,mid,peak],[x,r.y1,r.eave_z]],white);
 box(36,mid,peak+.03,72,.18,.08,cap);
 for(let x=1.5;x<72;x+=1.5)lines([[x,0,r.eave_z+.015],[x,mid,peak+.015],[x,18.4,r.eave_z+.015]],'#70b8c9');
 // Facade panels leave the existing front door apertures open. These meshes
 // are decorative and never enter the room/door graph or picking planes.
 for(const [a,b,w,h] of [[0,9,.9,2.1],[9,18,2.5,3],[18,27,2.5,3],[27,36,2.5,3],[36,45,2.5,3],[45,53.75,2.5,3],[54,72,2.5,3]]){
  const c=(a+b)/2;for(const [l,u,lo,hi] of [[a,c-w/2,0,r.eave_z],[c+w/2,b,0,r.eave_z],[c-w/2,c+w/2,h,r.eave_z]])box((l+u)/2,-.025,(lo+hi)/2,u-l,.05,hi-lo,white);
  if(a!==45)box(c,0,h/2,w,.035,h,side);
 }
 box(0,9.2,3.2025,.08,18.4,6.405,side);box(72,9.2,3.2025,.08,18.4,6.405,white);box(36,18.4,3.2025,72,.06,6.405,side);
 const c=config.canopy;face([[c.x0,0,c.wall_z],[c.x1,0,c.wall_z],[c.x1,-c.depth,c.front_z],[c.x0,-c.depth,c.front_z]],mat(c.color));
 box((c.x0+c.x1)/2,-c.depth,c.front_z-.1,c.x1-c.x0,.12,.22,side);
 for(let x=c.x0;x<=c.x1;x+=9){box(x,-c.depth+.15,c.front_z/2,.1,.1,c.front_z,side);lines([[x,0,c.wall_z+.01],[x,-c.depth,c.front_z+.01]],'#879da7');}
 for(let x=c.x0;x<c.x1;x+=1)lines([[x,0,c.wall_z+.012],[x,-c.depth,c.front_z+.012]],'#afbec4');
 const u=config.upper_left,top=u.base_z+u.height;
 box((u.x0+u.x1)/2,u.y0, u.base_z+u.height/2,u.x1-u.x0,.08,u.height,white);
 box(u.x0,(u.y0+u.y1)/2,u.base_z+u.height/2,.08,u.y1-u.y0,u.height,side);
 box(u.x1,(u.y0+u.y1)/2,u.base_z+u.height/2,.08,u.y1-u.y0,u.height,white);
 box((u.x0+u.x1)/2,u.y1,u.base_z+u.height/2,u.x1-u.x0,.08,u.height,white);
 box((u.x0+u.x1)/2,(u.y0+u.y1)/2,top,u.x1-u.x0,u.y1-u.y0,.12,blue);
 for(let x=1.5;x<27;x+=3)box(x,-.065,u.base_z+1.6,1.1,.025,1.1,glass);
 for(let z=u.base_z+.3;z<top;z+=.4)lines([[0,-.052,z],[27,-.052,z]],'#afbec4');
 for(const y of [u.y0,u.y1])box(13.5,y,top+.16,27,.12,.32,cap);
 const controls=document.createElement('section');controls.id='wandoExteriorControls';
 const row=document.createElement('label'),input=document.createElement('input');input.id='wandoExterior';input.type='checkbox';input.checked=true;row.className='displayToggle';row.append('사진 기준 외형 · 투시 ',input);controls.append(row);
 input.onchange=()=>{root.visible=input.checked;redraw();};
 const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent='외형 치수 근거 · 가정';details.append(summary);
 for(const value of config.basis){const p=document.createElement('p');p.textContent=value;details.append(p);}controls.append(details);pane.prepend(controls);
 return {root,dispose(){scene.remove(root);resources.forEach(o=>o.dispose());controls.remove();}};
}
