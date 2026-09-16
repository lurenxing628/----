'use strict';
const assert = require('node:assert/strict');

module.exports = async function recoveryCases({ page, reset, accepted, control, refresh, startButton, state, local, report, caseDone }) {
  for (const legacy of [true, false]) {
    await reset(); const original = await accepted();
    await page.evaluate(legacy => {
      window.unmountRun();
      if (legacy) {
        const intent = RunJobAPI.pending().read();
        localStorage.setItem(RunJobAPI.PENDING_KEY, JSON.stringify({ input_ref: intent.input_ref, request_key: intent.request_key, run_ref: intent.run_ref }));
      }
      localStorage.setItem('fixture-unrelated-pending', 'keep');
    }, legacy);
    await control('restore_scope');
    await page.evaluate(() => window.mountRun(window.currentPreflight));
    await page.locator('[data-query-state="context_replaced"]').waitFor();
    assert.equal(await page.evaluate(() => RunJobAPI.pending().read()), null);
    assert.equal(await page.evaluate(() => localStorage.getItem('fixture-unrelated-pending')), 'keep');
    assert.equal((await local()).request_key, original.request_key);
    assert.equal(await startButton().isDisabled(), false);
    assert.equal((await control('release')).calls.length, 1);
    await page.reload(); await page.locator('[data-query-state="context_replaced"]').waitFor();
    assert.equal((await control('release')).calls.length, 1);
    caseDone(legacy ? 'legacy-pending-proven-by-registered-protection-copy' : 'v2-pending-proven-by-restore-generation');
  }

  await reset(); const running = await accepted(); await control('start', { run_ref: running.run_ref }); await refresh(); await state('running').waitFor();
  await page.evaluate(() => {
    window.fixtureNow = Date.now; window.fixtureDelay = RunJobAPI.pollDelay;
    window.fixtureOffset = 0; Date.now = () => fixtureNow() + fixtureOffset; RunJobAPI.pollDelay = () => 20;
  });
  try {
    await refresh(); await page.waitForResponse(r => r.url().includes('/scheduling/requests/'));
    await page.evaluate(() => { window.fixtureOffset = 61000; });
    await page.waitForResponse(r => r.url().includes('/scheduling/requests/'));
    assert.equal(await page.getByText('已暂停自动查询。', { exact: false }).count(), 0);
    assert.equal(await startButton().isDisabled(), true);
    assert.equal((await local()).request_key, running.request_key);
    caseDone('confirmed-long-running-job-keeps-querying-after-60-seconds');
  } finally { await page.evaluate(() => { Date.now = fixtureNow; RunJobAPI.pollDelay = fixtureDelay; }); }
  await control('release'); await refresh(); await state('complete').waitFor();

  await reset();
  await page.evaluate(() => {
    window.unmountRun();
    const intent = RunJobAPI.pending().begin(currentPreflight.input_ref, null, 'a'.repeat(64));
    window.unknownRecoveryKey = intent.request_key;
    window.fixtureNow = Date.now; window.fixtureDelay = RunJobAPI.pollDelay;
    window.fixtureOffset = 0; Date.now = () => fixtureNow() + fixtureOffset; RunJobAPI.pollDelay = () => 20;
    window.mountRun(currentPreflight);
  });
  try {
    await page.getByText('暂未查到这次排产记录', { exact: true }).waitFor();
    await page.evaluate(() => { window.fixtureOffset = 61000; });
    await page.getByText('已暂停自动查询。可点「查询结果」再次核对原记录。', { exact: true }).waitFor();
    const count = report.requests.filter(row => row.path.includes('/scheduling/requests/')).length;
    await new Promise(resolve => setTimeout(resolve, 150));
    assert.equal(report.requests.filter(row => row.path.includes('/scheduling/requests/')).length, count);
    assert.equal(await page.locator('[data-query-state="querying"]').count(), 0);
    assert.equal(await startButton().isDisabled(), true);
    assert.equal((await local()).request_key, await page.evaluate(() => unknownRecoveryKey));
    assert.equal((await control('release')).calls.length, 0);
    const response = page.waitForResponse(r => r.url().includes('/scheduling/requests/'));
    await refresh(); await response;
    assert.equal((await control('release')).calls.length, 0);
    caseDone('unresolved-pauses-after-60-seconds-manual-query-never-resubmits');
  } finally { await page.evaluate(() => { Date.now = fixtureNow; RunJobAPI.pollDelay = fixtureDelay; }); }
};
