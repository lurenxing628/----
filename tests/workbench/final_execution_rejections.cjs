'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path');
const { run } = require('./final_execution_browser_support.cjs');

async function exercise(p) {
  const { page } = p, ref = p.ready.expected.final_e.task_refs['1'];
  const endpoint = '/execution/tasks/' + ref + '/reports';
  await p.read(() => page.locator('.sidebar a[href$="?view=field"]').click(), '/execution/tasks');
  await p.read(() => page.locator('[data-field-task="' + ref + '"] button[aria-expanded]').click(), '/execution/tasks/' + ref);
  await page.getByRole('button', { name: '新增本次报工', exact: true }).click();
  const quantity = page.getByLabel('本次完成数量', { exact: true });
  const start = page.getByLabel('实际开工', { exact: true }), end = page.getByLabel('本次实际完工', { exact: true });
  const hours = page.getByLabel('有效工时 (h)', { exact: true });
  for (const [label, startValue, endValue, quantityValue, hoursValue, status, invalidField, message] of [
    ['future', '2099-01-01T08:00', '2099-01-01T10:00', '2', '1', 422],
    ['reversed', '2026-09-02T08:00', '2026-09-02T07:00', '2', '0', 422, '本次实际完工', '本次实际完工不能早于实际开工。'],
    ['hours-exceed-span', '2026-09-02T08:00', '2026-09-02T10:00', '2', '3', 422, '有效工时 (h)', '有效工时不能超过本次实际起止跨度。'],
    ['overreport', '2026-09-02T08:00', '2026-09-02T10:00', '11', '1', 409]
  ]) {
    await p.step(['WBP-FIELD-018', 'WBP-FIELD-010.A006'], label + '-real-rejection-retains-editable-draft', async () => {
      await quantity.fill(quantityValue); await start.fill(startValue); await end.fill(endValue); await hours.fill(hoursValue);
      if (invalidField) {
        const posted = p.report.requests.filter(request => request.method === 'POST').length;
        await page.getByRole('button', { name: '保存报工', exact: true }).click();
        await page.locator('.field-editor').getByText(message, { exact: true }).waitFor();
        const invalid = page.getByLabel(invalidField, { exact: true });
        assert.equal(await invalid.getAttribute('aria-invalid'), 'true');
        assert(await invalid.evaluate(node => document.activeElement === node));
        assert.equal(p.report.requests.filter(request => request.method === 'POST').length, posted);
        p.report.client_rejections = [...(p.report.client_rejections || []), { case: label, message,
          no_post: true, focused_field: invalidField, http_contract: 'test_real_http_rejections_and_current_zero_overlap_contract' }];
      } else {
        const result = await p.read(() => page.getByRole('button', { name: '保存报工', exact: true }).click(), endpoint, status);
        assert.equal(result.committed, false);
        await page.locator('.field-editor').getByRole('alert').filter({ hasText: result.error.message }).waitFor();
        p.report.post_cases = [...(p.report.post_cases || []), label];
      }
      assert.equal(await quantity.inputValue(), quantityValue); assert.equal(await start.inputValue(), startValue);
      assert.equal(await end.inputValue(), endValue); assert.equal(await hours.inputValue(), hoursValue);
      assert.equal(await quantity.isDisabled(), false);
      await p.shot(label + '-draft-preserved');
    });
  }
  await p.step(['WBP-FIELD-010.A006', 'WBP-FIELD-018.A008'], 'actual-sql-abort-preserves-pending-original-and-no-duplicate-post', async () => {
    await quantity.fill('2'); await start.fill('2026-09-02T08:00'); await end.fill('2026-09-02T10:00'); await hours.fill('1');
    const result = await p.read(() => page.getByRole('button', { name: '保存报工', exact: true }).click(), endpoint, 500);
    assert.equal(result.committed, 'unknown');
    await page.getByText('结果待核实，已保留原请求。', { exact: false }).waitFor();
    const posted = p.report.requests.filter(request => request.method === 'POST' && request.url.endsWith(endpoint));
    p.report.post_cases.push('sql-abort');
    assert.deepEqual(p.report.post_cases, ['future', 'overreport', 'sql-abort']);
    assert.deepEqual(p.report.client_rejections.map(row => row.case), ['reversed', 'hours-exceed-span']);
    assert.equal(posted.length, 3);
    p.report.pending_request_key = JSON.parse(posted[2].body).request_key;
    assert.equal(await quantity.inputValue(), '2'); assert.equal(await hours.inputValue(), '1');
    assert.equal(await quantity.isDisabled(), true);
    const checked = await p.read(() => page.getByRole('button', { name: '核实原请求', exact: true }).click(),
      '/commands/' + p.report.pending_request_key);
    assert.equal(checked.state, 'not_recorded'); assert.equal(checked.may_be_in_flight, true);
    assert.equal(p.report.requests.filter(request => request.method === 'POST').length, 3);
    await p.shot('sql-abort-original-pending');
  });
  await p.step(['WBP-FIELD-010.A006'], 'real-restart-keeps-unknown-command-without-automatic-post', async () => {
    fs.writeFileSync(path.join(p.ready.root, 'rejection-restart-request.json'), JSON.stringify({ request_key: p.report.pending_request_key }));
    const resumed = path.join(p.ready.root, 'rejection-restart-complete.json'), deadline = Date.now() + 100000;
    while (!fs.existsSync(resumed)) { assert(Date.now() < deadline, 'Owned server restart timed out'); await new Promise(resolve => setTimeout(resolve, 50)); }
    assert.equal(JSON.parse(fs.readFileSync(resumed, 'utf8')).url, p.ready.url);
    const previousRequests = p.report.requests.length;
    await page.reload(); await page.locator('[data-field-workspace]').waitFor();
    const button = page.getByRole('button', { name: '核实原请求', exact: true });
    await page.waitForFunction(() => [...document.querySelectorAll('button')].some(node => node.textContent.includes('核实原请求') && !node.disabled));
    const checked = await p.read(() => button.click(), '/commands/' + p.report.pending_request_key);
    assert.equal(checked.state, 'not_recorded'); assert.equal(checked.may_be_in_flight, true);
    p.report.after_restart_requests = p.report.requests.slice(previousRequests);
    assert(p.report.after_restart_requests.every(request => request.method === 'GET'));
    assert(p.report.after_restart_requests.filter(request => request.url.endsWith('/commands/' + p.report.pending_request_key)).length >= 2);
    await p.shot('pending-original-no-resubmit');
  });
}
run('rejections', exercise, { once: true });
