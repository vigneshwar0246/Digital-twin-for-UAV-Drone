import type {Frame} from './types';
import {diagnosticFaults} from './FaultVisualizationController';

export function faultEpisodes(frames:Frame[]){
 const episodes:{code:string;name:string;severity:string;missionId:string;first:string;last:string;samples:number}[]=[];
 const active=new Map<string,(typeof episodes)[number]>();
 for(const frame of frames){
  for(const [code,event] of active)if(event.missionId!==frame.missionId)active.delete(code);
  const present=new Set<string>();
  for(const fault of diagnosticFaults(frame.faults)){
   present.add(fault.code);
   let episode=active.get(fault.code);
   if(!episode){episode={code:fault.code,name:fault.name,severity:fault.severity,missionId:frame.missionId,first:frame.timestamp,last:frame.timestamp,samples:0};episodes.push(episode);active.set(fault.code,episode);}
   episode.last=frame.timestamp;episode.samples++;episode.severity=fault.severity;
  }
  for(const code of active.keys())if(!present.has(code))active.delete(code);
 }
 return episodes;
}

export default function FaultTimeline({frames,current}:{frames:Frame[];current:Frame|null}){
 const episodes=faultEpisodes(frames.filter(frame=>frame.engineId===current?.engineId));
 const active=new Set(diagnosticFaults(current?.faults||[]).map(f=>f.code));
 return <section className="wt-panel wt-fault-timeline"><div className="wt-panel-head"><div><span className="wt-kicker">OBSERVED BACKEND DIAGNOSTICS</span><h3>Faults over time</h3></div><span className="wt-badge">{episodes.length} event{episodes.length===1?'':'s'}</span></div><p>Recent samples in this session. A fault appears only when the backend reported it; earlier events are history, not active diagnoses.</p>{episodes.length?<ol>{episodes.slice().reverse().map((event,i)=><li key={`${event.code}-${event.first}-${i}`}><span className="wt-badge">{active.has(event.code)&&event.missionId===current?.missionId&&event.last===current?.timestamp?'ACTIVE':'PAST'}</span><strong>{event.name}</strong><span>{event.severity} · {event.samples} sample{event.samples===1?'':'s'}</span><time>{new Date(event.first).toLocaleTimeString()} – {new Date(event.last).toLocaleTimeString()}</time></li>)}</ol>:<p>No backend fault events in the recent time series.</p>}</section>;
}
