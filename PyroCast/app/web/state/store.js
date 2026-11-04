// Pure state transitions. I/O belongs to a future boundary controller.
import {createSeriesCache} from './series_cache.js';
const freeze=x=>{if(x&&typeof x==='object'&&!Object.isFrozen(x)){Object.values(x).forEach(freeze);Object.freeze(x);}return x;};
const snapshot=x=>freeze(structuredClone(x));
const initial=()=>({fuelSettings:{data:null,draft:{},saving:false,message:''},buildingReview:{doors:null,openings:null,rooms:[],saving:false,status:""},building:null,result:null,screening:null,exploration:{top_n:8,origin_room_id:null,origin_mode:'ranked',samples:10},
 route:{vehicle:null,placing:false,vehicle_visible:true,hose_m:15,stair_factor:1.5,message:''},
 camera:{mode:'floor',target:null,pose:null},selection:{room_id:null,cell_id:null,source:'list'},floor:{floor_id:null},
 playback:{t_s:0,playing:false,speed:1,t_end_s:0},
 realView:{enabled:true,buildingTransparency:.7,smokeOpacity:.7,smokeGain:1,flameGain:1,temperatureSmoke:true,temperaturePattern:'weak',smokeColor:'current',smokeMode:'current',flameStyle:'current',flameDisplay:'hrr',fuelMarkers:false},
 openings:{exterior:true,interior:true,fixed:true},
 displayDetails:{cellOutline:false,floorTint:false,smokeInterface:false,boundaryDots:false},
 layers:{roomNames:true,building:true,openings:true,core:true,smoke:true,flame:true,plume:false,risk:true,selection:true,route:true},
 risk:{history:false,show:{FO:true,FGI:true,backdraft:true,smoke:false},threshold:{ribbon:100,caution:70}},
 jobs:{active:null,queue:[],lastError:null},request:{seq:0}});
