'use strict';
async function capabilities(h) {
  const { page, mark, request, select, shot, assert, report } = h;
  const ready = () => page.locator('[data-dashboard-workspace][data-analysis-ready=true]').waitFor();
  await mark('WBP-DASH-001.metric-pressure', () => request('/dashboard', () => page.locator('.dy-metrics').getByRole('button', { name: /^资源压力/ }).click()));
  await ready(); const axis = page.locator('[data-dashboard-timeline=delivery]'); await axis.waitFor();
  const bar = axis.locator('[data-analysis-task]').first(), batchRef = await bar.getAttribute('data-analysis-batch');
  await mark('WBP-DASH-007.hover-resource', async () => { await bar.hover(); await page.getByRole('tooltip').waitFor(); assert((await page.getByRole('tooltip').innerText()).includes('计划跨度')); });
  await mark(['WBP-DASH-007.select-batch', 'WBP-DASH-007.affected-batches'], async () => {
    await bar.click(); await page.locator('[data-analysis-delivery="' + batchRef + '"][data-selected=true]').waitFor();
    assert.equal(await bar.getAttribute('aria-pressed'), 'true');
  });
  await shot('resource-timeline-and-batch-link');
  await mark('WBP-DASH-007.compare-navigation', async () => { await page.getByRole('button', { name: '对比调整方案', exact: true }).click(); assert.equal(await page.getByRole('tab', { name: '方案对比', exact: true }).getAttribute('aria-selected'), 'true'); });
  await mark('WBP-DASH-001.category-select', () => request('/dashboard', () => select('异常类别', '停机影响')));
  await page.getByRole('tab', { name: '影响分析', exact: true }).click(); await ready();
  const maintenance = page.locator('[data-dashboard-timeline=downtime]'); await maintenance.waitFor();
  await mark('WBP-DASH-011.downtime-bar', async () => { await maintenance.locator('[data-downtime-ref]').first().focus(); await page.getByRole('tooltip').waitFor(); assert((await page.getByRole('tooltip').innerText()).includes('F maintenance record')); });
  await mark('WBP-DASH-011.plan-task-bar', async () => { const task = maintenance.locator('[data-analysis-task]').first(); await task.click(); assert.equal(await task.getAttribute('aria-pressed'), 'true'); await page.locator('[data-overlap-task][data-selected=true]').first().waitFor(); });
  await mark('WBP-DASH-011.reason-recorded-at', async () => { const evidence = page.getByRole('region', { name: '停机登记依据', exact: true }); assert((await evidence.innerText()).includes('登记时间（原存值）')); await evidence.getByText('F maintenance record', { exact: true }).waitFor(); });
  await shot('maintenance-and-original-plan-bars');
  await mark('WBP-DASH-001.metric-pending', () => request('/dashboard', () => page.locator('.dy-metrics').getByRole('button', { name: /^待排批次/ }).click()));
  await ready(); const pending = page.getByRole('region', { name: '待排批次与齐套日期', exact: true });
  await mark(['batch', 'quantity', 'due-date', 'ready-status', 'ready-date', 'constraints'].map(s => 'WBP-DASH-012.' + s), async () => {
    const row = pending.locator('tbody tr').filter({ has: page.getByText('B1', { exact: true }) }), cells = row.locator('td');
    assert.equal(await cells.nth(1).innerText(), '2'); assert.equal(await cells.nth(2).innerText(), '2026-09-08');
    assert.equal(await cells.nth(3).innerText(), '未齐套'); assert.equal(await cells.nth(4).innerText(), '未知');
    await pending.getByText('当前未选定', { exact: true }).waitFor();
  });
  await shot('pending-batches-and-readiness');
  await h.category('执行偏差'); await page.getByRole('tab', { name: '影响分析', exact: true }).click(); await ready();
  await mark('WBP-DASH-008.deviation-table', async () => { await page.getByRole('region', { name: '工序执行偏差', exact: true }).waitFor(); });
  await mark('WBP-DASH-008.field-report-navigation', async () => {
    await page.getByRole('region', { name: '工序执行偏差', exact: true }).getByRole('button', { name: '现场报工', exact: true }).first().click();
    await page.waitForURL('**view=field'); await page.getByRole('button', { name: '返回', exact: true }).click(); await ready();
  });
  await page.getByRole('tab', { name: '方案对比', exact: true }).click();
  await mark('WBP-DASH-014.no-independent-candidate', async () => { await page.getByRole('region', { name: '本问题候选状态', exact: true }).waitFor(); assert.equal(await page.locator('[data-dashboard-candidates]').count(), 0); });
  await page.getByRole('button', { name: '查看现有候选方案', exact: true }).click();
  await page.locator('[data-dashboard-candidates]').waitFor();
  const picker = page.getByLabel('选择排产运行', { exact: true }), option = picker.locator('option').nth(1);
  const runRef = await option.getAttribute('value'), label = await option.innerText();
  const catalog = await request('/scheduling/runs/' + runRef + '/candidates', () => select('选择排产运行', label));
  assert(catalog.data.candidates.length >= 3);
  const comparisons = [];
  for (const candidate of catalog.data.candidates.slice(0, 3)) {
    const ref = candidate.candidate_ref;
    const value = await mark('WBP-DASH-013.candidate-radio', () => request('/dashboard/candidates/' + ref + '/comparison', () => page.locator('input[name="dashboard-candidate"][value="' + ref + '"]').check()));
    await page.locator('[data-comparison-ready=true]').waitFor();
    assert.equal(value.data.candidate.candidate_ref, ref); assert.equal(value.data.candidate.run_ref, runRef);
    await page.locator('.wb-current-plan[data-plan-ref="' + ref + '"]').waitFor();
    assert(value.data.baseline.available);
    comparisons.push(value);
  }
  const current = comparisons[comparisons.length - 1].data, selected = current.candidate.candidate_ref;
  const number = value => value === null ? '未知' : value.toLocaleString('zh-CN', { maximumFractionDigits: 3 });
  await mark('WBP-DASH-013.benefits-costs', async () => {
    const rows = page.getByRole('region', { name: '整体收益与代价', exact: true }).locator('tbody tr');
    assert.equal(await rows.count(), 3 + current.resources.length);
    assert.equal(await rows.first().locator('td').nth(1).innerText(), number(current.summary.before.overdue_count));
    assert.equal(await rows.first().locator('td').nth(2).innerText(), number(current.summary.after.overdue_count));
  });
  await mark('WBP-DASH-013.per-batch-change', async () => {
    assert.equal(await page.locator('[data-comparison-batch]').count(), current.batches.length);
    for (const item of current.batches) {
      const row = page.locator('[data-comparison-batch="' + item.batch_ref + '"]');
      const expected = item.delay_delta_hours === null ? '未知' : item.delay_delta_hours > 0 ? '+' + number(item.delay_delta_hours) : number(item.delay_delta_hours);
      assert.equal(await row.locator('td').last().innerText(), expected);
      await row.getByRole('button').click(); assert.equal(await row.getAttribute('data-selected'), 'true');
    }
  });
  await shot('three-real-candidates-and-comparison');
  await mark('WBP-DASH-013.summary-dialog', async () => {
    await page.getByRole('button', { name: '查看方案摘要', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: '候选方案摘要', exact: true }); await dialog.getByText(selected, { exact: true }).waitFor();
    await shot('candidate-summary-dialog'); await page.keyboard.press('Escape'); await dialog.waitFor({ state: 'hidden' });
  });
  await page.reload(); await page.locator('[data-comparison-ready=true]').waitFor();
  assert.equal(await page.locator('input[name="dashboard-candidate"][value="' + selected + '"]').isChecked(), true);
  assert.equal(await page.getByRole('dialog').count(), 0);
  assert.equal(await page.locator('.wb-current-plan').getAttribute('data-plan-ref'), selected);
  const restored = await page.evaluate(() => history.state.workbench.context);
  assert.equal(restored.comparison.candidate_ref, selected);
  assert(!/write_token|request_key|confirmation/.test(JSON.stringify(restored)));
  report.capability_comparisons = comparisons; report.candidate_read_context = restored;
}
module.exports = { capabilities };
