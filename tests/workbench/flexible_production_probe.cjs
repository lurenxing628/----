'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const {chromium} = require('playwright'), {openPicker, select} = require('./custom_control_actions.cjs');
const ready = JSON.parse(fs.readFileSync(process.argv[2])), report = {cases: [], screenshots: [], errors: [], failed: 0};
let page, browser;
const button = (root, name) => root.getByRole('button', {name, exact: true});
const dialog = () => page.getByRole('dialog');
async function api(url) {
  const response = await page.request.get(ready.url + '/api/workbench/v1/' + url);
  assert.equal(response.status(), 200, await response.text()); return response.json();
}
async function save(suffix, name) {
  const pending = page.waitForResponse(r => r.request().method() === 'POST' && new URL(r.url()).pathname.endsWith(suffix));
  await button(dialog(), name).click();
  const response = await pending; assert.equal(response.status(), 200, await response.text());
  assert(['committed', 'unchanged'].includes((await response.json()).result));
}
async function close() {
  await dialog().locator('.modal-f').getByRole('button', {name: '关闭', exact: true}).click();
  await dialog().waitFor({state: 'detached'});
}
async function shot(name) {
  const target = path.join(ready.root, name + '.png');
  await page.screenshot({path: target, fullPage: true, animations: 'disabled'}); report.screenshots.push(target);
}

async function profileRoundtrip() {
  const ref=(await api('entities/shift_profile?query=RT-SH')).data.entities[0].ref;
  async function edit() {
    await page.goto(ready.resource_url);await page.locator('[data-rail-node="operator"]').click();
    await button(page,'RT-O').click();await button(dialog(),'编辑').click();await button(dialog(),'维护班次').click();
    await button(dialog(),'编辑 RT-SH').click();
    await dialog().getByLabel('第 1 天工作安排',{exact:true}).locator('option[value="rest"]').waitFor({state:'attached'});
  }
  await edit();await button(dialog(),'分段设置工作时间').click();
  await dialog().getByLabel('第 1 天工作时段第 1 段开始',{exact:true}).fill('09:00');
  await dialog().getByLabel('第 1 天工作时段第 1 段结束',{exact:true}).fill('12:00');
  await button(dialog(),'新增工作时段').click();
  await dialog().getByLabel('第 1 天工作时段第 2 段开始',{exact:true}).fill('14:00');
  await dialog().getByLabel('第 1 天工作时段第 2 段结束',{exact:true}).fill('18:00');
  await save('/entities/shift_profile/'+ref+'/update','保存');
  const original=(await api('entities/shift_profile/'+ref)).data.fields.pattern;
  await button(dialog(),'完成并返回').click();await button(dialog(),'取消').click();
  await edit();await select(dialog().getByLabel('第 1 天工作安排',{exact:true}),'rest');
  await select(dialog().getByLabel('第 1 天工作安排',{exact:true}),'work');
  assert.equal(await dialog().getByLabel('第 1 天工作时段第 1 段开始',{exact:true}).inputValue(),'09:00');
  assert.equal(await dialog().getByLabel('第 1 天工作时段第 2 段结束',{exact:true}).inputValue(),'18:00');
  await dialog().getByLabel('备注',{exact:true}).fill('工作休息切换后核对');await shot('shift-rest-work-restored');
  await save('/entities/shift_profile/'+ref+'/update','保存');
  assert.deepEqual((await api('entities/shift_profile/'+ref)).data.fields.pattern,original);
  await button(dialog(),'完成并返回').click();await button(dialog(),'取消').click();
  report.cases.push('persisted-multi-period-rest-work-roundtrip');
}

