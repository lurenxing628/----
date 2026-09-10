'use strict';
const assert = require('node:assert/strict');
const {openProcess, processPage} = require('./ed_material_process_stages.cjs');
const b = (scope, name) => (name === '关闭' ? scope.locator('.modal-f') : scope).getByRole('button', {name, exact: true});
async function detailStates(p, page, data) {
  await page.goto(p.ready.url + '/workbench?view=process');
  const area = page.locator('[data-resource-workspace]');
  await area.getByRole('searchbox').waitFor();
  await p.type(area.getByRole('searchbox'), data.empty_material);
  await p.response('/entities/material', () => p.click(b(area, '搜索')));
  const session = await page.context().newCDPSession(page);
  try {
    await session.send('Fetch.enable', {patterns: [{urlPattern: '*entities/material/*', requestStage: 'Response'}]});
    const waiting = new Promise(resolve => session.once('Fetch.requestPaused', resolve));
    await p.click(b(area, data.empty_material)); const response = await waiting;
    const d = page.getByRole('dialog', {name: '物料详情', exact: true});
    await d.getByText('正在读取详情…', {exact: true}).waitFor();
    assert.equal(await d.locator('.wb-resource-identity').count(), 0); await p.shot('material-cold-no-fabricated-values');
    await session.send('Fetch.continueRequest', {requestId: response.requestId}); await session.send('Fetch.disable');
    await d.locator('.wb-resource-stock').waitFor();
    assert.equal(await d.locator('.wb-resource-stock').innerText(), '0\n单位未填写');
    await p.shot('material-null-unit-spec-remark'); await p.click(b(d, '关闭'));
    p.intentionalNetworkFault = true;
    await session.send('Network.enable');
    await session.send('Network.emulateNetworkConditions', {offline: true, latency: 0, downloadThroughput: -1, uploadThroughput: -1});
    await p.click(b(area, data.empty_material)); await d.getByRole('alert').first().waitFor();
    assert.equal(await d.locator('.wb-resource-identity').count(), 0); assert.equal(await b(d, '编辑').count(), 0);
    await p.shot('material-detail-network-error-no-edit');
    await session.send('Network.emulateNetworkConditions', {offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1});
    await p.click(b(d, '重新读取')); await d.locator('.wb-resource-stock').waitFor(); await p.shot('material-error-real-retry');
    await p.click(b(d, '关闭')); p.intentionalNetworkFault = false;
    await p.type(area.getByRole('searchbox'), 'ED物料不存在的筛选范围'); await p.response('/entities/material', () => p.click(b(area, '搜索')));
    assert.equal(await area.getByRole('table', {name: '物料列表'}).locator('tbody tr input[type="checkbox"]').count(), 0);
    await p.shot('material-empty-search');
    await processPage(p, page);
    const process = page.locator('[data-process-workspace]');
    await p.type(process.getByRole('searchbox'), data.part); await p.response('/entities/part', () => process.getByRole('searchbox').press('Enter'));
    await session.send('Fetch.enable', {patterns: [{urlPattern: '*entities/part/*', requestStage: 'Response'}]});
    const pending = new Promise(resolve => session.once('Fetch.requestPaused', resolve));
    await p.click(b(process, '查看 ' + data.part)); const detail = await pending;
    await page.getByText('正在读取工艺详情…', {exact: true}).waitFor(); await p.shot('process-cold-no-values');
    await session.send('Fetch.continueRequest', {requestId: detail.requestId}); await session.send('Fetch.disable');
    await page.getByRole('tablist', {name: '零件工艺步骤'}).waitFor(); await p.click(b(page, '关闭详情'));
    p.intentionalNetworkFault = true;
    await session.send('Network.emulateNetworkConditions', {offline: true, latency: 0, downloadThroughput: -1, uploadThroughput: -1});
    await p.click(b(process, '查看 ' + data.part));
    await page.locator('.process-detail').getByRole('alert').waitFor(); await p.shot('process-detail-network-error');
    assert.equal(await page.getByRole('tablist', {name: '零件工艺步骤'}).count(), 0);
    await session.send('Network.emulateNetworkConditions', {offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1});
    await p.click(b(page, '重试读取详情')); await page.getByRole('tablist', {name: '零件工艺步骤'}).waitFor();
    await p.shot('process-error-real-retry'); await p.click(b(page, '关闭详情'));
  } finally {
    await session.send('Fetch.disable'); await session.send('Network.emulateNetworkConditions', {offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1});
    await session.detach(); p.intentionalNetworkFault = false;
  }
}
module.exports = {detailStates};
