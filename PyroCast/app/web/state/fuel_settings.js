// Same precedence as fuel_quantity.resolve: room > floor > AI/default.
export function fuelSettingsWithDraft(data,draft={}){
 const saved=data?.quantity_settings||{},rooms={...saved.rooms},floors={...saved.floors,...draft.floors};
 for(const [id,row] of Object.entries(draft.rooms||{})){if(row===null)delete rooms[id];else rooms[id]=row;}
 return {...saved,rooms,floors};
}
export function resolveFuel(data,draft,row){
 const saved=fuelSettingsWithDraft(data,draft),room=saved.rooms[row.id],floor=saved.floors[row.floor],setting=room??floor??{},ai=saved.defaults?.[row.id];
 const chosen=setting.usage_class||ai?.usage_class,usage_class=chosen||row.baseline_class,base=chosen?data.classes[usage_class].mean:row.baseline_load;
 const multiplier=setting.multiplier??1;
 return {usage_class,multiplier,load:base*multiplier,hrrpua:data.classes[usage_class].rhrf,scope:room?'room':floor?'floor':'default',
  pending:!setting.usage_class&&!ai&&data.ai_pending?.includes(row.id)};
}
