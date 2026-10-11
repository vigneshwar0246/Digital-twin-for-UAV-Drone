import {defineConfig} from '@playwright/test';

const host='127.0.0.1';
const port=5174;
const url=`http://${host}:${port}`;

export default defineConfig({
 testDir:'./e2e',
 timeout:60000,
 workers:1,
 use:{baseURL:url,viewport:{width:1440,height:900},launchOptions:{args:['--use-angle=swiftshader','--enable-webgl']}},
 webServer:{
  command:`node ./node_modules/vite/bin/vite.js --host ${host} --port ${port} --strictPort`,
  url,
  reuseExistingServer:false,
  timeout:60000,
 },
});
