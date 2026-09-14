'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const { execFileSync } = require('node:child_process');

const navigation = (ready, view, context) => ready.url + '/workbench?view=' + view + '&nav=' +
  encodeURIComponent(JSON.stringify({ version: 1, view, context }));
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
function snapshot(ready, label) {
  return JSON.parse(execFileSync(process.env.WORKBENCH_PYTHON || path.resolve(__dirname, '../../.venv/bin/python'),
    ['-B', path.join(__dirname, 'final_planning_database_probe.py'), ready.root, label], { encoding: 'utf8', env: process.env }));
}
async function theme(page, report) {
  if (await page.locator('html').getAttribute('data-theme') !== report.theme) await page.getByRole('button', { name: /^切换(?:深色|浅色)$/ }).click();
  assert.equal(await page.locator('html').getAttribute('data-theme'), report.theme);
}

async function delayConflictDetails(page, ready, report, h, flush) {
  const start = report.requests.length;
  const views = page.getByRole('tablist', { name: '计划中心视图', exact: true });
  await views.getByRole('tab', { name: '交付风险', exact: true }).click();
  const workspace = page.locator('[data-plan-workspace]');
  await views.getByRole('tab', { name: '交付风险', exact: true, selected: true }).waitFor();
  const table = workspace.getByRole('table', { name: '资源重叠明细', exact: true });
  await table.waitFor(); await flush();
  const data = h.last(value => value.plan && value.tasks), occupancy = data.projections.occupancy;
  assert.equal(data.plan.plan_ref, ready.expected.original_plan_ref);
  assert.equal(occupancy.plan_ref, data.plan.plan_ref); assert.deepEqual(occupancy.time_scope, data.time_scope);
  assert.equal(occupancy.basis, 'selected_plan_only');
  const expected = occupancy.resources.flatMap(resource => resource.segments.flatMap(segment => {
    assert(Number.isSafeInteger(segment.concurrent_operations) && segment.concurrent_operations > 0);
    if (segment.concurrent_operations === 1) return [];
    assert.equal(typeof resource.label, 'string'); assert(resource.label.trim());
    return [{ resource_ref: resource.resource_ref, kind: resource.kind, label: resource.label,
      start: segment.start, end: segment.end, concurrent_operations: segment.concurrent_operations }];
  }));
  assert(expected.length > 0 && expected.length <= 20, 'This persisted fixture must have nonempty first-page overlap details');
  const expectedCells = expected.map(row => [row.label + ({ machine: '设备', operator: '人员' }[row.kind]),
    row.start.replace('T', ' '), row.end.replace('T', ' '), String(row.concurrent_operations)]);
  const cells = async () => table.locator('tbody tr').evaluateAll(rows => rows.map(row =>
    Array.from(row.querySelectorAll('td'), cell => cell.textContent.trim())));
  assert.deepEqual(await cells(), expectedCells);
  const detail = workspace.getByRole('region', { name: '资源重叠明细', exact: true });
  assert((await detail.innerText()).includes('不代表等待、停机、缺料或超期原因'));
  await page.reload(); await table.waitFor(); await flush();
  const restored = h.last(value => value.plan && value.tasks);
  assert.equal(restored.plan.plan_ref, data.plan.plan_ref);
  assert.deepEqual(restored.projections.occupancy, occupancy); assert.deepEqual(await cells(), expectedCells);
  report.delay_conflicts = { plan_ref: data.plan.plan_ref, occupancy, expected_rows: expected,
    actual_cells: await cells(), f5_same_projection_and_rows: true, request_start: start, request_end: report.requests.length };
  await h.shot('required-delay-conflict-details');
}

