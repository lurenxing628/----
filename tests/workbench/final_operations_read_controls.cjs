'use strict';
async function readControls(h) {
  const { page, mark, request, select, assert, report, shot } = h;
  await h.dashboard();
  if (h.config.theme === 'dark') await page.getByRole('button', { name: '切换深色', exact: true }).click();
  await page.locator('.sidebar-nav').getByRole('link', { name: '系统管理', exact: true }).click();
  await page.getByRole('button', { name: '查看备份与恢复', exact: true }).waitFor();
  if (h.config.expected_config_fields) {
    const saved = await request('/system/config', () => page.getByRole('tab', { name: '配置', exact: true }).click());
    await mark(h.config.new_data_after_restore ? 'WBP-SYS-009.preserve-new-data' : 'WBP-SYS-018.restart', async () => {
      for (const [key, value] of Object.entries(h.config.expected_config_fields)) {
        const input = page.locator('#sm-maintenance-' + key); await input.waitFor();
        assert.equal(key.endsWith('_enabled') ? await input.isChecked() ? 'yes' : 'no' : await input.inputValue(), value);
      }
    });
    assert.deepEqual(saved.data.stored_values, h.config.expected_config_fields);
    assert.equal(await page.locator('.wb-current-plan').count(), 0);
    report.config_restart_values = saved.data.stored_values;
    await shot('config-restarted-process-readback'); return;
  }
  const all = await request('/system/backups', () => page.getByRole('tab', { name: '备份恢复', exact: true }).click());
  const region = page.getByRole('region', { name: '备份与维护记录', exact: true });
  const query = () => request('/system/backups', () => region.getByRole('button', { name: '查询', exact: true }).click());
  const clear = () => request('/system/backups', () => region.getByRole('button', { name: '清除筛选', exact: true }).click());
  if (h.config.restored_job_ref) {
    await select('记录类型', '恢复', region);
    const restored = await mark('WBP-SYS-006.type-restore', query);
    const event = restored.data.rows.find(row => row.event_ref === h.config.restored_job_ref);
    assert(event && event.record_kind === 'restore_event' && event.status === 'succeeded');
    await region.getByRole('button', { name: '查看详情 ' + event.summary, exact: true }).click();
    const detail = page.getByRole('region', { name: '维护事件详情', exact: true });
    await detail.waitFor(); await h.revealReference(detail, event.event_ref); assert((await detail.innerText()).includes(event.event_ref));
    assert.equal(await detail.getByRole('button', { name: /下载备份|恢复备份|删除备份/ }).count(), 0);
    await shot('real-restore-event-after-process-restart');
    await mark('WBP-SYS-009.restart', async () => { assert.equal(await page.locator('[data-restore-maintenance]').count(), 0); });
    report.restored_event = event; return;
  }
  assert(all.data.page.total > 10);
  await mark('WBP-SYS-007.next', () => request('/system/backups', () => region.getByRole('button', { name: '下一页', exact: true }).click()));
  await mark('WBP-SYS-007.previous', () => request('/system/backups', () => region.getByRole('button', { name: '上一页', exact: true }).click()));
  for (const size of [25, 50, 10]) await mark('WBP-SYS-007.size-' + size, () => request('/system/backups', () => select('每页数量', size + ' 条', region), 200, 'GET', { page: 1, page_size: size, snapshot_ref: '' }));
  for (const [type, label] of [['manual', '手动备份'], ['auto', '自动备份'], ['before_restore', '恢复前保护副本'], ['cleanup', '清理']]) {
    await select('记录类型', label, region);
    const value = await mark('WBP-SYS-006.type-' + type.replace('_', '-'), query);
    assert(value.data.rows.length > 0 && value.data.rows.every(row => row.type === type));
    if (type === 'cleanup') {
      const event = value.data.rows[0]; assert.equal(event.record_kind, 'cleanup_event');
      assert.equal(event.event_source, 'operation_audit'); assert.equal(JSON.parse(event.body).detail.removed_count, 1);
      await region.getByRole('button', { name: '查看详情 ' + event.summary, exact: true }).click();
      const detail = page.getByRole('region', { name: '维护事件详情', exact: true }); await detail.waitFor();
      assert.equal(await detail.getByRole('button', { name: /下载备份|恢复备份|删除备份/ }).count(), 0);
      await shot('real-cleanup-event-without-file-capabilities');
      report.cleanup_event = event;
      await page.reload(); await detail.waitFor();
      await h.revealReference(detail, event.event_ref); assert((await detail.innerText()).includes(event.event_ref));
      assert.equal(await detail.getByRole('button', { name: /下载备份|恢复备份|删除备份/ }).count(), 0);
      report.cleanup_read_context = await page.evaluate(() => history.state.workbench.context);
      assert.equal(report.cleanup_read_context.records.backups.filters.type, 'cleanup');
      assert.equal(report.cleanup_read_context.records.backups.selection.record_kind, 'cleanup_event');
      assert(!/write_token|request_key|confirmation/.test(JSON.stringify(report.cleanup_read_context)));
      await detail.getByRole('button', { name: '关闭详情', exact: true }).click();
    }
  }
  await clear();
  const file = all.data.rows.find(row => row.record_kind === 'backup_file'); assert(file);
  await region.getByLabel('搜索维护记录', { exact: true }).fill(file.filename);
  const selected = await mark('WBP-SYS-006.search', query); assert.equal(selected.data.page.total, 1);
  await select('记录状态', '未校验', region);
  await mark('WBP-SYS-006.status', query);
  for (const [label, action] of [['开始日期', 'start-date'], ['结束日期', 'end-date']]) {
    await region.getByLabel(label, { exact: true }).fill(file.time.slice(0, 10));
    const value = await mark('WBP-SYS-006.' + action, query); assert.equal(value.data.page.total, 1);
  }
  const row = region.locator('tbody tr').first();
  await mark(['time', 'type', 'status', 'filename', 'size', 'unread-state'].map(id => 'WBP-SYS-005.' + id).concat('WBP-SYS-019.unverified'), async () => {
    assert.equal(await row.locator('td').count(), 6); assert((await row.innerText()).includes(file.filename));
    const [whole, fraction] = (file.size_bytes / 1024).toFixed(1).split('.');
    const expectedSize = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + '.' + fraction + ' KB';
    const actualSize = await row.locator('td').nth(4).innerText();
    assert((await row.innerText()).includes('未校验')); assert.equal(actualSize, expectedSize);
    report.backup_size_display = { size_bytes: file.size_bytes, expected: expectedSize, actual: actualSize };
  });
  await row.click();
  const detail = page.getByRole('region', { name: '备份详情', exact: true });
  await mark(['WBP-SYS-007.full-body', 'WBP-SYS-007.validation-details'], async () => {
    await detail.waitFor(); assert.equal(await detail.locator('pre').innerText(), file.body);
    await detail.getByText('备份文件存在不代表已校验通过或可以恢复。', { exact: true }).waitFor();
  });
  await mark('WBP-SYS-007.close-x', () => detail.getByRole('button', { name: '关闭详情', exact: true }).click());
  await row.click(); await mark('WBP-SYS-007.close-escape', () => detail.press('Escape'));
  await mark('WBP-SYS-006.clear', clear);
  const logsRead = await request('/system/logs', () => page.getByRole('tab', { name: '运行日志', exact: true }).click());
  const logs = page.getByRole('region', { name: '运行日志与操作记录', exact: true });
  await select('记录类型', '运行日志', logs); await select('日志来源', '主日志（aps.log）', logs); await select('日志级别', '信息', logs);
  const logQuery = () => request('/system/logs', () => logs.getByRole('button', { name: '查询', exact: true }).click());
  const runtime = await mark(['WBP-SYS-011.runtime-source', 'WBP-SYS-012.type-runtime', 'WBP-SYS-012.search-file'], logQuery);
  assert(runtime.data.rows.length > 0 && runtime.data.rows.every(row => row.type === 'runtime' && row.file === 'aps.log' && row.level === 'INFO'));
  const runtimeRow = runtime.data.rows.find(row => row.time); assert(runtimeRow);
  for (const [label, action] of [['开始日期', 'start-date'], ['结束日期', 'end-date']]) {
    await logs.getByLabel(label, { exact: true }).fill(runtimeRow.time.slice(0, 10));
    const value = await mark('WBP-SYS-012.' + action, logQuery); assert(value.data.rows.length > 0);
  }
  await mark('WBP-SYS-011.columns', async () => { assert.equal(await logs.locator('thead th').count(), 6); });
  await logs.locator('tbody tr').first().click();
  await mark('WBP-SYS-011.detail', async () => { await page.getByRole('region', { name: '日志详情', exact: true }).waitFor(); });
  await mark('WBP-SYS-012.clear', () => request('/system/logs', () => logs.getByRole('button', { name: '清除筛选', exact: true }).click()));
  report.runtime_rows = runtime.data.rows; report.log_sources = logsRead.data.sources;
  await page.getByRole('tab', { name: '配置', exact: true }).click();
  await page.locator('#sm-maintenance-auto_backup_interval_minutes').waitFor();
  const original = await page.locator('#sm-maintenance-auto_backup_interval_minutes').inputValue();
  await page.locator('#sm-maintenance-auto_backup_interval_minutes').fill('57');
  await page.getByRole('button', { name: '放弃草稿', exact: true }).click();
  await mark('WBP-SYS-017.discard-confirm', () => request('/system/config', () => page.getByRole('dialog').getByRole('button', { name: '放弃并刷新', exact: true }).click()));
  assert.equal(await page.locator('#sm-maintenance-auto_backup_interval_minutes').inputValue(), original);
  await page.getByRole('radio', { name: '管理样例', exact: true }).check();
  await page.locator('#sm-auto_backup_interval_minutes').fill('53');
  await mark('WBP-SYS-017.validate', () => page.getByRole('button', { name: '检查参数', exact: true }).click());
  await mark('WBP-SYS-017.unsaved-preview', async () => { await page.getByText('样例草稿检查通过 · 未保存', { exact: true }).waitFor(); });
  assert.equal(await page.locator('.sm-preview dd').count(), 8);
  await page.locator('.sm-maintenance-config:visible').getByText('生效范围与自动维护规则', { exact: true }).click();
  await mark('WBP-SYS-019.skipped', async () => { await page.getByText(/备份失败时会跳过本轮备份清理，保底规则不会删掉全部近期副本。/).waitFor(); });
  await shot('sample-validation-is-explicitly-unsaved');
}
module.exports = { readControls };
