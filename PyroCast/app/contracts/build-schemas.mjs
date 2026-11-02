// Build declarative JSON Schema artifacts. No engine imports or network access.
import {writeFileSync} from 'node:fs';
const str={type:'string'}, num={type:'number'}, bool={type:'boolean'}, nil={type:'null'};
const nullable=s=>({anyOf:[s,nil]});
const arr=s=>({type:'array',items:s});
const obj=(properties,required=Object.keys(properties),additionalProperties=false)=>({type:'object',properties,required,additionalProperties});
const dict=s=>({type:'object',additionalProperties:s});
const en=(...values)=>({enum:values});
const point=n=>({type:'array',items:num,minItems:n,maxItems:n});
const ring={...arr(point(2)),minItems:3};
const poly=obj({polygon_m:ring,holes_m:arr(ring)});
const issue=obj({code:str,ref:str,msg:str});
const sha={type:'string',pattern:'^[a-f0-9]{64}$'};
const ref=name=>({$ref:'#/$defs/'+name});
const seriesNames=['T_upper_C','T_lower_C','interface_m','O2_upper_volfrac','O2_lower_volfrac',
 'fuel_upper_massfrac','HRR_actual_kW','HRR_supply_kW','HRR_doorjet_kW','HRR_upperburn_kW'];
const series=obj({...Object.fromEntries(seriesNames.map(k=>[k,arr(nullable(num))])),
 O2_basis:en('layered','room_proxy',null),aggregation:en('single','none'),
 aggregation_status:en('direct','not_defined'),source_cells:arr(str),room_id:str,
 field_sources:dict(str),legacy_optical:obj({ODu:arr(nullable(num)),ODl:arr(nullable(num))})});
const criterion=obj({met:nullable(bool),degree:nullable(num),r_T:nullable(num),r_F:nullable(num),r_O:nullable(num),
 bottleneck:en('T','F','O',null),dominant:en('T','F','O',null),status:nullable(str),burning_upper:nullable(bool)},
 ['met','degree','r_T','r_F','r_O','bottleneck','dominant','status']);
const frame=obj({smoke_stage:en(0,1,2,null),smoke_factors:arr(en('hot','fuel','deep')),
 FO:ref('criterion'),FGI:ref('criterion'),backdraft:ref('criterion'),rollover:ref('criterion'),untenable:ref('criterion'),
 source_cells:arr(str),aggregation:en('single','cell_any')});
const timeline={type:'object',patternProperties:{'^(0|[1-9][0-9]*)$':ref('conditionFrame')},additionalProperties:false};
const cell=obj({cell_id:str,polygon_m:ring,holes_m:arr(ring),polygons_m:arr(poly),
 legacy_display:obj({z_m:num,height_m:num,single_zone:bool})},['cell_id','polygon_m','holes_m','polygons_m']);
const room=obj({room_id:str,name:str,usage:nullable(str),core_kind:en('stair','elevator','shaft','lobby','corridor',null),
 polygon_m:ring,holes_m:arr(ring),polygons_m:arr(poly),floor_z_m:num,ceiling_z_m:num,cells:arr(cell)});
const opening=obj({opening_id:str,kind:en('door','window','passage','vertical'),
 door_class:en('fire_confirmed','fire_estimated','ordinary','fixed',null),door_class_basis:nullable(str),
 user_override:bool,a:str,b:str,center_m:point(3),width_m:{type:'number',minimum:0},sill_m:num,soffit_m:num,
 exterior:bool,initial_fraction:{type:'number',minimum:0,maximum:1},source_kind:str});
const schemas={
 building:obj({schema:{const:'pyrocast.building/1'},building_id:str,source_hash:sha,
  units:obj({length:{const:'m'},origin:point(3),up:{const:'z'}}),
  floors:arr(obj({floor_id:str,name:str,elevation_m:num,height_m:num,rooms:arr(room),openings:arr(opening)})),
  errors:arr(issue),scope:str,geometry_notes:arr(str)}),
 result:obj({schema:{const:'pyrocast.result/1'},result_id:str,
  engine:obj({kind:en('lite','cfast'),version:nullable(str),sha256:nullable(sha)}),
  scenario:obj({building_id:str,floor_id:nullable(str),origin_room_id:nullable(str),settings_snapshot:{type:'object'},
   settings_hash:sha,seed:nullable({type:'integer'}),opening_state:dict(nullable(num))}),
  status:en('complete','partial','failed'),t_end_s:nullable(num),dt_out_s:nullable(num),limits_text:arr(str),time_s:arr(num),
  rooms:dict(ref('series')),cells:dict(ref('series')),conditions:dict(ref('timeline')),cell_conditions:dict(ref('timeline')),
  index_by_cell:dict(obj(Object.fromEntries(['FO','FGI','backdraft','rollover'].map(k=>[k,arr(nullable(num))])))),
  index_history_max:dict(obj(Object.fromEntries(['FO','FGI','backdraft','rollover'].map(k=>[k,nullable(num)])))),
  index_history_peak_s:dict(obj(Object.fromEntries(['FO','FGI','backdraft','rollover'].map(k=>[k,nullable(num)])))),
  events:arr(obj({t_s:num,kind:en('ignition','supply_start','window_break','rule_trigger'),room_id:str,
   cell_id:nullable(str),parent_room_id:nullable(str),basis:str})),
  opening_risk:nullable(dict(arr(point(2)))),opening_risk_status:en('evaluated','not_evaluated','not_provided'),
  boundary_rooms:arr(str),boundary_by_cell:dict(arr(nullable(bool))),fallback_sensors:nullable(arr(str)),
  legacy_color:dict(obj({color:arr(str),rollover_band:arr(nullable(bool)),LOC_vol_fraction:nullable(num)})),
  errors:arr(issue),notes:arr(str),source_refs:dict(str),aggregation_policy:str}),
 screening:obj({schema:{const:'pyrocast.screening/1'},building_id:str,floor_id:str,
  stage1:arr(obj({room_id:str,rank:{type:'integer',minimum:1},score:num,factors:dict(obj({raw:nullable(num),norm:nullable(num)}))})),
  top_n:{type:'integer',minimum:1},stage2:arr(obj({room_id:str,rank:nullable({type:'integer',minimum:1}),
   worse_state:en('open','closed',null),burning_rooms:nullable(num),smoke_risk_rooms:nullable(num),
   smoke_caution_rooms:nullable(num),first_FO_s:nullable(num),result_ids:obj({open:nullable(str),closed:nullable(str)}),
   tied_states:arr(str),status:en('complete','partial','failed')})),
  mc:obj({origin_room_id:nullable(str),seed:nullable({type:'integer'}),samples:arr(obj({sample_id:str,
   status:en('complete','partial','failed'),result_id:nullable(str),opening_state:dict(nullable(num))})),aggregate:nullable({type:'object'})}),
  errors:arr(issue),source_revision:nullable(str)})
};
for(const [name,schema] of Object.entries(schemas)){
 schema.$schema='https://json-schema.org/draft/2020-12/schema';
 schema.$id=`https://pyrocast.local/contracts/${name}-1.json`;
 if(name==='result')schema.$defs={series,criterion,conditionFrame:frame,timeline};
 writeFileSync(new URL(`./${name}-1.schema.json`,import.meta.url),JSON.stringify(schema,null,2)+'\n');
}
