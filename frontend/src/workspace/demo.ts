import type {Controls,Frame} from './types';
import {PARAMETERS,DEMO_LIMITS} from './config';
// UI demonstration relationships only. No aircraft performance or diagnostic validation.
export function demoFrame(t:number,c:Controls,epoch:number):Frame{
 const oscillation=(x:number)=>Math.sin(t*x+c.seed*.01);const fault=Math.min(1,t/20);const is=(s:string)=>c.scenario===s?fault:0;
 const throttle=c.scenario==='Rapid Throttle'?50+30*Math.sin(t*.14):c.throttle;
 const altitude=c.scenario==='High Altitude'?6000:c.altitude;const ambient=c.scenario==='Hot Weather'?45:c.temperature;
 const rpm=800+throttle*30+oscillation(.7)*12-is('Misfire')*200;
 const baseCHT=95+c.load*.75+ambient*.35+Math.min(t/30,1)*10;
 const values:Record<string,number>={rpm,oilPressure:300+throttle*1.5-is('Oil Pressure Drop')*250,oilTemperature:60+c.load*.5+ambient*.3,fuelFlow:5+throttle*.38+is('Injector Degradation')*7,vibration:1+rpm/2200+oscillation(.9)*.1+is('Abnormal Vibration')*6+is('Misfire')*3,battery:27.5-is('Alternator Degradation')*3,alternator:28.2-is('Alternator Degradation')*6,timing:17+throttle*.04,load:c.load,throttle,altitude,ambient};
 for(let i=1;i<=4;i++){values[`cht${i}`]=baseCHT+i+oscillation(.12+i*.02)+is('Cylinder Overheating')*80+(i===3?is('Injector Degradation')*30+is('Sensor Drift')*45:0);values[`egt${i}`]=420+throttle*4+i*3+oscillation(.21)*3+(i===3?is('Injector Degradation')*140-is('Misfire')*180:0);}
 const signals:Frame['signals']={};for(const [key,[,unit]] of Object.entries(PARAMETERS))signals[key]={value:values[key]??null,unit,quality:values[key]===undefined?'MISSING':'VALID'};
 const thermal=Math.max(0,100-Math.max(0,values.cht3-DEMO_LIMITS.cht)*1.2),lubrication=Math.max(0,100-Math.max(0,DEMO_LIMITS.oilPressure-values.oilPressure)*.4),vibration=Math.max(0,100-Math.max(0,values.vibration-DEMO_LIMITS.vibration)*15),electrical=Math.max(0,100-Math.max(0,DEMO_LIMITS.alternator-values.alternator)*15);
 const subsystems={Cooling:thermal,Lubrication:lubrication,Combustion:100-is('Misfire')*40,Fuel:100-is('Injector Degradation')*35,Vibration:vibration,Electrical:electrical,Sensors:100-is('Sensor Drift')*25};const health=Math.min(...Object.values(subsystems));
 const active=!['Normal Operation','High Altitude','Hot Weather','Rapid Throttle'].includes(c.scenario)&&t>8;
 return {timestamp:new Date(epoch+t*1000).toISOString(),engineId:'DEMO-ENGINE-01',missionId:`DEMO-${epoch}`,phase:t<15?'START':'CRUISE',source:'DEMO SIMULATION',signals,health,rul:null,anomaly:active?fault*.8:.03,faults:active?[{code:c.scenario.replaceAll(' ','_'),name:c.scenario,severity:health<65?'warning':'advisory',score:fault*.8,probability:null,evidence:{scenario:c.scenario,provenance:'Scripted test scenario; not a backend diagnostic or ML prediction',cht3:values.cht3,vibration:values.vibration},action:`Review ${c.scenario.toLowerCase()} evidence in this software demonstration.`,affectedSubsystems:[],uncertainty:'high',source:'LOCAL_DEMO'}]:[],subsystems,advisory:active?'Review the injected scenario and associated signals.':'No scripted fault injected.',synchronized:true};
}