async function trialViewRecovery(page, ready, report, h, flush, requestStart) {
  const expected = { mode: 'batch', baseline: false, only_changed: true, query: 'B1', result_tab: 'capacity' };
  const original = h.last(value => value.scenario_ref === ready.expected.required.scenario_ref && value.tasks);
  const scenarioRef = original.scenario_ref, storageKey = 'aps_workbench_trial_view_v1:scenario:' + scenarioRef;
  const gantt = page.getByRole('region', { name: '试调甘特', exact: true });
  const tabs = page.getByRole('tablist', { name: '试调结果', exact: true });
  assert.equal(original.draft_ref, ready.expected.required.draft_ref);
  assert.equal(await page.evaluate(key => localStorage.getItem(key), storageKey), null, 'Fresh entry must not write default preferences');
  await gantt.getByRole('tablist', { name: '甘特分组', exact: true }).getByRole('tab', { name: '批次', exact: true }).click();
  await gantt.getByRole('checkbox', { name: '原安排', exact: true }).uncheck();
  await gantt.getByRole('checkbox', { name: '仅变更', exact: true }).check();
  const search = gantt.getByRole('searchbox', { name: '搜索试调工序', exact: true });
  await search.click(); assert.equal(await search.inputValue(), '');
  await page.keyboard.type(expected.query, { delay: 50 });
  assert.equal(await search.inputValue(), 'B1');
  await tabs.getByRole('tab', { name: '批次对比', exact: true }).click();
  await tabs.getByRole('tab', { name: '批次对比', exact: true }).press('ArrowRight');
  await page.getByRole('table', { name: '资源占用', exact: true }).waitFor(); await flush();
  async function observed(surface) {
    const current = surface.locator('[data-trial-workspace]'), board = surface.getByRole('region', { name: '试调甘特', exact: true });
    assert.equal(await current.getAttribute('data-open-kind'), 'scenario');
    assert.equal(await current.getAttribute('data-open-ref'), scenarioRef);
    const modeLabel = (await board.getByRole('tablist', { name: '甘特分组', exact: true }).locator('[role="tab"][aria-selected="true"]').innerText()).trim();
    const tabLabel = (await surface.getByRole('tablist', { name: '试调结果', exact: true }).locator('[role="tab"][aria-selected="true"]').innerText()).trim();
    const values = { mode: { '设备': 'machine', '人员': 'operator', '批次': 'batch' }[modeLabel],
      baseline: await board.getByRole('checkbox', { name: '原安排', exact: true }).isChecked(),
      only_changed: await board.getByRole('checkbox', { name: '仅变更', exact: true }).isChecked(),
      query: await board.getByRole('searchbox', { name: '搜索试调工序', exact: true }).inputValue(),
      result_tab: { '批次对比': 'delivery', '资源占用': 'capacity', '调整记录': 'history', '采用记录': 'adoptions',
        '约束问题': 'issues', '完整任务': 'tasks', '未排工序': 'unplanned' }[tabLabel] };
    assert.deepEqual(values, expected);
    const raw = await surface.evaluate(key => localStorage.getItem(key), storageKey), saved = JSON.parse(raw);
    assert.deepEqual(Object.keys(saved).sort(), ['kind', 'preferences', 'ref', 'schema_version']);
    assert.equal(saved.schema_version, 1); assert.equal(saved.kind, 'scenario'); assert.equal(saved.ref, scenarioRef);
    assert.deepEqual(saved.preferences, expected);
    return { scenario_ref: scenarioRef, url: surface.url(), controls: values, local_storage_raw: raw };
  }
  const selected = await observed(page);
  await page.reload(); await page.locator('[data-open-kind="scenario"] .tt-main').waitFor();
  await page.getByRole('table', { name: '资源占用', exact: true }).waitFor(); await flush();
  const reloaded = await observed(page);
  assert.equal(reloaded.local_storage_raw, selected.local_storage_raw);
  assert.deepEqual(h.last(value => value.scenario_ref === scenarioRef && value.tasks), original);
  const sameUrl = page.url(), responseStart = report.responses.length, newPageStart = report.requests.length;
  const other = await h.newTab(sameUrl); let fresh;
  try {
    await other.page.locator('[data-open-kind="scenario"] .tt-main').waitFor();
    await other.page.getByRole('table', { name: '资源占用', exact: true }).waitFor(); await flush();
    assert.equal(other.page.url(), sameUrl);
    assert.equal(await other.page.evaluate(() => history.state && history.state.trialAdoptionHistory || null), null,
      'A genuinely new page must recover from LS without a copied history entry');
    fresh = await observed(other.page); assert.equal(fresh.local_storage_raw, selected.local_storage_raw);
    const response = report.responses.slice(responseStart).findLast(row => row.body && row.body.data
      && row.body.data.scenario_ref === scenarioRef && row.body.data.tasks);
    assert(response, 'The new page must read the actual original scenario'); assert.deepEqual(response.body.data, original);
    assert(report.requests.slice(newPageStart).some(row => row.method === 'GET'
      && new URL(row.url).pathname === '/api/workbench/v1/trial/scenarios/' + scenarioRef));
  } finally { await other.page.close(); }
  await flush();
  assert(report.requests.slice(requestStart).every(row => row.method === 'GET'));
  report.trial_view_recovery = { scenario_ref: scenarioRef, draft_ref: original.draft_ref, storage_key: storageKey,
    selected, f5: reloaded, same_url_new_page: fresh, original_scenario_unchanged: true,
    real_controls_and_keyboard: true, request_start: requestStart, request_end: report.requests.length };
}

