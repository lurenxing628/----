'use strict';
const assert = require('node:assert/strict');
const { run } = require('./final_execution_browser_support.cjs');

function permanent(value) {
  return { ...value.data, rows: value.data.rows.map(row => {
    if (!Object.prototype.hasOwnProperty.call(row, 'elapsed_since_planned_minutes')) return row;
    const elapsed = row.due && !row.complete ? Math.round((Date.parse(value.meta.as_of + 'Z') - Date.parse(row.planned_end + 'Z')) / 600) / 100 : null;
    assert.equal(row.elapsed_since_planned_minutes, elapsed);
    const { elapsed_since_planned_minutes, ...facts } = row;
    return facts;
  }) };
}
function returnedView(p, returned, original) {
  assert.deepEqual(permanent(returned), permanent(original));
  const request = p.report.responses[p.report.responses.length - 1];
  assert.equal(new URL(request.url).searchParams.has('snapshot_ref'), false, 'Returning starts a new read with the permanent view');
  assert.equal(returned.meta.source, 'production'); assert(returned.meta.snapshot_ref);
}

async function exercise(p) {
  const { page } = p, suffix = '/analytics', work = page.locator('.rw-workbench');
  await p.read(() => page.locator('.sidebar a[href$="?view=reports"]').click(), suffix);
  let result = await p.read(() => work.getByRole('tablist', { name: '统计分析视图', exact: true }).getByRole('tab', { name: '执行复盘', exact: true }).click(), suffix);
  await p.step(['WBP-REVIEW-001.A001', 'WBP-REVIEW-002'], 'real-review-refresh-and-metric-denominators', async () => {
    result = await p.read(() => work.getByRole('button', { name: '刷新报表', exact: true }).click(), suffix);
    const summary = result.data.summary;
    assert.equal(summary.due, 66); assert.equal(summary.confirmed_due, 15); assert.equal(summary.due_on_time, 15);
    assert.equal(summary.completion_rate, 15 / 66); assert.equal(summary.late_open, 51);
    assert.equal(summary.effective_processing_hours, null); assert.equal(summary.known_effective_processing_hours, 7.5);
    assert.equal(summary.unknown_hour_events, 7); await p.shot('review-original-metrics');
  });
  await p.step(['WBP-SCOPE-002', 'WBP-SCOPE-003'], 'all-resource-types-unassigned-objects-all-seven-focuses-and-individual-chips', async () => {
    await work.getByRole('button', { name: '更多筛选', exact: true }).click();
    for (const type of ['machine', 'operator']) {
      await p.choose('资源类型', type); await p.choose('关联资源', 'unassigned');
      result = await p.read(() => work.getByRole('button', { name: '查询范围', exact: true }).click(), suffix);
      assert.equal(result.data.scope.resource_type, type); assert.equal(result.data.scope.resource_ref, 'unassigned');
      await p.read(() => work.getByRole('button', { name: '清除关联资源', exact: true }).click(), suffix);
      assert.equal(await work.getByLabel('关联资源', { exact: true }).inputValue(), '');
      await p.read(() => work.getByRole('button', { name: '清除资源类型', exact: true }).click(), suffix);
    }
    const options = await work.getByLabel('分析范围', { exact: true }).locator('option').evaluateAll(nodes => nodes.map(node => node.value));
    assert.equal(options.length, 7);
    for (const value of options.filter(value => value !== 'all')) {
      await p.choose('分析范围', value);
      result = await p.read(() => work.getByRole('button', { name: '查询范围', exact: true }).click(), suffix);
      assert.equal(result.data.scope.focus, value);
      if (value === 'unreported') assert.equal(result.data.page.total, 48);
      if (value === 'complete') assert.equal(result.data.page.total, 15);
      if (value === 'finish_late') assert.equal(result.data.page.total, 0);
      await p.shot('review-focus-' + value);
      await p.read(() => work.getByRole('button', { name: '清除分析范围', exact: true }).click(), suffix);
    }
    await work.getByRole('button', { name: '更多筛选', exact: true }).click();
  });
  await p.step(['WBP-REVIEW-003', 'WBP-REVIEW-004', 'WBP-REVIEW-005'], 'review-all-sorts-page-controls-and-complete-csv', async () => {
    const sorts = await work.getByLabel('排序列', { exact: true }).locator('option').evaluateAll(nodes => nodes.map(node => node.value));
    for (const sort of sorts) {
      if (sort !== await work.getByLabel('排序列', { exact: true }).inputValue())
        await p.read(() => p.choose('排序列', sort), suffix);
      await p.read(() => p.choose('排序方向', 'desc'), suffix);
      await p.read(() => p.choose('排序方向', 'asc'), suffix);
    }
    await p.read(() => p.choose('每页条数', '10'), suffix);
    result = await p.read(() => work.locator('#report-topic-panel .rw-list-pane > .wb-pager').getByRole('button', { name: '下一页', exact: true }).click(), suffix);
    assert.equal(result.data.page.number, 2);
    result = await p.read(() => work.locator('#report-topic-panel .rw-list-pane > .wb-pager').getByRole('button', { name: '上一页', exact: true }).click(), suffix);
    assert.equal(result.data.page.number, 1);
    result = await p.read(() => p.choose('每页条数', '50'), suffix);
    const first = result;
    result = await p.read(() => work.locator('#report-topic-panel .rw-list-pane > .wb-pager').getByRole('button', { name: '下一页', exact: true }).click(), suffix);
    assert.equal(result.data.rows.length, 16); p.report.export_source = [first, result];
    await p.download(() => work.getByRole('button', { name: '导出范围', exact: true }).click(), 'review-complete-csv');
    await work.getByText('已导出当前筛选全部 66 项，文件已交给浏览器下载。', { exact: true }).waitFor();
    result = await p.read(() => p.choose('每页条数', '20'), suffix);
  });
  await p.step(['WBP-SCOPE-006', 'WBP-REVIEW-006', 'WBP-REVIEW-007', 'WBP-REVIEW-008', 'WBP-REVIEW-009'], 'real-trend-title-table-distribution-and-current-drill-affordances', async () => {
    await work.locator('.er-chart-disclosure > summary').click();
    const circles = work.locator('.aw-series circle'); assert.equal(await circles.count(), 2);
    await circles.first().hover(); assert((await circles.first().locator('title').textContent()).includes('66 道'));
    await work.locator('.aw-data > summary').click();
    const chartRows = await work.locator('.aw-data tbody tr').allTextContents();
    assert(chartRows[0].includes('66') && chartRows[0].includes('15'));
    const facts = await work.locator('.er-insights').innerText(); assert(facts.includes('51'));
    const original = result;
    p.report.fact_drills = [];
    for (const [name, focus, total] of [['晚完成明细', 'finish_late', 0], ['未确认明细', 'unclosed', 51], ['工序明细', 'all', 66]]) {
      const opened = await p.read(() => work.locator('.er-insights').getByRole('button', { name, exact: true }).click(), suffix);
      assert.deepEqual(opened.data.scope, { ...original.data.scope, focus });
      assert.equal(opened.data.topic, 'delivery'); assert.equal(opened.data.page.total, total);
      await p.shot('fact-drill-' + focus);
      const returned = await p.read(() => work.locator('.rw-header').getByRole('button', { name: '返回来源', exact: true }).click(), suffix);
      returnedView(p, returned, original);
      await work.locator('.er-insights').waitFor();
      p.report.fact_drills.push({ name, opened, returned });
    }
    p.report.resource_drills = [];
    for (const [kind, label, collection] of [['machine', '设备', 'machines'], ['operator', '人员', 'people']]) {
      await work.getByRole('tablist', { name: '资源工时类型', exact: true }).getByRole('tab', { name: label, exact: true }).click();
      const section = work.getByRole('region', { name: '实际资源工时', exact: true });
      assert.equal(await section.locator('.er-resource-row').count(), 2);
      assert(await section.getByRole('button', { name: '资源工时下一页', exact: true }).isDisabled());
      for (const resource of original.data.resources[collection]) {
        const resourceRef = resource.resource_ref || 'unassigned', row = section.locator('[data-resource-ref="' + resourceRef + '"]');
        assert((await row.innerText()).includes('总工时未知'));
        const button = resource.resource_ref ? row.getByRole('button', { name: '查看 ' + resource.resource_label + ' 关联记录', exact: true })
          : row.getByRole('button', { name: resource.resource_label, exact: true });
        const opened = await p.read(() => button.click(), suffix);
        assert.deepEqual(opened.data.scope, { ...original.data.scope, resource_type: kind, resource_ref: resourceRef });
        assert.equal(opened.data.topic, 'records'); assert.equal(opened.data.page.total, resource.resource_ref ? 33 : 1);
        if (!resource.resource_ref) assert.equal(opened.data.rows[0][kind + '_ref'], null);
        else assert.equal(opened.data.summary.records, 33, 'Planned resource association retains every record of those operations, including unknown actual resources.');
        await p.shot('resource-drill-' + kind + '-' + resourceRef);
        const returned = await p.read(() => work.locator('.rw-header').getByRole('button', { name: '返回来源', exact: true }).click(), suffix);
        returnedView(p, returned, original);
        await section.waitFor(); assert.equal(await work.getByRole('tablist', { name: '资源工时类型', exact: true }).getByRole('tab', { selected: true }).innerText(), label);
        p.report.resource_drills.push({ kind, resourceRef, opened, returned });
      }
    }
    p.report.resource_pagination_case = 'test_full_main_resource_tabs_six_group_pages_drill_and_restart uses nine real groups; this two-group case does not claim pagination coverage.';
    await work.locator('#report-topic-panel > .rw-limitations > summary').click();
    await p.shot('all-review-evidence');
  });
  await p.step(['WBP-REPORT-001.A002', 'WBP-REPORT-010'], 'report-keyboard-topics-and-original-task-report-navigation-return', async () => {
    await p.read(() => work.getByRole('tablist', { name: '统计分析视图', exact: true }).getByRole('tab', { name: '报表中心', exact: true }).click(), suffix);
    let active = work.getByRole('tablist', { name: '报表专题', exact: true }).getByRole('tab', { selected: true });
    for (const [key, topic] of [['End', 'quality'], ['Home', 'delivery'], ['ArrowLeft', 'quality'], ['ArrowRight', 'delivery']]) {
      result = await p.read(() => active.press(key), suffix); assert.equal(result.data.topic, topic);
      active = work.getByRole('tablist', { name: '报表专题', exact: true }).getByRole('tab', { selected: true }); assert(await active.evaluate(node => document.activeElement === node));
    }
    await work.getByRole('searchbox', { name: '搜索批次或工序', exact: true }).fill('OP1');
    result = await p.read(() => work.getByRole('button', { name: '查询范围', exact: true }).click(), suffix);
    assert.equal(result.data.page.total, 1);
    result = await p.read(() => p.choose('每页条数', '10'), suffix);
    const original = result, operation = result.data.rows[0];
    const opened = await p.read(() => work.locator('.rw-primary-table tbody tr').first().getByRole('button', { name: /^查看工序/ }).click(), '/analytics/operations/' + operation.operation_ref);
    const detail = work.locator('.rw-detail'); await detail.waitFor();
    const field = await p.read(() => detail.getByRole('button', { name: '查看现场记录', exact: true }).click(), '/execution/tasks');
    assert.equal(field.data.plan.plan_ref, original.data.plan.plan_ref);
    const fieldTask = field.data.tasks.find(task => task.task_ref === operation.task_ref);
    assert.equal(fieldTask.operation_ref, operation.operation_ref);
    await page.locator('[data-field-task="' + operation.task_ref + '"].field-selected').waitFor();
    const fieldTitle = fieldTask.batch_id + ' · ' + fieldTask.operation_label + ' · ' + (fieldTask.piece_id === null ? '共同工序' : '分件 ' + fieldTask.piece_id);
    await page.locator('.field-detail').getByRole('heading', { name: fieldTitle, exact: true }).waitFor();
    await p.shot('report-original-field-task');
    const returned = await p.read(() => page.locator('.field-toolbar').getByRole('button', { name: '返回', exact: true }).click(), suffix);
    returnedView(p, returned, original);
    await detail.getByText('整道完成', { exact: true }).waitFor();
    await detail.getByRole('button', { name: '下一页', exact: true }).click();
    const report = opened.data.detail.records[10]; assert.equal(report.record_kind, 'production_report');
    const actual = await p.read(() => detail.getByRole('button', { name: '定位实际甘特 ' + report.report_no, exact: true }).click(), '/actual-gantt');
    assert.equal(actual.data.plan.plan_ref, original.data.plan.plan_ref);
    const task = actual.data.items.find(item => item.task.task_ref === operation.task_ref);
    assert.equal(task.task.operation_ref, operation.operation_ref); assert(task.execution.reports.some(row => row.report_ref === report.report_ref));
    await page.getByLabel('工序详情', { exact: true }).waitFor();
    assert.equal(await page.getByLabel('选择报工详情', { exact: true }).inputValue(), report.report_ref);
    await page.locator('[data-task-row="' + operation.task_ref + '"].is-selected').first().waitFor();
    await p.shot('report-exact-record-actual-gantt');
    const restored = await p.read(() => page.getByRole('button', { name: '回来源', exact: true }).click(), suffix);
    returnedView(p, restored, original);
    await detail.getByText('整道完成', { exact: true }).waitFor();
    assert((await detail.locator('.wb-detail-body > .wb-pager').innerText()).includes('第 2 / 2 页'));
    assert.equal(await work.getByRole('searchbox', { name: '搜索批次或工序', exact: true }).inputValue(), 'OP1');
    p.report.operation_navigation = { original, field, actual, restored, task_ref: operation.task_ref, report_ref: report.report_ref };
    await p.shot('report-original-detail-page-restored');
    await detail.getByRole('button', { name: /^关闭/ }).click();
  });
}
run('analytics', exercise, { once: true });
