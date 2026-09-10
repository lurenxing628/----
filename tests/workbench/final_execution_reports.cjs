'use strict';
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const { chromium } = require('playwright');
const { exercise } = require('./reports_review_browser_actions.cjs');
const ready = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const phase = process.argv[3] || 'initial';
const report = { scope: 'Task E full offline main.jsx and real factory', phase, cases: [], screenshots: [],
  errors: [], console_errors: [], http_errors: [], external: [], requests: [], responses: [], downloads: [], geometry: [] };

async function main() {
  let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true });
    report.browser = browser.version(); assert.match(report.browser, /^109\./);
    for (const [width, height] of [[1920, 1080], [1392, 924]]) for (const theme of ['light', 'dark']) {
      const state = width + '-' + theme, context = await browser.newContext({ viewport: { width, height }, acceptDownloads: true });
      const page = await context.newPage(); page.setDefaultTimeout(15000);
      page.on('pageerror', error => report.errors.push({ state, error: error.message }));
      page.on('console', message => { if (message.type() === 'error') report.console_errors.push({ state, text: message.text() }); });
      page.on('response', response => { if (response.status() >= 400) report.http_errors.push({ state, url: response.url(), status: response.status() }); });
      page.on('request', request => {
        if (request.url().startsWith('http') && new URL(request.url()).origin !== ready.url) report.external.push(request.url());
        if (request.url().includes('/api/workbench/')) report.requests.push({ state, method: request.method(), url: request.url() });
      });
      try {
        if (phase === 'initial') await exercise(page, ready, report, state);
        else {
          await page.goto(ready.workbench_url + '?view=reports');
          await page.locator('.rw-workbench #report-topic-panel').waitFor();
        }
        const current = await page.url(), original = await page.locator('.sidebar [aria-current=page]').innerText();
        const waited = page.waitForResponse(r => new URL(r.url()).pathname === '/api/workbench/v1/analytics');
        await page.reload(); const response = await waited, payload = await response.json();
        assert.equal(response.status(), 200); assert.equal(payload.data.summary.operations, 66);
        assert.equal(payload.data.summary.production_reports, 27); assert.equal(payload.data.summary.events, 6);
        await page.locator('.rw-workbench #report-topic-panel').waitFor();
        assert.equal(page.url(), current); assert.equal(await page.locator('.sidebar [aria-current=page]').innerText(), original);
        report.cases.push({ state, name: phase + '-real-refresh-same-facts', passed: true });
        const file = path.join(ready.root, 'screenshots', 'final-report-' + state + '-' + phase + '-refreshed.png');
        await page.screenshot({ path: file }); report.screenshots.push(file);
      } finally { await context.close(); }
    }
    assert.deepEqual(report.errors, []); assert.deepEqual(report.console_errors, []); assert.deepEqual(report.external, []); assert.deepEqual(report.http_errors, []);
  } catch (error) { report.error = error.stack; process.exitCode = 1; }
  finally {
    if (browser) await browser.close();
    fs.writeFileSync(path.join(ready.root, 'final-reports-' + phase + '.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify({ cases: report.cases.length, downloads: report.downloads.length, error: report.error }));
  }
}
main();
