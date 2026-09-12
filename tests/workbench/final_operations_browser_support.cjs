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
  async function request(suffix, run, status = 200, method = 'GET', expectedQuery = null) {
    // An older in-flight refresh can respond after this action has cancelled it.
    const response = page.waitForRequest(r => {
      const url = new URL(r.url());
      return url.pathname === base + suffix && r.method() === method && (!expectedQuery || Object.entries(expectedQuery).every(([key, value]) => (url.searchParams.get(key) || '') === String(value)));
    }).then(r => r.response());
    const [result] = await Promise.all([response, run()]);
    assert(result, 'The action request ended without a response');
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
    const rail = page.locator('.dy-rail');
    if (await rail.isVisible()) return request('/dashboard', () => rail.getByRole('button', { name: new RegExp('^' + label) }).click());
    const picker = page.getByLabel('异常类别', { exact: true });
    const value = await picker.locator('option').filter({ hasText: new RegExp('^' + label + '$') }).getAttribute('value');
    // Native selects do not dispatch change for the current option; explicitly leave and return.
    if (await picker.inputValue() === value) await request('/dashboard', () => select('异常类别', label === '全部风险' ? '交期风险' : '全部风险'));
    return request('/dashboard', () => select('异常类别', label));
  }
  async function revealReference(scope, value) {
    const detail = scope.locator('details.wb-ref:visible').filter({ hasText: value });
    assert.equal(await detail.count(), 1, 'Expected one diagnostic disclosure for the original reference');
    if (await detail.getAttribute('open') === null) await detail.locator('summary').click();
    await detail.getByText(value, { exact: true }).waitFor();
  }
  async function detail(kind, label) {
    await category(label);
    const row = page.locator('tr[data-category="' + kind + '"]').first();
    const ref = await row.getAttribute('data-item-ref');
    const result = await request('/dashboard/items/' + ref, () => row.getByRole('button').click());
    await page.locator('[data-detail-ref="' + ref + '"]').waitFor();
    return result.data.item;
  }
  return { page, config, report, mark, request, select, shot, download, dashboard, category, detail, revealReference, assert };
}
module.exports = { support };
