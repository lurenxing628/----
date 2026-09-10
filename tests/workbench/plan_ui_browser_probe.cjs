'use strict';
// Actual Chrome109 + current UI sources + injected adapters; not live backend proof.
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const { chromium } = require('playwright'), H = require('./plan_ui_browser_harness.cjs');
const F = require('./plan_ui_fixtures.cjs');
const output = path.resolve(process.argv[2] || '');
assert(process.argv[2] && output !== H.root && !output.startsWith(H.root + path.sep), 'Pass a temporary artifact directory outside checkout');
fs.mkdirSync(output, { recursive: true });
const report = { scope: 'plan-ui-component-mock', data_source: 'in-memory-fixture', production_persistence_tested: false, win7_hardware_tested: false,
  cases: [], screenshots: [], errors: [], external: [], unexpected_requests: [], geometry: [], downloads: [], assertions: 0 };
let state;
function ok(value, message) { report.assertions++; assert.ok(value, message); }
function equal(actual, expected, message) { report.assertions++; assert.deepEqual(actual, expected, message); }
async function settle(page) {
  await page.evaluate(async () => { await document.fonts.ready; await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))); });
}
async function mount(page, spec = {}) {
  await page.evaluate(spec => mountPlan(spec), { theme: state.theme, ...spec });
  await page.getByRole('table', { name: '可选排产方案' }).waitFor(); await settle(page);
}
const ready = page => page.locator('[data-plan-gantt]').waitFor();
async function choose(page, name = '正式排产计划 1') { await page.getByRole('radio', { name: '选择 ' + name, exact: true }).check(); await ready(page); await settle(page); }
async function shot(page, name) {
  await settle(page); const filename = path.join(output, state.id + '-' + name + '.png'); await page.screenshot({ path: filename }); report.screenshots.push(filename);
}
async function layout(page) {
  await settle(page);
  const value = await page.evaluate(() => {
    const box = element => { const r = element.getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height }; };
    const board = document.querySelector('[data-plan-scroll]'), main = document.querySelector('.plan-main'), inspector = document.querySelector('[data-plan-inspector]');
    const buttons = Array.from(document.querySelectorAll('.plan-icon')).map(button => ({ name: button.getAttribute('aria-label'), icon: !!button.querySelector('svg > *'), box: box(button) }));
    const grid = document.querySelector('.plan-gridline'), tick = document.querySelector('.plan-tick');
    return { viewport: innerWidth, document: document.documentElement.scrollWidth, body: document.body.scrollWidth, main: box(main), inspector: box(inspector), board: box(board), buttons,
      tick: tick && box(tick), grid: grid && box(grid), corner: box(document.querySelector('.plan-corner')),
      search: box(document.querySelector('.plan-search')), searchIcon: box(document.querySelector('.plan-search .ic')),
      segmentColors: Array.from(document.querySelectorAll('.plan-gantt .plan-segment button')).map(button => ({ pressed: button.getAttribute('aria-pressed'), fill: getComputedStyle(button).backgroundColor })),
      cornerSmall: box(document.querySelector('.plan-corner small')),
      facesContained: Array.from(document.querySelectorAll('.plan-bar-face')).every(face => { const a = box(face), b = box(face.parentElement); return a.left >= b.left - 0.1 && a.right <= b.right + 0.1 && a.top >= b.top - 0.1 && a.bottom <= b.bottom + 0.1; }),
      bars: document.querySelectorAll('[data-plan-task]').length, rows: document.querySelectorAll('.plan-lane').length,
      transparentCanvases: Array.from(document.querySelectorAll('.plan-global canvas,.plan-row-canvas')).filter(canvas => {
        const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data; for (let i = 3; i < pixels.length; i += 4) if (pixels[i]) return false; return true;
      }).length };
  });
  ok(value.document <= value.viewport + 1 && value.body <= value.viewport + 1, 'No document horizontal overflow: ' + JSON.stringify(value));
  ok(value.inspector.right <= value.viewport + 1, 'Inspector inside viewport');
  ok(value.board.right <= value.inspector.left + 1 || value.board.bottom <= value.inspector.top + 1, 'Timeline and inspector do not overlap');
  ok(value.buttons.every(button => button.icon), 'All icon tools have real bundled icons: ' + JSON.stringify(value.buttons));
  ok(value.buttons.every(button => button.box.width >= 30 && button.box.height >= 30), 'Stable icon dimensions');
  if (value.tick && value.grid) ok(Math.abs(value.tick.left - value.grid.left) <= 1, 'Ticks and grid share coordinates');
  equal(value.transparentCanvases, 0, 'Rendered chart canvases must contain pixels');
  ok(value.searchIcon.top >= value.search.top && value.searchIcon.bottom <= value.search.bottom, 'Search icon inside input row');
  ok(value.segmentColors.find(item => item.pressed === 'true').fill !== value.segmentColors.find(item => item.pressed === 'false').fill, 'Active segment visually distinct');
  ok(value.cornerSmall.bottom <= value.corner.bottom, 'Small header text cannot overlap first resource row');
  ok(value.facesContained, 'Bar paint and border stay inside exact-duration slots');
  report.geometry.push({ state: state.id, ...value });
}
async function run(page, name, action) {
  const row = { state: state.id, name, passed: false }, before = report.assertions; report.cases.push(row);
  try { await action(); equal(await page.evaluate(() => fixture.writes), 0, 'No mock write command attempted'); row.passed = true; }
  catch (error) { row.error = error.stack; await shot(page, 'FAILED-' + name); }
  row.assertions = report.assertions - before; console.log(state.id + ' / ' + name + ': ' + (row.passed ? 'passed' : 'FAILED'));
}
async function interactive(page) {
  await run(page, 'catalog-select-and-real-views', async () => {
    await mount(page); await page.getByRole('radio', { name: '选择 正式排产计划 1', exact: true }).waitFor();
    equal(await page.evaluate(() => fixture.calls.filter(row => row.type === 'workspace').length), 0, 'No automatic latest selection');
    ok(await page.getByRole('radio', { name: '选择 损坏记录仍保留' }).isDisabled(), 'Unavailable identity remains listed and disabled');
    await choose(page); equal(await page.locator('[data-plan-search-count]').textContent(), '36 / 36 道安排');
    ok(await page.getByRole('checkbox', { name: '显示初始基线' }).isDisabled(), 'Ordinary plans must not synthesize a baseline');
    equal(await page.getByRole('button', { name: /^采用方案/ }).count(), 0, 'Removed permanent adoption placeholder stays absent');
    await layout(page); await shot(page, 'analysis-light-or-dark');
    await page.getByRole('group', { name: '甘特分组' }).getByRole('button', { name: '人员', exact: true }).click();
    await page.waitForFunction(() => document.querySelector('.plan-corner').textContent.startsWith('人员 / 工序'));
    await page.getByRole('group', { name: '甘特分组' }).getByRole('button', { name: '批次', exact: true }).click();
    await page.waitForFunction(() => document.querySelector('.plan-corner').textContent.startsWith('批次 / 工序'));
    await page.getByRole('group', { name: '甘特分组' }).getByRole('button', { name: '设备', exact: true }).click();
    await page.getByRole('button', { name: '收起计划目录', exact: true }).click();
    await page.locator('[data-plan-task]').first().click();
    ok((await page.locator('[data-plan-inspector]').textContent()).includes('时间跨度'));
    ok(await page.getByRole('button', { name: /^调整此工序：/ }).isDisabled());
    ok(await page.getByRole('button', { name: /^保存：/ }).count() === 0, 'Read-only plan details cannot expose a save placeholder');
    await page.getByRole('button', { name: '资源负荷', exact: true }).click();
    await page.getByRole('table', { name: '资源负荷列表' }).waitFor(); await shot(page, 'selected-task-load');
    await page.getByRole('button', { name: '资源日历', exact: true }).click();
    await page.getByRole('table', { name: '资源日历列表' }).getByRole('button', { name: '1 段', exact: true }).first().click();
    ok((await page.getByRole('table', { name: '资源日历列表' }).textContent()).includes('普通允许'));
    await page.getByRole('button', { name: '查看甘特', exact: true }).click(); await ready(page);
    equal(await page.evaluate(() => fixture.navigations.at(-1).next), 'gantt');
    ok((await page.evaluate(() => fixture.navigations.at(-1).context.snapshot_ref)).startsWith('workspace-ui:'), 'Navigate with workspace snapshot');
    await layout(page); await shot(page, 'gantt-page');
  });
  await run(page, 'catalog-cursor-does-not-reselect', async () => {
    await mount(page); await choose(page);
    await page.getByRole('button', { name: '计划目录下一段', exact: true }).click(); await page.getByRole('radio', { name: '选择 正式排产计划 40', exact: true }).waitFor();
    const call = await page.evaluate(() => fixture.calls.filter(row => row.type === 'catalog').at(-1)); equal(call.scope, { collection: 'history', size: 20, cursor: 'next:history', snapshot_ref: 'catalog-ui-snapshot' });
    await page.getByRole('button', { name: '计划目录上一段', exact: true }).click(); await page.getByRole('radio', { name: '选择 正式排产计划 1', exact: true }).waitFor();
    await page.getByRole('button', { name: '刷新计划目录', exact: true }).click();
    await page.getByRole('button', { name: '已存场景', exact: true }).click(); await page.getByRole('radio', { name: '选择 夜班调整场景 3', exact: true }).waitFor();
    equal(await page.evaluate(() => fixture.calls.filter(row => row.type === 'workspace').length), 1, 'Collection, page and refresh retain selected plan');
    ok(!(await page.locator('.plan-catalog').textContent()).includes('总页'));
    await choose(page, '夜班调整场景 3');
    await page.getByRole('checkbox', { name: '显示初始基线' }).check();
    await page.locator('[data-before=true]').first().waitFor();
    const scopeText = await page.locator('.plan-global-labels').textContent(); ok(scopeText.includes('2026-09-09 20:30:00'), 'Baseline moves start earlier, no clipping');
    await page.locator('[data-before=true]').first().click();
    ok((await page.locator('[data-plan-inspector]').textContent()).includes('初始计划安排')); await shot(page, 'scenario-baseline');
  });
  await run(page, 'zoom-search-hover-boundaries', async () => {
    await mount(page); await choose(page); await page.getByRole('button', { name: '收起计划目录' }).click();
    const bar = page.locator('[data-plan-task]').first(), ref = await bar.getAttribute('data-plan-task');
    const before = await bar.boundingBox(); await bar.hover(); await page.getByRole('tooltip').waitFor();
    ok((await page.getByRole('tooltip').textContent()).includes('2026-09-09 22:30:00')); await bar.click();
    const selected = await bar.boundingBox(); equal(selected.width, before.width, 'Selection does not inflate real duration');
    await page.getByRole('button', { name: '放大时间轴' }).click(); await page.getByRole('button', { name: '定位选中任务' }).click(); await settle(page);
    const zoomed = await page.locator('[data-plan-task="' + ref + '"]').boundingBox(); ok(Math.abs(zoomed.width - 2 * before.width) < 1, 'Zoom proportional to time');
    await page.locator('[data-plan-scroll]').evaluate(node => { node.scrollLeft = node.scrollWidth / 3; node.scrollTop = 100; }); await settle(page);
    await layout(page);
    const global = await page.locator('.plan-global-labels').textContent();
    await page.getByRole('searchbox').fill('D2609-012'); await page.getByRole('searchbox').press('Enter');
    ok((await page.locator('[data-plan-inspector]').textContent()).includes('D2609-012'));
    equal(await page.locator('.plan-global-labels').textContent(), global, 'Client search preserves complete time range');
    await page.getByRole('button', { name: '适合完整跨度' }).click(); await settle(page);
    equal(await page.locator('[data-plan-scroll]').evaluate(node => node.scrollLeft), 0);
    await shot(page, 'search-fit');
    await page.getByRole('searchbox').fill('不存在的安排'); equal(await page.locator('[data-plan-search-count]').textContent(), '0 / 36 道安排');
    ok(await page.getByRole('button', { name: '定位选中任务' }).isDisabled());
  });
  await run(page, 'export-scope-csv-xlsx-and-stale', async () => {
    await mount(page); await choose(page); await page.getByRole('searchbox').fill('D2609-001');
    for (const format of ['csv', 'xlsx']) {
      await page.getByRole('button', { name: '导出', exact: true }).click();
      const dialog = page.getByRole('dialog'); ok((await dialog.textContent()).includes('本次导出仍包含此时间范围内的全部 36 道安排，不是搜索结果。'));
      await dialog.getByRole('button', { name: format.toUpperCase(), exact: true }).click();
      const pending = page.waitForEvent('download'); await dialog.getByRole('button', { name: '下载 ' + format.toUpperCase(), exact: true }).click();
      const download = await pending, filename = path.join(output, state.id + '-plan.' + format); await download.saveAs(filename); report.downloads.push(filename);
      equal(download.suggestedFilename(), '计划读取范围.' + format);
      const call = await page.evaluate(() => fixture.calls.filter(row => row.type === 'export').at(-1));
      equal(call.scope, { format, snapshot_ref: 'workspace-ui:' + F.ref(1) + ':full' });
    }
    await page.evaluate(() => { fixture.spec.exportFailure = '快照已失效，未更换计划。'; });
    await page.getByRole('button', { name: '导出', exact: true }).click(); await page.getByRole('dialog').getByRole('button', { name: '下载 CSV', exact: true }).click();
    await page.getByRole('dialog').getByRole('alert').waitFor(); ok((await page.getByRole('dialog').textContent()).includes('快照已失效'));
    equal(await page.evaluate(() => fixture.calls.filter(row => row.type === 'workspace').length), 1, 'Stale export cannot auto-refresh and change data');
    await page.getByRole('dialog').getByRole('button', { name: '取消', exact: true }).click();
  });
}
async function rangesAndLifecycle(page) {
  await run(page, 'keyboard-and-live-theme', async () => {
    await mount(page); await choose(page); await page.getByRole('button', { name: '收起计划目录' }).click();
    const board = page.locator('[data-plan-scroll]'); await board.focus(); await board.press('+');
    await page.waitForFunction(() => document.querySelector('.plan-gantt .plan-actions').textContent.includes('2×'));
    await board.press('f'); await page.waitForFunction(() => document.querySelector('.plan-gantt .plan-actions').textContent.includes('1×'));
    await board.press('/'); equal(await page.getByRole('searchbox').evaluate(node => node === document.activeElement), true);
    await page.getByRole('searchbox').fill('D2609-012'); await page.getByRole('searchbox').press('Enter');
    await board.focus(); await board.press('l'); ok((await page.locator('[data-plan-inspector]').textContent()).includes('D2609-012'));
    const machine = page.getByRole('group', { name: '甘特分组' }).getByRole('button', { name: '设备', exact: true });
    await machine.focus(); await machine.press('ArrowRight');
    equal(await page.getByRole('group', { name: '甘特分组' }).getByRole('button', { name: '人员', exact: true }).getAttribute('aria-pressed'), 'true');
    const pixels = () => page.locator('.plan-global canvas').evaluate(canvas => {
      const data = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
      return data.reduce((sum, value, index) => (sum + value * (index % 251 + 1)) % 2147483647, 0);
    });
    const before = await pixels();
    await page.getByRole('button', { name: '深色：' + (state.theme === 'light' ? '关' : '开'), exact: true }).click(); await settle(page);
    equal(await page.evaluate(() => document.documentElement.dataset.theme), state.theme === 'light' ? 'dark' : 'light');
    ok(await pixels() !== before, 'Existing canvas redraws on theme change');
  });
  await run(page, 'server-range-preserves-task-and-export-scope', async () => {
    await mount(page); await choose(page); await page.getByRole('button', { name: '读取范围', exact: true }).click();
    await page.getByLabel('读取开始时间', { exact: true }).fill('2026-09-09T23:00');
    await page.getByLabel('读取结束时间', { exact: true }).fill('2026-09-10T01:00');
    await page.getByRole('button', { name: '应用范围', exact: true }).click(); await ready(page);
    equal(await page.evaluate(() => fixture.calls.filter(row => row.type === 'workspace').at(-1).scope), { range_start: '2026-09-09T23:00:00', range_end: '2026-09-10T01:00:00' });
    const title = await page.locator('[data-plan-task]').first().getAttribute('title'); ok(title.includes('2026-09-09 22:30:00'), 'Task start is not clipped to query');
    await page.getByRole('button', { name: '导出', exact: true }).click(); const pending = page.waitForEvent('download');
    await page.getByRole('dialog').getByRole('button', { name: '下载 CSV', exact: true }).click(); await pending;
    const scope = await page.evaluate(() => fixture.calls.filter(row => row.type === 'export').at(-1).scope);
    equal(scope.range_start, '2026-09-09T23:00:00'); equal(scope.range_end, '2026-09-10T01:00:00');
    ok(scope.snapshot_ref.startsWith('workspace-ui:') && !scope.snapshot_ref.includes('catalog'));
    await page.getByLabel('读取开始时间', { exact: true }).fill('2026-09-11T00:00');
    await page.getByRole('button', { name: '应用范围', exact: true }).click(); await page.getByRole('alert').waitFor();
    equal(await page.evaluate(() => fixture.calls.filter(row => row.type === 'workspace').length), 2, 'Invalid range rejected before API request');
    await page.getByLabel('读取开始时间', { exact: true }).fill('2026-10-01T00:00');
    await page.getByLabel('读取结束时间', { exact: true }).fill('2026-10-02T00:00');
    await page.getByRole('button', { name: '应用范围', exact: true }).click(); await ready(page);
    equal(await page.locator('[data-plan-search-count]').textContent(), '0 / 0 道安排');
    ok((await page.getByRole('table', { name: '交付风险列表' }).textContent()).includes('没有记录'));
    ok(!(await page.locator('[data-plan-workspace]').textContent()).includes('全部完成'));
    await shot(page, 'empty-server-range');
    await page.getByRole('button', { name: '完整计划', exact: true }).click(); await ready(page);
    equal(await page.locator('[data-plan-search-count]').textContent(), '36 / 36 道安排');
  });
  await run(page, 'catalog-failure-cancel-export-and-adapter-reset', async () => {
    await mount(page, { badCatalog: true }); await page.getByRole('alert').waitFor(); equal(await page.getByRole('radio').count(), 0);
    await page.evaluate(() => { fixture.spec.badCatalog = false; }); await page.getByRole('button', { name: '重新读取目录', exact: true }).click(); await choose(page);
    await page.evaluate(() => { fixture.spec.hold = 'export'; }); await page.getByRole('button', { name: '导出', exact: true }).click();
    await page.getByRole('dialog').getByRole('button', { name: '下载 CSV', exact: true }).click();
    ok(await page.getByRole('dialog').getByRole('button', { name: 'XLSX', exact: true }).isDisabled());
    await page.getByRole('dialog').getByRole('button', { name: '取消导出', exact: true }).click();
    await page.evaluate(() => { fixture.held.splice(0).forEach(resolve => resolve()); fixture.spec.hold = null; }); await settle(page);
    equal(await page.evaluate(() => fixture.calls.filter(row => row.type === 'export').at(-1).aborted), true);
    equal(await page.getByRole('dialog').count(), 0);
    await page.evaluate(() => fixture.replaceAdapter()); await page.getByRole('radio', { name: '选择 正式排产计划 1', exact: true }).waitFor();
    equal(await page.locator('[data-plan-gantt]').count(), 0, 'New adapter cannot inherit old selection or data');
    equal(await page.evaluate(() => fixture.writes), 0);
    await page.evaluate(() => { fixture.spec.hold = 'catalog'; }); await page.getByRole('button', { name: '刷新计划目录' }).click();
    await page.getByRole('button', { name: '取消目录读取' }).click();
    await page.evaluate(() => fixture.held.splice(0).forEach(resolve => resolve())); await settle(page);
    equal(await page.getByRole('radio').count(), 0); ok((await page.locator('.plan-catalog').textContent()).includes('目录读取已取消'));
  });
}
async function failures(page) {
  for (const [name, spec, error] of [['bad-dto', { badWorkspace: true }, '协议不完整'], ['wrong-plan', { wrongPlan: true }, '串源'], ['api-failure', { workspaceFailure: '计划已失效' }, '计划已失效']]) {
    await run(page, name, async () => {
      await mount(page, spec); await page.getByRole('radio', { name: '选择 正式排产计划 1', exact: true }).check(); await page.getByRole('alert').waitFor();
      ok((await page.getByRole('alert').textContent()).includes(error)); equal(await page.locator('[data-plan-gantt]').count(), 0);
      ok(await page.getByRole('button', { name: /^导出：/ }).isDisabled());
      await page.evaluate(() => { fixture.spec.badWorkspace = fixture.spec.wrongPlan = false; fixture.spec.workspaceFailure = null; });
      await page.getByRole('button', { name: '重新读取所选计划' }).click(); await ready(page);
    });
  }
  await run(page, 'stale-request-and-explicit-cancel', async () => {
    await mount(page, { holdRef: F.ref(1) }); await page.getByRole('radio', { name: '选择 正式排产计划 1', exact: true }).check();
    await page.getByRole('button', { name: '取消计划读取', exact: true }).waitFor();
    await choose(page, '候选排产方案 2');
    await page.evaluate(() => { fixture.held.splice(0).forEach(resolve => resolve()); }); await settle(page);
    equal(await page.evaluate(() => fixture.calls.find(row => row.type === 'workspace' && row.ref === PlanUIFixtures.ref(1)).aborted), true);
    ok((await page.locator('.plan-heading').first().textContent()).includes('候选排产方案 2'));
    await page.evaluate(() => { fixture.spec.hold = 'workspace'; }); await page.getByRole('button', { name: '刷新所选计划' }).click();
    await page.getByRole('button', { name: '取消计划读取' }).click();
    ok((await page.locator('[data-plan-workspace]').textContent()).includes('计划读取已取消'));
    await page.evaluate(() => fixture.held.splice(0).forEach(resolve => resolve())); await settle(page);
    equal(await page.locator('[data-plan-gantt]').count(), 0);
  });
  await run(page, 'unknown-evidence-not-zero', async () => {
    await mount(page, { unknown: true, nullLabels: true }); await choose(page);
    await page.getByRole('button', { name: '资源负荷', exact: true }).click();
    ok((await page.getByRole('table', { name: '资源负荷列表' }).textContent()).includes('无法核实'));
    await page.locator('[data-plan-task]').first().click(); const text = await page.locator('[data-plan-inspector]').textContent();
    ok(text.includes('无法核实') && text.includes('未排工序') && text.includes('M-0'));
    await shot(page, 'unknown-evidence');
  });
}
async function scale(page) {
  await run(page, '10000-dense-and-concurrent-virtualization', async () => {
    const start = Date.now(); await mount(page, { dense: true, count: 10000 }); await choose(page);
    equal(await page.locator('[data-plan-search-count]').textContent(), '10000 / 10000 道安排');
    ok(await page.locator('[data-plan-dense-row]').count() > 0, 'Dense view uses interactive canvas');
    ok(await page.locator('[data-plan-task]').count() < 500, 'No10000barDOM'); await layout(page);
    await page.locator('[data-plan-dense-row]').first().focus(); await page.locator('[data-plan-dense-row]').first().press('Enter');
    await page.locator('[data-plan-dense-row]').first().press('ArrowRight');
    ok((await page.locator('[data-plan-inspector]').textContent()).includes('BATCH-00001'), 'Dense canvas supports keyboard selection');
    await page.getByRole('searchbox').fill('BATCH-09999'); await page.getByRole('searchbox').press('Enter');
    ok((await page.locator('[data-plan-inspector]').textContent()).includes('BATCH-09999')); report.dense_ms = Date.now() - start;
    await page.getByRole('searchbox').fill(''); await shot(page, '10000-dense');
    await mount(page, { concurrent: true, count: 10000 }); await choose(page);
    ok(await page.locator('.plan-lane').count() < 20); await page.locator('[data-plan-scroll]').evaluate(node => { node.scrollTop = node.scrollHeight; }); await settle(page);
    ok(await page.locator('.plan-lane').count() < 20); ok((await page.locator('.plan-resource').last().textContent()).includes('10000'));
    await page.getByRole('searchbox').fill('BATCH-09999'); await page.getByRole('searchbox').press('Enter');
    equal(await page.locator('[data-plan-task].conflict').count(), 1, 'Hidden conflicts not erased by search');
  });
}
async function main() {
  let server, browser;
  try {
    server = H.server(report); await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); const origin = 'http://127.0.0.1:' + server.address().port;
    assert(process.env.WORKBENCH_BROWSER); browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
    report.browser = browser.version(); assert.match(report.browser, /^109\./);
    for (const size of [{ width: 1920, height: 1080 }, { width: 1392, height: 924 }]) for (const theme of ['light', 'dark']) {
      state = { ...size, theme, id: size.width + 'x' + size.height + '-' + theme }; const context = await browser.newContext({ viewport: size });
      try {
        const page = await context.newPage(); page.setDefaultTimeout(10000);
        page.on('pageerror', error => report.errors.push({ state: state.id, message: error.message }));
        page.on('console', message => { if (message.type() === 'error') report.errors.push({ state: state.id, message: message.text() }); });
        await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
        await page.goto(origin); await page.waitForFunction(() => !!window.mountPlan);
        await interactive(page); await failures(page); await rangesAndLifecycle(page);
        if (size.width === 1920 && theme === 'light') await scale(page);
      } finally { await context.close(); }
    }
    for (const theme of ['light', 'dark']) {
      state = { width: 600, height: 900, theme, id: '600x900-' + theme };
      const context = await browser.newContext({ viewport: { width: 600, height: 900 } });
      try {
        const page = await context.newPage(); page.setDefaultTimeout(10000);
        page.on('pageerror', error => report.errors.push({ state: state.id, message: error.message }));
        page.on('console', message => { if (message.type() === 'error') report.errors.push({ state: state.id, message: message.text() }); });
        await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
        await page.goto(origin); await page.waitForFunction(() => !!window.mountPlan);
        await run(page, 'compact-no-overlap', async () => {
          await mount(page); await choose(page); await page.getByRole('button', { name: '收起计划目录' }).click();
          await layout(page); await page.locator('[data-plan-task]').first().click(); await shot(page, 'compact-task');
        });
      } finally { await context.close(); }
    }
    equal(report.errors, []); equal(report.external, []); equal(report.unexpected_requests, []);
    ok(report.cases.every(row => row.passed), 'See failures in plan-ui-result.json');
  } catch (error) { report.runner_error = error.stack; process.exitCode = 1; }
  finally {
    if (browser) await browser.close(); if (server && server.listening) await new Promise(resolve => server.close(resolve));
    report.summary = { cases: report.cases.length, failed: report.cases.filter(row => !row.passed).length, assertions: report.assertions, screenshots: report.screenshots.length };
    fs.writeFileSync(path.join(output, 'plan-ui-result.json'), JSON.stringify(report, null, 2)); console.log(JSON.stringify({ output, browser: report.browser, ...report.summary }));
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
