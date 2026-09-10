'use strict';
const assert = require('node:assert/strict'), path = require('node:path');
async function recoverReceipt({p, page, processArea, kind, file}) {
  const label = kind === 'route' ? '工艺路线' : '工时定额', b = (scope, name) => scope.getByRole('button', {name, exact: true});
  await p.click(b(processArea(), '导入' + label)); const d = page.getByRole('dialog', {name: '导入' + label, exact: true});
  await p.click(b(d, file.endsWith('.csv') ? 'CSV (.csv)' : 'Excel (.xlsx)'));
  p.step('setInputFiles', 'input[type=file]', file); await d.locator('input[type=file]').setInputFiles(path.join(p.root, 'uploads', file));
  await p.response('/process-files/' + kind + '/preview', () => p.click(b(d, '开始预检')));
  const ack = d.getByRole('checkbox', {name: /已核对全部修改前后内容/}); if (await ack.count()) await p.click(ack);
  const session = await page.context().newCDPSession(page), endpoint = '/process-files/' + kind + '/confirm';
  const started = p.report.network.length;
  try {
    p.intentionalNetworkFault = true; p.step('browser-only-network-throttle', 'CDP Network', {downloadThroughput: 16});
    await session.send('Network.enable');
    await session.send('Network.emulateNetworkConditions', {offline: false, latency: 0, downloadThroughput: 16, uploadThroughput: -1});
    const headers = page.waitForResponse(r => new URL(r.url()).pathname.endsWith(endpoint));
    await p.click(b(d, '确认导入')); const response = await headers;
    assert.equal(response.status(), 200);
    const key = JSON.parse(response.request().postData()).request_key;
    p.step('browser-only-offline-after-real-200-headers', 'CDP Network', {request_key: key});
    await session.send('Network.emulateNetworkConditions', {offline: true, latency: 0, downloadThroughput: -1, uploadThroughput: -1});
    const pending = b(d, '查询原请求回执'); await pending.waitFor();
    const receiptBefore = p.oracle().tables.WorkbenchCommandReceipts.find(row => row.request_key === key);
    assert(receiptBefore, 'Server committed the original request before the browser disconnected');
    await p.shot('offline-original-' + kind + '-pending');
    await session.send('Network.emulateNetworkConditions', {offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1});
    p.step('browser-only-online', 'CDP Network');
    const receipt = await p.response('/commands/' + key, () => p.click(pending));
    assert.equal(receipt.receipt_ref, receiptBefore.receipt_ref);
    assert(['committed', 'unchanged'].includes(receipt.result));
    await d.getByText(/已取得原文件请求的完成回执/).waitFor(); await p.shot('recovered-original-' + kind + '-receipt');
    const writes = p.report.network.slice(started).filter(r => r.event === 'request' && new URL(r.url).pathname.endsWith(endpoint));
    assert.equal(writes.length, 1, 'Recovery queried the original receipt without replaying the write');
    const receiptAfter = p.oracle().tables.WorkbenchCommandReceipts.filter(row => row.request_key === key);
    assert.deepEqual(receiptAfter, [receiptBefore]);
    p.report.recoveries = p.report.recoveries || [];
    p.report.recoveries.push({kind, request_key: key, receipt_ref: receipt.receipt_ref, write_requests: writes.length,
      actual_request: JSON.parse(writes[0].post), response: receipt, method: 'real server + browser CDP offline, no API replacement'});
    await p.click(b(d, '完成'));
  } finally {
    await session.send('Network.emulateNetworkConditions', {offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1});
    await session.detach(); p.intentionalNetworkFault = false;
  }
}
module.exports = {recoverReceipt};
