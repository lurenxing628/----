'use strict';
const assert = require('node:assert/strict');
const b = (scope, name) => (name === '关闭' ? scope.locator('.modal-f') : scope).getByRole('button', {name, exact: true});
async function materialWrites(p, page, data) {
  const area = page.locator('[data-resource-workspace]');
  const row = () => p.oracle().tables.Materials.find(r => r.material_id === data.material);
  const original = row();
  const open = async () => { await p.click(b(area, data.material)); await page.getByRole('dialog', {name: '物料详情', exact: true}).locator('.wb-resource-stock').waitFor(); };
  await open(); await p.click(b(page.getByRole('dialog', {name: '物料详情', exact: true}), '编辑'));
  let d = page.getByRole('dialog', {name: '编辑物料', exact: true});
  await p.type(d.locator('input[name="label"]'), '');
  await p.click(b(d, '保存')); await d.getByRole('alert').first().waitFor();
  assert.deepEqual(row(), original); await p.shot('material-invalid-name-no-write');
  const label = '已编辑长中文材料名称与库存范围核对-' + p.state + '-原备注保持不变';
  await p.type(d.locator('input[name="label"]'), label);
  await p.type(d.getByLabel('规格', {exact: true}), '直径125毫米/长度860毫米/此次只改单条材料规格');
  await p.click(d.getByLabel(/^状态/)); await page.getByRole('listbox').waitFor(); await p.shot('material-edit-status-dropdown');
  await p.click(page.getByRole('listbox').getByRole('option', {name: '停用', exact: true}));
  await p.select(d.getByLabel(/^状态/), '启用');
  await p.shot('material-edited-before-save');
  const response = await p.response('/update', () => p.click(b(d, '保存')));
  assert.equal(response.result, 'committed');
  await d.getByText('已刷新到最新数据。', {exact: true}).waitFor();
  const current = row(); assert.equal(current.name, label); assert.equal(current.remark, original.remark); assert.equal(current.stock_qty, 0);
  for (const key of Object.keys(original)) if (!['name', 'spec'].includes(key)) assert.deepEqual(current[key], original[key], key);
  await p.shot('material-real-save-receipt'); await p.click(b(d, '关闭'));
  assert.equal(await area.getByRole('searchbox').inputValue(), data.material_prefix);
  assert.equal(await area.locator('select[aria-label="状态筛选"]').inputValue(), 'active');
  const scope = await area.locator('.pager').innerText().catch(() => area.innerText());
  p.report.material_return = p.report.material_return || [];
  p.report.material_return.push({state: p.state, search_preserved: true, status_preserved: true, page_after_save: scope.match(/第\s*(\d+)\s*\//)?.[1], original_page: 2});
  if (!await b(area, data.material).count()) { await p.click(b(area, '下一页')); await b(area, data.material).waitFor(); }
  await open(); await p.click(b(page.getByRole('dialog', {name: '物料详情', exact: true}), '调整库存'));
  d = page.getByRole('dialog', {name: '调整库存', exact: true});
  const stock = d.getByLabel(/^调整后库存/);
  await p.type(stock, ''); await p.click(b(d, '保存')); await d.getByRole('alert').first().waitFor();
  assert.equal(row().stock_qty, 0); await p.shot('material-empty-stock-rejected');
  await p.type(stock, '12.375');
  await p.click(d.getByRole('button', {name: /^增加调整后库存/})); assert.equal(await stock.inputValue(), '13.375');
  await p.click(d.getByRole('button', {name: /^减少调整后库存/})); assert.equal(await stock.inputValue(), '12.375');
  await p.shot('material-stock-with-unit');
  const session = await page.context().newCDPSession(page);
  try {
    p.intentionalNetworkFault = true;
    await session.send('Fetch.enable', {patterns: [{urlPattern: '*entities/material/*/update', requestStage: 'Response'}]});
    const wait = new Promise(resolve => session.once('Fetch.requestPaused', resolve));
    await p.click(b(d, '保存')); const headers = await wait;
    assert.equal(headers.responseStatusCode, 200);
    const body = JSON.parse(headers.request.postData), key = body.request_key;
    await session.send('Network.enable');
    await session.send('Network.emulateNetworkConditions', {offline: true, latency: 0, downloadThroughput: -1, uploadThroughput: -1});
    await session.send('Fetch.failRequest', {requestId: headers.requestId, errorReason: 'ConnectionReset'});
    await session.send('Fetch.disable');
    await b(d, '查询结果').waitFor();
    const receipt = p.oracle().tables.WorkbenchCommandReceipts.find(r => r.request_key === key);
    assert(receipt); assert.equal(row().stock_qty, 12.375);
    await p.shot('material-pending-original-request');
    await session.send('Network.emulateNetworkConditions', {offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1});
    const reloaded = p.state === '1392-dark';
    if (reloaded) {
      await session.send('Fetch.enable', {patterns: [{urlPattern: '*commands/*', requestStage: 'Request'}]});
      const automatic = new Promise(resolve => session.once('Fetch.requestPaused', resolve));
      p.step('browser-reload', 'original pending material request', key);
      await page.reload({waitUntil: 'domcontentloaded'});
      const lookup = await automatic; assert(new URL(lookup.request.url).pathname.endsWith('/commands/' + key));
      await session.send('Fetch.failRequest', {requestId: lookup.requestId, errorReason: 'ConnectionReset'}); await session.send('Fetch.disable');
      d = page.getByRole('dialog', {name: '上次操作结果', exact: true}); await b(d, '查询结果').waitFor();
      await p.shot('material-reloaded-pending-original-key');
    }
    const recovered = await p.response('/commands/' + key, () => p.click(b(d, '查询结果')));
    assert.equal(recovered.receipt_ref, receipt.receipt_ref);
    await d.getByText(reloaded ? '保存已完成。' : '已刷新到最新数据。', {exact: true}).waitFor();
    assert.deepEqual(p.oracle().tables.WorkbenchCommandReceipts.filter(r => r.request_key === key), [receipt]);
    const requests = p.report.network.filter(r => r.event === 'request' && r.post && JSON.parse(r.post).request_key === key);
    assert.equal(requests.length, 1); assert.deepEqual(body.input, {fields: {stock_qty: 12.375}});
    p.report.recoveries = (p.report.recoveries || []).concat({state: p.state, request_key: key, receipt_ref: receipt.receipt_ref,
      write_requests: 1, reloaded, actual_input: body.input, method: 'CDP drops actual server 200 response with ConnectionReset; no mocked response or API write'});
    const after = row(); for (const k of Object.keys(current)) if (k !== 'stock_qty') assert.deepEqual(after[k], current[k], k);
    await p.shot('material-recovered-original-receipt'); await p.click(b(d, '关闭'));
  } finally { await session.send('Fetch.disable'); await session.send('Network.emulateNetworkConditions', {offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1}); await session.detach(); p.intentionalNetworkFault = false; }
}
module.exports = {materialWrites};
