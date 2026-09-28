'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const {chromium}=require('playwright');
const {connect}=require('./win7_workflow_transport.cjs');
const controls=require('./custom_control_actions.cjs');
const ready=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
(async()=>{
 const input=path.join(ready.root,'downloads','reported-batch-replace.xlsx');
 execFileSync(process.env.WIN7_HOST_PYTHON,['-B','-c','import openpyxl,sys\nw=openpyxl.Workbook();w.active.append(["批次号","图号","数量","交期","优先级","齐套","齐套日期","备注"]);w.active.append(["FIELD-REPLACE-NEW","P1",1,"2028-02-29","normal","yes",None,"只预检，不确认"]);w.save(sys.argv[1])',input]);
 const browser=await connect(chromium,ready.win7_evidence_root),context=await browser.newContext({viewport:{width:1920,height:1080}}),page=await context.newPage();page.setDefaultTimeout(30000);
 const report={passed:false,confirm_requests:[]};page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/import-confirm'))report.confirm_requests.push(r.url());});
 try{
  await page.goto('http://127.0.0.1:5000/workbench?view=batches');await page.locator('[data-batch-workspace]').waitFor();await page.getByRole('button',{name:'批量导入',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'批量导入批次',exact:true});await controls.select(dialog.getByLabel('导入模式',{exact:true}),'replace');await dialog.locator('input[type=file]').setInputFiles(input);
  const pending=page.waitForResponse(r=>r.url().endsWith('/import-preview')&&r.request().method()==='POST');await dialog.getByRole('button',{name:'开始预检',exact:true}).click();const response=await pending;assert.equal(response.status(),200);
  report.preview=await response.json();assert.equal(report.preview.data.can_confirm,false);
  assert(report.preview.data.deleted.some(row=>row.before.relationships.execution_reference_count>0&&row.errors.length),'A batch with actual execution records must be refused');
  assert(await dialog.getByRole('button',{name:'确认导入',exact:true}).isDisabled());report.text=await dialog.innerText();
  report.screenshot=path.join(ready.root,'screenshots','reported-batch-replace-protected.png');await page.screenshot({path:report.screenshot});
  await dialog.getByRole('button',{name:'取消',exact:true}).click();await page.getByRole('dialog',{name:'离开前确认',exact:true}).getByRole('button',{name:'放弃未保存内容并继续',exact:true}).click();
  assert.deepEqual(report.confirm_requests,[]);report.passed=true;
 }catch(e){report.error=e.stack;console.error(e);process.exitCode=1;}
 finally{fs.writeFileSync(path.join(ready.root,'reported-batch-protection.json'),JSON.stringify(report,null,2));await context.close();await browser.close();}
 console.log(JSON.stringify({reported_batch_replace_protected:report.passed}));
})().catch(e=>{console.error(e);process.exitCode=1});
