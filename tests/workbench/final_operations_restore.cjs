'use strict';
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const inflight = require('./final_operations_inflight.cjs');

function files(config) {
  const paths = [config.database, ...[config.backup_dir, config.journal_dir].flatMap(directory =>
    fs.readdirSync(directory).filter(name => /\.(db|json)$/.test(name)).map(name => path.join(directory, name)))];
  return Object.fromEntries(paths.filter(name => fs.existsSync(name)).sort().map(name => [name, crypto.createHash('sha256').update(fs.readFileSync(name)).digest('hex')]));
}
async function restore(h) {
  const { page, config, mark, request, shot, download, assert, report } = h;
  await page.goto(config.origin + '/workbench?view=system');
  if (config.mode === 'cold') {
    await page.locator('[data-restore-maintenance=cold]').waitFor();
    await page.getByRole('radio', { name: config.theme === 'dark' ? '深色' : '浅色', exact: true }).check();
    await page.getByRole('textbox', { name: '查询标识', exact: true }).fill(config.reference);
    await page.getByRole('button', { name: '查询维护结果', exact: true }).click();
    await page.waitForURL('**reference=' + config.reference);
    assert((await page.locator('main').innerText()).includes(config.corrupt ? '维护记录损坏' : '校验中'));
    await mark(config.corrupt ? 'WBP-SYS-019.blocked' : 'WBP-SYS-019.pending', async () => {
      assert.equal(await page.locator('[data-restore-maintenance=cold]').count(), 1);
    });
    report.after_readonly_files = files(config);
    const file = await download('导出维护诊断', 'cold-diagnostic.json');
    report.diagnostic = JSON.parse(fs.readFileSync(file)); assert.equal(report.diagnostic.database_checked_by_page, false);
    await shot(config.corrupt ? 'cold-corrupt-readonly' : 'cold-pending-readonly');
    return;
  }
  await page.getByRole('button', { name: '查看备份与恢复', exact: true }).waitFor();
  if (config.theme === 'dark') await page.locator('.header-controls').getByRole('button').click();
  await page.getByRole('tab', { name: '备份恢复', exact: true }).click();
  const row = page.locator('.sm-backups-table tbody tr').filter({ hasText: '_F_selected_source.db' });
  await mark('WBP-SYS-009.select', () => row.click());
  const detail = page.getByRole('region', { name: '备份详情', exact: true });
  await detail.getByRole('button', { name: '恢复备份', exact: true }).click();
  await mark('WBP-SYS-009.cancel', () => page.getByRole('dialog').getByRole('button', { name: '取消', exact: true }).click());
  await detail.getByRole('button', { name: '恢复备份', exact: true }).click();
  const dialog = page.getByRole('dialog'), confirm = dialog.getByRole('button', { name: '确认恢复', exact: true });
  assert(await confirm.isDisabled()); await dialog.getByRole('checkbox').check(); assert(await confirm.isDisabled());
  await dialog.getByRole('textbox').fill('恢复'); await shot('restore-confirm');
  const held = config.inflight ? await inflight.begin(h) : null;
  const sent = page.waitForRequest(value => new URL(value.url()).pathname === '/api/workbench/v1/system/backups/restore' && value.method() === 'POST');
  const result = await mark('WBP-SYS-009.confirm', () => request('/system/backups/restore', async () => {
    await confirm.click(); if (held) await inflight.release(h, held);
  }, 200, 'POST'));
  report.restore_request = (await sent).postDataJSON();
  report.operation = result.data.operation;
  assert.equal(report.operation.state, config.expected || 'succeeded');
  report.after_restore_files = files(config);
  await page.locator('[data-restore-maintenance=warm]').waitFor();
  await page.getByText(config.expected === 'rollback_failed' ? '系统已暂停，维护结果待核实' : '维护已结束，请重启整个软件', { exact: true }).waitFor();
  await mark('WBP-SYS-009.restored-readonly', async () => {
    assert(await page.evaluate(() => document.getElementById('root').inert));
    assert.equal(await page.getByRole('button', { name: '确认结果', exact: true }).count(), 0);
  });
  await mark('WBP-SYS-019.blocked', async () => { await page.getByText('业务操作已停用，须重启整个软件', { exact: true }).waitFor(); });
  await page.getByText('维护阶段与核对信息', { exact: true }).click();
  const stages = page.locator('.sm-restore-content details');
  await mark('WBP-SYS-009.protection-backup', async () => {
    await page.getByText(report.operation.protection_filename, { exact: true }).waitFor();
    assert((await stages.innerText()).includes(report.operation.protection_sha256));
  });
  await mark('WBP-SYS-009.verify', async () => {
    assert(report.operation.history.some(row => row.state === 'verifying'));
    assert((await stages.innerText()).includes('校验中'));
  });
  if (config.expected) await mark(config.expected === 'rolled_back' ? ['WBP-SYS-009.rollback', 'WBP-SYS-019.failure']
    : ['WBP-SYS-009.rollback-failure', 'WBP-SYS-019.rollback-failure'], async () => {
    assert((await stages.innerText()).includes('回滚中'));
    assert((await page.locator('.sm-restore-content').innerText()).includes(config.expected === 'rolled_back' ? '恢复失败，已回滚' : '回滚失败，需人工核查'));
  });
  report.pending = await page.evaluate(() => JSON.parse(localStorage.getItem('aps_workbench_system_pending_v1')));
  assert.equal(report.pending.request_key, report.operation.request_key);
  await shot('restore-result-readonly');
  await page.getByRole('radio', { name: '维护记录编号', exact: true }).check();
  await page.getByRole('textbox', { name: '查询标识', exact: true }).fill(report.operation.job_ref);
  await page.getByRole('button', { name: '查询维护结果', exact: true }).click();
  await page.waitForFunction(() => !document.querySelector('[data-restore-maintenance] [aria-busy=true]'));
  const diagnostic = await download('导出维护诊断', 'restore-diagnostic.json');
  report.diagnostic = JSON.parse(fs.readFileSync(diagnostic)); assert.equal(report.diagnostic.result.operation.job_ref, report.operation.job_ref);
  await page.reload(); await page.locator('[data-restore-maintenance=cold]').waitFor();
  assert.equal(await page.evaluate(() => JSON.parse(localStorage.getItem('aps_workbench_system_pending_v1')).request_key), report.pending.request_key);
  await shot('restore-refresh-still-readonly');
  report.after_readonly_files = files(config); assert.deepEqual(report.after_readonly_files, report.after_restore_files);
}
module.exports = { restore };
