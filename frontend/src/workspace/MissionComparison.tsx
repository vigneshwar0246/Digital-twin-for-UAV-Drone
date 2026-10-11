import {useState} from 'react';
import {request} from './api';
import {DataView} from './Panels';

export default function MissionComparison(){
 const [first,setFirst]=useState('');
 const [second,setSecond]=useState('');
 const [result,setResult]=useState<unknown>(null);
 const [error,setError]=useState('');
 const [busy,setBusy]=useState(false);
 const compare=async()=>{
  setBusy(true);setError('');setResult(null);
  try{setResult(await request('/missions/compare',{first_mission_id:first.trim(),second_mission_id:second.trim()}));}
  catch(e){setError((e as Error).message);}
  finally{setBusy(false);}
 };
 return <section className="wt-panel wt-controls">
  <span className="wt-kicker">RECORDED MISSION COMPARISON</span><h3>Compare two missions</h3>
  <p>Enter two saved simulation or historical dataset mission IDs. Both are re-analyzed with current prototype rules; differences do not establish cause.</p>
  <div className="wt-control-grid">
   <label>First mission ID<input value={first} maxLength={64} onChange={e=>setFirst(e.target.value)}/></label>
   <label>Second mission ID<input value={second} maxLength={64} onChange={e=>setSecond(e.target.value)}/></label>
  </div>
  <button className="wt-primary" disabled={busy||!first.trim()||!second.trim()||first.trim()===second.trim()} onClick={compare}>{busy?'Comparing…':'Compare missions'}</button>
  {error&&<p role="alert">{error}</p>}
  {result!==null&&<DataView data={result}/>}
 </section>;
}
