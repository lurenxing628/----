'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {select,openPicker}=require('./custom_control_actions.cjs');

async function post(page,suffix,click,status=200){
  const pending=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith(suffix)&&response.request().method()==='POST');
  await click();const response=await pending;assert.equal(response.status(),status,await response.text());return response.json();
}
async function receipt(page,suffix,name){
  const value=await post(page,suffix,()=>page.getByRole('dialog').getByRole('button',{name,exact:true}).click());
  assert(['committed','unchanged'].includes(value.result));await page.getByRole('dialog').getByText('服务器已确认提交。',{exact:true}).waitFor();return value;
}
async function calendar(page,state,helpers){
  const {run,close,type,shot,layout,recordExpected}=helpers;
  await page.locator('.hb-cal-block').click();await page.locator('.resource-calendar .cal-grid').waitFor();
  await run(page,state,'calendar-month-and-day',async()=>{
    const title=await page.locator('.resource-calendar .cal-title').innerText();
    await page.getByRole('button',{name:'下一月',exact:true}).click();await page.locator('.resource-calendar .cal-title').filter({hasNotText:title}).waitFor();
    await page.getByRole('button',{name:'上一月',exact:true}).click();await page.locator('.resource-calendar .cal-title').filter({hasText:title}).waitFor();
    await page.getByRole('button',{name:/^2026-09-10 默认规则/}).click();
    const fields=page.getByRole('dialog');
    await type(fields.getByLabel('可排工时（小时）',{exact:true}),'8.375');
    const precision=await post(page,'/calendar/upsert',()=>fields.getByRole('button',{name:'保存配置',exact:true}).click(),409);
    assert.equal(precision.committed,false);assert.equal(precision.error.code,'constraint_conflict');
    assert(precision.error.message.includes('分钟精度'));assert.equal(await fields.getByLabel('可排工时（小时）',{exact:true}).inputValue(),'8.375');
    recordExpected({path:'/api/workbench/v1/calendar/upsert',status:409,code:precision.error.code,kind:'subminute-rejected-without-rounding'});
    await type(fields.getByLabel('可排工时（小时）',{exact:true}),'8.4');
    await fields.getByRole('button',{name:'增加可排工时（小时）',exact:true}).click();
    assert.equal(await fields.getByLabel('可排工时（小时）',{exact:true}).inputValue(),'8.9');
    await fields.getByLabel('可排工时（小时）',{exact:true}).press('ArrowDown');
    await type(fields.getByLabel('效率（%）',{exact:true}),'62.5');
    await fields.getByRole('button',{name:'增加效率（%）',exact:true}).click();
    assert.equal(await fields.getByLabel('效率（%）',{exact:true}).inputValue(),'67.5');
    await fields.getByLabel('效率（%）',{exact:true}).press('ArrowDown');
    await receipt(page,'/calendar/upsert','保存配置');
    await page.getByText('已重新读取最新工作日历。',{exact:true}).waitFor();await close(page);
    await page.getByRole('button',{name:/^2026-09-10 单独配置/}).click();
    assert.equal(await page.getByRole('dialog').getByLabel('可排工时（小时）',{exact:true}).inputValue(),'8.4');
    assert.equal(await page.getByRole('dialog').getByLabel('效率（%）',{exact:true}).inputValue(),'62.5');
    await page.getByRole('dialog').getByRole('button',{name:'休息日',exact:true}).click();
    const conflict=await post(page,'/calendar/upsert',()=>page.getByRole('dialog').getByRole('button',{name:'保存配置',exact:true}).click(),409);
    assert.equal(conflict.committed,false);assert.equal(conflict.error.code,'constraint_conflict');assert(conflict.error.message.includes('班次起止'));
    recordExpected({path:'/api/workbench/v1/calendar/upsert',status:409,code:conflict.error.code,kind:'retained-shift-window-protected'});
    await close(page,{discard:true});await page.getByRole('button',{name:/^2026-09-10 单独配置/}).click();
    assert.equal(await page.getByRole('dialog').getByLabel('可排工时（小时）',{exact:true}).inputValue(),'8.4');
    await page.getByRole('button',{name:'清除配置',exact:true}).click();await receipt(page,'/calendar/delete','确认清除，恢复默认');await close(page);
    await page.getByRole('button',{name:/^2026-09-10 默认规则/}).click();await page.getByRole('dialog').getByRole('button',{name:'休息日',exact:true}).click();
    await shot(page,state+'-calendar-rest-draft');await receipt(page,'/calendar/upsert','保存配置');
    await page.getByText('已重新读取最新工作日历。',{exact:true}).waitFor();await close(page);
    await page.getByRole('button',{name:/^2026-09-10 单独配置/}).click();await page.getByRole('button',{name:'清除配置',exact:true}).click();
    await receipt(page,'/calendar/delete','确认清除，恢复默认');await close(page);
    await page.getByRole('button',{name:/^2026-09-10 默认规则/}).waitFor();await layout(page);
  });
  await run(page,state,'calendar-range-preview-confirm-clear',async()=>{
    for(const operation of ['upsert','delete']){
      await page.getByRole('button',{name:'批量维护',exact:true}).click();
      const dialog=page.getByRole('dialog',{name:'批量维护工作日历',exact:true}),start=dialog.locator('input[id$="-from"]'),end=dialog.locator('input[id$="-to"]');
      await start.fill('2027-01-03');
      const startPicker=await openPicker(start);await shot(page,state+'-calendar-custom-date');
      await startPicker.getByRole('button',{name:'选择月份',exact:true}).click();
      await startPicker.getByRole('gridcell',{name:'2027-02',exact:true}).click();
      assert.equal(await start.inputValue(),'2027-01-03');
      await startPicker.getByRole('button',{name:'选择月份',exact:true}).click();
      await startPicker.getByRole('gridcell',{name:'2027-01',exact:true}).click();
      await startPicker.getByRole('gridcell',{name:'2027-01-04',exact:true}).click();
      await end.fill('2027-01-09');
      const endPicker=await openPicker(end);await endPicker.getByRole('gridcell',{name:'2027-01-08',exact:true}).click();
      if(operation==='delete')await dialog.getByRole('button',{name:'清除配置，恢复默认',exact:true}).click();
      const preview=await post(page,'/calendar/range/preview',()=>dialog.getByRole('button',{name:'预览全部日期',exact:true}).click());
      assert.equal(preview.data.counts.selected,5);assert.equal(preview.data.days.length,5);
      const control=await dialog.getByRole('combobox',{name:'预览页码',exact:true}).evaluate(node=>({height:node.getBoundingClientRect().height,background:getComputedStyle(node).backgroundColor,theme:document.documentElement.dataset.theme}));
      assert.equal(control.height,32);if(control.theme==='dark')assert.notEqual(control.background,'rgb(255, 255, 255)');
      await shot(page,state+'-calendar-range-'+operation);await receipt(page,'/calendar/range/confirm','确认全部 5 天');await close(page);
    }
  });
}
async function catalog(page,state,helpers){
  const {run,close,type,rail,shot}=helpers;
  for(const [node,label,kind] of [['设备','设备组','machine_group'],['人员','班次','shift_profile']]){
    await run(page,state,'catalog-'+kind,async()=>{
      await rail(page,node);await page.getByRole('button',{name:'新增'+node,exact:true}).click();
      await page.getByRole('button',{name:'维护'+label,exact:true}).click();
      const modal=page.locator('.resource-catalog [role="dialog"]'),code='UI-CAT-'+state+'-'+kind;
      await modal.getByRole('button',{name:'新增'+(kind==='shift_profile'?'班次档':label),exact:true}).click();
      await type(modal.getByLabel('编号',{exact:true}),code);await type(modal.getByLabel('名称',{exact:true}),'UI '+label+' '+state);
      await select(modal.getByLabel('状态',{exact:true}),'active');
      if(kind==='shift_profile'){
        await modal.getByLabel('周期起始日期',{exact:true}).fill('2026-09-09');await type(modal.getByLabel('轮换天数',{exact:true}),'2');
        await modal.getByRole('button',{name:'生成逐日规则',exact:true}).click();
        await select(modal.getByLabel('第 1 天工作安排',{exact:true}),'work');
        await modal.getByLabel('第 1 天开始',{exact:true}).fill('21:14');
        const clock=await openPicker(modal.getByLabel('第 1 天开始',{exact:true}));
        await clock.getByRole('button',{name:'增加分',exact:true}).click();await shot(page,state+'-catalog-custom-time');
        await clock.getByRole('button',{name:'确定',exact:true}).click();await modal.getByLabel('第 1 天结束',{exact:true}).fill('05:15');
        await select(modal.getByLabel('第 2 天工作安排',{exact:true}),'rest');
      }
      await shot(page,state+'-catalog-filled-'+kind);await receipt(page,'/entities/'+kind+'/create','保存');
      await modal.getByRole('button',{name:'继续维护',exact:true}).click();await modal.getByRole('button',{name:'删除 '+code,exact:true}).click();
      const deleted=await receipt(page,'/delete','确认删除');assert(deleted.data.entity_ref);
      await modal.getByRole('button',{name:'完成并返回',exact:true}).click();await page.locator('.resource-catalog').waitFor({state:'detached'});
      await page.getByRole('dialog',{name:'新增'+node,exact:true}).waitFor();await close(page);
    });
  }
}
async function files(page,state,helpers,root,report){
  const {run,close,type,rail,search,shot,empty}=helpers;
  const code='UI-FILE-'+state;
  await rail(page,'物料');await search(page,'');await page.getByRole('button',{name:'MAT-001',exact:true}).waitFor();
  await run(page,state,'material-import-preview-and-confirm',async()=>{
    await page.getByRole('button',{name:'导入',exact:true}).click();const modal=page.getByRole('dialog');
    await modal.getByRole('button',{name:'CSV (.csv)',exact:true}).click();
    await modal.getByLabel('选择物料导入文件',{exact:true}).setInputFiles({name:'resource-input.csv',mimeType:'text/csv',buffer:Buffer.from('物料编号,名称,规格,单位,库存数量,状态,备注\n'+code+',Imported '+state+',D40,kg,4.5,active,Original imported note\n')});
    const preview=await post(page,'/imports/material/preview',()=>modal.getByRole('button',{name:'开始预检',exact:true}).click());
    assert.equal(preview.data.summary.new,1);assert.equal(preview.data.summary.rejected,0);await shot(page,state+'-import-preview');
    await receipt(page,'/imports/material/confirm','确认导入');await modal.getByRole('button',{name:'完成',exact:true}).click();await page.getByRole('dialog').waitFor({state:'detached'});
    await search(page,code);await page.getByRole('button',{name:code,exact:true}).waitFor();
  });
  await run(page,state,'material-export-and-bulk-delete',async()=>{
    await page.getByRole('checkbox',{name:'选择 '+code+' Imported '+state,exact:true}).check();
    await page.getByRole('button',{name:'导出',exact:true}).click();const modal=page.getByRole('dialog');
    await modal.getByRole('radio',{name:/已选物料/}).check();await modal.getByRole('button',{name:'CSV (.csv)',exact:true}).click();
    const preview=await post(page,'/exports/material/preview',()=>modal.getByRole('button',{name:'开始预检',exact:true}).click());assert.equal(preview.data.row_count,1);
    const waiting=page.waitForEvent('download');await modal.getByRole('button',{name:'下载文件',exact:true}).click();const download=await waiting;
    const file=path.join(root,'downloads',state+'-'+download.suggestedFilename());await download.saveAs(file);assert.equal(await download.failure(),null);
    const csv=fs.readFileSync(file,'utf8');assert(csv.includes(code));assert(csv.includes('Original imported note'));report.downloads.push(file);
    await modal.getByRole('button',{name:'完成',exact:true}).click();await page.getByRole('dialog').waitFor({state:'detached'});
    await page.getByRole('button',{name:'批量删除',exact:true}).click();
    const remove=await post(page,'/entities/material/bulk-preview',()=>page.getByRole('dialog').getByRole('button',{name:'开始预检',exact:true}).click());assert.equal(remove.data.rows.length,1);assert.equal(remove.data.summary.delete,1);
    await page.getByRole('checkbox',{name:'已核对完整删除范围及明细，确认删除这些物料。',exact:true}).check();
    const saved=await receipt(page,'/entities/material/bulk-confirm','确认删除');assert.equal(saved.data.deleted_count,1);
    await page.getByRole('dialog').getByRole('button',{name:'完成',exact:true}).click();await page.getByRole('dialog').waitFor({state:'detached'});
    await empty(page);
  });
}
module.exports={calendar,catalog,files};
