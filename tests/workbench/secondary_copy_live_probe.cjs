/* Real /workbench main and real GET responses; only the scoped style build varies. */
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const { chromium } = require('playwright'), M = require('./secondary_copy_metrics.cjs');
const ready = JSON.parse(fs.readFileSync(process.argv[2])), root = ready.root, origin = ready.url;
const report = { scope: 'frozen-formal-main-and-pages-with-private-style-candidates-real-temporary-SQLite',
  global_build: false, baseline_kind: ready.assets.secondary_copy.baseline_kind, historical_baseline_claimed: false,
  win7_hardware_tested: false, cases: [], errors: [], external: [], writes: [], api: [], scripts: [], screenshots: [] };
const targets = {
  process: ['.crumb > span:not(.cur):not(.sep)', '.wb-pager-summary', '.wb-th-title', '.tbl td .muted'],
  reports: ['.rw-header p', '.rw-asof', '.rw-basis', '.wb-pager-summary', '.rw-filters label'],
  system: ['.sm-header p', '.sm-source-note', '.sm-work-description', '.sm-meta']
};
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
async function settle(page) {
  await page.evaluate(async () => { await document.fonts.ready; await new Promise(r => requestAnimationFrame(r));
    await Promise.all(document.getAnimations().map(a => a.finished)); await new Promise(r => requestAnimationFrame(r)); });
}
async function shot(page, name) {
  const file = path.join(root, 'screenshots', name + '.png');
  await page.screenshot({ path: file, fullPage: false }); report.screenshots.push(file);
}
async function capture(browser, width, theme, view, phase) {
  const name = [width, theme, view, phase].join('-'), pending = [];
  const context = await browser.newContext({ viewport: { width, height: width === 1920 ? 1080 : 924 }, timezoneId: 'Asia/Shanghai' });
  await context.addInitScript(theme => { localStorage.setItem('aps_kit_theme', theme); localStorage.setItem('aps_theme', theme); }, theme);
  await context.route('**/*', route => {
    const request = route.request(), url = new URL(request.url());
    if (url.origin !== origin) { report.external.push(url.href); return route.abort(); }
    if (!['GET', 'HEAD'].includes(request.method())) { report.writes.push({ method: request.method(), url: url.href }); return route.abort(); }
    if (phase === 'before' && url.pathname === '/static/workbench/app/styles/10-shell.css') {
      url.pathname = '/static/workbench/app/styles/secondary-copy-before.css'; return route.continue({ url: url.href });
    }
    return route.continue();
  });
  const page = await context.newPage(); page.setDefaultTimeout(15000);
  page.on('pageerror', e => report.errors.push({ name, error: e.message }));
  page.on('console', m => { if (m.type() === 'error') report.errors.push({ name, console: m.text() }); });
  page.on('requestfailed', r => report.errors.push({ name, url: r.url(), failed: r.failure() }));
  page.on('response', response => {
    pending.push((async () => {
      const url = new URL(response.url());
      if (response.status() >= 400) report.errors.push({ name, url: url.href, status: response.status() });
      if (url.pathname.includes('/api/workbench/') && response.headers()['content-type']?.includes('application/json')) {
        const bytes = await response.body(), data = JSON.parse(bytes);
        report.api.push({ name, path: url.pathname, status: response.status(), ok: data.ok, source: data.meta?.source,
          snapshot_ref: data.meta?.snapshot_ref, total: data.data?.page?.total, body_sha256: sha(bytes) });
      }
      if (/\/(10-shell|secondary-copy-before)\.css$|\/main\.js$/.test(url.pathname))
        report.scripts.push({ name, path: url.pathname, sha256: sha(await response.body()) });
    })());
  });
  try {
    await page.goto(origin + '/workbench?view=' + view);
    await page.locator('.sidebar').waitFor();
    if (view === 'process') {
      await page.getByRole('button', { name: 'EO-MAT-001', exact: true }).waitFor();
      await page.locator('.wb-pager').waitFor();
      assert.match(await page.locator('.wb-pager').innerText(), /25/);
    } else if (view === 'reports') {
      await page.locator('.rw-workbench[data-ready="true"]').waitFor();
      assert((await page.locator('.rw-table tbody tr').count()) > 0, 'Nonempty real report required');
    } else await page.locator('.sm-work-description').first().waitFor();
    await settle(page); assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
    const samples = await M.measure(page, targets[view]);
    const row = { name, width, theme, view, phase, samples, tokens: await M.tokens(page), controls: await M.controls(page) };
    report.cases.push(row); await shot(page, name);
    if (view === 'process') { await page.locator('.wb-pager').scrollIntoViewIfNeeded(); await shot(page, name + '-pager'); }
    if (phase === 'after') M.readable(samples, targets[view]);
    else targets[view].forEach(selector => assert(samples.some(s => s.selector === selector), 'Missing baseline: ' + selector));
    if (theme === 'light' && view === 'process' && phase === 'before')
      assert(samples.some(s => s.color === M.original), 'Synthetic candidate must remove the scoped secondary-copy alias');
    await Promise.all(pending);
    const source = ready.assets.secondary_copy.candidates.find(c => c.phase === phase);
    assert(report.scripts.some(s => s.name === name && s.sha256 === source.sha256), 'Browser did not load the exact style candidate');
    assert(report.scripts.some(s => s.name === name && /\/main\.js$/.test(s.path)), 'Real main did not load');
    assert(report.api.some(a => a.name === name && a.source === 'production' && a.ok === true), 'Missing real API evidence');
    if (view !== 'system') assert(report.api.some(a => a.name === name && a.total > 0 &&
      a.path === (view === 'reports' ? '/api/workbench/v1/analytics' : '/api/workbench/v1/entities/material')), 'Nonempty real API data required');
    row.passed = true; return row;
  } catch (error) {
    await shot(page, name + '-FAILED'); fs.writeFileSync(path.join(root, name + '-dom.txt'), await page.locator('body').innerText());
    throw error;
  } finally { await Promise.all(pending); await context.close(); }
}
(async () => {
  let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true });
    report.browser = browser.version(); assert.match(report.browser, /^109\./);
    for (const width of [1920, 1392]) for (const theme of ['light', 'dark']) for (const view of Object.keys(targets)) {
      const before = await capture(browser, width, theme, view, 'before');
      const after = await capture(browser, width, theme, view, 'after');
      M.compare(before, after, theme);
    }
    for (const key of ['errors', 'external', 'writes']) assert.deepEqual(report[key], [], key);
    assert(report.api.every(a => a.ok === true && a.status === 200));
  } catch (error) { report.fatal = error.stack; console.error(error); process.exitCode = 1; }
  finally {
    if (browser) await browser.close(); report.stopped = true;
    fs.writeFileSync(path.join(root, 'secondary-copy-live.json'), JSON.stringify(report, null, 2));
  }
})();
