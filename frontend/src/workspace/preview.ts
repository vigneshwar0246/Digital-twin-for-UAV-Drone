import type {Frame} from './types';
import {visualFor,type EngineRegion,type FaultVisual} from './FaultVisualizationController';

export const previews=[
 {code:'NORMAL',name:'Normal Operation',component:'Complete engine',mechanism:'A neutral illustration of the four-stroke cycle.',channels:[],effect:'Smooth, bounded piston and shaft motion.'},
 {code:'LUBRICATION_ISSUE',name:'Lubrication degradation',component:'Oil sump, pump proxy and passages',mechanism:'Low oil quantity, leakage, pump malfunction or a restricted filter or passage can reduce oil pressure. The graphic does not identify a blockage.',channels:['oilPressure','oilTemperature'],effect:'Interrupted oil path and low-pressure warning.'},
 {code:'COOLING_SYSTEM_DEGRADATION',name:'Cooling-system degradation',component:'Cylinder heads and cooling fins',mechanism:'Restricted airflow or ineffective heat rejection can reduce cooling. This is distinct from observed overheating.',channels:['cht1','cht2','cht3','cht4','egt1','egt2','egt3','egt4'],effect:'Thermal waves over the air-cooled heads.'},
 {code:'FUEL_INJECTOR_DEGRADATION',name:'Fuel-injector degradation',component:'Injector nozzle and fuel path',mechanism:'Restricted or uneven fuel delivery can disturb combustion.',channels:['fuelFlow','cht1','cht2','cht3','cht4','egt1','egt2','egt3','egt4'],effect:'Uneven illustrative spray; no internal fuel-flow measurement.'},
 {code:'MISFIRE',name:'Misfire',component:'Combustion chambers',mechanism:'An ignition or mixture problem can cause an intermittent missing combustion event.',channels:['rpm','vibration','egt1','egt2','egt3','egt4'],effect:'Intermittent missing flashes and uneven conceptual cycle.'},
 {code:'ABNORMAL_VIBRATION',name:'Abnormal vibration',component:'Crankshaft and engine body',mechanism:'Rotating imbalance, mounting or other sources can increase vibration; bearing failure is not established.',channels:['vibration'],effect:'Bounded assembly motion and shaft wave rings.'},
 {code:'SENSOR_DRIFT',name:'Sensor drift',component:'Sensor marker and signal path',mechanism:'A biased sensor can report a shifted value while the physical component remains unaffected.',channels:['cht1','cht2','cht3','cht4'],effect:'Offset dashed signal and drift marker.'},
 {code:'SENSOR_FAILURE',name:'Sensor failure or frozen sensor',component:'Sensor marker and signal path',mechanism:'A disconnected, missing or frozen signal can prevent trustworthy measurement.',channels:['cht1','cht2','cht3','cht4'],effect:'Broken signal path and red fault indicator.'},
 {code:'BATTERY_ALTERNATOR_ABNORMALITY',name:'Alternator / electrical degradation',component:'Conceptual alternator and battery connection',mechanism:'Reduced charging output can follow alternator, regulator, wiring or load problems.',channels:['alternator','battery'],effect:'Interrupted electrical flow warning.'},
 {code:'COMBUSTION_INSTABILITY',name:'Combustion instability',component:'Cylinder chambers',mechanism:'Mixture, ignition or airflow variation can make combustion irregular without a total misfire.',channels:['rpm','vibration','egt1','egt2','egt3','egt4'],effect:'Differently timed combustion flashes.'},
 {code:'INJECTION_TIMING_ABNORMALITY',name:'Injection-timing abnormality',component:'Injector and crankshaft timing reference',mechanism:'The conceptual pulse arrives early or late relative to the crank cycle; this is not a verified ECU command.',channels:['timing','rpm'],effect:'Offset pulse beside a fixed timing reference.'},
 {code:'OVERHEATING',name:'Overheating',component:'Cylinder heads and upper body',mechanism:'Excess thermal load or inadequate heat rejection can raise temperature; the root cause is not established.',channels:['cht1','cht2','cht3','cht4','egt1','egt2','egt3','egt4'],effect:'Graded heat tint and thermal waves.'},
] as const;
export type PreviewCode=typeof previews[number]['code'];
export function previewVisual(code:PreviewCode):FaultVisual|null{
 if(code==='NORMAL')return null;
 const item=previews.find(p=>p.code===code)!;
 return visualFor({code,name:item.name,severity:'WARNING',score:null,probability:null,evidence:{},action:'',affectedSubsystems:[],uncertainty:'illustrative',source:'LOCAL_DEMO'});
}
export function observedChannels(frame:Frame|null,keys:readonly string[]){return keys.flatMap(key=>{const s=frame?.signals[key];return s&&s.quality==='VALID'&&s.value!==null?[`${key}: ${s.value} ${s.unit}`]:[];});}
export const previewRegion:Record<Exclude<PreviewCode,'NORMAL'>,EngineRegion>={LUBRICATION_ISSUE:'oil',COOLING_SYSTEM_DEGRADATION:'cooling',FUEL_INJECTOR_DEGRADATION:'fuel',MISFIRE:'combustion',ABNORMAL_VIBRATION:'rotating',SENSOR_DRIFT:'sensors',SENSOR_FAILURE:'sensors',BATTERY_ALTERNATOR_ABNORMALITY:'electrical',COMBUSTION_INSTABILITY:'combustion',INJECTION_TIMING_ABNORMALITY:'timing',OVERHEATING:'heads'};
