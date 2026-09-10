'use strict';
const assert = require('node:assert/strict');
const { run } = require('./final_execution_browser_support.cjs');
const { files } = require('./final_execution_field_files.cjs');
const { actual } = require('./final_execution_actual.cjs');

async function exercise(p, phase) {
  const { page, ready } = p, seed = ready.expected.final_e, taskRef = seed.task_refs['1'];
  const list = '/execution/tasks', detail = '/execution/tasks/' + taskRef;
  const readField = () => p.read(() => page.locator('.sidebar a[href$="?view=field"]').click(), list);
  const open = async () => {
    const row = page.locator('[data-field-task="' + taskRef + '"]');
    await row.waitFor();
    if (await row.locator('button[aria-expanded]').getAttribute('aria-expanded') !== 'true')
      await p.read(() => row.locator('button[aria-expanded]').click(), detail);
    await page.getByRole('table', { name: '逐次报工记录', exact: true }).waitFor();
  };
  const done = async () => {
    const response = await p.read(() => page.getByRole('button', { name: '重读已确认结果', exact: true }).click(), list);
    await page.getByRole('table', { name: '逐次报工记录', exact: true }).waitFor();
    return response;
  };
  if (phase === 'restart') {
    await readField(); await open();
    await p.step(['WBP-FIELD-004', 'WBP-FIELD-012'], 'real-process-restart-original-report-revisions-visible', async () => {
      const table = page.getByRole('table', { name: '逐次报工记录', exact: true });
      assert.equal(await table.locator('tbody > tr').count(), 2);
      assert((await table.innerText()).includes('2'));
      await page.getByRole('button', { name: /^录入信息 BG/ }).first().click();
      await page.getByText('逐项复核有效工时', { exact: false }).waitFor();
      await p.shot('restart-original-report-history');
    });
    await p.read(() => page.getByRole('button', { name: '实际甘特', exact: true }).click(), '/actual-gantt');
    await actual(p, { includeWrites: false });
    return;
  }
  const initial = await readField(); p.report.initial = initial;
  await p.step(['WBP-FIELD-001', 'WBP-FIELD-002', 'WBP-FIELD-003'], 'real-status-filters-search-page-size-and-counts', async () => {
    assert.equal(initial.data.summary.tasks, 33); assert.equal(initial.data.summary.reports, 7);
    const metrics = await page.locator('.field-metrics').innerText();
    assert.equal(await page.locator('.field-metrics > span').count(), 5);
    assert(metrics.includes('累计实报工时') && metrics.includes('未知') && metrics.includes('已知小计 3 h'));
    assert.deepEqual(initial.data.summary.state_counts, { complete: 1, exception: 0, partial: 1, paused: 1, started: 1, unreported: 29 });
    for (const [state, label] of [['unreported', '待报工'], ['started', '已登记开工'], ['partial', '部分完成'],
      ['paused', '已暂停'], ['exception', '异常'], ['complete', '已完工'], ['all', '全部']]) {
      const result = await p.read(() => page.getByRole('group', { name: '报工状态' }).getByRole('button', { name: label, exact: true }).click(), list);
      if (state === 'all') assert.equal(Object.prototype.hasOwnProperty.call(result.data.scope, 'state'), false);
      else assert.equal(result.data.scope.state, state);
      if (state !== 'all') assert(result.data.tasks.every(row => row.execution.execution_state === state));
      assert.deepEqual(result.data.summary.state_counts, initial.data.summary.state_counts);
      assert.equal(Number(await page.locator('[data-field-state-count="' + state + '"]').innerText()), state === 'all' ? 33 : initial.data.summary.state_counts[state]);
    }
    const search = page.getByRole('searchbox', { name: '搜索批次或工序', exact: true });
    for (const [query, count] of [['B1', 33], ['Part', 33], ['30 Turning', 1], ['中文车床', 33], ['中文人员', 33],
      [seed.original_report.report_no, 1]]) {
      await search.fill(query);
      const found = await p.read(() => page.getByRole('button', { name: '查询现场记录' }).click(), list);
      assert.equal(found.data.page.total, count, query);
    }
    await search.fill('NO-SUCH-FINAL-E');
    const empty = await p.read(() => page.getByRole('button', { name: '查询现场记录' }).click(), list);
    assert.equal(empty.data.page.total, 0); await page.getByText('当前范围没有任务', { exact: true }).waitFor();
    await p.read(() => page.getByRole('button', { name: '清除现场筛选' }).click(), list);
    await p.read(() => p.choose('现场每页数量', '10'), list);
    const page2 = await p.read(() => page.getByRole('button', { name: '现场下一页' }).click(), list);
    assert.equal(page2.data.page.number, 2);
    await p.read(() => page.getByRole('button', { name: '现场上一页' }).click(), list);
    await p.read(() => p.choose('现场每页数量', '50'), list);
    await p.shot('field-main');
  });
  await open();
  await p.step(['WBP-FIELD-006', 'WBP-FIELD-008', 'WBP-FIELD-010'], 'keyboard-create-start-only-unknown-not-zero', async () => {
    await page.getByRole('button', { name: '新增本次报工', exact: true }).click();
    await page.getByLabel('实际开工', { exact: true }).fill('2026-09-02T08:00');
    const saved = await p.read(() => page.getByRole('button', { name: '保存报工', exact: true }).click(), detail + '/reports');
    const after = await done();
    const report = after.data.tasks.find(row => row.task_ref === taskRef).execution.reports.find(row => row.report_ref === saved.data.rows[0].report_ref);
    p.report.created = report; p.report.receipts = [saved];
    assert.equal(report.completed_quantity, null); assert.equal(report.effective_processing_hours, null);
    assert.equal(report.actual_end, null); assert.equal(report.recorded_against_task_ref, taskRef);
    await page.getByRole('button', { name: '作业时间线', exact: true }).click();
    await page.locator('[data-field-point="report"]').first().hover();
    await page.getByRole('tooltip').waitFor(); await p.shot('start-only-unknown-end');
    await page.getByRole('button', { name: '作业时间线', exact: true }).click();
  });
  await p.step(['WBP-FIELD-006', 'WBP-FIELD-007', 'WBP-FIELD-009', 'WBP-FIELD-010'], 'supplement-real-quantity-resource-hours', async () => {
    await page.getByRole('button', { name: '补齐 ' + p.report.created.report_no, exact: true }).click();
    await page.getByRole('spinbutton', { name: '本次完成数量', exact: true }).fill('3');
    await page.getByLabel('本次实际完工', { exact: true }).fill('2026-09-02T09:00');
    await page.getByRole('spinbutton', { name: '有效工时 (h)', exact: true }).fill('0.75');
    await p.choose('实际设备', seed.machine_ref); await p.choose('实际人员', seed.operator_ref);
    await page.getByLabel('作业备注', { exact: true }).fill('三件首批真实报工');
    await page.getByLabel('补齐或更正原因', { exact: true }).fill('根据原始报工单补齐');
    await p.shot('supplement-input');
    const saved = await p.read(() => page.getByRole('button', { name: '保存报工', exact: true }).click(), '/reports/' + p.report.created.report_ref + '/supplement');
    p.report.receipts.push(saved); await done();
  });
  await p.step(['WBP-FIELD-005', 'WBP-FIELD-012'], 'correction-required-reason-and-three-original-revisions', async () => {
    await page.getByRole('button', { name: '更正 ' + p.report.created.report_no, exact: true }).click();
    const reason = page.getByLabel('补齐或更正原因', { exact: true });
    assert.equal(await reason.getAttribute('required'), '');
    await page.getByRole('spinbutton', { name: '本次完成数量', exact: true }).fill('2');
    await page.getByRole('spinbutton', { name: '有效工时 (h)', exact: true }).fill('0.5');
    await reason.fill('逐项复核有效工时');
    const saved = await p.read(() => page.getByRole('button', { name: '保存更正', exact: true }).click(), '/reports/' + p.report.created.report_ref + '/correct');
    p.report.receipts.push(saved);
    const after = await done();
    assert.equal(after.data.tasks.find(row => row.task_ref === taskRef).execution.reports[0].correction_history.length, 3);
    await page.getByRole('button', { name: '录入信息 ' + p.report.created.report_no, exact: true }).click();
    await page.getByText('逐项复核有效工时', { exact: false }).waitFor(); await p.shot('original-three-revisions');
    await page.getByRole('button', { name: '录入信息 ' + p.report.created.report_no, exact: true }).click();
  });
  await p.step(['WBP-FIELD-013'], 'draft-navigation-and-explicit-cancel-boundary', async () => {
    await page.getByRole('button', { name: '新增本次报工', exact: true }).click();
    await page.getByRole('spinbutton', { name: '本次完成数量', exact: true }).fill('4');
    const collapsedDisabled = await page.locator('[data-field-task="' + taskRef + '"] button[aria-expanded]').isDisabled();
    const otherRows = await page.locator('[data-field-task]:not([data-field-task="' + taskRef + '"]) button[aria-expanded]').evaluateAll(nodes =>
      nodes.map(node => ({ task_ref: node.closest('[data-field-task]').dataset.fieldTask, disabled: node.disabled })));
    assert.equal(collapsedDisabled, false); assert(otherRows.every(row => !row.disabled));
    await p.shot('draft-before-navigation');
    await page.locator('[data-field-task="' + taskRef + '"] button[aria-expanded]').click();
    await page.locator('.field-editor').waitFor({ state: 'hidden' });
    await open(); assert.equal(await page.getByLabel('本次完成数量', { exact: true }).inputValue(), '4');
    const other = seed.task_refs['30'];
    await p.read(() => page.locator('[data-field-task="' + other + '"] button[aria-expanded]').click(), list + '/' + other);
    await page.getByRole('button', { name: '新增本次报工', exact: true }).click();
    await page.getByLabel('本次完成数量', { exact: true }).fill('1');
    await open(); assert.equal(await page.getByLabel('本次完成数量', { exact: true }).inputValue(), '4');
    assert(await page.getByLabel('本次完成数量', { exact: true }).evaluate(node => document.activeElement === node));
    await page.getByRole('button', { name: '取消', exact: true }).click();
    await p.read(() => page.locator('[data-field-task="' + other + '"] button[aria-expanded]').click(), list + '/' + other);
    assert.equal(await page.getByLabel('本次完成数量', { exact: true }).inputValue(), '1');
    await page.getByRole('button', { name: '取消', exact: true }).click();
    await open(); await page.getByRole('button', { name: '新增本次报工', exact: true }).click();
    assert.equal(await page.getByLabel('本次完成数量', { exact: true }).inputValue(), '');
    await page.getByLabel('本次完成数量', { exact: true }).fill('4');
    await p.nav('报表中心', '/analytics'); await readField(); await open();
    await page.getByRole('button', { name: '新增本次报工', exact: true }).click();
    const restored = await page.getByRole('spinbutton', { name: '本次完成数量', exact: true }).inputValue();
    assert.equal(restored, '', 'The read-only history contract must not restore a write form');
    const history = await page.evaluate(() => window.history.state.workbench.context);
    assert.equal(Object.prototype.hasOwnProperty.call(history, 'editor'), false);
    assert.equal(Object.prototype.hasOwnProperty.call(history, 'draft'), false);
    await page.getByRole('button', { name: '取消', exact: true }).click();
  });
  await p.step(['WBP-FIELD-007', 'WBP-FIELD-011', 'WBP-FIELD-014'], 'remaining-all-completes-whole-operation-not-plan-quantity', async () => {
    await page.getByRole('button', { name: '新增本次报工', exact: true }).click();
    await page.getByLabel('实际开工', { exact: true }).fill('2026-09-02T10:00');
    await page.getByLabel('本次实际完工', { exact: true }).fill('2026-09-02T12:00');
    await page.getByRole('spinbutton', { name: '有效工时 (h)', exact: true }).fill('1.5');
    await page.locator('.field-editor details > summary').click();
    await p.choose('实际设备', seed.machine_ref); await p.choose('实际人员', seed.operator_ref);
    const saved = await p.read(() => page.getByRole('button', { name: '剩余全部完工', exact: true }).click(), detail + '/reports');
    p.report.receipts.push(saved);
    const after = await done(), current = after.data.tasks.find(row => row.task_ref === taskRef);
    assert.equal(current.execution.reports.find(row => row.report_ref === saved.data.rows[0].report_ref).completed_quantity, 8);
    assert.equal(current.quantity, null); assert.equal(current.quantity_reason, 'plan_target_not_recorded');
    assert.equal(current.execution.target_quantity, 10); assert.equal(current.execution.known_completed_quantity, 10);
    assert.equal(current.execution.execution_state, 'complete'); p.report.completed_task = current;
    await page.getByRole('button', { name: '作业时间线', exact: true }).click(); await p.shot('completed-timeline');
  });
  await files(p);
  await open();
  await p.read(() => page.getByRole('button', { name: '实际甘特', exact: true }).click(), '/actual-gantt');
  await actual(p, { includeWrites: false });
}
async function visuals(p) {
  await p.page.locator('[data-field-workspace]').waitFor();
  await p.shot('field-viewport');
  await p.read(() => p.page.locator('.sidebar a[href$="?view=fieldgantt"]').click(), '/actual-gantt');
  await p.page.locator('[data-actual-scroll]').waitFor(); await p.shot('actual-viewport');
  await p.read(() => p.page.locator('.sidebar a[href$="?view=field"]').click(), '/execution/tasks');
}
run('field', exercise, { once: true, visuals });
