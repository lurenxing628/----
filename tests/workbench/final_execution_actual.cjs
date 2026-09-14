'use strict';
const assert = require('node:assert/strict');

async function actual(p) {
  const { page, ready } = p, ref = ready.expected.final_e.task_refs['1'];
  const work = page.locator('[data-actual-gantt]');
  await page.locator('[data-actual-scroll]').waitFor();
  await p.step(['WBP-FG-001', 'WBP-FG-003', 'WBP-FG-007', 'WBP-FG-009'], 'same-original-plan-live-reports-selection-and-detail', async () => {
    const reading = p.report.responses.filter(row => new URL(row.url).pathname.endsWith('/actual-gantt')).slice(-1)[0].payload;
    const instant = value => Date.parse(value.replace(' ', 'T') + 'Z');
    const axisSpan = instant(reading.data.axis_span.end) - instant(reading.data.axis_span.start);
    const planStart = instant(reading.data.plan_span.start), planEnd = instant(reading.data.plan_span.end), planSpan = planEnd - planStart;
    const asOf = instant(reading.meta.as_of);
    assert(instant(reading.data.axis_span.start) <= asOf && asOf <= instant(reading.data.axis_span.end));
    await page.waitForFunction(() => history.state.workbench.context.actual_view?.position.windowSpan > 0);
    const initialView = await page.evaluate(() => history.state.workbench.context.actual_view);
    const { windowSpan: initialWindow, centerAt } = initialView.position;
    const hasPoints = reading.data.items.some(item => item.task.start === item.task.end || item.execution?.reports.some(row => row.actual_start && (!row.actual_end || row.actual_start === row.actual_end)));
    const renderedSpan = axisSpan + (hasPoints ? 2 * Math.max(60000, axisSpan * .04) : 0);
    const largestUsefulWindow = Math.max(planSpan * 1.2, renderedSpan / 1024);
    assert(initialWindow >= planSpan && initialWindow <= largestUsefulWindow + 1 && initialWindow < axisSpan,
      'The default window must show the plan at a useful scale while the full axis retains historical reports and as_of');
    assert(centerAt - initialWindow / 2 <= planStart && centerAt + initialWindow / 2 >= planEnd,
      'The default visible window must contain the plan dates, not only have the right duration');
    if (initialWindow > planSpan * 1.2) assert.equal(initialView.zoom, 1024, 'Only the renderer zoom cap may widen the plan window');
    assert.equal(await page.getByLabel('时间轴缩放模式', { exact: true }).innerText(), '手动');
    p.report.initial_actual_window = { axis_span: reading.data.axis_span, plan_span: reading.data.plan_span,
      as_of: reading.meta.as_of, visible_duration_ms: initialWindow, center_at: centerAt, zoom: initialView.zoom };
    await page.getByRole('button', { name: '定位选中工序', exact: true }).click();
    const row = page.locator('[data-task-row="' + ref + '"]').first();
    await row.locator('.fg-task-select').click();
    await page.getByRole('checkbox', { name: '详情', exact: true }).check();
    await page.getByLabel('工序详情', { exact: true }).waitFor();
    const options = await page.getByLabel('选择报工详情', { exact: true }).locator('option').evaluateAll(nodes => nodes.map(n => n.value));
    assert.equal(options.length, 3);
    await p.choose('选择报工详情', options[1]);
    await page.getByRole('button', { name: '定位本次报工', exact: true }).click();
    await p.shot('actual-selected-original-report');
    const text = await page.getByLabel('工序详情', { exact: true }).innerText();
    assert(text.includes('2'));
    const chain = await work.locator('[role=status]').allTextContents();
    p.report.critical_chain_state = chain;
    if (!(await page.getByRole('checkbox', { name: '关键链', exact: true }).count())) {
      assert(chain.some(text => text.includes('共同工序和分件之间有跨组依赖')));
      p.report.chain_boundary = 'Mixed common/piece predecessor scope is explicitly unsupported by the legacy read-only chain engine. Positive engine/target coverage is a separate real full-main chain fixture.';
    }
  });
  await p.step(['WBP-FG-004', 'WBP-FG-005', 'WBP-FG-006', 'WBP-FG-008', 'WBP-FG-010'], 'real-view-collapse-selection-keyboard-zoom-pan-and-late-filters', async () => {
    for (const mode of ['人员', '批次', '设备']) await page.getByRole('group', { name: '甘特视图' }).getByRole('button', { name: mode, exact: true }).click();
    await page.getByRole('button', { name: '全部折叠', exact: true }).click();
    assert.equal(await page.locator('[data-task-row]').count(), 0);
    await page.getByRole('button', { name: '全部展开', exact: true }).click();
    await page.getByRole('button', { name: '定位选中工序', exact: true }).click();
    await page.locator('[data-task-row="' + ref + '"] .fg-task-select').first().focus();
    await page.keyboard.press('Enter');
    await page.getByRole('checkbox', { name: '只看选中', exact: true }).check();
    assert((await page.locator('[data-actual-count]').innerText()).includes('1 / 33'));
    await page.getByRole('checkbox', { name: '只看选中', exact: true }).uncheck();
    await page.getByRole('button', { name: '适应全部', exact: true }).click();
    assert.equal(await page.getByLabel('时间轴缩放模式', { exact: true }).innerText(), '自动');
    const automaticStep = Number(await page.getByLabel('时间轴刻度', { exact: true }).getAttribute('data-tick-step'));
    await page.getByRole('button', { name: '放大时间轴', exact: true }).click();
    await page.getByRole('button', { name: '放大时间轴', exact: true }).click();
    assert.equal(await page.getByLabel('时间轴缩放模式', { exact: true }).innerText(), '手动');
    const manualStep = Number(await page.getByLabel('时间轴刻度', { exact: true }).getAttribute('data-tick-step'));
    assert(manualStep > 0 && manualStep < automaticStep);
    await page.getByLabel('时间轴水平位置', { exact: true }).focus(); await page.keyboard.press('End');
    await page.waitForFunction(() => document.querySelector('[data-actual-scroll]').scrollLeft > 0);
    await p.shot('actual-keyboard-pan');
    await page.getByRole('button', { name: '缩小时间轴', exact: true }).click();
    await page.getByRole('button', { name: '定位选中工序', exact: true }).click();
    await page.getByRole('button', { name: '适应全部', exact: true }).click();
    assert.equal(await page.getByLabel('时间轴缩放模式', { exact: true }).innerText(), '自动');
    assert.equal(Number(await page.getByLabel('时间轴刻度', { exact: true }).getAttribute('data-tick-step')), automaticStep);
    p.report.scale_states = { automaticStep, manualStep, restoredStep: automaticStep,
      basis: 'Original prototype presents mode and tick interval as scale status, not independent toggles.' };
    const late = await page.getByLabel('晚期筛选', { exact: true }).locator('option').evaluateAll(nodes => nodes.map(n => n.value));
    assert.equal(late.length, 4);
    for (const value of late) await p.choose('晚期筛选', value);
    await p.choose('晚期筛选', 'all');
  });
  await p.step(['WBP-FG-002', 'WBP-FG-004', 'WBP-FG-013', 'WBP-FG-014'], 'server-date-scope-empty-reset-visible-filter-export', async () => {
    await page.getByLabel('计划完工开始日', { exact: true }).fill('2026-09-08');
    await page.getByLabel('计划完工结束日', { exact: true }).fill('2026-09-08');
    const empty = await p.read(() => page.getByRole('button', { name: '应用范围', exact: true }).click(), '/actual-gantt');
    assert.equal(empty.data.task_count, 0);
    await page.getByText('当前范围没有匹配的工序。', { exact: true }).waitFor();
    assert(await page.getByRole('button', { name: '导出 CSV', exact: true }).isDisabled());
    await p.shot('actual-empty-scope');
    const restored = await p.read(() => page.getByRole('button', { name: '清除来源范围', exact: true }).click(), '/actual-gantt');
    assert.equal(restored.data.plan.plan_ref, ready.expected.final_e.plan_ref); assert.equal(restored.data.task_count, 33);
    const item = restored.data.items.find(row => row.task.task_ref === ref);
    assert.equal(item.execution.known_completed_quantity, 10);
    const report = item.execution.reports[0];
    await page.getByLabel('搜索现场甘特', { exact: true }).fill(report.report_no);
    assert((await page.locator('[data-actual-count]').innerText()).includes('1 / 33'));
    await page.getByRole('button', { name: '导出 CSV', exact: true }).click();
    await p.download(() => page.getByRole('button', { name: '下载 CSV', exact: true }).click(), 'actual-visible-scope');
    await page.getByLabel('搜索现场甘特', { exact: true }).fill('NO-SUCH-ACTUAL');
    await page.getByText('当前范围没有匹配的工序。', { exact: true }).waitFor();
    await page.getByLabel('搜索现场甘特', { exact: true }).fill('');
    p.report.actual_final = restored;
  });
  await p.step(['WBP-FG-002', 'WBP-FIELD-004'], 'return-to-original-field-identity-and-browser-refresh', async () => {
    const current = await p.read(() => page.getByRole('button', { name: '回来源', exact: true }).click(), '/execution/tasks');
    assert(current.data.tasks.some(row => row.task_ref === ref));
    await page.locator('[data-field-task="' + ref + '"]').waitFor();
    const reload = await p.read(() => page.reload(), '/execution/tasks');
    assert(reload.data.tasks.some(row => row.task_ref === ref));
    p.report.after_refresh = reload;
  });
}
module.exports = { actual };
