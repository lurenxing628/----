'use strict';
const assert = require('node:assert/strict');

async function predecessorLinks(page, table, report, screenshot) {
  const detail = page.getByRole('complementary', { name: '工序详情', exact: true });
  const links = detail.getByRole('button', { name: /^前序/ });
  const names = await links.allTextContents();
  const pieces = report.pieces;
  await screenshot(page, 'trial-common-predecessor-links');
  report.predecessor_links = { names, targets: [] };
  const geometry = await links.evaluateAll(nodes => nodes.map(node => {
    const box = node.getBoundingClientRect(), parent = node.closest('.tt-detail').getBoundingClientRect();
    return { width: box.width, height: box.height, right: box.right, parentRight: parent.right,
      scrollWidth: node.scrollWidth, clientWidth: node.clientWidth, scrollHeight: node.scrollHeight, clientHeight: node.clientHeight };
  }));
  report.predecessor_links.geometry = geometry;
  assert(geometry.every(row => row.right <= row.parentRight + 1 && row.scrollWidth <= row.clientWidth + 1
    && row.scrollHeight <= row.clientHeight + 1), 'Long predecessor labels must fit without clipping or overflow');
  if (names.length !== 3 || pieces.some(piece => names.filter(name => name.includes(piece)).length !== 1)) {
    report.findings.push({ id: 'EQ-TRIAL-PREDECESSOR-IDENTITY', names,
      message: 'Common join predecessor links must identify their individual pieces before clicking',
      source: 'frontend/workbench/app/TrialDetails.jsx', screenshot: report.screenshots.at(-1) });
    return;
  }
  for (const [index, piece] of pieces.entries()) {
    await links.filter({ hasText: piece }).click();
    const selected = await page.locator('.tt-task-label[aria-pressed="true"]').innerText();
    assert(selected.includes(piece) && selected.includes('30'), 'Predecessor link selected a different piece/stage');
    report.predecessor_links.targets.push({ piece, selected });
    await screenshot(page, 'trial-predecessor-target-identity-' + (index + 1));
    await table.getByRole('button', { name: 'B1 · Turning 40', exact: true }).click();
  }
}
module.exports = { predecessorLinks };
