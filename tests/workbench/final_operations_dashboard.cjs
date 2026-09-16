'use strict';
const { capabilities } = require('./final_operations_capabilities.cjs');

async function lifecycle(h, kind = 'delivery', label = '交期风险') {
  const { page, mark, request, select, shot, detail, assert, report } = h;
  const item = await detail(kind, label), ref = item.item_ref, region = page.locator('[data-detail-ref="' + ref + '"]');
  const modal = () => page.getByRole('dialog');
  const open = () => region.getByRole('button', { name: '登记处置', exact: true }).click();
  const submit = () => request('/dashboard/items/' + ref + '/transition', () => modal().getByRole('button', { name: '提交处置', exact: true }).click(), 200, 'POST');
  const finish = async () => { await request('/dashboard', () => modal().getByRole('button', { name: '完成', exact: true }).click()); await region.waitFor(); };
  await open(); await mark('WBP-DASH-003.cancel', async () => { await page.keyboard.press('Escape'); await modal().waitFor({ state: 'hidden' }); });
  await open();
  await mark('WBP-DASH-003.reject-invalid', async () => { await modal().getByRole('button', { name: '提交处置', exact: true }).click(); await modal().getByRole('alert').waitFor(); });
  await mark('WBP-DASH-003.edit-status', () => select('目标处置状态', '跟进中'));
  for (const [label, value, id] of [['责任人', 'F planner', 'edit-owner'], ['责任期限', '2026-09-11', 'edit-deadline'],
    ['处置行动', 'F verify material and machine arrangement', 'edit-action'], ['原因说明', 'F original facts verified', 'edit-remark']]) {
    await mark('WBP-DASH-003.' + id, () => modal().getByLabel(label, { exact: true }).fill(value));
  }
  await mark('WBP-DASH-003.retain-failed-draft', async () => {
    await modal().getByLabel('原因说明', { exact: true }).fill('');
    await modal().getByRole('button', { name: '提交处置', exact: true }).click(); await modal().getByRole('alert').waitFor();
    assert.equal(await modal().getByLabel('责任人', { exact: true }).inputValue(), 'F planner');
    assert.equal(await modal().getByLabel('责任期限', { exact: true }).inputValue(), '2026-09-11');
    assert.equal(await modal().getByLabel('处置行动', { exact: true }).inputValue(), 'F verify material and machine arrangement');
    await modal().getByLabel('原因说明', { exact: true }).fill('F original facts verified');
  });
  await shot(kind + '-following-form');
  const followed = await mark('WBP-DASH-003.submit', submit); assert.equal(followed.data.handling.status, 'following');
  await finish(); await open(); await select('目标处置状态', '已关闭');
  await mark('WBP-DASH-004.reject-incomplete', async () => { await modal().getByRole('button', { name: '提交处置', exact: true }).click(); await modal().getByRole('alert').waitFor(); });
  for (const [label, value, id] of [['完成时间', '2026-09-10T11:00:17', 'edit-completed-at'],
    ['具体完成结果', 'F production supervisor signed coordination result', 'edit-completion-result'], ['凭据说明', 'F-20260910-acceptance-record', 'edit-evidence-ref']]) {
    await mark('WBP-DASH-004.' + id, () => modal().getByLabel(label, { exact: true }).fill(value));
  }
  const closed = await mark('WBP-DASH-004.close', submit); assert.equal(closed.data.handling.status, 'closed');
  assert.deepEqual(closed.data.risk, followed.data.risk); await finish();
  await mark(['WBP-DASH-004.view-closed', 'WBP-DASH-004.retain-risk-facts'], async () => {
    await region.locator('.dy-tools .dy-badge').filter({ hasText: /^已关闭$/ }).waitFor();
    await region.locator('.dy-tools .dy-badge').filter({ hasText: /^风险仍在$/ }).waitFor();
    assert.equal(item.risk.active, true);
  });
  await shot(kind + '-closed-risk-still-active');
  await mark('WBP-DASH-005.open-reopen', () => region.getByRole('button', { name: '独立重开', exact: true }).click());
  await mark('WBP-DASH-005.require-reason', async () => { await modal().getByRole('button', { name: '确认独立重开', exact: true }).click(); await modal().getByRole('alert').waitFor(); });
  await mark('WBP-DASH-005.cancel-reopen', async () => { await page.keyboard.press('Escape'); await modal().waitFor({ state: 'hidden' }); });
  await region.getByRole('button', { name: '独立重开', exact: true }).click(); await modal().getByLabel('重开原因', { exact: true }).fill('F risk remains, separate reopening request');
  const reopened = await mark('WBP-DASH-005.confirm-reopen', () => request('/dashboard/items/' + ref + '/reopen', () => modal().getByRole('button', { name: '确认独立重开', exact: true }).click(), 200, 'POST'));
  assert.equal(reopened.data.handling.completed_at, null); await finish();
  const history = await mark(['WBP-DASH-006.open-history', 'WBP-DASH-001.tab-records'], () => request('/dashboard/items/' + ref + '/history', () => region.getByRole('button', { name: '查看处置历史', exact: true }).click()));
  assert.equal(history.data.history.items.length, 3); assert.deepEqual(history.data.history.items.map(row => row.sequence), [3, 2, 1]);
  assert.equal(history.data.history.items[0].before.completion_evidence, closed.data.handling.completion_evidence);
  await mark(['WBP-DASH-006.reverse-order', 'WBP-DASH-005.preserve-closed-history'], async () => { await page.locator('[data-history-sequence="3"]').waitFor(); });
  await mark('WBP-DASH-006.expand-before-after', () => page.locator('[data-history-sequence="3"]').getByText('变更前后及完成凭据', { exact: true }).click());
  await mark('WBP-DASH-006.source-records', () => page.getByRole('button', { name: '查看第 3 次原始依据', exact: true }).click());
  await shot(kind + '-reopen-history');
  await page.reload(); await page.locator('[data-history-sequence="3"]').waitFor();
  assert.equal(await page.getByRole('tab', { name: '处置历史', exact: true }).getAttribute('aria-selected'), 'true');
  assert.equal(await page.getByLabel('选择历史条目', { exact: true }).inputValue(), ref);
  await mark('WBP-DASH-006.select-history', () => select('选择历史条目', item.subject + ' · ' + label));
  await detail(kind, label); await region.getByText('跟进中', { exact: true }).first().waitFor();
  report.lifecycles.push({ kind, item_ref: ref, followed, closed, reopened, history, refresh_persisted: true });
}

