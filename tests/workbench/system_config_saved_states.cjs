'use strict';
const path = require('node:path');

async function fields(page, H) {
  const { assert, interval, ready, externalSave, read, revision, conflict, clean, passed, report } = H;
  await ready(page);
  const original = (await read(page)).data.values;
  const fields = await page.evaluate(() => window.SystemMaintenanceAPI.fields);
  for (const field of fields) {
    await externalSave(page, original); await page.reload(); await ready(page);
    await interval(page).fill('121');
    const draft = {...original, auto_backup_interval_minutes: 121};
    const different = field.switch ? draft[field.key] === 'yes' ? 'no' : 'yes' : draft[field.key] === field.max ? 1 : draft[field.key] + 1;
    const saved = await externalSave(page, {...draft, [field.key]: different});
    await revision(page); await conflict(page, 121);
    const values = await page.evaluate(() => Object.fromEntries(window.SystemMaintenanceAPI.fields.map(field => {
      const node = document.getElementById('sm-maintenance-' + field.key);
      return [field.key, field.switch ? node.checked ? 'yes' : 'no' : Number(node.value)];
    })));
    assert.deepEqual(values, draft);
    await page.getByText(field.label + '：' + saved.values[field.key], { exact: true }).count().then(count => assert.equal(count, 1));
    passed('one-different-field-keeps-entire-draft-' + field.key);
    await externalSave(page, draft); await revision(page); await ready(page); await clean(page, 121);
    passed('all-eight-equal-adopts-baseline-after-' + field.key);
  }
  assert(report.requests.filter(row => row.method === 'POST').every(row => Object.keys(row.input).length === 8));
}

