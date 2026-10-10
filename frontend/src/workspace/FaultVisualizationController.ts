import type {Fault} from './types';

export type EngineRegion='engine'|'cylinders'|'heads'|'cooling'|'oil'|'fuel'|'combustion'|'electrical'|'sensors'|'rotating'|'timing';
export interface FaultVisual {fault:Fault;regions:EngineRegion[];label:string;color:string;intensity:number;irregular:boolean;vibration:number}

const mappings:Record<string,{regions:EngineRegion[];label:string;irregular?:boolean;vibration?:boolean}>={
 MISFIRE:{regions:['cylinders','combustion'],label:'MISFIRE',irregular:true},
 FUEL_INJECTOR_DEGRADATION:{regions:['fuel'],label:'FUEL INJECTOR'},
 COOLING_SYSTEM_DEGRADATION:{regions:['cooling','heads'],label:'COOLING SYSTEM'},
 LUBRICATION_ISSUE:{regions:['oil'],label:'LUBRICATION'},
 SENSOR_DRIFT:{regions:['sensors'],label:'SENSOR DRIFT'},
 SENSOR_FAILURE:{regions:['sensors'],label:'SENSOR FAILURE'},
 COMBUSTION_INSTABILITY:{regions:['combustion','cylinders'],label:'COMBUSTION INSTABILITY',irregular:true},
 OVERHEATING:{regions:['heads','cooling','engine'],label:'OVERHEATING',irregular:true},
 ABNORMAL_VIBRATION:{regions:['rotating','engine'],label:'ABNORMAL VIBRATION',vibration:true},
 BATTERY_ALTERNATOR_ABNORMALITY:{regions:['electrical'],label:'ELECTRICAL SYSTEM',irregular:true},
 INJECTION_TIMING_ABNORMALITY:{regions:['timing','fuel'],label:'INJECTION TIMING',irregular:true},
};
const severityWeight:Record<string,number>={LOW:.35,ADVISORY:.35,MEDIUM:.58,WARNING:.68,HIGH:.82,CRITICAL:1};
const aliases:Record<string,string>={'FUEL INJECTOR DEGRADATION':'FUEL_INJECTOR_DEGRADATION','COOLING SYSTEM DEGRADATION':'COOLING_SYSTEM_DEGRADATION','LUBRICATION ISSUE':'LUBRICATION_ISSUE','SENSOR DRIFT':'SENSOR_DRIFT','SENSOR FAILURE':'SENSOR_FAILURE','COMBUSTION INSTABILITY':'COMBUSTION_INSTABILITY','ABNORMAL VIBRATION':'ABNORMAL_VIBRATION','BATTERY/ALTERNATOR ABNORMALITY':'BATTERY_ALTERNATOR_ABNORMALITY','INJECTION TIMING ABNORMALITY':'INJECTION_TIMING_ABNORMALITY'};
export function diagnosticFaults(faults:Fault[]){return faults.filter(f=>f.source==='BACKEND_DIAGNOSTIC');}
export function visualFor(fault:Fault):FaultVisual{
 const normalized=fault.code.toUpperCase().replaceAll(' ','_');const key=mappings[normalized]?normalized:(aliases[fault.name.toUpperCase()]||normalized);const map=mappings[key]||{regions:['engine'] as EngineRegion[],label:fault.name.toUpperCase()};
 const severity=severityWeight[fault.severity.toUpperCase()]??.5;const intensity=Math.min(1,Math.max(severity,(fault.score??0)*.85));const color=intensity>=.9?'#e11d28':intensity>=.65?'#ff5a1f':'#f5a623';
 return {fault,regions:map.regions,label:map.label,color,intensity,irregular:Boolean(map.irregular),vibration:map.vibration ? 1.8*intensity : 0};
}
export function cylinderFromEvidence(fault:Fault):number|null{
 // Only explicit localization metadata identifies a cylinder. A measurement name
 // appearing in evidence does not prove that cylinder caused the diagnosis.
 const e=fault.evidence,rule=typeof e.rule_evidence==='object'&&e.rule_evidence!==null?e.rule_evidence as Record<string,unknown>:{};
 const id=e.affected_cylinder??e.cylinder_id??rule.affected_cylinder??rule.cylinder_id;
 return typeof id==='number'&&Number.isInteger(id)&&id>=1&&id<=4?id:null;
}
export const regionFocus:Record<EngineRegion,{zoom:number;x:number;y:number}>={engine:{zoom:1.18,x:0,y:0},cylinders:{zoom:1.35,x:0,y:0},heads:{zoom:1.4,x:0,y:-20},cooling:{zoom:1.4,x:0,y:-25},oil:{zoom:1.5,x:15,y:-55},fuel:{zoom:1.55,x:0,y:45},combustion:{zoom:1.42,x:0,y:0},electrical:{zoom:1.65,x:-120,y:45},sensors:{zoom:1.5,x:70,y:0},rotating:{zoom:1.65,x:0,y:0},timing:{zoom:1.6,x:20,y:45}};
