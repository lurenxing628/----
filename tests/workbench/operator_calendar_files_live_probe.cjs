'use strict';
// 人员页上的「导入/导出个人日历」：模板、逐行的"整天按这里排"提示、只导勾选的人、导出回导不改事实。
// 只碰 RT-O 在 2027-03 的两天，跑完用「编辑个人日历」的范围清除清掉，不碰种子里 2026-09-09 那条。
const assert=require('node:assert/strict'),path=require('node:path');
const PREVIEW='/calendar-files/operator_calendar/preview',CONFIRM='/calendar-files/operator_calendar/confirm';
const EXPORT='/calendar-files/operator_calendar/export-preview';
const CODE='RT-O',FIRST='2027-03-01',SECOND='2027-03-02';
function csv(rows){const keys=Object.keys(rows[0]),cell=value=>'"'+String(value).replace(/"/g,'""')+'"';return [keys,...rows.map(row=>keys.map(key=>row[key]??''))].map(row=>row.map(cell).join(',')).join('\r\n');}
function row(code,date,type,start,end,eff,normal,urgent,note){
  return {'工号':code,'日期':date,'类型':type,'班次开始':start,'班次结束':end,
    '效率（%）':eff,'允许普通件':normal,'允许急件':urgent,'备注':note};
}
async function post(page,suffix,click){
  const response=page.waitForResponse(res=>new URL(res.url()).pathname.endsWith(suffix)&&res.request().method()==='POST');
  await click();const value=await response;assert.equal(value.status(),200,await value.text());return value.json();
}
async function dismiss(page,discard=false){
  await page.getByRole('dialog').getByRole('button',{name:/^(完成|取消|关闭)$/}).first().click();
  if(discard){const guard=page.getByRole('dialog',{name:'离开前确认',exact:true});await guard.waitFor();
    await guard.getByRole('button',{name:'放弃未保存内容并继续',exact:true}).click();}
  await page.getByRole('dialog').waitFor({state:'detached'});
}
async function save(page,dialog){
  const acknowledgement=dialog.locator('input[type="checkbox"]');
  if(await acknowledgement.count())await acknowledgement.check();
  const receipt=await post(page,CONFIRM,()=>dialog.getByRole('button',{name:'确认导入',exact:true}).click());
  assert(['committed','unchanged'].includes(receipt.result),JSON.stringify(receipt));await dismiss(page);return receipt;
}
async function upload(page,rows,file){
  await page.getByRole('button',{name:'导入个人日历',exact:true}).click();const dialog=page.getByRole('dialog');
  await dialog.getByRole('button',{name:'CSV (.csv)',exact:true}).click();
  await dialog.locator('input[type="file"]').setInputFiles(
    file||{name:'operator-calendar.csv',mimeType:'text/csv',buffer:Buffer.from(csv(rows))});
  const value=await post(page,PREVIEW,()=>dialog.getByRole('button',{name:'开始预检',exact:true}).click());
  return {dialog,data:value.data};
}
async function clearProbeDays(page){
  await page.getByRole('button',{name:CODE,exact:true}).click();
  await page.getByRole('dialog').getByRole('button',{name:'编辑个人日历',exact:true}).click();
  const panel=page.getByRole('dialog');
  await panel.locator('[data-operator-calendar-date]').first().waitFor();
  await panel.getByRole('button',{name:'按日期范围清除',exact:true}).click();
  await panel.locator('input[type="date"]').first().fill(FIRST);
  await panel.locator('input[type="date"]').last().fill(SECOND);
  const preview=await post(page,'/calendar/range-preview',
    ()=>panel.getByRole('button',{name:'预检要清除的日期',exact:true}).click());
  assert.equal(preview.data.count,2);
  const cleared=await post(page,'/calendar/range-clear',
    ()=>panel.getByRole('button',{name:'确认清除 2 天',exact:true}).click());
  assert.equal(cleared.data.cleared_count,2);
  await panel.getByText('保存已完成。',{exact:true}).waitFor();await dismiss(page);
}
async function operatorCalendarFiles(page,state,helpers,root,report){
  const {run,rail,search,shot}=helpers;
  await run(page,state,'operator-calendar-files-template-download',async()=>{
    await rail(page,'人员');await search(page,CODE);
    await page.getByRole('button',{name:'导入个人日历',exact:true}).click();
    const dialog=page.getByRole('dialog',{name:'批量导入 · 个人日历',exact:true});
    await dialog.waitFor();
    const waiting=page.waitForEvent('download');
    await dialog.getByRole('button',{name:'下载模板',exact:true}).click();
    const download=await waiting,file=path.join(root,'downloads',state+'-operator-calendar-'+download.suggestedFilename());
    await download.saveAs(file);assert.equal(await download.failure(),null);report.downloads.push(file);
    assert.equal(download.suggestedFilename(),'个人日历导入模板.xlsx');
    await shot(page,state+'-operator-calendar-import-blank');await dismiss(page);
  });
  await run(page,state,'operator-calendar-files-rejected-blocks-confirm',async()=>{
    // 工号不存在、以及上班的日子没填班次开始，都要挡住整批。
    const {dialog,data}=await upload(page,[row('RT-NOPE',FIRST,'工作日','09:00','','','','',''),
                                           row(CODE,SECOND,'工作日','','','','','','')]);
    assert.equal(data.summary.rejected,2);assert.equal(data.can_confirm,false);
    assert(await dialog.getByRole('button',{name:'确认导入',exact:true}).isDisabled());
    await shot(page,state+'-operator-calendar-import-rejected');await dismiss(page,true);
  });
  await run(page,state,'operator-calendar-files-import-overrides-the-rotation',async()=>{
    const {dialog,data}=await upload(page,[row(CODE,FIRST,'工作日','09:00','17:30','90','是','否','个人早班'),
                                           row(CODE,SECOND,'假期','','','','否','否','调休')]);
    assert.equal(data.summary.rejected,0);assert.equal(data.summary.new,2);
    assert(data.rows.every(item=>item.requires_confirmation));
    await dialog.getByText('这一天这个人整天按这里的安排排产，不再套用他的班次轮换，也不看全局工作日历。').first().waitFor();
    await shot(page,state+'-operator-calendar-import-preview');
    assert.equal((await save(page,dialog)).result,'committed');
  });
  await run(page,state,'operator-calendar-files-export-selected-people',async()=>{
    await page.getByRole('checkbox',{name:'选择 '+CODE+' Original operator',exact:true}).check();
    await page.getByRole('button',{name:'导出个人日历',exact:true}).click();
    const dialog=page.getByRole('dialog',{name:'批量导出 · 个人日历',exact:true});
    await dialog.getByRole('radio',{name:/已选人员/}).check();
    await dialog.locator('input[id$="-from"]').fill('2027-03-01');
    await dialog.locator('input[id$="-to"]').fill('2027-03-31');
    await dialog.getByRole('button',{name:'CSV (.csv)',exact:true}).click();
    const preview=await post(page,EXPORT,()=>dialog.getByRole('button',{name:'开始预检',exact:true}).click());
    // 只导出这段时间里单独设置过的日期；种子里 2026-09-09 那条不在范围内，所以正好两行。
    assert.equal(preview.data.row_count,2);
    assert.equal(preview.data.range.selected_refs.length,1);
    const downloading=page.waitForEvent('download');
    await dialog.getByRole('button',{name:'下载文件',exact:true}).click();
    const download=await downloading,file=path.join(root,'downloads',state+'-operator-calendar-'+download.suggestedFilename());
    await download.saveAs(file);assert.equal(await download.failure(),null);report.downloads.push(file);
    assert.equal(download.suggestedFilename(),'个人日历清单.csv');
    await shot(page,state+'-operator-calendar-export');await dismiss(page);
    const {dialog:back,data}=await upload(page,null,file);
    assert.equal(data.summary.rejected,0);assert.equal(data.summary.unchanged,2);
    assert.equal((await save(page,back)).result,'unchanged');
    await page.getByRole('button',{name:'清除所有选择',exact:true}).click();
  });
  await run(page,state,'operator-calendar-files-cleanup',async()=>{
    // 文件不做删除，取消特殊安排只能走人员详情里的范围清除，这也是模板说明里写给用户的做法。
    await clearProbeDays(page);
  });
}
module.exports={operatorCalendarFiles};
