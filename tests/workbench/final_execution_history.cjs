'use strict';
const assert = require('node:assert/strict');
const { run } = require('./final_execution_browser_support.cjs');

async function caption(page, plan, label) {
  const node = page.getByRole('status', { name: '当前方案', exact: true });
  if (!plan) { assert.equal(await node.count(), 0); return; }
  await node.waitFor();
  assert.equal(await node.getAttribute('data-plan-ref'), plan.plan_ref);
  const text = await node.innerText();
  assert(text.includes(label) && text.includes(plan.display_name));
  assert(text.includes(plan.is_current_official ? '当前正式采用' : '历史正式方案'));
  assert(text.includes('正式 v' + plan.version));
}

function noWriteFields(context) {
  const forbidden = new Set(['write_token', 'request_key', 'requestKey', 'write_context', 'draft', 'command',
    'completed_quantity', 'actual_start', 'actual_end', 'reason', 'declared_operator', 'receipt']);
  function visit(value) {
    if (!value || typeof value !== 'object') return;
    for (const [key, item] of Object.entries(value)) { assert(!forbidden.has(key), 'Write field persisted: ' + key); visit(item); }
  }
  visit(context);
}

async function roundtrips(p, view, suffix, verify, keys, away = 'reports', awaySuffix = '/analytics') {
  const { page } = p;
  await verify();
  const baseline = await page.evaluate(() => history.state.workbench.context);
  noWriteFields(baseline);
  p.report.baseline = baseline;
  const validate = async () => {
    await verify();
    await page.waitForFunction(({ view, baseline, keys }) => {
      const entry = history.state && history.state.workbench;
      return entry && entry.view === view && keys.every(key => JSON.stringify(entry.context[key]) === JSON.stringify(baseline[key]));
    }, { view, baseline, keys });
    const current = await page.evaluate(() => history.state.workbench.context);
    noWriteFields(current); p.report.restored.push(current);
  };
  const sidebar = target => target === 'review'
    ? page.getByRole('tablist', { name: '统计分析视图', exact: true }).getByRole('tab', { name: '执行复盘', exact: true }).click()
    : page.locator('.sidebar a[href$="?view=' + target + '"]').click();
  const steps = [
    ['F5', async () => { await p.read(() => page.reload(), suffix); }],
    ['sidebar-return', async () => { await p.read(() => sidebar(away), awaySuffix); await p.read(() => sidebar(view), suffix); }],
    ['browser-back', async () => { await p.read(() => sidebar(away), awaySuffix); await p.read(() => page.goBack(), suffix); }],
    ['browser-forward-back', async () => { await p.read(() => page.goForward(), awaySuffix); await p.read(() => page.goBack(), suffix); }]
  ];
  for (const [name, action] of steps) await p.step(['SH003'], view + '-' + name + '-real-readonly-state', async () => {
    await action(); await validate(); await p.shot(view + '-' + name);
  });
  assert(p.report.requests.every(request => request.method === 'GET'), 'Navigation replayed a command');
}

async function field(p) {
  const { page } = p, suffix = '/execution/tasks';
  await p.read(() => page.locator('.sidebar a[href$="?view=field"]').click(), suffix);
  await page.getByRole('searchbox', { name: '搜索批次或工序', exact: true }).fill('B1');
  await p.read(() => page.getByRole('button', { name: '查询现场记录', exact: true }).click(), suffix);
  await p.read(() => p.choose('现场每页数量', '10'), suffix);
  const data = await p.read(() => page.getByRole('button', { name: '现场下一页', exact: true }).click(), suffix);
  assert.equal(data.data.page.number, 2);
  const selected = data.data.tasks[0].task_ref;
  await p.read(() => page.locator('[data-field-task="' + selected + '"] button[aria-expanded]').click(), suffix + '/' + selected);
  const verify = async () => {
    await page.locator('[data-field-task="' + selected + '"] button[aria-expanded=true]').waitFor();
    await page.getByRole('table', { name: '逐次报工记录', exact: true }).waitFor();
    assert.equal(await page.getByRole('searchbox', { name: '搜索批次或工序', exact: true }).inputValue(), 'B1');
    assert.equal(await page.getByLabel('现场每页数量', { exact: true }).inputValue(), '10');
    assert((await page.getByRole('navigation', { name: '现场分页', exact: true }).innerText()).includes('第 2 / 4 页'));
    await caption(page, data.data.plan, '现场计划');
  };
  await roundtrips(p, 'field', suffix, verify, ['scope', 'table', 'task_ref', 'operation_ref', 'snapshot_ref']);
}

