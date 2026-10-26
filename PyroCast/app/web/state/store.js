// Pure state transitions. I/O belongs to a future boundary controller.
import {createSeriesCache} from './series_cache.js';
const freeze=x=>{if(x&&typeof x==='object'&&!Object.isFrozen(x)){Object.values(x).forEach(freeze);Object.freeze(x);}return x;};
const snapshot=x=>freeze(structuredClone(x));
const initial=()=>({building:null,result:null,screening:null,
 camera:{mode:'floor',target:null,pose:null},selection:{room_id:null,cell_id:null,source:'list'},floor:{floor_id:null},
 playback:{t_s:0,playing:false,speed:1,t_end_s:0},
 layers:{building:true,openings:true,core:true,smoke:true,flame:true,plume:true,risk:true,selection:true},
 risk:{show:{FO:true,FGI:true,backdraft:true,rollover:true,smoke:true}},
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
    case 'floor/set':if(p.floor_id!==null&&typeof p.floor_id!=='string')throw Error('Invalid floor');put('floor',{floor_id:p.floor_id});return true;
    case 'camera/fit':if(!['floor','all','top','room'].includes(p.mode))throw Error('Invalid camera mode');put('camera',{mode:p.mode,target:p.target??null,pose:p.pose??null});return true;
    case 'selection/set':if(!['list','click','touch'].includes(p.source)||![p.room_id,p.cell_id].every(v=>v===null||typeof v==='string'))throw Error('Invalid selection');put('selection',p);return true;
    case 'layers/toggle':if(!Object.hasOwn(state.layers,p.id))throw Error('Unknown layer');if(p.visible!==undefined&&typeof p.visible!=='boolean')throw Error('Invalid visibility');put('layers',{...state.layers,[p.id]:p.visible??!state.layers[p.id]});return true;
    case 'risk/set':if(!Object.hasOwn(state.risk.show,p.type)||typeof p.visible!=='boolean')throw Error('Invalid risk type');put('risk',{show:{...state.risk.show,[p.type]:p.visible}});return true;
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
