'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const {connect}=require('./win7_workflow_transport.cjs');
const controls=require('./custom_control_actions.cjs');
const ready=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),phase=process.argv[3]||'initial';
const report={phase,steps:[],requests:[],page_errors:[],passed:false};
const save=()=>fs.writeFileSync(path.join(ready.root,'batch-modes-'+phase+'.json'),JSON.stringify(report,null,2));
(async()=>{
 const browser=await connect(chromium,ready.win7_evidence_root),context=await browser.newContext({viewport:{width:1920,height:1080}}),page=await context.newPage();page.setDefaultTimeout(30000);
 page.on('pageerror',e=>report.page_errors.push(e.message));page.on('request',r=>{if(r.url().includes('/api/workbench/'))report.requests.push({method:r.method(),url:r.url()});});
 async function read(suffix,action){const pending=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith(suffix)&&r.request().method()==='POST');await action();const response=await pending;const body=await response.json();assert.equal(response.status(),200,JSON.stringify(body));return body;}
 const button=(name,scope=page)=>scope.getByRole('button',{name,exact:true});
 const list=async()=> (await read('/entities/batch/query',()=>button('刷新批次列表').click())).data.entities;
 const step=async(name,action)=>{const row={name,passed:false};report.steps.push(row);try{await action();row.passed=true;row.screenshot=path.join(ready.root,'screenshots',phase+'-'+name+'.png');await page.screenshot({path:row.screenshot});console.log(name+': passed');}catch(e){row.error=e.stack;throw e;}finally{save();}};
 async function preview(file,mode){
  await button('批量导入').click();const dialog=page.getByRole('dialog',{name:'批量导入批次',exact:true});
  if(mode!=='overwrite')await controls.select(dialog.getByLabel('导入模式',{exact:true}),mode);
  await dialog.locator('input[type=file]').setInputFiles(path.join(ready.root,'uploads',file+'.xlsx'));
  const value=await read('/import-preview',()=>button('开始预检',dialog).click());report.steps[report.steps.length-1].preview=value;
  assert.equal(value.data.can_confirm,true,JSON.stringify(value));return {dialog,value};
 }
 async function confirm(dialog){
  const receipt=await read('/import-confirm',()=>button('确认导入',dialog).click());assert.equal(receipt.result,'committed');report.steps[report.steps.length-1].receipt=receipt;
  await button('关闭',dialog).last().click();await dialog.waitFor({state:'detached'});
 }
 try{
  await page.goto('http://127.0.0.1:5000/workbench?view=batches');await page.locator('[data-batch-workspace]').waitFor();
  await page.bringToFront();await page.waitForFunction(()=>document.fonts.status==='loaded');
  if(phase==='initial'){
   await step('initial-xlsx-create',async()=>{if(ready.initial_committed_report){const previous=JSON.parse(fs.readFileSync(ready.initial_committed_report,'utf8'));assert.equal(previous.steps[0].receipt.result,'committed');report.steps[0].original_committed_receipt=previous.steps[0].receipt;report.steps[0].continuation=ready.initial_committed_report;}else{const {dialog}=await preview('initial','overwrite');await confirm(dialog);}const rows=await list();assert.equal(rows.find(r=>r.business_code==='MODE-001').fields.quantity,2);assert.equal(rows.find(r=>r.business_code==='MODE-002').fields.quantity,3);assert.equal(rows.length,3);});
   await step('append-skips-existing-and-adds-new',async()=>{const {dialog,value}=await preview('append','append');assert(value.data.rows.some(r=>r.action==='skipped'));await confirm(dialog);const rows=await list();const original=rows.find(r=>r.business_code==='MODE-001');assert.equal(original.fields.quantity,2);assert.equal(original.fields.remark,'保留初始备注');assert.equal(rows.find(r=>r.business_code==='MODE-003').fields.quantity,5);});
   await step('overwrite-updates-adds-and-preserves-empty-cell',async()=>{const {dialog}=await preview('overwrite','overwrite');await confirm(dialog);const rows=await list();const original=rows.find(r=>r.business_code==='MODE-001');assert.equal(original.fields.quantity,7);assert.equal(original.fields.remark,'保留初始备注');assert.equal(rows.find(r=>r.business_code==='MODE-004').fields.quantity,9);assert.equal(rows.length,5);});
   await step('bulk-update-preview-cancel-and-confirm-selected-only',async()=>{
    for(const code of ['MODE-001','MODE-003'])await page.getByRole('checkbox',{name:'选择 '+code,exact:true}).check();
    const before=await list();
    async function openBulk(){await button('批量修改').click();const edit=page.getByRole('dialog',{name:'批量修改批次',exact:true});await controls.select(edit.getByLabel('批量优先级',{exact:true}),'urgent');await edit.getByLabel('批量备注',{exact:true}).fill('批量修改已核对');const value=await read('/bulk-preview',()=>button('预览变更',edit).click());assert.equal(value.data.rows.length,2);return page.getByRole('dialog',{name:'确认批量修改',exact:true});}
    let dialog=await openBulk();await button('取消',dialog).click();await dialog.waitFor({state:'detached'});
    assert.deepEqual((await list()).map(r=>[r.business_code,r.fields]),before.map(r=>[r.business_code,r.fields]));
    dialog=await openBulk();const receipt=await read('/bulk-confirm',()=>button('确认变更',dialog).click());assert.equal(receipt.result,'committed');await button('关闭',dialog).last().click();await dialog.waitFor({state:'detached'});
    await page.reload();await page.locator('[data-batch-workspace]').waitFor();const after=await list();
    for(const row of after){const old=before.find(r=>r.business_code===row.business_code);if(['MODE-001','MODE-003'].includes(row.business_code)){assert.equal(row.fields.priority,'urgent');assert.equal(row.fields.remark,'批量修改已核对');assert.equal(row.fields.quantity,old.fields.quantity);}else assert.deepEqual(row.fields,old.fields);}
    if(await button('清除选择').isEnabled())await button('清除选择').click();
   });
   await step('replace-cancel-retains-all-batches',async()=>{const before=await list(),{dialog,value}=await preview('replace','replace');assert.equal(value.data.deleted.length,5);assert(await button('确认导入',dialog).isDisabled());await button('取消',dialog).click();const guard=page.getByRole('dialog',{name:'离开前确认',exact:true});await button('放弃未保存内容并继续',guard).click();await dialog.waitFor({state:'detached'});assert.deepEqual((await list()).map(r=>[r.business_code,r.fields]),before.map(r=>[r.business_code,r.fields]));});
   await step('replace-confirm-removes-exact-preview-and-imports',async()=>{const {dialog,value}=await preview('replace','replace');assert.deepEqual(value.data.deleted.map(r=>r.before.business_code).sort(),['MODE-001','MODE-002','MODE-003','MODE-004','PROC-B']);await dialog.getByRole('checkbox').check();assert(await button('确认导入',dialog).isEnabled());await confirm(dialog);});
  }
  await step('reload-exact-replacement-result',async()=>{await page.reload();await page.locator('[data-batch-workspace]').waitFor();const rows=await list();assert.equal(rows.length,1);assert.equal(rows[0].business_code,'MODE-R001');assert.equal(rows[0].fields.quantity,4);assert.equal(rows[0].fields.remark,'清空重导结果');report.final=rows;});
  assert.deepEqual(report.page_errors,[]);report.passed=true;
 }catch(e){report.error=e.stack;console.error(e);process.exitCode=1;await page.screenshot({path:path.join(ready.root,'screenshots',phase+'-failed.png')});}
 finally{save();await context.close();await browser.close();}
})().catch(e=>{report.error=e.stack;save();console.error(e);process.exitCode=1});
