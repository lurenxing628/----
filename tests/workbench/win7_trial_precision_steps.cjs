'use strict';
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
async function run(ctx){
 const {page,origin,root,repo,report,config,step,shot,flush,save}=ctx;
 assert(!config.readback_only, 'This probe must execute the complete workflow');
 assert.equal(config.isolated_test_database,true);
 assert.match(config.run_ref,/^[a-f0-9]{48}$/);assert.match(config.candidate_ref,/^[a-f0-9]{48}$/);
 page.setDefaultTimeout(120000);
 const h=require(path.join(repo,'tests/workbench/final_planning_probe_support.cjs')).support(page,{root,url:origin},report,save,flush);
 const button=(name,scope=page)=>scope.getByRole('button',{name,exact:true});
 const last=predicate=>{const row=report.responses.findLast(r=>r.body&&r.body.data&&predicate(r.body.data));assert(row,'Actual server DTO not captured');return row.body.data;};
 const normalized=time=>{const parts=String(time).replace('T',' ').split('.');return parts[0]+'.'+(parts[1]||'').padEnd(6,'0');};
 const pairs=tasks=>tasks.map(t=>[t.operation_ref,t.piece_id||null,normalized(t.start),normalized(t.end)]).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b)));
 report.precision={};const result=report.precision;let candidate,official,draft,original,editedTask;
 await step('open-new-candidate-with-fractional-times',async()=>{
  const nav={version:1,view:'run',context:{run_ref:config.run_ref}};
  assert((await page.goto(origin+'/workbench?view=run&nav='+encodeURIComponent(JSON.stringify(nav)))).ok());
  const row=page.getByRole('table',{name:'已保存候选',exact:true}).locator('[data-candidate-ref="'+config.candidate_ref+'"]');
  await button('详情',row).click();await page.getByRole('table',{name:'候选任务安排',exact:true}).waitFor();await flush();
  candidate=last(d=>d.candidate?.candidate_ref===config.candidate_ref&&Array.isArray(d.tasks));
  assert.equal(candidate.tasks.length,config.expected_task_count);
  result.fractional_task_count=candidate.tasks.filter(t=>/\.\d{6}$/.test(t.start)||/\.\d{6}$/.test(t.end)).length;
  assert(result.fractional_task_count>0);await shot('microsecond-candidate');
 });
 await step('adopt-complete-candidate-and-reload',async()=>{
  official=await h.confirmAdopt('candidate');assert.equal(official.tasks.length,config.expected_task_count);
  assert.deepEqual(pairs(official.tasks),pairs(candidate.tasks));result.adopted_plan_ref=official.plan.plan_ref;
  assert(official.projections.delivery_risks.items.every(r=>['on_time','overdue'].includes(r.risk)));
  await page.reload();await page.locator('[data-plan-workspace] .plan-main').waitFor();await flush();
  const reread=last(d=>d.plan?.plan_ref===official.plan.plan_ref&&Array.isArray(d.tasks));assert.deepEqual(pairs(reread.tasks),pairs(candidate.tasks));
  result.adoption_preserved_all_times=true;await shot('microsecond-official-reloaded');
 });
 await step('create-complete-trial-from-fractional-formal-plan',async()=>{
  draft=await h.createTrial(false);assert.equal(draft.tasks.length,config.expected_task_count);
  assert.deepEqual(pairs(draft.tasks),pairs(candidate.tasks));result.draft_ref=draft.draft_ref;
  const firstPage=draft.tasks.slice(0,50);editedTask=firstPage.find(t=>/\.\d{6}$/.test(t.start)&&Number(t.start.split('.')[1])<999998&&t.edit_context.can_change);
  assert(editedTask,'No editable fractional task on first task page');
  await button(editedTask.batch_id+' · '+editedTask.process_label+' '+editedTask.sequence,page.getByRole('table',{name:'完整任务明细',exact:true})).click();
  original=editedTask.start;await button('调整此工序',page.locator('.tt-detail')).click();
  assert.equal(await page.getByLabel('调整开工',{exact:true}).inputValue(),original);await shot('microsecond-trial-input');
 });
 async function changeStart(value){
  const field=page.getByLabel('调整开工',{exact:true});await field.fill(value);
  const response=page.waitForResponse(r=>r.url().includes('/trial/')&&r.request().method()==='POST');
  await button('保存调整').click();const reply=await response;if(!reply.ok())throw new Error(await reply.text());
  await button('调整此工序',page.locator('.tt-detail')).waitFor();await flush();
  draft=last(d=>d.draft_ref===result.draft_ref&&Array.isArray(d.tasks)&&!d.scenario_ref);
  const current=draft.tasks.find(t=>t.task_ref===editedTask.task_ref);assert(current);assert.equal(normalized(current.start),normalized(value));
 }
 await step('one-microsecond-change-is-preserved-then-restored',async()=>{
  const changed=original.split('.')[0]+'.'+String(Number(original.split('.')[1])+1).padStart(6,'0');
  await changeStart(changed);result.changed_start=changed;await shot('microsecond-trial-changed');
  await button('调整此工序',page.locator('.tt-detail')).click();await changeStart(original);
  assert.deepEqual(pairs(draft.tasks),pairs(candidate.tasks));result.microsecond_change_and_restore=true;
 });
 await step('invalid-date-stays-local-and-does-not-submit',async()=>{
  await button('调整此工序',page.locator('.tt-detail')).click();const field=page.getByLabel('调整开工',{exact:true});
  const before=report.requests.filter(r=>r.method==='POST').length;
  await field.fill('2026-02-30T08:00:00.000001');await button('保存调整').click();await page.getByText(/开工时间请按/).waitFor();await flush();
  assert.equal(report.requests.filter(r=>r.method==='POST').length,before);await shot('microsecond-invalid-date');
  await field.fill(original);await button('取消编辑').click();await button('调整此工序',page.locator('.tt-detail')).waitFor();result.invalid_date_not_submitted=true;
 });
 await step('save-and-adopt-complete-trial-with-exact-time-readback',async()=>{
  await button('保存试调方案').click();const dialog=page.getByRole('dialog',{name:'保存试调方案',exact:true});
  await dialog.getByLabel('试调方案名称',{exact:true}).fill('Win7 小数秒完整回归');await dialog.getByRole('checkbox').check();
  await button('确认保存试调方案',dialog).click();await dialog.waitFor({state:'hidden'});await flush();
  const saved=last(d=>d.scenario_ref&&Array.isArray(d.tasks));assert.deepEqual(pairs(saved.tasks),pairs(candidate.tasks));result.scenario_ref=saved.scenario_ref;
  const adopted=await h.confirmAdopt('trial');assert.deepEqual(pairs(adopted.tasks),pairs(candidate.tasks));result.trial_adopted_plan_ref=adopted.plan.plan_ref;
  result.saved_and_adopted_trial_preserved_times=true;await shot('microsecond-trial-adopted');
 });
 fs.writeFileSync(path.join(root,'precision-targets.json'),JSON.stringify(result,null,2));save();
}
module.exports={run};
