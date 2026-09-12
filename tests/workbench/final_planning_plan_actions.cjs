'use strict';
const assert = require('node:assert/strict');
const { processOrderActions } = require('./final_planning_process_order.cjs');

async function planActions(page, report, h, flush) {
  const { action, button, shot, last } = h;
  await action(['WBP-PLAN-002.identity', 'WBP-GANTT-002.click', 'WBP-GANTT-003.details', 'WBP-GANTT-003.quantities'], async () => {
    await h.formalDetails(); await h.pixels('[data-plan-workspace] .plan-main', 'official');
    report.first_official = last(data => data.plan && data.tasks);
    const points = report.first_official.tasks.filter(task => task.start === task.end);
    assert.equal(points.length, 4);
    assert(points.every(task => task.event_kind === 'point' && task.occupies_resources === false));
    const selected = page.locator('[data-plan-task][aria-pressed="true"]:not([data-before])');
    assert.equal(await selected.count(), 1); const ref = await selected.getAttribute('data-plan-task');
    await page.reload(); await page.locator('[data-plan-workspace] .plan-main').waitFor(); await flush();
    assert.equal(await page.locator('[data-plan-task="' + ref + '"]:not([data-before])').getAttribute('aria-pressed'), 'true');
    report.formal_selected_recovery = { plan_ref: report.first_official.plan.plan_ref, task_ref: ref, method: 'mouse', actual_reload: true };
  });
  await action(['WBP-GANTT-002.keyboard', 'WBP-GANTT-002.hover', 'WBP-PLAN-002.baseline', 'WBP-PLAN-002.comparison'], async () => {
    const original = report.first_official;
    const task = original.tasks.find(row => row.batch_id === 'B1' && row.sequence === 10);
    const target = page.locator('[data-plan-task="' + task.task_ref + '"]:not([data-before])');
    await target.press('Enter'); assert.equal(await target.getAttribute('aria-pressed'), 'true');
    await page.reload(); await page.locator('[data-plan-workspace] .plan-main').waitFor(); await flush();
    assert.equal(await target.getAttribute('aria-pressed'), 'true');
    report.formal_keyboard_recovery = { plan_ref: original.plan.plan_ref, task_ref: task.task_ref, method: 'keyboard', actual_reload: true };
    await target.scrollIntoViewIfNeeded(); await flush();
    await page.mouse.move(5, 5);
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await target.hover(); await page.getByRole('tooltip').waitFor();
    assert((await page.getByRole('tooltip').innerText()).includes('共同工序'));
    await shot('formal-keyboard-hover');
    await page.mouse.move(5, 5);
    const inspector = page.locator('[data-plan-inspector]');
    const baseline = original.projections.baseline;
    assert.equal(baseline.state, 'available');
    const pair = baseline.items.find(row => row.operation_ref === task.operation_ref);
    assert(pair.before && pair.after);
    await button('查看初始安排', inspector).click();
    assert((await inspector.innerText()).includes('初始计划安排'));
    assert((await inspector.innerText()).includes(pair.before.start.replace('T', ' ')));
    await button('查看当前安排', inspector).click();
    assert((await inspector.innerText()).includes('当前所选计划安排'));
    await shot('formal-original-baseline-comparison');
  });
  await action(['WBP-GANTT-001.only-changed', 'WBP-GANTT-001.expand', 'WBP-GANTT-001.collapse'], async () => {
    const gantt = page.locator('[data-plan-gantt]'), changed = gantt.getByRole('checkbox', { name: '仅变更', exact: true });
    const baseline = report.first_official.projections.baseline;
    const operations = new Set(baseline.items.filter(row => row.change !== 'unchanged').map(row => row.operation_ref));
    const expected = report.first_official.tasks.filter(task => operations.has(task.operation_ref));
    await changed.check(); await flush();
    assert.equal(await gantt.locator('[data-plan-search-count]').innerText(), expected.length + ' / ' + report.first_official.task_count + ' 道安排');
    const visible = await gantt.locator('[data-plan-task]:not([data-before])').evaluateAll(nodes => nodes.map(node => node.dataset.planTask));
    assert(visible.every(ref => expected.some(task => task.task_ref === ref)));
    await shot('formal-only-changed'); await changed.uncheck();
    const original = await gantt.boundingBox();
    const zoom = await gantt.locator('.plan-actions .plan-muted').innerText();
    await button('展开甘特', gantt).click(); await page.locator('.plan-gantt.plan-expanded').waitFor();
    const expanded = await gantt.boundingBox(), viewport = page.viewportSize();
    assert(expanded.width > original.width && expanded.height > original.height);
    assert(expanded.x >= 0 && expanded.y >= 0 && expanded.x + expanded.width <= viewport.width && expanded.y + expanded.height <= viewport.height);
    assert.equal(await gantt.locator('.plan-actions .plan-muted').innerText(), zoom, 'Expanding must not change timeline zoom');
    await shot('formal-expanded'); await button('收起甘特', gantt).click();
    assert.equal(await page.locator('.plan-gantt.plan-expanded').count(), 0);
    await button('展开甘特', gantt).click(); await page.keyboard.press('Escape');
    assert.equal(await page.locator('.plan-gantt.plan-expanded').count(), 0);
    assert.equal(await gantt.locator('.plan-actions .plan-muted').innerText(), zoom);
  });
  await action(['WBP-GANTT-001.machine', 'WBP-GANTT-001.operator', 'WBP-GANTT-001.batch',
    'WBP-GANTT-001.baseline', 'WBP-GANTT-001.search', 'WBP-GANTT-004.missing'], async () => {
    const group = page.getByRole('group', { name: '甘特分组', exact: true });
    for (const mode of ['人员', '批次', '设备']) { await button(mode, group).click(); assert.equal(await button(mode, group).getAttribute('aria-pressed'), 'true'); }
    await page.getByRole('checkbox', { name: '显示初始基线', exact: true }).check();
    await shot('formal-baseline');
    await page.getByRole('checkbox', { name: '显示初始基线', exact: true }).uncheck();
    const search = page.getByRole('searchbox', { name: '搜索批次、工序、设备、人员', exact: true });
    await search.fill('D-does-not-exist');
    await page.getByText('没有匹配安排，完整计划跨度保持不变。', { exact: true }).waitFor();
    await search.fill('');
    report.formal_search_keystrokes = [];
    let value = '';
    for (const character of 'item-B') {
      await search.type(character); value += character; await flush();
      assert.equal(await search.inputValue(), value, 'Each real keystroke must survive reconciliation');
      const refs = await page.locator('[data-plan-task]:not([data-before])').evaluateAll(nodes => nodes.map(node => node.dataset.planTask));
      assert.equal(new Set(refs).size, refs.length, 'Reconciliation must not duplicate task nodes');
      assert.equal(await page.locator('[data-plan-gantt]').count(), 1);
      report.formal_search_keystrokes.push({ value, visible_task_refs: refs });
    }
    await search.press('Enter');
    assert((await page.locator('[data-plan-inspector]').innerText()).includes('item-B'));
    await page.reload(); await page.locator('[data-plan-workspace] .plan-main').waitFor(); await flush();
    assert.equal(await search.inputValue(), 'item-B');
    report.formal_search_recovery = { plan_ref: report.first_official.plan.plan_ref, query: 'item-B', actual_reload: true };
    await search.press('Escape');
  });
  await action(['WBP-DELAY-001.metrics', 'WBP-DELAY-002.select-batch', 'WBP-GANTT-003.resources',
    'WBP-GANTT-004.batch-focus'], async () => {
    await button('B1', page.getByRole('table', { name: '交付风险列表', exact: true })).click();
    assert((await page.locator('[data-plan-inspector]').innerText()).includes('B1'));
    await page.getByRole('searchbox', { name: '搜索批次、工序、设备、人员', exact: true }).fill('');
    const group = page.getByRole('group', { name: '计划分析视图', exact: true });
    await button('资源负荷', group).click();
    await page.getByRole('table', { name: '资源负荷列表', exact: true }).waitFor(); await shot('resource-load');
    await button('资源日历', group).click();
    await page.getByRole('table', { name: '资源日历列表', exact: true }).waitFor(); await shot('resource-calendar');
    await button('交付风险', group).click();
  });
  await action(['WBP-PLAN-005.gantt-navigation', 'WBP-PLAN-004.reload'], async () => {
    const views = page.getByRole('tablist', { name: '计划中心视图', exact: true });
    await views.getByRole('tab', { name: '交付风险', exact: true }).click();
    await views.getByRole('tab', { name: '交付风险', exact: true, selected: true }).waitFor();
    await page.getByRole('table', { name: '交付风险列表', exact: true }).waitFor();
    await flush(); await h.caption(report.first_official.plan.plan_ref, '当前正式');
    await shot('formal-delay');
    await views.getByRole('tab', { name: '选择排产方案', exact: true }).click();
    await views.getByRole('tab', { name: '选择排产方案', exact: true, selected: true }).waitFor();
    await page.locator('[data-plan-workspace] .plan-main').waitFor();
    await views.getByRole('tab', { name: '设备 / 人员 / 批次甘特', exact: true }).click();
    await views.getByRole('tab', { name: '设备 / 人员 / 批次甘特', exact: true, selected: true }).waitFor();
    await page.locator('[data-plan-workspace] .plan-main').waitFor();
    await flush(); assert.equal(last(data => data.plan && data.tasks).plan.plan_ref, report.first_official.plan.plan_ref);
    await page.reload(); await page.locator('[data-plan-workspace] .plan-main').waitFor();
    await flush(); assert.deepEqual(last(data => data.plan && data.tasks).tasks, report.first_official.tasks);
    await h.caption(report.first_official.plan.plan_ref, '当前正式');
    await shot('gantt-reload');
  });
  await processOrderActions(page, report, h, flush);
}
module.exports = { planActions };
