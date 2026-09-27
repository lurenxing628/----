'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const {connect}=require('./win7_workflow_transport.cjs');
const root=process.argv[2],out=path.join(root,'process-restart');fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await connect(chromium,root),context=await browser.newContext({viewport:{width:1920,height:1080}}),page=await context.newPage();page.setDefaultTimeout(30000);
 const report={passed:false,page_errors:[]};page.on('pageerror',e=>report.page_errors.push(e.message));
 try{
  await page.goto('http://127.0.0.1:5000/workbench?view=process');await page.locator('[data-rail-node="process"]').click();
  const work=page.locator('[data-process-workspace]'),search=work.getByRole('searchbox');await search.fill('AN-P-1920-light');await search.press('Enter');
  await work.getByRole('button',{name:'查看 AN-P-1920-light',exact:true}).click();await page.getByRole('tablist',{name:'零件工艺步骤',exact:true}).waitFor();
  report.process_text=await page.locator('main').innerText().catch(()=>page.locator('body').innerText());assert(report.process_text.includes('AN-P-1920-light'));await page.screenshot({path:path.join(out,'process-detail.png')});
  await page.getByRole('button',{name:'关闭详情',exact:true}).click();await page.locator('.sidebar').getByText('批次管理',{exact:true}).click();
  const batches=page.locator('[data-batch-workspace]');await batches.waitFor();await batches.getByRole('searchbox').fill('AN-MULTI-');
  const pending=page.waitForResponse(r=>r.url().endsWith('/entities/batch/query')&&r.request().method()==='POST');await batches.getByRole('searchbox').press('Enter');const response=await pending;assert.equal(response.status(),200);report.batches=await response.json();assert.equal(report.batches.data.page.total,43);
  await batches.getByRole('button',{name:'AN-MULTI-001',exact:true}).waitFor();await page.screenshot({path:path.join(out,'batch-list.png')});assert.deepEqual(report.page_errors,[]);report.passed=true;
 }catch(e){report.error=e.stack;console.error(e);process.exitCode=1;}
 finally{fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));await context.close();await browser.close();}
 console.log(JSON.stringify({process_restart:report.passed,batch_count:report.batches?.data.page.total}));
})().catch(e=>{console.error(e);process.exitCode=1});
