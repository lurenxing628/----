'use strict';
const assert = require('node:assert/strict'), path = require('node:path');
async function recoverReceipt({p, page, processArea, kind, file}) {
  const label = kind === 'route' ? '工艺路线' : '工时定额', b = (scope, name) => scope.getByRole('button', {name, exact: true});
  await p.click(b(processArea(), '导入' + label)); const d = page.getByRole('dialog', {name: '导入' + label, exact: true});
  await p.click(b(d, file.endsWith('.csv') ? 'CSV (.csv)' : 'Excel (.xlsx)'));
  p.step('setInputFiles', 'input[type=file]', file); await d.locator('input[type=file]').setInputFiles(path.join(p.root, 'uploads', file));
  const preview = await p.response('/process-files/' + kind + '/preview', () => p.click(b(d, '开始预检')));
  assert.equal(await d.getByRole('checkbox', {name: /已核对全部修改前后内容/}).count(), 0);
  const session = await page.context().newCDPSession(page), endpoint = '/process-files/' + kind + '/confirm';
  const started = p.report.network.length;
  try {
    // Let the real server commit and answer 200, then drop that response in the browser (CDP Fetch at the response stage).
    // The earlier 16 B/s throttle made the 200 headers themselves take longer than the 15 s wait; this is deterministic.
    p.intentionalNetworkFault = true; p.step('browser-only-drop-real-200-response', 'CDP Fetch', endpoint);
    await session.send('Network.enable');
    await session.send('Fetch.enable', {patterns: [{urlPattern: '*' + endpoint, requestStage: 'Response'}]});
    const paused = new Promise(resolve => session.once('Fetch.requestPaused', resolve));
    await p.click(b(d, preview.data.zero_review_required ? '按 0 导入' : '确认导入')); const response = await paused;
    assert.equal(response.responseStatusCode, 200);
    const key = JSON.parse(response.request.postData).request_key;
    p.step('browser-only-offline-after-real-200-headers', 'CDP Network', {request_key: key});
    await session.send('Network.emulateNetworkConditions', {offline: true, latency: 0, downloadThroughput: -1, uploadThroughput: -1});
    await session.send('Fetch.failRequest', {requestId: response.requestId, errorReason: 'ConnectionReset'});
    await session.send('Fetch.disable');
    const pending = b(d, '查询结果'); await pending.waitFor();
    const receiptBefore = p.oracle().tables.WorkbenchCommandReceipts.find(row => row.request_key === key);
    assert(receiptBefore, 'Server committed the original request before the browser disconnected');
    await p.shot('offline-original-' + kind + '-pending');
    await session.send('Network.emulateNetworkConditions', {offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1});
    p.step('browser-only-online', 'CDP Network');
    const receipt = await p.response('/commands/' + key, () => p.click(pending));
    assert.equal(receipt.receipt_ref, receiptBefore.receipt_ref);
    assert(['committed', 'unchanged'].includes(receipt.result));
    // Completion copy after the recovered receipt (ProcessFileActions.jsx done status; glossary wording, 2026-09).
    await d.getByText(kind === 'hours' ? '导入已完成，请继续确认工时。' : '导入已完成，请刷新资料。', {exact: true}).waitFor();
    await p.shot('recovered-original-' + kind + '-receipt');
    const writes = p.report.network.slice(started).filter(r => r.event === 'request' && new URL(r.url).pathname.endsWith(endpoint));
    assert.equal(writes.length, 1, 'Recovery queried the original receipt without replaying the write');
    const receiptAfter = p.oracle().tables.WorkbenchCommandReceipts.filter(row => row.request_key === key);
    assert.deepEqual(receiptAfter, [receiptBefore]);
    p.report.recoveries = p.report.recoveries || [];
    p.report.recoveries.push({kind, request_key: key, receipt_ref: receipt.receipt_ref, write_requests: writes.length,
      actual_request: JSON.parse(writes[0].post), response: receipt, method: 'real server 200 dropped in the browser by CDP Fetch, then offline; no API replacement'});
    await p.click(b(d, '完成'));
  } finally {
    await session.send('Network.emulateNetworkConditions', {offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1});
    await session.detach(); p.intentionalNetworkFault = false;
  }
}
module.exports = {recoverReceipt};