async function nativeExportFailure(page, ready, report, h, flush) {
  await h.action(['WBP-TRIAL-011.export-failure'], async () => {
    const observed = [], listener = value => observed.push(value);
    page.on('download', listener);
    const before = snapshot(ready, 'native-export-before');
    try {
      await page.evaluate(() => {
        const original = URL.createObjectURL;
        window.__dNativeExport = { original, calls: 0 };
        URL.createObjectURL = function (blob) {
          const witness = window.__dNativeExport;
          witness.calls++; witness.received_blob = blob instanceof Blob; witness.bytes = blob.size;
          // Fault the native browser API's argument, not the business response or network.
          try { return Reflect.apply(original, URL, [null]); }
          catch (error) { witness.name = error.name; witness.message = error.message; throw error; }
          finally { URL.createObjectURL = original; }
        };
      });
      await h.button('导出对比').click(); await flush();
      const failure = await page.evaluate(() => {
        const value = window.__dNativeExport;
        return { calls: value.calls, received_blob: value.received_blob, bytes: value.bytes,
          name: value.name, message: value.message, native_restored: URL.createObjectURL === value.original };
      });
      assert.equal(failure.calls, 1); assert.equal(failure.received_blob, true); assert(failure.bytes > 0);
      assert.equal(failure.name, 'TypeError'); assert(failure.message); assert.equal(failure.native_restored, true);
      await page.getByRole('alert').filter({ hasText: failure.message }).waitFor();
      assert.equal(observed.length, 0, 'The failed native API must not produce a successful download');
      const after = snapshot(ready, 'native-export-after');
      assert.equal(before.sha256, after.sha256); assert.equal(before.tables, after.tables);
      await h.shot('required-native-export-error');
      const data = h.last(value => value.scenario_ref === ready.expected.required.scenario_ref && value.tasks);
      const expected = await page.evaluate(value => window.TrialExport.csv(value).text, data);
      const downloading = page.waitForEvent('download');
      await h.button('导出对比').click();
      const file = await downloading, destination = path.join(ready.root, 'downloads', 'required-retry.csv');
      await file.saveAs(destination); assert.equal(await file.failure(), null);
      assert.deepEqual(fs.readFileSync(destination), Buffer.from(expected, 'utf8'));
      assert.equal(await page.getByRole('alert').filter({ hasText: failure.message }).count(), 0);
      assert.equal(observed.length, 1);
      report.native_export_failure = { scenario_ref: data.scenario_ref, native_api: 'URL.createObjectURL',
        fault: 'one call delegates an invalid argument to the original Chromium API', failure, before, after,
        all_tables_and_schema_equal: true, retry: { path: destination, sha256: hash(fs.readFileSync(destination)) } };
      report.downloads.push(destination);
    } finally {
      page.off('download', listener);
      await page.evaluate(() => { const value = window.__dNativeExport; if (value) { URL.createObjectURL = value.original; delete window.__dNativeExport; } });
    }
  });
}

