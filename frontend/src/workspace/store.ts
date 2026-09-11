import {useSyncExternalStore} from 'react';
import type {Snapshot,Frame,Mode,Controls} from './types';
import {DEFAULT_CONTROLS} from './config';
import {demoFrame} from './demo';
import {latest,stream} from './api';
let state:Snapshot={mode:'SIMULATION',frame:null,history:[],recording:[],playing:true,speed:1,seconds:0,cursor:0,controls:DEFAULT_CONTROLS,status:'DEMO SIMULATION',error:'',engineId:'SIM_ENGINE_001',connected:false};
const listeners=new Set<()=>void>();let epoch=Date.now(),frames:Frame[]=[],lastWall=0;let stopTransport:(()=>void)|undefined;
export const getSnapshot=()=>state;
export function set(p:Partial<Snapshot>){state={...state,...p};listeners.forEach(f=>f());}
export function useTwin(){return useSyncExternalStore(f=>{listeners.add(f);return()=>{listeners.delete(f);};},getSnapshot);}
function accept(frame:Frame){set({frame,history:[...state.history,frame].slice(-240),recording:state.mode==='SIMULATION'?[...state.recording,frame].slice(-14400):state.recording});}
export function configure(p:Partial<Controls>){set({controls:{...state.controls,...p}});}
export function reset(){epoch=Date.now();frames=[];set({frame:null,history:[],recording:[],seconds:0,cursor:0,playing:false,error:''});}
export function installFrames(next:Frame[],mode:Mode){if(!next.length)throw new Error('Mission contains no samples');frames=next.slice(0,14400);set({mode,frame:frames[0],history:[frames[0]],recording:mode==='SIMULATION'?frames:state.recording,cursor:0,seconds:0,playing:false,error:'',status:frames[0].source});}
export function seek(index:number){if(!frames.length)return;const cursor=Math.max(0,Math.min(frames.length-1,Math.round(index)));set({cursor,frame:frames[cursor],history:frames.slice(Math.max(0,cursor-239),cursor+1),seconds:(Date.parse(frames[cursor].timestamp)-Date.parse(frames[0].timestamp))/1000});}
export const frameCount=()=>frames.length;
export function switchMode(mode:Mode){stopTransport?.();stopTransport=undefined;frames=[];set({mode,frame:null,history:[],seconds:0,cursor:0,playing:mode==='SIMULATION',error:'',status:mode==='REAL'?'WAITING FOR TELEMETRY':mode,connected:false});epoch=Date.now();}
export function startStore(){lastWall=performance.now();let stopped=false,busy=false,attempt=0,nextPoll=0;const controller=new AbortController();
 const interval=setInterval(async()=>{const now=performance.now(),dt=Math.min((now-lastWall)/1000,2);lastWall=now;
 if(state.mode==='REAL'){
  const url=import.meta.env.VITE_WS_URL;if(url){if(!stopTransport)stopTransport=stream(url,f=>{if(!stopped&&state.mode==='REAL'){accept(f);set({status:f.source,connected:true,error:''});}},status=>set({status,connected:false}));}
  else if(!busy&&now>=nextPoll){busy=true;const id=state.engineId;try{const f=await latest(id,controller.signal);if(!stopped&&state.mode==='REAL'&&state.engineId===id){if(!state.frame||Date.parse(f.timestamp)>Date.parse(state.frame.timestamp))accept(f);set({connected:true,error:'',status:f.source});attempt=0;}}catch(e){if(!stopped&&state.mode==='REAL')set({connected:false,error:(e as Error).message,status:'BACKEND UNAVAILABLE'});attempt++;}finally{busy=false;nextPoll=performance.now()+Math.min(30000,1000*2**attempt);}}
  if(state.frame&&Date.now()-Date.parse(state.frame.timestamp)>10000&&state.status!=='STALE')set({status:'STALE',frame:{...state.frame,synchronized:false,signals:Object.fromEntries(Object.entries(state.frame.signals).map(([k,v])=>[k,{...v,quality:v.quality==='VALID'?'STALE':v.quality}]))}});return;
 }
 if(!state.playing)return;
 const seconds=state.seconds+dt*state.speed;
 if(frames.length){const target=Date.parse(frames[0].timestamp)+seconds*1000;let cursor=state.cursor;while(cursor<frames.length-1&&Date.parse(frames[cursor+1].timestamp)<=target)cursor++;seek(cursor);set({seconds,playing:cursor<frames.length-1});}
 else if(state.mode==='SIMULATION'){set({seconds,playing:seconds<state.controls.duration});accept(demoFrame(seconds,state.controls,epoch));}
 },250);
 return()=>{stopped=true;controller.abort();clearInterval(interval);stopTransport?.();stopTransport=undefined;};}
