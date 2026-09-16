'use strict';
const assert = require('node:assert/strict');

async function originEdges(page, report, h, flush, draft, mapped, canonical) {
  const { button, shot, last } = h, origin = report.task_origin.origin;
  const before = report.requests.length;
  await button('返回方案').click(); await page.locator('[data-plan-workspace] .plan-main').waitFor(); await flush();
  const catalog = last(value => value.plans && value.plans.some(plan => plan.version === 4 && plan.kind === 'official' && plan.capabilities.view));
  const otherPlan = catalog.plans.find(plan => plan.version === 4 && plan.kind === 'official' && plan.capabilities.view);
  await page.locator('[data-plan-task="' + origin.task_ref + '"]:not([data-before])').click();
  await button('调整此工序', page.locator('[data-plan-inspector]')).click();
  const dialog = page.getByRole('dialog', { name: '从原来源新增试调', exact: true });
  await button('打开已有草稿', dialog).click();
  await dialog.waitFor({ state: 'hidden' }); await flush();
  const fixed = page.getByRole('checkbox', { name: '仅此原来源', exact: true });
  assert(await fixed.isChecked()); assert(await fixed.isDisabled());
  const row = page.getByRole('table', { name: '试调列表', exact: true }).locator('tr[data-trial-ref="' + draft.draft_ref + '"]');
  await button('打开', row).click(); await page.locator('[data-trial-workspace] .tt-main').waitFor(); await flush();
  assert.equal(await page.locator('[data-trial-workspace]').getAttribute('data-open-ref'), draft.draft_ref);
  assert.equal(await page.locator('.tt-gantt [data-task-ref][aria-pressed="true"]').getAttribute('data-task-ref'), mapped.task_ref);
  assert.deepEqual(last(value => value.draft_ref === draft.draft_ref && value.tasks).scope, draft.scope);
  await shot('original-task-existing-draft');
  const other = draft.tasks.find(task => task.operation_ref !== mapped.operation_ref && task.source_task_ref !== mapped.source_task_ref);
  assert(other && other.source_task_ref && otherPlan.plan_ref !== origin.plan_ref);
  report.task_origin.negative_cases = [];
  for (const [key, value, message] of [
    ['plan_ref', otherPlan.plan_ref, '当前草稿与原任务来源不一致，无法调整。'],
    ['operation_ref', other.operation_ref, '当前草稿中未找到原任务。'],
    ['task_ref', other.source_task_ref, '当前草稿中未找到原任务。'],
  ]) {
    const context = { draft_ref: draft.draft_ref, task_origin: { ...origin, [key]: value } }, target = new URL(canonical);
    target.searchParams.set('nav', JSON.stringify({ version: 1, view: 'trial', context }));
    const response = await page.goto(target.href); assert.equal(response.status(), 200);
    await page.locator('[data-trial-workspace] .tt-main').waitFor(); await flush();
    assert(await page.getByText(message, { exact: true }).count() > 0);
    assert.equal(await page.locator('.tt-gantt [data-task-ref][aria-pressed="true"]').count(), 0);
    assert(await button('保存试调方案').isDisabled()); assert(await button('放弃草稿').isDisabled());
    await h.selectTrial(20, 'item-B'); assert(await button('调整此工序').isDisabled());
    report.task_origin.negative_cases.push({ key, context, status: 200, message, no_replacement_write: true });
    await shot('original-task-rejected-' + key);
  }
  await h.action(['WBP-TRIAL-001.load-failure'], async () => {
    const target = new URL(canonical), wrongKind = report.candidate.candidate.candidate_ref;
    target.searchParams.set('nav', JSON.stringify({ version: 1, view: 'trial', context: { draft_ref: wrongKind } }));
    report.expected_rejected_api = report.expected_rejected_api || [];
    for (const reload of [false, true]) {
      const pending = page.waitForResponse(row => row.url().endsWith('/trial/drafts/' + wrongKind));
      const document = await (reload ? page.reload() : page.goto(target.href)); assert.equal(document.status(), 200);
      const response = await pending, value = await response.json();
      assert.equal(response.status(), 404); assert.equal(value.ok, false); assert(value.error.message);
      report.expected_rejected_api.push({ url: response.url(), status: response.status(), status_text: response.statusText() });
      await page.getByText(value.error.message, { exact: true }).first().waitFor(); await flush();
      assert.equal(await page.locator('[data-trial-workspace]').getAttribute('data-open-ref'), wrongKind);
      assert.equal(await page.locator('[data-trial-workspace] .tt-main').count(), 0);
      assert.equal(await page.locator('.tt-gantt [data-task-ref]').count(), 0);
      await shot('trial-missing-record-' + (reload ? 'refresh' : 'open'));
    }
  });
  await page.goto(canonical); await page.locator('[data-trial-workspace] .tt-main').waitFor(); await flush();
  assert.equal(await page.locator('.tt-gantt [data-task-ref][aria-pressed="true"]').getAttribute('data-task-ref'), mapped.task_ref);
  assert.deepEqual(last(value => value.draft_ref === draft.draft_ref && value.tasks).tasks, draft.tasks);
  assert(report.requests.slice(before).every(row => row.method === 'GET'));
  report.task_origin.existing_draft = { draft_ref: draft.draft_ref, task_ref: mapped.task_ref, read_only: true };
}
module.exports = { originEdges };
