'use strict';
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const { chromium } = require('playwright'), H = require('./test_master_overview_browser_harness.cjs');
const output = path.resolve(process.argv[2]);
const report = { scope: 'master-overview-independent-http-mock', persistence_tested_in_browser: false, win7_hardware_tested: false,
  cases: [], screenshots: [], errors: [], external: [], unexpected: [], requests: [], geometry: [], downloads: [] };
const harness = H.setup(report, output); let browser, state, page;
const root = () => page.getByRole('region', { name: '资料总览', exact: true });
async function ready() { await page.waitForFunction(() => document.querySelector('.master-overview .mo-table tbody tr')); await page.evaluate(() => document.fonts.ready); }
async function mount(spec = {}) { harness.state.spec = spec; harness.state.requests = []; await page.evaluate(spec => mountOverview(spec), { theme: state.theme, ...spec }); }
async function shot(name) { const file = path.join(output, state.id + '-' + name + '.png'); await page.screenshot({ path: file }); report.screenshots.push(file); }
async function run(name, action) {
  const result = { state: state.id, name, passed: false }; report.cases.push(result);
  try { await action(); assert(harness.state.requests.every(row => row.method === 'GET')); result.passed = true; }
  catch (error) { result.error = error.stack; await shot('FAILED-' + name); }
  console.log(state.id + ' / ' + name + ': ' + (result.passed ? 'passed' : result.error));
}
async function entityView(domain) {
  await root().getByRole('tab', { name: /^资料清单/ }).click();
  if (domain) await root().getByLabel('筛选资料类别', { exact: true }).selectOption(domain);
  await ready();
}
async function geometry() {
  const value = await page.evaluate(() => {
    const box = selector => { const r = document.querySelector(selector).getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width }; };
    const icons = Array.from(document.querySelectorAll('.master-overview button.mo-icon')).map(button => ({ name: button.getAttribute('aria-label'), nodes: button.querySelectorAll('svg>*').length, color: getComputedStyle(button).color, disabled: button.disabled }));
    return { viewport: innerWidth, document: document.documentElement.scrollWidth, list: box('.master-overview .mo-list'), detail: box('.master-overview .mo-detail'),
      icons, surface: getComputedStyle(document.querySelector('.master-overview .wb-metric')).backgroundColor,
      overlaps: Array.from(document.querySelectorAll('.master-overview .mo-heading button,.master-overview .mo-tools button')).filter(button => button.scrollWidth > button.clientWidth + 3).map(button => button.textContent) };
  });
  assert(value.document <= value.viewport + 1, JSON.stringify(value));
  assert(value.list.right <= value.detail.left + 1 || value.list.bottom <= value.detail.top + 1);
  assert(value.detail.right <= value.viewport + 1); assert(value.icons.every(row => row.nodes > 0), JSON.stringify(value.icons));
  if (state.theme === 'dark') assert(value.icons.filter(row => !row.disabled).every(row => row.color !== 'rgb(0, 0, 0)'), 'Dark theme tool icons must not be black');
  assert.deepEqual(value.overlaps, []); report.geometry.push({ state: state.id, ...value });
}
async function mainCases() {
  await run('detail-focus-close-and-sticky-actions', async () => {
    await mount(); await ready(); await root().getByRole('heading', { name: '资料详情', exact: true }).waitFor();
    const initialPreview = await page.evaluate(() => ({ scroll: window.scrollY, headingTop: document.querySelector('.mo-heading h2').getBoundingClientRect().top,
      focused: document.activeElement === document.querySelector('.wb-detail-heading h2') }));
    assert.equal(initialPreview.scroll, 0, '自动首条预览保留资料总览首屏'); assert(initialPreview.headingTop >= 0); assert.equal(initialPreview.focused, false);
    await root().getByRole('button', { name: '关闭资料详情', exact: true }).click();
    const opener = root().locator('.mo-table tbody tr').first().getByRole('button', { name: /^查看 / });
    await opener.click();
    await page.waitForFunction(() => document.activeElement && document.activeElement.textContent === '资料详情');
    const visible = await page.evaluate(() => {
      const heading = document.querySelector('.wb-detail-heading h2').getBoundingClientRect(), frame = document.querySelector('.mo-list .wb-table-frame');
      const action = frame.querySelector('tbody .wb-col-actions').getBoundingClientRect(), bounds = frame.getBoundingClientRect();
      return { top: heading.top, bottom: heading.bottom, height: innerHeight, action: action.right, right: bounds.right,
        sticky: getComputedStyle(frame.querySelector('tbody .wb-col-actions')).position, caption: frame.querySelector('caption').textContent,
        scopes: Array.from(frame.querySelectorAll('thead th')).every(th => th.scope === 'col') };
    });
    assert(visible.top >= 0 && visible.bottom <= visible.height); assert(visible.action <= visible.right + 1); assert.equal(visible.sticky, 'sticky'); assert(visible.scopes); assert.equal(visible.caption, '资料清单');
    await page.keyboard.press('Escape'); await page.waitForFunction(() => !document.querySelector('.master-overview .wb-detail'));
    assert(await opener.evaluate(node => node === document.activeElement));
  });
  await run('first-render-and-eight-domains', async () => {
    await mount(); await ready(); await root().getByRole('tab', { name: /^相关项/ }).waitFor();
    assert.equal(await root().locator('.mo-domains .mo-domain').count(), 8);
    assert.equal((await root().locator('.mo-metrics .wb-metric-value').allTextContents())[0], '104');
    await geometry(); await shot('overview');
  });
  await run('all-pages-column-filter-and-full-csv', async () => {
    await mount(); await ready(); await entityView('part');
    await root().getByLabel('基础资料排序', { exact: true }).selectOption('business_code'); await ready();
    await root().getByRole('button', { name: '基础资料下一页', exact: true }).click();
    await root().getByRole('button', { name: '查看 P020', exact: true }).waitFor();
    await root().getByRole('button', { name: '筛选列 编号', exact: true }).click();
    await root().getByLabel('列包含文字').fill('P0'); await root().getByRole('button', { name: '应用列筛选', exact: true }).click(); await ready();
    const pending = page.waitForEvent('download'); await root().getByRole('button', { name: '导出筛选结果', exact: true }).click();
    const download = await pending, filename = path.join(output, state.id + '-full.csv'); await download.saveAs(filename);
    const content = fs.readFileSync(filename, 'utf8'); assert(content.includes('P064')); assert.equal(content.split('\r\n').filter(Boolean).length, 66);
    assert(!harness.state.requests.filter(row => row.path.endsWith('/export')).some(row => !row.token));
    report.downloads.push({ filename, rows: 65 }); await shot('entities-filter-export');
  });
  await run('cross-page-exact-relation-and-maintenance', async () => {
    const op = harness.fixture.entities.find(row => row.domain === 'opType' && row.business_code === 'IN');
    await mount({ initialContext: { domain: 'opType', entity_ref: op.ref } }); await ready();
    await root().getByRole('tab', { name: /^相关项/ }).click();
    await root().getByRole('button', { name: /^M000 ·/ }).waitFor();
    for (let index = 0; index < 3; index++) { await root().getByRole('button', { name: '详情下一页', exact: true }).click(); await root().getByRole('tab', { name: /^相关项/ }).waitFor(); }
    await root().getByRole('button', { name: /^M030 ·/ }).click();
    await root().getByRole('button', { name: '查看 M030', exact: true }).waitFor();
    const locate = harness.state.requests.filter(row => row.path.includes('/locate/')).pop(); assert(locate.path.endsWith('/' + harness.fixture.entities.find(row => row.business_code === 'M030').ref));
    await root().getByRole('button', { name: '定位当前资料', exact: true }).click();
    const navigated = await page.evaluate(() => fixtureState.navigations.at(-1));
    assert.equal(navigated.view, 'process'); assert.equal(navigated.context.kind, 'machine'); assert.equal(navigated.context.source, 'production'); assert(!('business_code' in navigated.context));
    await root().getByRole('button', { name: '刷新资料', exact: true }).click(); await ready();
    assert.equal(await root().getByLabel('筛选资料类别', { exact: true }).inputValue(), 'equipment');
    await shot('relation-located');
  });
  await run('zero-versus-unknown-and-batch-navigation', async () => {
    const zero = harness.fixture.entities.find(row => row.business_code === 'MAT0');
    await mount({ initialContext: { domain: 'material', entity_ref: zero.ref } }); await ready();
    await root().getByRole('tab', { name: /^资料项/ }).click(); await root().locator('.mo-field').first().waitFor();
    const stock = root().locator('.mo-field').filter({ has: page.locator('dt', { hasText: /^库存数量$/ }) });
    assert.equal(await stock.locator('dd').first().textContent(), '0');
    await root().getByRole('tab', { name: /^相关项/ }).click(); await root().getByRole('button', { name: /^B000 ·/ }).click();
    const navigated = await page.evaluate(() => fixtureState.navigations.at(-1)); assert.equal(navigated.view, 'batches'); assert.deepEqual(Object.keys(navigated.context), ['entity_ref']);
    const unknown = harness.fixture.entities.find(row => row.business_code === 'MAT-UNKNOWN');
    await mount({ initialContext: { domain: 'material', entity_ref: unknown.ref } }); await ready();
    await root().getByRole('tab', { name: /^资料项/ }).click(); await root().locator('.mo-field').first().waitFor();
    assert.equal(await root().locator('.mo-field').filter({ has: page.locator('dt', { hasText: /^库存数量$/ }) }).locator('dd').first().textContent(), '未填写');
  });
  await run('long-chinese-route-stage-exact-ref', async () => {
    const route = harness.fixture.entities.find(row => row.domain === 'route');
    await mount({ initialContext: { domain: 'route', entity_ref: route.ref } }); await ready();
    await root().getByRole('tab', { name: /^待维护项/ }).last().waitFor();
    const item = root().locator('.mo-detail-list li').filter({ hasText: '单件工时 0 待复核' }); await item.getByRole('button').click();
    const value = await page.evaluate(() => fixtureState.navigations.at(-1)); assert.equal(value.context.stage, 'hours'); assert.equal(value.context.kind, 'part');
    assert.equal(value.context.entity_ref, route.ref); assert(/^[0-9a-f]{48}$/.test(value.context.template_operation_ref));
    await geometry(); await shot('long-chinese-route');
  });
  await run('missing-source-and-empty-filter', async () => {
    await mount({ gaps: true }); await ready();
    assert.equal(await root().locator('.mo-domains .mo-domain').last().locator('.wb-metric-value').textContent(), '未读取');
    await root().getByRole('tab', { name: /^资料清单/ }).click(); await ready();
    await root().getByRole('searchbox', { name: '搜索基础资料' }).fill('查不到的很长中文');
    await root().getByRole('button', { name: '执行基础资料搜索', exact: true }).click();
    await root().getByText('当前范围没有记录', { exact: true }).waitFor();
    assert(await root().getByRole('button', { name: '导出筛选结果', exact: true }).isDisabled());
    await root().getByRole('button', { name: '清除基础资料筛选', exact: true }).click(); await ready();
  });
  await run('failed-read-no-stale-or-fake-results', async () => {
    await mount({ failure: true }); await root().getByRole('alert').waitFor();
    assert.equal(await root().locator('.mo-table tbody tr').count(), 0);
    assert(await root().getByRole('button', { name: '导出筛选结果', exact: true }).isDisabled());
    harness.state.spec = {}; await root().getByRole('button', { name: '刷新资料', exact: true }).click(); await ready();
  });
}
async function failureCases() {
  await run('strict-column-scope-contract', async () => {
    const rejected = await page.evaluate(() => [null, 1, [], ''].map(column_filters => {
      try { APSMasterOverviewContract.scope({ column_filters }); return false; } catch (error) { return true; }
    })); assert.deepEqual(rejected, [true, true, true, true]);
  });
  await run('invalid-count-rejected', async () => { await mount({ badCount: true }); await root().getByRole('alert').waitFor(); assert.equal(await root().locator('.mo-table tbody tr').count(), 0); });
  await run('wrong-detail-identity-rejected', async () => { await mount({ wrongDetail: true }); await ready(); await root().getByRole('alert').waitFor(); assert.equal(await root().locator('.mo-detail h3').count(), 0); });
  await run('stale-export-no-download', async () => {
    await mount(); await ready(); harness.state.spec = { stale: true }; let downloaded = false; const listener = () => { downloaded = true; }; page.on('download', listener);
    await root().getByRole('button', { name: '导出筛选结果', exact: true }).click(); await root().getByRole('alert').waitFor(); assert.equal(downloaded, false); page.off('download', listener);
  });
  await run('bad-export-snapshot-rejected', async () => {
    await mount({ badExport: true }); await ready(); await root().getByRole('button', { name: '导出筛选结果', exact: true }).click(); await root().getByRole('alert').waitFor(); assert((await root().getByRole('alert').textContent()).includes('数据版本对不上'));
  });
  await run('no-navigation-and-missing-initial-ref', async () => {
    await mount({ noNavigation: true }); await ready(); assert(await root().getByRole('button', { name: /^维护基础资料/ }).isDisabled());
    await mount({ initialContext: { domain: 'part', entity_ref: 'f'.repeat(48) } }); await root().getByRole('alert').waitFor(); assert((await root().getByRole('alert').textContent()).includes('没有换成同号的其他记录'));
  });
  await run('rapid-filter-response-cannot-replace-new-scope', async () => {
    await mount({ delay: 180 }); await ready();
    await root().getByLabel('筛选资料类别', { exact: true }).selectOption('equipment'); await root().getByLabel('筛选资料类别', { exact: true }).selectOption('material');
    await ready(); assert.equal(await root().getByLabel('筛选资料类别', { exact: true }).inputValue(), 'material');
    assert((await root().locator('.mo-table tbody').textContent()).includes('MAT0'));
  });
}
(async () => {
  try {
    await new Promise(resolve => harness.server.listen(0, '127.0.0.1', resolve));
    const origin = 'http://127.0.0.1:' + harness.server.address().port;
    browser = await chromium.launch({ headless: true, executablePath: process.env.WORKBENCH_BROWSER }); report.browser = browser.version(); assert(report.browser.startsWith('109.'));
    for (const [width, height] of [[1920, 1080], [1392, 924], [1366, 768], [1280, 720]]) for (const theme of ['light', 'dark']) {
      state = { id: width + 'x' + height + '-' + theme, theme };
      const context = await browser.newContext({ viewport: { width, height }, acceptDownloads: true }); page = await context.newPage(); page.setDefaultTimeout(10000);
      page.on('pageerror', error => report.errors.push(error.stack));
      page.on('request', req => { if (!req.url().startsWith(origin) && !req.url().startsWith('blob:')) report.external.push(req.url()); });
      await page.goto(origin); await mainCases();
      if (width === 1920 && theme === 'light') await failureCases();
      await context.close();
    }
  } catch (error) { report.error = error.stack; }
  finally {
    if (browser) await browser.close(); await new Promise(resolve => harness.server.close(resolve));
    report.summary = { cases: report.cases.length, failed: report.cases.filter(row => !row.passed).length, screenshots: report.screenshots.length };
    fs.writeFileSync(path.join(output, 'master-overview-result.json'), JSON.stringify(report, null, 2));
    if (report.error || report.summary.failed || report.errors.length || report.external.length) process.exitCode = 1;
    console.log(JSON.stringify(report.summary));
  }
})();
