import {test,expect} from '@playwright/test';

const primary=[
 ['Live Digital Twin','/twin'],
 ['Engine Telemetry','/telemetry'],
 ['Health Monitoring','/health'],
 ['AI Diagnostics','/diagnostics'],
 ['Mission Simulation','/simulation'],
 ['Mission Replay','/replay'],
 ['Reports','/reports'],
];

test('presentation navigation keeps seven primary pages and secondary routes',async({page})=>{
 await page.goto('/twin');
 const nav=page.locator('.wt-sidebar nav');
 await expect(nav.locator('a')).toHaveCount(7);
 for(const [label,path] of primary){
  const link=nav.getByRole('link',{name:label,exact:false});
  await expect(link).toHaveAttribute('href',path);
  await link.click();
  await expect(page).toHaveURL(new RegExp(`${path}$`));
  await expect(page.getByRole('heading',{level:1})).toHaveText(label);
  await expect(link).toHaveClass(/active/);
 }
 await page.goBack();
 await expect(page).toHaveURL(/\/replay$/);
 await expect(nav.getByRole('link',{name:'Mission Replay'})).toHaveClass(/active/);
 await page.getByRole('button',{name:/Operator settings/}).click();
 await expect(page.getByRole('heading',{level:1})).toHaveText('System Configuration');
 await page.goto('/rul');
 await expect(page.getByRole('heading',{level:1})).toHaveText('RUL & Degradation');
 await page.goto('/overview');
 await expect(page).toHaveURL(/\/twin$/);
 await page.getByRole('link',{name:/Aircraft experience/}).click();
 await expect(page).toHaveURL(/\/$/);
 await expect(page.locator('.wt-sidebar')).toHaveCount(0);
});
