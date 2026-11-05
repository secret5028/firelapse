import assert from 'node:assert/strict';
import {viewStorageKey,readSavedView,writeSavedView,restoredView} from '../web/state/saved_view.js';
const map=new Map(),storage={getItem:k=>map.get(k),setItem:(k,v)=>map.set(k,v)};
const key=viewStorageKey('/model.html','hotel');
const saved={hash:'hotel',case_id:'sample-S08',floor:'5F',time_s:1420,tab:'display',selection:{room_id:'R16',cell_id:'R16_C1'}};
assert(writeSavedView(storage,key,saved));assert.equal(readSavedView(storage,key,'hotel').case_id,'sample-S08');
assert.equal(readSavedView(storage,key,'other'),null);
assert.notEqual(key,viewStorageKey('/model.html','other'));
const b={floors:[{floor_id:'5F',rooms:[{room_id:'R16',cells:[{cell_id:'R16_C1'}]}]},{floor_id:'2F',rooms:[{room_id:'R2',cells:[]}]}]};
assert.deepEqual(restoredView(saved,b,3600),{floor:'5F',time_s:1420,tab:'display',selection:{room_id:'R16',cell_id:'R16_C1',source:'list'}});
assert.equal(restoredView(saved,b,600).time_s,600);
assert.equal(restoredView({...saved,floor:'2F'},b,3600).selection.room_id,null);
assert.equal(restoredView({...saved,selection:{room_id:'R16',cell_id:'missing'}},b,3600).selection.cell_id,null);
storage.setItem(key,'{broken');assert.equal(readSavedView(storage,key,'hotel'),null);
assert.equal(readSavedView({getItem(){throw Error('blocked');}},key,'hotel'),null);
assert.equal(writeSavedView({setItem(){throw Error('quota');}},key,saved),false);
for(const time_s of [-1,null,'1420']){writeSavedView(storage,key,{...saved,time_s});assert.equal(readSavedView(storage,key,'hotel'),null);}
console.log('PASS: saved view isolation, corrupt/blocked storage, time clamp, floor/room/cell validation');