async function flexibleInputs() {
  await page.goto(ready.resource_url); await page.locator('[data-rail-node="op_int"]').click();
  await button(page, 'RT-IN2').click(); await button(dialog(), '编辑').click();
  await select(dialog().getByLabel('适用归属', {exact:true}), 'both');
  await save('/entities/op_type/' + (await api('entities/op_type?category=internal&query=RT-IN2')).data.entities[0].ref + '/update', '保存');
  await close();
  await page.locator('[data-rail-node="machine"]').click(); await button(page, 'RT-M').click(); await button(dialog(), '编辑').click();
  await dialog().getByRole('group', {name:'可做工种', exact:true}).getByLabel('Inspection', {exact:true}).check();
  await shot('machine-multiple-work-types');
  const machines = (await api('entities/machine?query=RT-M')).data.entities;
  await save('/entities/machine/' + machines[0].ref + '/update', '保存'); await close();
  const machine = (await api('entities/machine/' + machines[0].ref)).data;
  assert.equal(machine.relationships.op_type_refs.length, 2);
  report.cases.push('dual-source-and-multiple-machine-capabilities');
  await page.locator('.sidebar').getByText('批次管理', {exact:true}).click();
  const area = page.locator('[data-batch-workspace]');
  await area.getByRole('searchbox').fill('FLEX-B'); await area.getByRole('searchbox').press('Enter');
  await button(area, 'FLEX-B').click(); await button(area, '维护物料需求').click();
  const materials = dialog().getByLabel('选择物料', {exact:true});
  await materials.locator('option').filter({hasText:'MAT-001'}).waitFor({state:'attached'});
  await select(materials, {label:'MAT-001 · Material 1'}); await button(dialog(), '新增物料').click();
  await dialog().getByLabel('MAT-001需求量', {exact:true}).fill('100');
  await dialog().getByLabel('MAT-001到料量', {exact:true}).fill('10');
  const original = (await api('entities/batch?query=FLEX-B')).data.entities.find(row => row.business_code === 'FLEX-B');
  const detail = (await api('entities/batch/' + original.ref)).data;
  await select(dialog().getByLabel('MAT-001使用工序', {exact:true}), detail.operations[1].ref);
  for (const [n, day, quantity] of [[1,'2026-09-28','30'],[2,'2030-01-01','60']]) {
    await button(dialog(), '新增一次到料').click();
    await dialog().getByLabel('MAT-001第'+n+'次到料日期', {exact:true}).fill(day);
    await dialog().getByLabel('MAT-001第'+n+'次到料数量', {exact:true}).fill(quantity);
  }
  await shot('material-stage-and-arrivals'); await save('/materials_update', '核对并保存需求'); await close();
  const stored = (await api('entities/batch/' + original.ref)).data.materials.requirements[0];
  assert.equal(stored.operation_ref, detail.operations[1].ref); assert.equal(stored.arrivals.length, 2);
  report.cases.push('stage-material-and-arrival-controls');
  await page.goto(ready.url + '/workbench?view=run');
  const scope = page.locator('[data-preflight-workspace]');
  await scope.getByLabel('计划开始日期', {exact:true}).fill('2026-09-28');
  await scope.getByLabel('计划结束日期', {exact:true}).fill('2026-10-10');
  await scope.getByRole('radiogroup', {name:'物料放行方式'}).getByLabel('预检分批开工', {exact:true}).check();
  await button(scope, '选择批次').click();
  await scope.getByRole('searchbox').fill('FLEX-B'); await scope.getByRole('searchbox').press('Enter');
  await scope.getByLabel('选择 FLEX-B', {exact:true}).check();
  await button(scope, '预检可开工数量').click();
  await dialog().getByText(/原有 100 件/).waitFor();
  assert((await dialog().innerText()).includes('先做 40 件'));
  await shot('quantity-split-preview');
  await button(dialog(), '取消').click();
  assert.equal((await api('entities/batch/' + original.ref)).data.fields.quantity, 100);
  await button(scope, '预检可开工数量').click();
  await save('/split-confirm', '确认拆分并选择可开工子批');
  await dialog().waitFor({state:'detached'});
  assert.equal((await api('entities/batch/' + original.ref)).data.fields.quantity, 60);
  await button(scope, '开始排产检查').click();
  await scope.getByText(/检查时间：/).waitFor();
  await shot('split-child-preflight'); report.cases.push('read-only-preview-cancel-confirm-and-recheck');
}

