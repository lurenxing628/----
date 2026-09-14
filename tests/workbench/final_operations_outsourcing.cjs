'use strict';
const { lifecycle } = require('./final_operations_dashboard.cjs');

async function outsourcing(h) {
  const { page, mark, request, select, shot, category, assert, report } = h;
  await h.dashboard(); await category('外协回厂');
  const dialog = () => page.getByRole('dialog');
  await mark('WBP-DASH-009.open-registration', () => request('/outsourcing/targets', () => page.getByRole('button', { name: '新增外协登记', exact: true }).click()));
  await mark('WBP-DASH-010.cancel', () => dialog().getByRole('button', { name: '取消', exact: true }).click());
  await request('/outsourcing/targets', () => page.getByRole('button', { name: '新增外协登记', exact: true }).click());
  await dialog().getByLabel('选择工序 XB1-10', { exact: true }).check();
  await dialog().getByLabel('外协经办人', { exact: true }).fill('F shipping clerk');
  await dialog().getByLabel('外协核实原因', { exact: true }).fill('F dispatch handover verified');
  async function invalid(id) {
    await mark('WBP-DASH-010.' + id, async () => { await dialog().getByRole('button', { name: '预检核对', exact: true }).click(); await dialog().getByRole('alert').waitFor(); });
  }
  await invalid('reject-missing-sent');
  await dialog().getByLabel('实际发出', { exact: true }).fill('2026-09-07T09:00:17'); await invalid('reject-missing-planned');
  await dialog().getByLabel('计划回厂', { exact: true }).fill('2026-09-06T12:00'); await invalid('reject-reverse');
  await dialog().getByLabel('实际发出', { exact: true }).fill('2099-01-01T09:00');
  await dialog().getByLabel('计划回厂', { exact: true }).fill('2099-01-02T12:00');
  await mark('WBP-DASH-010.reject-future-sent', () => request('/outsourcing/receipts/preview', () => dialog().getByRole('button', { name: '预检核对', exact: true }).click(), 422, 'POST'));
  await dialog().getByLabel('实际发出', { exact: true }).fill('2026-09-07T09:00:17');
  await dialog().getByLabel('计划回厂', { exact: true }).fill('2026-09-09T12:00');
  await dialog().getByLabel('实际回厂', { exact: true }).fill('2099-01-01T09:00'); await select('外协确认状态', '已回厂');
  await mark('WBP-DASH-010.reject-future-return', () => request('/outsourcing/receipts/preview', () => dialog().getByRole('button', { name: '预检核对', exact: true }).click(), 422, 'POST'));
  await dialog().getByRole('button', { name: '清除实际回厂', exact: true }).click();
  await select('外协确认状态', '已回厂'); await invalid('reject-state-time'); await select('外协确认状态', '在途');
  async function commit(id) {
    const preview = await mark('WBP-DASH-010.preview', () => request('/outsourcing/receipts/preview', () => dialog().getByRole('button', { name: '预检核对', exact: true }).click(), 200, 'POST'));
    await shot(id + '-preview');
    const receipt = await mark('WBP-DASH-010.' + (id === 'create' ? 'save' : 'correct'), () => request('/outsourcing/receipts', () => dialog().getByRole('button', { name: '确认保存外协登记', exact: true }).click(), 200, 'POST'));
    assert.equal(receipt.data.execution.automatically_reported, false);
    await dialog().getByText('外协登记已完成。回厂不等于工序完工。', { exact: true }).waitFor();
    await mark('WBP-DASH-010.original-receipt', () => request('/outsourcing/receipts', () => dialog().getByRole('button', { name: '完成', exact: true }).click()));
    report.outsourcing.push({ preview, receipt }); return receipt.data.outsourcing_ref;
  }
  const ref = await commit('create');
  await lifecycle(h, 'external', '外协回厂');
  await page.locator('[data-detail-ref]').getByRole('button', { name: '外协物流登记', exact: true }).click();
  await page.locator('[data-dashboard-outsourcing]').waitFor(); assert.equal(await page.locator('.wb-current-plan').count(), 0);
  await mark('WBP-DASH-014.return-context', () => page.getByRole('button', { name: '返回值班台条目', exact: true }).click());
  await page.locator('[data-detail-ref]').waitFor(); await page.locator('.wb-current-plan').waitFor();
  await category('外协回厂');
  for (const [choice, id] of [['待回厂', 'awaiting'], ['超期未回', 'overdue']]) {
    const data = await mark('WBP-DASH-009.filter-' + id, () => request('/outsourcing/receipts', () => select('外协登记筛选', choice))); assert.equal(data.data.page.total, 1);
  }
  await request('/outsourcing/receipts', () => select('外协登记筛选', '全部登记'));
  async function edit() {
    const region = page.locator('[data-outsourcing-detail="' + ref + '"]');
    const row = page.locator('[data-outsourcing-ref="' + ref + '"]'); await row.waitFor();
    if (await row.getAttribute('data-selected') !== 'true') await request('/outsourcing/receipts/' + ref + '/history', () => row.getByRole('button').click());
    await region.waitFor();
    await region.getByRole('button', { name: '核实 / 更正登记', exact: true }).click();
    await dialog().getByLabel('外协经办人', { exact: true }).fill('F receiving clerk');
  }
  await edit(); await dialog().getByLabel('实际回厂', { exact: true }).fill('2026-09-10T10:00:27'); await select('外协确认状态', '已回厂');
  await dialog().getByLabel('外协核实原因', { exact: true }).fill('F physical receipt verified, no completion report'); await commit('return');
  await edit(); await dialog().getByLabel('计划回厂', { exact: true }).fill('2026-09-11T12:00');
  await dialog().getByLabel('外协核实原因', { exact: true }).fill('F planned return corrected, original actual receipt retained'); await commit('correction');
  const returned = await mark('WBP-DASH-009.filter-returned', () => request('/outsourcing/receipts', () => select('外协登记筛选', '已回厂')));
  assert.equal(returned.data.page.total, 1); assert.equal(returned.data.items[0].returned, '2026-09-10T10:00:27');
  await shot('outsourcing-returned');
  await page.reload(); await category('外协回厂');
  await request('/outsourcing/receipts/' + ref + '/history', () => page.locator('[data-outsourcing-ref="' + ref + '"]').getByRole('button').click());
  assert.equal(await page.locator('[data-fact-ref]').count(), 3); await page.locator('[data-fact-ref]').first().locator(':scope > summary').click();
  await mark('WBP-DASH-009.tracking-basis', async () => { await page.locator('[data-outsourcing-detail]').waitFor(); });
  await shot('outsourcing-history');
  report.outsourcing_ref = ref;
}
module.exports = { outsourcing };
