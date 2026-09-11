import { STATES } from '../state/experienceState';
export default function SelectionPrompt({state,onSelect}){
 if(state===STATES.SETTLED)return <button className="selection-prompt" onClick={onSelect}><span className="target-symbol">⌖</span><span>INITIALIZE DIGITAL TWIN<small>SELECT THE AIRCRAFT · OR PRESS ENTER</small></span><span>↗</span></button>;
 if(state===STATES.SELECTED)return <div className="selection-prompt initialized"><span className="orange-dot"/><span>DIGITAL TWIN INITIALIZED<small>SCROLL TO EXPLORE THE ENGINE</small></span><span>↓</span></div>;
 return null;
}
