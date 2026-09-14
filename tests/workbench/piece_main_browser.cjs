'use strict';
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict'), crypto = require('node:crypto');
const { chromium } = require('playwright');
const { trialChain } = require('./piece_main_actions.cjs');
const { ganttPixels, candidateDetail } = require('./piece_main_visuals.cjs');
const ready = JSON.parse(fs.readFileSync(process.argv[2])), width = Number(process.argv[3]), theme = process.argv[4], root = ready.root;
const report = { width, theme, pieces: ready.expected.pieces, stages: [], findings: [], responses: [], requests: [], screenshots: [], page_errors: [], console_errors: [], capture_errors: [], aborted_reads: [], failed_requests: [], external_requests: [], served_main: [], dto_capture: 'passive original fetch Response.clone; no route, mock, retry or synthetic request' };
const save = () => fs.writeFileSync(path.join(root, 'piece_main_browser.json'), JSON.stringify(report, null, 2));
const record = (stage, detail = {}) => { report.stages.push({ stage, ...detail }); console.log(JSON.stringify({ stage, ...detail })); save(); };
async function screenshot(page, stage) {
  const file = path.join(root, 'screenshots', 'piece_main_' + stage + '.png');
  await page.screenshot({ path: file, fullPage: true }); report.screenshots.push(file);
  const viewport = path.join(root, 'screenshots', 'piece_main_' + stage + '_viewport.png');
  await page.screenshot({ path: viewport });
  report.viewport_screenshots = (report.viewport_screenshots || []).concat(viewport);
  fs.writeFileSync(path.join(root, 'piece_main_' + stage + '.txt'), await page.locator('body').innerText()); save();
}
async function main() {
  const browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true });
  report.browser_version = browser.version();
  const context = await browser.newContext({ viewport: { width, height: 1000 }, colorScheme: theme });
  await context.exposeBinding('__pieceMainResponse', (_source, row) => report.responses.push(row));
  await context.exposeBinding('__pieceMainCaptureFailure', (_source, row) => {
    (row.name === 'AbortError' ? report.aborted_reads : report.capture_errors).push(row);
  });
  await context.addInitScript(({ origin }) => {
    const original = window.fetch.bind(window); window.__pieceMainPending = 0;
    window.fetch = (...args) => original(...args).then(response => {
      if (response.url.startsWith(origin + '/api/workbench/')) {
        window.__pieceMainPending++;
        const method = (args[1] && args[1].method || args[0] && args[0].method || 'GET').toUpperCase();
        response.clone().json().then(body => window.__pieceMainResponse({ url: response.url, status: response.status, body }))
          .catch(error => window.__pieceMainCaptureFailure({ url: response.url, method, name: error.name, error: String(error) }))
          .finally(() => { window.__pieceMainPending--; });
      }
      return response;
    });
  }, { origin: ready.url });
  const page = await context.newPage(), pending = [];
  page.setDefaultTimeout(20000);
  page.on('pageerror', error => report.page_errors.push(String(error)));
  page.on('console', message => { if (message.type() === 'error') report.console_errors.push(message.text()); });
  page.on('request', request => {
    if (!request.url().startsWith(ready.url + '/') && !/^(data:|blob:)/.test(request.url())) report.external_requests.push(request.url());
    if (request.url().includes('/api/workbench/')) report.requests.push({ method: request.method(), url: request.url(), input: request.postDataJSON() });
  });
  page.on('requestfailed', request => report.failed_requests.push({ url: request.url(), method: request.method(), failure: request.failure() }));
  // Only requestfinished proves that the browser downloaded the complete body.
  page.on('requestfinished', request => {
    if (!request.url().includes('/static/workbench/app/main.jsx.js')) return;
    pending.push((async () => {
      const response = await request.response();
      const bytes = await response.body(), compiled = fs.readFileSync(path.join(ready.assets.static, 'workbench/app/main.jsx.js'));
      assert.deepEqual(bytes, compiled); report.served_main.push({ url: response.url(), sha256: crypto.createHash('sha256').update(bytes).digest('hex') });
    })().catch(error => report.capture_errors.push({ url: request.url(), error: String(error) })));
  });
  const flush = async () => { await page.waitForLoadState('networkidle'); await page.waitForFunction(() => window.__pieceMainPending === 0); await Promise.all(pending); };
  try {
    await page.goto(ready.run_url);
    await page.locator('[data-preflight-workspace]').getByRole('heading', { name: '执行排产', exact: true }).waitFor();
    if (await page.locator('html').getAttribute('data-theme') !== theme) await page.getByRole('button', { name: /^切换(?:深色|浅色)$/ }).click();
    assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
    await screenshot(page, '01-main'); record('main_available', { url: page.url(), runtime: ready.runtime });
    await page.getByRole('button', { name: '选择批次', exact: true }).click();
    for (const batch of ready.expected.batches) await page.getByRole('checkbox', { name: '选择 ' + batch, exact: true }).check();
    await page.getByLabel('计划开始日期', { exact: true }).fill('2026-09-09');
    await page.getByLabel('计划结束日期', { exact: true }).fill('2026-09-25');
    await page.getByRole('button', { name: '开始排产检查', exact: true }).click();
    await page.getByText('检查明细 · ' + ready.expected.task_count + ' 道', { exact: true }).click();
    await screenshot(page, '02-preflight'); record('preflight_user_selected');
    await page.getByRole('button', { name: '核对并开始排产', exact: true }).click();
    await page.getByRole('button', { name: '确认开始排产', exact: true }).click();
    await Promise.race([page.getByRole('table', { name: '已保存候选', exact: true }).waitFor({ timeout: 120000 }),
      page.getByText('候选排产没有完成。请到「排产记录」查看原因，改好后重新做排产检查。', { exact: true }).waitFor({ timeout: 120000 }).then(() => { throw new Error('Real worker rejected the run; inspect server log'); })]);
    await screenshot(page, '03-worker-complete'); record('real_worker_complete');
    await page.getByRole('table', { name: '已保存候选', exact: true }).getByRole('button', { name: '详情', exact: true }).first().click();
    await page.getByRole('table', { name: '候选任务安排', exact: true }).waitFor();
    await screenshot(page, '04-candidate');
    await ganttPixels(page, '.rc-gantt', 'candidate', report);
    await candidateDetail(page, report, screenshot);
    await flush();
    const response = report.responses.findLast(row => row.body.data && row.body.data.tasks && row.body.data.candidate);
    assert(response, 'Actual browser candidate workspace response must exist');
    const tasks = response.body.data.tasks, pieces = tasks.filter(task => task.batch_label === 'B1' && [20, 30].includes(task.sequence));
    assert.equal(tasks.length, ready.expected.task_count); assert.equal(pieces.length, 6);
    const preflight = report.responses.find(row => row.url.endsWith('/scheduling/preflight')).body.data;
    const identities = new Map(preflight.tasks.map(row => [row.operation_ref, row]));
    if (pieces.some(task => !Object.hasOwn(task, 'piece_id') || task.piece_id !== identities.get(task.operation_ref).piece_id)) report.findings.push({ id: 'EQ-PIECE-IDENTITY', message: 'Candidate DTO and visible task rows cannot distinguish same-batch same-sequence pieces', source: 'core/services/workbench/run_candidate_tasks.py:operation_labels', sample: pieces, screenshot: report.screenshots.at(-1) });
    if (pieces.some(task => task.quantity !== 1 || task.batch_quantity !== 3)) report.findings.push({ id: 'EQ-PIECE-QUANTITY', message: 'Candidate task quantity does not separate per-piece work from the full batch', sample: pieces.map(task => ({ sequence: task.sequence, quantity: task.quantity, batch_quantity: task.batch_quantity, execution: task.execution_at_generation })), screenshot: report.screenshots.at(-1) });
    for (const task of tasks.filter(task => task.batch_label === 'B1' && [10, 40].includes(task.sequence))) {
      assert.equal(task.quantity, 3);
      if (Object.hasOwn(task, 'batch_quantity')) assert.equal(task.batch_quantity, 3);
    }
    record('candidate_read', { tasks: tasks.length, findings: report.findings.map(row => row.id) });
    await trialChain(page, ready, report, screenshot, record, flush);
  } catch (error) {
    report.error = String(error.stack || error); await screenshot(page, 'failure').catch(() => {}); process.exitCode = 1;
  } finally {
    await flush(); await context.close(); await Promise.all(pending); await browser.close(); save();
  }
}
main().catch(error => { report.error = String(error.stack || error); save(); console.error(error); process.exitCode = 1; });
