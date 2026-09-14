'use strict';
const assert = require('node:assert/strict');
const { navigation, snapshot, theme } = require('./final_planning_required_actions.cjs');

async function competingCandidate(other, ready, report, flush) {
  const page = other.page, h = other.h;
  await page.locator('[data-preflight-workspace]').getByRole('heading', { name: '执行排产', exact: true }).waitFor();
  await h.button('选择批次').click();
  await page.getByRole('checkbox', { name: '选择 B1', exact: true }).check();
  await page.getByRole('checkbox', { name: '选择 B2', exact: true }).check();
  await page.getByLabel('计划开始日期', { exact: true }).fill('2026-09-09');
  await page.getByLabel('计划结束日期', { exact: true }).fill('2026-09-25');
  await h.button('开始排产检查').click(); await flush();
  const checked = h.last((_data, row) => row.url.endsWith('/scheduling/preflight'));
  assert.equal(checked.tasks.length, ready.expected.task_count);
  await h.button('核对并开始排产').click();
  await h.button('确认开始排产', page.getByRole('dialog')).click();
  const table = page.getByRole('table', { name: '已保存候选', exact: true });
  await table.waitFor({ timeout: 120000 }); await flush();
  const run = h.last(data => data.run_ref && data.state === 'complete' && Array.isArray(data.candidates));
  assert.notEqual(run.run_ref, ready.expected.required.run_ref);
  await table.getByRole('button', { name: '详情', exact: true }).first().click();
  await page.getByRole('table', { name: '候选任务安排', exact: true }).waitFor(); await flush();
  const candidate = h.last(data => data.candidate && data.tasks);
  assert.equal(candidate.candidate.run_ref, run.run_ref);
  const official = await h.confirmAdopt('candidate', false);
  assert.equal(official.plan.version, ready.expected.required.baseline.version + 1);
  report.competing_candidate = { run_ref: run.run_ref, candidate_ref: candidate.candidate.candidate_ref,
    official_plan: official.plan, original_tasks: candidate.tasks };
  return official;
}

async function requiredStale(page, ready, report, h, flush) {
  const expected = ready.expected.required;
  assert.equal(expected.case, 'stale');
  await h.action(['WBP-TRIAL-007.stale-conflict'], async () => {
    await page.goto(navigation(ready, 'trial', { scenario_ref: expected.scenario_ref }));
    await page.locator('[data-open-kind="scenario"] .tt-main').waitFor(); await theme(page, report); await flush();
    const original = h.last(value => value.scenario_ref === expected.scenario_ref && value.tasks);
    assert.equal(original.task_count, ready.expected.task_count);
    const previewing = page.waitForResponse(row => row.request().method() === 'POST' && row.url().endsWith('/adopt-preview'));
    await h.button('正式采用', page.locator('.trial-adoption-action')).click();
    const preview = (await (await previewing).json()).data;
    assert.equal(preview.validation.can_adopt, true); assert.equal(preview.baseline.plan_ref, expected.baseline.plan_ref);
    let dialog = page.getByRole('dialog', { name: '确认正式采用试调方案', exact: true });
    const reason = 'D required original scenario stale rejection', operator = 'D required probe';
    await dialog.getByLabel('采用原因', { exact: true }).fill(reason);
    await dialog.getByLabel('经办人', { exact: true }).fill(operator);
    await dialog.getByRole('checkbox').check();
    const other = await h.newTab(ready.run_url);
    let official;
    try { official = await competingCandidate(other, ready, report, flush); }
    finally { await other.page.close(); }
    await flush();
    assert.notEqual(official.plan.plan_ref, preview.baseline.plan_ref);
    const before = snapshot(ready, 'scenario-stale-before');
    const endpoint = '/trial/scenarios/' + expected.scenario_ref + '/adopt';
    const rejecting = page.waitForResponse(row => row.request().method() === 'POST' && row.url().endsWith(endpoint));
    await h.button('确认正式采用', dialog).click();
    const response = await rejecting, body = await response.json();
    assert.equal(response.status(), 409); assert.equal(body.ok, false); assert.equal(body.committed, false);
    assert.equal(body.error.code, 'snapshot_stale');
    report.expected_rejected_api = (report.expected_rejected_api || []).concat({ url: response.url(), method: 'POST',
      status: 409, status_text: response.statusText(), code: body.error.code });
    await dialog.getByRole('alert').filter({ hasText: '上次采用没有生效' }).waitFor(); await flush();
    const after = snapshot(ready, 'scenario-stale-after');
    assert.equal(after.sha256, before.sha256); assert.equal(after.tables, before.tables);
    assert.equal(await dialog.getByLabel('采用原因', { exact: true }).inputValue(), reason);
    assert.equal(await dialog.getByLabel('经办人', { exact: true }).inputValue(), operator);
    assert(!(await dialog.getByRole('checkbox').isChecked())); assert(await h.button('确认正式采用', dialog).isDisabled());
    const saved = await page.evaluate(() => window.TrialAdoptionState.read());
    assert.equal(saved.phase, 'rejected'); assert.equal(saved.scenario_ref, original.scenario_ref);
    assert.equal(saved.preview.baseline.plan_ref, preview.baseline.plan_ref);
    assert.equal(saved.input.reason, reason); assert.equal(saved.input.declared_operator, operator);
    assert(report.requests.some(row => row.method === 'POST' && row.url.endsWith(endpoint)
      && row.input.request_key === saved.request_key));
    await h.shot('required-original-scenario-stale-rejection');
    const restoreStart = report.requests.length;
    await page.reload(); await page.locator('[data-open-kind="scenario"] .tt-main').waitFor(); await flush();
    assert.deepEqual(h.last(value => value.scenario_ref === original.scenario_ref && value.tasks), original);
    assert.deepEqual(await page.evaluate(() => window.TrialAdoptionState.read()), saved);
    assert(report.requests.slice(restoreStart).every(row => row.method === 'GET'), 'F5 must not replay an adoption');
    await h.button('重新核对采用').click();
    dialog = page.getByRole('dialog', { name: '确认正式采用试调方案', exact: true });
    assert.equal(await dialog.getByLabel('采用原因', { exact: true }).inputValue(), reason);
    const rechecking = page.waitForResponse(row => row.request().method() === 'POST' && row.url().endsWith('/adopt-preview'));
    await h.button('重新预检', dialog).click();
    const blocked = (await (await rechecking).json()).data;
    assert.equal(blocked.validation.can_adopt, false);
    assert(blocked.validation.issues.some(row => row.code === 'snapshot_stale'));
    assert(await h.button('确认正式采用', dialog).isDisabled()); await flush();
    const final = snapshot(ready, 'scenario-stale-final'); assert.equal(final.sha256, before.sha256);
    report.scenario_stale = { scenario_ref: original.scenario_ref, original_baseline: preview.baseline,
      newer_plan: official.plan, request_key: saved.request_key, reason, declared_operator: operator,
      before, after, final, all_tables_and_schema_equal: true, f5_original_request_retained: true,
      repreview_can_adopt: blocked.validation.can_adopt, code: body.error.code };
  });
}
module.exports = { requiredStale };
