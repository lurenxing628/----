'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require('playwright');
const {Probe} = require('./final_master_probe_support.cjs');
const ready = JSON.parse(fs.readFileSync(process.argv[2]));
const phase = process.argv[3] || 'overview';
const p = new Probe(ready, phase);
const base = '/api/workbench/v1/master-overview';
const ids = (family, numbers) => numbers.map(number => 'WBP-MD-' + family + '-A' + String(number).padStart(2, '0'));
const b = (scope, name) => name === '关闭' ? scope.locator('.modal-f').getByRole('button', {name, exact: true}) : scope.getByRole('button', {name, exact: true});
let page;
const area = () => page.getByRole('region', {name: '主数据总览', exact: true});
async function settled() {
  await page.waitForFunction(() => {
    const table = document.querySelector('.master-overview .mo-table');
    return table && table.getAttribute('aria-busy') === 'false';
  });
}
async function query(action) {
  const result = await p.response(base, action); await settled(); return result;
}
async function search(text, sequential = true) {
  if (sequential) await p.type(area().getByRole('searchbox', {name: '搜索主数据'}), text);
  else await p.fill(area().getByRole('searchbox', {name: '搜索主数据'}), text);
  return query(() => p.click(b(area(), '执行主数据搜索')));
}
async function open() {
  await page.goto(ready.url + '/workbench'); await page.locator('.sidebar').waitFor();
  const data = await query(() => p.click(page.locator('.sidebar a[href*="view=basedata"]')));
  assert.equal(new URL(page.url()).searchParams.get('view'), 'basedata');
  assert.equal(await page.locator('.sidebar [aria-current="page"]').getAttribute('href'), '/workbench?view=basedata');
  return data;
}
async function entity(domain, code) {
  await query(() => p.click(area().getByRole('tab', {name: /^实体清单/})));
  await query(() => p.select(area().getByLabel('筛选数据域'), domain));
  await search(code);
  await p.click(b(area(), '查看 ' + code));
  await area().locator('.mo-detail h3').waitFor();
}
async function detail(section) {
  const key = section === '字段' ? 'fields' : section === '相关项' ? 'relations' : 'issues';
  const tab = area().locator('.mo-detail').getByRole('tab', {name: new RegExp('^' + section)});
  const selected = await tab.getAttribute('aria-selected') === 'true';
  const waiting = selected ? null : page.waitForResponse(row => row.url().includes(base + '/entities/') && new URL(row.url()).searchParams.get('section') === key);
  await p.click(tab);
  assert.equal(await tab.getAttribute('aria-selected'), 'true');
  if (waiting) { const response = await waiting; assert.equal(response.status(), 200); }
  await page.getByRole('tabpanel', {name: section === '字段' ? '实体字段' : section === '相关项' ? '实体相关项' : '实体待维护项', exact: true}).waitFor();
}
async function main() {
  const browser = await chromium.launch({executablePath: process.env.WORKBENCH_BROWSER, headless: true});
  p.report.browser = browser.version(); assert(p.report.browser.startsWith('109.'));
  try {
    for (const [width, height] of [[1920, 1080], [1392, 924]]) for (const theme of ['light', 'dark']) {
      const context = await browser.newContext({viewport: {width, height}, timezoneId: 'Asia/Shanghai', acceptDownloads: true});
      page = await context.newPage(); p.attach(page, width + 'x' + height + '-' + theme);
      const first = await open();
      if (theme === 'dark') await p.click(b(page, '深色：关'));
      assert.equal(await page.evaluate(() => document.documentElement.dataset.theme), theme);
      if (phase === 'inspect') {
        fs.writeFileSync(ready.root + '/inspect-' + width + '-' + theme + '.txt', await page.locator('body').innerText());
        await p.run(ids('001', [4, 5, 6]), 'whole-entry-inspect', async () => {
          assert(first.data.overview.stats.entities > 0);
          assert.equal(await area().locator('.mo-domain').count(), 8);
        });
        await context.close(); continue;
      }
      await p.run(ids('001', [1, 4, 5, 6, 7]), 'actual-counts-refresh', async () => {
        const data = await query(() => p.click(b(area(), '刷新主数据')));
        const table = p.snapshot().tables;
        assert.equal(data.data.overview.domains.find(row => row.id === 'part').count, table.Parts.length);
        assert.equal(data.data.overview.domains.find(row => row.id === 'material').count, table.Materials.length);
        const metrics = await area().locator('.mo-metrics .wb-metric-value').allTextContents();
        assert.equal(metrics[0], String(data.data.overview.stats.entities));
        assert.equal(metrics[1], String(data.data.overview.stats.issues));
        assert.equal(metrics[2], String(data.data.overview.stats.affected));
        assert.equal(await area().locator('.mo-domain').count(), 8);
        assert(data.data.overview.basis.includes('不'));
      });
      if (phase === 'restart') {
        await p.run(ids('002', [2, 3, 5]), 'restart-original-entity', async () => {
          await entity('material', 'MAT-011'); await detail('字段');
          const stock = area().locator('.mo-field').filter({has: page.locator('dt', {hasText: /^库存数量$/})});
          assert.equal(await stock.locator('dd').first().innerText(), '未填');
        });
        await context.close(); continue;
      }
      await p.run([...ids('002', [2, 3, 5, 6, 7]), ...ids('003', [2, 3, 4, 5, 6, 7, 8])], 'entity-query-pages', async () => {
        await query(() => p.click(area().getByRole('tab', {name: /^实体清单/})));
        await query(() => p.select(area().getByLabel('筛选数据域'), 'part'));
        const data = await search('FC-P-'); assert.equal(data.data.page.total, 43);
        await query(() => p.select(area().getByLabel('主数据排序'), 'business_code'));
        assert.equal(await area().locator('.mo-table tbody tr').count(), 20);
        await query(() => p.click(b(area(), '主数据下一页'))); await b(area(), '查看 FC-P-021').waitFor();
        await query(() => p.click(b(area(), '主数据上一页'))); await b(area(), '查看 FC-P-001').waitFor();
        for (const size of [50, 100, 20]) {
          const next = await query(() => p.select(area().getByLabel('主数据每页条数'), size));
          assert.equal(next.data.page.size, size);
          assert.equal(await area().locator('.mo-table tbody tr').count(), Math.min(43, size));
        }
        const descending = await query(() => p.click(b(area(), '切换为降序')));
        assert.equal(descending.data.rows[0].business_code, 'FC-P-043');
      });
      await p.run(ids('007', [2, 3]), 'entity-all-pages-csv', async () => {
        const data = await p.download('entities', () => p.click(b(area(), '导出筛选结果')));
        assert.equal(data.rows.length, 44);
        assert(data.rows.some(row => row.includes('FC-P-001')) && data.rows.some(row => row.includes('FC-P-043')));
      });
      await p.run([...ids('004', [1, 2, 4, 5, 6]), ...ids('005', [3, 7])], 'original-fields-and-focus', async () => {
        await entity('material', 'MAT-011'); await detail('字段');
        const panel = page.getByRole('complementary', {name: '主数据实体详情', exact: true});
        const stock = area().locator('.mo-field').filter({has: page.locator('dt', {hasText: /^库存数量$/})});
        assert.equal(await stock.locator('dd').first().innerText(), '未填');
        assert((await area().locator('.mo-source').allTextContents()).some(text => text.includes('Materials.')));
        assert((await panel.innerText()).includes('个检查字段'));
        await p.click(b(panel, '返回清单'));
        assert.equal(await b(area(), '查看 MAT-011').evaluate(node => node === document.activeElement), true);
      });
      await p.run(ids('005', [2, 4, 5, 6, 7]), 'relations-cross-page-exact-locate', async () => {
        await entity('opType', 'RT-IN'); await detail('相关项');
        const list = page.getByRole('tabpanel', {name: '实体相关项', exact: true});
        assert.equal(await list.locator('li').count(), 10);
        async function turn(number, label) {
          const waiting = page.waitForResponse(row => row.url().includes(base + '/entities/') && new URL(row.url()).searchParams.get('detail_page') === String(number));
          await p.click(b(area(), label)); const response = await waiting; assert.equal(response.status(), 200);
          const body = await response.json(); const item = body.data.rows[0];
          await list.getByRole('button', {name: item.business_code + ' · ' + item.label, exact: true}).waitFor();
          return item;
        }
        await turn(2, '详情下一页'); await turn(1, '详情上一页');
        const item = await turn(2, '详情下一页');
        const target = list.getByRole('button', {name: item.business_code + ' · ' + item.label, exact: true});
        const code = item.business_code;
        await p.click(target); await b(area(), '查看 ' + code).waitFor();
        assert.equal(await area().getByLabel('筛选数据域').inputValue(), 'equipment');
        await area().locator('.mo-detail h3').waitFor();
        assert((await area().locator('.mo-detail').innerText()).includes(code));
      });
      await p.run(ids('006', [1, 3]), 'maintenance-real-resource-deep-link', async () => {
        await entity('material', 'MAT-011');
        await p.click(b(area(), '定位当前实体'));
        const dialog = page.getByRole('dialog', {name: '物料详情', exact: true});
        await dialog.getByText('MAT-011', {exact: true}).waitFor(); assert((await dialog.innerText()).includes('MAT-011'));
        assert.equal(new URL(page.url()).searchParams.get('view'), 'process');
        await p.click(b(dialog, '关闭'));
      });
      await open();
      await p.run([...ids('002', [1, 4]), ...ids('003', [1]), ...ids('004', [3]), ...ids('005', [1]), ...ids('007', [1])], 'issue-records-filter-csv', async () => {
        await query(() => p.select(area().getByLabel('筛选数据域'), 'part'));
        const rows = await search('FC-P-'); assert(rows.data.page.total >= 43);
        assert(rows.data.rows.every(row => row.rule && row.evidence && row.issue_ref));
        const status = await query(() => p.select(area().getByLabel('筛选检查状态'), 'attention'));
        assert(status.data.rows.every(row => row.status === 'attention'));
        await area().locator('.mo-focus').waitFor();
        await detail('待维护项');
        const file = await p.download('issues', () => p.click(b(area(), '导出筛选结果')));
        assert.equal(file.rows.length, status.data.page.total + 1);
      });
      await p.run(ids('002', [5, 7]), 'no-matches-explicit-empty', async () => {
        const data = await search('FC-NOT-FOUND-' + width, false); assert.equal(data.data.page.total, 0);
        await area().getByText('当前范围没有记录', {exact: true}).waitFor();
        assert(await b(area(), '导出筛选结果').isDisabled());
        assert.equal(await area().locator('.mo-table tbody tr').count(), 0);
        await query(() => p.click(b(area(), '清除主数据筛选')));
      });
      await p.run(ids('008', [3]), 'actual-network-failure-and-retry', async () => {
        p.expectedFailure = true;
        await context.setOffline(true);
        await p.click(b(area(), '刷新主数据'));
        await area().getByRole('alert').waitFor();
        assert.equal(await area().locator('.mo-table tbody tr').count(), 0);
        assert(await b(area(), '导出筛选结果').isDisabled());
        await p.shot('network-failure');
        await context.setOffline(false);
        await query(() => p.click(b(area(), '刷新主数据')));
        p.expectedFailure = false;
      });
      await p.run(ids('006', [4]), 'maintenance-whole-entry-and-reload', async () => {
        await p.click(b(area(), '维护基础资料'));
        await page.locator('[data-resource-workspace]').waitFor();
        assert.equal(new URL(page.url()).searchParams.get('view'), 'process');
        await page.reload(); await page.locator('[data-resource-workspace]').waitFor();
        assert.equal(new URL(page.url()).searchParams.get('view'), 'process');
      });
      await context.close();
    }
  } finally {
    await browser.close(); await Promise.all(p.pending); p.save();
  }
  assert.deepEqual(p.report.external, []);
  assert.deepEqual(p.report.errors.filter(row => !row.expected), []);
  assert.equal(p.report.summary.failed, 0);
  console.log(JSON.stringify(p.report.summary));
}
main().catch(error => {p.report.fatal = error.stack; p.save(); console.error(error); process.exitCode = 1;});
