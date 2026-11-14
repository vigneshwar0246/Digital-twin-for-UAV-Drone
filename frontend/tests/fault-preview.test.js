import test from 'node:test';
import assert from 'node:assert/strict';
import {build} from 'esbuild';

async function moduleFor(file){
 const result=await build({entryPoints:[file],bundle:true,platform:'node',format:'esm',write:false});
 return import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].contents).toString('base64')}`);
}
const controller=await moduleFor('src/workspace/FaultVisualizationController.ts');
const preview=await moduleFor('src/workspace/preview.ts');
const regions={MISFIRE:'cylinders',FUEL_INJECTOR_DEGRADATION:'fuel',COOLING_SYSTEM_DEGRADATION:'cooling',LUBRICATION_ISSUE:'oil',SENSOR_DRIFT:'sensors',SENSOR_FAILURE:'sensors',COMBUSTION_INSTABILITY:'combustion',OVERHEATING:'heads',ABNORMAL_VIBRATION:'rotating',BATTERY_ALTERNATOR_ABNORMALITY:'electrical',INJECTION_TIMING_ABNORMALITY:'timing'};
const fault=(code,source='BACKEND_DIAGNOSTIC')=>({code,name:code,severity:'WARNING',score:.6,probability:null,evidence:{},action:'',affectedSubsystems:[],uncertainty:'high',source});

test('all backend codes target their conceptual regions',()=>{
 for(const [code,region] of Object.entries(regions))assert.equal(controller.visualFor(fault(code)).regions[0],region,code);
 assert.equal(controller.visualFor(fault('UNKNOWN_CODE')).regions[0],'engine');
});
test('every preview selection is isolated from diagnostic faults',()=>{
 assert.equal(preview.previews.length,12);
 for(const item of preview.previews){
  const visual=preview.previewVisual(item.code);
  if(item.code==='NORMAL'){assert.equal(visual,null);continue;}
  assert.equal(visual.regions[0],regions[item.code]);
  assert.equal(visual.fault.source,'LOCAL_DEMO');
  assert.deepEqual(controller.diagnosticFaults([visual.fault]),[]);
 }
});
test('only valid observed values appear; environment and preview do not become diagnoses',()=>{
 assert.deepEqual(controller.diagnosticFaults([fault('MISFIRE','LOCAL_DEMO')]),[]);
 assert.deepEqual(preview.observedChannels({signals:{oilPressure:{value:null,unit:'kPa',quality:'MISSING'},oilTemperature:{value:95,unit:'°C',quality:'VALID'}}},['oilPressure','oilTemperature']),['oilTemperature: 95 °C']);
 assert.deepEqual(controller.diagnosticFaults([]),[]);
});
