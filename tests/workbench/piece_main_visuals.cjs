'use strict';
const assert = require('node:assert/strict');

async function ganttPixels(page, scope, label, report) {
  const measured = await page.locator(scope).evaluate(node => {
    const bounds = node.getBoundingClientRect();
    const canvases = Array.from(node.querySelectorAll('canvas')).map(canvas => {
      const rect = canvas.getBoundingClientRect(), bytes = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
      let nontransparent = 0; const colors = new Set();
      for (let index = 0; index < bytes.length; index += 4) {
        if (bytes[index + 3]) { nontransparent++; colors.add(bytes.slice(index, index + 4).join(',')); }
      }
      return { width: rect.width, height: rect.height, nontransparent, colors: colors.size };
    });
    const bars = Array.from(node.querySelectorAll('.tt-bar')).map(bar => {
      const rect = bar.getBoundingClientRect(); return { width: rect.width, height: rect.height, title: bar.title };
    });
    const main = document.querySelector('.main-content').getBoundingClientRect(), sidebar = document.querySelector('.sidebar').getBoundingClientRect();
    return { width: bounds.width, canvases, bars, documentWidth: document.documentElement.scrollWidth,
      viewportWidth: innerWidth, sidebarRight: sidebar.right, mainLeft: main.left };
  });
  assert(measured.width > 200, label + ' must have a real framed width');
  assert(measured.documentWidth <= measured.viewportWidth + 1, label + ' must not overflow the outer viewport');
  assert(measured.mainLeft >= measured.sidebarRight - 1, label + ' main/sidebar overlap');
  assert(measured.canvases.length || measured.bars.length, label + ' must render actual time bars');
  if (measured.canvases.length) assert(measured.canvases.some(row => row.nontransparent > 500 && row.colors > 2), label + ' canvas is blank');
  if (measured.bars.length) assert(measured.bars.every(row => row.width > 0 && row.height > 0), label + ' has invisible positive-duration work');
  report.visuals = (report.visuals || []).concat({ label, ...measured });
}

async function candidateDetail(page, report, screenshot) {
  const list = page.getByRole('table', { name: '候选任务安排', exact: true });
  const common = list.locator('.rc-list-row').filter({ has: page.getByText(/^40\s+Turning(?:\s|$)/) });
  await common.getByRole('button').click();
  let facts = await visibleFacts(page, '.rc-detail');
  assert.equal(facts['本工序目标量'], '3'); assert.equal(facts['生成时整批量'], '3');
  await screenshot(page, 'candidate-common-detail');
  const split = list.locator('.rc-list-row').filter({ has: page.getByText(/^20\s+Turning(?:\s|$)/) });
  for (const [index, piece] of report.pieces.entries()) {
    const row = split.filter({ hasText: '分件 ' + piece });
    if (await row.count() !== 1) {
      report.findings.push({ id: 'EQ-CANDIDATE-VISIBLE-IDENTITY', piece, message: 'Cannot select the piece by its displayed business identity' });
      continue;
    }
    await row.getByRole('button').click();
    facts = await visibleFacts(page, '.rc-detail');
    assert.equal(facts['分件'], piece); assert.equal(facts['本工序目标量'], '1'); assert.equal(facts['生成时整批量'], '3');
    await screenshot(page, 'candidate-detail-identity-' + (index + 1));
  }
  report.candidate_detail_rows_observed = await split.count();
}

async function visibleFacts(page, selector) {
  return page.locator(selector).evaluate(node => Object.fromEntries(Array.from(node.querySelectorAll('dt')).map(dt => [dt.textContent, dt.nextElementSibling.textContent])));
}

async function formalDetails(page, report, screenshot) {
  for (const [index, piece] of report.pieces.entries()) {
    const bar = page.getByRole('button', { name: new RegExp('^B1 · 20 Turning[\\s\\S]*分件 ' + piece) });
    assert.equal(await bar.count(), 1, 'Formal Gantt piece selection must use visible/accessibility business identity');
    await bar.click();
    const facts = await visibleFacts(page, '[data-plan-inspector]');
    assert(facts['分件'].includes(piece)); assert.equal(facts['本工序目标量'], '1.00'); assert.equal(facts['计划来源整批量'], '3.00');
    await screenshot(page, 'formal-detail-identity-' + (index + 1));
  }
  report.formal_detail_pieces_verified = 3;
}
module.exports = { ganttPixels, candidateDetail, formalDetails };