async function states(page, H) {
  const { assert, report, output, interval, save, ready, settled, clean, passed, acknowledge, pending, read,
    externalSave, revision, conflict, resetPage, flush } = H;
  await ready(page);
  const initialCount = report.requests.filter(row => row.method === 'POST').length;
  const original = (await read(page)).data.values;
  await page.getByLabel('深色', { exact: true }).check(); await page.getByLabel('每页条数').selectOption('25');
  await page.getByLabel('紧凑行距', { exact: true }).uncheck();
  assert.equal(report.requests.filter(row => row.method === 'POST').length, initialCount);
  assert.deepEqual((await read(page)).data.values, original); passed('preferences-never-write-maintenance-config');
  for (const value of ['0', '1.5', '1441', '']) {
    await interval(page).fill(value); await save(page).click();
    await page.getByText('有几项填得不对，配置没有保存。请修正标红的项。', { exact: true }).waitFor();
    assert.equal(report.requests.filter(row => row.method === 'POST').length, initialCount);
    passed('invalid-input-kept-without-post-' + (value || 'empty'));
  }
  await interval(page).fill('121'); await save(page).click();
  await page.getByRole('button', { name: '确认结果', exact: true }).waitFor();
  const originalPending = await pending(page), count = report.requests.filter(row => row.method === 'POST').length;
  await page.getByRole('button', { name: 'overview', exact: true }).click(); await page.getByRole('button', { name: 'config', exact: true }).click();
  await settled(page); await clean(page, 121);
  assert(await save(page).isDisabled()); assert(await interval(page).isDisabled());
  assert.deepEqual(await pending(page), originalPending);
  assert(await page.getByLabel('深色', { exact: true }).isChecked());
  assert.equal(await page.getByLabel('每页条数').inputValue(), '25');
  assert.equal(await page.getByLabel('紧凑行距', { exact: true }).isChecked(), false);
  passed('equal-readback-before-acknowledgement-keeps-original-lock');
  await page.reload(); await page.getByRole('button', { name: '确认结果', exact: true }).waitFor(); await settled(page);
  assert(await save(page).isDisabled()); assert.equal(report.requests.filter(row => row.method === 'POST').length, count);
  assert.deepEqual(await pending(page), originalPending); passed('unacknowledged-reload-uses-get-only');
  await acknowledge(page); await ready(page); await clean(page, 121);
  await save(page).click(); await page.getByText('配置没有变化，没有写入新的操作记录。').waitFor();
  await acknowledge(page); await ready(page); await clean(page, 121); passed('unchanged-receipt-readback-is-clean');

  await resetPage(page); await interval(page).fill('121'); await save(page).click();
  await page.getByRole('button', { name: '确认结果', exact: true }).waitFor();
  await externalSave(page, {auto_backup_interval_minutes: 122});
  await acknowledge(page); await settled(page); await conflict(page, 121);
  assert.equal((await read(page)).data.values.auto_backup_interval_minutes, 122);
  await page.screenshot({ path: path.join(output, 'system_config_saved_conflict.png'), fullPage: true });
  passed('another-save-after-our-receipt-preserves-draft-and-demands-review');
  await page.getByRole('button', { name: '核对后沿用草稿', exact: true }).click(); await ready(page);
  const posts = report.requests.filter(row => row.method === 'POST').length;
  await save(page).click(); await page.getByRole('button', { name: '确认结果', exact: true }).waitFor();
  await acknowledge(page); await ready(page); await clean(page, 121);
  assert.equal(report.requests.filter(row => row.method === 'POST').length, posts + 1);
  passed('explicit-review-uses-new-write-token-and-saves-once');

  await resetPage(page); await interval(page).fill('121');
  await externalSave(page, {auto_backup_interval_minutes: 122}); await save(page).click();
  await page.getByText('系统拒绝了这次提交，配置没有改动。请按上面的提示改好后重新提交。', { exact: true }).waitFor();
  assert(await save(page).isDisabled()); await acknowledge(page); await settled(page); await conflict(page, 121);
  assert(report.requests.some(row => row.path.endsWith('/config/save') && row.status === 409));
  passed('stale-rejection-does-not-rebase-to-receipt-or-discard-draft');

  await resetPage(page); await interval(page).fill('121'); await save(page).click();
  await page.getByRole('button', { name: '确认结果', exact: true }).waitFor();
  const readEndpoint = '**/api/workbench/v1/system/config';
  await page.route(readEndpoint, route => route.abort('failed')); await acknowledge(page);
  await page.locator('.sm-maintenance-config [role="alert"]').waitFor();
  assert.equal(await interval(page).inputValue(), '121'); assert(await save(page).isDisabled());
  await page.getByText('有未保存修改', { exact: true }).waitFor();
  passed('confirmed-receipt-with-failed-read-does-not-pretend-draft-is-saved');
  await page.getByRole('button', { name: '刷新配置', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: '保留草稿', exact: true }).click();
  assert.equal(await interval(page).inputValue(), '121');
  await page.unroute(readEndpoint); await revision(page); await ready(page); await clean(page, 121);
  passed('failed-read-recovery-adopts-only-the-next-real-equal-snapshot');

  await resetPage(page); await interval(page).fill('121');
  const endpoint = '**/api/workbench/v1/system/config/save';
  await page.route(endpoint, async route => { await route.fetch(); await route.abort('failed'); });
  await save(page).click(); await page.locator('.sm-maintenance-outcome [role="alert"]').waitFor();
  assert.equal(await page.getByRole('button', { name: '确认结果', exact: true }).count(), 0);
  const unknown = await pending(page), afterLost = report.requests.filter(row => row.method === 'POST').length;
  await page.unroute(endpoint);
  await page.getByRole('button', { name: 'overview', exact: true }).click(); await page.getByRole('button', { name: 'config', exact: true }).click();
  await settled(page); await clean(page, 121); assert(await save(page).isDisabled()); assert(await interval(page).isDisabled());
  assert.deepEqual(await pending(page), unknown); assert.equal(report.requests.filter(row => row.method === 'POST').length, afterLost);
  passed('lost-committed-response-equal-readback-does-not-unlock-or-resend');
  await page.getByRole('button', { name: '查询结果', exact: true }).click();
  await page.getByRole('button', { name: '确认结果', exact: true }).waitFor(); assert(await save(page).isDisabled());
  await acknowledge(page); await ready(page); await clean(page, 121);
  assert.equal(report.requests.filter(row => row.method === 'POST').length, afterLost); passed('lost-response-recovers-original-receipt-get-only');

  await resetPage(page); await interval(page).fill('121');
  await page.route(endpoint, route => route.abort('failed')); await save(page).click();
  await page.locator('.sm-maintenance-outcome [role="alert"]').waitFor(); await page.unroute(endpoint);
  const notRecorded = await pending(page), noWrite = report.requests.filter(row => row.method === 'POST').length;
  await page.getByRole('button', { name: '查询结果', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('.sm-maintenance-outcome').textContent.includes('查不到结果不代表没有执行'));
  await revision(page); await conflict(page, 121); assert(await page.getByRole('button', { name: '核对后沿用草稿', exact: true }).isDisabled());
  assert.equal(await page.getByRole('button', { name: '确认结果', exact: true }).count(), 0);
  await page.reload(); await settled(page); await flush(page);
  assert(await save(page).isDisabled()); assert.deepEqual(await pending(page), notRecorded);
  assert.equal(report.requests.filter(row => row.method === 'POST').length, noWrite);
  assert.equal((await read(page)).data.values.auto_backup_interval_minutes, 120);
  passed('not-recorded-result-stays-pending-across-revision-and-reload-without-resend');
  assert(report.requests.filter(row => row.method === 'POST').every(row => Object.keys(row.input).length === 8 && Object.keys(row.input).every(key => key.startsWith('auto_'))));
}

async function metadata(page, H) {
  const { assert, report, interval, save, ready, clean, acknowledge, passed, output, revision } = H;
  await ready(page);
  await page.getByText(/旧配置异常：.*原值：bad-old-value/).waitFor(); await page.getByText('默认值，尚未保存', { exact: true }).waitFor();
  assert.equal(await page.locator('.sm-config-row').count(), 8);
  const before = report.requests.filter(row => row.method === 'POST').length;
  await revision(page); await page.getByText(/旧配置异常：.*原值：bad-old-value/).waitFor();
  assert.equal(report.requests.filter(row => row.method === 'POST').length, before);
  passed('eight-fields-old-raw-value-and-default-labels-survive-reread');
  await interval(page).fill('121'); await save(page).click(); await page.getByRole('button', { name: '确认结果', exact: true }).waitFor();
  await page.getByText(/旧配置异常：.*原值：bad-old-value/).waitFor();
  await acknowledge(page); await ready(page); await clean(page, 121);
  assert.equal(await page.getByText(/旧配置异常/).count(), 0); assert.equal(await page.getByText('默认值，尚未保存', { exact: true }).count(), 0);
  assert.equal(await page.locator('.sm-config-row small').filter({hasText: '已存值：'}).count(), 8);
  await page.screenshot({path: path.join(output, 'system_config_saved_metadata.png'), fullPage: true});
  passed('confirmed-equal-snapshot-refreshes-raw-default-metadata-as-well-as-baseline');
}

module.exports = {fields, states, metadata};