async function main() {
  browser = await chromium.launch({executablePath: process.env.WORKBENCH_BROWSER, headless: true});
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}, locale: 'zh-CN'});
  page = await context.newPage(); page.setDefaultTimeout(20000); page.on('pageerror', error => report.errors.push(error.message));
  await page.goto(ready.resource_url);
  await page.locator('[data-rail-node="calendar"]').click();
  await button(page, '修改默认工作时间').click();
  const begin = dialog().getByLabel('默认工作时段第 1 段开始', {exact: true});
  await begin.waitFor(); assert.equal(await begin.inputValue(), '08:30');
  assert.equal(await dialog().getByLabel('默认工作时段第 1 段结束', {exact: true}).inputValue(), '11:50');
  assert.equal(await dialog().getByLabel('默认工作时段第 2 段开始', {exact: true}).inputValue(), '13:30');
  assert.equal(await dialog().getByLabel('默认工作时段第 2 段结束', {exact: true}).inputValue(), '17:30');
  const popup = await openPicker(begin); await popup.waitFor({state: 'visible'});
  await page.keyboard.press('Escape'); await popup.waitFor({state: 'detached'});
  report.cases.push('existing-workbench-time-picker');
  for (const [label, value] of [['第 1 段开始','09:00'],['第 1 段结束','12:00'],['第 2 段开始','14:00'],['第 2 段结束','18:00']])
    await dialog().getByLabel('默认工作时段' + label, {exact: true}).fill(value);
  await shot('default-work-periods');
  await save('/calendar/defaults', '保存默认工作时间'); await close();
  const defaults = (await api('calendar/defaults')).data;
  assert.equal(defaults.hours, 7); assert.equal(defaults.periods[1].start, '14:00');
  await page.reload(); await page.locator('[data-rail-node="calendar"]').click();
  await page.getByText('09:00–12:00、14:00–18:00 · 7 小时', {exact: true}).waitFor();
  report.cases.push('editable-default-persists-and-refreshes');
  const title = await page.locator('.cal-title').innerText(), [year, month] = title.match(/\d+/g).map(Number);
  const scope = 'calendar/month?year=' + year + '&month=' + month;
  const day = (await api(scope)).data.days.find(row => !row.explicit && row.fields.hours === 7);
  assert(day); await page.locator('[data-calendar-date="' + day.date + '"]').click();
  await dialog().getByLabel('工作时段第 1 段结束', {exact: true}).fill('11:30');
  await save('/calendar/upsert', '保存配置'); await close();
  const configured = (await api(scope)).data.days.find(row => row.date === day.date);
  assert(configured.explicit); assert.equal(configured.fields.hours, 6.5);
  assert.equal(configured.fields.periods[0].end, '11:30'); assert.equal(configured.effective.windows.length, 2);
  report.cases.push('single-date-period-override');
  await page.locator('[data-calendar-date="' + day.date + '"]').click();
  await button(dialog(), '清除单独设置').click();
  await save('/calendar/delete', '确认清除，恢复默认'); await close();
  const restored = (await api(scope)).data.days.find(row => row.date === day.date);
  assert.equal(restored.explicit, false); assert.deepEqual(restored.fields.periods, defaults.periods);
  report.cases.push('clear-date-restores-configured-default');
  await shot('calendar-default-result'); await profileRoundtrip(); await flexibleInputs(); assert.deepEqual(report.errors, []);
}
main().catch(async error => {
  report.failed++; report.error = error.stack; process.exitCode = 1;
  if (page) { await shot('failure'); fs.writeFileSync(path.join(ready.root, 'failure-dom.txt'), await page.locator('body').innerText()); }
}).finally(async () => {
  fs.writeFileSync(path.join(ready.root, 'flexible-production-browser.json'), JSON.stringify(report, null, 2));
  if (browser) await browser.close();
});
