'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
const {connect}=require('./win7_workflow_transport.cjs');
const ready=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),root=ready.root,repo=path.resolve(__dirname,'../..'),origin='http://127.0.0.1:5000';
const phase=process.argv[3]||'initial';
const report={phase,actions:[],requests:[],responses:[],screenshots:[],page_errors:[],http_errors:[],capture_errors:[],passed:false};
const save=()=>fs.writeFileSync(path.join(root,'trial-'+phase+'.json'),JSON.stringify(report,null,2));
const pending=new Set();
const flush=async()=>{while(pending.size)await Promise.allSettled([...pending]);};
const normalized=t=>{const p=String(t).replace('T',' ').split('.');return p[0]+'.'+(p[1]||'').padEnd(6,'0');};
const pairs=tasks=>tasks.map(t=>[t.operation_ref,t.piece_id||null,normalized(t.start),normalized(t.end)]).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b)));
(async()=>{
 const browser=await connect(chromium,ready.win7_evidence_root),context=await browser.newContext({viewport:{width:1920,height:1080}}),page=await context.newPage();
 page.setDefaultTimeout(60000);
 page.on('pageerror',e=>report.page_errors.push(e.message));
 page.on('request',r=>{if(r.url().includes('/api/workbench/'))report.requests.push({method:r.method(),url:r.url()});});
 page.on('response',response=>{
  if(!response.url().includes('/api/workbench/'))return;
  if(response.status()>=400)report.http_errors.push({url:response.url(),status:response.status()});
  if(!(response.headers()['content-type']||'').includes('json'))return;
  const task=(async()=>{try{report.responses.push({url:response.url(),status:response.status(),body:await response.json()});}catch(e){report.capture_errors.push({url:response.url(),error:e.message});}})();
  pending.add(task);task.finally(()=>pending.delete(task));
 });
 const shot=async name=>{const file=path.join(root,'screenshots',phase+'-'+name+'.png');await page.screenshot({path:file,timeout:15000});report.screenshots.push(file);save();};
 const step=async(name,fn)=>{const result={name,passed:false};report.actions.push(result);try{await fn();result.passed=true;console.log(name+': passed');}catch(e){result.error=e.stack;await shot('FAILED-'+name);throw e;}finally{save();}};
 const button=(name,scope=page)=>scope.getByRole('button',{name,exact:true});
 const h=require('./final_planning_probe_support.cjs').support(page,{root,url:origin},report,save,flush);
 let targets;
 try{
  if(phase==='initial'){
   await step('new-run-preflight-ten-tasks',async()=>{
    await page.goto(origin+'/workbench?view=run');await page.bringToFront();await page.waitForFunction(()=>document.fonts.status==='loaded',null,{timeout:30000});await button('选择批次').click();
    if(await button('清除选择').count()&&await button('清除选择').isEnabled())await button('清除选择').click();
    await page.getByRole('checkbox',{name:'选择 CAP-001',exact:true}).check();
    await page.getByLabel('计划开始日期',{exact:true}).fill('2026-09-28');await page.getByLabel('计划结束日期',{exact:true}).fill('2027-01-25');
    const response=page.waitForResponse(r=>r.url().endsWith('/scheduling/preflight')&&r.request().method()==='POST');
    await button('开始排产检查').click();const value=await (await response).json();assert.equal(value.data.tasks.length,10);await shot('preflight');
   });
   await step('new-real-worker-candidate',async()=>{
    await button('核对并开始排产').click();await button('确认开始排产',page.getByRole('dialog')).click();
    const table=page.getByRole('table',{name:'已保存候选',exact:true});await table.waitFor({timeout:300000});
    await table.getByRole('button',{name:'详情',exact:true}).first().click();await page.getByRole('table',{name:'候选任务安排',exact:true}).waitFor();await flush();
    const candidate=h.last(d=>d.candidate&&Array.isArray(d.tasks));assert.equal(candidate.tasks.length,10);
    report.candidate=candidate;await shot('candidate');
   });
   const config={isolated_test_database:true,run_ref:report.candidate.candidate.run_ref,candidate_ref:report.candidate.candidate.candidate_ref,expected_task_count:10};
   await require('./win7_trial_precision_steps.cjs').run({page,origin,root,repo,report,config,step,shot,flush,save});
   targets={...report.precision,pairs:pairs(report.candidate.tasks)};
   fs.writeFileSync(path.join(root,'trial-targets.json'),JSON.stringify(targets,null,2));
  }else targets=JSON.parse(fs.readFileSync(path.join(root,'trial-targets.json'),'utf8'));
  await step('reopen-saved-scenario-from-real-list',async()=>{
   await page.goto('about:blank');await page.goto(origin+'/workbench?view=trial');
   const tab=page.getByRole('tab',{name:'试调方案',exact:true});
   if(!await tab.isVisible())await button('草稿 / 试调方案列表').click();
   await tab.click();const row=page.getByRole('table',{name:'试调列表',exact:true}).getByRole('row').filter({hasText:'Win7 小数秒完整回归'});
   await button('打开',row).click();await page.locator('[data-trial-workspace][data-open-ref="'+targets.scenario_ref+'"]').waitFor();await flush();
   const current=h.last(d=>d.scenario_ref===targets.scenario_ref&&Array.isArray(d.tasks));assert.deepEqual(pairs(current.tasks),targets.pairs);await shot('scenario-reopened');
   await page.reload();await page.locator('[data-trial-workspace][data-open-ref="'+targets.scenario_ref+'"]').waitFor();await flush();
   assert.deepEqual(pairs(h.last(d=>d.scenario_ref===targets.scenario_ref&&Array.isArray(d.tasks)).tasks),targets.pairs);
  });
  await step('current-official-plan-ref-and-times-retained',async()=>{
   await page.goto(origin+'/workbench?view=gantt');await page.locator('[data-plan-workspace] .plan-main').waitFor();await flush();
   const plan=h.last(d=>d.plan&&Array.isArray(d.tasks));assert.equal(plan.plan.plan_ref,targets.trial_adopted_plan_ref);assert.deepEqual(pairs(plan.tasks),targets.pairs);await shot('current-official');
  });
  assert.deepEqual(report.page_errors,[]);assert.deepEqual(report.http_errors,[]);report.targets=targets;report.passed=true;
 }catch(error){report.error=error.stack;console.error(error);process.exitCode=1;}
 finally{await flush();save();await context.close();await browser.close();}
})().catch(error=>{report.error=error.stack;save();console.error(error);process.exitCode=1});
