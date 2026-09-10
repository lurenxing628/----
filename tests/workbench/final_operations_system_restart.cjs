'use strict';
const fs = require('node:fs'), path = require('node:path');

async function systemRestart(h) {
  const { page, request, select, assert, config, report, shot } = h;
  const writes = [];
  page.on('request', value => { if (!['GET', 'HEAD'].includes(value.method())) writes.push({ url: value.url(), method: value.method(), input: value.postDataJSON() }); });
  await h.dashboard();
  if (config.theme === 'dark') await page.locator('.header-controls').getByRole('button').click();
  await page.locator('.sidebar-nav').getByRole('link', { name: '系统管理', exact: true }).click();
  await page.getByRole('button', { name: '查看备份与恢复', exact: true }).waitFor();
  const backupRows = page.getByRole('region', { name: '备份与恢复记录', exact: true });
  const logRows = page.getByRole('region', { name: '运行日志与操作记录', exact: true });
  await request('/system/backups', () => page.getByRole('tab', { name: '备份恢复', exact: true }).click());
  await select('记录类型', '手动备份', backupRows);
  await select('记录状态', '未校验', backupRows);
  await backupRows.getByLabel('搜索维护记录', { exact: true }).fill('_F-SR');
  const listed = await request('/system/backups', () => backupRows.getByRole('button', { name: '查询', exact: true }).click());
  assert.equal(listed.data.page.total, 15);
  const files = await request('/system/backups', () => backupRows.getByRole('button', { name: '下一页', exact: true }).click());
  report.original_file = files.data.rows[0];
  await backupRows.getByRole('button', { name: '查看详情 ' + report.original_file.filename, exact: true }).click();
  await page.getByRole('region', { name: '备份详情', exact: true }).waitFor();
  await request('/system/logs', () => page.getByRole('tab', { name: '运行日志', exact: true }).click());
  await select('日志来源', '操作记录', logRows); await select('记录类型', '操作记录', logRows);
  await select('记录状态', '已记录', logRows); await select('日志级别', 'INFO', logRows);
  await logRows.getByLabel('搜索维护记录', { exact: true }).fill('F operation row');
  const allLogs = await request('/system/logs', () => logRows.getByRole('button', { name: '查询', exact: true }).click());
  assert.equal(allLogs.data.page.total, 31);
  const logs = await request('/system/logs', () => logRows.getByRole('button', { name: '下一页', exact: true }).click());
  report.original_log = logs.data.rows[0];
  await logRows.locator('tbody tr').first().click();
  await page.getByRole('region', { name: '日志详情', exact: true }).waitFor();
  if (config.active_kind === 'backups') {
    await request('/system/backups', () => page.getByRole('tab', { name: '备份恢复', exact: true }).click());
    await page.getByRole('region', { name: '备份详情', exact: true }).waitFor();
  }
  if (config.recovery_case === 'pending_config') {
    await request('/system/config', () => page.getByRole('tab', { name: '配置', exact: true }).click());
    await page.locator('#sm-maintenance-auto_backup_interval_minutes').fill('73');
    let committed, failed;
    const saved = new Promise((resolve, reject) => { committed = resolve; failed = reject; });
    await page.route('**/api/workbench/v1/system/config/save', async route => {
      try {
        const response = await route.fetch(); assert.equal(response.status(), 200);
        report.committed_config = await response.json(); report.config_input = route.request().postDataJSON();
        await route.abort('failed'); committed();
      } catch (error) { failed(error); }
    });
    const submitted = page.waitForRequest(value => new URL(value.url()).pathname === '/api/workbench/v1/system/config/save' && value.method() === 'POST');
    await page.getByRole('button', { name: '保存维护配置', exact: true }).click();
    await submitted; await saved;
    await page.getByRole('region', { name: '维护原请求结果', exact: true }).getByText(/原操作仍待核实/).waitFor();
    report.pending_before_restart = await page.evaluate(() => JSON.parse(localStorage.getItem('aps_workbench_system_pending_v1')));
    assert.equal(report.pending_before_restart.request_key, report.config_input.request_key);
    await page.unroute('**/api/workbench/v1/system/config/save');
    await request('/system/backups', () => page.getByRole('tab', { name: '备份恢复', exact: true }).click());
    await page.getByRole('region', { name: '备份详情', exact: true }).waitFor();
  }
  await page.waitForFunction(kind => {
    const c = history.state.workbench.context;
    return c.tab === kind && c.records.backups && c.records.logs && c.records.backups.selection && c.records.logs.selection;
  }, config.active_kind);
  if (config.recovery_case === 'legacy_selection') {
    await page.evaluate(({ backupRef, snapshot }) => {
      const state = structuredClone(history.state);
      state.workbench.context.records.backups.selection = { backup_ref: backupRef };
      state.workbench.context.records.backups.snapshot_ref = snapshot;
      history.replaceState(state, '', location.href);
    }, { backupRef: report.original_file.backup_ref, snapshot: files.meta.snapshot_ref });
    report.negative_legacy_history_fixture = true;
  }
  report.before_restart = { url: page.url(), context: await page.evaluate(() => history.state.workbench.context),
    snapshots: { backups: files.meta.snapshot_ref, logs: logs.meta.snapshot_ref } };
  await shot('system-' + config.active_kind + '-page-two-before-process-restart');
  fs.writeFileSync(path.join(config.restart_dir, 'browser-restart-request.json'), JSON.stringify(report));
  const resume = path.join(config.restart_dir, 'browser-restart-resume.json'), deadline = Date.now() + 60000;
  while (!fs.existsSync(resume) && Date.now() < deadline) await new Promise(resolve => setTimeout(resolve, 100));
  assert(fs.existsSync(resume));
  report.process_restart = JSON.parse(fs.readFileSync(resume, 'utf8'));
  assert.notEqual(report.process_restart.first_pid, report.process_restart.second_pid);
  assert.equal(report.process_restart.first_port, report.process_restart.second_port);
  const collected = [];
  const capture = response => { if (/\/api\/workbench\/v1\/system\/(backups|logs)$/.test(new URL(response.url()).pathname)) collected.push(response); };
  page.on('response', capture);
  const writesBeforeRestart = writes.length;
  await page.reload();
  if (['replaced_file', 'legacy_selection'].includes(config.recovery_case)) {
    const message = config.recovery_case === 'legacy_selection' ? '原选择缺少可信的稳定记录标识或记录类型' : '原选择记录未通过当前返回页的唯一身份核对';
    await backupRows.getByText(new RegExp(message)).waitFor();
    assert.equal(await page.getByRole('region', { name: '备份详情', exact: true }).count(), 0);
    assert.equal(await page.getByRole('dialog').count(), 0);
    assert.equal(await backupRows.locator('tbody tr[aria-expanded=true]').count(), 0);
    await backupRows.locator('.sm-page-number').getByText('2 / 2', { exact: true }).waitFor();
    page.off('response', capture);
    report.after_restart = { url: page.url(), context: await page.evaluate(() => history.state.workbench.context), reads: [] };
    for (const response of collected) report.after_restart.reads.push({ url: response.url(), status: response.status(), payload: await response.json() });
    assert.equal(report.after_restart.reads.length, 1); assert.equal(report.after_restart.reads[0].status, 200);
    const record = report.after_restart.context.records.backups;
    assert.deepEqual(record.filters, report.before_restart.context.records.backups.filters); assert.equal(record.page, 2);
    assert.equal(record.snapshot_ref, undefined); assert.equal(record.selection.backup_ref, undefined);
    if (config.recovery_case === 'replaced_file') {
      const sameName = report.after_restart.reads[0].payload.data.rows.filter(row => row.filename === report.original_file.filename);
      assert.equal(sameName.length, 1); assert.notEqual(sameName[0].key, report.original_file.key);
      assert.equal(record.selection.key, report.original_file.key); report.replacement_file = sameName[0];
    } else assert.equal(record.selection.key, undefined);
    report.browser_writes = writes; assert.equal(writes.length, 0);
    await shot('system-' + config.recovery_case + '-not-substituted-after-restart');
    return;
  }
  const labels = { backups: '备份详情', logs: '日志详情' };
  await page.getByRole('region', { name: labels[config.active_kind], exact: true }).waitFor();
  if (config.recovery_case === 'pending_config') {
    await page.getByText('八项维护配置已保存，事务和审计已留存。', { exact: true }).waitFor();
    const pending = await page.evaluate(() => JSON.parse(localStorage.getItem('aps_workbench_system_pending_v1')));
    assert.deepEqual(pending, report.pending_before_restart);
    const receipt = report.responses.find(row => new URL(row.url).pathname.endsWith('/system/results/' + pending.request_key));
    assert(receipt && receipt.status === 200); assert.equal(receipt.payload.data.command.receipt_ref, report.committed_config.receipt_ref);
    assert.equal(writes.length, writesBeforeRestart); assert.equal(writes.length, 1);
    report.pending_after_restart = pending; report.original_receipt_lookup = receipt;
  }
  await shot('system-' + config.active_kind + '-page-two-after-process-restart');
  const other = config.active_kind === 'backups' ? 'logs' : 'backups';
  await request('/system/' + other, () => page.getByRole('tab', { name: other === 'logs' ? '运行日志' : '备份恢复', exact: true }).click());
  await page.getByRole('region', { name: labels[other], exact: true }).waitFor();
  await shot('system-' + other + '-retained-inactive-selection-after-restart');
  page.off('response', capture);
  report.after_restart = { url: page.url(), context: await page.evaluate(() => history.state.workbench.context), reads: [] };
  for (const response of collected) report.after_restart.reads.push({ url: response.url(), status: response.status(), payload: await response.json() });
  const expected = structuredClone(report.before_restart.context); expected.tab = other;
  for (const record of Object.values(expected.records)) { delete record.snapshot_ref; if (record.selection) delete record.selection.backup_ref; }
  assert.deepEqual(report.after_restart.context, expected);
  for (const kind of ['backups', 'logs']) {
    const reads = report.after_restart.reads.filter(row => new URL(row.url).pathname.endsWith('/' + kind));
    assert.equal(reads.length, 1); assert.equal(reads[0].status, 200);
    assert.equal(reads[0].payload.data.page.number, 2);
    assert.notEqual(reads[0].payload.meta.snapshot_ref, report.before_restart.snapshots[kind]);
    const selection = report.after_restart.context.records[kind].selection;
    const matches = reads[0].payload.data.rows.filter(row => row.key === selection.key);
    assert.equal(matches.length, 1);
    assert.equal(matches[0].key, kind === 'backups' ? report.original_file.key : report.original_log.key);
    if (kind === 'backups') { assert.notEqual(matches[0].backup_ref, report.original_file.backup_ref); report.rebound_file = matches[0]; }
    const params = new URL(reads[0].url).searchParams;
    assert.equal(params.has('snapshot_ref'), false);
    for (const [key, value] of Object.entries(expected.records[kind].filters)) assert.equal(params.get(key) || '', value);
  }
  assert(!/snapshot_ref|backup_ref|write_token/.test(JSON.stringify(report.after_restart.context)));
  report.browser_writes = writes;
  assert.equal(writes.length, config.recovery_case === 'pending_config' ? 1 : 0);
  assert.equal(writes.length, writesBeforeRestart);
}

module.exports = { systemRestart };
