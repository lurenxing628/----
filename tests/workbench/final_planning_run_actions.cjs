'use strict';
const assert = require('node:assert/strict'), path = require('node:path');
const { pickerActions } = require('./final_planning_preflight_actions.cjs');
const { candidateNavigation, candidateTrialSource } = require('./final_planning_candidate_extra.cjs');
const { candidateStorageFailure } = require('./final_planning_storage_failure.cjs');
const { candidateDownloadFailure } = require('./final_planning_download_failure.cjs');
const { candidateAnalysis, candidateHistory } = require('./final_planning_analysis_actions.cjs');

async function runActions(page, ready, report, h, flush) {
  const { button, action, shot, last } = h;
  await page.goto(ready.run_url);
  await page.locator('[data-preflight-workspace]').getByRole('heading', { name: '执行排产', exact: true }).waitFor();
  if (await page.locator('html').getAttribute('data-theme') !== report.theme) await page.getByRole('button', { name: /^切换(?:深色|浅色)$/ }).click();
  await action(['WBP-RUN-001.open-picker', 'WBP-RUN-002.empty-guard'], async () => {
    await button('开始排产检查').click();
    await page.locator('[data-reason-group="no_eligible_tasks"]').waitFor();
    assert.equal(await button('核对并开始排产：请先选择要排产的批次。').isDisabled(), true);
    await page.locator('.rj-action-reason').getByText('请先选择要排产的批次。', { exact: true }).waitFor();
    await flush();
    assert.equal(await page.getByRole('button', { name: '确认开始排产', exact: true }).count(), 0);
    assert(!report.requests.some(row => row.method === 'POST' && row.url.endsWith('/scheduling/runs')));
    await button('选择批次').click();
    await page.getByRole('checkbox', { name: '选择 B1', exact: true }).waitFor();
  });
  await action(['WBP-RUN-002.select-all', 'WBP-RUN-002.clear', 'WBP-RUN-002.ready-only', 'WBP-RUN-002.single'], async () => {
    await button('全部待排').click(); await flush();
    await page.locator('input[aria-label="选择 B1"]:checked').waitFor();
    await page.locator('input[aria-label="选择 B2"]:checked').waitFor();
    assert(await page.getByRole('checkbox', { name: '选择 B1', exact: true }).isChecked());
    assert(await page.getByRole('checkbox', { name: '选择 B2', exact: true }).isChecked());
    await button('清除选择').click();
    assert(!await page.getByRole('checkbox', { name: '选择 B1', exact: true }).isChecked());
    assert(!await page.getByRole('checkbox', { name: '选择 B2', exact: true }).isChecked());
    await button('仅已齐套').click(); await flush();
    await page.locator('input[aria-label="选择 B1"]:checked').waitFor();
    await page.locator('input[aria-label="选择 B2"]:checked').waitFor();
    await page.getByRole('checkbox', { name: '选择 B2', exact: true }).uncheck();
    await page.getByRole('checkbox', { name: '选择 B2', exact: true }).check();
  });
  await pickerActions(page, ready, report, h, flush);
  await action(['WBP-RUN-001.dates', 'WBP-RUN-003.ready-off', 'WBP-RUN-003.ready-on',
    'WBP-RUN-003.exclude', 'WBP-RUN-003.auto-assign', 'WBP-RUN-003.actual-protected'], async () => {
    await page.getByLabel('计划开始日期', { exact: true }).fill('2026-09-09');
    await page.getByLabel('计划结束日期', { exact: true }).fill('2026-09-25');
    const date = page.getByLabel('计划开始日期', { exact: true });
    await date.press('F4');
    const calendar = page.getByRole('dialog', { name: '选择计划开始日期', exact: true });
    await calendar.getByRole('gridcell', { name: '2026-09-10', exact: true }).click();
    assert.equal(await date.inputValue(), '2026-09-10');
    await date.press('F4');
    await page.keyboard.press('Escape');
    assert.equal(await date.inputValue(), '2026-09-10');
    await date.fill('2026-09-09');
    report.shared_controls = { date_picker: 'F4 open, real day click, Escape cancel, input restored',
      source_identity: 'production preflight, immutable candidate source, official version and trial base are read from actual responses' };
    const rules = page.getByRole('radiogroup', { name: '齐套检查', exact: true });
    await rules.getByText('关闭', { exact: true }).click();
    await rules.getByText('开启', { exact: true }).click();
    const resources = page.getByRole('radiogroup', { name: '缺资源工序', exact: true });
    await resources.getByText('暂不排', { exact: true }).click();
    await resources.getByText('自动分配', { exact: true }).click();
    // 已开工工序不再是永远禁用的假单选，而是一行固定说明；这里锁住说明可见且没有残留的单选控件。
    await page.getByText('已开工工序：保留记录（不可修改）', { exact: true }).waitFor();
    assert.equal(await page.getByRole('radio', { name: '可重排', exact: true }).count(), 0);
  });
  await action(['WBP-RUN-004.check', 'WBP-RUN-004.tasks', 'WBP-RUN-004.metrics'], async () => {
    await button('开始排产检查').click();
    await page.getByText('检查明细 · ' + ready.expected.task_count + ' 道', { exact: true }).click();
    await page.getByRole('table', { name: '排产检查明细', exact: true }).waitFor();
    await flush(); const data = last((_data, row) => row.url.endsWith('/scheduling/preflight'));
    assert.equal(data.tasks.length, ready.expected.task_count);
    assert(data.tasks.some(task => task.status === 'protected'));
    assert.deepEqual(data.normalized_input.completed_policy, 'preserve_actuals');
    report.preflight = data; await shot('preflight');
  });
  await action(['WBP-RUN-006.cancel-confirm', 'WBP-RUN-006.confirm', 'WBP-RUN-006.worker-result'], async () => {
    await button('核对并开始排产').click();
    await button('取消', page.getByRole('dialog')).click(); await flush();
    assert(!report.requests.some(row => row.method === 'POST' && row.url.endsWith('/scheduling/runs')));
    await button('核对并开始排产').click(); await button('确认开始排产', page.getByRole('dialog')).click();
    await page.getByRole('table', { name: '已保存候选', exact: true }).waitFor({ timeout: 120000 });
    assert.equal(await page.getByRole('table', { name: '已保存候选', exact: true }).getByRole('button', { name: '详情', exact: true }).count(), 4);
    await shot('worker-four-candidates');
  });
  await action(['WBP-RUN-006.recover-run'], async () => {
    await flush();
    const original = last(data => data.found === true && data.run && data.run.state === 'complete').run;
    const writes = report.requests.filter(row => row.method === 'POST' && row.url.endsWith('/scheduling/runs')).length;
    await page.reload();
    await page.getByRole('table', { name: '已保存候选', exact: true }).waitFor(); await flush();
    const restored = last(data => data.found === true && data.run && data.run.state === 'complete').run;
    assert.equal(restored.run_ref, original.run_ref); assert.deepEqual(restored.candidates, original.candidates);
    assert.equal(report.requests.filter(row => row.method === 'POST' && row.url.endsWith('/scheduling/runs')).length, writes);
    report.restored_run_ref = restored.run_ref; await shot('run-recovered');
  });
  await action(['WBP-RUN-007.real-candidate', 'WBP-ANA-002.select-four'], async () => {
    await page.getByRole('table', { name: '已保存候选', exact: true }).getByRole('button', { name: '详情', exact: true }).first().click();
    await page.getByRole('table', { name: '候选任务安排', exact: true }).waitFor();
    const table = page.getByRole('table', { name: '候选比较', exact: true });
    for (const index of [1, 2, 3, 0]) {
      await page.locator('.rc-catalog > summary').click(); await table.waitFor();
      const row = table.locator('tbody tr').nth(index), ref = await row.getAttribute('data-candidate-ref');
      const candidate = last(data => data.candidates && data.run_ref).candidates[index];
      assert.equal(ref, candidate.candidate_ref);
      const control = row.getByRole('button', { name: '查看候选 ' + candidate.label, exact: true });
      const response = page.waitForResponse(row => row.url().includes('/candidates/' + ref + '/workspace'));
      await control.click(); report.candidate = (await (await response).json()).data; await flush();
      assert.equal(report.candidate.candidate.candidate_ref, ref);
      assert.equal(await page.locator('.rc-catalog').getAttribute('open'), null);
    }
    assert.equal(report.candidate.task_count, ready.expected.task_count);
    const points = report.candidate.tasks.filter(task => task.start === task.end);
    assert.equal(points.length, 4); assert(points.every(task => task.event_kind === 'point' && task.occupies_resources === false));
    await h.candidateDetail(); await h.pixels('.rc-gantt', 'candidate'); await shot('candidate-comparison');
  });
  await candidateAnalysis(page, report, h, flush);
  await candidateNavigation(page, ready, report, h, flush);
  if (report.mode === 'candidate-source') {
    await candidateTrialSource(page, ready, report, h, flush);
    return;
  }
  await action(['WBP-ANA-004.delay', 'WBP-PLAN-005.return-comparison', 'WBP-DELAY-001.scope', 'WBP-DELAY-002.full-batch-finish',
    'WBP-DELAY-003.last-operation', 'WBP-DELAY-003.compare', 'WBP-DELAY-002.due-date', 'WBP-DELAY-004.no-root-cause-claim'], async () => {
    const original = report.candidate;
    await h.caption(original.candidate.candidate_ref, '候选方案');
    await page.getByRole('tablist', { name: '计划中心视图', exact: true }).getByRole('tab', { name: '交付风险', exact: true }).click();
    await page.locator('[data-run-candidate-workspace]').getByRole('heading', { name: '候选交付风险', exact: true }).waitFor();
    const table = page.getByRole('table', { name: '候选交付风险列表', exact: true }); await table.waitFor();
    await button('定位末端工序 B1 60', table).click();
    await shot('candidate-delivery'); await flush();
    const risk = last(data => data.candidate && data.tasks).delivery_risks;
    const batch = risk.items.find(row => row.batch_id === 'B1');
    assert.equal(batch.due_date, '2026-09-25');
    assert.equal(batch.planned_finish, original.tasks.filter(row => row.batch_label === 'B1').map(row => row.end).sort().at(-1));
    assert.equal(risk.basis.root_causes, 'not_evaluated');
    await page.getByRole('tablist', { name: '计划中心视图', exact: true }).getByRole('tab', { name: '选择排产方案', exact: true }).click();
    await page.getByRole('table', { name: '候选任务安排', exact: true }).waitFor();
    await button('读取范围').click();
    const first = original.tasks.find(row => row.batch_label === 'B1' && row.sequence === 10);
    await page.getByLabel('候选读取开始', { exact: true }).fill(first.start.slice(0, 16));
    await page.getByLabel('候选读取结束', { exact: true }).fill(first.end.slice(0, 16));
    await button('应用范围').click(); await flush();
    await page.getByText('匹配安排 1 / 1', { exact: true }).waitFor();
    await page.reload(); await page.getByText('匹配安排 1 / 1', { exact: true }).waitFor(); await flush();
    let current = last(data => data.candidate && data.tasks);
    assert.equal(current.candidate.candidate_ref, original.candidate.candidate_ref);
    assert.equal(current.time_scope.range_start, first.start); assert.equal(current.time_scope.range_end, first.end);
    assert.equal(current.delivery_risks.items[0].planned_finish, batch.planned_finish);
    await page.locator('.sidebar-nav').getByRole('link', { name: '执行排产', exact: true }).click();
    await flush();
    await page.locator('.sidebar-nav').getByRole('link', { name: '选择排产方案', exact: true }).click();
    await page.getByText('匹配安排 1 / 1', { exact: true }).waitFor(); await flush();
    current = last(data => data.candidate && data.tasks);
    assert.equal(current.time_scope.range_start, first.start);
    await h.caption(original.candidate.candidate_ref, '候选方案');
    report.candidate_scope_recovery = { candidate_ref: current.candidate.candidate_ref, range: current.time_scope, actual_sidebar_and_reload: true };
    await button('读取范围').click(); await button('完整候选').click();
    await page.getByText('匹配安排 ' + ready.expected.task_count + ' / ' + ready.expected.task_count, { exact: true }).waitFor();
    await flush(); await shot('candidate-scope-restored');
  });
  await action(['WBP-ANA-002.preview-not-adopted', 'WBP-ANA-005.csv'], async () => {
    const data = last(value => value.candidate && value.tasks);
    assert.equal(data.generation.formal_version_allocated, false);
    assert(!Object.prototype.hasOwnProperty.call(data.candidate, 'plan_ref'));
    const waiting = page.waitForEvent('download'); await button('CSV').click();
    const file = await waiting, destination = path.join(ready.root, 'downloads', file.suggestedFilename());
    await file.saveAs(destination); assert.equal(await file.failure(), null);
    await page.getByText(/^已下载 13 条记录/).waitFor();
    report.candidate_download = { path: destination, candidate_ref: data.candidate.candidate_ref,
      run_ref: data.candidate.run_ref, tasks: data.tasks };
    report.downloads.push(destination); await shot('candidate-csv-downloaded');
  });
  await candidateDownloadFailure(page, report, h, flush);
  await candidateStorageFailure(page, report, h, flush);
  await action(['WBP-PLAN-003.cancel', 'WBP-PLAN-003.reason', 'WBP-PLAN-003.operator', 'WBP-PLAN-003.confirm', 'WBP-ANA-004.adopt'], async () => {
    report.first_official = await h.confirmAdopt('candidate');
    report.first_official_url = page.url();
    assert.equal(report.first_official.plan.version, 5);
    assert.equal(report.first_official.tasks.length, ready.expected.task_count);
    await h.caption(report.first_official.plan.plan_ref, '当前正式');
  });
  await action(['WBP-PLAN-003.recover-receipt'], async () => {
    const original = report.requests.find(row => row.method === 'POST' && row.url.endsWith('/adopt'));
    const requestStart = report.requests.length;
    const writes = report.requests.filter(row => row.method === 'POST' && row.url.endsWith('/adopt')).length;
    await page.goBack(); await page.locator('[data-run-candidate-workspace]').waitFor(); await flush();
    const endpoint = '/commands/' + original.input.request_key;
    assert(report.requests.slice(requestStart).some(row => row.method === 'GET' && row.url.endsWith(endpoint)));
    const recovered = last((_data, row) => row.url.endsWith(endpoint));
    assert.equal(recovered.official_plan.plan_ref, report.first_official.plan.plan_ref);
    assert.equal(recovered.candidate_ref, report.candidate.candidate.candidate_ref);
    await page.locator('[data-run-adoption-action]').getByRole('button').first().click();
    const dialog = page.getByRole('dialog', { name: '正式采用结果', exact: true });
    await button('进入正式计划', dialog).waitFor();
    assert((await dialog.innerText()).includes('第 ' + recovered.official_plan.version + ' 版'));
    await shot('candidate-original-receipt');
    await button('进入正式计划', dialog).click(); await page.locator('[data-plan-workspace] .plan-main').waitFor(); await flush();
    assert.equal(last(data => data.plan && data.tasks).plan.plan_ref, report.first_official.plan.plan_ref);
    assert.equal(report.requests.filter(row => row.method === 'POST' && row.url.endsWith('/adopt')).length, writes);
  });
  await candidateHistory(page, report, h, flush);
}
module.exports = { runActions };
