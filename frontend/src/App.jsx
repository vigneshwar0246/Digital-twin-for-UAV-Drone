import { lazy, Suspense, useCallback, useRef, useState, useEffect } from 'react';
import gsap from 'gsap';
import { createMotion, resolveState, canSelect, STATES } from './state/experienceState';
import { useScrollController } from './animation/scrollController';
import AircraftHUD from './components/AircraftHUD';
import SelectionPrompt from './components/SelectionPrompt';
const UAVScene=lazy(()=>import('./components/UAVScene'));
export default function App(){
 const track=useRef();const motion=useRef(createMotion()).current;
 const [selected,setSelected]=useState(false),[state,setState]=useState(STATES.INTRO);
 const publish=useCallback(()=>{setState(resolveState(motion.flight,motion.zoom,motion.selected));track.current?.style.setProperty('--progress',motion.selected?0.5+motion.zoom*0.5:motion.flight*0.5);},[motion]);
 useScrollController(track,motion,selected,publish);
 const select=useCallback(()=>{if(!canSelect(motion.flight,motion.selected))return;motion.selected=true;motion.pulse=1;gsap.to(motion,{pulse:0,duration:1.2});setSelected(true);publish();},[motion,publish]);
 useEffect(()=>{const onKey=e=>{if(e.key==='Enter'&&e.target===document.body)select();};window.addEventListener('keydown',onKey);return ()=>window.removeEventListener('keydown',onKey);},[select]);
 const engine=state===STATES.ZOOM||state===STATES.HERO;
 return <main ref={track} className={`experience ${selected?'is-selected':''} ${engine?'is-engine':''}`} data-state={state} style={{height:selected?'630svh':'380svh'}}>
 <div className="stage">
 <header><a className="brand" href="#" aria-label="Aerion home" onClick={e=>{e.preventDefault();window.location.reload();}}><span className="brand-mark">Λ</span>AERION<span className="brand-divider"/><span className="brand-sub">DIGITAL TWIN</span></a><div className="header-right"><span className="edition">ENGINEERING EXPERIENCE / 001</span><span className="status-dot"/>INTERACTIVE EXPLORATION</div></header>
 <div className="atmosphere atmosphere-one"/><div className="atmosphere atmosphere-two"/>
 <div className="hero-copy"><div className="eyebrow"><span/>BEYOND THE AIRFRAME</div><h1>{engine?<>Every detail.<br/><em>Connected.</em></>:<>Engineering,<br/><em>revealed.</em></>}</h1><p>{engine?'A closer look at the heart of the aircraft.':'From the freedom of flight to the precision within.'}<br/>{engine?'The foundation for a living digital twin.':'Explore an aircraft. Discover its digital twin.'}</p></div>
 <div className="scene"><Suspense fallback={<div className="loading">PREPARING THE AIRFRAME <span>…</span></div>}><UAVScene motion={motion} onSelect={select}/></Suspense></div>
 <div className="technical-scale" aria-hidden="true"><span>90</span><i/><i/><i/><span>60</span><i/><i/><i/><span>30</span><i/><i/><i/><span>00</span></div>
 <AircraftHUD state={state} selected={selected}/><SelectionPrompt state={state} onSelect={select}/>
 {state===STATES.HERO&&<button className="engine-enter" type="button" onClick={()=>window.dispatchEvent(new CustomEvent('aerion:enter'))}><span>ENTER</span><i aria-hidden="true">→</i></button>}
 <footer><div className="scroll-cue"><span className="scroll-icon">↓</span><div>{state===STATES.SETTLED?'SELECT TO CONTINUE':state===STATES.HERO?'SCROLL UP TO RETURN':'SCROLL TO EXPLORE'}<small>{state===STATES.SETTLED?'Your next perspective awaits.':'A different perspective, with every scroll.'}</small></div></div><div className="chapter-track"><span className={!engine?'active':''}>01 <b>AIRCRAFT</b></span><div className="progress-line"><i/></div><span className={engine?'active':''}>02 <b>ENGINE</b></span></div><div className="prototype-note">CONCEPT GEOMETRY<span>INTERACTIVE 3D STUDY</span></div></footer>
 <div className="sr-only" role="status" aria-live="polite">{state.replaceAll('_',' ')}</div>
 </div></main>;
}
