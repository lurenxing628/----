'use strict';
// 人员详情里的「编辑个人日历」：按天设班次、清除单天、按日期范围批量清除。
// 只动当前显示月里的两天，跑完用范围清除清掉，不碰种子里 RT-O 在 2026-09-09 的那条个人日历。
const assert=require('node:assert/strict');
async function post(page,suffix,click,status=200){
  const response=page.waitForResponse(res=>new URL(res.url()).pathname.endsWith(suffix)&&res.request().method()==='POST');
  await click();const value=await response;assert.equal(value.status(),status,await value.text());return value.json();
}
async function saved(page,panel,suffix,button){
  const receipt=await post(page,suffix,()=>panel.getByRole('button',{name:button,exact:true}).click());
  assert(['committed','unchanged'].includes(receipt.result),JSON.stringify(receipt));
  await panel.getByText('保存已完成。',{exact:true}).or(panel.getByText('删除已完成。',{exact:true})).first().waitFor();
  return receipt;
}
async function dismiss(page){
  // 保存完成后底部按钮从「关闭」变成「完成」，两种都要认。
  await page.getByRole('dialog').locator('.modal-f').getByRole('button',{name:/^(完成|关闭|取消)$/}).first().click();
  await page.getByRole('dialog').waitFor({state:'detached'});
}
async function reopen(page){
  // 每次保存后面板会停在"已完成"，关掉再从详情重新进，拿到刷新后的月视图。
  await dismiss(page);
  await page.getByRole('button',{name:'RT-O',exact:true}).click();
  await page.getByRole('dialog').getByRole('button',{name:'编辑个人日历',exact:true}).click();
  const panel=page.getByRole('dialog');
  await panel.locator('[data-operator-calendar-date]').first().waitFor();
  return panel;
}
async function operatorCalendar(page,state,helpers,root,report){
  const {run,rail,search,shot}=helpers;
  let first,second;
  await run(page,state,'operator-calendar-set-one-day',async()=>{
    await rail(page,'人员');await search(page,'RT-O');
    await page.getByRole('button',{name:'RT-O',exact:true}).click();
    await page.getByRole('dialog').getByRole('button',{name:'编辑个人日历',exact:true}).click();
    const panel=page.getByRole('dialog');
    await panel.locator('[data-operator-calendar-date]').first().waitFor();
    const dates=await panel.locator('[data-operator-calendar-date]').evaluateAll(
      nodes=>nodes.map(node=>node.dataset.operatorCalendarDate));
    assert(dates.length >= 28);
    first=dates[0];second=dates[1];
    await panel.locator('[data-operator-calendar-date="'+first+'"]').click();
    await panel.getByLabel('班次开始',{exact:true}).fill('09:00');
    await panel.getByLabel('班次结束',{exact:true}).fill('17:30');
    await panel.getByLabel('效率（%）',{exact:true}).fill('90');
    await panel.getByLabel('备注',{exact:true}).fill('个人早班');
    await shot(page,state+'-operator-calendar-day');
    await saved(page,panel,'/calendar/upsert','保存这一天');
  });
  await run(page,state,'operator-calendar-shows-the-saved-shift',async()=>{
    const panel=await reopen(page);
    // 工时由班次起止算出来，格子上直接显示这一天几点到几点。
    await panel.locator('[data-operator-calendar-date="'+first+'"]').getByText('09:00–17:30',{exact:true}).waitFor();
    await panel.locator('[data-operator-calendar-date="'+first+'"]').click();
    assert.equal(await panel.getByLabel('效率（%）',{exact:true}).inputValue(),'90');
    // 清除走两步：先点「清除单独设置」进入确认，再点「确认清除，恢复默认」才真正提交。
    await panel.getByRole('button',{name:'清除单独设置',exact:true}).click();
    await saved(page,panel,'/calendar/delete','确认清除，恢复默认');
  });
  await run(page,state,'operator-calendar-range-clear',async()=>{
    let panel=await reopen(page);
    await panel.locator('[data-operator-calendar-date="'+first+'"]').getByText('按班次',{exact:true}).waitFor();
    for(const day of [first,second]){
      await panel.locator('[data-operator-calendar-date="'+day+'"]').click();
      await panel.getByLabel('班次开始',{exact:true}).fill('07:00');
      await panel.getByLabel('班次结束',{exact:true}).fill('15:00');
      await saved(page,panel,'/calendar/upsert','保存这一天');
      panel=await reopen(page);
    }
    await panel.getByRole('button',{name:'按日期范围清除',exact:true}).click();
    await panel.locator('input[type="date"]').first().fill(first);
    await panel.locator('input[type="date"]').last().fill(second);
    const preview=await post(page,'/calendar/range-preview',
      ()=>panel.getByRole('button',{name:'预检要清除的日期',exact:true}).click());
    assert.equal(preview.data.count,2);
    await shot(page,state+'-operator-calendar-range');
    const cleared=await post(page,'/calendar/range-clear',
      ()=>panel.getByRole('button',{name:'确认清除 2 天',exact:true}).click());
    assert.equal(cleared.data.cleared_count,2);
    await panel.getByText('保存已完成。',{exact:true}).waitFor();
    const back=await reopen(page);
    for(const day of [first,second])
      await back.locator('[data-operator-calendar-date="'+day+'"]').getByText('按班次',{exact:true}).waitFor();
    await dismiss(page);
  });
}
module.exports={operatorCalendar};
