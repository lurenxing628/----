'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs');
const {chromium} = require('playwright');
const {Probe} = require('./final_master_probe_support.cjs');
const ready = JSON.parse(fs.readFileSync(process.argv[2])), p = new Probe(ready, 'domain_gaps');
p.continueOnFailure = true;
const ids = (family, numbers) => numbers.map(n => 'WBP-' + family + '-A' + String(n).padStart(2, '0'));
const b = (scope, name) => scope.getByRole('button', {name, exact: true});
let page;
async function open(view) {
  await page.goto('about:blank'); p.step('goto', '/workbench?view=' + view);
  await page.goto(ready.url + '/workbench?view=' + view);
  await page.locator('.wb-table[aria-busy="false"]').first().waitFor();
}
async function processPage() {
  await open('process');
  await p.response('/api/workbench/v1/entities/part', () => p.click(page.locator('.hb-tile').filter({has: page.locator('.hb-tname').getByText('工艺', {exact: true})})));
  return page.locator('[data-process-workspace]');
}
async function search(scope, query) {
  await p.type(scope.getByRole('searchbox'), query);
  return p.response('/api/workbench/v1/entities/part', () => p.click(b(scope, '搜索')));
}
async function processDetail(code) {
  const scope = await processPage(); await search(scope, code);
  await p.click(b(scope, '查看 ' + code));
  const parent = page.locator('.process-detail > .modal-bg [role="dialog"]');
  await parent.getByRole('tab', {name: /工艺路线/}).waitFor();
  return parent;
}
async function masterCounts() {
  await open('basedata');
  const area = page.getByRole('region', {name: '主数据总览', exact: true});
  const response = await p.response('/api/workbench/v1/master-overview', () => p.click(b(area, '刷新主数据')));
  await area.locator('.mo-table[aria-busy="false"]').waitFor();
  const overview = response.data.overview, tables = p.snapshot().tables;
  const withOperations = new Set(tables.PartOperations.map(row => row.part_no));
  const raw = {part: tables.Parts.length, route: tables.Parts.filter(row => withOperations.has(row.part_no) || typeof row.route_raw === 'string' && row.route_raw.trim()).length,
    opType: tables.OpTypes.length, equipment: tables.Machines.length, personnel: tables.Operators.length,
    material: tables.Materials.length, supplier: tables.Suppliers.length, calendar: tables.WorkCalendar.length};
  assert.equal(overview.domains.length, 8);
  for (const domain of overview.domains) {
    assert(domain.loaded); assert.equal(domain.count, raw[domain.id]);
    const tile = b(area, '查看数据域 ' + domain.label);
    assert.equal(await tile.locator('.wb-metric-value').innerText(), String(raw[domain.id]));
  }
  assert.equal(overview.stats.entities, Object.values(raw).reduce((sum, count) => sum + count, 0));
  assert.deepEqual(await area.locator('.mo-metrics .wb-metric-value').allTextContents(),
    ['entities', 'issues', 'affected', 'relations'].map(key => String(overview.stats[key])));
  p.report.all_domain_counts = (p.report.all_domain_counts || []).concat({variant: p.variant, raw, stats: overview.stats});
}
async function prerequisiteLocks() {
  const parent = await processDetail('PROC-001');
  await p.click(parent.getByRole('tab', {name: /工序归属/}));
  const source = parent.locator('[data-process-source-editor]:visible');
  await source.waitFor();
  assert(await source.getByRole('button', {name: /^检查归属/}).isDisabled());
  assert(await source.getByRole('checkbox', {name: '确认本页已核对工序', exact: true}).isDisabled());
  await p.shot('source-prerequisite-locked');
  await p.click(parent.getByRole('tab', {name: /工时定额/}));
  const hours = parent.locator('[data-process-hours-editor]:visible'); await hours.waitFor();
  assert(await hours.getByRole('button', {name: /^保存工时/}).isDisabled());
  assert(await hours.getByRole('checkbox', {name: '确认本页已核对工时', exact: true}).isDisabled());
  assert(await hours.getByLabel('工序 10 单件工时', {exact: true}).isDisabled());
  await p.shot('hours-prerequisite-locked'); await p.click(b(parent, '关闭详情'));
}
async function manualRows() {
  const parent = await processDetail('PROC-002');
  await p.click(parent.getByRole('tab', {name: /工艺路线/}));
  await p.click(b(parent, '录入路线'));
  const child = page.getByRole('dialog', {name: '录入工艺路线 · PROC-002', exact: true});
  await p.click(child.getByRole('tab', {name: '逐行表格', exact: true}));
  const table = child.getByRole('table', {name: '逐行路线录入', exact: true});
  assert.equal(await table.locator('tbody tr').count(), 1);
  await p.type(child.getByLabel('第 1 行工序号', {exact: true}), '10');
  await p.type(child.getByLabel('第 1 行工种', {exact: true}), '车削');
  await p.click(b(child, '添加工序'));
  await p.type(child.getByLabel('第 2 行工序号', {exact: true}), '30');
  await p.type(child.getByLabel('第 2 行工种', {exact: true}), '检验');
  await p.click(b(child, '添加工序')); assert.equal(await table.locator('tbody tr').count(), 3);
  await p.click(b(child, '删除第 3 行')); assert.equal(await table.locator('tbody tr').count(), 2);
  async function preview() {
    const waiting = page.waitForResponse(row => new URL(row.url()).pathname.endsWith('/route-preview'));
    await p.click(b(child, '预检路线')); const response = await waiting;
    assert.equal(response.status(), 200); return response.json();
  }
  let value = await preview();
  assert.deepEqual(value.data.operations.map(row => row.sequence), [10, 30]);
  assert.equal(value.data.counts.recognized, 2); assert(value.data.can_confirm_route);
  await p.shot('noncontinuous-route-sequences');
  await p.type(child.getByLabel('第 2 行工序号', {exact: true}), '10');
  value = await preview(); assert.equal(value.data.can_confirm_route, false);
  assert(value.data.diagnostics.some(row => row.code === 'duplicate_sequence'));
  assert(await child.getByRole('button', {name: /^确认保存路线/}).isDisabled());
  await p.shot('duplicate-route-rejected');
  await p.type(child.getByLabel('第 2 行工序号', {exact: true}), '30');
  await p.type(child.getByLabel('第 2 行工种', {exact: true}), 'C-MISSING-OPTYPE');
  value = await preview(); assert.equal(value.data.counts.unknown, 1);
  await child.getByRole('status').filter({hasText: /未识别 1/}).waitFor();
  await p.shot('unknown-route-summary');
  await p.click(b(child, '取消')); await p.click(b(parent, '关闭详情'));
  await p.click(b(page.getByRole('dialog', {name: '放弃未保存的工艺草稿？', exact: true}), '放弃草稿并关闭'));
  await parent.waitFor({state: 'detached'});
}
async function processMissing() {
  const scope = await processPage(), response = await search(scope, 'C-NO-SUCH-PART');
  assert.equal(response.data.page.total, 0);
  await scope.getByText('当前条件下没有零件。', {exact: true}).waitFor();
}
async function previousPage() {
  const scope = await processPage(); await search(scope, 'FC-P-');
  const next = await p.response('/api/workbench/v1/entities/part', () => p.click(b(scope, '下一页')));
  assert.equal(next.data.page.number, 2);
  const previous = await p.response('/api/workbench/v1/entities/part', () => p.click(b(scope, '上一页')));
  assert.equal(previous.data.page.number, 1);
  await b(scope, '查看 FC-P-001').waitFor();
}
async function main() {
  const browser = await chromium.launch({executablePath: process.env.WORKBENCH_BROWSER, headless: true});
  p.report.browser = browser.version(); assert(p.report.browser.startsWith('109.'));
  try {
    for (const [width, height] of [[1920, 1080], [1392, 924]]) for (const theme of ['light', 'dark']) {
      const context = await browser.newContext({viewport: {width, height}, timezoneId: 'Asia/Shanghai'});
      page = await context.newPage(); p.attach(page, width + 'x' + height + '-' + theme);
      await open('process'); if (theme === 'dark') await p.click(b(page, '深色：关'));
      for (const [name, actions, check] of [
        ['master-exact-eight-domains-four-metrics', ids('MD-001', [4, 5]), masterCounts],
        ['process-original-prerequisite-locks', ids('PROC-007', [2, 3]), prerequisiteLocks],
        ['route-rows-preview-boundaries', ids('PROC-006', [2, 3, 5, 6, 7, 8, 9, 10]), manualRows],
        ['process-no-matching-search', ids('PROC-003', [2]), processMissing],
        ['process-real-previous-page', ids('PROC-003', [4]), previousPage],
      ]) await p.run(actions, name, check);
      await context.close();
    }
  } finally { await browser.close(); await Promise.all(p.pending); p.save(); }
  assert.equal(p.report.summary.failed, 0); assert.deepEqual(p.report.external, []);
  assert.deepEqual(p.report.errors.filter(row => !row.expected), []);
  console.log(JSON.stringify(p.report.summary));
}
main().catch(error => { p.report.fatal = error.stack; p.save(); console.error(error); process.exitCode = 1; });
