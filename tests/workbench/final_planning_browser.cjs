'use strict';
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto'), assert = require('node:assert/strict');
const { chromium } = require('playwright');
const { support } = require('./final_planning_probe_support.cjs');
const { runActions } = require('./final_planning_run_actions.cjs');
const { planActions } = require('./final_planning_plan_actions.cjs');
const { trialActions } = require('./final_planning_trial_actions.cjs');
const { preflightReturn } = require('./final_planning_preflight_actions.cjs');
const { readonlyActions } = require('./final_planning_readonly_actions.cjs');
const { restartCandidateAnalysis } = require('./final_planning_analysis_actions.cjs');
const ready = JSON.parse(fs.readFileSync(process.argv[2])), width = Number(process.argv[3]), theme = process.argv[4], mode = process.argv[5];
const entryScript = JSON.parse(fs.readFileSync(path.join(ready.assets.static, 'workbench/asset-manifest.json'))).scripts.at(-1);
assert(/^workbench\/app\/main(?:\.jsx)?\.js$/.test(entryScript));
const report = { width, theme, mode, actions: [], requests: [], responses: [], screenshots: [], downloads: [], findings: [], pieces: ready.expected.pieces,
  external_requests: [], page_errors: [], console_errors: [], console_events: [], failed_requests: [], capture_errors: [], aborted_reads: [], served_main: [],
  capture_method: 'Passive original fetch Response.clone; no mock, retry or synthetic business request' };
