import {EmptyLayer} from './empty.js';
import {fuelPositions} from './fuel_quantity.js';
// CAD text only: never substitute inferred fuel/use classes for missing labels.
export function cadRoomNames(building){return (building.floors||[]).flatMap(f=>(f.rooms||[]).flatMap(r=>{
 const names=[...new Set((r.names||[]).map(n=>String(n).trim()).filter(n=>n&&!/협의|두께|구조검토|기어리스|tray|TRAY|급탕관|환탕관|급수관|주통기관|주오수관|벽체|문폭|복도폭|설치공간|축소|확대|변경|m\/s|→|->|^\(|^\d+\s*인승$|^(갑|화|-)$/.test(n)))];
 const text=names.join(' · ');
 if(!text)return [];const p=fuelPositions(r.polys)[0]?.p;if(!p)return [];
 return [{floor:f.name,id:r.id,text,point:[...p,.18]}];
}));}
export class RoomNamesLayer extends EmptyLayer{
 static id='roomNames';
 constructor(T,{building,groups,camera,container}){super(T);this.building=building;this.groups=groups;this.camera=camera;this.container=container;this.labels=[];}
 mount(scene,store){super.mount(scene,store);const doc=this.container.ownerDocument;this.root=doc.createElement('div');this.root.className='cadRoomNames';this.root.style.cssText='position:absolute;inset:0;pointer-events:none;overflow:hidden;z-index:5';this.container.append(this.root);
  for(const row of cadRoomNames(this.building)){const floor=this.groups.find(g=>g.name===row.floor);if(!floor)continue;const label=doc.createElement('span');label.textContent=row.text;label.title=row.floor+' '+row.id+' · '+row.text;label.style.cssText='position:absolute;transform:translate(-50%,-50%);white-space:nowrap;max-width:170px;overflow:hidden;text-overflow:ellipsis;font:11px sans-serif;color:#f2f7fa;text-shadow:0 1px 2px #102331,1px 0 2px #102331,-1px 0 2px #102331';this.root.append(label);this.labels.push({row,floor,label});}
 }
 tick(){this.root.hidden=this.visible===false||!this.frame?.layers?.building;if(this.root.hidden)return;const selected=this.frame.floor.floor_id;this.camera.updateMatrixWorld();
  const occupied=[],chosen=this.frame.selection?.room_id;
  const ordered=[...this.labels].sort((a,b)=>Number(`CAD_${b.row.floor}_${b.row.id}`===chosen)-Number(`CAD_${a.row.floor}_${a.row.id}`===chosen));
  for(const item of ordered){const {row,floor,label}=item;label.hidden=!floor.visible||(selected!==null&&selected!==row.floor);if(label.hidden)continue;floor.updateWorldMatrix(true,false);const p=floor.localToWorld(new this.THREE.Vector3(...row.point)).project(this.camera);label.hidden=p.z< -1||p.z>1||Math.abs(p.x)>1||Math.abs(p.y)>1;if(label.hidden)continue;
   const x=(p.x+1)*this.container.clientWidth/2,y=(1-p.y)*this.container.clientHeight/2,w=item.width||(item.width=label.offsetWidth),h=16;
   const box=[x-w/2-3,y-h/2-2,x+w/2+3,y+h/2+2];
   if(occupied.some(b=>box[0]<b[2]&&box[2]>b[0]&&box[1]<b[3]&&box[3]>b[1])){label.hidden=true;continue;}
   occupied.push(box);label.style.left=x+'px';label.style.top=y+'px';
  }
 }
 dispose(){this.root?.remove();this.labels=[];super.dispose();}
}
