'use strict';

module.exports = async function races(page, H) {
  const { assert, report, interval, save, ready, settled, clean, passed, acknowledge, externalSave, revision,
    conflict, hold, held, release, resetPage, flush, pending } = H;
  await ready(page); await interval(page).fill('121'); await save(page).click();
  await page.getByRole('button', {name: '确认结果', exact: true}).waitFor();
  await hold(page, 'confirmed-equal'); await acknowledge(page); await held(page, 'confirmed-equal');
  assert(await interval(page).isDisabled());
  await externalSave(page, {auto_backup_interval_minutes: 122}); await revision(page); await conflict(page, 121);
  assert(await page.evaluate(() => window.configSavedNetwork.held['confirmed-equal'].signal.aborted));
  await release(page, 'confirmed-equal'); await conflict(page, 121);
  assert.equal(await page.getByText('备份检查间隔：122', {exact: true}).count(), 1);
  passed('late-equal-save-read-cannot-clear-newer-conflicting-snapshot');

  await resetPage(page); await hold(page, 'old-120');
  await page.evaluate(() => window.configSavedProbe.bump()); await held(page, 'old-120');
  await externalSave(page, {auto_backup_interval_minutes: 121}); await revision(page); await ready(page); await clean(page, 121);
  await interval(page).fill('122');
  await release(page, 'old-120'); assert.equal(await interval(page).inputValue(), '122');
  await page.getByText('有未保存修改', {exact: true}).waitFor(); assert.equal(await page.getByRole('button', {name: '核对后沿用草稿'}).count(), 0);
  assert.equal(await page.locator('.sm-config-row').filter({hasText: '备份检查间隔'}).getByText('已存值：121', {exact: true}).count(), 1);
  passed('late-old-read-cannot-overwrite-new-baseline-or-new-edit');

  await resetPage(page); await interval(page).fill('121'); await save(page).click();
  await page.getByRole('button', {name: '确认结果', exact: true}).waitFor();
  await hold(page, 'leave-tab'); await acknowledge(page); await held(page, 'leave-tab');
  await page.getByRole('button', {name: 'overview', exact: true}).click(); await flush(page);
  assert(await page.evaluate(() => window.configSavedNetwork.held['leave-tab'].signal.aborted));
  await externalSave(page, {auto_backup_interval_minutes: 122}); await release(page, 'leave-tab');
  await page.getByRole('button', {name: 'config', exact: true}).click(); await settled(page); await conflict(page, 121);
  passed('leaving-tab-aborts-read-and-return-keeps-draft-against-real-later-save');

  await resetPage(page); await interval(page).fill('121'); await save(page).click();
  await page.getByRole('button', {name: '确认结果', exact: true}).waitFor();
  await page.getByRole('button', {name: 'overview', exact: true}).click(); await flush(page);
  const reads = report.requests.filter(row => row.path.endsWith('/config')).length;
  await acknowledge(page); await flush(page);
  assert.equal(report.requests.filter(row => row.path.endsWith('/config')).length, reads);
  await page.getByRole('button', {name: 'config', exact: true}).click(); await ready(page); await clean(page, 121);
  passed('acknowledging-on-other-tab-defers-read-until-config-is-active');

  await resetPage(page); await interval(page).fill('121');
  await page.evaluate(() => window.configSavedProbe.setSource('sample')); await flush(page);
  const sampleReads = report.requests.length; await page.evaluate(() => window.configSavedProbe.bump()); await flush(page);
  assert.equal(report.requests.length, sampleReads);
  await page.evaluate(() => window.configSavedProbe.setSource('current')); await settled(page); await conflict(page, 121);
  passed('sample-source-suspends-reads-without-dropping-draft');

  await resetPage(page); await externalSave(page, {auto_backup_interval_minutes: 122});
  await page.evaluate(() => {
    const input = document.querySelector('#sm-maintenance-auto_backup_interval_minutes');
    ReactDOM.flushSync(() => {
      window.configSavedProbe.bump();
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, '121');
      input.dispatchEvent(new Event('input', {bubbles: true}));
    });
  });
  await settled(page); await conflict(page, 121);
  passed('same-turn-local-edit-and-revision-do-not-overwrite-draft');

  await resetPage(page); await interval(page).fill('121'); await save(page).click();
  await page.getByRole('button', {name: '确认结果', exact: true}).waitFor();
  const intent = await pending(page); await hold(page, 'pending-read');
  await page.evaluate(() => window.configSavedProbe.bump()); await held(page, 'pending-read');
  await release(page, 'pending-read'); await clean(page, 121);
  assert(await interval(page).isDisabled()); assert(await save(page).isDisabled()); assert.deepEqual(await pending(page), intent);
  passed('delayed-equal-read-while-receipt-unconfirmed-never-unlocks');
  await acknowledge(page); await ready(page); await clean(page, 121);
};
