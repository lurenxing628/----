const assert = require('node:assert/strict');
const { Probe } = require('./reports_review_browser_support.cjs');
const { detailsAndCatalogs } = require('./reports_review_browser_details.cjs');
const topics = [['delivery', '工序完成情况'], ['records', '报工记录'], ['machines', '设备工时'], ['people', '人员工时'], ['quality', '数据完整性']];

async function exercise(page, ready, report, state) {
  const p = new Probe(page, ready, report, state), work = p.work;
  await page.goto(ready.workbench_url);
  await page.locator('.sidebar').waitFor();
  if (state.endsWith('dark')) await page.getByRole('button', { name: '切换深色', exact: true }).click();
  await p.step('main-navigation-review-and-report', async () => {
    await p.read(() => page.locator('.sidebar').getByText('报表中心', { exact: true }).click());
    await p.read(() => work.getByRole('tablist', { name: '统计分析视图', exact: true }).getByRole('tab', { name: '执行复盘', exact: true }).click());
    assert.equal(p.data.data.summary.operations, 66);
    assert.equal(p.data.data.summary.production_reports, 27);
    assert.equal(p.data.data.summary.events, 6);
    assert.equal(p.data.data.summary.records, 33);
    await p.geometry('review'); await p.shot('review');
    await p.read(() => work.getByRole('tablist', { name: '统计分析视图', exact: true }).getByRole('tab', { name: '报表中心', exact: true }).click());
    await p.geometry('reports'); await p.shot('reports');
  });
  await p.step('typed-search-empty-and-reset', async () => {
    const search = work.getByLabel('搜索批次或工序', { exact: true });
    await search.click(); await search.type('EI-OP-002');
    await p.read(() => search.press('Enter'));
    assert.equal(p.data.data.page.total, 1); assert.equal(p.data.data.scope.query, 'EI-OP-002');
    await p.shot('typed-filter');
    await search.fill('EI-NO-SUCH-OPERATION'); await p.read(() => search.press('Enter'));
    assert.equal(p.data.data.page.total, 0);
    assert.equal(await work.getByRole('button', { name: /^导出范围/ }).isDisabled(), true);
    await p.shot('empty');
    await p.read(() => work.getByRole('button', { name: '清除筛选', exact: true }).click());
    assert.equal(p.data.data.page.total, 66);
  });
  await p.step('typed-dates-resource-focus-dropdowns', async () => {
    await work.getByLabel('计划完工起日', { exact: true }).fill('2026-09-09');
    await work.getByLabel('计划完工止日', { exact: true }).fill('2026-09-09');
    await work.getByRole('button', { name: '更多筛选', exact: true }).click();
    await p.choose('资源类型', 'machine');
    const resource = await work.getByLabel('关联资源', { exact: true }).locator('option').evaluateAll(nodes => nodes.find(node => node.textContent.includes('一号精加工')).value);
    await p.choose('关联资源', resource); await p.choose('分析范围', 'unreported');
    await work.getByLabel('批次筛选', { exact: true }).click();
    await page.getByRole('listbox', { name: '批次筛选' }).waitFor(); await p.shot('batch-dropdown');
    await page.keyboard.press('Escape');
    await p.read(() => work.getByRole('button', { name: '查询范围', exact: true }).click());
    assert.equal(p.data.data.scope.focus, 'unreported');
    assert(p.data.data.rows.every(row => row.record_count === 0));
    assert.equal(p.data.data.scope.plan_finish_date_from, '2026-09-09');
    await p.geometry('expanded-filters'); await p.shot('expanded-filters');
    await p.read(() => work.getByRole('button', { name: '清除筛选', exact: true }).click());
    await work.getByRole('button', { name: '更多筛选', exact: true }).click();
  });
  for (const [topic, label] of topics) {
    await p.step('topic-' + topic + '-all-sorts-pagination-export', async () => {
      if (topic !== 'delivery') await p.read(() => work.getByRole('tab', { name: label, exact: true }).click());
      assert.equal(p.data.data.topic, topic);
      const options = await work.getByLabel('排序字段', { exact: true }).locator('option').evaluateAll(nodes => nodes.map(node => node.value));
      for (const option of options) {
        if (option !== p.data.data.page.sort[0].field) await p.read(() => p.choose('排序字段', option));
        await p.read(() => p.choose('排序方向', 'desc'));
        assert.equal(p.data.data.page.sort[0].direction, 'desc');
        await p.read(() => p.choose('排序方向', 'asc'));
      }
      await p.read(() => p.choose('每页条数', '10'));
      if (p.data.data.page.pages > 1) {
        await p.read(() => work.locator('#report-topic-panel .rw-list-pane > .wb-pager').getByRole('button', { name: '下一页', exact: true }).click());
        assert.equal(p.data.data.page.number, 2);
        assert.equal(p.data.data.rows.length, 10);
      }
      await p.geometry(topic); await p.shot(topic + '-page');
      await p.choose('导出格式', 'csv'); await p.download('导出范围');
      await p.choose('导出格式', 'xlsx'); await p.download('导出范围');
      await p.read(() => p.choose('每页条数', '50'));
      assert.equal(p.data.data.page.number, 1); assert.equal(p.data.data.page.size, 50);
      if (['delivery', 'records'].includes(topic)) {
        const scroll = work.getByRole('region', { name: '报表结果表格', exact: true });
        await scroll.focus(); await scroll.press('End');
        await page.waitForFunction(() => document.querySelector('.rw-primary-table').scrollTop > 100);
        const geometry = await scroll.evaluate(node => ({ top: node.getBoundingClientRect().top,
          head: node.querySelector('th').getBoundingClientRect().top, width: node.clientWidth, scrollWidth: node.scrollWidth }));
        assert(Math.abs(geometry.top - geometry.head) < 2, 'Header must stay visible during keyboard scrolling');
        assert(geometry.scrollWidth <= geometry.width + 1, 'All main columns fit both target viewports');
        await p.shot(topic + '-50-rows-keyboard-scroll');
      }
      await p.read(() => p.choose('每页条数', '20'));
    });
  }
  await detailsAndCatalogs(p);
}
module.exports = { exercise };
