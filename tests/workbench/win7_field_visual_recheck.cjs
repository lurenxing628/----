'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright'),{connect}=require('./win7_workflow_transport.cjs');
const ready=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
(async()=>{
 const report={passed:false,captures:[],mutations:[],errors:[]};
 const browser=await connect(chromium,ready.win7_evidence_root),context=await browser.newContext({viewport:{width:1920,height:1080}}),page=await context.newPage();page.setDefaultTimeout(30000);
 page.on('pageerror',e=>report.errors.push(e.message));page.on('request',r=>{if(r.method()!=='GET'&&r.url().includes('/api/'))report.mutations.push(r.url());});
 try{
  await page.goto('http://127.0.0.1:5000/workbench?view=field');await page.bringToFront();await page.locator('[data-field-task]').first().waitFor();await page.waitForFunction(()=>document.fonts.status==='loaded');
  const ref=ready.expected.final_e.task_refs['1'];await page.locator('[data-field-task="'+ref+'"] button[aria-expanded]').click();
  await page.locator('.main-content').hover();await page.mouse.wheel(0,1200);
  for(let round=1;round<=3;round++)for(const [width,height] of [[1920,1080],[1392,924]])for(const theme of ['light','dark']){
   await page.setViewportSize({width,height});if(await page.locator('html').getAttribute('data-theme')!==theme)await page.getByRole('button',{name:/^切换(?:深色|浅色)$/}).click();
   await page.waitForFunction(value=>document.documentElement.dataset.theme===value,theme);
   await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
   const geometry=await page.evaluate(()=>{const rect=s=>{const r=document.querySelector(s).getBoundingClientRect();return {top:r.top,left:r.left,right:r.right,bottom:r.bottom};};return {header:rect('.top-header'),sidebar:rect('.sidebar'),app:rect('.app-container'),width:document.documentElement.scrollWidth,innerWidth,scrollY,fonts:document.fonts.status};});
   assert(Math.abs(geometry.header.top)<=1&&Math.abs(geometry.sidebar.top)<=1&&Math.abs(geometry.app.top+geometry.scrollY)<=1,JSON.stringify(geometry));assert(geometry.width<=width+1);
   const file=path.join(ready.root,'screenshots','visual-recheck-'+round+'-'+width+'-'+theme+'.png');await page.screenshot({path:file,timeout:15000});report.captures.push({round,width,theme,file,geometry});
  }
  assert.deepEqual(report.mutations,[]);assert.deepEqual(report.errors,[]);report.passed=true;
 }catch(e){report.error=e.stack;console.error(e);process.exitCode=1;}finally{fs.writeFileSync(path.join(ready.root,'visual-recheck.json'),JSON.stringify(report,null,2));await context.close();await browser.close();}
 console.log(JSON.stringify({passed:report.passed,captures:report.captures.length}));
})().catch(e=>{console.error(e);process.exitCode=1});
