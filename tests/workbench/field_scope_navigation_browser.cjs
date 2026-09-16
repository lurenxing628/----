'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), {spawn} = require('node:child_process');
const {chromium} = require('playwright'), H = require('./field_workspace_probe_harness.cjs');
const output = path.resolve(process.argv[2] || '');
assert(process.argv[2] && !output.startsWith(H.root + '/'));
fs.mkdirSync(output, {recursive: true});
const report = {production_db: false, global_build: false, cases: [], errors: [], http_errors: [], reads: [], writes: []};
let browser, page, server, backend;
const exact = name => page.getByRole('button', {name, exact: true});
async function run(name, action) { await action(); report.cases.push({name, passed: true}); }
async function read() { return page.evaluate(async () => (await (await fetch('/api/workbench/v1/execution/tasks?size=100')).json()).data); }
async function saved(label) {
  const response = page.waitForResponse(value => value.request().method() === 'POST' && /\/execution\/(tasks|reports)\//.test(value.url()));
  await exact(label).click();
  assert.equal((await (await response).json()).result, 'committed');
  await page.getByText('已保存并刷新最新报工。', {exact: true}).waitFor();
  await page.getByRole('table', {name: '逐次报工记录', exact: true}).waitFor();
}
function boundSince(start, task, originalScope) {
  const rows = report.reads.slice(start).filter(row => row.path.endsWith('/execution/tasks'));
  const selected = rows.filter(row => row.query.task_ref);
  assert(selected.length > 0, JSON.stringify(rows));
  for (const row of rows) {
    assert.equal(row.query.plan_ref, originalScope.plan_ref);
    assert.equal(row.query.query, originalScope.query);
    assert.equal(row.query.batch_ids, JSON.stringify(originalScope.batch_ids));
    assert.equal(row.query.range_start, originalScope.range_start);
    assert.equal(row.query.range_end, originalScope.range_end);
  }
  for (const row of selected) {
    assert.equal(row.query.task_ref, task.task_ref);
    assert.equal(row.query.operation_ref, task.operation_ref);
  }
}
async function main() {
  try {
    backend = spawn(path.join(H.root, '.venv/bin/python'), ['-m', 'tests.workbench.field_workspace_probe_server', path.join(output, 'db')], {cwd: H.root, stdio: ['ignore', 'pipe', 'pipe']});
    let stderr = ''; backend.stderr.on('data', chunk => stderr += chunk);
    const ready = await new Promise((resolve, reject) => {
      let text = ''; backend.stdout.on('data', chunk => { text += chunk; try { resolve(JSON.parse(text.split('\n')[0])); } catch {} });
      backend.on('exit', code => reject(new Error('Fixture exited ' + code + ': ' + stderr)));
    });
    server = H.createServer(ready.url, report); await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const origin = 'http://127.0.0.1:' + server.address().port;
    browser = await chromium.launch({executablePath: process.env.WORKBENCH_BROWSER, headless: true}); report.browser = browser.version();
    page = await browser.newPage({viewport: {width: 1392, height: 924}}); page.setDefaultTimeout(10000);
    page.on('pageerror', error => report.errors.push(error.message));
    page.on('response', response => { if (response.url().includes('/api/') && response.status() >= 400) report.http_errors.push({url: response.url(), status: response.status()}); });
    page.on('request', request => {
      if (!request.url().includes('/api/workbench/v1/execution/')) return;
      const url = new URL(request.url());
      if (request.method() === 'GET') report.reads.push({path: url.pathname, query: Object.fromEntries(url.searchParams)});
      if (request.method() === 'POST') report.writes.push({url: request.url(), body: request.postDataJSON()});
    });
    await page.goto(origin); await page.locator('[data-field-task]').first().waitFor();
    const initial = await read(), first = initial.tasks.find(task => task.operation_label === '5 Turning'), second = initial.tasks.find(task => task.operation_label === '6 Turning');
    const scope = {plan_ref: initial.scope.plan_ref, query: 'Turning', batch_ids: ['B1'], range_start: '2026-09-09T07:00:00', range_end: '2026-09-09T11:00:00'};
    const context = {plan_ref: scope.plan_ref, scope, table: {page: 1, size: 20}, task_ref: first.task_ref, operation_ref: first.operation_ref, return_to: {view: 'dashboard', context: {category: 'delivery'}}};
    await page.evaluate(initialContext => mountField({initialContext}), context);
    await page.getByRole('table', {name: '逐次报工记录', exact: true}).waitFor();
    await run('anchored-first-task-save-retains-plan-and-scope', async () => {
      const start = report.reads.length;
      await exact('新增本次报工').click(); await page.getByLabel('本次完成数量', {exact: true}).fill('0'); await saved('保存报工');
      boundSince(start, first, scope);
    });
    await run('switch-second-task-save-uses-matching-operation', async () => {
      await page.getByRole('button', {name: /^查看报工 B1 6 Turning/}).click();
      await page.getByRole('table', {name: '逐次报工记录', exact: true}).waitFor();
      const start = report.reads.length;
      await exact('新增本次报工').click(); await page.getByLabel('本次完成数量', {exact: true}).fill('1'); await saved('保存报工');
      boundSince(start, second, scope);
      assert.equal(await page.locator('[data-field-task].field-selected').getAttribute('data-field-task'), second.task_ref);
    });
    await run('second-task-correction-keeps-operation-and-one-report', async () => {
      const start = report.reads.length;
      await page.getByRole('button', {name: /^更正 BG/}).click(); await page.getByLabel('有效工时（小时）', {exact: true}).fill('0');
      await page.getByLabel('补齐或更正原因', {exact: true}).fill('核对当前工序，不沿用入口工序'); await saved('保存更正');
      boundSince(start, second, scope);
      const latest = await read(), a = latest.tasks.find(task => task.task_ref === first.task_ref), b = latest.tasks.find(task => task.task_ref === second.task_ref);
      assert.equal(a.execution.reports.length, 1); assert.equal(a.execution.reports[0].completed_quantity, 0);
      assert.equal(b.execution.reports.length, 1); assert.equal(b.execution.reports[0].completed_quantity, 1); assert.equal(b.execution.reports[0].effective_processing_hours, 0);
      assert.equal(b.execution.reports[0].correction_history.length, 2);
    });
    await run('collapse-and-refresh-clear-both-selection-identities', async () => {
      await page.locator('[data-field-task].field-selected .field-link').click();
      const start = report.reads.length; await exact('刷新现场记录').click(); await page.locator('[data-field-task]').first().waitFor();
      const rows = report.reads.slice(start).filter(row => row.path.endsWith('/execution/tasks'));
      assert(rows.length > 0); for (const row of rows) { assert.equal(row.query.task_ref, undefined); assert.equal(row.query.operation_ref, undefined); assert.equal(row.query.plan_ref, scope.plan_ref); }
      assert.equal(await page.locator('.field-detail').count(), 0);
    });
    await run('pagination-clears-task-anchor-and-return-keeps-original-dashboard', async () => {
      const start = report.reads.length; await exact('现场下一页').click(); await page.getByText('共 26 道工序 · 第 2 / 2 页', {exact: true}).waitFor();
      const rows = report.reads.slice(start).filter(row => row.path.endsWith('/execution/tasks'));
      assert(rows.length > 0); for (const row of rows) { assert.equal(row.query.task_ref, undefined); assert.equal(row.query.operation_ref, undefined); assert.equal(row.query.plan_ref, scope.plan_ref); }
      await exact('返回').click(); assert.deepEqual(await page.evaluate(() => probe.nav.at(-1)), {view: 'dashboard', context: {category: 'delivery'}});
    });
    assert.deepEqual(report.errors, []); assert.deepEqual(report.http_errors, []); report.completed = true;
  } catch (error) { report.error = error.stack; process.exitCode = 1; if (page) await page.screenshot({path: path.join(output, 'FAILED.png')}).catch(() => {}); }
  finally {
    if (browser) await browser.close(); if (server) await new Promise(resolve => server.close(resolve));
    if (backend && backend.exitCode === null && backend.signalCode === null) { const exited = new Promise(resolve => backend.once('exit', resolve)); backend.kill('SIGTERM'); await exited; }
    fs.writeFileSync(path.join(output, 'field-scope-navigation.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify({output, cases: report.cases.length, completed: report.completed, error: report.error}));
  }
}
main();
