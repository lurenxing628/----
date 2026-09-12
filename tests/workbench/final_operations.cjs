'use strict';
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const { chromium } = require('playwright');
const { support } = require('./final_operations_browser_support.cjs');
const { dashboard } = require('./final_operations_dashboard.cjs');
const { outsourcing } = require('./final_operations_outsourcing.cjs');
const { system } = require('./final_operations_system.cjs');
const { restore } = require('./final_operations_restore.cjs');
const { readControls } = require('./final_operations_read_controls.cjs');
const { edges } = require('./final_operations_edges.cjs');
const { restart, unlocatable } = require('./final_operations_navigation.cjs');
const { systemRestart } = require('./final_operations_system_restart.cjs');
const config = JSON.parse(fs.readFileSync(0, 'utf8'));
const report = { mode: config.mode, main_entrypoint: true, asset_overlay: false, assets: config.assets, viewport: config.viewport, theme: config.theme,
  actions: [], screenshots: [], responses: [], downloads: [], lifecycles: [], outsourcing: [], navigation: [], page_errors: [], external: [] };
let browser, context, page;
(async () => {
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true, args: ['--disable-background-networking'] });
    report.browser = browser.version(); assert(report.browser.startsWith('109.'));
    context = await browser.newContext({ viewport: config.viewport, acceptDownloads: true }); page = await context.newPage();
    page.setDefaultTimeout(18000);
    page.on('pageerror', error => report.page_errors.push(error.message));
    const pending = [];
    page.on('response', response => { if (response.url().includes('/api/')) pending.push((async () => {
      const row = { url: response.url(), method: response.request().method(), status: response.status() };
      if ((response.headers()['content-type'] || '').includes('application/json')) { try { row.payload = await response.json(); } catch (error) { row.body_error = error.message; } }
      report.responses.push(row);
    })()); });
    await page.route('**/*', route => { if (!route.request().url().startsWith(config.origin + '/')) { report.external.push(route.request().url()); return route.abort(); } return route.continue(); });
    const h = support(page, config, report);
    if (config.mode === 'normal') {
      await h.dashboard();
      if (config.theme === 'dark') await page.getByRole('button', { name: '切换深色', exact: true }).click();
      assert.equal(await page.locator('html').getAttribute('data-theme'), config.theme);
      await dashboard(h); await outsourcing(h); await system(h);
    } else if (['read-controls', 'config-readback'].includes(config.mode)) await readControls(h);
    else if (config.mode === 'edges') await edges(h);
    else if (config.mode === 'dashboard-restart') await restart(h);
    else if (config.mode === 'dashboard-unlocatable') await unlocatable(h);
    else if (config.mode === 'system-restart') await systemRestart(h);
    else await restore(h);
    await context.storageState({ path: path.join(config.output, 'storage.json') });
    await context.close(); context = null; await Promise.all(pending);
    assert.deepEqual(report.page_errors, []); assert.deepEqual(report.external, []);
    report.status = 'passed';
  } catch (error) {
    report.status = 'failed'; report.error = error.stack;
    if (page && !page.isClosed()) await page.screenshot({ path: path.join(config.output, 'failure.png'), fullPage: true });
    process.exitCode = 1;
  } finally {
    if (context) await context.close(); if (browser) await browser.close();
    fs.writeFileSync(path.join(config.output, 'report.json'), JSON.stringify(report, null, 2));
    process.stdout.write(JSON.stringify({ status: report.status, actions: report.actions.length, output: config.output, error: report.error }) + '\n');
  }
})();
