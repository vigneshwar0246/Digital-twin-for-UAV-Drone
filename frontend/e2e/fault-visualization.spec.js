import {test,expect} from '@playwright/test';
const codes=['MISFIRE','FUEL_INJECTOR_DEGRADATION','COOLING_SYSTEM_DEGRADATION','LUBRICATION_ISSUE','SENSOR_DRIFT','SENSOR_FAILURE','COMBUSTION_INSTABILITY','OVERHEATING','ABNORMAL_VIBRATION','BATTERY_ALTERNATOR_ABNORMALITY','INJECTION_TIMING_ABNORMALITY'];
const diagnostic=code=>({fault_code:code,fault_name:code.replaceAll('_',' '),severity:'CRITICAL',engineering_score:.91,probability:null,affected_subsystems:['THERMAL_HEALTH'],uncertainty:'high',evidence:{rule_evidence:{cht_mean_c:245},statistical_evidence:[]},recommended_action:'Inspect recorded evidence.'});
function response(faults){return [{telemetry:{timestamp:new Date().toISOString(),engine_id:'TEST',mission_id:'M1',rpm:2100},state:{synchronized:true,faults:{diagnostics:faults},telemetry:{parameters:{}}}}];}
test('backend diagnostics color physical regions, focus, reset, and clear across responsive views',async({page})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));let faults=codes.map(diagnostic);
 await page.route('**/api/v1/**',route=>route.fulfill({json:response(faults)}));
 await page.goto('/twin');await expect(page.locator('.wt-engine-object svg')).toBeVisible();await expect(page.locator('.wt-engine-three')).toHaveCount(0);await page.getByRole('button',{name:'3D engine',exact:true}).click();await expect(page.locator('.wt-engine-three canvas')).toBeVisible();await expect(page.locator('.wt-mesh-label').first()).toBeVisible();await page.locator('.wt-fault-picker').getByRole('button',{name:'OVERHEATING · CRITICAL',exact:true}).click();await expect(page.locator('.wt-engine-three')).toHaveAttribute('data-focus','OVERHEATING');await page.waitForTimeout(700);await page.screenshot({path:'test-results/faults-3d.png',fullPage:true});await page.getByRole('button',{name:'2D cutaway',exact:true}).click();await expect(page.locator('.wt-fault-picker button')).toHaveCount(11);await expect(page.locator('.wt-fault-marker')).toHaveCount(1);
 await expect(page.locator('[data-fault-surface]').first()).toBeVisible();
 await page.locator('.wt-fault').filter({hasText:'OVERHEATING'}).getByRole('button',{name:'Focus component'}).click();
 await expect(page.locator('.wt-active-fault')).toContainText('OVERHEATING');
 await expect(page.locator('.wt-active-fault')).toContainText('Engineering score 0.910');
 await expect(page.locator('.wt-engine-object')).not.toHaveCSS('transform','matrix(1, 0, 0, 1, 0, 0)');
 await page.getByRole('button',{name:'Reset view'}).click();
 await expect(page.locator('.wt-engine-object')).toHaveCSS('transform','matrix(1, 0, 0, 1, 0, 0)');
 for(const width of [1440,390]){await page.setViewportSize({width,height:900});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);}
 await page.screenshot({path:'test-results/faults-mobile.png',fullPage:true});
 faults=[];await expect(page.locator('.wt-fault-marker')).toHaveCount(0);await expect(page.locator('[data-fault-surface]')).toHaveCount(0);await expect(page.locator('.wt-active-fault')).toHaveCount(0);expect(errors).toEqual([]);
});
test('demo uses backend diagnostics and recorded replay preserves them',async({page})=>{
 await page.route('**/api/v1/**',async route=>{
  if(route.request().url().endsWith('/telemetry/synchronize')){const telemetry=route.request().postDataJSON();await route.fulfill({json:{telemetry,state:{synchronized:true,faults:{diagnostics:[diagnostic('LUBRICATION_ISSUE')]},telemetry:{parameters:{}}}}});}
  else await route.fulfill({json:response([])});
 });
 await page.goto('/simulation');await page.getByRole('button',{name:'Start demo',exact:true}).click();await expect(page.locator('.wt-fault-marker')).toContainText('LUBRICATION');
 await page.getByRole('link',{name:'Mission Replay'}).click();await page.getByRole('button',{name:'Open current recording'}).click();await expect(page.locator('.wt-fault-marker')).toContainText('LUBRICATION');
});
