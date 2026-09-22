'use strict';
// 日历页上的「导入/导出日历」：模板、假期加班提示、按日期范围导出、导出回导不改事实。
// 只碰 2027-03 这两天，跑完用批量维护清掉，数据库回到进入这段场景之前的样子。
const assert=require('node:assert/strict'),path=require('node:path');
const PREVIEW='/calendar-files/work_calendar/preview',CONFIRM='/calendar-files/work_calendar/confirm';
const EXPORT='/calendar-files/work_calendar/export-preview';
const FIRST='2027-03-01',SECOND='2027-03-02';
function csv(rows){const keys=Object.keys(rows[0]),cell=value=>'"'+String(value).replace(/"/g,'""')+'"';return [keys,...rows.map(row=>keys.map(key=>row[key]??''))].map(row=>row.map(cell).join(',')).join('\r\n');}
async function post(page,suffix,click){
  const response=page.waitForResponse(res=>new URL(res.url()).pathname.endsWith(suffix)&&res.request().method()==='POST');
  await click();const value=await response;assert.equal(value.status(),200,await value.text());return value.json();
}
async function dismiss(page){
  await page.getByRole('dialog').getByRole('button',{name:/^(完成|取消)$/}).first().click();
  await page.getByRole('dialog').waitFor({state:'detached'});
}
async function save(page,dialog){
  const acknowledgement=dialog.locator('input[type="checkbox"]');
  if(await acknowledgement.count())await acknowledgement.check();
  const receipt=await post(page,CONFIRM,()=>dialog.getByRole('button',{name:'确认导入',exact:true}).click());
  assert(['committed','unchanged'].includes(receipt.result),JSON.stringify(receipt));await dismiss(page);return receipt;
}
async function upload(page,rows){
  await page.getByRole('button',{name:'导入日历',exact:true}).click();const dialog=page.getByRole('dialog');
  await dialog.getByRole('button',{name:'CSV (.csv)',exact:true}).click();
  await dialog.locator('input[type="file"]').setInputFiles({name:'calendar.csv',mimeType:'text/csv',buffer:Buffer.from(csv(rows))});
  const value=await post(page,PREVIEW,()=>dialog.getByRole('button',{name:'开始预检',exact:true}).click());
  return {dialog,data:value.data};
}
function row(date,type,hours,eff,normal,urgent,note){
  return {'日期':date,'类型':type,'可排工时（小时）':hours,'效率（%）':eff,'允许普通件':normal,'允许急件':urgent,'备注':note};
}
async function calendarFiles(page,state,helpers,root,report){
  const {run,close,shot}=helpers;
  await run(page,state,'calendar-files-template-download',async()=>{
    await page.getByRole('button',{name:'导入日历',exact:true}).click();
    const dialog=page.getByRole('dialog',{name:'批量导入 · 工作日历',exact:true});
    await dialog.waitFor();
    const waiting=page.waitForEvent('download');
    await dialog.getByRole('button',{name:'下载模板',exact:true}).click();
    const download=await waiting,file=path.join(root,'downloads',state+'-calendar-'+download.suggestedFilename());
    await download.saveAs(file);assert.equal(await download.failure(),null);report.downloads.push(file);
    assert.equal(download.suggestedFilename(),'工作日历导入模板.xlsx');
    await shot(page,state+'-calendar-import-blank');await dismiss(page);
  });
  await run(page,state,'calendar-files-rejected-blocks-confirm',async()=>{
    const {dialog,data}=await upload(page,[row(FIRST,'工作日','25','','','','')]);
    assert.equal(data.summary.rejected,1);assert.equal(data.can_confirm,false);
    assert(await dialog.getByRole('button',{name:'确认导入',exact:true}).isDisabled());
    await shot(page,state+'-calendar-import-rejected');await dismiss(page);
  });
  await run(page,state,'calendar-files-import-with-holiday-overtime',async()=>{
    // 第二行是假期带工时：界面上设不出来，文件能存，但必须在预检里说明它会显示成工作日。
    const {dialog,data}=await upload(page,[row(FIRST,'工作日','8','100','是','是','调休上班'),
                                           row(SECOND,'假期','4','80','是','否','放假加班半天')]);
    assert.equal(data.summary.rejected,0);assert.equal(data.summary.new,2);
    assert.equal(data.rows[0].requires_confirmation,false);
    assert(data.rows[1].requires_confirmation&&data.rows[1].notes.some(note=>note.includes('工作日')));
    await dialog.getByText('这一天是假期但安排了工时，效率按排产设置里的假期效率算；日历页上会显示成工作日。').first().waitFor();
    await shot(page,state+'-calendar-import-preview');
    assert.equal((await save(page,dialog)).result,'committed');
  });
  await run(page,state,'calendar-files-export-round-trip',async()=>{
    await page.getByRole('button',{name:'导出日历',exact:true}).click();
    const dialog=page.getByRole('dialog');
    await dialog.locator('input[id$="-from"]').fill('2027-03-01');
    await dialog.locator('input[id$="-to"]').fill('2027-03-31');
    await dialog.getByRole('button',{name:'CSV (.csv)',exact:true}).click();
    const preview=await post(page,EXPORT,()=>dialog.getByRole('button',{name:'开始预检',exact:true}).click());
    // 只导出这段时间里单独配置过的日期，其余按默认规则走，不出现在文件里。
    assert.equal(preview.data.row_count,2);
    assert.deepEqual(preview.data.range,{start_date:'2027-03-01',end_date:'2027-03-31'});
    const downloading=page.waitForEvent('download');
    await dialog.getByRole('button',{name:'下载文件',exact:true}).click();
    const download=await downloading,file=path.join(root,'downloads',state+'-calendar-'+download.suggestedFilename());
    await download.saveAs(file);assert.equal(await download.failure(),null);report.downloads.push(file);
    assert.equal(download.suggestedFilename(),'工作日历清单.csv');
    await shot(page,state+'-calendar-export');await dismiss(page);
    await page.getByRole('button',{name:'导入日历',exact:true}).click();
    const back=page.getByRole('dialog');
    await back.getByRole('button',{name:'CSV (.csv)',exact:true}).click();
    await back.locator('input[type="file"]').setInputFiles(file);
    const again=await post(page,PREVIEW,()=>back.getByRole('button',{name:'开始预检',exact:true}).click());
    assert.equal(again.data.summary.rejected,0);assert.equal(again.data.summary.unchanged,2);
    assert.equal((await save(page,back)).result,'unchanged');
  });
  await run(page,state,'calendar-files-cleanup',async()=>{
    // 文件不做删除，恢复默认规则只能走批量维护里的清除，这也是模板说明里写给用户的做法。
    await page.getByRole('button',{name:'批量维护',exact:true}).click();
    const dialog=page.getByRole('dialog',{name:'批量维护工作日历',exact:true});
    await dialog.locator('input[id$="-from"]').fill(FIRST);
    await dialog.locator('input[id$="-to"]').fill(SECOND);
    await dialog.getByRole('button',{name:'清除单独设置，恢复默认',exact:true}).click();
    const preview=await post(page,'/calendar/range/preview',()=>dialog.getByRole('button',{name:'预览变更',exact:true}).click());
    assert.equal(preview.data.counts.selected,2);
    const confirmed=await post(page,'/calendar/range/confirm',()=>dialog.getByRole('button',{name:'确认全部 2 天',exact:true}).click());
    assert.equal(confirmed.result,'committed');
    await dialog.getByText('保存已完成。',{exact:true}).waitFor();await close(page);
  });
}
module.exports={calendarFiles};
