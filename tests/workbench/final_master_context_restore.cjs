'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require('playwright');
const {Probe} = require('./final_master_probe_support.cjs');
const ready = JSON.parse(fs.readFileSync(process.argv[2]));
const p = new Probe(ready, 'context_restore');
p.continueOnFailure = true;
p.report.contract = 'WBP-SH-003 actual workspace read scope, identity, F5, sidebar, back; no command replay';
p.report.contexts = [];
const b = (scope, name) => scope.getByRole('button', {name, exact: true});
const base = '/api/workbench/v1/master-overview';
let page;
async function settled(view) {
  await page.locator('.sidebar').waitFor();
  if (view === 'basedata') await page.locator('.mo-table[aria-busy="false"]').waitFor();
  else if (view === 'batches') await page.locator('[data-batch-workspace]').waitFor();
  else await page.locator('[data-resource-workspace]').waitFor();
}
async function open(view) {
  p.step('goto', '/workbench?view=' + view); await page.goto(ready.url + '/workbench?view=' + view);
  await settled(view);
}
async function sidebar(view) {
  await p.click(page.locator('.sidebar a[href*="view=' + view + '"]'));
  await settled(view); assert.equal(new URL(page.url()).searchParams.get('view'), view);
}
async function saved(matches, description) {
  await page.waitForFunction(({matches}) => {
    const current = history.state && history.state.workbench && history.state.workbench.context;
    if (!current) return false;
    return matches.every(([path, value]) => JSON.stringify(path.split('.').reduce((result, key) => result && result[key], current)) === JSON.stringify(value));
  }, {matches});
  const state = await page.evaluate(() => history.state.workbench);
  p.report.contexts.push({variant: p.variant, description, state});
  assert(!/"(?:request_key|write_token|create_context|write_context|snapshot_ref)"/.test(JSON.stringify(state.context)));
  return state.context;
}
async function sameContext(expected) {
  await page.waitForFunction(expected => {
    function stable(value) { return JSON.stringify(value && typeof value === 'object' ? Array.isArray(value) ? value.map(item => JSON.parse(stable(item)))
      : Object.fromEntries(Object.keys(value).sort().map(key => [key, JSON.parse(stable(value[key]))])) : value); }
    const actual = history.state && history.state.workbench && history.state.workbench.context;
    return !!actual && stable(actual) === stable(expected);
  }, expected);
  assert.deepEqual(await page.evaluate(() => history.state.workbench.context), expected);
}
async function refresh(view, expected, check) {
  p.step('reload', view); await page.reload(); await settled(view); await sameContext(expected); await check();
}
async function roundTrips(view, expected, check) {
  await refresh(view, expected, check);
  const other = view === 'batches' ? 'basedata' : 'batches';
  await sidebar(other); await sidebar(view); await sameContext(expected); await check();
  await sidebar(other); p.step('goBack', view); await page.goBack(); await settled(view); await sameContext(expected); await check();
}
async function rail(label) {
  await p.click(page.locator('.hb-tile').filter({has: page.locator('.hb-tname').getByText(label, {exact: true})}));
}
async function list(kind, action) {
  const waiting = page.waitForResponse(async response => ['/api/workbench/v1/entities/' + kind, '/api/workbench/v1/entities/' + kind + '/query'].includes(new URL(response.url()).pathname)
    && await response.finished() === null);
  const [response] = await Promise.all([waiting, action()]); assert.equal(response.status(), 200);
  const result = await response.json(); assert.equal(result.meta.source, 'production');
  await page.locator('.wb-table[aria-busy="false"]').waitFor(); return result;
}
async function resource() {
  await open('process'); await list('machine', () => rail('设备'));
  const scope = page.locator('[data-resource-workspace]');
  await p.type(scope.getByRole('searchbox', {name: '搜索编号或名称', exact: true}), 'FC-M-');
  await list('machine', () => p.click(b(scope, '搜索')));
  await list('machine', () => p.click(scope.locator('.wb-resource-th[data-column-key="business_code"] .wb-th-sort')));
  const result = await list('machine', () => p.click(b(scope, '下一页')));
  assert.equal(result.data.page.number, 2); assert.equal(result.data.page.total, 21);
  const entity = result.data.entities[0], checkbox = scope.getByRole('checkbox', {name: '选择 ' + entity.business_code + ' ' + entity.label, exact: true});
  await p.click(checkbox);
  const expected = await saved([['kind', 'machine'], ['read_view.scope.page', 2], ['read_view.scope.query', 'FC-M-'], ['read_view.selected_refs', [entity.ref]], ['read_view.sort_active', true]], 'resource-selected-page-2');
  const check = async () => { await checkbox.waitFor(); assert(await checkbox.isChecked()); assert.equal(await scope.getByRole('searchbox').inputValue(), 'FC-M-');
    await scope.getByText('第 2 / 2 页', {exact: true}).waitFor(); };
  await roundTrips('process', expected, check);
  await p.click(checkbox.locator('xpath=ancestor::tr').getByRole('button', {name: '查看/编辑', exact: true}));
  const dialog = page.getByRole('dialog', {name: '设备详情', exact: true}); await dialog.getByText(entity.business_code, {exact: true}).waitFor();
  const detail = await saved([['read_view.detail.entity_ref', entity.ref]], 'resource-readonly-detail');
  await refresh('process', detail, async () => { await dialog.getByText(entity.business_code, {exact: true}).waitFor(); });
  await p.shot('resource-detail-after-F5'); await p.click(dialog.locator('.modal-f').getByRole('button', {name: '关闭', exact: true}));
  await saved([['read_view.detail', null]], 'resource-detail-closed');
  await p.click(b(page, '新增设备'));
  const editor = page.getByRole('dialog', {name: '新增设备', exact: true});
  await p.type(editor.locator('input[name="business_code"]'), 'FC-UNSAVED-MACHINE');
  await refresh('process', expected, check); assert.equal(await page.getByRole('dialog').count(), 0);
}
async function processFlow() {
  await open('process'); await list('part', () => rail('工艺'));
  const scope = page.locator('[data-process-workspace]');
  await p.type(scope.getByRole('searchbox', {name: '搜索图号、名称、路线', exact: true}), 'FC-P-');
  await list('part', () => p.click(b(scope, '搜索')));
  await list('part', () => p.click(scope.locator('.wb-resource-th[data-column-key="business_code"] .wb-th-sort')));
  const result = await list('part', () => p.click(b(scope, '下一页'))); assert.equal(result.data.page.number, 2);
  const entity = result.data.entities[0], checkbox = scope.getByRole('checkbox', {name: '选择 ' + entity.business_code, exact: true});
  await p.click(checkbox);
  const expected = await saved([['kind', 'part'], ['read_view.scope.query', 'FC-P-'], ['read_view.scope.page', 2], ['read_view.selected_refs', [entity.ref]]], 'process-selected-page-2');
  const check = async () => { await checkbox.waitFor(); assert(await checkbox.isChecked()); await scope.getByText('第 2 / 3 页', {exact: true}).waitFor();
    assert.equal(await scope.getByRole('searchbox').inputValue(), 'FC-P-'); };
  await roundTrips('process', expected, check);
  await p.click(b(scope, '查看 ' + entity.business_code)); const dialog = page.getByRole('dialog');
  await dialog.getByRole('tablist', {name: '零件工艺步骤', exact: true}).waitFor();
  const detail = await saved([['read_view.entity_ref', entity.ref]], 'process-readonly-detail');
  await refresh('process', detail, async () => { await dialog.getByRole('tablist', {name: '零件工艺步骤', exact: true}).waitFor();
    assert((await dialog.innerText()).includes(entity.business_code)); });
}
async function batches() {
  await open('batches'); const scope = page.locator('[data-batch-workspace]');
  await scope.locator('.wb-table[aria-busy="false"]').waitFor();
  await p.type(scope.getByRole('searchbox', {name: '搜索批次号、图号、零件名', exact: true}), 'FC-B-');
  const first = await list('batch', () => p.click(b(scope, '搜索'))); assert.equal(first.data.page.total, 43);
  await list('batch', () => p.click(b(scope, '数量'))); await list('batch', () => p.click(b(scope, '数量')));
  const result = await list('batch', () => p.click(b(scope, '下一页')));
  const entity = result.data.entities[0], checkbox = scope.getByRole('checkbox', {name: '选择 ' + entity.business_code, exact: true}); await p.click(checkbox);
  const expected = await saved([['read_view.scope.query', 'FC-B-'], ['read_view.scope.page', 2], ['read_view.scope.direction', 'desc'], ['read_view.selected_refs', [entity.ref]]], 'batch-selected-page-2');
  const check = async () => { await checkbox.waitFor(); assert(await checkbox.isChecked()); await scope.getByText('第 2 / 3 页', {exact: true}).waitFor();
    assert.equal(await b(scope, '数量').locator('xpath=ancestor::th').getAttribute('aria-sort'), 'descending'); };
  await roundTrips('batches', expected, check);
  await p.click(checkbox.locator('xpath=ancestor::tr').getByRole('button', {name: '查看/编辑', exact: true}));
  await b(scope, '返回列表').waitFor(); const detail = await saved([['read_view.entity_ref', entity.ref]], 'batch-readonly-detail');
  await roundTrips('batches', detail, async () => { await scope.locator('[data-batch-detail="' + entity.ref + '"]').waitFor();
    await scope.getByRole('heading', {name: '批次详情 · ' + entity.business_code, exact: true}).waitFor(); });
  await p.click(b(scope, '返回列表')); await sameContext(expected); await p.click(b(scope, '新增批次'));
  const editor = page.getByRole('dialog', {name: '新增批次', exact: true}); await p.type(editor.getByLabel('批次号', {exact: true}), 'FC-UNSAVED-BATCH');
  await refresh('batches', expected, check); assert.equal(await page.getByRole('dialog').count(), 0);
}
async function calendar() {
  await open('process'); await p.response('/api/workbench/v1/calendar/month', () => p.click(page.locator('.hb-cal-block')));
  const scope = page.getByRole('region', {name: '工作日历', exact: true});
  for (let count = 0; count < 2; count++) await p.response('/api/workbench/v1/calendar/month', () => p.click(b(scope, '下一月')));
  const title = await scope.locator('.cal-title').innerText();
  const expected = await saved([['kind', 'calendar']], 'calendar-month'); assert(/^\d{4}-\d{2}$/.test(expected.month));
  await roundTrips('process', expected, async () => { await scope.locator('.cal-grid').waitFor(); assert.equal(await scope.locator('.cal-title').innerText(), title); });
}
async function overview() {
  await open('basedata'); const scope = page.locator('.master-overview');
  await p.response(base, () => p.click(scope.getByRole('tab', {name: /^资料清单/})));
  await p.response(base, () => p.select(scope.getByLabel('筛选资料类别'), 'part'));
  await p.type(scope.getByRole('searchbox', {name: '搜索基础资料', exact: true}), 'FC-P-');
  await p.response(base, () => p.click(b(scope, '执行基础资料搜索')));
  await p.response(base, () => p.select(scope.getByLabel('基础资料排序'), 'business_code'));
  await p.response(base, () => p.click(b(scope, '基础资料下一页')));
  await p.click(b(scope, '查看 FC-P-024'));
  await p.click(scope.locator('.mo-detail').getByRole('tab', {name: /^字段/}));
  await page.getByRole('tabpanel', {name: '资料项', exact: true}).waitFor();
  const expected = await saved([['read_view.scope.query', 'FC-P-'], ['read_view.page', 2], ['read_view.section', 'fields']], 'master-page-2-fields');
  const check = async () => { await b(scope, '查看 FC-P-024').waitFor(); await page.getByRole('tabpanel', {name: '资料项', exact: true}).waitFor();
    assert((await scope.locator('.mo-detail').innerText()).includes('FC-P-024')); assert.equal(await scope.getByRole('searchbox').inputValue(), 'FC-P-'); };
  await roundTrips('basedata', expected, check);
}
async function main() {
  const browser = await chromium.launch({executablePath: process.env.WORKBENCH_BROWSER, headless: true});
  p.report.browser = browser.version(); assert(p.report.browser.startsWith('109.'));
  try {
    for (const [width, height] of [[1920, 1080], [1392, 924]]) for (const theme of ['light', 'dark']) {
      const context = await browser.newContext({viewport: {width, height}, timezoneId: 'Asia/Shanghai'});
      page = await context.newPage(); p.attach(page, width + 'x' + height + '-' + theme); await open('batches');
      if (theme === 'dark') await p.click(b(page, '切换深色'));
      const scenarios = [['resource', resource], ['process', processFlow], ['batch', batches], ['calendar', calendar], ['master-overview', overview]];
      const selected = process.env.FINAL_MASTER_CONTEXT_CASES ? process.env.FINAL_MASTER_CONTEXT_CASES.split(',') : scenarios.map(row => row[0]);
      assert(selected.length && new Set(selected).size === selected.length && selected.every(name => scenarios.some(row => row[0] === name)));
      p.report.selected_scenarios = selected;
      for (const [name, action] of scenarios) if (selected.includes(name)) await p.run([], name + '-context-restoration', action);
      await context.close();
    }
  } finally { await browser.close(); await Promise.all(p.pending); p.save(); }
  assert.deepEqual(p.report.external, []); assert.equal(p.report.summary.failed, 0);
  assert.deepEqual(p.report.errors.filter(row => !row.expected), []);
  assert.deepEqual(p.report.requests.filter(row => !['GET', 'HEAD'].includes(row.method) && !/\/(query|facets)(?:\?|$)/.test(row.url)), []);
  console.log(JSON.stringify(p.report.summary));
}
main().catch(error => { p.report.fatal = error.stack; p.save(); console.error(error); process.exitCode = 1; });
