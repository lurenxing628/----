'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs');
const {chromium} = require('playwright');
const {Probe} = require('./final_master_probe_support.cjs');
const {focusTrap, originalFocus} = require('./final_master_modal_controls.cjs');
const ready = JSON.parse(fs.readFileSync(process.argv[2]));
const p = new Probe(ready, 'remaining_controls');
p.continueOnFailure = true;
p.report.scope_decisions = [];
const b = (scope, name) => scope.getByRole('button', {name, exact: true});
const shared = (family, index) => 'WBP-SH-' + family + '-C' + String(index).padStart(2, '0');
let page;
async function open(view) {
  await page.goto('about:blank');
  p.step('goto', '/workbench?view=' + view);
  await page.goto(ready.url + '/workbench?view=' + view);
  await page.locator('.sidebar').waitFor();
  await page.locator('.wb-table[aria-busy="false"]').first().waitFor();
}
async function processDetail() {
  await open('process');
  await p.click(page.locator('.hb-tile').filter({has: page.locator('.hb-tname').getByText('工艺', {exact: true})}));
  const scope = page.locator('[data-process-workspace]');
  await p.type(scope.getByRole('searchbox'), 'PROC-001');
  await p.response('/api/workbench/v1/entities/part', () => p.click(b(scope, '搜索')));
  const trigger = b(scope, '查看 PROC-001');
  await p.click(trigger);
  const parent = page.locator('.process-detail > .modal-bg [role="dialog"]');
  await parent.getByRole('tab', {name: /工艺路线/}).waitFor();
  await p.click(parent.getByRole('tab', {name: /工艺路线/}));
  await b(parent, '录入路线').waitFor();
  return {parent, trigger};
}
async function processFocus() {
  const {parent, trigger} = await processDetail();
  await focusTrap(page, p, parent);
  await p.click(b(parent, '关闭详情'));
  await parent.waitFor({state: 'detached'});
  await originalFocus(page, trigger);
}
async function nestedRoute() {
  const {parent, trigger} = await processDetail(), entry = b(parent, '录入路线');
  await p.click(entry);
  const child = page.getByRole('dialog', {name: '录入工艺路线 · PROC-001', exact: true});
  await child.getByRole('textbox', {name: '路线文字', exact: true}).waitFor();
  assert.equal(await parent.evaluate(node => getComputedStyle(node).visibility), 'hidden');
  assert.equal(await parent.getAttribute('aria-modal'), null);
  await focusTrap(page, p, child);
  await p.shot('route-child-focus');
  p.step('press', 'nested route dialog', 'Escape'); await page.keyboard.press('Escape');
  await child.waitFor({state: 'hidden'});
  await parent.waitFor({state: 'visible'});
  await originalFocus(page, entry);
  assert.equal(await parent.getAttribute('aria-modal'), 'true');
  await p.click(b(parent, '关闭详情'));
  await parent.waitFor({state: 'detached'});
  await originalFocus(page, trigger);
}
async function batchCountBoundary() {
  await open('batches');
  const waiting = page.waitForResponse(row => new URL(row.url()).pathname === '/api/workbench/v1/entities/batch/facets');
  await p.click(b(page.locator('[data-batch-workspace]'), '筛选数量'));
  const response = await waiting; assert.equal(response.status(), 200);
  const data = await response.json(), dialog = page.getByRole('dialog', {name: '筛选数量', exact: true});
  await b(dialog, '全选列值').waitFor();
  const expected = [...new Set(p.snapshot().tables.Batches.map(row => String(row.quantity)))].sort();
  assert.deepEqual(data.data.values.map(String).sort(), expected);
  const labels = await dialog.locator('.batch-value-list label').allTextContents();
  assert.deepEqual(labels.map(row => row.trim()).sort(), expected);
  p.report.scope_decisions.push({variant: p.variant, action_id: shared('006', 5),
    observed: {distinct_values: expected.length, labels, occurrence_counts_present: false},
    status: 'needs_main_scope_decision', reason: 'Actual batch-specific header shows values but no per-value occurrence counts. This is not a pass of a count display.',
    source: 'frontend/workbench/app/BatchTable.jsx:16'});
  await p.shot('batch-value-count-boundary');
  await p.click(b(dialog, '取消'));
}
async function masterHeaderBoundary() {
  await open('basedata');
  const table = page.getByRole('table', {name: '资料清单', exact: true});
  const expected = await table.locator('thead .mo-column').count();
  assert(expected > 1);
  assert.equal(await table.locator('thead button[aria-label^="筛选列 "]').count(), expected);
  assert.equal(await table.locator('.aps-th,.aps-fbtn,.aps-sort-btn,.wb-th-sort,.wb-th-filter').count(), 0);
  const trigger = table.locator('thead button[aria-label^="筛选列 "]').first();
  await p.click(trigger);
  const band = page.locator('.master-overview .mo-filter-band'); await band.waitFor();
  assert.equal(await page.getByRole('dialog').count(), 0);
  await originalFocus(page, band.getByRole('textbox', {name: '列包含文字', exact: true}));
  await p.shot('master-own-header-filter');
  await p.click(b(band, '关闭列筛选'));
  await band.waitFor({state: 'detached'});
  assert.equal(await table.locator('.aps-th,.aps-fbtn,.aps-sort-btn,.wb-th-sort,.wb-th-filter').count(), 0);
}
async function dateConstraintsAndDisabled() {
  await open('process');
  await p.click(page.locator('.hb-cal-block'));
  await page.locator('.resource-calendar .cal-grid').waitFor();
  await p.click(b(page, '批量维护'));
  const dialog = page.getByRole('dialog', {name: '批量维护工作日历', exact: true});
  const start = dialog.locator('input[id$="-from"]'), end = dialog.locator('input[id$="-to"]');
  await p.fill(start, '2027-01-04'); await p.fill(end, '2027-01-08');
  const constraints = await dialog.locator('input[type="date"]').evaluateAll(nodes => nodes.map(node =>
    ({id: node.id, min: node.min, max: node.max, readOnly: node.readOnly, disabled: node.disabled})));
  assert.equal(constraints.length, 2);
  assert(constraints.every(row => row.min === '' && row.max === '' && !row.readOnly && !row.disabled));
  p.report.scope_decisions.push({variant: p.variant, action_ids: [10, 11, 13].map(index => shared('008', index)),
    status: 'needs_main_scope_decision', observed: constraints,
    reason: 'Actual calendar date controls have no min/max/readOnly props; no attributes are injected to manufacture coverage.',
    source: 'frontend/workbench/app/CalendarRangeDialog.jsx:60'});
  let release, entered;
  const released = new Promise(resolve => { release = resolve; }), started = new Promise(resolve => { entered = resolve; });
  const pattern = '**/api/workbench/v1/calendar/range/preview';
  const hold = async route => { entered(); await released; await route.continue(); };
  await page.route(pattern, hold);
  const response = page.waitForResponse(row => new URL(row.url()).pathname === '/api/workbench/v1/calendar/range/preview');
  try {
    await p.click(b(dialog, '预览全部日期')); await started;
    await page.waitForFunction(() => {
      const nodes = Array.from(document.querySelectorAll('.calendar-range-dialog input[type="date"]')).filter(n => n.getClientRects().length);
      return nodes.length === 2 && nodes.every(n => n.disabled);
    });
    assert(await start.isDisabled() && await end.isDisabled());
    const rect = await start.boundingBox(); assert(rect);
    p.step('pointer-click', 'disabled calendar date icon', {x: rect.x + rect.width - 15, y: rect.y + rect.height / 2});
    await page.mouse.click(rect.x + rect.width - 15, rect.y + rect.height / 2);
    assert.equal(await page.locator('.wb-control-popup:visible').count(), 0);
    assert.equal(await start.inputValue(), '2027-01-04');
    await p.shot('real-request-date-disabled');
  } finally { release(); }
  const real = await response; assert.equal(real.status(), 200);
  await real.finished(); await page.unroute(pattern, hold);
  await p.click(b(dialog, '返回修改范围'));
  await page.waitForFunction(() => !document.querySelector('input[id$="-from"]').disabled);
  await p.click(b(dialog, '取消'));
}
async function main() {
  const browser = await chromium.launch({executablePath: process.env.WORKBENCH_BROWSER, headless: true});
  p.report.browser = browser.version(); assert(p.report.browser.startsWith('109.'));
  try {
    for (const [width, height] of [[1920, 1080], [1392, 924]]) for (const theme of ['light', 'dark']) {
      const context = await browser.newContext({viewport: {width, height}, timezoneId: 'Asia/Shanghai'});
      page = await context.newPage(); p.attach(page, width + 'x' + height + '-' + theme);
      await open('process'); if (theme === 'dark') await p.click(b(page, '切换深色'));
      const scenarios = [
        ['process-tab-focus-return', [shared('009', 11)], processFocus],
        ['process-route-nested-close', [shared('009', 12)], nestedRoute],
        ['master-own-header-boundary', [shared('006', 13)], masterHeaderBoundary],
        ['calendar-date-disabled', [shared('008', 12)], dateConstraintsAndDisabled],
        ['batch-count-boundary', [], batchCountBoundary]
      ];
      const selected = process.env.FINAL_MASTER_REMAINING_CASES ? process.env.FINAL_MASTER_REMAINING_CASES.split(',') : scenarios.map(row => row[0]);
      assert(selected.length && new Set(selected).size === selected.length && selected.every(name => scenarios.some(row => row[0] === name)));
      p.report.selected_scenarios = selected;
      for (const [name, actions, check] of scenarios) if (selected.includes(name)) await p.run(actions, name, check);
      await context.close();
    }
  } finally { await browser.close(); await Promise.all(p.pending); p.save(); }
  assert.equal(p.report.summary.failed, 0);
  assert.deepEqual(p.report.external, []);
  assert.deepEqual(p.report.errors.filter(row => !row.expected), []);
  console.log(JSON.stringify(p.report.summary));
}
main().catch(error => { p.report.fatal = error.stack; p.save(); console.error(error); process.exitCode = 1; });
