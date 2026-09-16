'use strict';
const assert = require('node:assert/strict');
const { run } = require('./final_execution_browser_support.cjs');

async function exercise(p, phase) {
  const { page, ready } = p, seed = ready.expected.final_e;
  const list = '/calibration', part = '/calibration/' + seed.template_ref;
  const read = () => p.read(() => page.locator('.sidebar a[href$="?view=calib"]').click(), list);
  await read();
  if (phase === 'restart') {
    await p.step(['WBP-CALIB-004', 'WBP-CALIB-006'], 'real-restart-retains-original-adoption-receipt', async () => {
      await page.getByRole('button', { name: '查看采用结果', exact: true }).click();
      await page.getByRole('region', { name: '采用与锁定结果', exact: true }).waitFor();
      const saved = await page.evaluate(() => window.CalibrationAdoptionState.read());
      assert.equal(saved.phase, 'committed'); assert.equal(saved.baseline.template_operation_ref, seed.template_ref);
      assert.equal(saved.receipt.data.new_unit_hours, 3); p.report.saved = saved;
      await p.shot('restart-original-adoption');
      await page.getByRole('dialog').locator('.modal-f').getByRole('button', { name: '关闭', exact: true }).click();
    });
    return;
  }
  await p.step(['WBP-CALIB-001', 'WBP-CALIB-002'], 'real-source-summary-typed-search-filters-sort-pagination', async () => {
    const search = page.getByRole('searchbox', { name: '搜索校准明细', exact: true });
    await search.fill('NO-CALIBRATION');
    const empty = await p.read(() => page.getByRole('button', { name: '搜索', exact: true }).click(), list);
    assert.equal(empty.data.summary.total, 0);
    await page.getByRole('status').getByText('当前筛选没有记录', { exact: true }).waitFor();
    const restored = await p.read(() => page.getByRole('button', { name: '清除筛选', exact: true }).click(), list);
    assert.equal(restored.data.summary.total, 2); assert.equal(restored.data.summary.suggested, 1);
    await p.read(() => page.getByRole('checkbox', { name: '仅看偏差 > 20%', exact: true }).check(), list);
    const table = page.getByRole('table', { name: '校准明细', exact: true });
    await page.waitForFunction(() => document.querySelectorAll('table[aria-label="校准明细"] tbody tr').length === 1);
    const suggestions = await table.innerText(); assert(suggestions.includes('200%'));
    await p.read(() => page.getByRole('checkbox', { name: '仅看偏差 > 20%', exact: true }).uncheck(), list);
    const sorts = await page.getByLabel('排序列', { exact: true }).locator('option').evaluateAll(nodes => nodes.map(n => n.value));
    for (const sort of sorts) if (sort !== await page.getByLabel('排序列', { exact: true }).inputValue()) await p.read(() => p.choose('排序列', sort), list);
    await p.read(() => p.choose('排序方向', 'desc'), list);
    await p.read(() => p.choose('每页条数', '10'), list);
    const sorted = await p.read(() => table.getByRole('button', { name: '图号 / 零件排序', exact: true }).click(), list);
    assert.equal(sorted.data.scope.sort, 'part_no'); assert.equal(sorted.data.scope.direction, 'asc');
    const facets = await p.read(() => table.getByRole('button', { name: '筛选原定额（小时/件）', exact: true }).click(), '/calibration/facets/old_unit_hours');
    assert.deepEqual(facets.data.options.map(row => row.label), ['1', '7']);
    assert(await page.getByRole('dialog').getByRole('checkbox', { name: '7', exact: true }).isChecked());
    const filtered = await p.read(() => page.getByRole('dialog').getByRole('checkbox', { name: '7', exact: true }).click(), list);
    assert.equal(filtered.data.summary.total, 1); assert.equal(filtered.data.items[0].template_operation_ref, seed.template_ref);
    assert.equal(filtered.data.scope.column_filters.old_unit_hours.mode, 'exclude');
    await p.read(() => table.getByRole('button', { name: '筛选原定额（小时/件）', exact: true }).click(), '/calibration/facets/old_unit_hours');
    await p.read(() => page.getByRole('dialog').getByRole('button', { name: '清除', exact: true }).click(), list);
    await p.read(() => table.getByRole('button', { name: '筛选可用记录数', exact: true }).click(), '/calibration/facets/sample_count');
    assert(await page.getByRole('dialog').getByRole('checkbox', { name: '5', exact: true }).isChecked());
    const insufficient = await p.read(() => page.getByRole('dialog').getByRole('checkbox', { name: '5', exact: true }).click(), list);
    assert.equal(insufficient.data.summary.total, 1); assert.equal(insufficient.data.items[0].deviation_percent, null);
    const excluded = await p.read(() => page.getByRole('checkbox', { name: '仅看偏差 > 20%', exact: true }).check(), list);
    assert.equal(excluded.data.summary.total, 0);
    await p.read(() => page.getByRole('button', { name: '清除筛选', exact: true }).click(), list);
    const separator = table.getByRole('separator', { name: '调整图号 / 零件列宽', exact: true });
    const before = await table.locator('th').first().evaluate(node => node.getBoundingClientRect().width);
    await separator.press('Shift+ArrowRight');
    await page.waitForFunction(value => document.querySelector('.ca-table th').getBoundingClientRect().width > value + 8, before);
    const keyboard = await table.locator('th').first().evaluate(node => node.getBoundingClientRect().width);
    const handle = await separator.boundingBox();
    await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2); await page.mouse.down();
    await page.mouse.move(handle.x + handle.width / 2 + 48, handle.y + handle.height / 2, { steps: 6 }); await page.mouse.up();
    const pointer = await table.locator('th').first().evaluate(node => node.getBoundingClientRect().width);
    assert(pointer > keyboard + 8);
    p.report.table_controls = { facets, filtered, insufficient, excluded, widths: { before, keyboard, pointer } };
    await p.shot('calibration-summary');
  });
  await p.step(['WBP-CALIB-003', 'WBP-CALIB-006'], 'part-number-click-and-real-selected-sample-provenance', async () => {
    const row = page.locator('.ca-table tr[data-ref="' + seed.template_ref + '"]');
    const previous = page.url(), scopeBefore = await page.getByLabel('排序列', { exact: true }).inputValue();
    const partRead = await p.read(() => row.getByRole('button', { name: '查看零件 P1', exact: true }).click(), '/entities/part/' + seed.part_ref);
    assert.equal(partRead.data.ref, seed.part_ref);
    const partDialog = page.getByRole('dialog');
    await partDialog.locator('[data-process-location="' + seed.template_ref + '"]').waitFor();
    assert(await partDialog.getByRole('button', { name: /^开始维护/ }).isDisabled());
    assert.equal(await partDialog.getByRole('button', { name: /确认采用|确认路线|确认归属|确认工时/ }).count(), 0);
    await p.shot('calibration-original-part-readonly');
    await partDialog.getByRole('button', { name: '关闭详情', exact: true }).click();
    assert.equal(page.url(), previous); assert.equal(await page.getByLabel('排序列', { exact: true }).inputValue(), scopeBefore);
    p.report.part_detail = partRead;
    const detail = await p.read(() => row.getByRole('button', { name: /^查看 P1/ }).click(), part);
    assert.equal(detail.data.suggestion.suggested_unit_hours, 3);
    assert.deepEqual(detail.data.samples.filter(row => row.selected).map(row => row.unit_hours).sort((a, b) => a - b), [1, 2, 3, 4, 50]);
    p.report.detail_before = detail;
    await page.getByText('定额记录与计算依据', { exact: true }).click();
    await page.getByText('取最近 20 条来源与版本已确认的整道完工记录，至少 5 条才生成中位数建议。原定额为 0 或未填写时都不算相对偏差。', { exact: true }).waitFor();
    const basis = page.locator('.ca-detail > .wb-detail-body > .ca-evidence');
    await basis.locator('.wb-ref > summary').click();
    assert((await basis.innerText()).includes(seed.template_ref));
    await page.locator('[data-sample-group="selected"] > details').first().locator('> summary').click();
    const sample = page.locator('[data-sample-group="selected"] .ca-sample[open]');
    await sample.locator(':scope > .wb-ref > summary').click();
    const report = sample.locator(':scope > details').filter({ has: page.locator(':scope > summary', { hasText: /^报工 ·/ }) }).first();
    await report.locator(':scope > summary').click();
    assert((await report.innerText()).includes('登记与更正记录'));
    await p.shot('calibration-real-source-and-records');
  });
  await p.step(['WBP-CALIB-005'], 'download-all-filtered-calibration-csv-and-xlsx', async () => {
    for (const format of ['csv', 'xlsx']) {
      await p.choose('导出格式', format);
      await p.download(() => page.getByRole('button', { name: '导出全部筛选', exact: true }).click(), 'calibration-' + format);
    }
  });
  await p.step(['WBP-CALIB-004', 'WBP-CALIB-006'], 'preview-cancel-then-explicit-adopt-locked-original-receipt', async () => {
    await page.getByRole('button', { name: '预检采用', exact: true }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('采用原因', { exact: true }).fill('最终全站逐项核对后采用');
    await dialog.getByLabel('经办人', { exact: true }).fill('现场验收员');
    const preview = await p.read(() => dialog.getByRole('button', { name: '检查是否可采用', exact: true }).click(), part + '/adopt-preview');
    assert.equal(preview.data.validation.can_adopt, true); assert.equal(preview.data.suggestion.sample_count, 5);
    assert.equal(preview.data.suggestion.suggested_unit_hours, 3);
    await p.shot('calibration-preview-before-cancel');
    await dialog.locator('.modal-f').getByRole('button', { name: '关闭', exact: true }).click();
    assert.equal(p.report.requests.filter(row => row.method === 'POST' && new URL(row.url).pathname.endsWith('/adopt')).length, 0);
    await page.getByRole('button', { name: '预检采用', exact: true }).click();
    await p.read(() => dialog.getByRole('button', { name: '检查是否可采用', exact: true }).click(), part + '/adopt-preview');
    await dialog.getByRole('checkbox').check();
    const receipt = await p.read(() => dialog.getByRole('button', { name: '确认采用并锁定', exact: true }).click(), part + '/adopt');
    assert.equal(receipt.data.new_unit_hours, 3); assert.equal(receipt.data.locked, true);
    await page.getByRole('region', { name: '采用与锁定结果', exact: true }).waitFor();
    p.report.receipt = receipt;
    p.report.saved = await page.evaluate(() => window.CalibrationAdoptionState.read());
    assert.equal(p.report.saved.receipt.receipt_ref, receipt.receipt_ref);
    await p.shot('calibration-committed-receipt');
    await dialog.locator('.modal-f').getByRole('button', { name: '关闭', exact: true }).click();
    const activeRequests = p.report.requests.length;
    const stale = await p.read(() => page.getByRole('button', { name: '导出全部筛选', exact: true }).click(), list + '/export', 409);
    assert.equal(stale.error.code, 'snapshot_stale');
    assert.equal(p.report.requests.slice(activeRequests).filter(row => new URL(row.url).pathname.endsWith(list)).length, 0);
    await page.getByText('数据已更新，请点「刷新」后重试。已选记录和完工记录来源已保留，不会自动跳到最新记录。', { exact: true }).waitFor();
    await p.shot('adopted-active-old-snapshot-rejected');
    await p.nav('报表中心', '/analytics');
    await p.read(() => page.getByRole('tablist', { name: '统计分析视图', exact: true })
      .getByRole('tab', { name: '执行复盘', exact: true }).click(), '/analytics');
    const refreshedDetail = page.waitForResponse(response => new URL(response.url()).pathname.endsWith(part));
    const refreshed = await p.read(() => page.locator('.sidebar a[href$="?view=calib"]').click(), list);
    assert.equal(new URL(p.report.responses[p.report.responses.length - 1].url).searchParams.has('snapshot_ref'), false);
    assert.equal(refreshed.data.items.find(row => row.template_operation_ref === seed.template_ref).old_unit_hours, 3);
    const detailAfter = await (await refreshedDetail).json();
    assert.equal(detailAfter.data.suggestion.template_operation_ref, seed.template_ref);
    assert.equal(detailAfter.data.suggestion.old_unit_hours, 3);
    await page.locator('.ca-table tr[data-ref="' + seed.template_ref + '"][data-selected=true]').waitFor();
    await p.read(() => page.reload(), list);
    const recovered = await page.evaluate(() => window.CalibrationAdoptionState.read());
    assert.deepEqual(recovered, p.report.saved);
    assert.equal(p.report.requests.filter(row => row.method === 'POST' && new URL(row.url).pathname.endsWith('/adopt')).length, 1);
  });
}

async function visuals(p) {
  await p.page.getByRole('button', { name: '查看采用结果', exact: true }).click();
  await p.page.getByRole('region', { name: '采用与锁定结果', exact: true }).waitFor(); await p.shot('adoption-receipt-viewport');
  await p.page.getByRole('dialog').locator('.modal-f').getByRole('button', { name: '关闭', exact: true }).click();
}
run('calibration', exercise, { once: true, visuals });
