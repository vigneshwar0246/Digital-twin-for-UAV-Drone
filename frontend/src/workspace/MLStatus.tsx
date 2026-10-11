import {useEffect,useState} from 'react';
import type {Frame} from './types';
import {diagnosticHistory,request} from './api';

type Readiness={status?:string;database?:string;ml_status?:string;diagnostic_mode?:string};

export default function MLStatus({frame}:{frame:Frame|null}){
  const [ready,setReady]=useState<Readiness|null>(null);
  const [history,setHistory]=useState<Frame[]>([]);
  const [error,setError]=useState('');
  useEffect(()=>{let active=true;const refresh=()=>request('/ready').then(data=>{if(active)setReady(data as Readiness);}).catch(()=>{if(active)setReady({status:'unavailable'});});refresh();const timer=setInterval(refresh,10000);return()=>{active=false;clearInterval(timer);};},[]);
  const result=frame?.diagnosticResult;
  const source=String(result?.source||'unavailable');
  const score=typeof result?.score==='number'&&Number.isFinite(result.score)?result.score:null;
  return <section className="wt-panel wt-controls">
    <span className="wt-kicker">DIAGNOSTIC SOURCE</span><h3>{source==='ml_research'?'Research ML prediction':source==='engineering_rules'?'Engineering diagnosis':'Diagnosis unavailable'}</h3>
    <p>{result?.fault_class?`Fault class: ${String(result.fault_class)}.`:'Waiting for valid telemetry.'} {score!==null?`${String(result?.score_kind||'Score')}: ${score.toFixed(3)}.`:''}</p>
    <p>{result?.model_version?`Model ${String(result.model_version)}. `:''}{String(result?.warning||'No diagnostic result yet.')}</p>
    <p>Sensor quality: {String(result?.sensor_quality||'unknown')}. Backend: {ready?.status||'checking'}; database: {ready?.database||'checking'}; ML: {ready?.ml_status||'checking'}.</p>
    <button disabled={!frame} onClick={async()=>{if(!frame)return;setError('');try{setHistory(await diagnosticHistory(frame.engineId));}catch(e){setError((e as Error).message);}}}>Load saved diagnostic history</button>
    {error&&<p role="alert">{error}</p>}
    {history.length===0?<p>No saved history loaded.</p>:<ul>{history.slice(-10).reverse().map((item,index)=><li key={`${item.timestamp}-${index}`}>{new Date(item.timestamp).toLocaleString()} · {String(item.diagnosticResult?.fault_class||'Unavailable')} · {String(item.diagnosticResult?.source||'unknown')}</li>)}</ul>}
  </section>;
}
