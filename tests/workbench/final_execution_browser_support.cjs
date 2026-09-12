'use strict';
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
const controls = require('./custom_control_actions.cjs');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

class Probe {
  constructor(ready, report, page, state) { Object.assign(this, { ready, report, page, state }); }
  async step(ids, action, run) {
    const row = { ids, action, state: this.state, passed: false };
    this.report.actions.push(row);
    try { row.result = await run(); row.passed = true; }
    catch (error) { row.error = error.stack; await this.shot('failure-' + this.report.actions.length); throw error; }
  }
  async read(action, suffix, status = 200) {
    const pending = this.page.waitForResponse(r => new URL(r.url()).pathname.endsWith(suffix))
      .then(response => ({ response }), error => ({ error }));
    await action();
    const outcome = await pending; if (outcome.error) throw outcome.error;
    const response = outcome.response, data = await response.json();
    this.report.responses.push({ state: this.state, url: response.url(), status: response.status(), payload: data });
    assert.equal(response.status(), status, JSON.stringify(data));
    if (status === 200) assert.equal(data.ok, true);
    return data;
  }
  async choose(label, value, owner = this.page) {
    const field = owner.getByLabel(label, { exact: true });
    await field.waitFor({ state: 'visible' });
    await controls.select(field, value);
  }
  async shot(name) {
    const file = path.join(this.ready.root, 'screenshots', this.state + '-' + name + '.png');
    await this.page.screenshot({ path: file, animations: 'disabled' });
    const geometry = await this.page.evaluate(() => ({ theme: document.documentElement.dataset.theme,
      viewport: [innerWidth, innerHeight], documentWidth: document.documentElement.scrollWidth,
      dialogs: [...document.querySelectorAll('[role=dialog]')].filter(n => n.getClientRects().length).map(n => {
        const r = n.getBoundingClientRect(); return { left: r.left, right: r.right, top: r.top, bottom: r.bottom };
      }) }));
    this.report.screenshots.push({ state: this.state, name, path: file, sha256: hash(fs.readFileSync(file)), geometry });
    assert(geometry.documentWidth <= geometry.viewport[0] + 1, 'Page overflow');
    for (const r of geometry.dialogs) assert(r.left >= 0 && r.right <= geometry.viewport[0] && r.top >= 0 && r.bottom <= geometry.viewport[1] + 1);
  }
  async download(action, name) {
    const pending = this.page.waitForEvent('download');
    await action();
    const download = await pending;
    const file = path.join(this.ready.root, 'downloads', this.state + '-' + name + '-' + download.suggestedFilename());
    await download.saveAs(file); assert.equal(await download.failure(), null);
    const bytes = fs.readFileSync(file);
    this.report.downloads.push({ state: this.state, name, path: file, sha256: hash(bytes), bytes: bytes.length });
    return file;
  }
  async nav(label, suffix) {
    return this.read(() => this.page.locator('.sidebar').getByText(label, { exact: true }).click(), suffix);
  }
  async theme(theme) {
    const current = await this.page.locator('html').getAttribute('data-theme');
    if (current !== theme) await this.page.getByRole('button', { name: /^切换(?:深色|浅色)$/ }).click();
    await this.page.waitForFunction(value => document.documentElement.dataset.theme === value, theme);
  }
  gap(id, action, evidence, status = 'missing') { this.report.gaps.push({ id, action, state: this.state, status, evidence }); }
}

async function run(kind, exercise, { once = false, visuals = null } = {}) {
  const ready = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const phase = process.argv[3] || 'initial';
  const report = { kind, phase, full_main: true, actions: [], screenshots: [], responses: [], requests: [],
    downloads: [], gaps: [], page_errors: [], console_errors: [], external_requests: [], failed_requests: [] };
  let browser, activePage;
  try {
    browser = await chromium.launch({ executablePath: process.env.WORKBENCH_BROWSER, headless: true });
    report.browser = browser.version(); assert.match(report.browser, /^109\./);
    const savedContext = path.join(ready.root, kind + '-browser-storage.json');
    const context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, acceptDownloads: true,
      ...(phase === 'restart' ? { storageState: savedContext } : {}) });
    const page = await context.newPage(); activePage = page; page.setDefaultTimeout(15000);
    page.on('pageerror', error => report.page_errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') report.console_errors.push(message.text()); });
    page.on('request', request => {
      if (request.url().startsWith('http') && new URL(request.url()).origin !== ready.url) report.external_requests.push(request.url());
      if (request.url().includes('/api/workbench/')) report.requests.push({ method: request.method(), url: request.url(), body: request.postData() });
    });
    page.on('requestfailed', request => report.failed_requests.push({ method: request.method(), url: request.url(), failure: request.failure() }));
    const p = new Probe(ready, report, page, '1920-light-' + phase);
    await page.goto(ready.workbench_url); await page.locator('.sidebar').waitFor();
    await p.theme('light');
    const scripts = await page.locator('script[src]').evaluateAll(nodes => nodes.map(n => n.src));
    assert(scripts.some(src => src.endsWith('/main.js') || src.includes('/main.js?')), 'Must serve compiled full main.jsx');
    report.main_script = scripts.find(src => src.includes('/main.js'));
    if (once) await exercise(p, phase);
    for (const [width, height] of [[1920, 1080], [1392, 924]]) for (const theme of ['light', 'dark']) {
      p.state = width + '-' + theme + '-' + phase;
      await page.setViewportSize({ width, height }); await p.theme(theme);
      if (!once) await exercise(p, phase);
      else await p.shot(kind + '-final');
      if (visuals) await visuals(p, phase);
    }
    await context.storageState({ path: savedContext });
    await context.close();
    assert.deepEqual(report.page_errors, []); assert.deepEqual(report.external_requests, []);
  } catch (error) {
    report.error = error.stack; process.exitCode = 1;
    if (activePage && !activePage.isClosed()) {
      report.failure_state = await activePage.evaluate(() => {
        const position = node => node && ({ left: node.scrollLeft, top: node.scrollTop, width: node.clientWidth,
          height: node.clientHeight, scrollWidth: node.scrollWidth, scrollHeight: node.scrollHeight });
        return { url: location.href, history: history.state, actual: position(document.querySelector('[data-actual-scroll]')),
          table: position(document.querySelector('.rw-primary-table')), main: position(document.querySelector('.main-content')),
          window: { top: scrollY, left: scrollX }, text: document.querySelector('.main-content').innerText };
      });
      const file = path.join(ready.root, 'screenshots', 'final-' + kind + '-' + phase + '-failure-state.png');
      await activePage.screenshot({ path: file, animations: 'disabled' }); report.failure_screenshot = file;
    }
  }
  finally {
    if (browser) await browser.close();
    fs.writeFileSync(path.join(ready.root, 'final-' + kind + '-' + phase + '.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify({ kind, phase, actions: report.actions.length, gaps: report.gaps, error: report.error }));
  }
}
module.exports = { Probe, run, controls, hash };
