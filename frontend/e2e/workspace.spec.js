import {test,expect} from '@playwright/test';
test('workspace simulation, navigation, replay and report',async({page})=>{
 // Deterministic API contract fixtures keep this navigation test independent of a local database.
 await page.route('**/api/v1/**',async route=>{
  const submitted=route.request().method()==='POST'?route.request().postDataJSON():null;
  const telemetry=submitted||{timestamp:new Date().toISOString(),engine_id:'E2E',mission_id:'M1',rpm:2200};
  const entry={telemetry,state:{synchronized:true,telemetry:{parameters:{}},faults:{diagnostics:submitted?[{fault_code:'FUEL_INJECTOR_DEGRADATION',fault_name:'Injector Degradation',severity:'WARNING',engineering_score:.7,uncertainty:'high',affected_subsystems:['FUEL_SYSTEM_HEALTH'],evidence:{fuel_flow_residual_lph:7}}]:[]}}};
  await route.fulfill({json:submitted?entry:[entry]});
 });
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/twin');await expect(page.getByRole('heading',{name:'Live Digital Twin',exact:true})).toBeVisible();
 await expect(page.locator('.wt-metric').first().locator('strong')).not.toContainText('—');
 await page.getByRole('link',{name:'Mission Simulation'}).click();
 await page.getByLabel('Scenario / fault injection').selectOption('Injector Degradation');
 await page.getByRole('button',{name:'Start demo',exact:true}).click();
 await page.getByLabel('Speed',{exact:true}).selectOption('10');
 await page.waitForTimeout(2000);
 await page.getByRole('link',{name:'AI Diagnostics'}).click();
 await expect(page.locator('.wt-fault h4')).toContainText('Injector Degradation');
 await page.getByRole('link',{name:'Mission Replay'}).click();
 await page.getByRole('button',{name:'Open current recording'}).click();
 const timeline=page.getByRole('slider',{name:'Replay timeline'});await expect(timeline).toBeEnabled();
 await timeline.fill('0');const first=await page.locator('.wt-metric').allInnerTexts();
 const lastFrame=await timeline.getAttribute('max');await timeline.fill(lastFrame);
 await expect(timeline).toHaveValue(lastFrame);
 expect(await page.locator('.wt-metric').allInnerTexts()).not.toEqual(first);
 await page.getByRole('link',{name:'Reports',exact:false}).click();
 const download=page.waitForEvent('download');await page.getByRole('button',{name:'Export JSON'}).click();expect((await download).suggestedFilename()).toBe('mission-report.json');
 await page.goto('/twin');await page.screenshot({path:'test-results/workspace-desktop.png',fullPage:true});
 for(const width of [1920,1366,390]){await page.setViewportSize({width,height:900});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);}
 expect(errors).toEqual([]);
});
test('backend failure remains explicit and does not fall back to simulated live values',async({page})=>{
 await page.route('**/api/v1/**',route=>route.fulfill({status:503,contentType:'application/json',body:'{"detail":"offline"}'}));
 await page.goto('/twin');await page.getByLabel('Data source').selectOption('REAL');
 await expect(page.getByRole('alert')).toContainText('Backend request failed');
 await expect(page.locator('.wt-statusbar')).toContainText('BACKEND DISCONNECTED');
 await expect(page.locator('.wt-metric').first()).toContainText('—');
});
test('backend sensor fault quality survives a missing numeric reading',async({page})=>{
 await page.goto('/twin');
 const signal=await page.evaluate(async()=>{
  const {normalize}=await import('/src/workspace/api.ts');
  return normalize({telemetry:{timestamp:new Date().toISOString(),engine_id:'E2E',mission_id:'M1'},state:{telemetry:{parameters:{rpm:{value:null,quality:'SENSOR_FAULT'}}}}},'TEST').signals.rpm;
 });
 expect(signal).toMatchObject({value:null,quality:'SENSOR_FAULT'});
});
