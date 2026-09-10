'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');

function isCanceledRead(method, url, errorText) {
  if (errorText !== 'net::ERR_ABORTED') return false;
  const pathname = new URL(url).pathname;
  const resourceFacets = /^\/api\/workbench\/v1\/entities\/(material|machine|operator|supplier|op_type)\/(facets|facet-selection)$/.test(pathname);
  const batchRead = ['/api/workbench/v1/entities/batch/query', '/api/workbench/v1/entities/batch/facets'].includes(pathname);
  return pathname.startsWith('/api/workbench/') && (method === 'GET' || method === 'POST' && (resourceFacets || batchRead));
}

class Probe {
  constructor(ready, phase) {
    this.ready = ready;
    this.phase = phase;
    this.report = {phase, entry: 'complete_actual_workbench', root: ready.root, build_id: ready.assets.build_id,
      cases: [], steps: [], requests: [], responses: [], errors: [], external: [], screenshots: [], downloads: []};
    this.pending = [];
  }
  save() {
    this.report.summary = {cases: this.report.cases.length, failed: this.report.cases.filter(row => !row.passed).length,
      actions: [...new Set(this.report.cases.filter(row => row.passed).flatMap(row => row.actions))].length,
      screenshots: this.report.screenshots.length, steps: this.report.steps.length};
    fs.writeFileSync(path.join(this.ready.root, 'final-master-' + this.phase + '.json'), JSON.stringify(this.report, null, 2) + '\n');
  }
  snapshot() {
    return JSON.parse(execFileSync(process.env.FINAL_MASTER_PYTHON,
      ['-B', '-m', 'tests.workbench.final_master_fixture_support', 'snapshot', this.ready.root],
      {cwd: path.resolve(__dirname, '../..'), maxBuffer: 64 * 1024 * 1024}));
  }
  attach(page, variant) {
    this.page = page;
    this.variant = variant;
    page.setDefaultTimeout(12000);
    page.on('pageerror', error => this.report.errors.push({variant, kind: 'pageerror', message: error.stack}));
    page.on('console', message => {
      if (message.type() === 'error') this.report.errors.push({variant, kind: 'console', expected: !!this.expectedFailure, message: message.text()});
    });
    page.on('requestfailed', request => {
      const canceledRead = isCanceledRead(request.method(), request.url(), request.failure()?.errorText);
      this.report.errors.push({variant, kind: 'requestfailed', expected: !!this.expectedFailure || canceledRead,
        reason: canceledRead ? 'Canceled read-only request during supersession or closed view; completed reads and visible outcomes are asserted separately' : undefined,
        method: request.method(), url: request.url(), failure: request.failure()});
    });
    page.on('request', request => {
      if (!request.url().startsWith(this.ready.url + '/') && !/^(data:|blob:)/.test(request.url())) this.report.external.push(request.url());
      if (request.url().includes('/api/workbench/')) this.report.requests.push({variant, at: new Date().toISOString(), url: request.url(), method: request.method(), body: request.postData()});
    });
    page.on('response', response => {
      if (!response.url().includes('/api/workbench/')) return;
      const row = {variant, at: new Date().toISOString(), url: response.url(), status: response.status(), expected: !!this.expectedFailure};
      this.report.responses.push(row);
      if (response.headers()['content-type']?.includes('json')) {
        this.pending.push(response.json().then(payload => { row.payload = payload; }, error => {
          row.body_error = error.message;
        }));
      }
    });
  }
  step(method, target, value) {
    this.report.steps.push({variant: this.variant, method, target: String(target), value, at: new Date().toISOString()});
  }
  async click(target) { this.step('click', target); await target.click(); }
  async fill(target, value) { this.step('fill', target, value); await target.fill(String(value)); }
  async type(target, value) {
    this.step('pressSequentially', target, value);
    await target.click(); await target.press('ControlOrMeta+A'); await target.press('Backspace');
    await target.pressSequentially(String(value));
  }
  async press(target, key) { this.step('press', target, key); await target.press(key); }
  async select(target, value) { this.step('selectOption', target, value); await target.selectOption(String(value)); }
  async response(suffix, action, expected = 200) {
    const waiting = this.page.waitForResponse(async row => {
      if (new URL(row.url()).pathname !== suffix) return false;
      return await row.finished() === null;
    });
    const [response] = await Promise.all([waiting, action()]);
    assert.equal(response.status(), expected);
    const body = await response.json();
    if (expected === 200 && body.meta) assert.equal(body.meta.source, 'production');
    return body;
  }
  async shot(name) {
    await this.page.evaluate(() => document.fonts.ready);
    const geometry = await this.page.evaluate(() => ({width: innerWidth, height: innerHeight,
      theme: document.documentElement.dataset.theme, scrollWidth: document.documentElement.scrollWidth,
      dialogs: [...document.querySelectorAll('[role="dialog"]')].filter(node => node.getClientRects().length).map(node => ({
        label: node.getAttribute('aria-label'), rect: node.getBoundingClientRect().toJSON(),
        containsFocus: node.contains(document.activeElement)}))}));
    const file = path.join(this.ready.root, 'screenshots', this.phase + '-' + this.variant + '-' + name + '.png');
    await this.page.screenshot({path: file});
    this.report.screenshots.push({variant: this.variant, file, geometry, V: 'pending_main_review'});
    assert(geometry.scrollWidth <= geometry.width + 1, 'Document horizontal overflow');
    return file;
  }
  async download(name, action) {
    const waiting = this.page.waitForEvent('download');
    await action(); const download = await waiting;
    const file = path.join(this.ready.root, 'downloads', this.phase + '-' + this.variant + '-' + name + path.extname(download.suggestedFilename()));
    await download.saveAs(file); assert.equal(await download.failure(), null);
    const result = JSON.parse(execFileSync(process.env.FINAL_MASTER_PYTHON,
      ['-B', '-m', 'tests.workbench.final_master_fixture_support', 'download', file],
      {cwd: path.resolve(__dirname, '../..'), maxBuffer: 16 * 1024 * 1024}));
    assert(result.bytes > 0); this.report.downloads.push(result);
    return result;
  }
  async run(actions, name, callback, policy = 'read') {
    const start = this.report.steps.length;
    const before = this.snapshot();
    const row = {variant: this.variant, name, actions, policy, passed: false, step_start: start};
    try {
      await callback();
      row.screenshot = await this.shot(name);
      const after = this.snapshot();
      assert.deepEqual(after.schema, before.schema);
      assert.equal(after.integrity, 'ok'); assert.deepEqual(after.foreign_keys, []);
      if (policy === 'read') assert.deepEqual(after.tables, before.tables, 'Read-only flow changed database rows');
      row.before_sha256 = before.sha256; row.after_sha256 = after.sha256;
      row.passed = true;
    } catch (error) {
      row.error = error.stack;
      fs.writeFileSync(path.join(this.ready.root, 'failure-' + this.phase + '-' + this.variant + '-' + name + '.txt'), await this.page.locator('body').innerText());
      console.error('FINAL_MASTER_FAIL ' + name + '\n' + error.stack);
      try { row.failure_screenshot = await this.shot(name + '-FAILED'); }
      catch (captureError) { row.capture_error = captureError.stack; }
    } finally {
      row.step_end = this.report.steps.length;
      this.report.cases.push(row); this.save();
    }
    if (!this.continueOnFailure) assert(row.passed, name + ' failed; see private evidence');
    return row.passed;
  }
}

module.exports = {Probe, isCanceledRead};
