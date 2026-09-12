const assert = require('node:assert/strict');

async function detailsAndCatalogs(p) {
  const { page, work } = p;
  await p.step('long-text-detail-revisions-keyboard-close', async () => {
    await p.read(() => work.getByRole('tab', { name: '报工记录', exact: true }).click());
    const search = work.getByLabel('搜索批次或工序', { exact: true });
    await search.fill('EI-LONG-'); await p.read(() => search.press('Enter'));
    assert.equal(p.data.data.page.total, 1);
    const row = work.locator('.rw-primary-table tbody tr');
    assert((await row.boundingBox()).height < 160, 'Collapsed long text must not expand a dense row');
    await row.getByLabel('展开备注', { exact: true }).click();
    await p.shot('long-remark-expanded');
    await row.getByLabel('展开备注', { exact: true }).click();
    await row.getByRole('button', { name: /^查看工序/ }).click();
    const detail = work.locator('.rw-detail');
    await detail.getByText('逐次报工 1 条', { exact: false }).waitFor();
    await p.shot('long-detail');
    await page.keyboard.press('Escape'); await detail.waitFor({ state: 'hidden' });
    await search.fill('OP1'); await p.read(() => search.press('Enter'));
    await work.locator('.rw-primary-table tbody tr').first().getByRole('button', { name: /^查看工序/ }).click();
    await detail.locator('.rw-limitations').first().waitFor();
    await detail.locator('.rw-limitations > summary').first().click();
    await detail.getByText('逐次报工修订历史（2 次登记）', { exact: true }).waitFor();
    await detail.locator('.rw-limitations[open] > details > summary').last().click();
    await p.shot('correction-evidence');
    await detail.getByRole('button', { name: '下一页', exact: true }).click();
    assert((await detail.locator('.wb-detail-body > .wb-pager').textContent()).includes('第 2 / 2 页'));
    await detail.getByRole('button', { name: /^关闭/ }).click();
    await p.read(() => work.getByRole('button', { name: '清除筛选', exact: true }).click());
  });
  await p.step('review-navigation-restores-report-tab-sort-page', async () => {
    const originalViewport = page.viewportSize(), scrollingViewport = { width: 1366, height: 768 };
    await page.setViewportSize(scrollingViewport);
    try {
      await p.read(() => p.choose('每页条数', '10'));
      await p.read(() => work.locator('#report-topic-panel .rw-list-pane > .wb-pager').getByRole('button', { name: '下一页', exact: true }).click());
      const before = p.data;
      const table = work.getByRole('region', { name: '报表结果表格', exact: true });
      assert.equal(before.data.page.number, 2); assert.equal(before.data.page.size, 10);
      assert.equal(await table.locator('tbody tr').count(), 10);
      const range = await table.evaluate(node => ({ clientHeight: node.clientHeight, scrollHeight: node.scrollHeight }));
      assert(range.scrollHeight - range.clientHeight > 10, 'Ten real records must overflow in the supported scroll-test viewport');
      (p.report.scroll_restore_viewports || (p.report.scroll_restore_viewports = [])).push({ state: p.state, originalViewport, scrollingViewport, range });
      await table.focus(); await table.press('End');
      await page.waitForFunction(() => document.querySelector('.rw-primary-table').scrollTop > 10);
      await page.waitForFunction(() => {
        const table = document.querySelector('.rw-primary-table');
        return table.scrollHeight - table.clientHeight - table.scrollTop < 2;
      });
      const tableTop = await table.evaluate(node => node.scrollTop);
      await p.read(() => work.getByRole('tablist', { name: '统计分析视图', exact: true }).getByRole('tab', { name: '执行复盘', exact: true }).click());
      assert.equal(p.data.data.topic, 'delivery');
      await work.locator('.er-chart-disclosure > summary').click();
      await work.locator('.aw-data > summary').click();
      await p.shot('review-charts');
      const firstReading = page.waitForResponse(response => {
        const url = new URL(response.url());
        return url.pathname === '/api/workbench/v1/analytics' && url.searchParams.get('page') === '1' && !url.searchParams.has('snapshot_ref');
      }).then(response => response.json());
      await p.read(() => work.getByRole('tablist', { name: '统计分析视图', exact: true }).getByRole('tab', { name: '报表中心', exact: true }).click(),
        '/api/workbench/v1/analytics', 200, before.data.page.number);
      const first = await firstReading;
      assert.equal(first.ok, true); assert.deepEqual(first.data.scope, before.data.scope);
      assert.equal(p.data.meta.snapshot_ref, first.meta.snapshot_ref);
      assert.deepEqual(p.data.data, before.data);
      await page.waitForFunction(expected => Math.abs(document.querySelector('.rw-primary-table').scrollTop - expected) < 2, tableTop);
      await p.shot('restored-report-position');
    } finally { await page.setViewportSize(originalViewport); }
  });
  await p.step('all-four-catalogs-filter-sort-window-and-export', async () => {
    await p.read(() => work.locator('.rw-catalog > summary').click(), '/api/workbench/v1/reports/overdue');
    const catalog = work.getByRole('region', { name: '其他报表目录' });
    for (const kind of ['overdue', 'utilization', 'downtime', 'official-review']) {
      if (kind !== 'overdue') await p.read(() => p.choose('其他报表', kind, catalog), '/api/workbench/v1/reports/' + kind);
      if (kind !== 'official-review') {
        await p.read(() => p.choose('目录排序方向', 'desc', catalog), '/api/workbench/v1/reports/' + kind);
        const sorts = await catalog.getByLabel('目录排序字段', { exact: true }).locator('option').evaluateAll(nodes => nodes.map(node => ({ value: node.value, selected: node.selected })));
        for (const option of sorts.filter(row => !row.selected)) await p.read(() => p.choose('目录排序字段', option.value, catalog), '/api/workbench/v1/reports/' + kind);
        const search = catalog.getByLabel('搜索目录报表', { exact: true });
        await search.click(); await search.type('EI-NO-CATALOG');
        const empty = await p.read(() => search.press('Enter'), '/api/workbench/v1/reports/' + kind);
        assert.equal(empty.data.page.total, 0);
        assert.equal(await catalog.getByRole('button', { name: /^导出 XLSX/ }).isDisabled(), true);
        await p.shot('catalog-' + kind + '-empty');
        await search.fill(''); await p.read(() => search.press('Enter'), '/api/workbench/v1/reports/' + kind);
        if (kind !== 'overdue') {
          await catalog.getByLabel('统计窗口起日', { exact: true }).fill('2026-09-09');
          await catalog.getByLabel('统计窗口止日', { exact: true }).fill('2026-09-09');
          await p.read(() => catalog.getByRole('button', { name: '读取目录范围', exact: true }).click(), '/api/workbench/v1/reports/' + kind);
        }
      }
      await catalog.getByLabel('其他报表', { exact: true }).scrollIntoViewIfNeeded();
      await p.geometry('catalog-' + kind); await p.shot('catalog-' + kind);
      await p.download('导出 XLSX', catalog);
    }
  });
}
module.exports = { detailsAndCatalogs };
