'use strict';
const assert = require('node:assert/strict');
const path = require('node:path');

async function recoverReceipt({p, page, processArea, kind, file}) {
  const label = kind === 'route' ? '工艺路线' : '工时定额';
  const b = (scope, name) => scope.getByRole('button', {name, exact: true});
  const dialog = () => page.getByRole('dialog', {name: '导入' + label, exact: true});
  await p.click(b(processArea(), '导入' + label));
  await p.click(b(dialog(), file.endsWith('.csv') ? 'CSV (.csv)' : 'Excel (.xlsx)'));
  p.step('setInputFiles', 'input[type=file]', file);
  await dialog().locator('input[type=file]').setInputFiles(path.join(p.root, 'uploads', file));
  await p.response('/process-files/' + kind + '/preview', () => p.click(b(dialog(), '开始预检')));
  const ack = dialog().getByRole('checkbox', {name: /已核对全部修改前后内容/});
  if (await ack.count()) await p.click(ack);
  const endpoint = '/api/workbench/v1/process-files/' + kind + '/confirm';
  const writePattern = '**' + endpoint, lookupPattern = '**/api/workbench/v1/commands/**';
  const context = page.context(), started = p.report.network.length;
  let unavailable = true, observed = null, dropped = false, injectionError = null;
  const lookupFault = route => unavailable ? route.abort('failed') : route.continue();
  async function responseFault(route) {
    if (dropped) { injectionError = new Error('Unexpected repeated write during receipt recovery'); await route.abort('failed'); return; }
    dropped = true;
    try {
      const request = route.request().postDataJSON();
      const response = await route.fetch();
      assert.equal(response.status(), 200);
      const receipt = await response.json(); assert(['committed', 'unchanged'].includes(receipt.result));
      const stored = p.oracle().tables.WorkbenchCommandReceipts.find(row => row.request_key === request.request_key);
      assert(stored); assert.equal(stored.receipt_ref, receipt.receipt_ref);
      observed = {request_key: request.request_key, receipt, stored, actual_request: request};
      p.step('drop-real-committed-response', endpoint, {request_key: request.request_key, receipt_ref: receipt.receipt_ref});
    } catch (error) { injectionError = error; }
    await route.abort('failed');
  }
  try {
    p.intentionalNetworkFault = true;
    await context.route(lookupPattern, lookupFault); await context.route(writePattern, responseFault);
    await p.click(b(dialog(), '确认导入'));
    await b(dialog(), '查询原请求回执').waitFor();
    if (injectionError) throw injectionError;
    assert(observed && dropped);
    await p.shot('dropped-original-' + kind + '-pending');
    p.step('reload', 'actual workbench', {request_key: observed.request_key});
    await page.reload(); await b(dialog(), '查询原请求回执').waitFor();
    await p.shot('F5-original-' + kind + '-pending');
    unavailable = false;
    p.step('restore-receipt-network', lookupPattern, {request_key: observed.request_key});
    const receipt = await p.response('/commands/' + observed.request_key, () => p.click(b(dialog(), '查询原请求回执')));
    assert.equal(receipt.receipt_ref, observed.stored.receipt_ref); assert(['committed', 'unchanged'].includes(receipt.result));
    await dialog().getByText(kind === 'hours' ? '已核实原文件回执；导入不代替工时阶段的人工确认。'
      : '已取得原文件请求的完成回执，工艺确认状态以重新读取的详情为准。', {exact: true}).waitFor();
    await p.shot('recovered-original-' + kind + '-receipt');
    const writes = p.report.network.slice(started).filter(row => row.event === 'request' && new URL(row.url).pathname === endpoint);
    assert.equal(writes.length, 1); assert.equal(JSON.parse(writes[0].post).request_key, observed.request_key);
    assert.deepEqual(p.oracle().tables.WorkbenchCommandReceipts.filter(row => row.request_key === observed.request_key), [observed.stored]);
    p.report.recoveries = p.report.recoveries || [];
    p.report.recoveries.push({kind, request_key: observed.request_key, receipt_ref: receipt.receipt_ref,
      write_requests: writes.length, actual_request: observed.actual_request, actual_server_response: observed.receipt, response: receipt,
      method: 'Original browser request forwarded with route.fetch to real server, committed response discarded; original lookup blocked, F5, real lookup restored; no fulfill or synthetic API data'});
    await p.click(b(dialog(), '完成')); await dialog().waitFor({state: 'detached'});
    const resume = b(page, '继续原导航');
    if (await resume.isVisible()) { await p.click(resume); await processArea().locator('.wb-table[aria-busy="false"]').waitFor(); }
  } finally {
    unavailable = false;
    await context.unroute(writePattern, responseFault); await context.unroute(lookupPattern, lookupFault);
    p.intentionalNetworkFault = false;
  }
}

module.exports = {recoverReceipt};
