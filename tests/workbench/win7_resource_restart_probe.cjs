'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const {connect}=require('./win7_workflow_transport.cjs');
const root=process.argv[2],out=path.join(root,'resource-restart');fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await connect(chromium,root),context=await browser.newContext({viewport:{width:1920,height:1080}}),page=await context.newPage();
 const report={steps:[],page_errors:[],passed:false};page.on('pageerror',e=>report.page_errors.push(e.message));page.setDefaultTimeout(20000);
 try{
  await page.goto('http://127.0.0.1:5000/workbench?view=process');await page.getByRole('button',{name:'MAT-001',exact:true}).waitFor();
  for(const [node,code,text] of [['物料','MAT-001','Material 1'],['设备','RT-M','Lathe'],['人员','RT-O','Original operator'],['供应商','RT-S','Original supplier']]){
   await page.locator('[data-rail-node]').filter({has:page.getByText(node,{exact:true})}).click();
   await page.getByRole('searchbox',{name:'搜索编号或名称'}).fill(code);await page.getByRole('button',{name:'搜索',exact:true}).click();
   await page.getByRole('button',{name:code,exact:true}).click();const dialog=page.getByRole('dialog');await dialog.waitFor();assert((await dialog.innerText()).includes(text));
   const screenshot=path.join(out,code+'.png');await page.screenshot({path:screenshot});report.steps.push({node,code,label:text,screenshot,passed:true});
   await dialog.locator('.modal-f').getByRole('button',{name:'关闭',exact:true}).click();await dialog.waitFor({state:'detached'});
  }
  assert.deepEqual(report.page_errors,[]);report.passed=true;
 }catch(e){report.error=e.stack;console.error(e);process.exitCode=1;}
 finally{fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await context.close();await browser.close();}
 console.log(JSON.stringify({passed:report.passed,steps:report.steps.length}));
})().catch(e=>{console.error(e);process.exitCode=1});