function finite(x){if(!Number.isFinite(x))throw Error('Finite number required');return x;}
export function createStore({validators={},seriesCache=createSeriesCache()}={}){
 let state=freeze(initial());const listeners=new Map(Object.keys(state).map(k=>[k,new Set()]));
 const put=(slice,value)=>{state=freeze({...state,[slice]:snapshot(value)});for(const fn of [...listeners.get(slice)])fn(state[slice]);};
 const validate=(kind,value)=>{const fn=validators[kind];if(!fn||!fn(value))throw Error(`Invalid or unvalidated ${kind} contract`);};
 const api={
  get(slice){if(!listeners.has(slice))throw Error('Unknown slice: '+slice);return state[slice];},
  subscribe(slice,fn){if(!listeners.has(slice)||typeof fn!=='function')throw Error('Invalid subscription');listeners.get(slice).add(fn);return ()=>listeners.get(slice).delete(fn);},
  dispatch(action,p={}){
   switch(action){
    case 'fuelSettings/set':if(Object.keys(p).some(k=>!Object.hasOwn(state.fuelSettings,k)))throw Error('Invalid fuel settings');put('fuelSettings',{...state.fuelSettings,...p});return true;
    case 'buildingReview/set':if(Object.keys(p).some(k=>!Object.hasOwn(state.buildingReview,k)))throw Error('Invalid building review');put('buildingReview',{...state.buildingReview,...p});return true;
    case 'exploration/set':{
     if(Object.keys(p).some(k=>!Object.hasOwn(state.exploration,k)))throw Error('Unknown exploration setting');
     if(p.origin_mode!==undefined&&!['ranked','manual'].includes(p.origin_mode))throw Error('Invalid origin mode');
     for(const k of ['top_n','samples'])if(p[k]!==undefined&&(!Number.isSafeInteger(p[k])||p[k]<1))throw Error('Positive integer required');
     if(p.origin_room_id!==undefined&&p.origin_room_id!==null&&typeof p.origin_room_id!=='string')throw Error('Invalid origin');
     put('exploration',{...state.exploration,...p});return true;
    }
    case 'route/set':{
     if(Object.keys(p).some(k=>!Object.hasOwn(state.route,k)))throw Error('Unknown route setting');
     for(const k of ['hose_m','stair_factor'])if(p[k]!==undefined&&(!Number.isFinite(p[k])||p[k]<1))throw Error('호스 길이·계단 계수는 1 이상이어야 합니다');
     if(p.vehicle!==undefined&&p.vehicle!==null&&(!Array.isArray(p.vehicle)||p.vehicle.length!==3||!p.vehicle.every(Number.isFinite)))throw Error('Invalid vehicle point');
     for(const k of ['placing','vehicle_visible'])if(p[k]!==undefined&&typeof p[k]!=='boolean')throw Error('Invalid route flag');
     put('route',{...state.route,...p});return true;
    }
    case 'floor/set':if(p.floor_id!==null&&typeof p.floor_id!=='string')throw Error('Invalid floor');put('floor',{floor_id:p.floor_id});return true;
    case 'camera/fit':if(!['floor','all','top','room','fire'].includes(p.mode))throw Error('Invalid camera mode');put('camera',{mode:p.mode,target:p.target??null,pose:p.pose??null});return true;
    case 'openings/set':if(Object.keys(p).some(k=>!Object.hasOwn(state.openings,k)||typeof p[k]!=='boolean'))throw Error('Invalid opening display');put('openings',{...state.openings,...p});return true;
    case 'displayDetails/set':if(Object.keys(p).some(k=>!Object.hasOwn(state.displayDetails,k)||typeof p[k]!=='boolean'))throw Error('Invalid display detail');put('displayDetails',{...state.displayDetails,...p});return true;
    case 'selection/set':if(!['list','click','touch'].includes(p.source)||![p.room_id,p.cell_id].every(v=>v===null||typeof v==='string'))throw Error('Invalid selection');put('selection',p);return true;
    case 'layers/toggle':if(!Object.hasOwn(state.layers,p.id))throw Error('Unknown layer');if(p.visible!==undefined&&typeof p.visible!=='boolean')throw Error('Invalid visibility');put('layers',{...state.layers,[p.id]:p.visible??!state.layers[p.id]});return true;
    case 'realView/set':
     if(Object.keys(p).some(k=>!Object.hasOwn(state.realView,k)))throw Error('Unknown real-view setting');
     if(p.buildingTransparency!==undefined&&(!Number.isFinite(p.buildingTransparency)||p.buildingTransparency<0||p.buildingTransparency>1))throw Error('Invalid building transparency');
     for(const k of ['enabled','temperatureSmoke','fuelMarkers'])if(p[k]!==undefined&&typeof p[k]!=='boolean')throw Error('Invalid real-view flag');
     if(p.smokeOpacity!==undefined&&(!Number.isFinite(p.smokeOpacity)||p.smokeOpacity<0||p.smokeOpacity>1))throw Error('Invalid smoke opacity');
      for(const [key,min,max] of [['smokeGain',.3,1.5],['flameGain',.5,2]])if(p[key]!==undefined&&(!Number.isFinite(p[key])||p[key]<min||p[key]>max))throw Error('Invalid display gain');
     if(p.temperaturePattern!==undefined&&!['current','weak','off'].includes(p.temperaturePattern))throw Error('Invalid temperature pattern');
     if(p.smokeColor!==undefined&&p.smokeColor!=='current')throw Error('Invalid smoke color');
     if(p.smokeMode!==undefined&&!['current','soot'].includes(p.smokeMode))throw Error('Invalid smoke mode');
     if(p.flameStyle!==undefined&&!['current','four_stage'].includes(p.flameStyle))throw Error('Invalid flame style');
     if(p.flameDisplay!==undefined&&p.flameDisplay!=='hrr')throw Error('Invalid flame display');
     put('realView',{...state.realView,...p});return true;
    case 'risk/set':if(!Object.hasOwn(state.risk.show,p.type)||typeof p.visible!=='boolean')throw Error('Invalid risk type');put('risk',{...state.risk,show:{...state.risk.show,[p.type]:p.visible}});return true;
    case 'risk/history':if(typeof p.enabled!=='boolean')throw Error('Invalid history flag');put('risk',{...state.risk,history:p.enabled});return true;
    case 'risk/threshold':{
     const threshold={...state.risk.threshold,...p};
     if(Object.keys(p).some(k=>!['ribbon','caution'].includes(k))||Object.values(threshold).some(v=>!Number.isFinite(v)||v<0)||threshold.caution>threshold.ribbon)throw Error('Invalid risk thresholds');
     put('risk',{...state.risk,threshold});return true;
    }
    case 'playback/seek':put('playback',{...state.playback,t_s:Math.max(0,Math.min(state.playback.t_end_s,finite(p.t_s)))});return true;
    case 'playback/play':if(typeof p.playing!=='boolean')throw Error('Invalid play state');put('playback',{...state.playback,playing:p.playing});return true;
    case 'playback/speed':if(![1,5,10,20,30,60].includes(p.speed))throw Error('Invalid playback speed');put('playback',{...state.playback,speed:p.speed});return true;
    case 'building/set':validate('building',p);put('building',p);return true;
    case 'screening/set':validate('screening',p);put('screening',p);return true;
    case 'result/load':put('request',{seq:state.request.seq+1});return state.request.seq;
    case 'result/receive':
     if(p.seq!==state.request.seq||p.seq===0)return false;
     validate('result',p.result);
     {const {rooms,cells,...meta}=p.result;seriesCache.replace(p.result.result_id,{rooms:rooms??{},cells:cells??{}});put('result',meta);}
     put('playback',{...state.playback,t_s:0,playing:false,t_end_s:p.result.t_end_s??0});return true;
    case 'jobs/start':if(state.jobs.active!==null)return false;if(typeof p.id!=='string')throw Error('Job ID required');put('jobs',{...state.jobs,active:p,lastError:null});return true;
    case 'jobs/finish':case 'jobs/fail':if(state.jobs.active?.id!==p.id)return false;put('jobs',{...state.jobs,active:null,lastError:action==='jobs/fail'?String(p.error):null});return true;
    default:throw Error('Unknown action: '+action);
   }
  },
  diagnostics(){return {subscriptions:[...listeners.values()].reduce((n,s)=>n+s.size,0)};}
 };return Object.freeze(api);
}
export const seriesCache=createSeriesCache();
export const store=createStore({seriesCache});
// A legacy sender gets only this capability, never a store reader.
export const legacyDispatchBridge=store=>Object.freeze({dispatch:(action,payload)=>store.dispatch(action,payload)});
