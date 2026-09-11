import { STATES } from '../state/experienceState';
export default function AircraftHUD({state,selected}){
 const engine=state===STATES.HERO||state===STATES.ZOOM;
 return <><div className="object-caption"><span className="orange-dot"/><span>{engine?'PROPULSION ASSEMBLY':'MALE · UNMANNED AIRCRAFT'}</span><span className="caption-rule"/><span>{engine?'04 / CYLINDERS':'01 / AIRFRAME'}</span></div><div className="telemetry-note"><span className="cross">+</span><span>{engine?'INTERNAL GEOMETRY':'AIRFRAME EXPLORATION'}<small>{selected?'DIGITAL TWIN INITIALIZED':'SCROLL-CONTROLLED VIEW'}</small></span></div></>;
}
