const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const assert = require('node:assert/strict');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

class Probe {
  constructor(page, ready, report, state) {
    Object.assign(this, { page, ready, report, state });
    this.work = page.locator('.rw-workbench');
    this.data = null;
  }
  async shot(name, fullPage = false) {
    const file = path.join(this.ready.root, 'screenshots', this.state + '-' + name + '.png');
    await this.page.screenshot({ path: file, fullPage });
    this.report.screenshots.push(file);
  }
  async step(name, run) {
    const row = { state: this.state, name, passed: false };
    this.report.cases.push(row);
    try { await run(); row.passed = true; }
    catch (error) { row.error = error.stack; await this.shot('failed-' + this.report.cases.length); throw error; }
  }
  async choose(label, value, owner = this.work) {
    const select = owner.getByLabel(label, { exact: true });
    const text = await select.locator('option').evaluateAll((options, expected) => {
      const option = options.find(item => item.value === expected);
      if (!option) throw new Error('Missing option: ' + expected);
      return option.textContent;
    }, value);
    await select.click();
    await this.page.getByRole('listbox', { name: label, exact: true }).getByRole('option', { name: text, exact: true }).click();
  }
  async read(action, endpoint = '/api/workbench/v1/analytics', expectedStatus = 200, expectedPage = null) {
    const pending = this.page.waitForResponse(response => {
      const url = new URL(response.url());
      return url.pathname === endpoint && (expectedPage === null || url.searchParams.get('page') === String(expectedPage));
    }).then(response => ({ response }), error => ({ error }));
    await action();
    const outcome = await pending; if (outcome.error) throw outcome.error;
    const response = outcome.response;
    assert.equal(response.status(), expectedStatus, await response.text());
    const payload = await response.json();
    this.report.responses.push({ state: this.state, url: response.url(), status: response.status(), payload });
    if (expectedStatus === 200) {
      assert.equal(payload.ok, true);
      assert.equal(payload.meta.source, 'production');
      if (endpoint === '/api/workbench/v1/analytics') {
        await this.work.locator('#report-topic-panel').waitFor();
        this.data = payload;
        await this.checkRows();
      }
    }
    return payload;
  }
  async checkRows() {
    const data = this.data.data;
    if (!data.rows.length) { await this.work.locator('#report-topic-panel .rw-list-pane > .wb-empty').waitFor(); return; }
    const table = this.work.locator('#report-topic-panel .rw-primary-table');
    await table.locator('tbody tr').first().waitFor();
    assert.equal(await table.locator('tbody tr').count(), data.rows.length);
    const texts = await table.locator('tbody tr').allTextContents();
    for (let index = 0; index < texts.length; index++) {
      const row = data.rows[index];
      assert(texts[index].includes(row.operation_label || row.resource_label));
    }
  }
  async geometry(name) {
    const result = await this.work.evaluate(root => {
      const rect = node => { const r = node.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height, right: r.right, bottom: r.bottom }; };
      const style = node => ({ background: getComputedStyle(node).backgroundColor, shadow: getComputedStyle(node).boxShadow, ...rect(node) });
      const fields = [...root.querySelectorAll('.aw-scope-main input,.aw-scope-main select,.aw-scope-tools button,.rw-table-heading input,.rw-table-heading select,.rw-table-heading button')]
        .filter(node => node.getClientRects().length).map(node => ({ label: node.getAttribute('aria-label') || node.textContent, ...rect(node) }));
      const collisions = [];
      for (let i = 0; i < fields.length; i++) for (let j = i + 1; j < fields.length; j++) {
        const a = fields[i], b = fields[j];
        if (Math.min(a.right, b.right) - Math.max(a.x, b.x) > 1 && Math.min(a.bottom, b.bottom) - Math.max(a.y, b.y) > 1) collisions.push([a.label, b.label]);
      }
      const table = root.querySelector('#report-topic-panel .rw-primary-table');
      return { theme: document.documentElement.dataset.theme, documentWidth: document.documentElement.scrollWidth, viewportWidth: innerWidth,
        workspace: style(root), metrics: style(root.querySelector('.rw-metrics')), fields, collisions,
        table: table ? { ...style(table), scrollWidth: table.scrollWidth, clientWidth: table.clientWidth, scrollHeight: table.scrollHeight, clientHeight: table.clientHeight } : null,
        metricTones: [...root.querySelectorAll('.wb-metric')].map(node => ({ tone: node.dataset.tone, value: node.querySelector('.wb-metric-value').textContent, color: getComputedStyle(node.querySelector('.wb-metric-value')).color })) };
    });
    this.report.geometry.push({ state: this.state, name, ...result });
    assert(result.documentWidth <= result.viewportWidth, 'Page-level horizontal overflow');
    assert.deepEqual(result.collisions, []);
    assert.equal(result.workspace.shadow, 'none');
    assert.equal(result.metrics.background, 'rgba(0, 0, 0, 0)');
    assert.equal(result.theme, this.state.endsWith('dark') ? 'dark' : 'light');
    for (const field of result.fields) assert(field.width >= 30 && field.height >= 30, field.label);
  }
  async download(button, owner = this.work) {
    const waiting = this.page.waitForEvent('download');
    const responsePending = this.page.waitForResponse(response => new URL(response.url()).pathname.endsWith('/export'));
    await owner.getByRole('button', { name: button, exact: true }).click();
    const [download, response] = await Promise.all([waiting, responsePending]);
    assert.equal(response.status(), 200);
    const file = path.join(this.ready.root, 'downloads', this.state + '-' + this.report.downloads.length + '-' + download.suggestedFilename());
    await download.saveAs(file);
    const bytes = fs.readFileSync(file);
    assert.equal(bytes.length, Number(response.headers()['content-length']));
    this.report.downloads.push({ state: this.state, path: file, filename: download.suggestedFilename(),
      url: response.url(), sha256: hash(bytes), bytes: bytes.length, headers: await response.allHeaders() });
  }
}
module.exports = { Probe, hash };
