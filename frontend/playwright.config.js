import { defineConfig } from '@playwright/test';
export default defineConfig({testDir:'./e2e',timeout:60000,workers:1,use:{baseURL:'http://127.0.0.1:5173',viewport:{width:1440,height:900},launchOptions:{args:['--use-angle=swiftshader','--enable-webgl']}},webServer:{command:'npm.cmd run dev',url:'http://127.0.0.1:5173',reuseExistingServer:true}});
