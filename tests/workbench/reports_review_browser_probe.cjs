const fs = require('fs');
const path = require('path');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const { exercise } = require('./reports_review_browser_actions.cjs');
const ready = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const root = ready.root;
const report = { scope: 'real-factory-main-workbench', browser: null, cases: [], screenshots: [], errors: [], console_errors: [], http_errors: [], external: [], requests: [], responses: [], downloads: [], geometry: [] };

async function main() {
  let browser;
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true });
    report.browser = browser.version();
    for (const viewport of [{ width: 1920, height: 1080 }, { width: 1392, height: 924 }]) {
      for (const theme of ['light', 'dark']) {
        const state = `${viewport.width}-${theme}`;
        const context = await browser.newContext({ viewport, acceptDownloads: true });
        const page = await context.newPage();
        page.setDefaultTimeout(12000);
        page.on('pageerror', error => report.errors.push({ state, error: error.message }));
        page.on('console', message => { if (message.type() === 'error') report.console_errors.push({ state, text: message.text() }); });
        page.on('response', response => { if (response.status() >= 400) report.http_errors.push({ state, url: response.url(), status: response.status() }); });
        page.on('request', request => {
          if (request.url().startsWith('http') && new URL(request.url()).origin !== ready.url) report.external.push(request.url());
          if (request.url().includes('/api/workbench/')) report.requests.push({ state, method: request.method(), url: request.url() });
        });
        try { await exercise(page, ready, report, state); } finally { await context.close(); }
      }
    }
  } catch (error) { report.error = error.stack; process.exitCode = 1; }
  finally {
    if (browser) await browser.close();
    report.summary = { cases: report.cases.length, passed: report.cases.filter(row => row.passed).length,
      failed: report.cases.filter(row => !row.passed).length, screenshots: report.screenshots.length, downloads: report.downloads.length };
    fs.writeFileSync(path.join(root, 'ei-browser.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify({ summary: report.summary, error: report.error }, null, 2));
  }
}
main();
