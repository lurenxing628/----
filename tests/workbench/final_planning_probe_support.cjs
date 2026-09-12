'use strict';
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const { ganttPixels, candidateDetail, formalDetails } = require('./piece_main_visuals.cjs');

function support(page, ready, report, save, flush) {
  const button = (name, scope = page) => scope.getByRole('button', { name, exact: true });
  const last = predicate => {
    const found = report.responses.findLast(row => row.body && row.body.data && predicate(row.body.data, row));
    assert(found, 'The actual browser response must exist'); return found.body.data;
  };
  async function shot(name) {
    const target = path.join(ready.root, 'screenshots', 'final-planning-' + report.mode + '-' + name + '.png');
    await page.screenshot({ path: target, fullPage: true });
    const viewport = target.replace('.png', '-viewport.png'); await page.screenshot({ path: viewport });
    report.screenshots.push({ name, full: target, viewport });
    fs.writeFileSync(target.replace('.png', '.txt'), await page.locator('body').innerText()); save();
    fs.writeFileSync(target.replace('.png', '.html'), await page.locator('body').innerHTML());
  }
  async function action(ids, fn) {
    const before = report.requests.length;
    await fn(); await flush();
    for (const action_id of ids) report.actions.push({ action_id, status: 'passed', request_start: before, request_end: report.requests.length });
    console.log(JSON.stringify({ actions: ids })); save();
  }
  async function caption(ref, identity) {
    const current = page.locator('.wb-current-plan[data-plan-ref="' + ref + '"]');
    await current.waitFor();
    assert.equal(await current.getAttribute('data-plan-ref'), ref);
    const text = await current.innerText();
    assert(text.includes(identity), text);
    if (identity.includes('候选')) assert(!/正式 v\d/.test(text), text);
    report.captions = (report.captions || []).concat({ reference: ref, text });
  }
  async function confirmAdopt(kind, cancel = true) {
    const scope = page.locator(kind === 'candidate' ? '[data-run-adoption-action]' : '.trial-adoption-action');
    async function openPreview() {
      const response = page.waitForResponse(row => row.url().endsWith('/adopt-preview') && row.request().method() === 'POST');
      await button(kind === 'candidate' ? '采用方案' : '正式采用', scope).click();
      const preview = await (await response).json();
      assert.equal(preview.data.validation.can_adopt, true, JSON.stringify(preview));
      await flush();
    }
    await openPreview();
    let dialog = page.getByRole('dialog');
    await dialog.getByLabel('采用原因', { exact: true }).waitFor();
    const bounds = await dialog.evaluate(node => {
      const box = node.getBoundingClientRect();
      return { left: box.left, right: box.right, top: box.top, bottom: box.bottom,
        viewportWidth: innerWidth, viewportHeight: innerHeight, focusedInside: node.contains(document.activeElement) };
    });
    assert(bounds.left >= 0 && bounds.right <= bounds.viewportWidth && bounds.top >= 0 && bounds.bottom <= bounds.viewportHeight);
    await dialog.getByLabel('采用原因', { exact: true }).press('Tab');
    assert(await dialog.evaluate(node => node.contains(document.activeElement)), 'Modal keyboard focus must remain inside');
    report.modals = (report.modals || []).concat({ kind, ...bounds, tab_focus_inside: true });
    if (cancel) {
      const writes = report.requests.filter(row => /\/adopt$/.test(row.url)).length;
      await button('取消', dialog).click(); await flush();
      assert.equal(report.requests.filter(row => /\/adopt$/.test(row.url)).length, writes);
      await openPreview(); dialog = page.getByRole('dialog');
    }
    await dialog.getByLabel('采用原因', { exact: true }).fill('任务D真实全入口验收，保留原身份与完整范围');
    await dialog.getByLabel('声明人', { exact: true }).fill('D acceptance');
    await dialog.getByRole('checkbox').check();
    await button('确认正式采用', dialog).click();
    await button('进入正式方案', dialog).waitFor(); await shot(kind + '-adopted');
    await button('进入正式方案', dialog).click();
    await page.locator('[data-plan-workspace] .plan-main').waitFor(); await flush();
    return last(data => data.plan && data.tasks);
  }
  async function createTrial(fromTask = false) {
    await (fromTask ? button('调整此工序', page.locator('[data-plan-inspector]')) : button('试调', page.locator('.plan-heading').first())).click();
    const dialog = page.getByRole('dialog');
    await button('核对原来源', dialog).click();
    await dialog.getByRole('checkbox', { name: '确认基于此来源创建独立草稿，正式计划保持不变', exact: true }).check();
    await button('确认创建草稿', dialog).click();
    await page.locator('[data-trial-workspace] .tt-main').waitFor();
    await page.getByRole('tab', { name: '完整任务', exact: true }).click(); await flush();
    return last(data => data.draft_ref && data.tasks && !data.scenario_ref);
  }
  async function selectTrial(sequence, piece = null, batch = 'B1') {
    await page.getByRole('tab', { name: '完整任务', exact: true }).click();
    let row = page.getByRole('table', { name: '完整任务明细', exact: true }).getByRole('row')
      .filter({ has: button(batch + ' · Turning ' + sequence) });
    if (piece) row = row.filter({ hasText: piece });
    assert.equal(await row.count(), 1); await row.getByRole('button').click();
  }
  return { button, last, shot, action, caption, confirmAdopt, createTrial, selectTrial,
    pixels: (selector, name) => ganttPixels(page, selector, name, report),
    candidateDetail: () => candidateDetail(page, report, (_page, name) => shot(name)),
    formalDetails: async () => {
      try { await formalDetails(page, report, (_page, name) => shot(name)); }
      catch (error) {
        report.formal_match_debug = await page.getByRole('button', { name: /^B1 · 20 Turning[\s\S]*分件 item-A/ }).evaluateAll(nodes =>
          nodes.map(node => ({ html: node.outerHTML, workspace: node.closest('[data-plan-workspace]') !== null, lane: node.closest('.plan-lane')?.outerHTML })));
        save(); throw error;
      }
    } };
}
module.exports = { support };
