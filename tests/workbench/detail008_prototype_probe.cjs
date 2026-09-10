'use strict';
const assert = require('node:assert/strict');
const path = require('node:path');
const {chromium} = require('playwright');
const {start, inspect, shot, sha, json} = require('./detail008_prototype_support.cjs');
const {probeDetails, probeCodeCollision} = require('./detail008_prototype_links.cjs');

async function main() {
  const env = await start();
  let browser;
  try {
    browser = await chromium.launch({executablePath: process.env.WORKBENCH_BROWSER, headless: true});
    env.report.browser_version = browser.version();
    const context = await browser.newContext({viewport: {width: 1392, height: 900}, locale: 'zh-CN'});
    await context.route('**/*', async route => {
      if (route.request().url().startsWith(env.base + '/') || /^(data:|blob:)/.test(route.request().url())) await route.continue();
      else { env.report.external.push(route.request().url()); await route.abort(); }
    });
    const page = await context.newPage();
    await page.addInitScript(() => {
      window.__detail008Clicks = [];
      document.addEventListener('click', event => window.__detail008Clicks.push({trusted: event.isTrusted,
        tag: event.target.tagName, text: event.target.textContent?.trim().slice(0, 100),
        within_unified_drawer: !!event.target.closest('.apsd-panel')}), true);
    });
    page.setDefaultTimeout(12000);
    page.on('pageerror', error => env.report.errors.push({type: 'pageerror', message: error.stack}));
    page.on('console', message => {
      if (message.type() === 'error') env.report.errors.push({type: 'console', message: message.text()});
    });
    const click = async (locator, chain) => {
      env.report.steps.push({action: 'actual_pointer_click', locator: String(locator), chain, at: new Date().toISOString()});
      await locator.click();
    };
    const entry = async id => {
      await page.locator('.sidebar-nav').waitFor();
      if (id === 'delay') {
        await click(page.locator('.sidebar-nav a[href="#analysis"]'), ['analysis']);
        await click(page.getByRole('button', {name: '\u4ea4\u4ed8\u98ce\u9669', exact: true}), ['analysis', 'delay']);
      } else await click(page.locator('.sidebar-nav a[href="#' + id + '"]'), [id]);
      await page.waitForURL(url => url.searchParams.get('view') === id);
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    };
    await page.goto(env.base + '/ui_kits/workbench/index.html');
    await page.locator('.sidebar-nav').waitFor();
    env.report.initial = await inspect(page);
    if (process.env.DETAIL008_CASE === 'code-collision') {
      await probeCodeCollision(env, page, click, entry);
      return;
    }
    for (const id of ['dashboard', 'gantt', 'run', 'analysis', 'delay', 'review', 'reports', 'calib', 'batches', 'process', 'field', 'fieldgantt', 'basedata', 'system']) {
      await entry(id);
      env.report.entries.push({id, ...(await inspect(page)), screenshot: await shot(env, page, 'entry-' + id)});
      env.save();
    }
    env.report.runtime_functions = await page.evaluate(() => Object.fromEntries([
      'App', 'AppShell', 'GanttScreen', 'GanttBoard', 'AnalysisScreen', 'DelayScreen', 'BasicDataScreen',
      'BaseDataScreen', 'CalibScreen', 'ProcessNative', 'BatchesScreen', 'FieldGanttScreen', 'ReportsScreen',
      'APSPlanAInit'].map(key => [key, typeof window[key] === 'function' ? window[key].toString() : null])));
    env.report.detail_open_function_sha256 = sha(await page.evaluate(() => window.APSDetail.open.toString()));
    // Expand pure record body strings into a detached document. This is graph evidence, not a UI entry.
    env.report.record_graph = await page.evaluate(() => Object.entries(window.APSDetail.RECORDS).map(([code, record]) => ({
      code, type: record.type, foot: record.foot || [], links: [...new DOMParser().parseFromString(record.body(), 'text/html')
        .querySelectorAll('[data-apsd-go]')].map(node => node.getAttribute('data-apsd-go'))})));
    env.report.bundle_errors = await page.evaluate(() => window.APSDesignSystem_edbc5d.__errors);
    await entry('process');
    env.report.native_start = await inspect(page);
    const nodes = env.report.native_start.controls.filter(row => row.data.node).map(row => ({node: row.data.node, sub: row.data.sub}));
    for (const node of nodes) {
      const selector = '[data-node="' + node.node + '"]' + (node.sub ? '[data-sub="' + node.sub + '"]' : ':not([data-sub])');
      await click(page.locator('.plana ' + selector), ['process', node]);
      env.report.controls.push({native: node, ...(await inspect(page))});
    }
    await probeDetails(env, page, click, entry);
    env.report.index_click_events = await page.evaluate(() => window.__detail008Clicks);
    assert(env.report.index_click_events.every(row => row.trusted));
    await click(page.locator('.sidebar-nav a[href="trial-sample.html"]'), ['trial']);
    await page.waitForURL('**/trial-sample.html');
    env.report.entries.push({id: 'trial', ...(await inspect(page)), screenshot: await shot(env, page, 'entry-trial')});
    env.report.trial_detail_api_present = await page.evaluate(() => typeof window.APSDetail !== 'undefined');
    assert.equal(env.report.trial_detail_api_present, false);
    assert.equal(env.report.entries.length, 15);
    env.report.inventory_complete = true;
    env.report.conclusion = 'no_current_ui_path_to_detail008_in_frozen_15_entries';
    json(path.join(env.root, 'runtime-functions.json'), env.report.runtime_functions);
    delete env.report.runtime_functions;
    env.save();
  } catch (error) {
    env.report.failure = error.stack;
    process.exitCode = 1;
    console.error(error.stack);
  } finally {
    if (browser) { await browser.close(); env.report.browser_closed = true; }
    await env.stop();
    console.log('DETAIL008_SUMMARY ' + JSON.stringify({root: env.root, entries: env.report.entries.length,
      native_views: env.report.controls.length, errors: env.report.errors.length, source_changes: env.report.source_changes,
      planning_unchanged: env.report.planning_unchanged, failure: env.report.failure || null}));
  }
}
main().catch(error => { console.error(error.stack); process.exitCode = 1; });
