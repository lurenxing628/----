'use strict';
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict'), crypto = require('node:crypto');
const { chromium } = require('playwright');
const { adoption } = require('./piece_downstream_browser_support.cjs');
const ready = JSON.parse(fs.readFileSync(process.argv[2])), width = Number(process.argv[3]), theme = process.argv[4], root = ready.root;
const report = { width, theme, pieces_verified: [], screenshots: [], responses: [], page_errors: [], console_errors: [], external_requests: [], served_main: [], capture_errors: [] };
const safe = value => Array.isArray(value) ? value.map(safe) : value && typeof value === 'object' ? Object.fromEntries(Object.entries(value).filter(([key]) => key !== 'write_context').map(([key, item]) => [key, safe(item)])) : value;
const save = () => fs.writeFileSync(path.join(root, 'piece_downstream_browser.json'), JSON.stringify(safe(report), null, 2));
async function shot(page, stage) {
  const file = path.join(root, 'screenshots', 'fb-' + stage + '.png');
  await page.screenshot({ path: file, fullPage: true }); report.screenshots.push(file);
  assert(!await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), 'No document overflow');
  save();
}
async function main() {
  const browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true });
  report.browser_version = browser.version();
  const page = await browser.newPage({ viewport: { width, height: 1000 }, timezoneId: 'America/New_York' });
  page.setDefaultTimeout(20000);
  const pending = [];
  page.on('pageerror', error => report.page_errors.push(String(error)));
  page.on('console', message => { if (message.type() === 'error') report.console_errors.push(message.text()); });
  page.on('request', request => { if (!request.url().startsWith(ready.url + '/') && !/^(data:|blob:)/.test(request.url())) report.external_requests.push(request.url()); });
  page.on('requestfinished', request => {
    if (!request.url().includes('/api/workbench/') && !request.url().includes('/static/workbench/app/main.jsx.js')) return;
    pending.push((async () => {
      const response = await request.response();
      if (request.url().includes('/api/workbench/') && (response.headers()['content-type'] || '').includes('application/json')) {
        report.responses.push({ url: response.url(), status: response.status(), body: safe(await response.json()) });
      } else if (request.url().includes('/static/workbench/app/main.jsx.js')) {
        const bytes = await response.body(); assert.deepEqual(bytes, fs.readFileSync(path.join(ready.assets.static, 'workbench/app/main.jsx.js')));
        report.served_main.push(crypto.createHash('sha256').update(bytes).digest('hex'));
      }
    })().catch(error => report.capture_errors.push(String(error))));
  });
  const flush = async () => { await page.waitForLoadState('networkidle'); await Promise.all(pending); };
  const latest = test => report.responses.slice().reverse().find(test).body;
  try {
    const formal = await adoption(page, ready, theme, report, flush);
    report.formal = formal;
    await page.locator('.sidebar-nav a[href$="?view=field"]').click();
    await page.locator('[data-field-task]').first().waitFor(); await flush();
    const field = latest(row => row.url.includes('/execution/tasks?') && row.body.data.tasks);
    assert.equal(field.data.plan.plan_ref, formal.plan.plan_ref);
    for (const task of field.data.tasks) {
      const original = formal.tasks.find(row => row.task_ref === task.task_ref); assert(original);
      for (const key of ['operation_ref', 'task_ref', 'plan_ref', 'piece_id', 'quantity', 'batch_quantity', 'quantity_basis', 'quantity_reason']) assert.deepEqual(task[key], original[key]);
      const row = page.locator('[data-field-task="' + task.task_ref + '"]');
      assert((await row.locator('[data-field-piece]').innerText()).includes(task.piece_id || '共同工序'));
      assert((await row.locator('[data-field-quantity]').innerText()).startsWith(task.execution.known_completed_quantity + ' / ' + task.quantity));
    }
    await shot(page, 'field-all');
    for (const [index, piece] of ready.expected.pieces.entries()) {
      if (index) { await page.getByRole('button', { name: '清除现场筛选', exact: true }).click(); await flush(); }
      const task = formal.tasks.find(row => row.piece_id === piece && row.sequence === 20);
      const row = page.locator('[data-field-task="' + task.task_ref + '"]');
      await row.locator('.field-link').click();
      const detail = page.locator('.field-detail'); await detail.waitFor();
      assert((await detail.locator('h3').first().innerText()).includes(piece));
      assert((await detail.locator('.field-detail-heading').innerText()).includes('计划应做 1 件 · 批次 3 件'));
      if (!index) {
        await detail.getByRole('button', { name: '新增本次报工', exact: true }).click();
        await page.getByLabel('本次完成数量', { exact: true }).fill('0');
        await page.getByLabel('实际开工', { exact: true }).fill(task.start.slice(0, 16));
        await page.getByLabel('本次实际完工', { exact: true }).fill(task.end.slice(0, 16));
        await page.getByLabel('有效工时 (h)', { exact: true }).fill('0');
        const submitted = page.waitForResponse(response => response.request().method() === 'POST'
          && new URL(response.url()).pathname.endsWith('/execution/tasks/' + task.task_ref + '/reports'));
        const reread = page.waitForResponse(response => response.request().method() === 'GET'
          && new URL(response.url()).pathname.endsWith('/execution/tasks/' + task.task_ref));
        await page.getByRole('button', { name: '保存报工', exact: true }).click();
        const receipt = await submitted, refreshed = await reread;
        assert.equal(receipt.status(), 200); assert.equal(refreshed.status(), 200);
        assert.equal((await refreshed.json()).data.task.task_ref, task.task_ref);
        await page.getByText('已保存并重读最新报工。', { exact: true }).waitFor();
        report.automatic_reread = { write_url: receipt.url(), read_url: refreshed.url(), task_ref: task.task_ref };
        await detail.getByRole('button', { name: /^录入信息 / }).waitFor(); await flush();
        assert(!(await detail.locator('.field-detail-heading').innerText()).includes('已完工'));
        const saved = latest(item => item.url.includes('/execution/tasks/') && item.body.data && item.body.data.task).data.task;
        assert.equal(saved.execution.reports.length, 1);
        const r = saved.execution.reports[0]; assert.equal(r.completed_quantity, 0);
        assert.equal(r.operation_ref, task.operation_ref); assert.equal(r.recorded_against_task_ref, task.task_ref); assert.equal(r.recorded_against_plan_ref, task.plan_ref);
        report.new_report = r;
      }
      await shot(page, 'field-' + index);
      await detail.getByRole('button', { name: '实际甘特', exact: true }).click(); await page.locator('[data-actual-scroll]').waitFor();
      await page.getByRole('checkbox', { name: '详情', exact: true }).check(); await flush();
      const actual = latest(item => /\/actual-gantt\?/.test(item.url)).data;
      const item = actual.items.find(item => item.task.task_ref === task.task_ref);
      assert.deepEqual(item.task, task); assert.notEqual(item.execution.execution_state, 'complete');
      const description = await page.getByLabel('工序详情', { exact: true }).innerText();
      assert(description.includes(piece) && description.includes('计划应做：1.00 件 · 批次：3.00 件'));
      await page.getByLabel('搜索现场甘特', { exact: true }).fill(piece);
      await page.getByRole('button', { name: '批次', exact: true }).click();
      assert((await page.locator('[data-actual-count]').innerText()).includes('2 / 9'));
      const select = page.locator('[data-task-row="' + task.task_ref + '"][data-kind="actual"] .fg-task-select');
      await select.waitFor(); assert((await select.innerText()).includes(piece)); await select.focus(); await page.keyboard.press('Enter');
      const mark = page.locator('[data-task-ref="' + task.task_ref + '"][data-actual-mark="plan"]');
      await mark.hover(); assert((await page.getByRole('tooltip').innerText()).includes(piece));
      assert((await page.getByRole('tooltip').innerText()).includes('计划应做：1.00 件 · 批次：3.00 件'));
      await shot(page, 'actual-' + index);
      await page.getByRole('button', { name: '导出 CSV', exact: true }).click();
      const download = page.waitForEvent('download'); await page.getByRole('button', { name: '下载 CSV', exact: true }).click();
      const file = path.join(root, 'downloads', 'fb-piece-' + index + '.csv'); await (await download).saveAs(file);
      const csv = fs.readFileSync(file, 'utf8'); assert(csv.includes('单件编号') && csv.includes(piece) && csv.includes(task.task_ref));
      assert(!ready.expected.pieces.filter(p => p !== piece).some(p => csv.includes(p)));
      report.pieces_verified.push({ piece, task_ref: task.task_ref, operation_ref: task.operation_ref, plan_ref: task.plan_ref, csv: file });
      await page.getByRole('button', { name: '现场报工', exact: true }).click(); await page.locator('.field-detail').waitFor(); await flush();
    }
    await page.getByRole('button', { name: '清除现场筛选', exact: true }).click(); await flush();
    await page.getByLabel('搜索批次或工序', { exact: true }).fill(ready.expected.pieces[1]);
    await page.getByRole('button', { name: '查询现场记录', exact: true }).click(); await flush();
    await page.waitForFunction(() => document.querySelectorAll('[data-field-task]').length === 2);
    assert.equal(await page.locator('[data-field-task]').count(), 2); await shot(page, 'field-piece-search');
    // Real main.jsx history restoration is the existing explicit-plan entry contract.
    await page.evaluate(planRef => { history.replaceState({ workbench: { view: 'field', key: 900, context: { plan_ref: planRef } } }, '', '/workbench?view=field'); }, ready.expected.original_plan_ref);
    await page.reload(); await page.locator('[data-field-task]').waitFor(); await flush();
    assert((await page.locator('[data-field-quantity]').innerText()).includes('/ 未知'));
    assert((await page.locator('[data-field-quantity]').innerText()).includes('旧计划未记录原数量证据'));
    await page.locator('.field-link').click(); await page.locator('.field-detail').waitFor();
    await shot(page, 'old-field-unknown');
    await page.getByRole('button', { name: '实际甘特', exact: true }).click(); await page.locator('[data-actual-scroll]').waitFor();
    await page.getByRole('checkbox', { name: '详情', exact: true }).check();
    assert((await page.getByLabel('工序详情', { exact: true }).innerText()).includes('计划应做：未知 件 · 批次：未知 件'));
    await shot(page, 'old-actual-unknown');
    report.quantity_contracts = await page.evaluate(async planRef => {
      const dto = await (await fetch('/api/workbench/v1/actual-gantt?plan_ref=' + planRef)).json();
      const field = await (await fetch('/api/workbench/v1/execution/tasks?plan_ref=' + planRef)).json();
      ActualGanttContract.workspace(dto, { plan_ref: planRef }); FieldContract.query(field, 'list');
      const accepted = [];
      for (const patch of [{ piece_id: undefined }, { quantity: undefined }, { quantity: true }, { quantity: -1 }, { batch_quantity: 3 }, { quantity_basis: 'guessed' }, { quantity_reason: 'guessed' }]) {
        const bad = JSON.parse(JSON.stringify(dto)); Object.assign(bad.data.items[0].task, patch);
        try { ActualGanttContract.workspace(bad, { plan_ref: planRef }); accepted.push(['actual', patch]); } catch (_) { /* Malformed response must be rejected. */ }
        if (FieldContract.task({ ...field.data.tasks[0], ...patch })) accepted.push(['field', patch]);
      }
      return { incorrectly_accepted: accepted, old_quantity: dto.data.items[0].task.quantity };
    }, ready.expected.original_plan_ref);
    assert.deepEqual(report.quantity_contracts.incorrectly_accepted, []); await flush();
    assert.deepEqual(report.capture_errors, []);
    assert(report.responses.every(row => row.body.ok === true && (row.status === 200 || row.status === 202 && row.url.endsWith('/scheduling/runs'))), 'No product errors may be hidden');
  } catch (error) { report.error = error.stack; await shot(page, 'failure').catch(() => {}); process.exitCode = 1; }
  finally { await flush(); await browser.close(); save(); }
}
main().catch(error => { report.error = error.stack; save(); console.error(error); process.exitCode = 1; });