async function dashboard(h) {
  const { page, mark, request, select, shot, category, detail, assert, report } = h;
  await h.dashboard();
  const caption = page.locator('.wb-current-plan'); await caption.waitFor();
  const plan = report.responses.find(row => row.payload && row.payload.data && row.payload.data.plan).payload.data.plan;
  assert.equal(await caption.getAttribute('data-plan-ref'), plan.plan_ref);
  assert((await caption.innerText()).includes(plan.display_name)); assert((await caption.innerText()).includes('正式 v1'));
  report.dashboard_caption = { reference: plan.plan_ref, text: await caption.innerText() };
  await shot('dashboard-overview');
  for (const [label, suffix] of [['交期风险', 'delivery'], ['执行偏差', 'actual'], ['外协回厂', 'external'], ['停机影响', 'downtime'], ['齐套缺口', 'material'], ['候选方案待确认', 'candidate']]) {
    await mark('WBP-DASH-001.card-' + suffix, () => category(label));
  }
  for (const [label, suffix] of [['交期风险', 'delivery'], ['执行偏差', 'actual'], ['外协回厂', 'external']]) {
    await mark('WBP-DASH-001.metric-' + suffix, () => request('/dashboard', () => page.locator('.dy-metrics').getByRole('button', { name: new RegExp('^' + label) }).click()));
  }
  await category('全部风险');
  for (const [label, suffix] of [['处置清单', 'items'], ['影响分析', 'analysis'], ['方案对比', 'compare'], ['处置历史', 'records']]) {
    await mark('WBP-DASH-001.tab-' + suffix, () => page.getByRole('tab', { name: label, exact: true }).click());
  }
  await mark('WBP-DASH-001.keyboard-tabs', async () => { await page.getByRole('tab', { name: '处置清单', exact: true }).focus(); await page.keyboard.press('ArrowRight'); assert.equal(await page.getByRole('tab', { name: '影响分析', exact: true }).getAttribute('aria-selected'), 'true'); await page.keyboard.press('Home'); });
  for (const [choice, suffix] of [['未关闭', 'open'], ['全部状态', 'all'], ['待分析', 'new'], ['跟进中', 'following'], ['待验证', 'verification'], ['已关闭', 'closed']]) {
    await mark('WBP-DASH-002.status-' + suffix, () => request('/dashboard', () => select('处置状态', choice)));
  }
  await mark('WBP-DASH-002.clear', () => request('/dashboard', () => page.getByRole('button', { name: '清除条目筛选', exact: true }).click()));
  await lifecycle(h);
  for (const [query, suffix] of [['B1', 'batch'], ['F planner', 'owner'], ['F verify', 'action'], ['F risk remains', 'remark']]) {
    await category('全部风险'); await page.getByLabel('搜索条目、责任人、行动或备注', { exact: true }).fill(query);
    const result = await mark('WBP-DASH-002.search-' + suffix, () => request('/dashboard', () => page.getByRole('button', { name: '执行条目搜索', exact: true }).click()));
    assert(result.data.page.total > 0);
    await request('/dashboard', () => page.getByRole('button', { name: '清除条目筛选', exact: true }).click());
  }
  await detail('material', '齐套缺口'); await page.locator('[data-detail-ref]').getByRole('listitem').getByText('F steel', { exact: true }).waitFor(); await shot('material-evidence');
  await detail('downtime', '停机影响');
  await mark('WBP-DASH-011.overlap-table', async () => { await page.locator('[data-detail-ref]').getByRole('listitem').getByText('F maintenance record', { exact: true }).waitFor(); });
  await shot('downtime-evidence');
  await detail('actual', '执行偏差'); await shot('actual-evidence');
  await mark('WBP-DASH-008.actual-comparison-navigation', async () => {
    await page.locator('[data-detail-ref]').getByRole('button', { name: '现场实际甘特', exact: true }).click();
    await page.waitForURL('**view=fieldgantt'); await page.getByRole('button', { name: '回来源', exact: true }).waitFor();
    const state = await page.evaluate(() => history.state.workbench); assert.equal(state.context.return_to.view, 'dashboard');
    await page.getByRole('button', { name: '回来源', exact: true }).click(); await page.locator('[data-detail-ref]').waitFor();
  });
  await capabilities(h);
  await page.locator('[data-run-ref]').first().waitFor(); await shot('candidate-directory');
  await mark('WBP-DASH-014.existing-candidates', async () => { await page.getByRole('button', { name: '查看候选', exact: true }).first().click(); await page.waitForURL('**view=analysis');
    report.navigation.push(await page.evaluate(() => history.state.workbench)); });
}
module.exports = { dashboard, lifecycle };
