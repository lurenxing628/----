'use strict';
const assert = require('node:assert/strict');
const key = '__final_planning_private_quota__';

async function fillNativeStorage(page) {
  return page.evaluate(key => {
    if (localStorage.getItem(key) !== null) throw new Error('Private quota key already exists');
    const before = Object.keys(localStorage).sort().map(name => [name, localStorage.getItem(name)]);
    let low = 0, high = 8 * 1024 * 1024, failures = 0;
    function attempt(size) {
      try { localStorage.setItem(key, 'x'.repeat(size)); return true; }
      catch (error) { if (error.name !== 'QuotaExceededError') throw error; failures++; return false; }
    }
    if (attempt(high)) { localStorage.removeItem(key); throw new Error('Native quota not reached within the bounded private fixture'); }
    while (low + 1 < high) { const middle = Math.floor((low + high) / 2); if (attempt(middle)) low = middle; else high = middle; }
    if (!attempt(low) || attempt(low + 1)) throw new Error('Native quota boundary is inconsistent');
    return { key, characters: low, native_error: 'QuotaExceededError', failures, before };
  }, key);
}

async function releaseNativeStorage(page, quota) {
  const after = await page.evaluate(key => {
    localStorage.removeItem(key);
    return Object.keys(localStorage).sort().map(name => [name, localStorage.getItem(name)]);
  }, key);
  assert.deepEqual(after, quota.before, 'Only the private quota key may be changed');
}

async function candidateStorageFailure(page, report, h, flush) {
  await h.action(['WBP-PLAN-004.storage-failure'], async () => {
    const before = report.requests.length;
    await h.button('采用方案', page.locator('[data-run-adoption-action]')).click();
    const dialog = page.getByRole('dialog', { name: '确认正式采用', exact: true });
    await dialog.getByLabel('采用原因', { exact: true }).fill('Private native storage failure');
    await dialog.getByLabel('声明人', { exact: true }).fill('D acceptance');
    await dialog.getByRole('checkbox').check();
    const quota = await fillNativeStorage(page);
    try {
      await h.button('确认正式采用', dialog).click();
      await dialog.getByText('无法保存采用恢复记录，未开始新的采用，请保留当前页面。', { exact: true }).waitFor();
      assert(await h.button('确认正式采用', dialog).isDisabled());
      assert.equal(await dialog.getByLabel('采用原因', { exact: true }).inputValue(), 'Private native storage failure');
      assert.equal(await page.evaluate(() => localStorage.getItem('aps_workbench_candidate_adoption_pending_v1')), null);
      await h.shot('candidate-native-storage-refused');
    } finally { await releaseNativeStorage(page, quota); }
    await h.button('重读恢复记录', dialog).click(); await flush();
    await h.button('取消', dialog).click(); await dialog.waitFor({ state: 'hidden' });
    assert(!report.requests.slice(before).some(row => row.method === 'POST' && row.url.endsWith('/adopt')));
    report.candidate_native_storage = { ...quota, no_adoption_sent: true };
  });
}

async function trialStorageFailure(page, report, h, flush) {
  await h.action(['WBP-TRIAL-012.storage-failure'], async () => {
    await h.selectTrial(20, 'item-B');
    const detail = page.getByRole('complementary', { name: '工序详情', exact: true });
    await h.button('调整此工序', detail).click();
    await page.getByLabel('调整开工', { exact: true }).fill('2026-09-09T13:15');
    const before = report.requests.length, quota = await fillNativeStorage(page);
    try {
      await h.button('保存调整', detail).click();
      await page.getByText('无法保存试调请求恢复记录，本次未发送。', { exact: true }).first().waitFor();
      assert.equal(await page.getByLabel('调整开工', { exact: true }).inputValue(), '2026-09-09T13:15');
      assert.equal(await page.evaluate(() => localStorage.getItem('aps_workbench_trial_pending_v1')), null);
      assert(await h.button('保存调整', detail).isDisabled());
      await h.shot('trial-native-storage-refused');
    } finally { await releaseNativeStorage(page, quota); }
    await h.button('取消编辑', detail).click();
    const discard = page.getByRole('dialog', { name: '离开前确认', exact: true });
    await discard.getByText('试调工序的设备、人员或开工调整尚未保存。', { exact: true }).waitFor();
    await h.button('留在当前页面', discard).click(); await discard.waitFor({ state: 'hidden' });
    assert.equal(await page.getByLabel('调整开工', { exact: true }).inputValue(), '2026-09-09T13:15');
    assert.equal(await page.locator('[data-trial-workspace]').getAttribute('data-open-ref'), report.draft_ref);
    await h.shot('trial-native-storage-leave-refused');
    await h.button('取消编辑', detail).click();
    await h.button('放弃未保存内容并继续', discard).click(); await discard.waitFor({ state: 'hidden' });
    assert.equal(await page.getByLabel('调整开工', { exact: true }).count(), 0);
    await h.button('重读恢复记录与当前内容').click(); await flush();
    assert(report.requests.slice(before).every(row => row.method === 'GET'));
    const latest = h.last(row => row.draft_ref === report.draft_ref && row.tasks);
    const task = latest.tasks.find(row => row.sequence === 20 && row.piece_id === 'item-B');
    const original = report.original_draft.tasks.find(row => row.task_ref === task.task_ref);
    assert.equal(task.start, original.start); assert.equal(task.end, original.end);
    assert(!await h.button('调整此工序', detail).isDisabled());
    report.trial_native_storage = { ...quota, no_change_sent: true };
  });
}
module.exports = { candidateStorageFailure, trialStorageFailure };
