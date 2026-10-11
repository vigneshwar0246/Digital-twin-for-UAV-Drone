import {test,expect} from '@playwright/test';
test('flight, click gate, engine zoom, reversal and refresh',async({page})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await page.goto('/');await expect(page.locator('canvas')).toBeVisible();
 const main=page.locator('main');await expect(main).toHaveAttribute('data-state','INTRO');
 await page.evaluate(()=>window.scrollTo(0,innerHeight*1.4));await expect(main).toHaveAttribute('data-state','AIRCRAFT_FLIGHT');
 await page.evaluate(()=>window.scrollTo(0,0));await expect(main).toHaveAttribute('data-state','INTRO',{timeout:15000});
 await page.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));await expect(main).toHaveAttribute('data-state','AIRCRAFT_SETTLED');
 await page.mouse.wheel(0,4000);await page.waitForTimeout(900);await expect(main).toHaveAttribute('data-state','AIRCRAFT_SETTLED');
 await page.locator('canvas').click({position:{x:730,y:450}});await expect(main).toHaveAttribute('data-state','AIRCRAFT_SELECTED');
 await page.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));await expect(main).toHaveAttribute('data-state','ENGINE_HERO');
 await expect(page.getByRole('button',{name:/ENTER/})).toBeVisible();
 await expect(page.getByText('Every detail.')).toBeHidden();
 await expect(page.getByText('Aero piston engine.')).toHaveCount(0);
 await page.evaluate(()=>window.scrollTo(0,0));await expect(main).toHaveAttribute('data-state','INTRO',{timeout:15000});
 await page.reload();await expect(main).toHaveAttribute('data-state','INTRO');expect(errors).toEqual([]);
});
test('mobile preserves framing and selection',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.goto('/');await expect(page.locator('canvas')).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 await page.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));await expect(page.locator('main')).toHaveAttribute('data-state','AIRCRAFT_SETTLED');
 await page.getByRole('button',{name:/INITIALIZE DIGITAL TWIN/}).click();await page.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));await expect(page.locator('main')).toHaveAttribute('data-state','ENGINE_HERO');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