async function requiredReadonly(page, ready, report, h, flush) {
  const expected = ready.expected.required;
  assert.equal(expected.case, 'readonly');
  await h.action(['WBP-RUN-007.no-result'], async () => {
    await page.goto(navigation(ready, 'run', { run_ref: expected.run_ref }));
    await page.getByText('这次排产没有保存候选方案。', { exact: true }).waitFor(); await theme(page, report); await flush();
    const data = h.last(value => value.run_ref === expected.run_ref && Array.isArray(value.candidates));
    assert.equal(data.state, 'failed'); assert.equal(data.result_persisted, false); assert.deepEqual(data.candidates, []);
    assert.equal(data.error.code, 'snapshot_stale');
    assert.equal(await page.getByRole('table', { name: '已保存候选', exact: true }).count(), 0);
    assert.equal(await h.button('详情', page.getByRole('region', { name: '这次排产', exact: true })).count(), 0);
    await page.reload(); await page.getByText('这次排产没有保存候选方案。', { exact: true }).waitFor(); await flush();
    assert.deepEqual(h.last(value => value.run_ref === expected.run_ref && Array.isArray(value.candidates)), data);
    report.no_result = { run: data, reload_same_record: true };
  });
  await h.action(['WBP-GANTT-002.conflict-track'], async () => {
    await page.goto(navigation(ready, 'gantt', { plan_ref: ready.expected.original_plan_ref }));
    await page.locator('[data-plan-gantt]').waitFor(); await flush();
    const data = h.last(value => value.plan && value.tasks);
    assert.equal(data.plan.plan_ref, ready.expected.original_plan_ref);
    const resource = data.projections.occupancy.resources.find(row => row.kind === 'machine' && row.has_overlap);
    assert(resource); assert.equal(resource.overlap_hours, .25);
    assert.deepEqual(resource.segments.filter(row => row.concurrent_operations > 1), [
      { start: '2026-09-09T08:30:00', end: '2026-09-09T08:45:00', concurrent_operations: 2 }
    ]);
    const tasks = data.tasks.filter(row => row.machine_ref === resource.resource_ref);
    assert.equal(tasks.length, 2);
    const locations = [];
    for (const task of tasks) {
      const bar = page.locator('[data-plan-task="' + task.task_ref + '"]:not([data-before])');
      await bar.waitFor(); assert((await bar.getAttribute('class')).split(' ').includes('conflict'));
      locations.push(await bar.evaluate(node => {
        const box = node.getBoundingClientRect();
        return { task_ref: node.dataset.planTask, top: box.top, bottom: box.bottom, lane: node.closest('.plan-lane').style.top };
      }));
    }
    assert.notEqual(locations[0].lane, locations[1].lane);
    assert(locations[0].bottom <= locations[1].top || locations[1].bottom <= locations[0].top);
    await h.shot('required-persistent-conflict-tracks');
    await page.reload(); await page.locator('[data-plan-gantt]').waitFor(); await flush();
    const restored = h.last(value => value.plan && value.tasks);
    assert.deepEqual(restored.tasks, data.tasks); assert.deepEqual(restored.projections.occupancy, data.projections.occupancy);
    report.conflict_track = { plan_ref: data.plan.plan_ref, resource, tasks, locations, reload_same_projection: true };
  });
  const l5Start = report.requests.length, l5Before = snapshot(ready, 'l5-readonly-before');
  await delayConflictDetails(page, ready, report, h, flush);
  const trialStart = report.requests.length;
  await page.goto(navigation(ready, 'trial', { scenario_ref: expected.scenario_ref }));
  await page.locator('[data-open-kind="scenario"] .tt-main').waitFor(); await flush();
  await trialViewRecovery(page, ready, report, h, flush, trialStart);
  const l5After = snapshot(ready, 'l5-readonly-after');
  assert.equal(l5After.sha256, l5Before.sha256); assert.equal(l5After.tables, l5Before.tables);
  assert(report.requests.slice(l5Start).every(row => row.method === 'GET'));
  report.l5_readonly_witness = { before: l5Before, after: l5After, all_tables_and_schema_equal: true,
    request_start: l5Start, request_end: report.requests.length, only_get: true };
  // Keep the existing pytest node's original action-set contract; add only explicit L5 evidence.
  report.required_l5_actions = [{ action_id: 'WBP-DELAY-004.conflicts', status: 'passed', gates: { K: 'passed', P: 'passed' },
    request_start: report.delay_conflicts.request_start, request_end: report.delay_conflicts.request_end,
    evidence: 'delay_conflicts', database_witness: 'l5_readonly_witness' }].concat([
    'WBP-TRIAL-003.mode', 'WBP-TRIAL-003.baseline', 'WBP-TRIAL-003.only-changed', 'WBP-TRIAL-003.search',
    'WBP-TRIAL-010.tabs', 'WBP-TRIAL-010.keyboard'
  ].map(action_id => ({ action_id, status: 'passed', gates: { P: 'passed' }, request_start: trialStart,
    request_end: report.trial_view_recovery.request_end, evidence: 'trial_view_recovery', database_witness: 'l5_readonly_witness' })));
  await nativeExportFailure(page, ready, report, h, flush);
  assert(report.requests.every(row => row.method === 'GET'), 'The required read-only cases cannot write business data');
}
module.exports = { requiredReadonly, navigation, snapshot, theme };