async function actual(p) {
  const { page } = p, suffix = '/actual-gantt';
  const data = await p.read(() => page.locator('.sidebar a[href$="?view=fieldgantt"]').click(), suffix);
  await page.locator('[data-actual-scroll]').waitFor();
  await page.getByRole('group', { name: '甘特视图', exact: true }).getByRole('button', { name: '批次', exact: true }).click();
  const first = page.locator('[data-task-row]').first(), ref = await first.getAttribute('data-task-row');
  await first.locator('.fg-task-select').click();
  await page.getByRole('checkbox', { name: '详情', exact: true }).check();
  await page.getByRole('checkbox', { name: '只看选中', exact: true }).check();
  await page.getByRole('button', { name: '放大时间轴', exact: true }).click();
  await page.getByRole('button', { name: '放大时间轴', exact: true }).click();
  await page.getByLabel('时间轴水平位置', { exact: true }).focus(); await page.keyboard.press('End');
  await page.waitForFunction(() => document.querySelector('[data-actual-scroll]').scrollLeft > 100);
  const left = await page.locator('[data-actual-scroll]').evaluate(node => node.scrollLeft);
  p.report.expected_scroll = { left };
  const verify = async () => {
    await page.locator('[data-task-row="' + ref + '"].is-selected').first().waitFor();
    assert(await page.getByRole('checkbox', { name: '详情', exact: true }).isChecked());
    assert(await page.getByRole('checkbox', { name: '只看选中', exact: true }).isChecked());
    await page.waitForFunction(left => Math.abs(document.querySelector('[data-actual-scroll]').scrollLeft - left) < 2, left);
    await caption(page, data.data.plan, '对照计划');
  };
  await roundtrips(p, 'fieldgantt', suffix, verify, ['scope', 'task_ref', 'actual_view']);
}