const save = () => fs.writeFileSync(path.join(ready.root, 'final_planning_' + mode + '.json'), JSON.stringify(report, null, 2));
async function restart(page, h, flush) {
  const original = JSON.parse(fs.readFileSync(path.join(ready.root, 'final_planning_actions.json')));
  const { action, last, button, shot } = h;
  await action(['WBP-PLAN-004.new-process', 'WBP-PLAN-002.stable-identities'], async () => {
    await page.goto(ready.url + '/workbench?view=analysis');
    const row = page.getByRole('table', { name: '可选排产方案', exact: true }).getByRole('row')
      .filter({ has: page.getByRole('cell', { name: String(original.second_official.plan.version), exact: true }) });
    await row.getByRole('radio', { name: '选择 ' + original.second_official.plan.display_name, exact: true }).check();
    await page.locator('[data-plan-workspace] .plan-main').waitFor(); await flush();
    const data = last(value => value.plan && value.tasks);
    assert.equal(data.plan.plan_ref, original.second_official.plan.plan_ref);
    assert.deepEqual(data.tasks, original.second_official.tasks);
    await shot('new-process-official');
  });
  await action(['WBP-PLAN-001.official', 'WBP-PLAN-001.historical', 'WBP-PLAN-001.scenario'], async () => {
    await h.caption(original.second_official.plan.plan_ref, '当前正式');
    const table = page.getByRole('table', { name: '可选排产方案', exact: true });
    const historical = table.getByRole('row').filter({ has: page.getByRole('cell', { name: '5', exact: true }) });
    await historical.getByRole('radio', { name: '选择 ' + original.first_official.plan.display_name, exact: true }).check();
    await flush();
    const data = last(value => value.plan && value.tasks);
    assert.equal(data.plan.plan_ref, original.first_official.plan.plan_ref);
    assert.deepEqual(data.tasks, original.first_official.tasks);
    await h.caption(data.plan.plan_ref, '历史正式'); await shot('new-process-historical');
    await button('已存场景', page.locator('.plan-catalog')).click(); await flush();
    const legacy = table.getByRole('row').filter({ hasText: 'piece-main-old-scene name' });
    await legacy.waitFor();
    const catalog = last(value => value.plans && value.plans.some(plan => plan.display_name === 'piece-main-old-scene name'));
    const plan = catalog.plans.find(value => value.display_name === 'piece-main-old-scene name');
    assert.equal(plan.kind, 'scenario'); assert.equal(plan.is_current_official, false);
    const choice = legacy.getByRole('radio');
    assert.equal(await choice.isDisabled(), !plan.capabilities.view);
    if (plan.capabilities.view) {
      await choice.check(); await flush();
      assert.equal(last(value => value.plan && value.tasks).plan.plan_ref, plan.plan_ref);
      await h.caption(plan.plan_ref, '场景预览');
    } else {
      assert(plan.blocked_reasons.length > 0);
      assert.equal(last(value => value.plan && value.tasks).plan.plan_ref, original.first_official.plan.plan_ref);
    }
    report.legacy_scenario_catalog = { plan_ref: plan.plan_ref, viewable: plan.capabilities.view, blocked_reasons: plan.blocked_reasons };
    await shot('new-process-legacy-scenario-catalog');
  });
  await restartCandidateAnalysis(page, original, report, h, flush);
  await action(['WBP-TRIAL-012.new-process', 'WBP-TRIAL-002.catalog-source'], async () => {
    await page.goto(ready.url + '/workbench/trial');
    await page.getByRole('tab', { name: '已存场景', exact: true }).click();
    const row = page.getByRole('table', { name: '试调目录', exact: true }).getByRole('row').filter({ hasText: original.scenario_name });
    await button('打开', row).click(); await page.locator('[data-open-kind="scenario"] .tt-main').waitFor(); await flush();
    const data = last(value => value.scenario_ref === original.scenario_ref && value.tasks);
    assert.deepEqual(data.tasks, original.scenario.tasks);
    await page.getByRole('tab', { name: '采用记录', exact: true }).click(); await flush();
    await shot('new-process-scenario');
    assert(report.requests.every(row => row.method === 'GET'), 'New-process recovery must not write');
  });
}
async function main() {
  const browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true });
  report.browser_version = browser.version();
  const context = await browser.newContext({ viewport: { width, height: 1000 }, colorScheme: theme });
  await context.exposeBinding('__finalPlanningResponse', (_source, row) => report.responses.push(row));
  await context.exposeBinding('__finalPlanningFailure', (_source, row) => {
    (row.name === 'AbortError' && row.method === 'GET' ? report.aborted_reads : report.capture_errors).push(row);
  });
  await context.addInitScript(({ origin }) => {
    const original = window.fetch.bind(window); window.__finalPlanningPending = 0;
    window.fetch = (...args) => {
      window.__finalPlanningPending++;
      return original(...args).then(response => {
      if (response.url.startsWith(origin + '/api/workbench/') && (response.headers.get('content-type') || '').includes('application/json')) {
        const method = (args[1] && args[1].method || args[0] && args[0].method || 'GET').toUpperCase();
        response.clone().json().then(body => window.__finalPlanningResponse({ url: response.url, status: response.status, body }))
          .catch(error => window.__finalPlanningFailure({ url: response.url, method, name: error.name, error: String(error) }))
          .finally(() => { window.__finalPlanningPending--; });
      } else window.__finalPlanningPending--;
      return response;
      }, error => { window.__finalPlanningPending--; throw error; });
    };
  }, { origin: ready.url });
  const pending = [], pages = new Set();
  function wirePage(page) {
  pages.add(page); page.setDefaultTimeout(20000);
  page.on('pageerror', error => report.page_errors.push(String(error)));
  page.on('console', message => { if (message.type() === 'error') {
    report.console_errors.push(message.text()); report.console_events.push({ text: message.text(), location: message.location() });
  } });
  page.on('request', request => {
    if (!request.url().startsWith(ready.url + '/') && !/^(data:|blob:)/.test(request.url())) report.external_requests.push(request.url());
    if (request.url().includes('/api/workbench/')) report.requests.push({ url: request.url(), method: request.method(), input: request.postDataJSON() });
  });
  page.on('requestfailed', request => report.failed_requests.push({ url: request.url(), method: request.method(), failure: request.failure() }));
  page.on('requestfinished', request => {
    if (new URL(request.url()).pathname !== '/static/' + entryScript) return;
    pending.push((async () => {
      const response = await request.response(), bytes = await response.body();
      assert.deepEqual(bytes, fs.readFileSync(path.join(ready.assets.static, entryScript)));
      report.served_main.push({ sha256: crypto.createHash('sha256').update(bytes).digest('hex') });
    })().catch(error => report.capture_errors.push({ url: request.url(), error: String(error) })));
  });
  }
  context.on('page', wirePage);
  const page = await context.newPage();
  const flush = async () => {
    for (const surface of pages) if (!surface.isClosed()) {
      await surface.waitForLoadState('networkidle');
      await surface.waitForFunction(() => window.__finalPlanningPending === 0);
    }
    await Promise.all(pending);
  };
  const h = support(page, ready, report, save, flush);
  h.newTab = async url => {
    const other = await context.newPage(); await other.goto(url);
    return { page: other, h: support(other, ready, report, save, flush) };
  };
  try {
    if (mode === 'restart') await restart(page, h, flush);
    else if (mode === 'readonly') await readonlyActions(page, ready, report, h, flush);
    else if (mode === 'preflight') {
      await page.goto(ready.run_url); await page.getByRole('heading', { name: '排产前检查', exact: true }).waitFor();
      if (await page.locator('html').getAttribute('data-theme') !== report.theme) await page.getByRole('button', { name: /^深色：/ }).click();
      assert.equal(await page.locator('html').getAttribute('data-theme'), report.theme);
      await h.button('选择批次').click(); await flush();
      await page.getByRole('checkbox', { name: '选择 B1', exact: true }).check();
      await preflightReturn(page, report, h, flush);
    }
    else if (mode === 'candidate-source') await runActions(page, ready, report, h, flush);
    else { await runActions(page, ready, report, h, flush); await planActions(page, report, h, flush); await trialActions(page, ready, report, h, flush); }
    await flush();
    for (const key of ['external_requests', 'page_errors', 'capture_errors', 'findings']) assert.deepEqual(report[key], [], key);
    const apiErrors = report.expected_rejected_api || [];
    for (const item of apiErrors) {
      assert([404, 409].includes(item.status));
      assert(report.requests.some(row => row.method === (item.method || 'GET') && row.url === item.url));
      assert(report.responses.some(row => row.url === item.url && row.status === item.status && row.body.ok === false
        && (item.status !== 409 || row.body.committed === false && row.body.error.code === item.code)));
    }
    const rejected = (report.expected_rejected_documents || []).map(item => ({ ...item, status_text: 'BAD REQUEST' })).concat(apiErrors);
    const network = report.network_faults || [];
    const unexpected = report.console_events.filter(event => !rejected.some(item => item.url === event.location.url
      && event.text === 'Failed to load resource: the server responded with a status of ' + item.status + ' (' + item.status_text + ')')
      && !network.some(item => item.url === event.location.url && event.text === 'Failed to load resource: ' + item.error));
    assert.deepEqual(unexpected, [], 'Unexpected browser console errors');
    assert(report.console_events.length <= rejected.length + network.length, 'Only explicitly witnessed errors are expected');
    assert(report.served_main.length); assert(report.browser_version.startsWith('109.'));
    assert(report.failed_requests.every(row => row.method === 'GET' && (row.failure.errorText === 'net::ERR_ABORTED'
      || network.some(item => item.url === row.url && item.error === row.failure.errorText))));
  } catch (error) {
    report.error = String(error.stack || error); process.exitCode = 1;
    try { await h.shot('failure'); } catch (capture) { report.capture_errors.push({ stage: 'failure-screenshot', error: String(capture) }); }
  } finally {
    await context.close(); await Promise.all(pending); await browser.close(); save();
  }
}
main().catch(error => { report.error = String(error.stack || error); save(); console.error(error); process.exitCode = 1; });
