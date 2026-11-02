// Pure state transitions. I/O belongs to a future boundary controller.
import {createSeriesCache} from './series_cache.js';
const freeze=x=>{if(x&&typeof x==='object'&&!Object.isFrozen(x)){Object.values(x).forEach(freeze);Object.freeze(x);}return x;};
const snapshot=x=>freeze(structuredClone(x));
const initial=()=>({buildingReview:{doors:null,openings:null,rooms:[],saving:false,status:""},building:null,result:null,screening:null,exploration:{top_n:8,origin_room_id:null,origin_mode:'ranked',samples:10},
 camera:{mode:'floor',target:null,pose:null},selection:{room_id:null,cell_id:null,source:'list'},floor:{floor_id:null},
 playback:{t_s:0,playing:false,speed:1,t_end_s:0},
 realView:{enabled:true,smokeOpacity:1,temperatureSmoke:true,temperaturePattern:'current',smokeColor:'current',flameDisplay:'growth',fuelMarkers:true},
 openings:{exterior:true,interior:true},
 layers:{building:true,openings:true,core:true,smoke:true,flame:true,plume:true,risk:true,selection:true,operations:false},
 risk:{history:true,show:{FO:true,FGI:true,backdraft:true,rollover:true,smoke:true},threshold:{ribbon:100,caution:70}},
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
    case 'buildingReview/set':if(Object.keys(p).some(k=>!Object.hasOwn(state.buildingReview,k)))throw Error('Invalid building review');put('buildingReview',{...state.buildingReview,...p});return true;
    case 'exploration/set':{
     if(Object.keys(p).some(k=>!Object.hasOwn(state.exploration,k)))throw Error('Unknown exploration setting');
     if(p.origin_mode!==undefined&&!['ranked','manual'].includes(p.origin_mode))throw Error('Invalid origin mode');
     for(const k of ['top_n','samples'])if(p[k]!==undefined&&(!Number.isSafeInteger(p[k])||p[k]<1))throw Error('Positive integer required');
     if(p.origin_room_id!==undefined&&p.origin_room_id!==null&&typeof p.origin_room_id!=='string')throw Error('Invalid origin');
     put('exploration',{...state.exploration,...p});return true;
    }
    case 'floor/set':if(p.floor_id!==null&&typeof p.floor_id!=='string')throw Error('Invalid floor');put('floor',{floor_id:p.floor_id});return true;
    case 'camera/fit':if(!['floor','all','top','room','fire'].includes(p.mode))throw Error('Invalid camera mode');put('camera',{mode:p.mode,target:p.target??null,pose:p.pose??null});return true;
    case 'openings/set':if(Object.keys(p).some(k=>!Object.hasOwn(state.openings,k)||typeof p[k]!=='boolean'))throw Error('Invalid opening display');put('openings',{...state.openings,...p});return true;
    case 'selection/set':if(!['list','click','touch'].includes(p.source)||![p.room_id,p.cell_id].every(v=>v===null||typeof v==='string'))throw Error('Invalid selection');put('selection',p);return true;
    case 'layers/toggle':if(!Object.hasOwn(state.layers,p.id))throw Error('Unknown layer');if(p.visible!==undefined&&typeof p.visible!=='boolean')throw Error('Invalid visibility');put('layers',{...state.layers,[p.id]:p.visible??!state.layers[p.id]});return true;
    case 'realView/set':
     if(Object.keys(p).some(k=>!Object.hasOwn(state.realView,k)))throw Error('Unknown real-view setting');
     for(const k of ['enabled','temperatureSmoke','fuelMarkers'])if(p[k]!==undefined&&typeof p[k]!=='boolean')throw Error('Invalid real-view flag');
     if(p.smokeOpacity!==undefined&&(!Number.isFinite(p.smokeOpacity)||p.smokeOpacity<0||p.smokeOpacity>1))throw Error('Invalid smoke opacity');
     if(p.temperaturePattern!==undefined&&!['current','weak','off'].includes(p.temperaturePattern))throw Error('Invalid temperature pattern');
     if(p.smokeColor!==undefined&&!['current','neutral'].includes(p.smokeColor))throw Error('Invalid smoke color');
     if(p.flameDisplay!==undefined&&!['growth','hrr'].includes(p.flameDisplay))throw Error('Invalid flame display');
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
