/* Real pointer interactions and real JSON/downloads from the isolated BP fixture. */
'use strict';
const UI = require('./run_ui_source.cjs');
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const { chromium } = require('playwright');
const { serve, layout, contrast } = require('./run_presentation_support.cjs');
const output = process.argv[2], backend = process.argv[3];
const report = { browser: null, variants: [], screenshots: [], errors: [], external: [], dialogs: [], requests: [], downloads: [], checks: [], layouts: [], contrasts: [] };
report.console = []; report.responses = []; report.failedRequests = []; report.hostEntrypoints = []; report.targetViewports = [];
const server = serve(backend, report, output);
let page, origin, variant, fixtures;
const button = name => UI.button(page, name);
async function catalog(open = true) {
  const panel = page.locator('details.rc-catalog');
  if (await panel.evaluate(node => node.open) !== open) await panel.locator(':scope > summary').click();
  await page.waitForFunction(open => document.querySelector('details.rc-catalog').open === open, open);
}
const done = name => report.checks.push({ variant, name });
async function shot(name) {
  const filename = path.join(output, variant + '-' + name + '.png');
  await page.screenshot({ path: filename, animations: 'disabled' }); report.screenshots.push(filename);
  fs.writeFileSync(filename.replace(/\.png$/, '.html'), await page.content());
  fs.writeFileSync(filename.replace(/\.png$/, '-accessible.yaml'), await page.locator('body').ariaSnapshot());
}
async function restore(value, view = 'analysis') {
  const context = { ...value }; delete context.refs;
  await page.evaluate(({ context, view }) => {
    history.replaceState({ workbench: { view, context, key: Date.now() } }, '', '/workbench?view=' + view);
    dispatchEvent(new PopStateEvent('popstate')); window.scrollTo(0, 0);
  }, { context, view });
  if (context.candidate_ref) await page.getByRole('heading', { name: '候选工作区', exact: true }).waitFor();
  await page.locator('[data-candidate-ref], [data-run-ref]').first().waitFor({ state: 'attached' });
}
async function realWorkspace(ref) {
  const response = await page.request.get(origin + '/api/workbench/v1/scheduling/candidates/' + ref + '/workspace');
  assert.equal(response.status(), 200); const value = await response.json();
  fs.writeFileSync(path.join(output, variant + '-' + ref + '-workspace.json'), JSON.stringify(value, null, 2));
  return value;
}
async function checkLayout(name, gantt = true) {
  await page.evaluate(() => window.scrollTo(0, 0));
  const value = await layout(page); report.layouts.push({ variant, name, ...value });
  assert.equal(value.overflow, false); assert.deepEqual(value.controlClipping, []); assert.deepEqual(value.cellClipping, []);
  assert.equal(value.fontSize, '13px'); assert.equal(value.border, '1px');
  if (gantt) {
    assert.equal(await page.getByRole('checkbox', { name: '初始计划', exact: true }).isChecked(), false);
    assert.equal(await page.locator('[data-baseline-lane], [data-baseline-list]').count(), 0);
    assert.equal(value.scrollY, 0); assert(value.canvas && value.painted > 300);
    assert(value.canvas.bottom <= value.viewport.height, JSON.stringify(value));
    assert(value.preview.y < value.viewport.height); assert.equal(value.scope.borderLeft, '0px');
    assert.equal(await page.locator('details.rc-catalog').evaluate(node => node.open), false, 'Selected candidate keeps the comparison list collapsed on first screen');
  }
  const colors = await contrast(page); assert(colors.length > 30);
  const failures = colors.filter(r => r.ratio < 4.5); report.contrasts.push({ variant, name, minimum: Math.min(...colors.map(r => r.ratio)), failures });
  assert.deepEqual(failures, []); await shot(name);
}
async function download(fmt, data, name) {
  const pending = page.waitForEvent('download'); await button(fmt.toUpperCase()).click(); const file = await pending;
  const filename = path.join(output, variant + '-' + name + '.' + fmt); await file.saveAs(filename); assert.equal(await file.failure(), null);
  const unplanned = data.unplanned_operations || [];
  report.downloads.push({ path: filename, format: fmt, task_count: data.task_count, row_count: data.task_count + unplanned.length,
    candidate_ref: data.candidate.candidate_ref, run_ref: data.candidate.run_ref, row_refs: data.tasks.map(t => t.row_ref),
    operation_refs: [...data.tasks, ...unplanned].map(t => t.operation_ref), starts: data.tasks.map(t => t.start) });
  await page.getByText(/^已下载 \d+ 条记录/).waitFor(); done('verified-download-' + fmt + '-' + name);
}
async function candidates() {
  await restore(fixtures.complete); await page.locator('[data-candidate-lane]').first().waitFor();
  const initial = (await realWorkspace(fixtures.complete.candidate_ref)).data;
  assert.equal(initial.task_count, 3); assert(initial.tasks.every(t => t.machine.label === 'Original lathe'));
  await checkLayout('candidate-first-screen');
  const originalViewport = page.viewportSize();
  if (originalViewport.width === 1920) {
    for (const size of [{ width: 1366, height: 768 }, { width: 1280, height: 720 }]) {
      await page.setViewportSize(size);
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      await checkLayout('candidate-target-' + size.width);
      report.targetViewports.push({ ...size, theme: await page.locator('html').getAttribute('data-theme'), passed: true });
    }
    await page.setViewportSize(originalViewport);
  }
  await catalog();
  const directory = await (await page.request.get(origin + '/api/workbench/v1/scheduling/runs/' + fixtures.complete.run_ref + '/candidates')).json();
  const expanded = await layout(page);
  assert(expanded.rowHeights.length === 4 && expanded.rowHeights.every(h => h > 0 && h <= 52), JSON.stringify(expanded));
  assert.deepEqual(await page.locator('[data-candidate-ref]').evaluateAll(rows => rows.map(row => row.dataset.candidateRef)), directory.data.candidates.map(c => c.candidate_ref));
  for (const c of directory.data.candidates) {
    const cells = page.locator('[data-candidate-ref="' + c.candidate_ref + '"] td');
    assert.equal(await cells.nth(2).innerText(), String(c.task_count));
    for (const [i, key] of ['overdue_count', 'total_tardiness_hours', 'makespan_hours'].entries()) {
      const expected = await page.evaluate(metric => metric.value === null ? '未知' : RunCandidateModel.number(metric.value), c.metrics[key]);
      assert.equal(await cells.nth(i + 3).innerText(), expected);
    }
  }
  done('all-four-core-metrics-equal-real-catalog');
  assert.equal(await page.locator('.rc-generation').getAttribute('open'), null);
  const row = page.locator('[data-candidate-ref="' + fixtures.complete.candidate_ref + '"]');
  assert(!(await row.innerText()).includes(fixtures.complete.candidate_ref));
  await row.locator('summary').click(); assert((await row.innerText()).includes(fixtures.complete.candidate_ref)); await shot('candidate-id');
  await row.locator('summary').click(); assert(!(await row.innerText()).includes(fixtures.complete.candidate_ref)); done('full-ref-expand-collapse-no-normal-row-height');
  await page.getByText('生成资料与记录编号', { exact: true }).click();
  const generation = page.locator('.rc-generation'); assert((await generation.innerText()).includes(fixtures.complete.run_ref));
  await generation.getByText(fixtures.complete.run_ref, { exact: true }).waitFor();
  await generation.getByText(fixtures.complete.candidate_ref, { exact: true }).waitFor();
  assert((await generation.innerText()).includes(fixtures.complete.candidate_ref));
  assert((await generation.innerText()).includes('实际工时 / 成本')); await shot('generation-expanded');
  await generation.locator('summary').first().click(); done('generation-details-retain-records-metrics-and-gaps');
  await page.getByText('范围与导出口径', { exact: true }).click();
  assert((await page.locator('.rc-scope').filter({ has: page.getByText('范围与导出口径', { exact: true }) }).innerText()).includes('不改变导出范围')); await page.getByText('范围与导出口径', { exact: true }).click();
  await page.locator('.rc-reasons').filter({ has: page.locator('summary', { hasText: '原因与数据缺项' }) }).first().locator('summary').first().click();
  await shot('gaps-expanded'); await page.locator('.rc-reasons[open]').locator('summary').first().click();
  await page.getByLabel('候选状态', { exact: true }).click(); await page.getByRole('listbox').waitFor(); await shot('shared-select');
  await page.getByRole('listbox').getByRole('option', { name: '全部', exact: true }).click();
  for (const ref of fixtures.complete.refs) {
    await catalog();
    await button('查看候选 ' + ref).click();
    await page.waitForFunction(ref => document.querySelector('[data-candidate-ref="' + ref + '"]')?.getAttribute('aria-selected') === 'true', ref);
    await page.getByRole('heading', { name: '候选工作区', exact: true }).waitFor();
    const data = (await realWorkspace(ref)).data;
    assert.equal(await page.locator('[data-candidate-task-list] [data-row-ref]').count(), data.task_count);
    assert.equal(await page.locator('.rc-generation').getAttribute('open'), null);
  }
  done('all-four-real-candidates-selected');
  const selected = (await realWorkspace(fixtures.complete.refs[3])).data;
  const canvas = page.locator('[data-candidate-lane]').first(), box = await canvas.boundingBox();
  const model = await page.evaluate(data => {
    const m = RunCandidateModel.layout(data, 'machine', '');
    return { start: m.start, end: m.end, item: m.rows[0].items[0] };
  }, selected);
  await page.mouse.click(box.x + ((model.item.start + model.item.end) / 2 - model.start) / (model.end - model.start) * box.width, box.y + 20);
  await UI.reference(page.getByRole('complementary'), model.item.task.row_ref); await shot('canvas-click-detail');
  await button('关闭工序详情').click(); await button('工序详情 ' + selected.tasks[2].row_ref).click();
  await UI.reference(page.getByRole('complementary'), selected.tasks[2].operation_ref); done('canvas-and-row-detail-pointer-clicks');
  await button('关闭工序详情').click(); await page.getByLabel('搜索候选工序').fill(selected.tasks[0].row_ref);
  await download('csv', selected, 'search-full-scope'); await download('xlsx', selected, 'search-full-scope');
  await page.getByLabel('搜索候选工序').fill('');
  // The full shell injects real host actions; the direct component's no-renderer contract is tested by history-widgets.
  assert.equal(await page.locator('[data-run-adoption-action]').count(), 1);
  assert(await button('正式采用').isEnabled()); assert(await button('试调').isEnabled());
  assert.equal(await page.getByRole('button', { name: /^采用方案：/ }).count(), 0);
  assert.equal(selected.capabilities.adopt, false); assert.equal(selected.capabilities.edit_draft, false);
  report.hostEntrypoints.push({ variant, host: 'full-current-shell', adoption: '采用方案', trial: '试调', enabled: true, writes_exercised: false });
  done('full-shell-injected-host-entrypoints');
  assert((await page.locator('[aria-label="生成时范围"]').innerText()).includes('生成时未分配正式版本'));
  await restore(fixtures.partial); const partial = (await realWorkspace(fixtures.partial.candidate_ref)).data;
  assert(partial.unplanned_operation_count > 0); assert((await page.locator('.rc-scope').filter({ has: page.getByText('范围与导出口径', { exact: true }) }).innerText()).includes('未安排 1 道'));
  await checkLayout('partial-first-screen'); await page.getByRole('tab', { name: '未安排明细', exact: true }).click();
  await page.getByText('生成时该工序明确排除，未隐藏此项。', { exact: true }).waitFor(); await download('xlsx', partial, 'partial');
  for (const state of ['failed', 'skipped']) {
    await restore(fixtures[state]); assert.equal(await page.locator('[data-candidate-lane]').count(), 0);
    const current = page.locator('[aria-label="生成时范围"]'); assert.equal(await current.locator('[data-candidate-status]').getAttribute('data-candidate-status'), state);
    await page.getByText('生成资料与记录编号', { exact: true }).click(); assert((await current.innerText()).includes('未知'));
    const metric = page.locator('.rc-generation .rc-metric').first(); await metric.locator('summary').click(); assert((await metric.innerText()).length > 3);
    await shot(state + '-unknown'); done(state + '-status-unknown-reason-retained');
  }
}
async function capacity() {
  await restore(fixtures.capacity); await page.locator('[data-candidate-lane]').first().waitFor();
  const data = (await realWorkspace(fixtures.capacity.candidate_ref)).data; assert.equal(data.task_count, 5000);
  await checkLayout('5000-first-screen');
  const list = page.locator('[data-candidate-task-list]'); await list.evaluate(n => { n.scrollTop = n.scrollHeight; });
  await button('工序详情 ' + data.tasks[4999].row_ref).click(); await UI.reference(page.getByRole('complementary'), data.tasks[4999].row_ref);
  assert(await page.locator('[data-candidate-task-list] [data-row-ref]').count() <= 16);
  await page.getByLabel('搜索候选工序').fill('CAP-099'); await download('csv', data, '5000'); await download('xlsx', data, '5000');
  done('5000-last-row-reachable-virtualization-and-full-export');
}
async function historyAndRun() {
  await button('返回运行页').click(); await page.getByRole('table', { name: '已保存候选' }).waitFor();
  const identity = page.locator('.rj-record > .wb-ref'); assert(!(await identity.innerText()).includes(fixtures.capacity.run_ref));
  await identity.locator('summary').click(); assert((await identity.innerText()).includes(fixtures.capacity.run_ref)); await identity.locator('summary').click();
  const rows = page.getByRole('table', { name: '已保存候选' }).locator('tbody tr'); assert.equal(await rows.count(), 4);
  await rows.first().locator('summary').click(); assert((await rows.first().innerText()).includes(fixtures.capacity.candidate_ref));
  await rows.first().locator('summary').click(); await checkLayout('run-record', false);
  await rows.first().getByRole('button', { name: '详情', exact: true }).click(); await page.getByRole('heading', { name: '候选工作区', exact: true }).waitFor();
  await button('排产记录').click(); await page.locator('[data-run-history-workspace][aria-busy=false]').waitFor();
  const response = await (await page.request.get(origin + '/api/workbench/v1/scheduling/runs')).json();
  const historyRows = page.getByRole('table', { name: '排产历史', exact: true }).locator('tbody tr'); assert.equal(await historyRows.count(), response.data.runs.length);
  for (const run of response.data.runs) {
    const r = page.locator('[data-run-ref="' + run.run_ref + '"]'); assert(!(await r.innerText()).includes(run.run_ref));
    assert.equal(await r.getAttribute('data-run-state'), run.state);
    assert.equal((await r.locator('td').nth(4).innerText()).trim(), run.candidate_count.toLocaleString('zh-CN'));
    assert.equal((await r.locator('td').nth(5).innerText()).trim(), run.task_count.toLocaleString('zh-CN'));
  }
  await checkLayout('history-first-screen', false);
  const row = page.locator('[data-run-ref="' + fixtures.complete.run_ref + '"]'); await row.locator('td').first().locator('.wb-ref > summary').click();
  assert((await row.innerText()).includes(fixtures.complete.run_ref)); await row.getByText('排产设置', { exact: true }).click();
  assert((await row.innerText()).includes('保留开工和完工记录')); await shot('history-details');
  await button('查看运行 ' + fixtures.complete.run_ref).click(); await page.locator('[data-candidate-ref]').first().waitFor();
  assert.equal(await page.getByRole('heading', { name: '候选工作区', exact: true }).count(), 0);
  await button('查看候选 ' + fixtures.complete.candidate_ref).click(); await page.getByRole('heading', { name: '候选工作区', exact: true }).waitFor();
  done('real-run-history-candidate-navigation-and-full-identity');
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve)); let browser;
  assert(![63938, 51093, 56264, 52155, 51733].includes(server.address().port));
  origin = 'http://127.0.0.1:' + server.address().port;
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
    report.browser = browser.version(); assert.match(report.browser, /^109\./);
    for (const [width, height] of [[1920, 1080], [1392, 924]]) for (const theme of ['light', 'dark']) {
      variant = width + 'x' + height + '-' + theme; const row = { variant, width, height, theme, passed: false }; report.variants.push(row);
      const context = await browser.newContext({ viewport: { width, height }, recordHar: { path: path.join(output, variant + '-network.har'), content: 'embed' } });
      await context.tracing.start({ screenshots: true, snapshots: true, sources: true });
      await context.addInitScript(theme => { localStorage.setItem('aps_theme', theme); localStorage.setItem('aps_kit_theme', theme); }, theme);
      page = await context.newPage(); page.setDefaultTimeout(20000);
      page.on('pageerror', error => report.errors.push(error.message)); page.on('dialog', dialog => { report.dialogs.push(dialog.type()); dialog.dismiss(); });
      page.on('console', message => report.console.push({ variant, type: message.type(), text: message.text(), location: message.location() }));
      page.on('response', response => report.responses.push({ variant, status: response.status(), url: response.url() }));
      page.on('requestfailed', request => report.failedRequests.push({ variant, url: request.url(), error: request.failure() }));
      page.on('request', request => { if (request.url().includes('/api/')) report.requests.push({ variant, method: request.method(), path: new URL(request.url()).pathname }); });
      await page.route('**/*', route => { if (!route.request().url().startsWith(origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
      try {
        fixtures = await (await page.request.get(origin + '/fixture/cases')).json();
        await context.addInitScript(value => { history.replaceState({ workbench: { view: 'analysis', context: { run_ref: value.run_ref, candidate_ref: value.candidate_ref }, key: 1 } }, '', '/workbench?view=analysis'); }, fixtures.complete);
        await page.goto(origin + '/workbench?view=analysis');
        await candidates(); await capacity(); await historyAndRun(); row.passed = true;
      } catch (error) { row.error = error.stack; await shot('FAILED'); throw error; }
      finally { await context.tracing.stop({ path: path.join(output, variant + '-trace.zip') }); await context.close(); }
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.external, []); assert.deepEqual(report.dialogs, []);
    assert.deepEqual(report.console.filter(row => row.type === 'error'), []);
    assert.deepEqual(report.responses.filter(row => row.status >= 400), []);
    assert(report.requests.every(row => row.method === 'GET'));
    assert.deepEqual(report.requests.filter(row => row.path.endsWith('/baseline')), []);
    assert.deepEqual(report.targetViewports.map(row => [row.width, row.height, row.theme, row.passed]),
      [[1366, 768, 'light', true], [1280, 720, 'light', true], [1366, 768, 'dark', true], [1280, 720, 'dark', true]]);
    console.log(JSON.stringify({ browser: report.browser, checks: report.checks.length, variants: report.variants.length, downloads: report.downloads.length, output }));
  } finally {
    if (browser) await browser.close(); await new Promise(resolve => server.close(resolve));
    fs.writeFileSync(path.join(output, 'presentation.json'), JSON.stringify(report, null, 2));
  }
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
