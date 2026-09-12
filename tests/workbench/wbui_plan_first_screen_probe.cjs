'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const { chromium } = require('playwright'), H = require('./plan_ui_browser_harness.cjs');
const F = require('./plan_ui_fixtures.cjs');
const output = process.argv[2]; assert(output && !path.resolve(output).startsWith(H.root + path.sep));
fs.mkdirSync(output, { recursive: true });
const report = { sources: [], probes: [], errors: [], unexpected_requests: [], cases: [], selection_lifecycle: [], screenshots: [], production_persistence_tested: false };
const server = H.server(report);
async function selectionLifecycle(page) {
  const plan = F.ref(1), tasks = F.workspace(plan, {}, { count: 3, processOrder: true }).data.tasks;
  const previous = tasks[1].task_ref, initial = tasks[2].task_ref;
  const range = { range_start: '2026-09-10T00:00:00', range_end: '2026-09-10T00:30:00' };
  async function capture(stage, ready = true) {
    if (ready) await page.locator('[data-plan-gantt]').waitFor();
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    return page.evaluate(stage => ({ stage,
      selected_refs: [...new Set(Array.from(document.querySelectorAll('[data-plan-task][aria-pressed="true"]')).map(node => node.dataset.planTask))],
      visible_refs: [...new Set(Array.from(document.querySelectorAll('[data-plan-task]')).map(node => node.dataset.planTask))],
      alerts: Array.from(document.querySelectorAll('[role="alert"]')).map(node => node.textContent),
      calls: PlanUIFixtures.clone(fixture.calls), writes: fixture.writes,
      inspector: document.querySelector('[data-plan-inspector]')?.textContent || null,
    }), stage);
  }
  for (const [name, selectedRef, related, missing] of [
    ['legal-initial-then-outside-predecessor', initial, true, false],
    ['unknown-initial-never-substituted', F.ref(99999), false, false],
    ['outside-initial-not-restored-by-full-read', previous, false, false],
    ['missing-predecessor-does-not-restore-initial', initial, true, true],
  ]) {
    const item = { name, passed: false, initial_ref: selectedRef, related_ref: related ? previous : null, stages: [] };
    report.selection_lifecycle.push(item);
    try {
      const spec = { count: 3, processOrder: true, context: { plan_ref: plan, ...range, selected_task_ref: selectedRef },
        ...(missing ? { omitFullTaskRef: previous } : {}) };
      const valid = await page.evaluate(({ plan, range, spec }) => [range, {}].every(scope => {
        const data = PlanUIFixtures.workspace(plan, scope, spec).data;
        return PlanProcessOrder.validate(data.projections.process_order, data);
      }), { plan, range, spec });
      assert(valid, 'Scoped and full relation fixtures must satisfy the real process-order contract');
      await page.evaluate(spec => mountPlan(spec), spec);
      item.stages.push(await capture('initial-window'));
      if (related) await page.locator('[data-plan-inspector]').getByRole('button', { name: '前序安排在当前读取范围外', exact: true }).click();
      else {
        await page.getByRole('button', { name: '读取范围', exact: true }).click();
        await page.getByRole('button', { name: '完整计划', exact: true }).click();
      }
      await page.waitForFunction(() => fixture.calls.some(call => call.type === 'workspace' && call.scope.range_start === undefined));
      item.stages.push(await capture('explicit-full-read'));
      const [before, after] = item.stages, reads = after.calls.filter(call => call.type === 'workspace');
      assert.deepEqual(before.visible_refs, [initial], 'Initial window contains only the third task');
      assert.deepEqual(before.selected_refs, related ? [initial] : [], 'Initial identity must restore exactly or remain unselected');
      assert.equal(reads.length, 2); assert(reads.every(call => call.ref === plan));
      assert.deepEqual(reads[0].scope, range); assert.deepEqual(reads[1].scope, {});
      assert.equal(before.writes, 0); assert.equal(after.writes, 0);
      assert(after.calls.every(call => ['catalog', 'workspace'].includes(call.type)), 'Selection navigation may only read');
      assert.deepEqual(after.selected_refs, related && !missing ? [previous] : [], 'Full read must honor the new intent and never replay the old initial task');
      if (!related) assert(before.alerts.some(text => /任务|定位/.test(text) && /范围|未找到|不存在/.test(text)), 'Missing initial target must be explicitly reported without expanding its range');
      if (missing) assert(after.alerts.some(text => text.includes('同一完整计划中未找到该关系任务，未定位到替代任务。')), 'Missing relation must expose its exact failure');
      else if (related) assert.deepEqual(after.alerts, []);
      item.passed = true;
    } catch (error) {
      item.failure = error.stack;
    }
    const screenshot = path.join(output, 'selection-' + name + '.png');
    await page.screenshot({ path: screenshot }); report.screenshots.push(screenshot);
  }
  const retry = { name: 'initial-read-retry-restores-valid-target', passed: false, initial_ref: initial, stages: [] };
  report.selection_lifecycle.push(retry);
  try {
    await page.evaluate(spec => mountPlan(spec), { count: 3, processOrder: true, workspaceFailure: '初始计划读取失败，等待手动重试',
      context: { plan_ref: plan, ...range, selected_task_ref: initial } });
    await page.getByRole('alert').waitFor();
    retry.stages.push(await capture('initial-read-failed', false));
    await page.evaluate(() => { fixture.spec.workspaceFailure = null; });
    await page.getByRole('button', { name: '重新读取所选计划', exact: true }).click();
    retry.stages.push(await capture('explicit-retry'));
    const [before, after] = retry.stages, reads = after.calls.filter(call => call.type === 'workspace');
    assert.deepEqual(before.visible_refs, []); assert.deepEqual(before.selected_refs, []);
    assert(before.alerts.some(text => text.includes('初始计划读取失败，等待手动重试')));
    assert.equal(reads.length, 2); assert(reads.every(call => call.ref === plan));
    assert.deepEqual(reads.map(call => call.scope), [range, range]);
    assert.deepEqual(after.selected_refs, [initial], 'A failed initial read must not consume a still-valid restoration target');
    assert.deepEqual(after.alerts, []); assert.equal(before.writes, 0); assert.equal(after.writes, 0);
    assert(after.calls.every(call => ['catalog', 'workspace'].includes(call.type)), 'Retry may only read');
    retry.passed = true;
  } catch (error) { retry.failure = error.stack; }
  const retryScreenshot = path.join(output, 'selection-' + retry.name + '.png');
  await page.screenshot({ path: retryScreenshot }); report.screenshots.push(retryScreenshot);
  const fullRange = { name: 'failed-initial-full-range-does-not-replay-target', passed: false, initial_ref: initial, stages: [] };
  report.selection_lifecycle.push(fullRange);
  try {
    await page.evaluate(spec => mountPlan(spec), { count: 3, processOrder: true, workspaceFailure: '初始计划读取失败，等待切换完整范围',
      context: { plan_ref: plan, ...range, selected_task_ref: initial } });
    await page.getByRole('alert').waitFor();
    fullRange.stages.push(await capture('initial-read-failed', false));
    await page.evaluate(() => { fixture.spec.workspaceFailure = null; });
    await page.getByRole('button', { name: '读取范围', exact: true }).click();
    await page.getByRole('button', { name: '完整计划', exact: true }).click();
    fullRange.stages.push(await capture('explicit-full-range'));
    const [before, after] = fullRange.stages, reads = after.calls.filter(call => call.type === 'workspace');
    assert.deepEqual(before.visible_refs, []); assert.deepEqual(before.selected_refs, []);
    assert(before.alerts.some(text => text.includes('初始计划读取失败，等待切换完整范围')));
    assert.equal(reads.length, 2); assert(reads.every(call => call.ref === plan));
    assert.deepEqual(reads.map(call => call.scope), [range, {}]);
    assert.equal(after.visible_refs.length, 3);
    assert.deepEqual(after.selected_refs, [], 'Choosing the full plan after a failed read must cancel the old initial selection');
    assert.deepEqual(after.alerts, []); assert.equal(before.writes, 0); assert.equal(after.writes, 0);
    assert(after.calls.every(call => ['catalog', 'workspace'].includes(call.type)), 'Full-range navigation may only read');
    fullRange.passed = true;
  } catch (error) { fullRange.failure = error.stack; }
  const fullRangeScreenshot = path.join(output, 'selection-' + fullRange.name + '.png');
  await page.screenshot({ path: fullRangeScreenshot }); report.screenshots.push(fullRangeScreenshot);
  assert(report.selection_lifecycle.every(item => item.passed), JSON.stringify(report.selection_lifecycle.map(({ name, passed, failure }) => ({ name, passed, failure }))));
}
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true });
  report.browser = browser.version();
  try {
    const page = await browser.newPage(); page.on('pageerror', error => report.errors.push(error.stack)); page.setDefaultTimeout(6000);
    await page.goto('http://127.0.0.1:' + server.address().port);
    for (const [width, height] of [[1366, 768], [1280, 720]]) for (const view of ['analysis', 'gantt', 'delay']) {
      await page.setViewportSize({ width, height });
      await page.evaluate(view => { window.scrollTo(0, 0); mountPlan({ view }); }, view);
      await page.locator('[data-plan-gantt]').waitFor();
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.equal(await page.locator('.plan-catalog').getAttribute('data-collapsed'), 'true');
      assert.equal(await page.getByRole('table', { name: '可选排产方案' }).count(), 0);
      const value = await page.evaluate(() => {
        const first = document.querySelector('.plan-lane').getBoundingClientRect();
        return { top: first.top, bottom: first.bottom, viewport: innerHeight, width: innerWidth, pageWidth: document.documentElement.scrollWidth,
          plans: fixture.calls.filter(call => call.type === 'workspace').map(call => call.ref) };
      });
      assert(value.top >= 0 && value.bottom <= height, 'First Gantt row fully visible: ' + JSON.stringify({ view, ...value }));
      assert(value.pageWidth <= width + 1, 'No root horizontal overflow');
      assert.deepEqual(value.plans, ['1'.padStart(48, '0')]);
      const text = await page.locator('.plan-footer').textContent();
      for (const label of ['已核实准时', '资源重叠', '初始基线', '零时长点']) assert(text.includes(label));
      const visibleBar = page.locator('.plan-bar-face strong').first();
      if (await visibleBar.count()) assert((await visibleBar.textContent()).startsWith('D2609-'));
      const image = path.join(output, view + '-' + width + '.png'); await page.screenshot({ path: image }); report.screenshots.push(image);
      report.cases.push({ view, width, height, ...value });
    }
    await page.evaluate(() => mountPlan({ context: { query: 'D2609' } }));
    await page.getByRole('table', { name: '可选排产方案' }).waitFor();
    assert.equal(await page.evaluate(() => fixture.calls.filter(call => call.type === 'workspace').length), 0);
    await page.evaluate(() => mountPlan({ asOf: '2026-09-10T06:00:00' })); await page.locator('[data-plan-gantt]').waitFor();
    assert.equal(await page.locator('[data-plan-time-line=today]').getAttribute('data-time-value'), '2026-09-10T00:00:00');
    assert.equal(await page.locator('[data-plan-time-line=as-of]').getAttribute('data-time-value'), '2026-09-10T06:00:00');
    await page.getByLabel('切换所选计划', { exact: true }).selectOption('2'.padStart(48, '0'));
    await page.waitForFunction(() => fixture.calls.filter(call => call.type === 'workspace').some(call => call.ref === PlanUIFixtures.ref(2)));
    assert.equal(await page.locator('.plan-catalog').getAttribute('data-collapsed'), 'true');
    await page.evaluate(() => mountPlan({ context: { plan_ref: PlanUIFixtures.ref(2), snapshot_ref: 'workspace-ui:explicit' }, workspaceFailure: '指定计划读取失败' }));
    await page.getByRole('alert').waitFor();
    assert.equal(await page.locator('[data-plan-gantt]').count(), 0);
    assert.deepEqual(await page.evaluate(() => fixture.calls.filter(call => call.type === 'workspace').map(call => call.ref)), ['2'.padStart(48, '0')]);
    await selectionLifecycle(page);
    assert.deepEqual(report.errors, []); report.passed = true;
  } catch (error) { report.passed = false; report.failure = error.stack; process.exitCode = 1; }
  finally { await browser.close(); await new Promise(resolve => server.close(resolve)); fs.writeFileSync(path.join(output, 'result.json'), JSON.stringify(report, null, 2)); console.log(JSON.stringify({ passed: report.passed, cases: report.cases, errors: report.errors, failure: report.failure, output })); }
})().catch(error => { console.error(error); server.close(); process.exitCode = 1; });
