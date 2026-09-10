'use strict';
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const fields = {
  auto_backup_enabled: 'yes', auto_backup_interval_minutes: '37', auto_backup_cleanup_enabled: 'no',
  auto_backup_keep_days: '17', auto_backup_cleanup_interval_minutes: '41', auto_log_cleanup_enabled: 'no',
  auto_log_cleanup_keep_days: '19', auto_log_cleanup_interval_minutes: '43',
};
async function system(h) {
  const { page, mark, request, select, shot, download, assert, report } = h;
  await page.locator('.sidebar-nav').getByRole('link', { name: '系统管理', exact: true }).click();
  await page.getByRole('button', { name: '重新检查', exact: true }).waitFor();
  await page.getByRole('button', { name: '查看备份与恢复', exact: true }).waitFor();
  await mark(['WBP-SYS-001.metric-page', 'WBP-SYS-001.metric-source', 'WBP-SYS-001.metric-database', 'WBP-SYS-001.metric-backup'], async () => {
    assert((await page.locator('.sm-metrics').innerText()).includes('未校验')); assert.equal(await page.locator('.sm-check-table tbody tr').count(), 8);
  });
  await mark('WBP-SYS-003.rerun', () => request('/system/overview', () => page.getByRole('button', { name: '重新检查', exact: true }).click()));
  const diagnostic = await mark('WBP-SYS-004.download-json', () => download('导出当前诊断 JSON', 'page-diagnostic.json'));
  const dto = JSON.parse(fs.readFileSync(diagnostic)); assert.equal(dto.system.meta.source, 'production'); assert.equal(dto.page_check.checks.length, 8);
  await mark(['WBP-SYS-004.verify-json-payload', 'WBP-SYS-003.timestamp', ...['runtime', 'scripts', 'ui', 'icons', 'styles', 'model', 'download', 'theme'].map(s => 'WBP-SYS-003.check-' + s)], async () => { assert(dto.page_check.checkedAt); assert(dto.page_check.checks.every(row => row.status === 'available')); });
  await shot('system-overview');
  for (const [title, tab, name] of [['查看备份与恢复', 'backups', '备份恢复'], ['查看运行日志', 'logs', '运行日志'], ['查看自动维护策略', 'config', '配置']]) {
    await mark('WBP-SYS-002.row-' + tab, async () => { await page.getByRole('button', { name: title, exact: true }).click(); assert.equal(await page.getByRole('tab', { name, exact: true }).getAttribute('aria-selected'), 'true'); });
    await page.getByRole('tab', { name: '概况', exact: true }).click();
  }
  await mark('WBP-SYS-001.source-sample', () => page.getByRole('radio', { name: '管理样例', exact: true }).check());
  await mark('WBP-SYS-001.source-current', () => page.getByRole('radio', { name: '本机数据', exact: true }).check());
  await mark('WBP-SYS-001.keyboard-tabs', async () => { await page.getByRole('tab', { name: '概况', exact: true }).focus(); await page.keyboard.press('End'); assert.equal(await page.getByRole('tab', { name: '配置', exact: true }).getAttribute('aria-selected'), 'true'); });
  const config = page.locator('.sm-maintenance-config:visible');
  await config.getByRole('button', { name: '保存维护配置', exact: true }).waitFor();
  for (const key of Object.keys(fields)) {
    const input = page.locator('#sm-maintenance-' + key);
    await mark('WBP-SYS-016.' + key, async () => {
      if (key.endsWith('_enabled')) { const previous = await input.isChecked(); await input.setChecked(!previous); await input.setChecked(fields[key] === 'yes'); }
      else await input.fill(fields[key]);
    });
  }
  await page.locator('#sm-maintenance-auto_backup_interval_minutes').fill('0');
  await mark('WBP-SYS-017.invalid-fields', async () => { await config.getByRole('button', { name: '保存维护配置', exact: true }).click(); await config.getByText('配置校验未通过，请修正标出的字段。', { exact: true }).waitFor(); });
  await page.locator('#sm-maintenance-auto_backup_interval_minutes').fill('37');
  await mark('WBP-SYS-017.discard-cancel', async () => { await page.getByRole('button', { name: '放弃草稿', exact: true }).click(); await page.getByRole('dialog').getByRole('button', { name: '保留草稿', exact: true }).click(); assert.equal(await page.locator('#sm-maintenance-auto_backup_interval_minutes').inputValue(), '37'); });
  await shot('system-eight-fields');
  let dropped = false;
  await page.route('**/api/workbench/v1/system/config/save', async route => {
    assert(!dropped); dropped = true; const response = await route.fetch(); assert.equal(response.status(), 200);
    report.config_committed_response = await response.json(); report.config_input = route.request().postDataJSON(); await route.abort('failed');
  });
  await mark('WBP-SYS-018.save', () => config.getByRole('button', { name: '保存维护配置', exact: true }).click());
  await page.getByRole('region', { name: '维护原请求结果', exact: true }).getByText(/原操作仍待核实/).waitFor();
  await mark('WBP-SYS-018.unknown-result', async () => { report.config_pending = await page.evaluate(() => JSON.parse(localStorage.getItem('aps_workbench_system_pending_v1'))); assert.equal(report.config_pending.action, 'config'); });
  await shot('system-config-unknown');
  await page.unroute('**/api/workbench/v1/system/config/save');
  await mark(['WBP-SYS-018.reload', 'WBP-SYS-018.lookup', 'WBP-SYS-018.original-receipt'], async () => {
    await page.reload(); await page.getByText('八项维护配置已保存，事务和审计已留存。', { exact: true }).waitFor();
    const original = await page.evaluate(() => JSON.parse(localStorage.getItem('aps_workbench_system_pending_v1'))); assert.equal(original.request_key, report.config_pending.request_key);
  });
  await shot('system-config-original-receipt'); await page.getByRole('button', { name: '确认结果', exact: true }).click();
  await mark('WBP-SYS-001.tab-config', () => page.getByRole('tab', { name: '配置', exact: true }).click());
  await page.locator('#sm-maintenance-auto_backup_interval_minutes').waitFor();
  await mark('WBP-SYS-016.read-snapshot', async () => { for (const [key, value] of Object.entries(fields)) {
    const input = page.locator('#sm-maintenance-' + key); assert.equal(key.endsWith('_enabled') ? await input.isChecked() ? 'yes' : 'no' : await input.inputValue(), value); } });
  for (const [name, id] of [['深色', 'dark'], ['浅色', 'light']]) await mark('WBP-SYS-015.' + id, () => page.getByRole('radio', { name, exact: true }).check());
  await page.getByRole('radio', { name: h.config.theme === 'dark' ? '深色' : '浅色', exact: true }).check();
  await mark('WBP-SYS-015.compact', async () => { await page.getByLabel('紧凑行距', { exact: true }).uncheck(); await page.getByLabel('紧凑行距', { exact: true }).check(); });
  for (const n of [25, 50, 10]) await mark('WBP-SYS-015.size-' + n, async () => {
    await page.locator('.sm-preferences select').click(); await page.locator('.wb-control-popup').getByRole('option', { name: n + ' 条', exact: true }).click();
  });
  await mark(['WBP-SYS-019.scope', 'WBP-SYS-019.request-trigger'], () => page.getByText('生效范围与自动维护规则', { exact: true }).click());
  await mark('WBP-SYS-001.tab-logs', () => page.getByRole('tab', { name: '运行日志', exact: true }).click());
  const logs = page.getByRole('region', { name: '运行日志与操作记录', exact: true });
  await logs.getByRole('button', { name: '查询', exact: true }).waitFor();
  await select('日志来源', '操作记录', logs); await select('记录类型', '操作记录', logs); await select('记录状态', '已记录', logs); await select('日志级别', 'INFO', logs);
  await logs.getByLabel('搜索维护记录', { exact: true }).fill('F operation row');
  const filtered = await mark(['WBP-SYS-011.operation-source', 'WBP-SYS-012.search-detail', 'WBP-SYS-012.type-operation', 'WBP-SYS-012.status', 'WBP-SYS-012.level', 'WBP-SYS-012.record-set'], () => request('/system/logs', () => logs.getByRole('button', { name: '查询', exact: true }).click()));
  assert.equal(filtered.data.page.total, 31);
  await mark('WBP-SYS-012.page', () => request('/system/logs', () => logs.getByRole('button', { name: '下一页', exact: true }).click()));
  await logs.locator('tbody tr').first().click(); await mark('WBP-SYS-012.detail', async () => { await page.getByRole('region', { name: '日志详情', exact: true }).waitFor(); });
  await page.waitForFunction(() => { const c = history.state && history.state.workbench && history.state.workbench.context; return c && c.records && c.records.logs && c.records.logs.page === 2 && c.records.logs.selection; });
  report.system_read_context = await page.evaluate(() => history.state.workbench.context);
  assert(!/write_token|request_key|auto_backup_|confirmation/.test(JSON.stringify(report.system_read_context)));
  await page.reload(); await page.getByRole('region', { name: '日志详情', exact: true }).waitFor();
  assert.equal(await page.getByRole('tab', { name: '运行日志', exact: true }).getAttribute('aria-selected'), 'true');
  assert((await logs.locator('.sm-pager').innerText()).includes('2 / 4'));
  assert.equal(await logs.getByLabel('搜索维护记录', { exact: true }).inputValue(), 'F operation row');
  await page.locator('.sidebar-nav a[href*="view=dashboard"]').click(); await page.locator('[data-dashboard-workspace][data-ready=true]').waitFor();
  await page.goBack(); await page.getByRole('region', { name: '日志详情', exact: true }).waitFor();
  assert((await logs.locator('.sm-pager').innerText()).includes('2 / 4'));
  await shot('system-log-detail-restored'); await page.getByRole('region', { name: '日志详情', exact: true }).press('Escape');
  await request('/system/logs', () => logs.getByRole('button', { name: '上一页', exact: true }).click());
  report.log_rows = filtered.data.page.total;
  await mark(['WBP-SYS-013.export', 'WBP-SYS-013.all-filtered-pages'], () => download('导出窗口 CSV', 'logs.csv', logs));
  await mark(['WBP-SYS-014.build-zip', 'WBP-SYS-014.download-zip'], () => download('脱敏诊断 ZIP', 'logs.zip', logs));
  await shot('system-logs');
  await mark('WBP-SYS-001.tab-backups', () => page.getByRole('tab', { name: '备份恢复', exact: true }).click());
  await page.getByRole('button', { name: '创建备份', exact: true }).waitFor();
  await page.getByRole('button', { name: '创建备份', exact: true }).click(); await page.getByRole('dialog').getByRole('button', { name: '取消', exact: true }).click();
  await page.getByRole('button', { name: '创建备份', exact: true }).click();
  const created = await mark('WBP-SYS-008.create', () => request('/system/backups/create', () => page.getByRole('dialog').getByRole('button', { name: '确认创建', exact: true }).click(), 200, 'POST'));
  assert.equal(created.data.operation.state, 'succeeded'); report.created_backup = created.data.operation;
  const backupBytes = fs.readFileSync(path.join(h.config.backup_dir, created.data.operation.filename));
  await mark('WBP-SYS-008.database-payload', async () => { assert.equal(backupBytes.subarray(0, 16).toString(), 'SQLite format 3\u0000'); });
  fs.writeFileSync(path.join(h.config.output, 'created-backup-payload.db'), backupBytes);
  report.created_payload_sha256 = crypto.createHash('sha256').update(backupBytes).digest('hex');
  await mark('WBP-SYS-008.receipt', async () => { await page.getByRole('region', { name: '维护原请求结果', exact: true }).getByText('已完成', { exact: true }).waitFor(); });
  await page.getByRole('button', { name: '确认结果', exact: true }).click();
  const filename = created.data.operation.filename, backups = page.getByRole('region', { name: '备份与恢复记录', exact: true });
  await mark('WBP-SYS-010.select', () => backups.getByRole('button', { name: '查看详情 ' + filename, exact: true }).click());
  await mark('WBP-SYS-005.detail', async () => { await page.getByRole('region', { name: '备份详情', exact: true }).waitFor(); });
  await mark('WBP-SYS-008.download-backup', () => download('下载备份', filename, page.getByRole('region', { name: '备份详情', exact: true })));
  const downloadedBackup = fs.readFileSync(path.join(h.config.output, filename));
  assert.deepEqual(downloadedBackup, backupBytes);
  await mark('WBP-SYS-008.verify-downloaded-database', async () => { assert.equal(downloadedBackup.subarray(0, 16).toString(), 'SQLite format 3\u0000'); });
  await shot('system-backup-created');
  await page.getByRole('region', { name: '备份详情', exact: true }).getByRole('button', { name: '删除备份', exact: true }).click();
  await mark('WBP-SYS-010.cancel', () => page.getByRole('dialog').getByRole('button', { name: '取消', exact: true }).click());
  await page.getByRole('region', { name: '备份详情', exact: true }).getByRole('button', { name: '删除备份', exact: true }).click();
  await page.getByRole('dialog').getByRole('checkbox').check();
  const deleted = await mark('WBP-SYS-010.confirm', () => request('/system/backups/delete', () => page.getByRole('dialog').getByRole('button', { name: '确认删除', exact: true }).click(), 200, 'POST'));
  assert.equal(deleted.data.operation.state, 'succeeded'); report.deleted_backup = deleted.data.operation;
  await mark('WBP-SYS-010.receipt', async () => { await page.getByRole('region', { name: '维护原请求结果', exact: true }).getByText('已完成', { exact: true }).waitFor(); });
  await page.getByRole('button', { name: '确认结果', exact: true }).click();
  await mark('WBP-SYS-010.filesystem-removal', async () => {
    assert.equal(fs.existsSync(path.join(h.config.backup_dir, filename)), false);
    assert.equal(await backups.getByRole('button', { name: '查看详情 ' + filename, exact: true }).count(), 0);
  });
  await shot('system-backup-deleted');
  report.config_fields = fields;
}
module.exports = { system, fields };
