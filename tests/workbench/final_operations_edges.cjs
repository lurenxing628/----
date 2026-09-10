'use strict';
const fs = require('node:fs');
async function edges(h) {
  const { page, mark, request, assert, report, shot } = h;
  await h.dashboard();
  const item = await h.detail('delivery', '交期风险');
  await request('/dashboard/items/' + item.item_ref + '/history', () => page.locator('[data-detail-ref]').getByRole('button', { name: '查看处置历史', exact: true }).click());
  const history = page.getByRole('region', { name: '处置历史', exact: true });
  const second = await mark('WBP-DASH-006.history-page', () => request('/dashboard/items/' + item.item_ref + '/history', () => history.getByRole('button', { name: '历史下一页', exact: true }).click()));
  assert.equal(second.data.history.page.number, 2); assert.equal(second.data.history.page.total, 26);
  await page.reload(); await page.locator('[data-history-sequence="6"]').waitFor();
  assert.equal((await page.evaluate(() => window.history.state.workbench.context)).history_page, 2);
  await request('/dashboard/items/' + item.item_ref + '/history', () => history.getByRole('button', { name: '历史上一页', exact: true }).click());
  await shot('history-real-second-page-and-refresh');
  await page.locator('.sidebar-nav').getByRole('link', { name: '系统管理', exact: true }).click();
  await page.getByRole('button', { name: '查看自动维护策略', exact: true }).waitFor();
  await request('/system/config', () => page.getByRole('tab', { name: '配置', exact: true }).click());
  await mark('WBP-SYS-016.unknown-values', async () => {
    await page.getByText(/旧配置异常：.*原值：invalid-F-stored/).waitFor();
    assert.notEqual(await page.locator('#sm-maintenance-auto_backup_interval_minutes').inputValue(), '0');
  });
  await shot('invalid-stored-config-is-not-silently-saved');
  await mark('WBP-SYS-001.tab-overview', () => page.getByRole('tab', { name: '概况', exact: true }).click());
  await request('/system/backups', () => page.getByRole('tab', { name: '备份恢复', exact: true }).click());
  await page.getByRole('button', { name: '创建备份', exact: true }).click();
  const originalMode = fs.statSync(h.config.backup_dir).mode & 0o777;
  try {
    fs.chmodSync(h.config.backup_dir, 0o555);
    const failed = await mark('WBP-SYS-008.failure', () => request('/system/backups/create', () => page.getByRole('dialog').getByRole('button', { name: '确认创建', exact: true }).click(), 200, 'POST'));
    assert.equal(failed.data.operation.state, 'recovery_required'); assert.equal(failed.data.operation.code, 'storage_failure');
    const status = page.getByRole('region', { name: '维护原请求结果', exact: true });
    await status.getByText('需人工恢复核查', { exact: true }).waitFor();
    await mark(['WBP-SYS-019.failure', 'WBP-SYS-019.pending'], async () => { assert.equal(await status.getByRole('button', { name: '确认结果', exact: true }).count(), 0); });
    report.failed_create = failed;
    await shot('real-backup-storage-failure-retains-original-request');
  } finally { fs.chmodSync(h.config.backup_dir, originalMode); }
}
module.exports = { edges };
