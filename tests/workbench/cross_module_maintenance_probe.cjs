'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const {chromium} = require('playwright'), {select} = require('./custom_control_actions.cjs');
const ready = JSON.parse(fs.readFileSync(process.argv[2])), report = {cases: [], screenshots: [], errors: [], failed: 0};
let page, browser, serial = 0;
const button = (root, name) => root.getByRole('button', {name, exact: true});
const dialog = () => page.getByRole('dialog');
async function api(url, body) {
  const response = body ? await page.request.post(ready.url + '/api/workbench/v1/' + url, {data: body}) : await page.request.get(ready.url + '/api/workbench/v1/' + url);
  assert.equal(response.status(), 200, await response.text()); return response.json();
}
async function command(url, context, input) {
  return api(url, {request_key: 'cross-browser-command-' + (++serial), write_token: context.write_token, input});
}
async function saved(suffix, click) {
  const pending = page.waitForResponse(r => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(suffix));
  await click(); const response = await pending; assert.equal(response.status(), 200, await response.text());
  const result = await response.json(); assert(['committed', 'unchanged'].includes(result.result));
  return result;
}
async function close() {
  await dialog().locator('.modal-f').getByRole('button', {name: /^(关闭|完成)$/}).first().click();
  await dialog().waitFor({state: 'detached'});
}
async function resource(kind, code) {
  await page.goto(ready.resource_url);
  await page.locator('[data-rail-node="' + kind + '"]').click();
  await page.getByRole('searchbox', {name: '搜索编号或名称'}).fill(code);
  await button(page, '搜索').click(); await button(page, code).click();
}
async function shot(name) {
  const file = path.join(ready.root, name + '.png'); await page.screenshot({path: file, fullPage: true}); report.screenshots.push(file);
}
async function run(name, fn) {
  try { await fn(); report.cases.push(name); console.log('PASS ' + name); }
  catch (e) { report.failed++; report.error = e.stack; await shot('failure'); fs.writeFileSync(path.join(ready.root, 'failure-dom.txt'), await page.locator('body').innerText()); throw e; }
}
async function main() {
  browser = await chromium.launch({executablePath: process.env.WORKBENCH_BROWSER, headless: true});
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}, locale: 'zh-CN'});
  page = await context.newPage(); page.setDefaultTimeout(15000); page.on('pageerror', e => report.errors.push(e.message));
  await page.goto(ready.resource_url);
  await run('resource-stock-and-supplier-cycle-precision', async () => {
    await page.locator('[data-rail-node="material"]').click();
    const stock=page.locator('.wb-table tbody tr').filter({has:button(page,'MAT-001')});
    await stock.getByText('1.25 kg',{exact:true}).waitFor();
    await page.locator('[data-rail-node="supplier"]').click();
    const supplier=page.locator('.wb-table tbody tr').filter({has:button(page,'RT-S')});
    await supplier.getByText('3.25',{exact:true}).waitFor(); await shot('supplier-cycle-precision');
  });
  await run('downtime-create-edit-cancel', async () => {
    await resource('machine', 'RT-M'); await button(dialog(), '维护停机计划').click();
    await dialog().getByLabel('停机开始', {exact: true}).fill('2026-10-05T08:00');
    await dialog().getByLabel('停机结束', {exact: true}).fill('2026-10-05T10:00');
    await saved('/downtimes/create', () => button(dialog(), '保存停机计划').click());
    await dialog().getByText('已刷新停机记录。', {exact: true}).waitFor(); await shot('downtime-created'); await close();
    await button(page, 'RT-M').click(); await button(dialog(), '维护停机计划').click();
    await button(dialog(), '维护').click(); await dialog().getByLabel('停机结束', {exact: true}).fill('2026-10-05T11:00');
    await saved('/downtimes/update', () => button(dialog(), '保存停机计划').click()); await dialog().getByText('已刷新停机记录。', {exact: true}).waitFor(); await close();
    await button(page, 'RT-M').click(); await button(dialog(), '维护停机计划').click(); await button(dialog(), '维护').click();
    await button(dialog(), '取消这段停机').click(); await saved('/downtimes/cancel', () => button(dialog(), '确认取消这段停机').click());
    await dialog().getByText('已取消', {exact: true}).waitFor(); await close();
  });
  await run('personal-calendar-stale-draft-and-exact-efficiency', async () => {
    const people = await api('entities/operator?query=RT-O'); const ref = people.data.entities[0].ref;
    const now = new Date(), year = now.getFullYear(), month = now.getMonth()+1, day = year+'-'+String(month).padStart(2,'0')+'-15';
    const base = 'entities/operator/'+ref+'/calendar';
    let read = await api(base+'/month?year='+year+'&month='+month);
    const initial = {type:'work',shiftStart:'09:00',shiftEnd:'17:30',eff:87.654,allowNormal:'yes',allowUrgent:'yes',note:'原配置'};
    await command(base+'/upsert',read.data.write_context,{date:day,fields:initial});
    await resource('operator','RT-O'); await button(dialog(),'编辑个人日历').click(); await dialog().locator('[data-operator-calendar-date="'+day+'"]').click();
    assert.equal(await dialog().getByLabel('效率（%）',{exact:true}).inputValue(),'87.654');
    await dialog().getByLabel('备注',{exact:true}).fill('待保存备注');
    read = await api(base+'/month?year='+year+'&month='+month);
    await command(base+'/upsert',read.data.write_context,{date:day,fields:{...initial,shiftStart:'10:00',shiftEnd:'18:00',eff:80}});
    await button(dialog(),'刷新本月').click(); await button(dialog(),'采用最新配置并重新填写').waitFor();
    assert(await button(dialog(),'保存这一天').isDisabled()); await shot('calendar-stale-draft');
    await button(dialog(),'采用最新配置并重新填写').click(); assert.equal(await dialog().getByLabel('班次开始',{exact:true}).inputValue(),'10:00');
    await dialog().getByLabel('班次结束',{exact:true}).fill(''); await dialog().getByLabel('备注',{exact:true}).fill('新备注');
    await saved('/calendar/upsert',()=>button(dialog(),'保存这一天').click()); await close();
    const changed = (await api(base+'/month?year='+year+'&month='+month)).data.days.find(row=>row.date===day);
    assert.equal(changed.shift_start,'10:00'); assert.equal(changed.efficiency,.8);
  });
  await run('shift-rest-to-work-loads-editable-default-periods', async () => {
    await resource('operator','RT-O'); await button(dialog(),'编辑').click(); await button(dialog(),'维护班次').click();
    await button(dialog(),'新增班次档').click();
    await dialog().getByLabel('状态',{exact:true}).locator('option[value="active"]').waitFor({state:'attached'});
    await select(dialog().getByLabel('状态',{exact:true}),'active');
    await dialog().getByLabel('编号',{exact:true}).fill('CROSS-SH'); await dialog().getByLabel('名称',{exact:true}).fill('验证轮换');
    await dialog().getByLabel('周期起始日期',{exact:true}).fill('2026-10-01');
    await dialog().getByLabel('轮换天数',{exact:true}).fill('1'); await button(dialog(),'生成逐日规则').click();
    const arrangement=dialog().getByLabel('第 1 天工作安排',{exact:true});
    await arrangement.locator('option[value="rest"]').waitFor({state:'attached'});
    await select(arrangement,'rest'); await select(arrangement,'work');
    const period=(number,edge)=>dialog().getByLabel('第 1 天工作时段第 '+number+' 段'+edge,{exact:true});
    assert.equal(await period(1,'开始').inputValue(),'08:30'); assert.equal(await period(1,'结束').inputValue(),'11:50');
    assert.equal(await period(2,'开始').inputValue(),'13:30'); assert.equal(await period(2,'结束').inputValue(),'17:30');
    await period(1,'开始').fill('08:00'); await period(1,'结束').fill('12:00'); await period(2,'结束').fill('16:00');
    const created=await saved('/entities/shift_profile/create',()=>button(dialog(),'保存').click());
    const profile=(await api('entities/shift_profile/'+created.data.entity_ref)).data;
    assert.deepEqual(profile.fields.pattern[0].periods,[{start:'08:00',end:'12:00',day_offset:0},{start:'13:30',end:'16:00',day_offset:0}]);
    await button(dialog(),'完成并返回').click(); await button(dialog(),'取消').click();
  });
  await run('global-night-shift-hours-and-window-edit', async () => {
    await page.goto(ready.resource_url); await page.locator('[data-rail-node="calendar"]').click();
    await page.locator('[data-calendar-date="2026-09-09"]').click();
    assert.equal(await dialog().getByLabel('班次开始',{exact:true}).inputValue(),'22:30');
    await dialog().getByLabel('可排工时（小时）',{exact:true}).fill('9');
    await saved('/calendar/upsert',()=>button(dialog(),'保存配置').click());
    await dialog().getByText('已刷新，显示最新工作日历。',{exact:true}).waitFor(); await close();
    let day = (await api('calendar/month?year=2026&month=9')).data.days.find(row=>row.date==='2026-09-09');
    assert.equal(day.stored.shift_start,'22:30'); assert.equal(day.stored.shift_end,'07:30');
    await page.locator('[data-calendar-date="2026-09-09"]').click();
    await dialog().getByLabel('班次结束（空白按工时推算）',{exact:true}).fill('08:00');
    assert.equal(await dialog().getByLabel('可排工时（小时）',{exact:true}).inputValue(),'9.5');
    await shot('global-night-shift-edit'); await saved('/calendar/upsert',()=>button(dialog(),'保存配置').click());
    await dialog().getByText('已刷新，显示最新工作日历。',{exact:true}).waitFor(); await close();
  });
  await run('material-requirements-precision-and-save', async () => {
    let partList = await api('entities/part');
    const part = await command('process/parts/create',partList.data.create_context,{business_code:'CROSS-P',label:'验证零件',route_raw:'',remark:null});
    const list = await api('entities/batch');
    await command('entities/batch/create',list.data.create_context,{business_code:'CROSS-B',part_ref:part.data.entity_ref,fields:{quantity:5,due_date:'2028-01-01',priority:'normal',ready_status:'no',ready_date:null,remark:null}});
    await page.locator('.sidebar').getByText('批次管理',{exact:true}).click();
    const area=page.locator('[data-batch-workspace]'); await area.getByRole('searchbox').fill('CROSS-B'); await area.getByRole('searchbox').press('Enter');
    await button(area,'CROSS-B').click(); await button(area,'维护物料需求').click();
    const material = dialog().getByLabel('选择物料',{exact:true}); await material.locator('option').filter({hasText:'MAT-001'}).waitFor({state:'attached'});
    await select(material,{label:'MAT-001 · Material 1'}); await button(dialog(),'新增物料').click();
    await dialog().getByLabel('MAT-001需求量',{exact:true}).fill('12.375'); await dialog().getByLabel('MAT-001到料量',{exact:true}).fill('0.04');
    await saved('/materials_update',()=>button(dialog(),'核对并保存需求').click()); await close();
    await area.locator('summary').filter({hasText:'物料齐套原记录'}).click();
    const demand = area.getByRole('table',{name:'批次物料齐套',exact:true});
    await demand.getByText('12.375',{exact:true}).waitFor(); await demand.getByText('0.04',{exact:true}).waitFor(); await shot('batch-material-precision');
  });
  assert.deepEqual(report.errors, []);
}
main().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
  if(browser) await browser.close(); fs.writeFileSync(path.join(ready.root,'cross-module-browser.json'),JSON.stringify(report,null,2));
});