async function reports(p) {
  const { page } = p, suffix = '/analytics';
  // The shared frame may fit ten rows at 1080px; use the supported baseline height to exercise a real scroll range.
  await page.setViewportSize({ width: 1366, height: 768 }); p.state = '1366-light-' + p.report.phase;
  await p.read(() => page.locator('.sidebar a[href$="?view=reports"]').click(), suffix);
  await page.getByLabel('搜索批次或工序', { exact: true }).fill('B1');
  await p.read(() => page.getByRole('button', { name: '查询范围', exact: true }).click(), suffix);
  await p.read(() => page.getByRole('tab', { name: '报工记录', exact: true }).click(), suffix);
  await p.read(() => p.choose('排序字段', 'effective_processing_hours'), suffix);
  await p.read(() => p.choose('排序方向', 'desc'), suffix);
  await p.read(() => p.choose('每页条数', '10'), suffix);
  const paging = () => page.locator('#report-topic-panel .rw-list-pane > .wb-pager');
  const data = await p.read(() => paging().getByRole('button', { name: '下一页', exact: true }).click(), suffix);
  const row = page.locator('.rw-primary-table tbody tr').first();
  const detailResponse = page.waitForResponse(response => new URL(response.url()).pathname.includes('/analytics/operations/'));
  await row.getByRole('button', { name: /^查看工序/ }).click();
  const detail = await (await detailResponse).json();
  const ref = detail.data.detail.operation.operation_ref;
  p.report.selected_operation = ref;
  await page.locator('.rw-detail[role="region"]').waitFor();
  await page.locator('.er-chart-disclosure > summary').click();
  await p.read(() => page.locator('.rw-catalog > summary').click(), '/reports/overdue');
  const table = page.getByRole('region', { name: '报表结果表格', exact: true });
  await table.focus(); await table.press('End');
  await page.waitForFunction(() => {
    const table = document.querySelector('.rw-primary-table');
    return table.scrollTop > 10 && Math.abs(table.scrollHeight - table.clientHeight - table.scrollTop) < 2;
  });
  const top = await table.evaluate(node => node.scrollTop);
  p.report.expected_scroll = { top };
  const verify = async () => {
    await page.locator('.rw-detail[role="region"]').waitFor();
    assert.equal(await page.getByLabel('搜索批次或工序', { exact: true }).inputValue(), 'B1');
    assert.equal(await page.getByRole('tab', { name: '报工记录', exact: true }).getAttribute('aria-selected'), 'true');
    assert.equal(await page.getByLabel('排序字段', { exact: true }).inputValue(), 'effective_processing_hours');
    assert.equal(await page.getByLabel('排序方向', { exact: true }).inputValue(), 'desc');
    assert((await paging().innerText()).includes('第 2 / 4 页'));
    await page.locator('.er-chart-disclosure[open]').waitFor(); await page.locator('.rw-catalog[open]').waitFor();
    await page.waitForFunction(({ ref, top }) => history.state.workbench.context.selected === ref
      && Math.abs(document.querySelector('.rw-primary-table').scrollTop - top) < 2, { ref, top });
    await caption(page, data.data.plan, '报表计划');
  };
  await roundtrips(p, 'reports', suffix, verify, ['scope', 'topic', 'table', 'selected', 'snapshot_ref', 'chartsOpen', 'catalogOpen'], 'review');
}

async function calibration(p) {
  const { page, ready } = p, suffix = '/calibration', ref = ready.expected.final_e.template_ref;
  await p.read(() => page.locator('.sidebar a[href$="?view=calib"]').click(), suffix);
  await page.getByRole('searchbox', { name: '搜索校准明细', exact: true }).fill('P1');
  await p.read(() => page.getByRole('button', { name: '搜索', exact: true }).click(), suffix);
  await p.read(() => p.choose('排序方向', 'desc'), suffix);
  await p.read(() => p.choose('每页条数', '10'), suffix);
  const detail = await p.read(() => page.locator('.ca-table tr[data-ref="' + ref + '"]').getByRole('button', { name: /^查看 P1/ }).click(), suffix + '/' + ref);
  const sample = detail.data.suggestion.sample_refs[0];
  await page.locator('.ca-sample[data-sample-ref="' + sample + '"] > summary').click();
  const verify = async () => {
    await page.locator('.ca-table tr[data-ref="' + ref + '"][data-selected=true]').waitFor();
    await page.locator('.ca-sample[data-sample-ref="' + sample + '"][open]').waitFor();
    assert.equal(await page.getByRole('searchbox', { name: '搜索校准明细', exact: true }).inputValue(), 'P1');
    assert.equal(await page.getByLabel('排序方向', { exact: true }).inputValue(), 'desc');
    assert.equal(await page.getByLabel('每页条数', { exact: true }).inputValue(), '10');
    await caption(page, null);
  };
  await roundtrips(p, 'calib', suffix, verify, ['scope', 'table', 'selected', 'sample_ref', 'snapshot_ref']);
}

async function exercise(p, view) {
  p.report.restored = [];
  const actions = { field, fieldgantt: actual, reports, calib: calibration };
  assert(actions[view], 'Unknown read-only history domain');
  await actions[view](p);
}
run('history', exercise, { once: true });
