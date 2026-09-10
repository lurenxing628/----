'use strict';
const assert = require('node:assert/strict');

async function pickerActions(page, ready, report, h, flush) {
  const { button, action, last, shot } = h;
  await action(['WBP-RUN-001.close-picker', 'WBP-RUN-002.paging'], async () => {
    await button('收起范围').click();
    assert.equal(await page.locator('.pf-picker').count(), 0);
    await button('选择批次').click(); await flush();
    await page.getByText('共 ' + ready.expected.picker_batch_count + ' 批 · 第 1 / 2 页', { exact: true }).waitFor();
    await button('批次下一页').click();
    await page.getByText('共 23 批 · 第 2 / 2 页', { exact: true }).waitFor();
    await page.getByRole('checkbox', { name: '选择 Z-D-21', exact: true }).waitFor();
    await button('批次上一页').click(); await flush();
    assert(await page.getByRole('checkbox', { name: '选择 B1', exact: true }).isChecked());
    await page.getByLabel('批次每页条数', { exact: true }).selectOption('50');
    await page.getByText('共 23 批 · 第 1 / 1 页', { exact: true }).waitFor();
    assert.equal(await page.locator('.pf-picker-list input[type=checkbox]').count(), 23);
    await page.getByLabel('批次每页条数', { exact: true }).selectOption('20'); await flush();
  });
  await action(['WBP-RUN-001.search', 'WBP-RUN-001.range-selection', 'WBP-RUN-002.filtered', 'WBP-RUN-002.ready-filter'], async () => {
    const picker = page.locator('.pf-picker'), query = page.getByLabel('搜索排产批次', { exact: true });
    await query.fill('D-no-such-batch'); await button('搜索', picker).click();
    await page.getByText('当前筛选没有待排批次。', { exact: true }).waitFor();
    await query.fill('Z-D-'); await button('搜索', picker).click(); await flush();
    await button('全选当前筛选').click(); await flush();
    await page.getByText('已选 21 批 · 含非当前页 1 批', { exact: true }).waitFor();
    assert.equal(last((_data, row) => row.url.endsWith('/entities/batch/selection')).count, 21);
    await button('批次下一页').click(); await flush();
    assert(await page.getByRole('checkbox', { name: '选择 Z-D-21', exact: true }).isChecked());
    await page.getByLabel('批次齐套筛选', { exact: true }).selectOption('partial'); await flush();
    assert.equal(await page.locator('.pf-picker-list input[type=checkbox]').count(), 7);
    await page.getByLabel('批次齐套筛选', { exact: true }).selectOption('no'); await flush();
    assert.equal(await page.locator('.pf-picker-list input[type=checkbox]').count(), 14);
    await page.getByLabel('批次齐套筛选', { exact: true }).selectOption('yes');
    await page.getByText('当前筛选没有待排批次。', { exact: true }).waitFor();
    await query.fill(''); await button('搜索', picker).click(); await flush();
    assert.equal(await page.locator('.pf-picker-list input[type=checkbox]').count(), 2);
    await button('仅已齐套').click(); await flush();
    await page.locator('input[aria-label="选择 B1"]:checked').waitFor();
    await page.locator('input[aria-label="选择 B2"]:checked').waitFor();
    await page.getByLabel('批次齐套筛选', { exact: true }).selectOption(''); await flush();
    await shot('batch-picker-filter-pages');
  });
}

async function preflightReturn(page, report, h, flush) {
  const { action, button, last, shot } = h;
  await action(['WBP-RUN-001.date-guard'], async () => {
    const before = report.requests.filter(row => row.method === 'POST').length;
    await page.getByLabel('计划开始日期', { exact: true }).fill('2026-10-01');
    await page.getByLabel('计划结束日期', { exact: true }).fill('2026-09-25');
    await button('开始排产检查').click();
    await page.getByRole('alert').getByText('请核对精确批次范围、日期窗口和本次排产规则。', { exact: true }).waitFor();
    await flush(); assert.equal(report.requests.filter(row => row.method === 'POST').length, before);
  });
  await action(['WBP-RUN-004.reasons', 'WBP-RUN-005.batch-link'], async () => {
    await button('清空选择').click();
    await page.getByRole('checkbox', { name: '选择 Z-D-01', exact: true }).check();
    await page.getByLabel('计划开始日期', { exact: true }).fill('2026-09-11');
    await page.getByLabel('计划结束日期', { exact: true }).fill('2026-09-23');
    await button('开始排产检查').click(); await button('重新检查').waitFor(); await flush();
    const data = last((_data, row) => row.url.endsWith('/scheduling/preflight'));
    assert.equal(data.counts.unready_batches, 1); assert.equal(data.counts.eligible_tasks, 0);
    assert.equal(data.tasks.length, 1); assert(data.tasks[0].issues.length > 0);
    report.unready_preflight = data;
    await shot('unready-preflight-reasons');
    await button('查看批次').click(); await page.locator('[data-batch-workspace]').waitFor(); await flush();
    assert((await page.locator('[data-batch-workspace]').innerText()).includes('Z-D-01'));
    await shot('preflight-batch-target');
  });
  await action(['WBP-RUN-005.return-context', 'WBP-RUN-005.invalidate-check'], async () => {
    const requests = report.requests.length;
    await button('返回排产').click(); await page.locator('[data-preflight-workspace]').waitFor(); await flush();
    const values = { start_date: await page.getByLabel('计划开始日期', { exact: true }).inputValue(),
      end_date: await page.getByLabel('计划结束日期', { exact: true }).inputValue(),
      window_text: await page.locator('.pf-window').innerText() };
    report.preflight_return = values;
    await shot('preflight-return-context');
    assert.equal(values.start_date, '2026-09-11'); assert.equal(values.end_date, '2026-09-23');
    assert(values.window_text.includes('已选 1 批'));
    assert.equal(await page.getByRole('table', { name: '排产前检查明细', exact: true }).count(), 0);
    const restored = await page.evaluate(() => history.state.workbench.context);
    assert.deepEqual(restored, report.unready_preflight.normalized_input);
    assert.deepEqual(Object.keys(restored).sort(), ['batch_refs', 'completed_policy', 'end_date', 'missing_resource_policy', 'ready_check', 'start_date']);
    assert(report.requests.slice(requests).every(row => row.method === 'GET'), 'Returning must not recheck or run automatically');
    await button('开始排产检查').waitFor();
    report.preflight_return.context = restored;
    await button('选择批次').click(); await flush();
    assert(await page.getByRole('checkbox', { name: '选择 Z-D-01', exact: true }).isChecked());
    await button('仅已齐套').click(); await flush();
    await page.locator('input[aria-label="选择 B1"]:checked').waitFor();
    await page.locator('input[aria-label="选择 B2"]:checked').waitFor();
  });
}
module.exports = { pickerActions, preflightReturn };
