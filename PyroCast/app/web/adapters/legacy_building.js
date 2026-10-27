// References are borrowed from the CAD loader, never from another display layer.
// The three install() branches, in their original order. A colour-bearing
// material alone is not enough: only objects touched by a branch are selected.
export function legacyBuildingStyle(object,floorId){
 if(!object.material?.color)return null;
 let color=null,opacity=null;
 if(object.name?.startsWith(floorId+'_'))color='#aab7c0';
 else if([0x8a8a8a,0x8b5a2b,0x93acb5].includes(object.material.color.getHex()))color='#b8c3cb';
 if(object.isLineSegments&&object.userData.cadOutline){color='#bdcbd5';opacity=.42;}
 return color===null?null:{color,opacity};
}
export function readLegacyBuildingSource({building,groups,sourceHash}){
 if(!/^[a-f0-9]{64}$/.test(sourceHash))throw Error('CAD source hash required');
 const floors=building.floors.map(f=>{
  const matches=groups.filter(g=>g.name===f.name);if(matches.length!==1)throw Error('Missing/duplicate CAD floor group: '+f.name);
  const group=matches[0],objects=[],styles=[];
  group.traverse(object=>{const style=legacyBuildingStyle(object,f.name);if(!style)return;
   if(!object.isMesh&&!object.isLine)throw Error('Unsupported install-coloured CAD object: '+object.type);
   objects.push(object);styles.push(Object.freeze(style));
  });
  return Object.freeze({id:f.name,group,objects:Object.freeze(objects),styles:Object.freeze(styles)});
 });return Object.freeze({source_hash:sourceHash,floors:Object.freeze(floors)});
}
