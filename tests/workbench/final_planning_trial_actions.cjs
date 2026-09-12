'use strict';
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const { trialControls } = require('./final_planning_trial_controls.cjs');
const { originalTaskEntry } = require('./final_planning_process_order.cjs');
const { trialConstraints } = require('./final_planning_trial_constraints.cjs');
const { trialStorageFailure } = require('./final_planning_storage_failure.cjs');
const { trialStaleWrite } = require('./final_planning_stale_write.cjs');

async function trialActions(page, ready, report, h, flush) {
  const { action, button, shot, last, selectTrial } = h;
  await action(['WBP-PLAN-005.trial-navigation', 'WBP-TRIAL-002.source', 'WBP-TRIAL-004.full-scope', 'WBP-GANTT-004.trial-link'], async () => {
    report.original_draft = await originalTaskEntry(page, report, h, flush);
    assert.equal(report.original_draft.task_count, ready.expected.task_count);
    assert.equal(report.original_draft.base.plan_ref, report.first_official.plan.plan_ref);
    report.draft_ref = report.original_draft.draft_ref;
    await h.caption(report.draft_ref, '试调草稿');
    assert.equal(report.original_draft.tasks.filter(task => task.start === task.end).length, 4);
    await h.pixels('.tt-gantt', 'trial'); await shot('trial-complete');
  });
  await trialControls(page, report, h, flush);
  await trialConstraints(page, report, h, flush);
  await trialStorageFailure(page, report, h, flush);
  await trialStaleWrite(page, ready, report, h, flush);
  await action(['WBP-TRIAL-004.execution', 'WBP-TRIAL-006.lock', 'WBP-TRIAL-006.actuals'], async () => {
    await selectTrial(10); assert(await button('调整此工序').isDisabled());
    await selectTrial(10, null, 'B2'); assert(await button('调整此工序').isDisabled());
    await shot('locked-and-execution-protection');
  });
  await action(['WBP-TRIAL-005.cancel', 'WBP-TRIAL-012.leave-guard'], async () => {
    const before = report.requests.length;
    await selectTrial(50, 'item-B'); await button('调整此工序').click();
    await page.getByLabel('调整开工', { exact: true }).fill('2026-09-09T13:00');
    await button('返回方案').click();
    const discard = page.getByRole('dialog', { name: '离开前确认', exact: true });
    await discard.getByText('试调工序的设备、人员或开工调整尚未保存。', { exact: true }).waitFor();
    await button('留在当前页面', discard).click(); await discard.waitFor({ state: 'hidden' });
    assert.equal(await page.getByLabel('调整开工', { exact: true }).inputValue(), '2026-09-09T13:00');
    assert.equal(await page.locator('[data-trial-workspace]').getAttribute('data-open-ref'), report.draft_ref);
    await button('取消编辑').click();
    await button('放弃未保存内容并继续', discard).click(); await discard.waitFor({ state: 'hidden' });
    assert.equal(await page.getByLabel('调整开工', { exact: true }).count(), 0);
    assert.equal(await page.locator('[data-trial-workspace]').getAttribute('data-open-ref'), report.draft_ref);
    assert(!report.requests.slice(before).some(row => /\/change$/.test(row.url)));
  });
  await action(['WBP-TRIAL-005.resources', 'WBP-TRIAL-005.date', 'WBP-TRIAL-005.save',
    'WBP-TRIAL-006.precedence-conflict'], async () => {
    await selectTrial(50, 'item-B'); await button('调整此工序').click();
    const machines = page.getByRole('combobox', { name: '调整设备', exact: true });
    const people = page.getByRole('combobox', { name: '调整人员', exact: true });
    await machines.selectOption({ label: 'M2 · Lathe 2' });
    await people.selectOption({ label: 'O2 · Operator 2' });
    await page.getByLabel('调整开工', { exact: true }).fill('2026-09-09T08:00');
    await button('保存调整').click(); await button('调整此工序').waitFor(); await flush();
    report.conflict = last(data => data.draft_ref === report.draft_ref && data.tasks);
    assert.equal(report.conflict.validation.constraints_status, 'blocked');
    assert(report.conflict.validation.issues.length > 0);
    await page.getByRole('tab', { name: '约束问题', exact: true }).click(); await shot('precedence-conflict');
  });
  await action(['WBP-TRIAL-005.repair-conflict', 'WBP-TRIAL-006.valid-point'], async () => {
    await selectTrial(50, 'item-B'); await button('调整此工序').click();
    const original = report.original_draft.tasks.find(task => task.sequence === 50 && task.piece_id === 'item-B');
    await page.getByLabel('调整开工', { exact: true }).fill(original.start.slice(0, 16));
    await page.getByRole('combobox', { name: '调整设备', exact: true }).selectOption(original.machine_ref);
    await page.getByRole('combobox', { name: '调整人员', exact: true }).selectOption(original.operator_ref);
    await button('保存调整').click(); await button('调整此工序').waitFor(); await flush();
    assert.equal(last(data => data.draft_ref === report.draft_ref && data.tasks).validation.constraints_status, 'valid');
    await selectTrial(60); await button('调整此工序').click();
    await page.getByLabel('调整开工', { exact: true }).fill('2026-09-09T13:00');
    await button('保存调整').click(); await button('调整此工序').waitFor(); await flush();
    const changed = last(data => data.draft_ref === report.draft_ref && data.tasks);
    assert.equal(changed.validation.constraints_status, 'valid');
    const point = changed.tasks.find(task => task.sequence === 60);
    assert.equal(point.start, '2026-09-09T13:00:00'); assert.equal(point.start, point.end);
    assert.equal(point.hours.total_hours, 0); assert.equal(point.quantity, 3);
    await shot('point-move-saved');
  });
  await action(['WBP-TRIAL-010.tabs', 'WBP-TRIAL-010.keyboard', 'WBP-TRIAL-004.capacity'], async () => {
    const tabs = page.getByRole('tablist', { name: '试调结果', exact: true });
    for (const name of ['批次对比', '资源占用', '调整记录', '采用记录', '未排工序', '完整任务']) {
      await tabs.getByRole('tab', { name, exact: true }).click(); await flush();
    }
    await tabs.getByRole('tab', { name: '完整任务', exact: true }).press('Home');
    assert.equal(await tabs.getByRole('tab', { name: '批次对比', exact: true }).getAttribute('aria-selected'), 'true');
    await tabs.getByRole('tab', { name: '批次对比', exact: true }).press('End');
    await tabs.getByRole('tab', { name: '未排工序', exact: true }).press('ArrowLeft');
    await shot('trial-tabs-keyboard');
  });
  await action(['WBP-TRIAL-008.cancel'], async () => {
    await button('放弃草稿').click(); const dialog = page.getByRole('dialog');
    await button('取消', dialog).click();
    assert(!report.requests.some(row => /\/discard$/.test(row.url)));
  });
  await action(['WBP-TRIAL-007.save-scenario', 'WBP-TRIAL-011.csv', 'WBP-TRIAL-011.raw'], async () => {
    await button('保存场景').click(); const dialog = page.getByRole('dialog');
    report.scenario_name = 'D final planning ' + report.width + ' ' + report.theme;
    await dialog.getByLabel('场景名称', { exact: true }).fill(report.scenario_name);
    await dialog.getByRole('checkbox', { name: '确认保存完整场景，冲突和未排工序一并保留', exact: true }).check();
    await button('确认保存场景', dialog).click();
    await page.locator('[data-open-kind="scenario"] .tt-main').waitFor(); await flush();
    report.scenario_ref = await page.locator('[data-trial-workspace]').getAttribute('data-open-ref');
    report.scenario = last(data => data.scenario_ref === report.scenario_ref && data.tasks);
    await h.caption(report.scenario_ref, '已存场景预览');
    for (const name of ['导出对比', '导出原始数据']) {
      const pending = page.waitForEvent('download'); await button(name).click(); const file = await pending;
      const destination = path.join(ready.root, 'downloads', file.suggestedFilename()); await file.saveAs(destination);
      assert.equal(await file.failure(), null); assert(fs.statSync(destination).size > 100);
      report.downloads.push(destination);
    }
    await shot('saved-scenario');
  });
  await action(['WBP-TRIAL-007.cancel', 'WBP-TRIAL-007.reason', 'WBP-TRIAL-007.confirm'], async () => {
    report.second_official = await h.confirmAdopt('trial');
    assert.equal(report.second_official.plan.version, 6);
    assert.equal(report.second_official.tasks.length, ready.expected.task_count);
    const task = report.second_official.tasks.find(row => row.sequence === 60);
    assert.equal(task.start, '2026-09-09T13:00:00'); assert.equal(task.start, task.end);
  });
  await action(['WBP-TRIAL-012.reload', 'WBP-TRIAL-007.recover-receipt', 'WBP-TRIAL-001.return-source'], async () => {
    await page.goBack(); await page.locator('[data-open-kind="scenario"] .tt-main').waitFor();
    await page.reload(); await page.locator('[data-open-kind="scenario"] .tt-main').waitFor(); await flush();
    assert.equal(await page.locator('[data-trial-workspace]').getAttribute('data-open-ref'), report.scenario_ref);
    assert.deepEqual(last(data => data.scenario_ref === report.scenario_ref && data.tasks).tasks, report.scenario.tasks);
    await page.locator('.trial-adoption-action').getByRole('button').first().click();
    const dialog = page.getByRole('dialog'); await button('查询原请求', dialog).click();
    await button('进入正式方案', dialog).waitFor(); await shot('original-receipt');
    await button('关闭', dialog.locator('.modal-f')).click();
    await button('返回方案').click(); await page.locator('[data-plan-workspace] .plan-main').waitFor(); await flush();
    assert.equal(last(data => data.plan && data.tasks).plan.plan_ref, report.first_official.plan.plan_ref);
    assert.deepEqual(last(data => data.plan && data.tasks).tasks, report.first_official.tasks);
    await shot('original-plan-return');
  });
  await action(['WBP-TRIAL-008.confirm', 'WBP-TRIAL-009.reset-disposition'], async () => {
    const draft = await h.createTrial();
    assert.notEqual(draft.draft_ref, report.draft_ref);
    assert.equal(draft.base.plan_ref, report.first_official.plan.plan_ref);
    await button('放弃草稿').click();
    const dialog = page.getByRole('dialog', { name: '确认放弃草稿', exact: true });
    assert(await button('确认放弃', dialog).isDisabled());
    await dialog.getByRole('checkbox', { name: '确认放弃当前指定草稿', exact: true }).check();
    const response = page.waitForResponse(row => row.url().endsWith('/discard') && row.request().method() === 'POST');
    await button('确认放弃', dialog).click();
    const receipt = await (await response).json();
    assert.equal(receipt.data.draft_ref, draft.draft_ref);
    assert.equal(receipt.data.status, 'discarded'); assert.equal(receipt.data.history_retained, true);
    await dialog.waitFor({ state: 'hidden' }); await flush();
    const discarded = last(data => data.draft_ref === draft.draft_ref && data.tasks);
    assert.equal(discarded.status, 'discarded');
    assert.equal(discarded.tasks.length, draft.tasks.length);
    for (let index = 0; index < draft.tasks.length; index += 1) {
      const { edit_context: before, ...original } = draft.tasks[index];
      const { edit_context: closed, ...retained } = discarded.tasks[index];
      assert.deepEqual(retained, original);
      assert.equal(closed.can_change, false);
      assert.deepEqual(closed.blocked_reasons.slice(0, -1), before.blocked_reasons);
      assert.equal(closed.blocked_reasons.at(-1).code, 'draft_closed');
      assert(closed.blocked_reasons.at(-1).message.length > 0);
    }
    assert(await button('放弃草稿').isDisabled()); assert(await button('保存场景').isDisabled());
    report.discarded_draft = discarded;
    await page.reload(); await page.locator('[data-trial-workspace] .tt-main').waitFor(); await flush();
    assert.equal(await page.locator('[data-trial-workspace]').getAttribute('data-open-ref'), draft.draft_ref);
    assert.equal(last(data => data.draft_ref === draft.draft_ref && data.tasks).status, 'discarded');
    await shot('discarded-draft-retained');
    await button('返回方案').click(); await page.locator('[data-plan-workspace] .plan-main').waitFor(); await flush();
    assert.equal(last(data => data.plan && data.tasks).plan.plan_ref, report.first_official.plan.plan_ref);
    assert.deepEqual(last(data => data.plan && data.tasks).tasks, report.first_official.tasks);
  });
}
module.exports = { trialActions };
