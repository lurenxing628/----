'use strict';
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');

function support(page, config, report) {
  const base = '/api/workbench/v1';
  async function mark(ids, run) {
    const before = report.responses.length;
    const value = await run();
    for (const action_id of Array.isArray(ids) ? ids : [ids]) report.actions.push({ action_id, kind: 'K', response_start: before, response_end: report.responses.length });
    return value;
  }
  async function request(suffix, run, status = 200, method = 'GET') {
    const response = page.waitForResponse(r => new URL(r.url()).pathname === base + suffix && r.request().method() === method);
    await run(); const result = await response;
    assert.equal(result.status(), status, await result.text());
    return result.json();
  }
  async function select(label, choice, scope = page) {
    await scope.getByLabel(label, { exact: true }).click();
    await page.locator('.wb-control-popup').getByRole('option', { name: choice, exact: true }).click();
  }
  async function shot(name) {
    const file = path.join(config.output, name + '.png');
    await page.screenshot({ path: file, animations: 'disabled' });
    const geometry = await page.evaluate(() => ({ viewport: { width: innerWidth, height: innerHeight },
      scrollWidth: document.documentElement.scrollWidth, theme: document.documentElement.dataset.theme,
      main: document.querySelector('main') ? document.querySelector('main').innerText.slice(0, 300) : null }));
    assert(geometry.scrollWidth <= config.viewport.width + 1, JSON.stringify(geometry));
    report.screenshots.push({ file, geometry, main_visual_review: 'pending' });
  }
  async function download(label, name, scope = page) {
    const event = page.waitForEvent('download'); await scope.getByRole('button', { name: label, exact: true }).click();
    const value = await event, target = path.join(config.output, name); await value.saveAs(target);
    assert.equal(await value.failure(), null); assert(fs.statSync(target).size > 0);
    report.downloads.push({ path: target, suggested: value.suggestedFilename(), bytes: fs.statSync(target).size });
    return target;
  }
  async function dashboard() {
    await page.goto(config.origin + '/workbench?view=dashboard');
    await page.locator('[data-dashboard-workspace][data-ready=true]').waitFor();
  }
  async function category(label) {
    return request('/dashboard', () => page.locator('.dy-rail').getByRole('button', { name: new RegExp('^' + label) }).click());
  }
  async function detail(kind, label) {
    await category(label);
    const row = page.locator('tr[data-category="' + kind + '"]').first();
    const ref = await row.getAttribute('data-item-ref');
    const result = await request('/dashboard/items/' + ref, () => row.getByRole('button').click());
    await page.locator('[data-detail-ref="' + ref + '"]').waitFor();
    return result.data.item;
  }
  return { page, config, report, mark, request, select, shot, download, dashboard, category, detail, assert };
}
module.exports = { support };
