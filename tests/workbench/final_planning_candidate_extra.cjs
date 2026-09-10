'use strict';
const assert = require('node:assert/strict');

async function candidateNavigation(page, ready, report, h, flush) {
  const { action, button, last, shot } = h, original = report.candidate;
  const heading = () => page.locator('[data-run-candidate-workspace] > .rc-heading').first();
  await action(['WBP-ANA-004.gantt'], async () => {
    const before = report.requests.length;
    await button('查看甘特', heading()).click();
    await page.getByRole('heading', { name: '候选甘特', exact: true }).waitFor(); await flush();
    const current = last(value => value.candidate && value.tasks);
    assert.equal(current.candidate.candidate_ref, original.candidate.candidate_ref);
    assert.equal(current.candidate.run_ref, original.candidate.run_ref);
    assert.deepEqual(current.tasks, original.tasks);
    await h.caption(original.candidate.candidate_ref, '候选预览'); await shot('candidate-gantt-exact-source');
    await button('交付风险', heading()).click();
    await page.getByRole('heading', { name: '候选交付风险', exact: true }).waitFor();
    await button('返回比较', heading()).click();
    await page.getByRole('heading', { name: '候选排产结果', exact: true }).waitFor(); await flush();
    assert.equal(last(value => value.candidate && value.tasks).candidate.candidate_ref, original.candidate.candidate_ref);
    assert(report.requests.slice(before).every(row => row.method === 'GET'));
  });
}

async function candidateTrialSource(page, ready, report, h, flush) {
  const { action, button, last, shot } = h, original = report.candidate;
  const heading = () => page.locator('[data-run-candidate-workspace] > .rc-heading').first();
  await action(['WBP-TRIAL-002.candidate-source'], async () => {
    const before = report.requests.length;
    await button('试调', heading()).click();
    const dialog = page.getByRole('dialog', { name: '从原来源创建试调', exact: true });
    await button('核对原来源', dialog).click();
    await dialog.getByRole('checkbox', { name: '确认基于此来源创建独立草稿，正式计划保持不变', exact: true }).check();
    await button('确认创建草稿', dialog).click();
    await page.locator('[data-trial-workspace] .tt-main').waitFor(); await flush();
    const draft = last(value => value.draft_ref && value.tasks && !value.scenario_ref);
    assert.deepEqual(draft.base, { candidate_ref: original.candidate.candidate_ref });
    assert.equal(draft.task_count, ready.expected.task_count);
    assert.deepEqual(draft.tasks.map(row => row.operation_ref).sort(), original.tasks.map(row => row.operation_ref).sort());
    assert(draft.tasks.every(row => original.tasks.some(task => task.operation_ref === row.operation_ref && task.row_ref === row.source_row_ref)));
    assert(!report.requests.slice(before).some(row => row.method === 'POST' && row.url.endsWith('/adopt')));
    report.candidate_source_draft = draft; await shot('candidate-full-draft-not-adopted');
    await button('返回方案').click(); await page.locator('[data-run-candidate-workspace] .rc-main').waitFor(); await flush();
    const returned = last(value => value.candidate && value.tasks);
    assert.equal(returned.candidate.candidate_ref, original.candidate.candidate_ref);
    assert.deepEqual(returned.tasks, original.tasks);
    await h.caption(original.candidate.candidate_ref, '候选预览');
    await shot('candidate-source-returned');
  });
  await action(['WBP-PLAN-003.stale-conflict'], async () => {
    const before = report.requests.length;
    const pending = page.waitForResponse(row => row.url().endsWith('/adopt-preview') && row.request().method() === 'POST');
    await button('正式采用', page.locator('[data-run-adoption-action]')).click();
    const response = await pending, value = await response.json();
    assert.equal(response.status(), 409); assert.equal(value.ok, false); assert.equal(value.committed, false);
    assert.equal(value.error.code, 'snapshot_stale');
    report.expected_rejected_api = [{ url: response.url(), method: 'POST', status: response.status(),
      status_text: response.statusText(), code: value.error.code }];
    const dialog = page.getByRole('dialog', { name: '确认正式采用', exact: true });
    await dialog.getByText(value.error.message, { exact: true }).waitFor();
    assert(await button('确认正式采用', dialog).isDisabled());
    assert(!report.requests.slice(before).some(row => row.method === 'POST' && row.url.endsWith('/adopt')));
    report.candidate_stale_preview = { candidate_ref: original.candidate.candidate_ref, code: value.error.code,
      committed: value.committed, phase: 'preview_after_durable_trial_create', commit_attempted: false };
    await shot('candidate-stale-after-trial-create'); await button('取消', dialog).click();
  });
}
module.exports = { candidateNavigation, candidateTrialSource };
