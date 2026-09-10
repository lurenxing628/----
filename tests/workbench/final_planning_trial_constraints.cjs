'use strict';
const assert = require('node:assert/strict');

async function trialConstraints(page, report, h, flush) {
  const { action, button, last, shot } = h;
  const original = report.original_draft.tasks.find(row => row.batch_id === 'B1' && row.sequence === 20 && row.piece_id === 'item-B');
  const resources = report.original_draft.resources;
  const machine = resources.machines.find(row => row.business_code === 'M1').ref;
  const operator = resources.operators.find(row => row.business_code === 'O1').ref;
  report.constraint_probes = [];
  async function change(patch, name) {
    await h.selectTrial(20, 'item-B');
    const detail = page.getByRole('complementary', { name: '工序详情', exact: true });
    await button('调整此工序', detail).click();
    const value = { machine_ref: original.machine_ref, operator_ref: original.operator_ref, start: original.start, ...patch };
    await page.getByRole('combobox', { name: '调整设备', exact: true }).selectOption(value.machine_ref);
    await page.getByRole('combobox', { name: '调整人员', exact: true }).selectOption(value.operator_ref);
    await page.getByLabel('调整开工', { exact: true }).fill(value.start.slice(0, 16));
    const pending = page.waitForResponse(response => response.url().endsWith('/change') && response.request().method() === 'POST');
    await button('保存调整', detail).click(); const response = await pending;
    assert.equal(response.status(), 200);
    await button('调整此工序', detail).waitFor(); await flush();
    const data = last(row => row.draft_ref === report.draft_ref && row.tasks);
    const task = data.tasks.find(row => row.task_ref === original.task_ref);
    assert.deepEqual(data.tasks.map(row => row.task_ref).sort(), report.original_draft.tasks.map(row => row.task_ref).sort());
    assert.equal(task.source_task_ref, original.source_task_ref); assert.equal(task.operation_ref, original.operation_ref);
    assert.equal(task.machine_ref, value.machine_ref); assert.equal(task.operator_ref, value.operator_ref); assert.equal(task.start, value.start);
    report.constraint_probes.push({ name, task, issues: data.validation.issues });
    return { data, task, codes: new Set(data.validation.issues.map(row => row.code)) };
  }
  async function restore() {
    const value = await change({}, 'restore-original');
    assert.equal(value.data.validation.constraints_status, 'valid');
    assert.equal(value.task.end, original.end); assert.equal(value.task.changed, false);
  }
  await action(['WBP-TRIAL-006.authorization'], async () => {
    const value = await change({ machine_ref: machine }, 'unauthorized-person');
    assert(value.codes.has('machine_authorization_missing'));
    assert.equal(value.data.validation.constraints_status, 'blocked');
    await page.getByRole('tab', { name: '约束问题', exact: true }).click(); await shot('trial-authorization-conflict');
    await restore();
  });
  await action(['WBP-TRIAL-006.overlap'], async () => {
    const value = await change({ machine_ref: machine, operator_ref: operator, start: '2026-09-09T08:00:00' }, 'real-resource-overlap');
    for (const code of ['machine_overlap', 'operator_overlap', 'precedence_violation']) assert(value.codes.has(code), code);
    await page.getByRole('tab', { name: '约束问题', exact: true }).click(); await shot('trial-resource-overlap');
    await restore();
  });
  await action(['WBP-TRIAL-006.calendar'], async () => {
    const value = await change({ start: '2026-09-09T06:00:00' }, 'outside-working-calendar');
    assert(value.codes.has('calendar_duration_conflict'));
    assert.equal(value.task.end, '2026-09-09T08:15:00');
    await page.getByRole('tab', { name: '约束问题', exact: true }).click(); await shot('trial-calendar-gap-preserved');
    await restore();
  });
  await action(['WBP-TRIAL-005.calendar-end'], async () => {
    const value = await change({ start: '2026-09-09T15:55:00' }, 'cross-day-calendar-end');
    assert.equal(value.task.end, '2026-09-10T08:10:00');
    assert.equal(value.task.hours.total_hours, .25);
    const calendar = value.data.capacity.resources.find(row => row.resource_type === 'operator' && row.resource_ref === original.operator_ref).calendar;
    assert.equal(calendar.state, 'available');
    assert(calendar.windows.some(row => row.start === '2026-09-09T08:00:00' && row.end === '2026-09-09T16:00:00'));
    await shot('trial-real-cross-day-end'); await restore();
  });
}
module.exports = { trialConstraints };
