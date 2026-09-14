'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process');
const {chromium}=require('playwright'),H=require('./field_workspace_probe_harness.cjs');
const output=path.resolve(process.argv[2]||'');assert(process.argv[2]&&!output.startsWith(H.root+'/'));
fs.mkdirSync(output,{recursive:true});
const report={scope:'Field fastpath isolated real Flask SQLite and pending mock',production_db:false,global_build:false,cases:[],errors:[],writes:[]};
let page,browser,server,backend;
const exact=name=>page.getByRole('button',{name,exact:true});
async function run(name,fn){await fn();report.cases.push({name,passed:true});console.log(name+' passed');}
async function save(label){const response=page.waitForResponse(value=>value.request().method()==='POST'&&/\/execution\/(tasks|reports)\//.test(value.url()));await exact(label).click();const value=await (await response).json();assert.equal(value.ok,true,JSON.stringify(value));return value;}
async function open(sequence){const button=page.getByRole('button',{name:new RegExp('^查看报工 B1 '+sequence+' Turning')});await button.click();await page.getByRole('table',{name:'逐次报工记录',exact:true}).waitFor();}
async function latest(sequence){return page.evaluate(async sequence=>{const response=await fetch('/api/workbench/v1/execution/tasks?size=100'),result=await response.json();return result.data.tasks.find(task=>task.operation_label===sequence+' Turning');},sequence);}
async function main(){
 try {
  backend=spawn(path.join(H.root,'.venv/bin/python'),['-m','tests.workbench.field_workspace_probe_server',path.join(output,'db')],{cwd:H.root,stdio:['ignore','pipe','pipe']});
  let stderr='';backend.stderr.on('data',chunk=>stderr+=chunk);
  const ready=await new Promise((resolve,reject)=>{let text='';backend.stdout.on('data',chunk=>{text+=chunk;try{resolve(JSON.parse(text.split('\n')[0]));}catch{}});backend.on('exit',code=>reject(new Error('Fixture exited '+code+': '+stderr)));});
  server=H.createServer(ready.url,report);await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const origin='http://127.0.0.1:'+server.address().port;
  browser=await chromium.launch({executablePath:process.env.WORKBENCH_BROWSER,headless:true});report.browser=browser.version();
  page=await browser.newPage({viewport:{width:1280,height:720}});page.setDefaultTimeout(12000);page.on('pageerror',error=>report.errors.push(error.stack));
  page.on('request',request=>{if(request.method()==='POST'&&/\/execution\/(tasks|reports)\//.test(request.url()))report.writes.push({url:request.url(),body:request.postDataJSON()});});
  await page.goto(origin);await page.locator('[data-field-task]').first().waitFor();
  await run('new suggestions clear to unknown and automatic reread preserves ledger null',async()=>{
   await open(5);await exact('新增本次报工').click();assert((await page.locator('.field-suggestion').innerText()).includes('保存后将登记为实际记录'));
   await page.screenshot({path:path.join(output,'field-editor-suggestions.png'),fullPage:false});
   assert((await page.getByLabel('实际开工',{exact:true}).inputValue()).length>0);await exact('清除实际开工').click();await exact('清除本次实际完工').click();
   await page.getByLabel('本次完成数量',{exact:true}).fill('1');await save('保存报工');await page.locator('.field-editor').waitFor({state:'hidden'});
   await page.getByText('已保存并刷新最新报工。',{exact:true}).waitFor();const task=await latest(5);assert.equal(task.execution.reports.length,1);assert.equal(task.execution.reports[0].actual_start,null);assert.equal(task.execution.reports[0].actual_end,null);assert.equal(task.execution.reports[0].completed_quantity,1);
   // The save notice describes the read that follows a save; a manual refresh must replace it, otherwise a later read failure would be reported as "报工已保存，但刷新失败".
   await exact('刷新现场记录').click();await page.locator('[data-field-task]').first().waitFor();
   assert.equal(await page.getByText('已保存并刷新最新报工。',{exact:true}).count(),0,'a manual refresh replaces the post-save notice');
  });
  await run('supplement has no fresh defaults and focuses field errors',async()=>{
   const task=await latest(5),record=task.execution.reports[0];await exact('补齐 '+record.report_no).click();assert.equal(await page.getByLabel('实际开工',{exact:true}).inputValue(),'');assert.equal(await page.getByLabel('本次实际完工',{exact:true}).inputValue(),'');assert.equal(await page.locator('.field-suggestion').count(),0);
   await page.getByLabel('有效工时（小时）',{exact:true}).fill('0');await exact('保存报工').click();await page.locator('[aria-invalid="true"]').waitFor();assert.equal(await page.getByLabel('补齐或更正原因',{exact:true}).evaluate(node=>document.activeElement===node),true);
   await page.screenshot({path:path.join(output,'field-editor-validation.png'),fullPage:false});
   await page.getByLabel('补齐或更正原因',{exact:true}).fill('保留未知起止，仅补零工时');await save('保存报工');await page.locator('.field-editor').waitFor({state:'hidden'});const after=await latest(5);assert.equal(after.execution.reports[0].actual_end,null);assert.equal(after.execution.reports[0].effective_processing_hours,0);
  });
  await run('save continue waits for fresh write context and creates another request',async()=>{
   await exact('新增本次报工').click();await page.getByLabel('本次完成数量',{exact:true}).fill('1');await save('保存并继续');
   await page.getByText('已核对最新报工，已打开新的报工草稿。',{exact:true}).waitFor();assert.equal(await page.getByLabel('本次完成数量',{exact:true}).inputValue(),'');
   await exact('复制上一条').click();assert.equal(await page.getByLabel('本次完成数量',{exact:true}).inputValue(),'1');
   await save('保存报工');await page.locator('.field-editor').waitFor({state:'hidden'});
   const after=await latest(5);assert.equal(after.execution.reports.length,3);const last=report.writes.slice(-2);assert.notEqual(last[0].body.request_key,last[1].body.request_key);assert.notEqual(last[0].body.write_token,last[1].body.write_token);
   for(const value of last)for(const key of ['request_key','report_ref','revision_ref','task_ref','write_context'])assert.equal(Object.hasOwn(value.body.input,key),false);
  });
  await run('retained drafts survive collapsed rows and cancellation is explicit',async()=>{
   await exact('新增本次报工').click();await exact('清除实际开工').click();await page.getByLabel('本次完成数量',{exact:true}).fill('2');
   await page.locator('[data-field-task].field-selected .field-link').click();await page.locator('.field-editor').waitFor({state:'hidden'});assert(await page.evaluate(()=>WorkbenchGuards.hasDirty()));
   await open(6);await exact('新增本次报工').click();await page.getByLabel('本次完成数量',{exact:true}).fill('3');
   await exact('取消').click();await exact('放弃未保存内容并继续').click();await page.locator('.field-editor').waitFor({state:'hidden'});assert(await page.evaluate(()=>WorkbenchGuards.hasDirty()),'another task draft remains protected');
   await open(5);assert.equal(await page.getByLabel('实际开工',{exact:true}).inputValue(),'');assert.equal(await page.getByLabel('本次完成数量',{exact:true}).inputValue(),'2');
   await exact('取消').click();await exact('留在当前页面').click();assert.equal(await page.getByLabel('本次完成数量',{exact:true}).inputValue(),'2');
   await exact('取消').click();await exact('放弃未保存内容并继续').click();await page.locator('.field-editor').waitFor({state:'hidden'});assert.equal(await page.evaluate(()=>WorkbenchGuards.hasDirty()),false);
  });
  await run('layout scrolling and reachable actions in both themes',async()=>{
   assert(await page.getByRole('table',{name:'现场任务列表'}).locator('caption').count());assert(await page.getByRole('table',{name:'逐次报工记录'}).locator('caption').count());
   assert.equal(await page.locator('.field-workspace table th:not([scope])').count(),0);
   for(const theme of ['light','dark'])for(const width of [1280,1366]){await page.setViewportSize({width,height:width===1280?720:768});await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
    const geometry=await page.evaluate(()=>{const frame=document.querySelector('.field-workspace>.field-scroll'),head=frame.querySelector('thead th'),action=frame.querySelector('tbody tr .wb-col-actions');frame.scrollTop=100;frame.scrollLeft=100;return{root:document.documentElement.scrollWidth,width:innerWidth,head:getComputedStyle(head).position,maxHeight:getComputedStyle(frame).maxHeight,action:getComputedStyle(action).position};});
    assert(geometry.root<=geometry.width+1,JSON.stringify(geometry));assert.equal(geometry.head,'sticky');assert.equal(geometry.action,'sticky');assert.notEqual(geometry.maxHeight,'none');await page.screenshot({path:path.join(output,'field-'+width+'-'+theme+'.png'),fullPage:false});}
  });
  await page.goto(origin+'/?mock=1');await page.locator('[data-field-task]').first().waitFor();
  await run('pending save continue never creates another draft or write',async()=>{
   await open(5);await exact('新增本次报工').click();await page.getByLabel('本次完成数量',{exact:true}).fill('1');await exact('保存并继续').click();await exact('查询结果').waitFor();
   assert(await exact('保存并继续').isDisabled());assert(await exact('取消').isDisabled());assert.equal(await page.evaluate(()=>probe.writes.length),1);const key=await page.evaluate(()=>probe.writes[0].body.request_key);
   await exact('查询结果').click();assert.equal(await page.evaluate(()=>probe.writes.length),1);assert((await page.evaluate(()=>probe.lookups)).every(value=>value===key));
   assert.equal(await page.getByLabel('本次完成数量',{exact:true}).inputValue(),'1');assert(await page.evaluate(()=>WorkbenchGuards.hasDirty()));
  });
  await run('confirmed receipt with read failure or stale context never opens another draft',async()=>{
   await page.evaluate(()=>{window.mockReadFailure=true;window.mockReceipt={ok:true,result:'committed',data:{rows:[]},receipt_ref:'confirmed-original-request',warnings:[]};});
   await exact('查询结果').click();await page.getByText('报工已保存，但刷新失败；请再点「刷新现场记录」，没有重复写入。',{exact:true}).waitFor();assert.equal(await page.locator('.field-editor').count(),0);assert.equal(await page.evaluate(()=>probe.writes.length),1);
   await page.evaluate(()=>{window.mockReadFailure=false;});await exact('刷新现场任务').click();await page.getByText('本页数据已过期，没有打开新的报工草稿。请点「刷新现场记录」后再新增。',{exact:true}).waitFor();
   assert.equal(await page.locator('.field-editor').count(),0);assert.equal(await page.evaluate(()=>probe.writes.length),1);
  });
  assert.deepEqual(report.errors,[]);report.completed=true;
 } catch(error){report.error=error.stack;process.exitCode=1;if(page)await page.screenshot({path:path.join(output,'FAILED.png')}).catch(()=>{});}
 finally {if(browser)await browser.close();if(server)await new Promise(resolve=>server.close(resolve));if(backend&&backend.exitCode===null&&backend.signalCode===null){const exited=new Promise(resolve=>backend.once('exit',resolve));backend.kill('SIGTERM');await exited;}fs.writeFileSync(path.join(output,'field-fastpath.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({output,cases:report.cases.length,completed:report.completed,error:report.error}));}
}
main();
